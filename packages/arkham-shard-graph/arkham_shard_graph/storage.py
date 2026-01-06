"""Graph storage - persist and retrieve graphs from database."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


def _parse_jsonb(value: Any, default: Any = None) -> Any:
    """Parse a JSONB field that may already be parsed by the database driver."""
    if value is None:
        return default if default is not None else {}
    if isinstance(value, (dict, list)):
        return value  # Already parsed by PostgreSQL JSONB
    if isinstance(value, str):
        if not value or value.strip() == "":
            return default if default is not None else {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else {}
    return default if default is not None else {}


class GraphStorage:
    """
    Storage service for graphs.

    Provides in-memory caching with database persistence.
    """

    def __init__(self, db_service=None):
        """
        Initialize graph storage.

        Args:
            db_service: Database service for persistence
        """
        self.db_service = db_service
        self._cache: dict[str, Graph] = {}  # In-memory cache: project_id -> Graph

    async def save_graph(self, graph: Graph) -> None:
        """
        Save graph to storage (cache + database).

        Args:
            graph: Graph to save
        """
        # Cache in memory
        self._cache[graph.project_id] = graph

        # Persist to database if available
        if self.db_service:
            try:
                await self._persist_graph(graph)
                logger.info(f"Graph persisted for project {graph.project_id}")
            except Exception as e:
                logger.error(f"Error persisting graph: {e}", exc_info=True)
        else:
            logger.debug(f"Graph cached for project {graph.project_id} (no persistence)")

    async def load_graph(self, project_id: str) -> Graph:
        """
        Load graph from storage.

        Args:
            project_id: Project ID

        Returns:
            Graph object

        Raises:
            ValueError: If graph not found
        """
        # Check cache first
        if project_id in self._cache:
            logger.debug(f"Graph loaded from cache for project {project_id}")
            return self._cache[project_id]

        # Load from database
        if self.db_service:
            try:
                graph = await self._load_from_db(project_id)
                if graph:
                    self._cache[project_id] = graph
                    logger.info(f"Graph loaded from database for project {project_id}")
                    return graph
            except Exception as e:
                logger.error(f"Error loading graph from database: {e}", exc_info=True)

        raise ValueError(f"Graph not found for project {project_id}")

    async def delete_graph(self, project_id: str) -> None:
        """
        Delete graph from storage.

        Args:
            project_id: Project ID
        """
        # Remove from cache
        if project_id in self._cache:
            del self._cache[project_id]

        # Delete from database
        if self.db_service:
            try:
                await self._delete_from_db(project_id)
                logger.info(f"Graph deleted for project {project_id}")
            except Exception as e:
                logger.error(f"Error deleting graph: {e}", exc_info=True)

    async def graph_exists(self, project_id: str) -> bool:
        """
        Check if a graph exists for the project.

        Args:
            project_id: Project ID

        Returns:
            True if graph exists
        """
        # Check cache first
        if project_id in self._cache:
            return True

        # Check database
        if self.db_service:
            try:
                result = await self.db_service.fetch_one(
                    "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
                    {"project_id": project_id}
                )
                return result is not None
            except Exception as e:
                logger.error(f"Error checking graph existence: {e}")
                return False

        return False

    async def list_graphs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """
        List all graphs with metadata.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of graph metadata dictionaries
        """
        if not self.db_service:
            # Return cached graphs
            graphs = []
            for project_id, graph in list(self._cache.items())[offset:offset+limit]:
                graphs.append({
                    "id": f"graph-{project_id}",
                    "project_id": project_id,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                    "created_at": graph.created_at.isoformat() if graph.created_at else None,
                    "updated_at": graph.updated_at.isoformat() if graph.updated_at else None,
                })
            return graphs

        try:
            rows = await self.db_service.fetch_all(
                """
                SELECT id, project_id, node_count, edge_count, created_at, updated_at, metadata
                FROM arkham_graph.graphs
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
                """,
                {"limit": limit, "offset": offset}
            )
            return [
                {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "node_count": row["node_count"],
                    "edge_count": row["edge_count"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "metadata": _parse_jsonb(row["metadata"], {}),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error listing graphs: {e}")
            return []

    def clear_cache(self) -> None:
        """Clear in-memory cache."""
        self._cache.clear()
        logger.info("Graph cache cleared")

    async def _persist_graph(self, graph: Graph) -> None:
        """
        Persist graph to database.

        Args:
            graph: Graph to persist
        """
        if not self.db_service:
            return

        graph_id = f"graph-{graph.project_id}"
        now = datetime.utcnow()

        # Check if graph exists
        existing = await self.db_service.fetch_one(
            "SELECT id FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": graph.project_id}
        )

        if existing:
            # Delete existing nodes and edges (cascade will handle it)
            await self.db_service.execute(
                "DELETE FROM arkham_graph.graphs WHERE project_id = :project_id",
                {"project_id": graph.project_id}
            )

        # Insert graph record
        await self.db_service.execute(
            """
            INSERT INTO arkham_graph.graphs (id, project_id, node_count, edge_count, created_at, updated_at, metadata)
            VALUES (:id, :project_id, :node_count, :edge_count, :created_at, :updated_at, :metadata)
            """,
            {
                "id": graph_id,
                "project_id": graph.project_id,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "created_at": graph.created_at or now,
                "updated_at": now,
                "metadata": json.dumps(graph.metadata or {}),
            }
        )

        # Insert nodes in batches
        if graph.nodes:
            for node in graph.nodes:
                await self.db_service.execute(
                    """
                    INSERT INTO arkham_graph.nodes
                    (id, graph_id, entity_id, entity_type, label, document_count, degree, properties, created_at)
                    VALUES (:id, :graph_id, :entity_id, :entity_type, :label, :document_count, :degree, :properties, :created_at)
                    """,
                    {
                        "id": node.id,
                        "graph_id": graph_id,
                        "entity_id": node.entity_id,
                        "entity_type": node.entity_type,
                        "label": node.label,
                        "document_count": node.document_count,
                        "degree": node.degree,
                        "properties": json.dumps(node.properties or {}),
                        "created_at": node.created_at or now,
                    }
                )

        # Insert edges in batches
        if graph.edges:
            for edge in graph.edges:
                edge_id = f"edge-{uuid.uuid4().hex[:8]}"
                await self.db_service.execute(
                    """
                    INSERT INTO arkham_graph.edges
                    (id, graph_id, source_id, target_id, relationship_type, weight, co_occurrence_count, document_ids, properties, created_at)
                    VALUES (:id, :graph_id, :source_id, :target_id, :relationship_type, :weight, :co_occurrence_count, :document_ids, :properties, :created_at)
                    """,
                    {
                        "id": edge_id,
                        "graph_id": graph_id,
                        "source_id": edge.source,
                        "target_id": edge.target,
                        "relationship_type": edge.relationship_type,
                        "weight": edge.weight,
                        "co_occurrence_count": edge.co_occurrence_count,
                        "document_ids": json.dumps(edge.document_ids or []),
                        "properties": json.dumps(edge.properties or {}),
                        "created_at": edge.created_at or now,
                    }
                )

        logger.debug(f"Persisted graph {graph_id}: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    async def _load_from_db(self, project_id: str) -> Graph | None:
        """
        Load graph from database.

        Args:
            project_id: Project ID

        Returns:
            Graph object or None if not found
        """
        if not self.db_service:
            return None

        # Load graph metadata
        graph_row = await self.db_service.fetch_one(
            "SELECT id, project_id, node_count, edge_count, created_at, updated_at, metadata FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        if not graph_row:
            return None

        graph_id = graph_row["id"]

        # Load nodes
        node_rows = await self.db_service.fetch_all(
            """
            SELECT id, entity_id, entity_type, label, document_count, degree, properties, centrality_score, community_id, created_at
            FROM arkham_graph.nodes
            WHERE graph_id = :graph_id
            """,
            {"graph_id": graph_id}
        )

        nodes = []
        for row in node_rows:
            node = GraphNode(
                id=row["id"],
                entity_id=row["entity_id"],
                label=row["label"] or "",
                entity_type=row["entity_type"] or "unknown",
                document_count=row["document_count"] or 0,
                degree=row["degree"] or 0,
                properties=_parse_jsonb(row["properties"], {}),
                created_at=row["created_at"],
            )
            nodes.append(node)

        # Load edges
        edge_rows = await self.db_service.fetch_all(
            """
            SELECT id, source_id, target_id, relationship_type, weight, co_occurrence_count, document_ids, properties, created_at
            FROM arkham_graph.edges
            WHERE graph_id = :graph_id
            """,
            {"graph_id": graph_id}
        )

        edges = []
        for row in edge_rows:
            edge = GraphEdge(
                source=row["source_id"],
                target=row["target_id"],
                relationship_type=row["relationship_type"] or "related_to",
                weight=row["weight"] or 1.0,
                co_occurrence_count=row["co_occurrence_count"] or 0,
                document_ids=_parse_jsonb(row["document_ids"], []),
                properties=_parse_jsonb(row["properties"], {}),
                created_at=row["created_at"],
            )
            edges.append(edge)

        # Create graph object
        graph = Graph(
            project_id=project_id,
            nodes=nodes,
            edges=edges,
            metadata=_parse_jsonb(graph_row["metadata"], {}),
            created_at=graph_row["created_at"],
            updated_at=graph_row["updated_at"],
        )

        logger.debug(f"Loaded graph from DB: {len(nodes)} nodes, {len(edges)} edges")
        return graph

    async def _delete_from_db(self, project_id: str) -> None:
        """
        Delete graph from database.

        Args:
            project_id: Project ID
        """
        if not self.db_service:
            return

        # Delete graph (cascade will delete nodes and edges)
        await self.db_service.execute(
            "DELETE FROM arkham_graph.graphs WHERE project_id = :project_id",
            {"project_id": project_id}
        )

        logger.debug(f"Deleted graph from DB for project {project_id}")

    async def get_graph_count(self) -> int:
        """Get total count of graphs."""
        if not self.db_service:
            return len(self._cache)

        try:
            result = await self.db_service.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_graph.graphs",
                {}
            )
            return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Error counting graphs: {e}")
            return 0
