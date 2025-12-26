"""Tests for graph shard models."""

import pytest
from datetime import datetime

from arkham_shard_graph.models import (
    # Enums
    RelationshipType,
    CentralityMetric,
    ExportFormat,
    CommunityAlgorithm,
    # Dataclasses
    GraphNode,
    GraphEdge,
    Graph,
    GraphPath,
    CentralityResult,
    Community,
    GraphStatistics,
    # Pydantic models
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
)


# --- Enum Tests ---


class TestRelationshipType:
    """Test RelationshipType enum."""

    def test_enum_values(self):
        """Test all enum values are defined."""
        assert RelationshipType.WORKS_FOR.value == "works_for"
        assert RelationshipType.AFFILIATED_WITH.value == "affiliated_with"
        assert RelationshipType.LOCATED_IN.value == "located_in"
        assert RelationshipType.MENTIONED_WITH.value == "mentioned_with"
        assert RelationshipType.RELATED_TO.value == "related_to"
        assert RelationshipType.TEMPORAL.value == "temporal"
        assert RelationshipType.HIERARCHICAL.value == "hierarchical"

    def test_enum_membership(self):
        """Test enum membership."""
        assert "works_for" in [e.value for e in RelationshipType]
        assert len(list(RelationshipType)) == 7


class TestCentralityMetric:
    """Test CentralityMetric enum."""

    def test_enum_values(self):
        """Test all enum values are defined."""
        assert CentralityMetric.DEGREE.value == "degree"
        assert CentralityMetric.BETWEENNESS.value == "betweenness"
        assert CentralityMetric.PAGERANK.value == "pagerank"
        assert CentralityMetric.ALL.value == "all"

    def test_enum_count(self):
        """Test enum has expected number of values."""
        assert len(list(CentralityMetric)) == 4


class TestExportFormat:
    """Test ExportFormat enum."""

    def test_enum_values(self):
        """Test all enum values are defined."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.GRAPHML.value == "graphml"
        assert ExportFormat.GEXF.value == "gexf"

    def test_enum_count(self):
        """Test enum has expected number of values."""
        assert len(list(ExportFormat)) == 3


class TestCommunityAlgorithm:
    """Test CommunityAlgorithm enum."""

    def test_enum_values(self):
        """Test all enum values are defined."""
        assert CommunityAlgorithm.LOUVAIN.value == "louvain"
        assert CommunityAlgorithm.LABEL_PROPAGATION.value == "label_propagation"
        assert CommunityAlgorithm.CONNECTED_COMPONENTS.value == "connected_components"

    def test_enum_count(self):
        """Test enum has expected number of values."""
        assert len(list(CommunityAlgorithm)) == 3


# --- Dataclass Tests ---


class TestGraphNode:
    """Test GraphNode dataclass."""

    def test_node_creation(self):
        """Test creating a graph node."""
        node = GraphNode(
            id="node1",
            entity_id="ent1",
            label="Entity 1",
            entity_type="person",
        )

        assert node.id == "node1"
        assert node.entity_id == "ent1"
        assert node.label == "Entity 1"
        assert node.entity_type == "person"
        assert node.document_count == 0
        assert node.degree == 0
        assert node.properties == {}
        assert isinstance(node.created_at, datetime)

    def test_node_with_all_fields(self):
        """Test creating node with all fields."""
        created = datetime(2024, 1, 1)
        node = GraphNode(
            id="node1",
            entity_id="ent1",
            label="Entity 1",
            entity_type="person",
            document_count=5,
            degree=3,
            properties={"key": "value"},
            created_at=created,
        )

        assert node.document_count == 5
        assert node.degree == 3
        assert node.properties == {"key": "value"}
        assert node.created_at == created

    def test_node_to_dict(self):
        """Test converting node to dictionary."""
        node = GraphNode(
            id="node1",
            entity_id="ent1",
            label="Entity 1",
            entity_type="person",
            document_count=5,
            degree=3,
        )

        data = node.to_dict()

        assert data["id"] == "node1"
        assert data["entity_id"] == "ent1"
        assert data["label"] == "Entity 1"
        assert data["entity_type"] == "person"
        assert data["document_count"] == 5
        assert data["degree"] == 3
        assert data["properties"] == {}
        assert "created_at" in data


class TestGraphEdge:
    """Test GraphEdge dataclass."""

    def test_edge_creation(self):
        """Test creating a graph edge."""
        edge = GraphEdge(
            source="node1",
            target="node2",
            relationship_type="works_for",
            weight=0.8,
        )

        assert edge.source == "node1"
        assert edge.target == "node2"
        assert edge.relationship_type == "works_for"
        assert edge.weight == 0.8
        assert edge.document_ids == []
        assert edge.co_occurrence_count == 0
        assert edge.properties == {}
        assert isinstance(edge.created_at, datetime)

    def test_edge_with_all_fields(self):
        """Test creating edge with all fields."""
        created = datetime(2024, 1, 1)
        edge = GraphEdge(
            source="node1",
            target="node2",
            relationship_type="works_for",
            weight=0.8,
            document_ids=["doc1", "doc2"],
            co_occurrence_count=5,
            properties={"context": "investigation"},
            created_at=created,
        )

        assert edge.document_ids == ["doc1", "doc2"]
        assert edge.co_occurrence_count == 5
        assert edge.properties == {"context": "investigation"}
        assert edge.created_at == created

    def test_edge_to_dict(self):
        """Test converting edge to dictionary."""
        edge = GraphEdge(
            source="node1",
            target="node2",
            relationship_type="works_for",
            weight=0.8,
            document_ids=["doc1"],
            co_occurrence_count=3,
        )

        data = edge.to_dict()

        assert data["source"] == "node1"
        assert data["target"] == "node2"
        assert data["relationship_type"] == "works_for"
        assert data["weight"] == 0.8
        assert data["document_ids"] == ["doc1"]
        assert data["co_occurrence_count"] == 3
        assert "created_at" in data


class TestGraph:
    """Test Graph dataclass."""

    def test_graph_creation(self):
        """Test creating a graph."""
        graph = Graph(project_id="proj1")

        assert graph.project_id == "proj1"
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.metadata == {}
        assert isinstance(graph.created_at, datetime)
        assert isinstance(graph.updated_at, datetime)

    def test_graph_with_nodes_and_edges(self):
        """Test creating graph with nodes and edges."""
        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="org"),
        ]
        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.9)
        ]

        graph = Graph(
            project_id="proj1",
            nodes=nodes,
            edges=edges,
            metadata={"custom": "data"},
        )

        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.metadata["custom"] == "data"

    def test_graph_to_dict(self):
        """Test converting graph to dictionary."""
        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
        ]
        edges = [
            GraphEdge(source="n1", target="n1", relationship_type="related_to", weight=0.5)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)
        data = graph.to_dict()

        assert data["project_id"] == "proj1"
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["metadata"]["entity_count"] == 1
        assert data["metadata"]["relationship_count"] == 1
        assert "created_at" in data["metadata"]
        assert "updated_at" in data["metadata"]


class TestGraphPath:
    """Test GraphPath dataclass."""

    def test_path_creation(self):
        """Test creating a graph path."""
        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n2", target="n3", relationship_type="affiliated_with", weight=0.7),
        ]

        path = GraphPath(
            source_entity_id="e1",
            target_entity_id="e3",
            path=["n1", "n2", "n3"],
            edges=edges,
            total_weight=1.5,
            path_length=2,
        )

        assert path.source_entity_id == "e1"
        assert path.target_entity_id == "e3"
        assert path.path == ["n1", "n2", "n3"]
        assert len(path.edges) == 2
        assert path.total_weight == 1.5
        assert path.path_length == 2

    def test_path_to_dict(self):
        """Test converting path to dictionary."""
        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8)
        ]

        path = GraphPath(
            source_entity_id="e1",
            target_entity_id="e2",
            path=["n1", "n2"],
            edges=edges,
            total_weight=0.8,
            path_length=1,
        )

        data = path.to_dict()

        assert data["source_entity_id"] == "e1"
        assert data["target_entity_id"] == "e2"
        assert data["path"] == ["n1", "n2"]
        assert data["path_length"] == 1
        assert len(data["edges"]) == 1
        assert data["total_weight"] == 0.8


class TestCentralityResult:
    """Test CentralityResult dataclass."""

    def test_centrality_result_creation(self):
        """Test creating centrality result."""
        result = CentralityResult(
            entity_id="e1",
            label="Entity 1",
            score=0.95,
            rank=1,
        )

        assert result.entity_id == "e1"
        assert result.label == "Entity 1"
        assert result.score == 0.95
        assert result.rank == 1
        assert result.entity_type == ""

    def test_centrality_result_with_type(self):
        """Test creating centrality result with entity type."""
        result = CentralityResult(
            entity_id="e1",
            label="Entity 1",
            score=0.85,
            rank=2,
            entity_type="person",
        )

        assert result.entity_type == "person"

    def test_centrality_result_to_dict(self):
        """Test converting centrality result to dictionary."""
        result = CentralityResult(
            entity_id="e1",
            label="Entity 1",
            score=0.95,
            rank=1,
            entity_type="person",
        )

        data = result.to_dict()

        assert data["entity_id"] == "e1"
        assert data["label"] == "Entity 1"
        assert data["score"] == 0.95
        assert data["rank"] == 1
        assert data["entity_type"] == "person"


class TestCommunity:
    """Test Community dataclass."""

    def test_community_creation(self):
        """Test creating a community."""
        community = Community(
            id="comm1",
            entity_ids=["e1", "e2", "e3"],
            size=3,
            density=0.67,
        )

        assert community.id == "comm1"
        assert community.entity_ids == ["e1", "e2", "e3"]
        assert community.size == 3
        assert community.density == 0.67
        assert community.description == ""
        assert community.modularity_contribution == 0.0
        assert community.internal_edges == 0
        assert community.external_edges == 0
        assert isinstance(community.created_at, datetime)

    def test_community_with_metrics(self):
        """Test creating community with metrics."""
        community = Community(
            id="comm1",
            entity_ids=["e1", "e2"],
            size=2,
            density=1.0,
            description="Closely connected group",
            modularity_contribution=0.25,
            internal_edges=5,
            external_edges=2,
        )

        assert community.description == "Closely connected group"
        assert community.modularity_contribution == 0.25
        assert community.internal_edges == 5
        assert community.external_edges == 2

    def test_community_to_dict(self):
        """Test converting community to dictionary."""
        community = Community(
            id="comm1",
            entity_ids=["e1", "e2"],
            size=2,
            density=1.0,
            internal_edges=3,
            external_edges=1,
        )

        data = community.to_dict()

        assert data["id"] == "comm1"
        assert data["entity_ids"] == ["e1", "e2"]
        assert data["size"] == 2
        assert data["density"] == 1.0
        assert data["internal_edges"] == 3
        assert data["external_edges"] == 1


class TestGraphStatistics:
    """Test GraphStatistics dataclass."""

    def test_statistics_creation(self):
        """Test creating graph statistics."""
        stats = GraphStatistics(
            project_id="proj1",
            node_count=100,
            edge_count=250,
            density=0.05,
            avg_degree=5.0,
            avg_clustering=0.3,
            connected_components=3,
            diameter=6,
            avg_path_length=3.2,
        )

        assert stats.project_id == "proj1"
        assert stats.node_count == 100
        assert stats.edge_count == 250
        assert stats.density == 0.05
        assert stats.avg_degree == 5.0
        assert stats.avg_clustering == 0.3
        assert stats.connected_components == 3
        assert stats.diameter == 6
        assert stats.avg_path_length == 3.2
        assert stats.entity_type_distribution == {}
        assert stats.relationship_type_distribution == {}

    def test_statistics_with_distributions(self):
        """Test creating statistics with distributions."""
        entity_dist = {"person": 60, "org": 40}
        rel_dist = {"works_for": 150, "affiliated_with": 100}

        stats = GraphStatistics(
            project_id="proj1",
            node_count=100,
            edge_count=250,
            density=0.05,
            avg_degree=5.0,
            avg_clustering=0.3,
            connected_components=1,
            diameter=5,
            avg_path_length=2.8,
            entity_type_distribution=entity_dist,
            relationship_type_distribution=rel_dist,
        )

        assert stats.entity_type_distribution == entity_dist
        assert stats.relationship_type_distribution == rel_dist

    def test_statistics_to_dict(self):
        """Test converting statistics to dictionary."""
        stats = GraphStatistics(
            project_id="proj1",
            node_count=10,
            edge_count=15,
            density=0.33,
            avg_degree=3.0,
            avg_clustering=0.4,
            connected_components=1,
            diameter=3,
            avg_path_length=1.5,
        )

        data = stats.to_dict()

        assert data["project_id"] == "proj1"
        assert data["node_count"] == 10
        assert data["edge_count"] == 15
        assert data["density"] == 0.33
        assert data["avg_degree"] == 3.0
        assert data["avg_clustering"] == 0.4
        assert data["connected_components"] == 1
        assert data["diameter"] == 3
        assert data["avg_path_length"] == 1.5


# --- Pydantic Model Tests ---


class TestBuildGraphRequest:
    """Test BuildGraphRequest Pydantic model."""

    def test_minimal_request(self):
        """Test creating minimal build graph request."""
        req = BuildGraphRequest(project_id="proj1")

        assert req.project_id == "proj1"
        assert req.document_ids is None
        assert req.entity_types is None
        assert req.min_co_occurrence == 1
        assert req.include_temporal is False

    def test_full_request(self):
        """Test creating full build graph request."""
        req = BuildGraphRequest(
            project_id="proj1",
            document_ids=["doc1", "doc2"],
            entity_types=["person", "org"],
            min_co_occurrence=2,
            include_temporal=True,
        )

        assert req.project_id == "proj1"
        assert req.document_ids == ["doc1", "doc2"]
        assert req.entity_types == ["person", "org"]
        assert req.min_co_occurrence == 2
        assert req.include_temporal is True


class TestPathRequest:
    """Test PathRequest Pydantic model."""

    def test_path_request(self):
        """Test creating path request."""
        req = PathRequest(
            project_id="proj1",
            source_entity_id="e1",
            target_entity_id="e2",
        )

        assert req.project_id == "proj1"
        assert req.source_entity_id == "e1"
        assert req.target_entity_id == "e2"
        assert req.max_depth == 6

    def test_path_request_with_depth(self):
        """Test creating path request with custom depth."""
        req = PathRequest(
            project_id="proj1",
            source_entity_id="e1",
            target_entity_id="e2",
            max_depth=4,
        )

        assert req.max_depth == 4


class TestPathResponse:
    """Test PathResponse Pydantic model."""

    def test_path_not_found(self):
        """Test creating path response for no path."""
        resp = PathResponse(
            path_found=False,
            path_length=0,
            path=[],
            edges=[],
            total_weight=0.0,
        )

        assert resp.path_found is False
        assert resp.path_length == 0
        assert resp.path == []
        assert resp.edges == []

    def test_path_found(self):
        """Test creating path response for found path."""
        resp = PathResponse(
            path_found=True,
            path_length=2,
            path=["n1", "n2", "n3"],
            edges=[{"source": "n1", "target": "n2"}],
            total_weight=1.5,
        )

        assert resp.path_found is True
        assert resp.path_length == 2
        assert len(resp.path) == 3
        assert len(resp.edges) == 1


class TestCentralityRequest:
    """Test CentralityRequest Pydantic model."""

    def test_default_request(self):
        """Test creating default centrality request."""
        req = CentralityRequest(project_id="proj1")

        assert req.project_id == "proj1"
        assert req.metric == "all"
        assert req.limit == 50

    def test_custom_request(self):
        """Test creating custom centrality request."""
        req = CentralityRequest(
            project_id="proj1",
            metric="pagerank",
            limit=20,
        )

        assert req.metric == "pagerank"
        assert req.limit == 20


class TestCentralityResponse:
    """Test CentralityResponse Pydantic model."""

    def test_centrality_response(self):
        """Test creating centrality response."""
        resp = CentralityResponse(
            project_id="proj1",
            metric="pagerank",
            results=[{"entity_id": "e1", "score": 0.95}],
            calculated_at="2024-01-01T00:00:00",
        )

        assert resp.project_id == "proj1"
        assert resp.metric == "pagerank"
        assert len(resp.results) == 1
        assert resp.calculated_at == "2024-01-01T00:00:00"


class TestCommunityRequest:
    """Test CommunityRequest Pydantic model."""

    def test_default_request(self):
        """Test creating default community request."""
        req = CommunityRequest(project_id="proj1")

        assert req.project_id == "proj1"
        assert req.algorithm == "louvain"
        assert req.min_community_size == 3
        assert req.resolution == 1.0

    def test_custom_request(self):
        """Test creating custom community request."""
        req = CommunityRequest(
            project_id="proj1",
            algorithm="label_propagation",
            min_community_size=5,
            resolution=1.5,
        )

        assert req.algorithm == "label_propagation"
        assert req.min_community_size == 5
        assert req.resolution == 1.5


class TestCommunityResponse:
    """Test CommunityResponse Pydantic model."""

    def test_community_response(self):
        """Test creating community response."""
        resp = CommunityResponse(
            project_id="proj1",
            community_count=3,
            communities=[{"id": "comm1", "size": 5}],
            modularity=0.45,
        )

        assert resp.project_id == "proj1"
        assert resp.community_count == 3
        assert len(resp.communities) == 1
        assert resp.modularity == 0.45


class TestNeighborsRequest:
    """Test NeighborsRequest Pydantic model."""

    def test_default_request(self):
        """Test creating default neighbors request."""
        req = NeighborsRequest(
            entity_id="e1",
            project_id="proj1",
        )

        assert req.entity_id == "e1"
        assert req.project_id == "proj1"
        assert req.depth == 1
        assert req.min_weight == 0.0
        assert req.limit == 50

    def test_custom_request(self):
        """Test creating custom neighbors request."""
        req = NeighborsRequest(
            entity_id="e1",
            project_id="proj1",
            depth=2,
            min_weight=0.5,
            limit=20,
        )

        assert req.depth == 2
        assert req.min_weight == 0.5
        assert req.limit == 20


class TestExportRequest:
    """Test ExportRequest Pydantic model."""

    def test_default_request(self):
        """Test creating default export request."""
        req = ExportRequest(project_id="proj1")

        assert req.project_id == "proj1"
        assert req.format == "json"
        assert req.include_metadata is True
        assert req.filter is None

    def test_custom_request(self):
        """Test creating custom export request."""
        req = ExportRequest(
            project_id="proj1",
            format="graphml",
            include_metadata=False,
            filter={"entity_types": ["person"]},
        )

        assert req.format == "graphml"
        assert req.include_metadata is False
        assert req.filter == {"entity_types": ["person"]}


class TestExportResponse:
    """Test ExportResponse Pydantic model."""

    def test_export_response(self):
        """Test creating export response."""
        resp = ExportResponse(
            format="json",
            data='{"nodes": []}',
            node_count=10,
            edge_count=15,
            file_size_bytes=1024,
        )

        assert resp.format == "json"
        assert resp.data == '{"nodes": []}'
        assert resp.node_count == 10
        assert resp.edge_count == 15
        assert resp.file_size_bytes == 1024


class TestFilterRequest:
    """Test FilterRequest Pydantic model."""

    def test_minimal_request(self):
        """Test creating minimal filter request."""
        req = FilterRequest(project_id="proj1")

        assert req.project_id == "proj1"
        assert req.entity_types is None
        assert req.min_degree is None
        assert req.min_edge_weight is None
        assert req.relationship_types is None
        assert req.document_ids is None

    def test_full_request(self):
        """Test creating full filter request."""
        req = FilterRequest(
            project_id="proj1",
            entity_types=["person"],
            min_degree=3,
            min_edge_weight=0.5,
            relationship_types=["works_for"],
            document_ids=["doc1"],
        )

        assert req.entity_types == ["person"]
        assert req.min_degree == 3
        assert req.min_edge_weight == 0.5
        assert req.relationship_types == ["works_for"]
        assert req.document_ids == ["doc1"]


class TestGraphResponse:
    """Test GraphResponse Pydantic model."""

    def test_graph_response(self):
        """Test creating graph response."""
        resp = GraphResponse(
            project_id="proj1",
            nodes=[{"id": "n1", "label": "Node 1"}],
            edges=[{"source": "n1", "target": "n2"}],
            metadata={"custom": "data"},
        )

        assert resp.project_id == "proj1"
        assert len(resp.nodes) == 1
        assert len(resp.edges) == 1
        assert resp.metadata == {"custom": "data"}
