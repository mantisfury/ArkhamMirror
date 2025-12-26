"""Tests for the graph builder."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_graph.builder import GraphBuilder
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge, RelationshipType


class TestGraphBuilderCreation:
    """Test graph builder creation."""

    def test_builder_creation_no_services(self):
        """Test creating builder without services."""
        builder = GraphBuilder()

        assert builder.entities_service is None
        assert builder.documents_service is None

    def test_builder_creation_with_services(self):
        """Test creating builder with services."""
        entities_service = MagicMock()
        documents_service = MagicMock()

        builder = GraphBuilder(
            entities_service=entities_service,
            documents_service=documents_service,
        )

        assert builder.entities_service == entities_service
        assert builder.documents_service == documents_service


class TestGraphBuilding:
    """Test graph building."""

    @pytest.mark.asyncio
    async def test_build_basic_graph(self):
        """Test building a basic graph."""
        builder = GraphBuilder()

        graph = await builder.build_graph(project_id="proj1")

        assert graph.project_id == "proj1"
        assert isinstance(graph.nodes, list)
        assert isinstance(graph.edges, list)
        assert len(graph.nodes) > 0
        assert graph.metadata["min_co_occurrence"] == 1

    @pytest.mark.asyncio
    async def test_build_graph_with_min_co_occurrence(self):
        """Test building graph with minimum co-occurrence."""
        builder = GraphBuilder()

        graph = await builder.build_graph(
            project_id="proj1",
            min_co_occurrence=3,
        )

        assert graph.metadata["min_co_occurrence"] == 3
        # Edges should have co_occurrence_count >= 3
        for edge in graph.edges:
            assert edge.co_occurrence_count >= 3

    @pytest.mark.asyncio
    async def test_build_graph_with_entity_types(self):
        """Test building graph with entity type filter."""
        builder = GraphBuilder()

        entity_types = ["person", "org"]
        graph = await builder.build_graph(
            project_id="proj1",
            entity_types=entity_types,
        )

        assert graph.metadata["entity_types"] == entity_types

    @pytest.mark.asyncio
    async def test_build_graph_with_document_filter(self):
        """Test building graph with document filter."""
        builder = GraphBuilder()

        document_ids = ["doc1", "doc2"]
        graph = await builder.build_graph(
            project_id="proj1",
            document_ids=document_ids,
        )

        assert graph.metadata["document_ids"] == document_ids

    @pytest.mark.asyncio
    async def test_build_graph_with_temporal(self):
        """Test building graph with temporal relationships."""
        builder = GraphBuilder()

        graph = await builder.build_graph(
            project_id="proj1",
            include_temporal=True,
        )

        assert graph.metadata["include_temporal"] is True


class TestNodeBuilding:
    """Test node building."""

    def test_build_nodes(self):
        """Test building nodes from entities."""
        builder = GraphBuilder()

        entities = [
            {
                "id": "e1",
                "label": "Entity 1",
                "entity_type": "person",
                "document_count": 5,
                "properties": {"age": 30},
            },
            {
                "id": "e2",
                "label": "Entity 2",
                "entity_type": "org",
                "document_count": 3,
            },
        ]

        nodes = builder._build_nodes(entities)

        assert len(nodes) == 2

        assert nodes[0].id == "e1"
        assert nodes[0].label == "Entity 1"
        assert nodes[0].entity_type == "person"
        assert nodes[0].document_count == 5
        assert nodes[0].properties == {"age": 30}

        assert nodes[1].id == "e2"
        assert nodes[1].label == "Entity 2"
        assert nodes[1].entity_type == "org"
        assert nodes[1].document_count == 3

    def test_build_nodes_with_defaults(self):
        """Test building nodes with default values."""
        builder = GraphBuilder()

        entities = [
            {"id": "e1"},
        ]

        nodes = builder._build_nodes(entities)

        assert len(nodes) == 1
        assert nodes[0].id == "e1"
        assert nodes[0].label == "e1"
        assert nodes[0].entity_type == "unknown"
        assert nodes[0].document_count == 0


class TestEdgeBuilding:
    """Test edge building."""

    def test_build_edges(self):
        """Test building edges from co-occurrences."""
        builder = GraphBuilder()

        co_occurrences = {
            ("e1", "e2"): {
                "count": 5,
                "document_ids": ["doc1", "doc2"],
                "relationship_type": "works_for",
            },
            ("e2", "e3"): {
                "count": 2,
                "document_ids": ["doc3"],
                "relationship_type": "affiliated_with",
            },
        }

        edges = builder._build_edges(co_occurrences, min_co_occurrence=1)

        assert len(edges) == 2

        assert edges[0].source == "e1"
        assert edges[0].target == "e2"
        assert edges[0].relationship_type == "works_for"
        assert edges[0].co_occurrence_count == 5
        assert edges[0].document_ids == ["doc1", "doc2"]
        assert 0.0 <= edges[0].weight <= 1.0

    def test_build_edges_with_min_threshold(self):
        """Test building edges with minimum threshold."""
        builder = GraphBuilder()

        co_occurrences = {
            ("e1", "e2"): {"count": 5},
            ("e2", "e3"): {"count": 2},
            ("e3", "e4"): {"count": 1},
        }

        edges = builder._build_edges(co_occurrences, min_co_occurrence=3)

        # Only edge with count >= 3 should be included
        assert len(edges) == 1
        assert edges[0].co_occurrence_count == 5


class TestNodeDegrees:
    """Test node degree calculation."""

    def test_update_node_degrees(self):
        """Test updating node degrees from edges."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="works_for", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.6),
        ]

        builder._update_node_degrees(nodes, edges)

        assert nodes[0].degree == 2  # n1 connected to n2, n3
        assert nodes[1].degree == 2  # n2 connected to n1, n3
        assert nodes[2].degree == 2  # n3 connected to n1, n2

    def test_update_node_degrees_isolated(self):
        """Test degree calculation with isolated node."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
        ]

        edges = []

        builder._update_node_degrees(nodes, edges)

        assert nodes[0].degree == 0
        assert nodes[1].degree == 0


class TestFilterGraph:
    """Test graph filtering."""

    def test_filter_by_entity_types(self):
        """Test filtering graph by entity types."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=2),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="org", degree=2),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=2),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        filtered = builder.filter_graph(graph, entity_types=["person"])

        # Only person entities
        assert len(filtered.nodes) == 2
        assert all(n.entity_type == "person" for n in filtered.nodes)

        # Only edges between person entities
        assert len(filtered.edges) == 1
        assert filtered.edges[0].source == "n1"
        assert filtered.edges[0].target == "n3"

    def test_filter_by_min_degree(self):
        """Test filtering graph by minimum degree."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=2),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=1),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=2),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        filtered = builder.filter_graph(graph, min_degree=2)

        # Only nodes with original degree >= 2 should be included
        # Note: degrees are recalculated after filtering, so check node IDs instead
        assert len(filtered.nodes) == 2
        node_ids = {n.id for n in filtered.nodes}
        assert "n1" in node_ids
        assert "n3" in node_ids
        assert "n2" not in node_ids  # n2 had degree 1

    def test_filter_by_edge_weight(self):
        """Test filtering graph by edge weight."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=2),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=2),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=2),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.3),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        filtered = builder.filter_graph(graph, min_edge_weight=0.7)

        # Only edges with weight >= 0.7
        assert len(filtered.edges) == 2
        assert all(e.weight >= 0.7 for e in filtered.edges)

    def test_filter_by_relationship_types(self):
        """Test filtering graph by relationship types."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=2),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=2),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=2),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="works_for", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        filtered = builder.filter_graph(graph, relationship_types=["works_for"])

        # Only works_for relationships
        assert len(filtered.edges) == 2
        assert all(e.relationship_type == "works_for" for e in filtered.edges)

    def test_filter_removes_isolated_nodes(self):
        """Test that filtering removes isolated nodes."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=1),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=1),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=0),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.3),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        # Filter with high weight threshold - removes all edges
        filtered = builder.filter_graph(graph, min_edge_weight=0.5)

        # All nodes should be removed (no edges remaining)
        assert len(filtered.nodes) == 0
        assert len(filtered.edges) == 0


class TestExtractSubgraph:
    """Test subgraph extraction."""

    def test_extract_subgraph_depth_1(self):
        """Test extracting 1-hop subgraph."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(5)
        ]

        edges = [
            GraphEdge(source="n0", target="n1", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n0", target="n2", relationship_type="works_for", weight=0.7),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.6),
            GraphEdge(source="n2", target="n4", relationship_type="related_to", weight=0.5),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        subgraph = builder.extract_subgraph(graph, entity_id="n0", depth=1)

        # Should include n0 and its 1-hop neighbors (n1, n2)
        assert len(subgraph.nodes) == 3
        node_ids = {n.id for n in subgraph.nodes}
        assert "n0" in node_ids
        assert "n1" in node_ids
        assert "n2" in node_ids

    def test_extract_subgraph_depth_2(self):
        """Test extracting 2-hop subgraph."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(5)
        ]

        edges = [
            GraphEdge(source="n0", target="n1", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n2", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
            GraphEdge(source="n3", target="n4", relationship_type="works_for", weight=0.5),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        subgraph = builder.extract_subgraph(graph, entity_id="n0", depth=2)

        # Should include n0, n1 (1-hop), n2 (2-hop)
        assert len(subgraph.nodes) == 3
        node_ids = {n.id for n in subgraph.nodes}
        assert "n0" in node_ids
        assert "n1" in node_ids
        assert "n2" in node_ids

    def test_extract_subgraph_with_max_nodes(self):
        """Test extracting subgraph with max node limit."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(10)
        ]

        edges = [
            GraphEdge(source=f"n{i}", target=f"n{i+1}", relationship_type="works_for", weight=0.8)
            for i in range(9)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        subgraph = builder.extract_subgraph(graph, entity_id="n0", depth=10, max_nodes=5)

        # Should limit to 5 nodes
        assert len(subgraph.nodes) <= 5

    def test_extract_subgraph_with_min_weight(self):
        """Test extracting subgraph with minimum weight filter."""
        builder = GraphBuilder()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(4)
        ]

        edges = [
            GraphEdge(source="n0", target="n1", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n0", target="n2", relationship_type="works_for", weight=0.3),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        subgraph = builder.extract_subgraph(graph, entity_id="n0", depth=2, min_weight=0.7)

        # n2 should be excluded (weight 0.3 < 0.7)
        node_ids = {n.id for n in subgraph.nodes}
        assert "n0" in node_ids
        assert "n1" in node_ids
        assert "n2" not in node_ids


class TestAdjacencyList:
    """Test adjacency list building."""

    def test_build_adjacency_list(self):
        """Test building adjacency list from edges."""
        builder = GraphBuilder()

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
        ]

        adjacency = builder._build_adjacency_list(edges)

        assert len(adjacency["n1"]) == 2
        assert ("n2", 0.8) in adjacency["n1"]
        assert ("n3", 0.7) in adjacency["n1"]

        assert len(adjacency["n2"]) == 2
        assert ("n1", 0.8) in adjacency["n2"]
        assert ("n3", 0.6) in adjacency["n2"]

        assert len(adjacency["n3"]) == 2
        assert ("n1", 0.7) in adjacency["n3"]
        assert ("n2", 0.6) in adjacency["n3"]

    def test_build_adjacency_list_empty(self):
        """Test building adjacency list from empty edges."""
        builder = GraphBuilder()

        adjacency = builder._build_adjacency_list([])

        assert len(adjacency) == 0
