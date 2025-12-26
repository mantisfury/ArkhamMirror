"""API endpoints for the Graph Shard."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

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
)

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/graph", tags=["graph"])

# Shard components (injected by init_api)
_builder = None
_algorithms = None
_exporter = None
_storage = None
_event_bus = None


def init_api(builder, algorithms, exporter, storage=None, event_bus=None):
    """
    Initialize API with shard components.

    Args:
        builder: GraphBuilder instance
        algorithms: GraphAlgorithms instance
        exporter: GraphExporter instance
        storage: Optional storage service
        event_bus: Optional event bus service
    """
    global _builder, _algorithms, _exporter, _storage, _event_bus

    _builder = builder
    _algorithms = algorithms
    _exporter = exporter
    _storage = storage
    _event_bus = event_bus

    logger.info("Graph API initialized")


# --- Endpoints ---


@router.post("/build")
async def build_graph(request: BuildGraphRequest) -> dict[str, Any]:
    """
    Build entity relationship graph.

    Constructs graph from document co-occurrences.
    """
    if not _builder:
        raise HTTPException(status_code=503, detail="Graph builder not available")

    try:
        start_time = datetime.utcnow()

        graph = await _builder.build_graph(
            project_id=request.project_id,
            document_ids=request.document_ids,
            entity_types=request.entity_types,
            min_co_occurrence=request.min_co_occurrence,
            include_temporal=request.include_temporal,
        )

        build_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Store graph if storage available
        if _storage:
            await _storage.save_graph(graph)

        # Publish event
        if _event_bus:
            await _event_bus.publish(
                "graph.built",
                {
                    "project_id": request.project_id,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                },
            )

        return {
            "project_id": graph.project_id,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "graph_id": f"graph-{graph.project_id}",
            "build_time_ms": build_time,
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
            await _event_bus.publish(
                "graph.exported",
                {
                    "project_id": request.project_id,
                    "format": request.format,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                },
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
