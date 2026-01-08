"""Graph Shard - Entity relationship visualization and analysis."""

import json
import logging
from datetime import datetime
from typing import Any

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .builder import GraphBuilder
from .algorithms import GraphAlgorithms
from .exporter import GraphExporter
from .storage import GraphStorage

logger = logging.getLogger(__name__)

# Database schema SQL
GRAPH_SCHEMA_SQL = """
-- Graph shard schema
CREATE SCHEMA IF NOT EXISTS arkham_graph;

-- Main graphs table (one per project)
CREATE TABLE IF NOT EXISTS arkham_graph.graphs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE,
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Graph nodes
CREATE TABLE IF NOT EXISTS arkham_graph.nodes (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL REFERENCES arkham_graph.graphs(id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    entity_type TEXT,
    label TEXT,
    document_count INTEGER DEFAULT 0,
    degree INTEGER DEFAULT 0,
    properties JSONB DEFAULT '{}',
    centrality_score REAL,
    community_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Graph edges
CREATE TABLE IF NOT EXISTS arkham_graph.edges (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL REFERENCES arkham_graph.graphs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT,
    weight REAL DEFAULT 1.0,
    co_occurrence_count INTEGER DEFAULT 0,
    document_ids JSONB DEFAULT '[]',
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-defined positions for link analysis mode
CREATE TABLE IF NOT EXISTS arkham_graph.user_positions (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    user_id TEXT,  -- For multi-user support (nullable for single-user)
    node_id TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    pinned BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(graph_id, user_id, node_id)
);

-- Annotations for link analysis mode
CREATE TABLE IF NOT EXISTS arkham_graph.annotations (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    node_id TEXT,  -- NULL for graph-level annotations
    edge_source TEXT,  -- For edge annotations
    edge_target TEXT,  -- For edge annotations
    annotation_type TEXT NOT NULL,  -- "note", "label", "highlight", "group"
    content TEXT,
    style JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT  -- For multi-user support
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_graph_graphs_project ON arkham_graph.graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph ON arkham_graph.nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_entity ON arkham_graph.nodes(entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON arkham_graph.nodes(entity_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_graph ON arkham_graph.edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON arkham_graph.edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON arkham_graph.edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON arkham_graph.edges(relationship_type);
CREATE INDEX IF NOT EXISTS idx_graph_positions_graph ON arkham_graph.user_positions(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_positions_node ON arkham_graph.user_positions(node_id);
CREATE INDEX IF NOT EXISTS idx_graph_annotations_graph ON arkham_graph.annotations(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_annotations_node ON arkham_graph.annotations(node_id);
CREATE INDEX IF NOT EXISTS idx_graph_annotations_type ON arkham_graph.annotations(annotation_type);
"""


class GraphShard(ArkhamShard):
    """
    Graph shard for ArkhamFrame.

    Provides entity relationship visualization and graph analysis
    for investigative journalism.

    Features:
    - Entity graph building from document co-occurrences
    - Path finding between entities
    - Centrality metrics (degree, betweenness, PageRank)
    - Community detection
    - Graph export (JSON, GraphML, GEXF)
    - Subgraph extraction
    - Comprehensive graph statistics
    """

    name = "graph"
    version = "0.1.0"
    description = "Entity relationship graph analysis and visualization"

    def __init__(self):
        super().__init__()
        self.builder: GraphBuilder | None = None
        self.algorithms: GraphAlgorithms | None = None
        self.exporter: GraphExporter | None = None
        self.storage: GraphStorage | None = None

        self._frame = None
        self._event_bus = None
        self._entities_service = None
        self._documents_service = None
        self._db_service = None

    async def initialize(self, frame) -> None:
        """
        Initialize the Graph shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Graph Shard...")

        # Get Frame services
        self._event_bus = frame.get_service("events")
        self._entities_service = frame.get_service("entities")
        self._documents_service = frame.get_service("documents")
        self._db_service = frame.get_service("database") or frame.get_service("db")

        if not self._entities_service:
            logger.warning("Entities service not available - graph building may be limited")

        if not self._documents_service:
            logger.warning("Documents service not available - co-occurrence analysis may be limited")

        if not self._db_service:
            logger.warning("Database service not available - using in-memory storage only")
        else:
            # Create database schema
            await self._create_schema()

        # Create components
        self.builder = GraphBuilder(
            entities_service=self._entities_service,
            documents_service=self._documents_service,
            db_service=self._db_service,
        )

        self.algorithms = GraphAlgorithms()

        self.exporter = GraphExporter()

        self.storage = GraphStorage(
            db_service=self._db_service,
            get_tenant_id=self.get_tenant_id_or_none,
        )

        # Initialize API
        init_api(
            builder=self.builder,
            algorithms=self.algorithms,
            exporter=self.exporter,
            storage=self.storage,
            event_bus=self._event_bus,
            db_service=self._db_service,
        )

        # Subscribe to events
        if self._event_bus:
            await self._subscribe_to_events()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.graph_shard = self

        logger.info("Graph Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Graph Shard...")

        # Unsubscribe from events
        if self._event_bus:
            await self._unsubscribe_from_events()

        # Clear storage cache
        if self.storage:
            self.storage.clear_cache()

        # Clear components
        self.builder = None
        self.algorithms = None
        self.exporter = None
        self.storage = None

        logger.info("Graph Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # --- Event Subscriptions ---

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events."""
        if not self._event_bus:
            return

        # Subscribe to entity events (using correct naming convention)
        await self._event_bus.subscribe(
            "entities.entity.created",
            self._on_entity_created,
        )

        await self._event_bus.subscribe(
            "entities.entity.merged",
            self._on_entities_merged,
        )

        # Subscribe to document events
        await self._event_bus.subscribe(
            "documents.document.deleted",
            self._on_document_deleted,
        )

        logger.info("Subscribed to events: entities.entity.created, entities.entity.merged, documents.document.deleted")

    async def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from events."""
        if not self._event_bus:
            return

        await self._event_bus.unsubscribe("entities.entity.created", self._on_entity_created)
        await self._event_bus.unsubscribe("entities.entity.merged", self._on_entities_merged)
        await self._event_bus.unsubscribe("documents.document.deleted", self._on_document_deleted)

        logger.info("Unsubscribed from events")

    # --- Event Handlers ---

    async def _on_entity_created(self, event_data: dict) -> None:
        """
        Handle entity created event.

        Invalidates graph cache for affected projects.
        """
        entity_id = event_data.get("entity_id")
        project_id = event_data.get("project_id")

        if not entity_id or not project_id:
            return

        logger.debug(f"Entity created: {entity_id} in project {project_id}")

        # Invalidate cached graph
        if self.storage and project_id in self.storage._cache:
            del self.storage._cache[project_id]
            logger.debug(f"Invalidated graph cache for project {project_id}")

    async def _on_entities_merged(self, event_data: dict) -> None:
        """
        Handle entities merged event.

        Updates graphs to merge nodes.
        """
        source_entity_id = event_data.get("source_entity_id")
        target_entity_id = event_data.get("target_entity_id")
        project_id = event_data.get("project_id")

        if not source_entity_id or not target_entity_id or not project_id:
            return

        logger.info(
            f"Entities merged: {source_entity_id} -> {target_entity_id} in project {project_id}"
        )

        # Invalidate cached graph (rebuild will merge automatically)
        if self.storage and project_id in self.storage._cache:
            del self.storage._cache[project_id]
            logger.debug(f"Invalidated graph cache for project {project_id}")

        # TODO: More sophisticated merge that updates existing graph
        # instead of invalidating cache

    async def _on_document_deleted(self, event_data: dict) -> None:
        """
        Handle document deleted event.

        Updates edge weights and removes orphaned edges.
        """
        doc_id = event_data.get("document_id")
        project_id = event_data.get("project_id")

        if not doc_id or not project_id:
            return

        logger.debug(f"Document deleted: {doc_id} in project {project_id}")

        # Invalidate cached graph (rebuild will exclude deleted document)
        if self.storage and project_id in self.storage._cache:
            del self.storage._cache[project_id]
            logger.debug(f"Invalidated graph cache for project {project_id}")

    # --- Public API for other shards ---

    async def build_graph(
        self,
        project_id: str,
        document_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        min_co_occurrence: int = 1,
    ):
        """
        Public method for other shards to build graphs.

        Args:
            project_id: Project ID
            document_ids: Optional document filter
            entity_types: Optional entity type filter
            min_co_occurrence: Minimum co-occurrence count

        Returns:
            Graph object
        """
        if not self.builder:
            raise RuntimeError("Graph Shard not initialized")

        graph = await self.builder.build_graph(
            project_id=project_id,
            document_ids=document_ids,
            entity_types=entity_types,
            min_co_occurrence=min_co_occurrence,
        )

        # Cache graph
        if self.storage:
            await self.storage.save_graph(graph)

        return graph

    async def find_path(
        self,
        project_id: str,
        source: str,
        target: str,
        max_depth: int = 6,
    ):
        """
        Public method to find path between entities.

        Args:
            project_id: Project ID
            source: Source entity ID
            target: Target entity ID
            max_depth: Maximum path length

        Returns:
            GraphPath if found, None otherwise
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Find path
        path = self.algorithms.find_shortest_path(
            graph=graph,
            source_entity_id=source,
            target_entity_id=target,
            max_depth=max_depth,
        )

        return path

    async def calculate_centrality(
        self,
        project_id: str,
        metric: str = "pagerank",
        limit: int = 50,
    ):
        """
        Public method to calculate centrality.

        Args:
            project_id: Project ID
            metric: Centrality metric (degree, betweenness, pagerank)
            limit: Top N results

        Returns:
            List of CentralityResult objects
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Calculate centrality
        if metric == "degree":
            results = self.algorithms.calculate_degree_centrality(graph, limit)
        elif metric == "betweenness":
            results = self.algorithms.calculate_betweenness_centrality(graph, limit)
        elif metric == "pagerank":
            results = self.algorithms.calculate_pagerank(graph, limit)
        else:
            raise ValueError(f"Unknown metric: {metric}")

        return results

    async def detect_communities(
        self,
        project_id: str,
        min_size: int = 3,
        resolution: float = 1.0,
    ):
        """
        Public method to detect communities.

        Args:
            project_id: Project ID
            min_size: Minimum community size
            resolution: Resolution parameter

        Returns:
            Tuple of (communities list, modularity score)
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Detect communities
        communities, modularity = self.algorithms.detect_communities_louvain(
            graph=graph,
            min_community_size=min_size,
            resolution=resolution,
        )

        return communities, modularity

    async def get_neighbors(
        self,
        entity_id: str,
        project_id: str,
        depth: int = 1,
        limit: int = 50,
    ):
        """
        Public method to get entity neighbors.

        Args:
            entity_id: Entity ID
            project_id: Project ID
            depth: Hop distance
            limit: Maximum neighbors

        Returns:
            Dictionary with neighbor information
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Get neighbors
        result = self.algorithms.get_neighbors(
            graph=graph,
            entity_id=entity_id,
            depth=depth,
            limit=limit,
        )

        return result

    async def export_graph(
        self,
        project_id: str,
        format: str = "json",
        include_metadata: bool = True,
    ):
        """
        Public method to export graph.

        Args:
            project_id: Project ID
            format: Export format (json, graphml, gexf)
            include_metadata: Include metadata

        Returns:
            Serialized graph as string
        """
        if not self.exporter or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        from .models import ExportFormat

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Export
        format_enum = ExportFormat(format.lower())
        data = self.exporter.export_graph(
            graph=graph,
            format=format_enum,
            include_metadata=include_metadata,
        )

        return data

    def get_statistics(self, project_id: str):
        """
        Public method to get graph statistics.

        Args:
            project_id: Project ID

        Returns:
            GraphStatistics object
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph (sync method, needs to be called from async context)
        # For sync wrapper, caller needs to handle async
        raise NotImplementedError("Use async version: calculate_statistics")

    async def calculate_statistics(self, project_id: str):
        """
        Public async method to calculate graph statistics.

        Args:
            project_id: Project ID

        Returns:
            GraphStatistics object
        """
        if not self.algorithms or not self.storage:
            raise RuntimeError("Graph Shard not initialized")

        # Load graph
        graph = await self.storage.load_graph(project_id)

        # Calculate statistics
        stats = self.algorithms.calculate_statistics(graph)

        return stats

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database schema for graph persistence."""
        if not self._db_service:
            logger.warning("No database service - skipping schema creation")
            return

        try:
            await self._db_service.execute(GRAPH_SCHEMA_SQL)

            # ===========================================
            # Multi-tenancy Migration
            # ===========================================
            await self._db_service.execute("""
                DO $$
                DECLARE
                    tables_to_update TEXT[] := ARRAY['graphs', 'nodes', 'edges', 'user_positions', 'annotations'];
                    tbl TEXT;
                BEGIN
                    FOREACH tbl IN ARRAY tables_to_update LOOP
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'arkham_graph'
                            AND table_name = tbl
                            AND column_name = 'tenant_id'
                        ) THEN
                            EXECUTE format('ALTER TABLE arkham_graph.%I ADD COLUMN tenant_id UUID', tbl);
                        END IF;
                    END LOOP;
                END $$;
            """)

            await self._db_service.execute("""
                CREATE INDEX IF NOT EXISTS idx_graph_graphs_tenant
                ON arkham_graph.graphs(tenant_id)
            """)

            await self._db_service.execute("""
                CREATE INDEX IF NOT EXISTS idx_graph_nodes_tenant
                ON arkham_graph.nodes(tenant_id)
            """)

            await self._db_service.execute("""
                CREATE INDEX IF NOT EXISTS idx_graph_edges_tenant
                ON arkham_graph.edges(tenant_id)
            """)

            await self._db_service.execute("""
                CREATE INDEX IF NOT EXISTS idx_graph_user_positions_tenant
                ON arkham_graph.user_positions(tenant_id)
            """)

            await self._db_service.execute("""
                CREATE INDEX IF NOT EXISTS idx_graph_annotations_tenant
                ON arkham_graph.annotations(tenant_id)
            """)

            logger.info("Graph database schema created/verified")
        except Exception as e:
            logger.error(f"Failed to create graph schema: {e}", exc_info=True)
            raise

    # === Private Helpers ===

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default
