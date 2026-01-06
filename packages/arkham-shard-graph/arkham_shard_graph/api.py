"""API endpoints for the Graph Shard."""

import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request

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


# === Helper to get shard instance ===

def get_shard(request: Request) -> "GraphShard":
    """Get the graph shard instance from app state."""
    shard = getattr(request.app.state, "graph_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Graph shard not available")
    return shard


def init_api(builder, algorithms, exporter, storage=None, event_bus=None, scorer=None):
    """
    Initialize API with shard components.

    Args:
        builder: GraphBuilder instance
        algorithms: GraphAlgorithms instance
        exporter: GraphExporter instance
        storage: Optional storage service
        event_bus: Optional event bus service
        scorer: Optional CompositeScorer instance
    """
    global _builder, _algorithms, _exporter, _storage, _event_bus, _scorer

    _builder = builder
    _algorithms = algorithms
    _exporter = exporter
    _storage = storage
    _event_bus = event_bus
    _scorer = scorer or CompositeScorer()

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
