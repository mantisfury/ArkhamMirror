"""Graph builder - constructs entity relationship graphs from documents."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from .models import Graph, GraphNode, GraphEdge, RelationshipType

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds entity relationship graphs from document data.

    Uses co-occurrence analysis and explicit relationships to establish
    entity connections.
    """

    def __init__(self, entities_service=None, documents_service=None, db_service=None):
        """
        Initialize graph builder.

        Args:
            entities_service: Service for entity data
            documents_service: Service for document data
            db_service: Database service for direct queries
        """
        self.entities_service = entities_service
        self.documents_service = documents_service
        self.db_service = db_service

    async def build_graph(
        self,
        project_id: str,
        document_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        min_co_occurrence: int = 1,
        include_temporal: bool = False,
        include_document_entities: bool = True,
        include_cooccurrences: bool = True,
    ) -> Graph:
        """
        Build entity relationship graph.

        Args:
            project_id: Project ID
            document_ids: Optional list of document IDs to include
            entity_types: Optional filter for entity types
            min_co_occurrence: Minimum co-occurrence count for edges
            include_temporal: Include temporal relationships
            include_document_entities: Include entities from documents (default True)
            include_cooccurrences: Include co-occurrence edges (default True)

        Returns:
            Constructed Graph object
        """
        logger.info(f"Building graph for project {project_id} (entities={include_document_entities}, cooccurrences={include_cooccurrences})")

        entities = []
        co_occurrences: dict[tuple[str, str], dict[str, Any]] = {}

        # Get entities from project (if enabled)
        if include_document_entities:
            entities = await self._get_entities(project_id, entity_types, document_ids)
            logger.info(f"Found {len(entities)} entities")

            # Get co-occurrence data from document mentions (if enabled)
            if include_cooccurrences and entities:
                co_occurrences = await self._get_co_occurrences(
                    project_id, entities, document_ids, min_co_occurrence
                )
                logger.info(f"Found {len(co_occurrences)} entity pairs from co-occurrence")

                # Also get explicit relationships
                relationships = await self._get_explicit_relationships(project_id, entities)
                logger.info(f"Found {len(relationships)} explicit relationships")

                # Merge relationships into co-occurrences
                for key, rel_data in relationships.items():
                    if key in co_occurrences:
                        # Enhance existing co-occurrence with relationship type
                        co_occurrences[key]["relationship_type"] = rel_data["relationship_type"]
                        co_occurrences[key]["count"] = max(co_occurrences[key]["count"], rel_data.get("count", 1))
                    else:
                        co_occurrences[key] = rel_data
        else:
            logger.info("Document entities disabled - building graph from cross-shard sources only")

        # Build nodes (may be empty if entities disabled)
        nodes = self._build_nodes(entities)

        # Build edges (may be empty if co-occurrences disabled)
        edges = self._build_edges(co_occurrences, min_co_occurrence)

        # Update node degrees
        self._update_node_degrees(nodes, edges)

        # Create graph
        graph = Graph(
            project_id=project_id,
            nodes=nodes,
            edges=edges,
            metadata={
                "min_co_occurrence": min_co_occurrence,
                "include_temporal": include_temporal,
                "include_document_entities": include_document_entities,
                "include_cooccurrences": include_cooccurrences,
                "entity_types": entity_types or [],
                "document_ids": document_ids or [],
                "entity_count": len(entities),
                "relationship_count": len(co_occurrences),
            },
        )

        logger.info(
            f"Graph built: {len(nodes)} nodes, {len(edges)} edges"
        )

        return graph

    async def _get_entities(
        self, project_id: str, entity_types: list[str] | None, document_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get entities for the graph from database.

        Args:
            project_id: Project ID
            entity_types: Optional entity type filter
            document_ids: Optional document filter

        Returns:
            List of entity dictionaries
        """
        # Try database first
        if self.db_service:
            try:
                # Build query with optional filters
                # Use arkham_frame.entities table (core entity storage)
                query = """
                    SELECT
                        e.id,
                        e.text as label,
                        e.entity_type,
                        e.metadata,
                        1 as document_count,
                        e.document_id
                    FROM arkham_frame.entities e
                    WHERE e.canonical_id IS NULL
                """
                params: dict[str, Any] = {}

                # Filter by project_id (required for data isolation)
                if project_id:
                    query += " AND e.project_id = :project_id"
                    params["project_id"] = project_id

                # Filter by entity types
                if entity_types:
                    query += " AND e.entity_type = ANY(:entity_types)"
                    params["entity_types"] = entity_types

                # Filter by documents (if specified)
                if document_ids:
                    query += " AND e.document_id = ANY(:document_ids)"
                    params["document_ids"] = document_ids

                query += " ORDER BY e.created_at DESC"
                query += " LIMIT 500"  # Reasonable limit for visualization

                rows = await self.db_service.fetch_all(query, params)

                entities = []
                for row in rows:
                    entities.append({
                        "id": str(row["id"]),
                        "label": row["label"],
                        "entity_type": row["entity_type"],
                        "document_count": row["document_count"] or 0,
                        "properties": row.get("metadata") or {},
                    })

                if entities:
                    return entities

            except Exception as e:
                logger.warning(f"Failed to get entities from database: {e}")

        # Fall back to entities service
        if self.entities_service:
            try:
                entities = await self.entities_service.list_entities(
                    entity_types=entity_types,
                    limit=500,
                )
                return [
                    {
                        "id": str(e.get("id", "")),
                        "label": e.get("name", "Unknown"),
                        "entity_type": e.get("entity_type", "unknown"),
                        "document_count": e.get("document_count", 0),
                        "properties": e.get("metadata", {}),
                    }
                    for e in entities
                ]
            except Exception as e:
                logger.warning(f"Failed to get entities from service: {e}")

        # Return empty list if no data source available
        logger.warning("No entities data source available")
        return []

    async def _get_co_occurrences(
        self,
        project_id: str,
        entities: list[dict[str, Any]],
        document_ids: list[str] | None,
        min_count: int,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """
        Calculate entity co-occurrences from document mentions.

        Args:
            project_id: Project ID
            entities: List of entities
            document_ids: Optional document filter
            min_count: Minimum co-occurrence count

        Returns:
            Dictionary mapping entity pairs to co-occurrence data
        """
        co_occurrences: dict[tuple[str, str], dict[str, Any]] = {}
        entity_ids = [e["id"] for e in entities]

        if not entity_ids:
            return co_occurrences

        # Try database first
        if self.db_service:
            try:
                # Query co-occurrences: entities that appear in the same document
                # Use arkham_frame.entities table directly
                query = """
                    SELECT
                        e1.id as entity_a,
                        e2.id as entity_b,
                        COUNT(DISTINCT e1.document_id) as co_occurrence_count,
                        ARRAY_AGG(DISTINCT e1.document_id::text) as document_ids
                    FROM arkham_frame.entities e1
                    JOIN arkham_frame.entities e2
                        ON e1.document_id = e2.document_id
                        AND e1.id < e2.id  -- Avoid duplicates
                    WHERE e1.id = ANY(:entity_ids)
                      AND e2.id = ANY(:entity_ids)
                """
                params: dict[str, Any] = {"entity_ids": entity_ids}

                if document_ids:
                    query += " AND e1.document_id = ANY(:document_ids)"
                    params["document_ids"] = document_ids

                query += """
                    GROUP BY e1.id, e2.id
                    HAVING COUNT(DISTINCT e1.document_id) >= :min_count
                    ORDER BY co_occurrence_count DESC
                    LIMIT 1000
                """
                params["min_count"] = min_count

                rows = await self.db_service.fetch_all(query, params)

                for row in rows:
                    ent_a = str(row["entity_a"])
                    ent_b = str(row["entity_b"])

                    # Ensure consistent ordering
                    if ent_a > ent_b:
                        ent_a, ent_b = ent_b, ent_a

                    doc_ids = row["document_ids"] or []
                    if isinstance(doc_ids, str):
                        doc_ids = [doc_ids]

                    co_occurrences[(ent_a, ent_b)] = {
                        "count": row["co_occurrence_count"],
                        "document_ids": doc_ids,
                        "relationship_type": RelationshipType.MENTIONED_WITH.value,
                    }

                if co_occurrences:
                    return co_occurrences

            except Exception as e:
                logger.warning(f"Failed to get co-occurrences from database: {e}")

        # Fall back to simple heuristic if no DB
        # Connect entities of the same document count (rough approximation)
        logger.debug("Using fallback co-occurrence calculation")
        for i in range(len(entities)):
            for j in range(i + 1, min(i + 5, len(entities))):  # Connect nearby entities
                ent_a = entities[i]["id"]
                ent_b = entities[j]["id"]

                # Simple heuristic based on document overlap
                shared_docs = min(
                    entities[i].get("document_count", 0),
                    entities[j].get("document_count", 0)
                )

                if shared_docs >= min_count:
                    co_occurrences[(ent_a, ent_b)] = {
                        "count": shared_docs,
                        "document_ids": [],
                        "relationship_type": RelationshipType.MENTIONED_WITH.value,
                    }

        return co_occurrences

    async def _get_explicit_relationships(
        self,
        project_id: str,
        entities: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """
        Get explicit relationships between entities.

        Args:
            project_id: Project ID
            entities: List of entities

        Returns:
            Dictionary mapping entity pairs to relationship data
        """
        relationships: dict[tuple[str, str], dict[str, Any]] = {}
        entity_ids = [e["id"] for e in entities]

        if not entity_ids or not self.db_service:
            return relationships

        try:
            # Use arkham_frame.entity_relationships if it exists
            query = """
                SELECT
                    source_id,
                    target_id,
                    relationship_type,
                    confidence,
                    metadata
                FROM arkham_frame.entity_relationships
                WHERE source_id = ANY(:entity_ids)
                  AND target_id = ANY(:entity_ids)
            """
            rows = await self.db_service.fetch_all(query, {"entity_ids": entity_ids})

            for row in rows:
                source = str(row["source_id"])
                target = str(row["target_id"])

                # Ensure consistent ordering
                if source > target:
                    source, target = target, source

                relationships[(source, target)] = {
                    "count": 1,
                    "document_ids": [],
                    "relationship_type": row["relationship_type"] or RelationshipType.RELATED_TO.value,
                    "confidence": row.get("confidence", 1.0),
                    "properties": row.get("metadata") or {},
                }

        except Exception as e:
            logger.warning(f"Failed to get explicit relationships: {e}")

        return relationships

    def _build_nodes(self, entities: list[dict[str, Any]]) -> list[GraphNode]:
        """
        Build graph nodes from entities.

        Args:
            entities: List of entity dictionaries

        Returns:
            List of GraphNode objects
        """
        nodes = []

        for entity in entities:
            node = GraphNode(
                id=entity["id"],
                entity_id=entity["id"],
                label=entity.get("label", entity["id"]),
                entity_type=entity.get("entity_type", "unknown"),
                document_count=entity.get("document_count", 0),
                properties=entity.get("properties", {}),
            )
            nodes.append(node)

        return nodes

    def _build_edges(
        self,
        co_occurrences: dict[tuple[str, str], dict[str, Any]],
        min_co_occurrence: int,
    ) -> list[GraphEdge]:
        """
        Build graph edges from co-occurrence data.

        Args:
            co_occurrences: Co-occurrence data
            min_co_occurrence: Minimum count threshold

        Returns:
            List of GraphEdge objects
        """
        edges = []

        for (source, target), data in co_occurrences.items():
            count = data.get("count", 0)

            if count < min_co_occurrence:
                continue

            # Calculate weight (normalized by count)
            weight = min(1.0, count / 10.0)

            edge = GraphEdge(
                source=source,
                target=target,
                relationship_type=data.get(
                    "relationship_type", RelationshipType.MENTIONED_WITH.value
                ),
                weight=weight,
                document_ids=data.get("document_ids", []),
                co_occurrence_count=count,
                properties=data.get("properties", {}),
            )
            edges.append(edge)

        return edges

    def _update_node_degrees(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> None:
        """
        Update node degree counts.

        Args:
            nodes: List of nodes
            edges: List of edges
        """
        degree_map = defaultdict(int)

        for edge in edges:
            degree_map[edge.source] += 1
            degree_map[edge.target] += 1

        for node in nodes:
            node.degree = degree_map.get(node.id, 0)

    def filter_graph(
        self,
        graph: Graph,
        entity_types: list[str] | None = None,
        min_degree: int | None = None,
        min_edge_weight: float | None = None,
        relationship_types: list[str] | None = None,
        document_ids: list[str] | None = None,
    ) -> Graph:
        """
        Filter graph by various criteria.

        Args:
            graph: Original graph
            entity_types: Entity types to include
            min_degree: Minimum node degree
            min_edge_weight: Minimum edge weight
            relationship_types: Relationship types to include
            document_ids: Document IDs to include

        Returns:
            Filtered Graph object
        """
        # Filter nodes
        filtered_nodes = graph.nodes

        if entity_types:
            filtered_nodes = [
                n for n in filtered_nodes if n.entity_type in entity_types
            ]

        if min_degree is not None:
            filtered_nodes = [n for n in filtered_nodes if n.degree >= min_degree]

        # Get filtered node IDs
        node_ids = {n.id for n in filtered_nodes}

        # Filter edges
        filtered_edges = graph.edges

        # Only include edges between filtered nodes
        filtered_edges = [
            e for e in filtered_edges
            if e.source in node_ids and e.target in node_ids
        ]

        if min_edge_weight is not None:
            filtered_edges = [e for e in filtered_edges if e.weight >= min_edge_weight]

        if relationship_types:
            filtered_edges = [
                e for e in filtered_edges if e.relationship_type in relationship_types
            ]

        if document_ids:
            filtered_edges = [
                e for e in filtered_edges
                if any(doc_id in e.document_ids for doc_id in document_ids)
            ]

        # Update node degrees after edge filtering
        self._update_node_degrees(filtered_nodes, filtered_edges)

        # Remove isolated nodes (no edges)
        connected_node_ids = set()
        for edge in filtered_edges:
            connected_node_ids.add(edge.source)
            connected_node_ids.add(edge.target)

        filtered_nodes = [n for n in filtered_nodes if n.id in connected_node_ids]

        # Create filtered graph
        filtered_graph = Graph(
            project_id=graph.project_id,
            nodes=filtered_nodes,
            edges=filtered_edges,
            metadata={
                **graph.metadata,
                "filtered": True,
                "filter_criteria": {
                    "entity_types": entity_types,
                    "min_degree": min_degree,
                    "min_edge_weight": min_edge_weight,
                    "relationship_types": relationship_types,
                    "document_ids": document_ids,
                },
            },
        )

        return filtered_graph

    def extract_subgraph(
        self,
        graph: Graph,
        entity_id: str,
        depth: int = 2,
        max_nodes: int = 100,
        min_weight: float = 0.0,
    ) -> Graph:
        """
        Extract subgraph centered on an entity.

        Args:
            graph: Original graph
            entity_id: Center entity ID
            depth: Maximum distance from center
            max_nodes: Maximum nodes to include
            min_weight: Minimum edge weight

        Returns:
            Subgraph as Graph object
        """
        # Build adjacency list
        adjacency = self._build_adjacency_list(graph.edges)

        # BFS to find nodes within depth
        visited = set()
        queue = [(entity_id, 0)]
        nodes_by_distance = defaultdict(list)

        while queue and len(visited) < max_nodes:
            current, dist = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)
            nodes_by_distance[dist].append(current)

            if dist < depth:
                # Add neighbors
                for neighbor, edge_weight in adjacency.get(current, []):
                    if neighbor not in visited and edge_weight >= min_weight:
                        queue.append((neighbor, dist + 1))

        # Collect nodes
        subgraph_node_ids = visited
        subgraph_nodes = [n for n in graph.nodes if n.id in subgraph_node_ids]

        # Collect edges
        subgraph_edges = [
            e for e in graph.edges
            if e.source in subgraph_node_ids
            and e.target in subgraph_node_ids
            and e.weight >= min_weight
        ]

        # Create subgraph
        subgraph = Graph(
            project_id=graph.project_id,
            nodes=subgraph_nodes,
            edges=subgraph_edges,
            metadata={
                **graph.metadata,
                "subgraph": True,
                "center_entity": entity_id,
                "depth": depth,
                "max_nodes": max_nodes,
            },
        )

        return subgraph

    def _build_adjacency_list(
        self, edges: list[GraphEdge]
    ) -> dict[str, list[tuple[str, float]]]:
        """
        Build adjacency list from edges.

        Args:
            edges: List of edges

        Returns:
            Adjacency list mapping node IDs to (neighbor, weight) tuples
        """
        adjacency = defaultdict(list)

        for edge in edges:
            adjacency[edge.source].append((edge.target, edge.weight))
            adjacency[edge.target].append((edge.source, edge.weight))

        return adjacency
