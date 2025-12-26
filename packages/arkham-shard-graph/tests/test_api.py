"""Tests for graph API endpoints."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_graph.api import router, init_api
from arkham_shard_graph.builder import GraphBuilder
from arkham_shard_graph.algorithms import GraphAlgorithms
from arkham_shard_graph.exporter import GraphExporter
from arkham_shard_graph.storage import GraphStorage
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def initialized_api():
    """Initialize API with components."""
    builder = GraphBuilder()
    algorithms = GraphAlgorithms()
    exporter = GraphExporter()
    storage = GraphStorage()
    event_bus = AsyncMock()

    init_api(
        builder=builder,
        algorithms=algorithms,
        exporter=exporter,
        storage=storage,
        event_bus=event_bus,
    )

    yield {
        "builder": builder,
        "algorithms": algorithms,
        "exporter": exporter,
        "storage": storage,
        "event_bus": event_bus,
    }


class TestAPIInitialization:
    """Test API initialization."""

    def test_init_api(self):
        """Test initializing API."""
        builder = GraphBuilder()
        algorithms = GraphAlgorithms()
        exporter = GraphExporter()

        init_api(builder=builder, algorithms=algorithms, exporter=exporter)

        # API should be initialized
        assert True  # If no error, initialization worked


class TestBuildGraphEndpoint:
    """Test /build endpoint."""

    @pytest.mark.asyncio
    async def test_build_graph_success(self, client, initialized_api):
        """Test building graph."""
        response = client.post(
            "/api/graph/build",
            json={
                "project_id": "proj1",
                "min_co_occurrence": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "node_count" in data
        assert "edge_count" in data
        assert "build_time_ms" in data

    @pytest.mark.asyncio
    async def test_build_graph_with_filters(self, client, initialized_api):
        """Test building graph with filters."""
        response = client.post(
            "/api/graph/build",
            json={
                "project_id": "proj1",
                "document_ids": ["doc1", "doc2"],
                "entity_types": ["person"],
                "min_co_occurrence": 2,
                "include_temporal": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"

    def test_build_graph_not_initialized(self, client):
        """Test building graph when service not initialized."""
        # Reinitialize with None
        init_api(None, None, None, None, None)

        response = client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        assert response.status_code == 503
        assert "not available" in response.json()["detail"]


class TestGetGraphEndpoint:
    """Test /{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_success(self, client, initialized_api):
        """Test getting graph."""
        # Build graph first
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        # Get graph
        response = client.get("/api/graph/proj1")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data


class TestGetEntitySubgraphEndpoint:
    """Test /entity/{entity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_subgraph(self, client, initialized_api):
        """Test getting entity subgraph."""
        # Build graph first
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        # Get subgraph
        response = client.get(
            "/api/graph/entity/ent0",
            params={"project_id": "proj1", "depth": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "nodes" in data
        assert "edges" in data

    @pytest.mark.asyncio
    async def test_get_entity_subgraph_with_limits(self, client, initialized_api):
        """Test getting entity subgraph with limits."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/entity/ent0",
            params={
                "project_id": "proj1",
                "depth": 1,
                "max_nodes": 50,
                "min_weight": 0.5,
            },
        )

        assert response.status_code == 200


class TestFindPathEndpoint:
    """Test /path endpoint."""

    @pytest.mark.asyncio
    async def test_find_path_success(self, client, initialized_api):
        """Test finding path between entities."""
        # Build graph first
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/path",
            json={
                "project_id": "proj1",
                "source_entity_id": "ent0",
                "target_entity_id": "ent1",
                "max_depth": 6,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "path_found" in data
        assert "path_length" in data
        assert "path" in data
        assert "edges" in data

    @pytest.mark.asyncio
    async def test_find_path_not_found(self, client, initialized_api):
        """Test finding path when no path exists."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/path",
            json={
                "project_id": "proj1",
                "source_entity_id": "nonexistent1",
                "target_entity_id": "nonexistent2",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["path_found"] is False

    def test_find_path_not_initialized(self, client):
        """Test finding path when service not initialized."""
        init_api(None, None, None, None, None)

        response = client.post(
            "/api/graph/path",
            json={
                "project_id": "proj1",
                "source_entity_id": "e1",
                "target_entity_id": "e2",
            },
        )

        assert response.status_code == 503


class TestCentralityEndpoint:
    """Test /centrality/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_calculate_centrality_degree(self, client, initialized_api):
        """Test calculating degree centrality."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "degree", "limit": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert data["metric"] == "degree"
        assert "results" in data
        assert "calculated_at" in data

    @pytest.mark.asyncio
    async def test_calculate_centrality_betweenness(self, client, initialized_api):
        """Test calculating betweenness centrality."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "betweenness"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metric"] == "betweenness"

    @pytest.mark.asyncio
    async def test_calculate_centrality_pagerank(self, client, initialized_api):
        """Test calculating PageRank centrality."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "pagerank"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metric"] == "pagerank"

    @pytest.mark.asyncio
    async def test_calculate_centrality_all(self, client, initialized_api):
        """Test calculating all centrality metrics."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "all"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metric"] == "all"

    @pytest.mark.asyncio
    async def test_calculate_centrality_invalid_metric(self, client, initialized_api):
        """Test calculating centrality with invalid metric."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "invalid"},
        )

        assert response.status_code == 400
        assert "Invalid metric" in response.json()["detail"]


class TestCommunitiesEndpoint:
    """Test /communities endpoint."""

    @pytest.mark.asyncio
    async def test_detect_communities_success(self, client, initialized_api):
        """Test detecting communities."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/communities",
            json={
                "project_id": "proj1",
                "algorithm": "louvain",
                "min_community_size": 3,
                "resolution": 1.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "community_count" in data
        assert "communities" in data
        assert "modularity" in data

    @pytest.mark.asyncio
    async def test_detect_communities_custom_params(self, client, initialized_api):
        """Test detecting communities with custom parameters."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/communities",
            json={
                "project_id": "proj1",
                "algorithm": "louvain",
                "min_community_size": 2,
                "resolution": 1.5,
            },
        )

        assert response.status_code == 200


class TestNeighborsEndpoint:
    """Test /neighbors/{entity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_neighbors_success(self, client, initialized_api):
        """Test getting entity neighbors."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/neighbors/ent0",
            params={"project_id": "proj1", "depth": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert "entity_id" in data
        assert "neighbor_count" in data
        assert "neighbors" in data

    @pytest.mark.asyncio
    async def test_get_neighbors_with_filters(self, client, initialized_api):
        """Test getting neighbors with filters."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/neighbors/ent0",
            params={
                "project_id": "proj1",
                "depth": 2,
                "min_weight": 0.5,
                "limit": 20,
            },
        )

        assert response.status_code == 200


class TestExportEndpoint:
    """Test /export endpoint."""

    @pytest.mark.asyncio
    async def test_export_json(self, client, initialized_api):
        """Test exporting graph as JSON."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/export",
            json={
                "project_id": "proj1",
                "format": "json",
                "include_metadata": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert "data" in data
        assert "node_count" in data
        assert "edge_count" in data
        assert "file_size_bytes" in data

    @pytest.mark.asyncio
    async def test_export_graphml(self, client, initialized_api):
        """Test exporting graph as GraphML."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/export",
            json={
                "project_id": "proj1",
                "format": "graphml",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "graphml"
        assert "graphml" in data["data"]

    @pytest.mark.asyncio
    async def test_export_gexf(self, client, initialized_api):
        """Test exporting graph as GEXF."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/export",
            json={
                "project_id": "proj1",
                "format": "gexf",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "gexf"
        assert "gexf" in data["data"]

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client, initialized_api):
        """Test exporting with invalid format."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/export",
            json={
                "project_id": "proj1",
                "format": "invalid",
            },
        )

        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]


class TestStatisticsEndpoint:
    """Test /stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_statistics_success(self, client, initialized_api):
        """Test getting graph statistics."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.get(
            "/api/graph/stats",
            params={"project_id": "proj1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "node_count" in data
        assert "edge_count" in data
        assert "density" in data
        assert "avg_degree" in data
        assert "connected_components" in data


class TestFilterGraphEndpoint:
    """Test /filter endpoint."""

    @pytest.mark.asyncio
    async def test_filter_graph_by_entity_types(self, client, initialized_api):
        """Test filtering graph by entity types."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/filter",
            json={
                "project_id": "proj1",
                "entity_types": ["person"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj1"
        assert "nodes" in data
        assert "edges" in data

    @pytest.mark.asyncio
    async def test_filter_graph_by_degree(self, client, initialized_api):
        """Test filtering graph by minimum degree."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/filter",
            json={
                "project_id": "proj1",
                "min_degree": 2,
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_graph_by_edge_weight(self, client, initialized_api):
        """Test filtering graph by edge weight."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/filter",
            json={
                "project_id": "proj1",
                "min_edge_weight": 0.5,
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_graph_multiple_criteria(self, client, initialized_api):
        """Test filtering graph with multiple criteria."""
        client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        response = client.post(
            "/api/graph/filter",
            json={
                "project_id": "proj1",
                "entity_types": ["person"],
                "min_degree": 1,
                "min_edge_weight": 0.3,
                "relationship_types": ["works_for", "affiliated_with"],
            },
        )

        assert response.status_code == 200


class TestServiceUnavailable:
    """Test service unavailable scenarios."""

    def test_build_service_unavailable(self, client):
        """Test build endpoint when service unavailable."""
        init_api(None, None, None, None, None)

        response = client.post(
            "/api/graph/build",
            json={"project_id": "proj1"},
        )

        assert response.status_code == 503

    def test_export_service_unavailable(self, client):
        """Test export endpoint when service unavailable."""
        init_api(None, None, None, None, None)

        response = client.post(
            "/api/graph/export",
            json={"project_id": "proj1", "format": "json"},
        )

        assert response.status_code == 503

    def test_algorithms_service_unavailable(self, client):
        """Test centrality endpoint when service unavailable."""
        init_api(None, None, None, None, None)

        response = client.get(
            "/api/graph/centrality/proj1",
            params={"metric": "degree"},
        )

        assert response.status_code == 503
