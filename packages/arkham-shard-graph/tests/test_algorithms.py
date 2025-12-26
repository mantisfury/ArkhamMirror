"""Tests for graph algorithms."""

import pytest

from arkham_shard_graph.algorithms import GraphAlgorithms
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge


class TestGraphAlgorithmsCreation:
    """Test algorithm class creation."""

    def test_algorithms_creation(self):
        """Test creating algorithms instance."""
        algorithms = GraphAlgorithms()
        assert algorithms is not None


class TestShortestPath:
    """Test shortest path finding."""

    def test_find_shortest_path_simple(self):
        """Test finding shortest path in simple graph."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        # Use node IDs (not entity IDs)
        path = algorithms.find_shortest_path(graph, "n1", "n3")

        assert path is not None
        assert path.source_entity_id == "n1"
        assert path.target_entity_id == "n3"
        assert path.path_length == 2
        assert path.path == ["n1", "n2", "n3"]
        assert len(path.edges) == 2

    def test_find_shortest_path_direct(self):
        """Test finding direct path (single edge)."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        # Use node IDs (not entity IDs)
        path = algorithms.find_shortest_path(graph, "n1", "n2")

        assert path is not None
        assert path.path_length == 1
        assert path.path == ["n1", "n2"]

    def test_find_shortest_path_not_found(self):
        """Test path finding when no path exists."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        path = algorithms.find_shortest_path(graph, "e1", "e3")

        assert path is None

    def test_find_shortest_path_max_depth(self):
        """Test path finding respects max depth."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(6)
        ]

        edges = [
            GraphEdge(source=f"n{i}", target=f"n{i+1}", relationship_type="works_for", weight=0.8)
            for i in range(5)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        # Path from n0 to n5 is length 5, but we set max_depth to 3
        path = algorithms.find_shortest_path(graph, "e0", "e5", max_depth=3)

        assert path is None

    def test_find_shortest_path_with_multiple_paths(self):
        """Test finding shortest path when multiple paths exist."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
            GraphNode(id="n4", entity_id="e4", label="E4", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n4", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n1", target="n3", relationship_type="works_for", weight=0.6),
            GraphEdge(source="n3", target="n4", relationship_type="related_to", weight=0.5),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        # Use node IDs (not entity IDs)
        path = algorithms.find_shortest_path(graph, "n1", "n4")

        assert path is not None
        assert path.path_length == 2  # Both paths have length 2


class TestDegreeCentrality:
    """Test degree centrality calculation."""

    def test_calculate_degree_centrality(self):
        """Test calculating degree centrality."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=3),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=2),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=1),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        results = algorithms.calculate_degree_centrality(graph, limit=10)

        assert len(results) == 3
        assert results[0].entity_id == "e1"
        assert results[0].rank == 1
        assert results[0].score == 1.0  # Highest degree normalized to 1.0
        assert results[1].entity_id == "e2"
        assert results[1].rank == 2
        assert results[2].entity_id == "e3"
        assert results[2].rank == 3

    def test_calculate_degree_centrality_with_limit(self):
        """Test degree centrality with result limit."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person", degree=10-i)
            for i in range(10)
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        results = algorithms.calculate_degree_centrality(graph, limit=5)

        assert len(results) == 5

    def test_calculate_degree_centrality_empty_graph(self):
        """Test degree centrality on empty graph."""
        algorithms = GraphAlgorithms()

        graph = Graph(project_id="proj1")

        results = algorithms.calculate_degree_centrality(graph)

        assert len(results) == 0


class TestBetweennessCentrality:
    """Test betweenness centrality calculation."""

    def test_calculate_betweenness_centrality(self):
        """Test calculating betweenness centrality."""
        algorithms = GraphAlgorithms()

        # Star topology: n1 is center, connected to n2, n3, n4
        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
            GraphNode(id="n4", entity_id="e4", label="E4", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n1", target="n4", relationship_type="related_to", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        results = algorithms.calculate_betweenness_centrality(graph)

        assert len(results) > 0
        # n1 should have highest betweenness (center of star)
        assert results[0].entity_id == "e1"

    def test_calculate_betweenness_centrality_with_limit(self):
        """Test betweenness centrality with result limit."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(5)
        ]

        edges = [
            GraphEdge(source=f"n{i}", target=f"n{i+1}", relationship_type="works_for", weight=0.8)
            for i in range(4)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        results = algorithms.calculate_betweenness_centrality(graph, limit=3)

        assert len(results) == 3


class TestPageRank:
    """Test PageRank calculation."""

    def test_calculate_pagerank(self):
        """Test calculating PageRank."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        results = algorithms.calculate_pagerank(graph)

        assert len(results) == 3
        # All scores should sum approximately to 1
        total_score = sum(r.score for r in results)
        assert 0.9 < total_score < 1.1

    def test_calculate_pagerank_with_damping(self):
        """Test PageRank with custom damping factor."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        results = algorithms.calculate_pagerank(graph, damping=0.5)

        assert len(results) == 2

    def test_calculate_pagerank_empty_graph(self):
        """Test PageRank on empty graph."""
        algorithms = GraphAlgorithms()

        graph = Graph(project_id="proj1")

        results = algorithms.calculate_pagerank(graph)

        assert len(results) == 0


class TestCommunityDetection:
    """Test community detection."""

    def test_detect_communities_simple(self):
        """Test detecting communities in simple graph."""
        algorithms = GraphAlgorithms()

        # Two separate clusters
        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
            GraphNode(id="n4", entity_id="e4", label="E4", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n3", target="n4", relationship_type="works_for", weight=0.9),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        communities, modularity = algorithms.detect_communities_louvain(graph, min_community_size=2)

        assert len(communities) >= 1
        assert isinstance(modularity, float)

    def test_detect_communities_single_cluster(self):
        """Test detecting community in fully connected graph."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="related_to", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        communities, modularity = algorithms.detect_communities_louvain(graph, min_community_size=3)

        assert len(communities) >= 1

    def test_detect_communities_with_resolution(self):
        """Test community detection with custom resolution."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(6)
        ]

        edges = [
            GraphEdge(source="n0", target="n1", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n3", target="n4", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n4", target="n5", relationship_type="works_for", weight=0.9),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        communities, modularity = algorithms.detect_communities_louvain(
            graph, min_community_size=2, resolution=1.5
        )

        assert isinstance(communities, list)

    def test_detect_communities_empty_graph(self):
        """Test community detection on empty graph."""
        algorithms = GraphAlgorithms()

        graph = Graph(project_id="proj1")

        communities, modularity = algorithms.detect_communities_louvain(graph)

        assert len(communities) == 0
        assert modularity == 0.0


class TestGraphStatistics:
    """Test graph statistics calculation."""

    def test_calculate_statistics(self):
        """Test calculating comprehensive graph statistics."""
        algorithms = GraphAlgorithms()

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

        stats = algorithms.calculate_statistics(graph)

        assert stats.project_id == "proj1"
        assert stats.node_count == 3
        assert stats.edge_count == 3
        assert 0.0 <= stats.density <= 1.0
        assert stats.avg_degree == 2.0
        assert 0.0 <= stats.avg_clustering <= 1.0
        assert stats.connected_components >= 1
        assert stats.entity_type_distribution["person"] == 2
        assert stats.entity_type_distribution["org"] == 1

    def test_calculate_statistics_empty_graph(self):
        """Test statistics for empty graph."""
        algorithms = GraphAlgorithms()

        graph = Graph(project_id="proj1")

        stats = algorithms.calculate_statistics(graph)

        assert stats.node_count == 0
        assert stats.edge_count == 0
        assert stats.density == 0.0
        assert stats.avg_degree == 0.0

    def test_calculate_statistics_disconnected(self):
        """Test statistics for disconnected graph."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=1),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=1),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person", degree=1),
            GraphNode(id="n4", entity_id="e4", label="E4", entity_type="person", degree=1),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n3", target="n4", relationship_type="works_for", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        stats = algorithms.calculate_statistics(graph)

        # Should have 2 connected components
        assert stats.connected_components == 2


class TestGetNeighbors:
    """Test getting entity neighbors."""

    def test_get_neighbors_1hop(self):
        """Test getting 1-hop neighbors."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        result = algorithms.get_neighbors(graph, "n1", depth=1)

        assert result["entity_id"] == "n1"
        assert result["neighbor_count"] == 2
        assert len(result["neighbors"]) == 2

    def test_get_neighbors_2hop(self):
        """Test getting 2-hop neighbors."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        result = algorithms.get_neighbors(graph, "n1", depth=2)

        assert result["neighbor_count"] >= 1

    def test_get_neighbors_with_min_weight(self):
        """Test getting neighbors with weight filter."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
            GraphNode(id="n3", entity_id="e3", label="E3", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.9),
            GraphEdge(source="n1", target="n3", relationship_type="affiliated_with", weight=0.3),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        result = algorithms.get_neighbors(graph, "n1", depth=1, min_weight=0.7)

        # Only n2 should be included (weight 0.9 >= 0.7)
        assert result["neighbor_count"] == 1

    def test_get_neighbors_with_limit(self):
        """Test getting neighbors with result limit."""
        algorithms = GraphAlgorithms()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(10)
        ]

        edges = [
            GraphEdge(source="n0", target=f"n{i}", relationship_type="works_for", weight=0.8)
            for i in range(1, 10)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        result = algorithms.get_neighbors(graph, "n0", depth=1, limit=5)

        assert result["neighbor_count"] <= 5


class TestHelperMethods:
    """Test helper methods."""

    def test_build_adjacency_dict(self):
        """Test building adjacency dictionary."""
        algorithms = GraphAlgorithms()

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        adjacency = algorithms._build_adjacency_dict(edges)

        assert "n2" in adjacency["n1"]
        assert "n1" in adjacency["n2"]
        assert "n3" in adjacency["n2"]
        assert "n2" in adjacency["n3"]

    def test_build_weighted_adjacency(self):
        """Test building weighted adjacency dictionary."""
        algorithms = GraphAlgorithms()

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        adjacency = algorithms._build_weighted_adjacency(edges)

        assert ("n2", 0.8) in adjacency["n1"]
        assert ("n1", 0.8) in adjacency["n2"]
        assert ("n3", 0.7) in adjacency["n2"]
        assert ("n2", 0.7) in adjacency["n3"]
