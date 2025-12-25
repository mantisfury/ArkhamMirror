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

    Uses co-occurrence analysis to establish entity relationships.
    """

    def __init__(self, entities_service=None, documents_service=None):
        """
        Initialize graph builder.

        Args:
            entities_service: Service for entity data
            documents_service: Service for document data
        """
        self.entities_service = entities_service
        self.documents_service = documents_service

    async def build_graph(
        self,
        project_id: str,
        document_ids: list[str] | None = None,
        entity_types: list[str] | None = None,
        min_co_occurrence: int = 1,
        include_temporal: bool = False,
    ) -> Graph:
        """
        Build entity relationship graph.

        Args:
            project_id: Project ID
            document_ids: Optional list of document IDs to include
            entity_types: Optional filter for entity types
            min_co_occurrence: Minimum co-occurrence count for edges
            include_temporal: Include temporal relationships

        Returns:
            Constructed Graph object
        """
        logger.info(f"Building graph for project {project_id}")

        # Get entities from project
        entities = await self._get_entities(project_id, entity_types)
        logger.info(f"Found {len(entities)} entities")

        # Get co-occurrence data
        co_occurrences = await self._get_co_occurrences(
            project_id, entities, document_ids, min_co_occurrence
        )
        logger.info(f"Found {len(co_occurrences)} entity pairs")

        # Build nodes
        nodes = self._build_nodes(entities)

        # Build edges
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
                "entity_types": entity_types or [],
                "document_ids": document_ids or [],
            },
        )

        logger.info(
            f"Graph built: {len(nodes)} nodes, {len(edges)} edges"
        )

        return graph

    async def _get_entities(
        self, project_id: str, entity_types: list[str] | None
    ) -> list[dict[str, Any]]:
        """
        Get entities for the graph.

        Args:
            project_id: Project ID
            entity_types: Optional entity type filter

        Returns:
            List of entity dictionaries
        """
        # TODO: Implement actual entity fetching via service
        # For now, return mock data

        # In real implementation:
        # if self.entities_service:
        #     entities = await self.entities_service.get_by_project(
        #         project_id, entity_types=entity_types
        #     )
        #     return entities

        # Mock implementation
        return [
            {
                "id": f"ent{i}",
                "label": f"Entity {i}",
                "entity_type": entity_types[i % len(entity_types)] if entity_types else "person",
                "document_count": i + 1,
                "properties": {},
            }
            for i in range(10)
        ]

    async def _get_co_occurrences(
        self,
        project_id: str,
        entities: list[dict[str, Any]],
        document_ids: list[str] | None,
        min_count: int,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """
        Calculate entity co-occurrences.

        Args:
            project_id: Project ID
            entities: List of entities
            document_ids: Optional document filter
            min_count: Minimum co-occurrence count

        Returns:
            Dictionary mapping entity pairs to co-occurrence data
        """
        # TODO: Implement actual co-occurrence analysis
        # For now, return mock data

        # In real implementation:
        # if self.documents_service:
        #     co_occurrences = await self.documents_service.get_entity_co_occurrences(
        #         project_id, document_ids=document_ids
        #     )
        #     return {
        #         (pair[0], pair[1]): data
        #         for pair, data in co_occurrences.items()
        #         if data["count"] >= min_count
        #     }

        # Mock implementation
        co_occurrences = {}
        entity_ids = [e["id"] for e in entities]

        for i in range(len(entity_ids)):
            for j in range(i + 1, min(i + 4, len(entity_ids))):
                ent_a = entity_ids[i]
                ent_b = entity_ids[j]
                count = (i + j) % 5 + 1

                if count >= min_count:
                    co_occurrences[(ent_a, ent_b)] = {
                        "count": count,
                        "document_ids": [f"doc{k}" for k in range(count)],
                        "relationship_type": RelationshipType.MENTIONED_WITH.value,
                    }

        return co_occurrences

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
