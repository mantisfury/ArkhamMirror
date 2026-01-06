"""API endpoints for the Graph Shard."""

import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request, Body
from pydantic import BaseModel

from .models import (
    BuildGraphRequest,
    PathRequest,
    PathResponse,
    CentralityRequest,
    CentralityResponse,
    CommunityRequest,
    CommunityResponse,
    NeighborsRequest,
    ExportRequest,
    ExportResponse,
    FilterRequest,
    GraphResponse,
    ExportFormat,
    CentralityMetric,
    ScoreConfigRequest,
    ScoreResponse as ScoreResponseModel,
    EntityScoreResponse,
)
from .scoring import CompositeScorer, ScoreConfig
from .layouts import LayoutEngine, LayoutType, HierarchicalDirection
from .temporal import TemporalGraphEngine, TemporalSnapshot, EvolutionMetrics
from .flows import FlowAnalyzer

if TYPE_CHECKING:
    from .shard import GraphShard

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/graph", tags=["graph"])

# Shard components (injected by init_api)
_builder = None
_algorithms = None
_exporter = None
_storage = None
_event_bus = None
_scorer = None
_layout_engine = None
_temporal_engine = None
_db_service = None
_flow_analyzer = None


# === Helper to get shard instance ===

def get_shard(request: Request) -> "GraphShard":
    """Get the graph shard instance from app state."""
    shard = getattr(request.app.state, "graph_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Graph shard not available")
    return shard


def init_api(builder, algorithms, exporter, storage=None, event_bus=None, scorer=None, layout_engine=None, db_service=None):
    """
    Initialize API with shard components.

    Args:
        builder: GraphBuilder instance
        algorithms: GraphAlgorithms instance
        exporter: GraphExporter instance
        storage: Optional storage service
        event_bus: Optional event bus service
        scorer: Optional CompositeScorer instance
        layout_engine: Optional LayoutEngine instance
        db_service: Optional database service for temporal queries
    """
    global _builder, _algorithms, _exporter, _storage, _event_bus, _scorer, _layout_engine, _temporal_engine, _db_service, _flow_analyzer

    _builder = builder
    _algorithms = algorithms
    _exporter = exporter
    _storage = storage
    _event_bus = event_bus
    _scorer = scorer or CompositeScorer()
    _layout_engine = layout_engine or LayoutEngine()
    _db_service = db_service
    _temporal_engine = TemporalGraphEngine(db_service=db_service) if db_service else None
    _flow_analyzer = FlowAnalyzer()

    logger.info("Graph API initialized")


# --- Endpoints ---


# ========== Scoring Endpoints (must be before /{project_id} catch-all) ==========


@router.post("/scores")
async def calculate_scores(request: ScoreConfigRequest) -> ScoreResponseModel:
    """
    Calculate composite importance scores for all entities.

    Combines multiple signals:
    - Centrality (PageRank, betweenness, eigenvector, HITS, closeness)
    - Frequency (TF-IDF style rarity weighting)
    - Recency (exponential time decay)
    - Credibility (source reliability from credibility shard)
    - Corroboration (multiple independent sources)

    Returns entities ranked by composite score.
    """
    if not _scorer:
        raise HTTPException(status_code=503, detail="Scoring service not available")

    try:
        start_time = datetime.utcnow()

        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Build config
        config = ScoreConfig(
            centrality_type=request.centrality_type,
            centrality_weight=request.centrality_weight,
            frequency_weight=request.frequency_weight,
            recency_weight=request.recency_weight,
            credibility_weight=request.credibility_weight,
            corroboration_weight=request.corroboration_weight,
            recency_half_life_days=request.recency_half_life_days,
            entity_type_weights=request.entity_type_weights or {},
        )

        # TODO: Fetch entity mentions from database for frequency/recency/corroboration
        # For now, use node properties
        entity_mentions: dict[str, list[dict]] = {}

        # TODO: Fetch credibility ratings from credibility shard
        # For now, use empty dict (neutral scores)
        credibility_ratings: dict[str, float] = {}

        # Calculate scores
        scores = _scorer.calculate_scores(
            graph=graph,
            config=config,
            entity_mentions=entity_mentions,
            credibility_ratings=credibility_ratings,
        )

        # Limit results
        scores = scores[:request.limit]

        calculation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Build response
        score_responses = [
            EntityScoreResponse(
                entity_id=s.entity_id,
                label=s.label,
                entity_type=s.entity_type,
                composite_score=s.composite_score,
                centrality_score=s.centrality_score,
                frequency_score=s.frequency_score,
                recency_score=s.recency_score,
                credibility_score=s.credibility_score,
                corroboration_score=s.corroboration_score,
                rank=s.rank,
                degree=s.degree,
                document_count=s.document_count,
                source_count=s.source_count,
            )
            for s in scores
        ]

        return ScoreResponseModel(
            project_id=request.project_id,
            scores=score_responses,
            config={
                "centrality_type": config.centrality_type,
                "weights": config.normalized_weights(),
                "recency_half_life_days": config.recency_half_life_days,
            },
            calculation_time_ms=calculation_time,
            entity_count=len(scores),
        )

    except Exception as e:
        logger.error(f"Error calculating scores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores/{project_id}")
async def get_scores(
    project_id: str,
    centrality_type: str = Query("pagerank", description="Centrality algorithm"),
    limit: int = Query(100, ge=1, le=500),
) -> ScoreResponseModel:
    """
    Get composite scores with default configuration.

    Simplified endpoint for quick score retrieval.
    """
    # Use default config
    request = ScoreConfigRequest(
        project_id=project_id,
        centrality_type=centrality_type,
        limit=limit,
    )
    return await calculate_scores(request)


# ========== Layout Calculation ==========


class LayoutRequest(BaseModel):
    """Request for layout calculation."""
    project_id: str
    layout_type: str = "hierarchical"  # hierarchical, radial, circular, tree, bipartite, grid
    root_node_id: str | None = None
    direction: str = "TB"  # TB, BT, LR, RL (for hierarchical/tree)
    # Layout-specific options
    layer_spacing: float = 100
    node_spacing: float = 50
    radius: float = 300  # For circular
    radius_step: float = 100  # For radial
    # Bipartite options
    left_types: list[str] | None = None
    right_types: list[str] | None = None
    # Grid options
    columns: int | None = None
    cell_width: float = 100
    cell_height: float = 100


@router.post("/layout")
async def calculate_layout(request: LayoutRequest) -> dict[str, Any]:
    """
    Calculate node positions for specified layout algorithm.

    Returns pre-calculated positions that the frontend can use
    instead of force simulation.

    Layout types:
    - hierarchical: Sugiyama-style layered layout (good for org charts)
    - radial: Concentric circles from center node (good for ego networks)
    - circular: All nodes on a circle (good for small graphs)
    - tree: Reingold-Tilford tree layout (good for tree structures)
    - bipartite: Two-column layout by entity type (good for document-entity)
    - grid: Simple grid layout (good for overview)
    """
    if not _layout_engine:
        raise HTTPException(status_code=503, detail="Layout engine not available")

    try:
        start_time = datetime.utcnow()

        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Validate layout type
        try:
            layout_type = LayoutType(request.layout_type)
        except ValueError:
            valid_types = [lt.value for lt in LayoutType if lt != LayoutType.FORCE_DIRECTED]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid layout type: {request.layout_type}. Valid types: {valid_types}"
            )

        # Force-directed should be handled by frontend
        if layout_type == LayoutType.FORCE_DIRECTED:
            raise HTTPException(
                status_code=400,
                detail="Force-directed layout is handled by the frontend"
            )

        # Build options dict
        options = {
            "root_node_id": request.root_node_id,
            "direction": request.direction,
            "layer_spacing": request.layer_spacing,
            "node_spacing": request.node_spacing,
            "radius": request.radius,
            "radius_step": request.radius_step,
            "left_types": request.left_types or ["document"],
            "right_types": request.right_types or ["person", "organization", "location"],
            "columns": request.columns,
            "cell_width": request.cell_width,
            "cell_height": request.cell_height,
            "level_spacing": request.layer_spacing,  # For tree layout
            "sibling_spacing": request.node_spacing,  # For tree layout
            "vertical_spacing": request.node_spacing,  # For bipartite layout
            "spacing": request.layer_spacing * 3,  # Column spacing for bipartite
        }

        # Calculate layout
        result = _layout_engine.calculate_layout(graph, layout_type, options)

        calculation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        response = result.to_dict()
        response["calculation_time_ms"] = calculation_time
        response["node_count"] = len(result.positions)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating layout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/layout/types")
async def get_layout_types() -> dict[str, Any]:
    """
    Get available layout types and their descriptions.
    """
    return {
        "layout_types": [
            {
                "id": "force",
                "name": "Force-Directed",
                "description": "Physics simulation that clusters connected nodes. Best for general exploration.",
                "frontend_only": True,
            },
            {
                "id": "hierarchical",
                "name": "Hierarchical",
                "description": "Layered layout showing hierarchy levels. Best for org charts and command structures.",
                "options": ["root_node_id", "direction", "layer_spacing", "node_spacing"],
            },
            {
                "id": "radial",
                "name": "Radial",
                "description": "Concentric circles from a center node. Best for ego networks and influence mapping.",
                "options": ["center_node_id", "radius_step"],
            },
            {
                "id": "circular",
                "name": "Circular",
                "description": "All nodes arranged on a circle. Best for small networks and community overview.",
                "options": ["radius"],
            },
            {
                "id": "tree",
                "name": "Tree",
                "description": "Classic tree structure. Best for tree-shaped data without cycles.",
                "options": ["root_node_id", "direction", "level_spacing", "sibling_spacing"],
            },
            {
                "id": "bipartite",
                "name": "Bipartite",
                "description": "Two-column layout by entity type. Best for document-entity relationships.",
                "options": ["left_types", "right_types", "spacing"],
            },
            {
                "id": "grid",
                "name": "Grid",
                "description": "Simple grid arrangement. Best for overview of many nodes.",
                "options": ["columns", "cell_width", "cell_height"],
            },
        ]
    }


# ========== Temporal Graph Analysis ==========


class TemporalSnapshotsRequest(BaseModel):
    """Request for temporal snapshots."""
    project_id: str
    start_date: str | None = None  # ISO format
    end_date: str | None = None    # ISO format
    interval_days: int = 7
    cumulative: bool = True
    max_snapshots: int = 50


@router.get("/temporal/range")
async def get_temporal_range(
    project_id: str = Query(...),
) -> dict[str, Any]:
    """
    Get available time range for temporal analysis.

    Returns the earliest and latest dates with data,
    suggested interval, and expected number of snapshots.
    """
    if not _temporal_engine:
        raise HTTPException(status_code=503, detail="Temporal engine not available")

    try:
        temporal_range = await _temporal_engine.get_temporal_range(project_id)

        if not temporal_range:
            return {
                "available": False,
                "message": "No temporal data available for this project",
            }

        return {
            "available": True,
            **temporal_range.to_dict(),
        }

    except Exception as e:
        logger.error(f"Error getting temporal range: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/temporal/snapshots")
async def get_temporal_snapshots(request: TemporalSnapshotsRequest) -> dict[str, Any]:
    """
    Generate graph snapshots at regular time intervals.

    Returns a series of snapshots showing how the network evolved,
    including added/removed nodes and edges between each snapshot.

    Use cumulative=True (default) for all data up to each point,
    or cumulative=False for only data within each time window.
    """
    if not _temporal_engine:
        raise HTTPException(status_code=503, detail="Temporal engine not available")

    try:
        from datetime import timedelta

        start_time = datetime.utcnow()

        # Parse dates if provided
        start_date = None
        end_date = None

        if request.start_date:
            start_date = datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        if request.end_date:
            end_date = datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))

        interval = timedelta(days=request.interval_days)

        # Generate snapshots
        snapshots = await _temporal_engine.generate_snapshots(
            project_id=request.project_id,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            cumulative=request.cumulative,
            max_snapshots=request.max_snapshots,
        )

        # Calculate evolution metrics
        metrics = _temporal_engine.calculate_evolution_metrics(snapshots)

        calculation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return {
            "project_id": request.project_id,
            "snapshot_count": len(snapshots),
            "snapshots": [s.to_dict() for s in snapshots],
            "evolution_metrics": metrics.to_dict(),
            "cumulative": request.cumulative,
            "interval_days": request.interval_days,
            "calculation_time_ms": calculation_time,
        }

    except Exception as e:
        logger.error(f"Error generating temporal snapshots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/snapshot/{timestamp}")
async def get_snapshot_at_time(
    timestamp: str,
    project_id: str = Query(...),
    cumulative: bool = Query(True),
    window_days: int = Query(7, description="Window size if not cumulative"),
) -> dict[str, Any]:
    """
    Get a single graph snapshot at a specific timestamp.

    Args:
        timestamp: ISO format timestamp
        project_id: Project ID
        cumulative: Include all data up to this point (default: True)
        window_days: If not cumulative, window size in days
    """
    if not _temporal_engine:
        raise HTTPException(status_code=503, detail="Temporal engine not available")

    try:
        from datetime import timedelta

        # Parse timestamp
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        window_size = timedelta(days=window_days) if not cumulative else None

        snapshot = await _temporal_engine.get_snapshot_at(
            project_id=project_id,
            timestamp=ts,
            cumulative=cumulative,
            window_size=window_size,
        )

        return {
            "project_id": project_id,
            "snapshot": snapshot.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {e}")
    except Exception as e:
        logger.error(f"Error getting snapshot at {timestamp}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/evolution")
async def get_evolution_metrics(
    project_id: str = Query(...),
    interval_days: int = Query(7),
    max_snapshots: int = Query(50),
) -> dict[str, Any]:
    """
    Get evolution metrics without full snapshot data.

    Lighter-weight endpoint for getting just the metrics
    about how the network has evolved over time.
    """
    if not _temporal_engine:
        raise HTTPException(status_code=503, detail="Temporal engine not available")

    try:
        from datetime import timedelta

        snapshots = await _temporal_engine.generate_snapshots(
            project_id=project_id,
            interval=timedelta(days=interval_days),
            cumulative=True,
            max_snapshots=max_snapshots,
        )

        metrics = _temporal_engine.calculate_evolution_metrics(snapshots)

        # Build timeline summary (without full node/edge data)
        timeline = [
            {
                "timestamp": s.timestamp.isoformat(),
                "node_count": s.node_count,
                "edge_count": s.edge_count,
                "added_nodes": len(s.added_nodes),
                "removed_nodes": len(s.removed_nodes),
                "added_edges": len(s.added_edges),
                "removed_edges": len(s.removed_edges),
                "density": s.density,
            }
            for s in snapshots
        ]

        return {
            "project_id": project_id,
            "metrics": metrics.to_dict(),
            "timeline": timeline,
            "snapshot_count": len(snapshots),
        }

    except Exception as e:
        logger.error(f"Error getting evolution metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Relationship Types ==========


# Relationship type metadata for frontend
RELATIONSHIP_TYPE_METADATA = {
    # Basic relationships
    "works_for": {"category": "organizational", "label": "Works For", "color": "#3b82f6", "directed": True},
    "affiliated_with": {"category": "organizational", "label": "Affiliated With", "color": "#8b5cf6", "directed": False},
    "located_in": {"category": "spatial", "label": "Located In", "color": "#10b981", "directed": True},
    "mentioned_with": {"category": "basic", "label": "Mentioned With", "color": "#6b7280", "directed": False},
    "related_to": {"category": "basic", "label": "Related To", "color": "#6b7280", "directed": False},
    "temporal": {"category": "temporal", "label": "Temporal", "color": "#f59e0b", "directed": True},
    "hierarchical": {"category": "organizational", "label": "Hierarchical", "color": "#3b82f6", "directed": True},

    # Organizational relationships
    "owns": {"category": "organizational", "label": "Owns", "color": "#059669", "directed": True},
    "founded": {"category": "organizational", "label": "Founded", "color": "#0891b2", "directed": True},
    "employed_by": {"category": "organizational", "label": "Employed By", "color": "#3b82f6", "directed": True},
    "member_of": {"category": "organizational", "label": "Member Of", "color": "#6366f1", "directed": True},
    "reports_to": {"category": "organizational", "label": "Reports To", "color": "#7c3aed", "directed": True},
    "subsidiary_of": {"category": "organizational", "label": "Subsidiary Of", "color": "#2563eb", "directed": True},
    "partner_of": {"category": "organizational", "label": "Partner Of", "color": "#4f46e5", "directed": False},

    # Personal relationships
    "married_to": {"category": "personal", "label": "Married To", "color": "#ec4899", "directed": False},
    "child_of": {"category": "personal", "label": "Child Of", "color": "#f472b6", "directed": True},
    "parent_of": {"category": "personal", "label": "Parent Of", "color": "#db2777", "directed": True},
    "sibling_of": {"category": "personal", "label": "Sibling Of", "color": "#e879f9", "directed": False},
    "relative_of": {"category": "personal", "label": "Relative Of", "color": "#d946ef", "directed": False},
    "knows": {"category": "personal", "label": "Knows", "color": "#a855f7", "directed": False},
    "friend_of": {"category": "personal", "label": "Friend Of", "color": "#c084fc", "directed": False},

    # Interaction relationships
    "communicated_with": {"category": "interaction", "label": "Communicated With", "color": "#14b8a6", "directed": False},
    "met_with": {"category": "interaction", "label": "Met With", "color": "#06b6d4", "directed": False},
    "transacted_with": {"category": "interaction", "label": "Transacted With", "color": "#22c55e", "directed": False},
    "collaborated_with": {"category": "interaction", "label": "Collaborated With", "color": "#84cc16", "directed": False},

    # Spatial relationships
    "visited": {"category": "spatial", "label": "Visited", "color": "#f97316", "directed": True},
    "resides_in": {"category": "spatial", "label": "Resides In", "color": "#fb923c", "directed": True},
    "headquartered_in": {"category": "spatial", "label": "Headquartered In", "color": "#ea580c", "directed": True},
    "traveled_to": {"category": "spatial", "label": "Traveled To", "color": "#fdba74", "directed": True},

    # Temporal relationships
    "preceded_by": {"category": "temporal", "label": "Preceded By", "color": "#eab308", "directed": True},
    "followed_by": {"category": "temporal", "label": "Followed By", "color": "#facc15", "directed": True},
    "concurrent_with": {"category": "temporal", "label": "Concurrent With", "color": "#fde047", "directed": False},

    # Cross-shard relationship types
    "contradicts": {"category": "analysis", "label": "Contradicts", "color": "#ef4444", "directed": False, "dash": [5, 5]},
    "supports": {"category": "analysis", "label": "Supports", "color": "#22c55e", "directed": False},
    "pattern_match": {"category": "analysis", "label": "Pattern Match", "color": "#a855f7", "directed": False, "dash": [3, 3]},
    "derived_from": {"category": "analysis", "label": "Derived From", "color": "#64748b", "directed": True},
    "evidence_for": {"category": "analysis", "label": "Evidence For", "color": "#16a34a", "directed": True},
    "evidence_against": {"category": "analysis", "label": "Evidence Against", "color": "#dc2626", "directed": True},

    # Co-occurrence (default)
    "co_occurrence": {"category": "basic", "label": "Co-occurrence", "color": "#94a3b8", "directed": False},
}


@router.get("/relationship-types")
async def get_relationship_types() -> dict[str, Any]:
    """
    Get available relationship types with metadata.

    Returns relationship types grouped by category with styling information
    for the frontend.
    """
    # Group by category
    categories: dict[str, list[dict]] = {}
    for rel_type, metadata in RELATIONSHIP_TYPE_METADATA.items():
        category = metadata["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append({
            "id": rel_type,
            **metadata,
        })

    # Sort each category
    for category in categories:
        categories[category].sort(key=lambda x: x["label"])

    return {
        "relationship_types": RELATIONSHIP_TYPE_METADATA,
        "categories": categories,
        "category_order": ["organizational", "personal", "interaction", "spatial", "temporal", "analysis", "basic"],
    }


# ========== Cross-Shard Data Integration ==========


@router.get("/sources/status")
async def get_sources_status() -> dict[str, Any]:
    """
    Get availability status of cross-shard data sources.

    Returns count and availability for each shard that can contribute
    nodes or edges to the graph.
    """
    import httpx

    sources = {
        "claims": {"endpoint": "/api/claims", "available": False, "count": 0},
        "achEvidence": {"endpoint": "/api/ach/evidence", "available": False, "count": 0},
        "achHypotheses": {"endpoint": "/api/ach/hypotheses", "available": False, "count": 0},
        "provenanceArtifacts": {"endpoint": "/api/provenance/artifacts", "available": False, "count": 0},
        "timelineEvents": {"endpoint": "/api/timeline/events", "available": False, "count": 0},
        "contradictions": {"endpoint": "/api/contradictions", "available": False, "count": 0},
        "patterns": {"endpoint": "/api/patterns", "available": False, "count": 0},
        "credibilityRatings": {"endpoint": "/api/credibility/ratings", "available": False, "count": 0},
    }

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=5.0) as client:
        for key, source in sources.items():
            try:
                response = await client.get(source["endpoint"])
                if response.status_code == 200:
                    data = response.json()
                    source["available"] = True
                    # Try different count fields
                    source["count"] = (
                        data.get("total") or
                        data.get("count") or
                        len(data.get("items", data.get("results", [])))
                    )
            except Exception:
                pass

    return {"sources": sources}


@router.post("/sources/nodes")
async def get_cross_shard_nodes(
    project_id: str = Query(...),
    include_claims: bool = Query(False),
    include_ach_evidence: bool = Query(False),
    include_ach_hypotheses: bool = Query(False),
    include_provenance: bool = Query(False),
    include_timeline: bool = Query(False),
) -> dict[str, Any]:
    """
    Fetch nodes from enabled cross-shard sources.

    Transforms data from other shards into graph nodes.
    """
    import httpx

    nodes: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=10.0) as client:
        # Claims as nodes
        if include_claims:
            try:
                response = await client.get(f"/api/claims?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("claims", [])):
                        nodes.append({
                            "id": f"claim-{item.get('id')}",
                            "label": item.get("text", item.get("claim", ""))[:50],
                            "entity_type": "claim",
                            "source_shard": "claims",
                            "original_id": item.get("id"),
                            "properties": {
                                "status": item.get("status"),
                                "confidence": item.get("confidence"),
                            },
                        })
            except Exception as e:
                errors.append(f"claims: {str(e)}")

        # ACH Evidence as nodes
        if include_ach_evidence:
            try:
                response = await client.get(f"/api/ach/evidence?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("evidence", [])):
                        nodes.append({
                            "id": f"evidence-{item.get('id')}",
                            "label": item.get("description", "")[:50],
                            "entity_type": "evidence",
                            "source_shard": "ach",
                            "original_id": item.get("id"),
                            "properties": {
                                "credibility": item.get("credibility"),
                                "relevance": item.get("relevance"),
                                "matrix_id": item.get("matrix_id"),
                            },
                        })
            except Exception as e:
                errors.append(f"ach_evidence: {str(e)}")

        # ACH Hypotheses as nodes
        if include_ach_hypotheses:
            try:
                response = await client.get(f"/api/ach/hypotheses?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("hypotheses", [])):
                        nodes.append({
                            "id": f"hypothesis-{item.get('id')}",
                            "label": item.get("title", item.get("description", ""))[:50],
                            "entity_type": "hypothesis",
                            "source_shard": "ach",
                            "original_id": item.get("id"),
                            "properties": {
                                "is_lead": item.get("is_lead"),
                                "matrix_id": item.get("matrix_id"),
                            },
                        })
            except Exception as e:
                errors.append(f"ach_hypotheses: {str(e)}")

        # Provenance Artifacts as nodes
        if include_provenance:
            try:
                response = await client.get(f"/api/provenance/artifacts?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("artifacts", [])):
                        nodes.append({
                            "id": f"artifact-{item.get('id')}",
                            "label": item.get("name", item.get("title", ""))[:50],
                            "entity_type": "artifact",
                            "source_shard": "provenance",
                            "original_id": item.get("id"),
                            "properties": {
                                "artifact_type": item.get("artifact_type"),
                                "source_type": item.get("source_type"),
                            },
                        })
            except Exception as e:
                errors.append(f"provenance: {str(e)}")

        # Timeline Events as nodes
        if include_timeline:
            try:
                response = await client.get(f"/api/timeline/events?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("events", [])):
                        nodes.append({
                            "id": f"event-{item.get('id')}",
                            "label": item.get("title", item.get("description", ""))[:50],
                            "entity_type": "event",
                            "source_shard": "timeline",
                            "original_id": item.get("id"),
                            "properties": {
                                "event_date": item.get("event_date"),
                                "event_type": item.get("event_type"),
                            },
                        })
            except Exception as e:
                errors.append(f"timeline: {str(e)}")

    return {
        "nodes": nodes,
        "node_count": len(nodes),
        "errors": errors if errors else None,
    }


@router.post("/sources/edges")
async def get_cross_shard_edges(
    project_id: str = Query(...),
    include_contradictions: bool = Query(False),
    include_patterns: bool = Query(False),
) -> dict[str, Any]:
    """
    Fetch edges from enabled cross-shard sources.

    Transforms data from other shards into graph edges.
    """
    import httpx

    edges: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=10.0) as client:
        # Contradictions as edges
        if include_contradictions:
            try:
                response = await client.get(f"/api/contradictions?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("contradictions", [])):
                        # Contradiction links two entities
                        source_id = item.get("entity_a_id") or item.get("source_entity_id")
                        target_id = item.get("entity_b_id") or item.get("target_entity_id")
                        if source_id and target_id:
                            edges.append({
                                "source": source_id,
                                "target": target_id,
                                "relationship_type": "contradicts",
                                "weight": item.get("severity", 0.5),
                                "source_shard": "contradictions",
                                "original_id": item.get("id"),
                                "properties": {
                                    "contradiction_type": item.get("contradiction_type"),
                                    "severity": item.get("severity"),
                                },
                            })
            except Exception as e:
                errors.append(f"contradictions: {str(e)}")

        # Patterns as edges
        if include_patterns:
            try:
                response = await client.get(f"/api/patterns/matches?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("matches", [])):
                        # Pattern matches link entities
                        source_id = item.get("entity_a_id") or item.get("source_entity_id")
                        target_id = item.get("entity_b_id") or item.get("target_entity_id")
                        if source_id and target_id:
                            edges.append({
                                "source": source_id,
                                "target": target_id,
                                "relationship_type": "pattern_match",
                                "weight": item.get("confidence", 0.5),
                                "source_shard": "patterns",
                                "original_id": item.get("id"),
                                "properties": {
                                    "pattern_type": item.get("pattern_type"),
                                    "confidence": item.get("confidence"),
                                },
                            })
            except Exception as e:
                errors.append(f"patterns: {str(e)}")

    return {
        "edges": edges,
        "edge_count": len(edges),
        "errors": errors if errors else None,
    }


@router.get("/sources/credibility")
async def get_credibility_weights(
    project_id: str = Query(...),
) -> dict[str, Any]:
    """
    Fetch credibility ratings for edge weight adjustment.

    Returns source credibility scores that can be applied to edges.
    """
    import httpx

    ratings: dict[str, float] = {}

    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=10.0) as client:
            response = await client.get(f"/api/credibility/ratings?project_id={project_id}&limit=1000")
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", data.get("ratings", [])):
                    source_id = item.get("source_id") or item.get("document_id")
                    if source_id:
                        # Admiralty Code: A-F reliability (1.0-0.0), 1-6 credibility (1.0-0.0)
                        reliability = item.get("reliability_score", 0.5)
                        credibility = item.get("credibility_score", 0.5)
                        # Combined score
                        ratings[source_id] = (reliability + credibility) / 2
    except Exception as e:
        logger.warning(f"Failed to fetch credibility ratings: {e}")

    return {
        "ratings": ratings,
        "source_count": len(ratings),
    }


# ========== Graph Building & Stats ==========


async def _enrich_graph_with_cross_shard_data(
    graph,
    project_id: str,
    include_claims: bool = False,
    include_ach_evidence: bool = False,
    include_ach_hypotheses: bool = False,
    include_provenance_artifacts: bool = False,
    include_timeline: bool = False,
    include_contradictions: bool = False,
    include_patterns: bool = False,
    apply_credibility_weights: bool = False,
) -> tuple[list, list, dict]:
    """
    Fetch and merge cross-shard data into the graph.

    Returns:
        Tuple of (added_nodes, added_edges, credibility_ratings)
    """
    import httpx
    from .models import GraphNode, GraphEdge

    added_nodes = []
    added_edges = []
    credibility_ratings = {}

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=10.0) as client:
        # === NODE SOURCES ===

        # Claims as nodes
        if include_claims:
            try:
                response = await client.get(f"/api/claims?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("claims", [])):
                        node = GraphNode(
                            id=f"claim-{item.get('id')}",
                            entity_id=f"claim-{item.get('id')}",
                            label=(item.get("text", item.get("claim", ""))[:50] or "Claim"),
                            entity_type="claim",
                            properties={
                                "source_shard": "claims",
                                "original_id": item.get("id"),
                                "status": item.get("status"),
                                "confidence": item.get("confidence"),
                            },
                        )
                        added_nodes.append(node)
                    logger.info(f"Added {len(data.get('items', data.get('claims', [])))} claim nodes")
            except Exception as e:
                logger.warning(f"Failed to fetch claims: {e}")

        # ACH Evidence as nodes
        if include_ach_evidence:
            try:
                response = await client.get(f"/api/ach/evidence?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("evidence", [])):
                        node = GraphNode(
                            id=f"evidence-{item.get('id')}",
                            entity_id=f"evidence-{item.get('id')}",
                            label=(item.get("description", "")[:50] or "Evidence"),
                            entity_type="evidence",
                            properties={
                                "source_shard": "ach",
                                "original_id": item.get("id"),
                                "credibility": item.get("credibility"),
                                "relevance": item.get("relevance"),
                                "matrix_id": item.get("matrix_id"),
                            },
                        )
                        added_nodes.append(node)
                    logger.info(f"Added {len(data.get('items', data.get('evidence', [])))} evidence nodes")
            except Exception as e:
                logger.warning(f"Failed to fetch ACH evidence: {e}")

        # ACH Hypotheses as nodes
        if include_ach_hypotheses:
            try:
                response = await client.get(f"/api/ach/hypotheses?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("hypotheses", [])):
                        node = GraphNode(
                            id=f"hypothesis-{item.get('id')}",
                            entity_id=f"hypothesis-{item.get('id')}",
                            label=(item.get("title", item.get("description", ""))[:50] or "Hypothesis"),
                            entity_type="hypothesis",
                            properties={
                                "source_shard": "ach",
                                "original_id": item.get("id"),
                                "is_lead": item.get("is_lead"),
                                "matrix_id": item.get("matrix_id"),
                            },
                        )
                        added_nodes.append(node)
                    logger.info(f"Added {len(data.get('items', data.get('hypotheses', [])))} hypothesis nodes")
            except Exception as e:
                logger.warning(f"Failed to fetch ACH hypotheses: {e}")

        # Provenance Artifacts as nodes
        if include_provenance_artifacts:
            try:
                response = await client.get(f"/api/provenance/artifacts?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("artifacts", [])):
                        node = GraphNode(
                            id=f"artifact-{item.get('id')}",
                            entity_id=f"artifact-{item.get('id')}",
                            label=(item.get("name", item.get("title", ""))[:50] or "Artifact"),
                            entity_type="artifact",
                            properties={
                                "source_shard": "provenance",
                                "original_id": item.get("id"),
                                "artifact_type": item.get("artifact_type"),
                                "source_type": item.get("source_type"),
                            },
                        )
                        added_nodes.append(node)
                    logger.info(f"Added {len(data.get('items', data.get('artifacts', [])))} artifact nodes")
            except Exception as e:
                logger.warning(f"Failed to fetch provenance artifacts: {e}")

        # Timeline Events as nodes
        if include_timeline:
            try:
                response = await client.get(f"/api/timeline/events?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    events = data.get("items", data.get("events", []))
                    for item in events:
                        # Timeline events use 'text' field for description
                        label = item.get("title") or item.get("text") or item.get("description") or "Event"
                        if len(label) > 50:
                            label = label[:47] + "..."
                        node = GraphNode(
                            id=f"event-{item.get('id')}",
                            entity_id=f"event-{item.get('id')}",
                            label=label,
                            entity_type="event",
                            properties={
                                "source_shard": "timeline",
                                "original_id": item.get("id"),
                                "event_date": item.get("date_start") or item.get("event_date"),
                                "event_type": item.get("event_type"),
                            },
                        )
                        added_nodes.append(node)
                    logger.info(f"Added {len(events)} event nodes")
            except Exception as e:
                logger.warning(f"Failed to fetch timeline events: {e}")

        # === EDGE SOURCES ===

        # Get all existing node IDs for edge validation
        existing_node_ids = {n.id for n in graph.nodes} | {n.id for n in added_nodes}

        # Contradictions as edges
        if include_contradictions:
            try:
                response = await client.get(f"/api/contradictions?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    edge_count = 0
                    for item in data.get("items", data.get("contradictions", [])):
                        source_id = item.get("entity_a_id") or item.get("source_entity_id")
                        target_id = item.get("entity_b_id") or item.get("target_entity_id")
                        # Only add edge if both nodes exist
                        if source_id and target_id and source_id in existing_node_ids and target_id in existing_node_ids:
                            edge = GraphEdge(
                                source=source_id,
                                target=target_id,
                                relationship_type="contradicts",
                                weight=item.get("severity", 0.5),
                                properties={
                                    "source_shard": "contradictions",
                                    "original_id": item.get("id"),
                                    "contradiction_type": item.get("contradiction_type"),
                                },
                            )
                            added_edges.append(edge)
                            edge_count += 1
                    logger.info(f"Added {edge_count} contradiction edges")
            except Exception as e:
                logger.warning(f"Failed to fetch contradictions: {e}")

        # Patterns as edges
        if include_patterns:
            try:
                response = await client.get(f"/api/patterns/matches?project_id={project_id}&limit=500")
                if response.status_code == 200:
                    data = response.json()
                    edge_count = 0
                    for item in data.get("items", data.get("matches", [])):
                        source_id = item.get("entity_a_id") or item.get("source_entity_id")
                        target_id = item.get("entity_b_id") or item.get("target_entity_id")
                        # Only add edge if both nodes exist
                        if source_id and target_id and source_id in existing_node_ids and target_id in existing_node_ids:
                            edge = GraphEdge(
                                source=source_id,
                                target=target_id,
                                relationship_type="pattern_match",
                                weight=item.get("confidence", 0.5),
                                properties={
                                    "source_shard": "patterns",
                                    "original_id": item.get("id"),
                                    "pattern_type": item.get("pattern_type"),
                                },
                            )
                            added_edges.append(edge)
                            edge_count += 1
                    logger.info(f"Added {edge_count} pattern edges")
            except Exception as e:
                logger.warning(f"Failed to fetch patterns: {e}")

        # === CREDIBILITY WEIGHTS ===

        if apply_credibility_weights:
            try:
                response = await client.get(f"/api/credibility/ratings?project_id={project_id}&limit=1000")
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", data.get("ratings", [])):
                        source_id = item.get("source_id") or item.get("document_id")
                        if source_id:
                            reliability = item.get("reliability_score", 0.5)
                            credibility = item.get("credibility_score", 0.5)
                            credibility_ratings[source_id] = (reliability + credibility) / 2
                    logger.info(f"Loaded {len(credibility_ratings)} credibility ratings")
            except Exception as e:
                logger.warning(f"Failed to fetch credibility ratings: {e}")

    return added_nodes, added_edges, credibility_ratings


@router.post("/build")
async def build_graph(request: BuildGraphRequest) -> dict[str, Any]:
    """
    Build entity relationship graph.

    Constructs graph from document co-occurrences.
    Optionally includes cross-shard data sources.
    """
    if not _builder:
        raise HTTPException(status_code=503, detail="Graph builder not available")

    try:
        start_time = datetime.utcnow()

        # Log requested cross-shard sources
        cross_shard_sources = []
        if request.include_temporal:
            cross_shard_sources.append("timeline_events")
        if request.include_claims:
            cross_shard_sources.append("claims")
        if request.include_ach_evidence:
            cross_shard_sources.append("ach_evidence")
        if request.include_ach_hypotheses:
            cross_shard_sources.append("ach_hypotheses")
        if request.include_provenance_artifacts:
            cross_shard_sources.append("provenance_artifacts")
        if request.include_contradictions:
            cross_shard_sources.append("contradictions")
        if request.include_patterns:
            cross_shard_sources.append("patterns")
        if request.apply_credibility_weights:
            cross_shard_sources.append("credibility_weights")

        if cross_shard_sources:
            logger.info(f"Building graph with cross-shard sources: {cross_shard_sources}")

        # Build base graph from entities (conditionally)
        graph = await _builder.build_graph(
            project_id=request.project_id,
            document_ids=request.document_ids,
            entity_types=request.entity_types,
            min_co_occurrence=request.min_co_occurrence,
            include_temporal=request.include_temporal,
            include_document_entities=request.include_document_entities,
            include_cooccurrences=request.include_cooccurrences,
        )

        # Enrich with cross-shard data if any source is enabled
        added_nodes_count = 0
        added_edges_count = 0
        if cross_shard_sources:
            added_nodes, added_edges, credibility_ratings = await _enrich_graph_with_cross_shard_data(
                graph=graph,
                project_id=request.project_id,
                include_claims=request.include_claims,
                include_ach_evidence=request.include_ach_evidence,
                include_ach_hypotheses=request.include_ach_hypotheses,
                include_provenance_artifacts=request.include_provenance_artifacts,
                include_timeline=request.include_temporal,
                include_contradictions=request.include_contradictions,
                include_patterns=request.include_patterns,
                apply_credibility_weights=request.apply_credibility_weights,
            )

            # Add cross-shard nodes to graph
            graph.nodes.extend(added_nodes)
            added_nodes_count = len(added_nodes)

            # Add cross-shard edges to graph
            graph.edges.extend(added_edges)
            added_edges_count = len(added_edges)

            # Apply credibility weights to existing edges
            if credibility_ratings:
                for edge in graph.edges:
                    # Check if any document in edge has credibility rating
                    edge_credibility_scores = []
                    for doc_id in edge.document_ids:
                        if doc_id in credibility_ratings:
                            edge_credibility_scores.append(credibility_ratings[doc_id])

                    # Adjust edge weight based on average credibility
                    if edge_credibility_scores:
                        avg_credibility = sum(edge_credibility_scores) / len(edge_credibility_scores)
                        edge.weight = edge.weight * avg_credibility
                        edge.properties["credibility_adjusted"] = True
                        edge.properties["credibility_factor"] = avg_credibility

            # Update metadata
            graph.metadata["cross_shard_sources"] = cross_shard_sources
            graph.metadata["cross_shard_nodes_added"] = added_nodes_count
            graph.metadata["cross_shard_edges_added"] = added_edges_count

        build_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Store graph if storage available
        if _storage:
            await _storage.save_graph(graph)

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "graph.graph.built",
                {
                    "project_id": request.project_id,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                    "cross_shard_sources": cross_shard_sources,
                },
                source="graph-shard",
            )

        return {
            "project_id": graph.project_id,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "graph_id": f"graph-{graph.project_id}",
            "build_time_ms": build_time,
            "cross_shard_nodes_added": added_nodes_count,
            "cross_shard_edges_added": added_edges_count,
        }

    except Exception as e:
        logger.error(f"Error building graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics(project_id: str = Query(...)) -> dict[str, Any]:
    """
    Get comprehensive graph statistics.

    Returns metrics like density, diameter, clustering, etc.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Calculate statistics
        stats = _algorithms.calculate_statistics(graph)

        return stats.to_dict()

    except Exception as e:
        logger.error(f"Error calculating statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_graph(project_id: str) -> GraphResponse:
    """
    Get complete graph for a project.

    Returns full graph with all nodes and edges.
    """
    try:
        # Load from storage if available
        if _storage:
            graph = await _storage.load_graph(project_id)
        else:
            # Build on demand
            if not _builder:
                raise HTTPException(status_code=503, detail="Graph service not available")

            graph = await _builder.build_graph(project_id=project_id)

        return GraphResponse(
            project_id=graph.project_id,
            nodes=[n.to_dict() for n in graph.nodes],
            edges=[e.to_dict() for e in graph.edges],
            metadata=graph.metadata,
        )

    except Exception as e:
        logger.error(f"Error getting graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}")
async def get_entity_subgraph(
    entity_id: str,
    project_id: str = Query(...),
    depth: int = Query(2, ge=1, le=3),
    max_nodes: int = Query(100, ge=1, le=500),
    min_weight: float = Query(0.0, ge=0.0, le=1.0),
) -> GraphResponse:
    """
    Get subgraph centered on an entity.

    Extracts neighborhood around the specified entity.
    """
    try:
        # Get full graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Extract subgraph
        subgraph = _builder.extract_subgraph(
            graph=graph,
            entity_id=entity_id,
            depth=depth,
            max_nodes=max_nodes,
            min_weight=min_weight,
        )

        return GraphResponse(
            project_id=subgraph.project_id,
            nodes=[n.to_dict() for n in subgraph.nodes],
            edges=[e.to_dict() for e in subgraph.edges],
            metadata=subgraph.metadata,
        )

    except Exception as e:
        logger.error(f"Error getting entity subgraph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Ego Network Analysis ==========


@router.get("/ego/{entity_id}")
async def get_ego_network(
    entity_id: str,
    project_id: str = Query(...),
    depth: int = Query(2, ge=1, le=3),
    include_alter_alter_ties: bool = Query(True),
    include_metrics: bool = Query(True),
) -> dict[str, Any]:
    """
    Get ego network centered on a specific entity.

    An ego network includes:
    - The ego (center node)
    - Alters (nodes directly connected to ego)
    - Alter-alter ties (edges between alters, optional)
    - At depth 2: alters of alters

    Also calculates ego-centric metrics including Burt's structural holes:
    - Effective size: Network size accounting for redundancy
    - Efficiency: Effective size / actual size
    - Constraint: Degree to which ego's contacts constrain their actions
    - Hierarchy: Concentration of constraint

    Args:
        entity_id: ID of the ego (center) entity
        project_id: Project ID
        depth: Network depth (1 or 2)
        include_alter_alter_ties: Include edges between alters
        include_metrics: Calculate structural hole metrics
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        start_time = datetime.utcnow()

        # Get full graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Extract ego network
        ego_graph = _algorithms.extract_ego_network(
            graph=graph,
            ego_entity_id=entity_id,
            depth=depth,
            include_alter_alter_ties=include_alter_alter_ties,
        )

        # Check for error
        if ego_graph.metadata.get("error"):
            raise HTTPException(
                status_code=404,
                detail=f"Entity {entity_id} not found in graph"
            )

        # Calculate metrics if requested
        metrics = None
        if include_metrics:
            metrics = _algorithms.calculate_ego_metrics(graph, entity_id)

        calculation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Build response
        return {
            "project_id": project_id,
            "ego_id": entity_id,
            "ego_label": ego_graph.metadata.get("ego_label"),
            "depth": depth,
            "graph": {
                "nodes": [n.to_dict() for n in ego_graph.nodes],
                "edges": [e.to_dict() for e in ego_graph.edges],
                "metadata": ego_graph.metadata,
            },
            "metrics": metrics,
            "node_count": len(ego_graph.nodes),
            "edge_count": len(ego_graph.edges),
            "nodes_by_depth": ego_graph.metadata.get("nodes_by_depth", {}),
            "calculation_time_ms": calculation_time,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ego network: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ego/{entity_id}/metrics")
async def get_ego_metrics(
    entity_id: str,
    project_id: str = Query(...),
) -> dict[str, Any]:
    """
    Get ego-centric metrics for an entity without the full network.

    Lighter-weight endpoint for getting just structural hole metrics.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Calculate metrics
        metrics = _algorithms.calculate_ego_metrics(graph, entity_id)

        if metrics.get("error"):
            raise HTTPException(
                status_code=404,
                detail=f"Entity {entity_id} not found in graph"
            )

        return {
            "project_id": project_id,
            "entity_id": entity_id,
            **metrics,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ego metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/path")
async def find_path(request: PathRequest) -> PathResponse:
    """
    Find shortest path between two entities.

    Uses BFS to find the shortest connection.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Find path
        path = _algorithms.find_shortest_path(
            graph=graph,
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            max_depth=request.max_depth,
        )

        if not path:
            return PathResponse(
                path_found=False,
                path_length=0,
                path=[],
                edges=[],
                total_weight=0.0,
            )

        return PathResponse(
            path_found=True,
            path_length=path.path_length,
            path=path.path,
            edges=[e.to_dict() for e in path.edges],
            total_weight=path.total_weight,
        )

    except Exception as e:
        logger.error(f"Error finding path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/centrality/{project_id}")
async def calculate_centrality(
    project_id: str,
    metric: str = Query("all", description="Centrality metric: degree, betweenness, pagerank, all"),
    limit: int = Query(50, ge=1, le=200),
) -> CentralityResponse:
    """
    Calculate centrality metrics.

    Identifies most important/connected entities.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Validate metric
        try:
            metric_enum = CentralityMetric(metric.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")

        # Get graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Calculate centrality
        results = []

        if metric_enum == CentralityMetric.DEGREE:
            results = _algorithms.calculate_degree_centrality(graph, limit)
        elif metric_enum == CentralityMetric.BETWEENNESS:
            results = _algorithms.calculate_betweenness_centrality(graph, limit)
        elif metric_enum == CentralityMetric.PAGERANK:
            results = _algorithms.calculate_pagerank(graph, limit)
        elif metric_enum == CentralityMetric.ALL:
            # Calculate all metrics and merge
            degree = _algorithms.calculate_degree_centrality(graph, limit)
            betweenness = _algorithms.calculate_betweenness_centrality(graph, limit)
            pagerank = _algorithms.calculate_pagerank(graph, limit)

            # Use PageRank as primary, add others as metadata
            results = pagerank
            # TODO: Merge multiple metrics into results

        return CentralityResponse(
            project_id=project_id,
            metric=metric,
            results=[r.to_dict() for r in results],
            calculated_at=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating centrality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/communities")
async def detect_communities(request: CommunityRequest) -> CommunityResponse:
    """
    Detect communities in graph.

    Identifies clusters of closely connected entities.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Detect communities
        communities, modularity = _algorithms.detect_communities_louvain(
            graph=graph,
            min_community_size=request.min_community_size,
            resolution=request.resolution,
        )

        return CommunityResponse(
            project_id=request.project_id,
            community_count=len(communities),
            communities=[c.to_dict() for c in communities],
            modularity=modularity,
        )

    except Exception as e:
        logger.error(f"Error detecting communities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neighbors/{entity_id}")
async def get_neighbors(
    entity_id: str,
    project_id: str = Query(...),
    depth: int = Query(1, ge=1, le=2),
    min_weight: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Get neighbors of an entity.

    Returns entities connected to the specified entity.
    """
    if not _algorithms:
        raise HTTPException(status_code=503, detail="Graph algorithms not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Get neighbors
        result = _algorithms.get_neighbors(
            graph=graph,
            entity_id=entity_id,
            depth=depth,
            min_weight=min_weight,
            limit=limit,
        )

        return result

    except Exception as e:
        logger.error(f"Error getting neighbors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_graph(request: ExportRequest) -> ExportResponse:
    """
    Export graph in various formats.

    Supports JSON, GraphML, and GEXF formats.
    """
    if not _exporter:
        raise HTTPException(status_code=503, detail="Graph exporter not available")

    try:
        # Validate format
        try:
            format_enum = ExportFormat(request.format.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid format: {request.format}")

        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Apply filters if provided
        if request.filter:
            graph = _builder.filter_graph(
                graph=graph,
                entity_types=request.filter.get("entity_types"),
                min_edge_weight=request.filter.get("min_edge_weight"),
                relationship_types=request.filter.get("relationship_types"),
                document_ids=request.filter.get("document_ids"),
            )

        # Export
        data = _exporter.export_graph(
            graph=graph,
            format=format_enum,
            include_metadata=request.include_metadata,
        )

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "graph.graph.exported",
                {
                    "project_id": request.project_id,
                    "format": request.format,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                },
                source="graph-shard",
            )

        return ExportResponse(
            format=request.format,
            data=data,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            file_size_bytes=len(data.encode("utf-8")),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filter")
async def filter_graph(request: FilterRequest) -> GraphResponse:
    """
    Filter graph by various criteria.

    Returns filtered subgraph.
    """
    if not _builder:
        raise HTTPException(status_code=503, detail="Graph builder not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        # Apply filters
        filtered_graph = _builder.filter_graph(
            graph=graph,
            entity_types=request.entity_types,
            min_degree=request.min_degree,
            min_edge_weight=request.min_edge_weight,
            relationship_types=request.relationship_types,
            document_ids=request.document_ids,
        )

        return GraphResponse(
            project_id=filtered_graph.project_id,
            nodes=[n.to_dict() for n in filtered_graph.nodes],
            edges=[e.to_dict() for e in filtered_graph.edges],
            metadata=filtered_graph.metadata,
        )

    except Exception as e:
        logger.error(f"Error filtering graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Flow Endpoints ==========


class FlowRequest(BaseModel):
    """Request for flow data extraction."""
    project_id: str
    flow_type: str = "entity"  # "entity" or "relationship"
    source_types: list[str] | None = None
    target_types: list[str] | None = None
    intermediate_types: list[str] | None = None
    relationship_types: list[str] | None = None
    min_weight: float = 0.0
    aggregate_by_type: bool = False
    max_links: int = 100
    min_link_value: float = 0.0


@router.post("/flows")
async def get_flow_data(request: FlowRequest) -> dict[str, Any]:
    """
    Get flow data for Sankey diagram visualization.

    Extracts flow data from the graph based on entity types and relationships.

    Args:
        request: Flow configuration including source/target types and filters

    Returns:
        FlowData with nodes, links, and metadata for Sankey rendering
    """
    if not _builder or not _flow_analyzer:
        raise HTTPException(status_code=503, detail="Flow analyzer not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(request.project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=request.project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        if not graph or not graph.nodes:
            return {
                "nodes": [],
                "links": [],
                "total_flow": 0,
                "layer_count": 0,
                "node_count": 0,
                "link_count": 0,
            }

        # Extract flows based on type
        if request.flow_type == "relationship":
            flow_data = _flow_analyzer.extract_relationship_flows(
                graph=graph,
                flow_relationship_types=request.relationship_types,
                min_weight=request.min_weight,
                aggregate_by_type=request.aggregate_by_type,
            )
        else:
            # Default: entity-based flows
            flow_data = _flow_analyzer.extract_entity_flows(
                graph=graph,
                source_types=request.source_types,
                target_types=request.target_types,
                intermediate_types=request.intermediate_types,
                relationship_types=request.relationship_types,
                min_weight=request.min_weight,
            )

        # Aggregate if requested
        if request.max_links > 0 or request.min_link_value > 0:
            flow_data = _flow_analyzer.aggregate_flows(
                flow_data=flow_data,
                min_value=request.min_link_value,
                max_links=request.max_links,
            )

        return _flow_analyzer.to_dict(flow_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting flow data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flows/{project_id}")
async def get_flows_simple(
    project_id: str,
    flow_type: str = Query("entity", description="Flow type: entity or relationship"),
    source_types: str = Query(None, description="Comma-separated source entity types"),
    target_types: str = Query(None, description="Comma-separated target entity types"),
    min_weight: float = Query(0.0, description="Minimum edge weight"),
    aggregate: bool = Query(False, description="Aggregate by entity type"),
    max_links: int = Query(50, description="Maximum number of links"),
) -> dict[str, Any]:
    """
    Get flow data for Sankey diagram (simple GET endpoint).

    A simpler GET endpoint for basic flow extraction.
    """
    if not _builder or not _flow_analyzer:
        raise HTTPException(status_code=503, detail="Flow analyzer not available")

    try:
        # Get graph
        if _storage:
            graph = await _storage.load_graph(project_id)
        elif _builder:
            graph = await _builder.build_graph(project_id=project_id)
        else:
            raise HTTPException(status_code=503, detail="Graph service not available")

        if not graph or not graph.nodes:
            return {
                "nodes": [],
                "links": [],
                "total_flow": 0,
                "layer_count": 0,
                "node_count": 0,
                "link_count": 0,
            }

        # Parse comma-separated types
        src_types = source_types.split(",") if source_types else None
        tgt_types = target_types.split(",") if target_types else None

        # Extract flows
        if flow_type == "relationship":
            flow_data = _flow_analyzer.extract_relationship_flows(
                graph=graph,
                min_weight=min_weight,
                aggregate_by_type=aggregate,
            )
        else:
            flow_data = _flow_analyzer.extract_entity_flows(
                graph=graph,
                source_types=src_types,
                target_types=tgt_types,
                min_weight=min_weight,
            )

        # Aggregate
        flow_data = _flow_analyzer.aggregate_flows(
            flow_data=flow_data,
            max_links=max_links,
        )

        return _flow_analyzer.to_dict(flow_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting flow data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Link Analysis Mode - Positions & Annotations
# =============================================================================

class PositionData(BaseModel):
    """Single node position."""
    node_id: str
    x: float
    y: float
    pinned: bool = True


class SavePositionsRequest(BaseModel):
    """Request to save multiple node positions."""
    project_id: str
    positions: list[PositionData]
    user_id: str | None = None


class AnnotationData(BaseModel):
    """Annotation data."""
    graph_id: str
    node_id: str | None = None
    edge_source: str | None = None
    edge_target: str | None = None
    annotation_type: str  # "note", "label", "highlight", "group"
    content: str | None = None
    style: dict[str, Any] = {}
    user_id: str | None = None


@router.post("/positions")
async def save_positions(request: SavePositionsRequest) -> dict[str, Any]:
    """
    Save user-defined node positions for link analysis mode.

    Positions are stored per graph and optionally per user.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get or create graph ID for project
        graph_id_result = await _db_service.fetch_one(
            "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": request.project_id}
        )

        if not graph_id_result:
            raise HTTPException(status_code=404, detail="Graph not found for project")

        graph_id = graph_id_result["id"]
        saved_count = 0

        for pos in request.positions:
            import uuid
            from datetime import datetime

            pos_id = str(uuid.uuid4())
            now = datetime.utcnow()

            # Upsert position (SQLite/PostgreSQL compatible)
            await _db_service.execute(
                """
                INSERT INTO arkham_graph.user_positions
                    (id, graph_id, user_id, node_id, x, y, pinned, created_at, updated_at)
                VALUES (:id, :graph_id, :user_id, :node_id, :x, :y, :pinned, :created_at, :updated_at)
                ON CONFLICT (graph_id, user_id, node_id)
                DO UPDATE SET x = :x, y = :y, pinned = :pinned, updated_at = :updated_at
                """,
                {
                    "id": pos_id,
                    "graph_id": graph_id,
                    "user_id": request.user_id,
                    "node_id": pos.node_id,
                    "x": pos.x,
                    "y": pos.y,
                    "pinned": pos.pinned,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            saved_count += 1

        return {
            "success": True,
            "saved_count": saved_count,
            "project_id": request.project_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{project_id}")
async def get_positions(
    project_id: str,
    user_id: str = Query(None, description="User ID for multi-user support"),
) -> dict[str, Any]:
    """
    Get saved node positions for a project.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get graph ID for project
        graph_id_result = await _db_service.fetch_one(
            "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        if not graph_id_result:
            return {"positions": {}, "project_id": project_id}

        graph_id = graph_id_result["id"]

        # Get positions
        if user_id:
            rows = await _db_service.fetch_all(
                """
                SELECT node_id, x, y, pinned, updated_at
                FROM arkham_graph.user_positions
                WHERE graph_id = :graph_id AND (user_id = :user_id OR user_id IS NULL)
                ORDER BY updated_at DESC
                """,
                {"graph_id": graph_id, "user_id": user_id}
            )
        else:
            rows = await _db_service.fetch_all(
                """
                SELECT node_id, x, y, pinned, updated_at
                FROM arkham_graph.user_positions
                WHERE graph_id = :graph_id AND user_id IS NULL
                ORDER BY updated_at DESC
                """,
                {"graph_id": graph_id}
            )

        # Build positions dict
        positions = {}
        for row in rows:
            positions[row["node_id"]] = {
                "x": row["x"],
                "y": row["y"],
                "pinned": row["pinned"],
            }

        return {
            "positions": positions,
            "project_id": project_id,
            "position_count": len(positions),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{project_id}")
async def clear_positions(
    project_id: str,
    user_id: str = Query(None, description="User ID for multi-user support"),
) -> dict[str, Any]:
    """
    Clear all saved positions for a project.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get graph ID for project
        graph_id_result = await _db_service.fetch_one(
            "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        if not graph_id_result:
            return {"deleted_count": 0, "project_id": project_id}

        graph_id = graph_id_result["id"]

        # Delete positions
        if user_id:
            await _db_service.execute(
                """
                DELETE FROM arkham_graph.user_positions
                WHERE graph_id = :graph_id AND user_id = :user_id
                """,
                {"graph_id": graph_id, "user_id": user_id}
            )
        else:
            await _db_service.execute(
                """
                DELETE FROM arkham_graph.user_positions
                WHERE graph_id = :graph_id AND user_id IS NULL
                """,
                {"graph_id": graph_id}
            )

        return {
            "success": True,
            "project_id": project_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/annotations")
async def save_annotation(annotation: AnnotationData) -> dict[str, Any]:
    """
    Save an annotation (note, label, highlight, or group).
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        import uuid
        import json
        from datetime import datetime

        annotation_id = str(uuid.uuid4())
        now = datetime.utcnow()

        await _db_service.execute(
            """
            INSERT INTO arkham_graph.annotations
                (id, graph_id, node_id, edge_source, edge_target, annotation_type,
                 content, style, created_at, updated_at, user_id)
            VALUES (:id, :graph_id, :node_id, :edge_source, :edge_target, :annotation_type,
                    :content, :style, :created_at, :updated_at, :user_id)
            """,
            {
                "id": annotation_id,
                "graph_id": annotation.graph_id,
                "node_id": annotation.node_id,
                "edge_source": annotation.edge_source,
                "edge_target": annotation.edge_target,
                "annotation_type": annotation.annotation_type,
                "content": annotation.content,
                "style": json.dumps(annotation.style),
                "created_at": now,
                "updated_at": now,
                "user_id": annotation.user_id,
            }
        )

        return {
            "success": True,
            "annotation_id": annotation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/annotations/{project_id}")
async def get_annotations(
    project_id: str,
    annotation_type: str = Query(None, description="Filter by type"),
    user_id: str = Query(None, description="User ID"),
) -> dict[str, Any]:
    """
    Get all annotations for a project.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get graph ID for project
        graph_id_result = await _db_service.fetch_one(
            "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        if not graph_id_result:
            return {"annotations": [], "project_id": project_id}

        graph_id = graph_id_result["id"]

        # Build query
        query = """
            SELECT id, node_id, edge_source, edge_target, annotation_type,
                   content, style, created_at, updated_at, user_id
            FROM arkham_graph.annotations
            WHERE graph_id = :graph_id
        """
        params: dict[str, Any] = {"graph_id": graph_id}

        if annotation_type:
            query += " AND annotation_type = :annotation_type"
            params["annotation_type"] = annotation_type

        if user_id:
            query += " AND (user_id = :user_id OR user_id IS NULL)"
            params["user_id"] = user_id

        query += " ORDER BY created_at DESC"

        rows = await _db_service.fetch_all(query, params)

        import json
        annotations = []
        for row in rows:
            style = row["style"]
            if isinstance(style, str):
                try:
                    style = json.loads(style)
                except:
                    style = {}

            annotations.append({
                "id": row["id"],
                "node_id": row["node_id"],
                "edge_source": row["edge_source"],
                "edge_target": row["edge_target"],
                "annotation_type": row["annotation_type"],
                "content": row["content"],
                "style": style,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "user_id": row["user_id"],
            })

        return {
            "annotations": annotations,
            "project_id": project_id,
            "count": len(annotations),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting annotations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: str,
    content: str = Body(None),
    style: dict[str, Any] = Body(None),
) -> dict[str, Any]:
    """
    Update an existing annotation.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        import json
        from datetime import datetime

        updates = []
        params: dict[str, Any] = {"id": annotation_id, "updated_at": datetime.utcnow()}

        if content is not None:
            updates.append("content = :content")
            params["content"] = content

        if style is not None:
            updates.append("style = :style")
            params["style"] = json.dumps(style)

        if not updates:
            return {"success": True, "annotation_id": annotation_id, "updated": False}

        updates.append("updated_at = :updated_at")

        await _db_service.execute(
            f"""
            UPDATE arkham_graph.annotations
            SET {", ".join(updates)}
            WHERE id = :id
            """,
            params
        )

        return {
            "success": True,
            "annotation_id": annotation_id,
            "updated": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str) -> dict[str, Any]:
    """
    Delete an annotation.
    """
    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        await _db_service.execute(
            "DELETE FROM arkham_graph.annotations WHERE id = :id",
            {"id": annotation_id}
        )

        return {
            "success": True,
            "annotation_id": annotation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
