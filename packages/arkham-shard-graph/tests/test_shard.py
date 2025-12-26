"""Tests for the Graph shard."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from arkham_shard_graph.shard import GraphShard
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge


class TestGraphShardMetadata:
    """Test shard metadata."""

    def test_shard_name(self):
        """Test shard has correct name."""
        shard = GraphShard()
        assert shard.name == "graph"

    def test_shard_version(self):
        """Test shard has version."""
        shard = GraphShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard has description."""
        shard = GraphShard()
        assert "graph" in shard.description.lower()
        assert len(shard.description) > 0


class TestGraphShardInitialization:
    """Test shard initialization."""

    def test_shard_creation(self):
        """Test creating shard instance."""
        shard = GraphShard()

        assert shard.name == "graph"
        assert shard.builder is None
        assert shard.algorithms is None
        assert shard.exporter is None
        assert shard.storage is None

    @pytest_asyncio.fixture
    async def mock_frame(self):
        """Create mock frame."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)
        return frame

    @pytest_asyncio.fixture
    async def mock_frame_with_services(self):
        """Create mock frame with all services."""
        frame = MagicMock()

        # Mock services
        events_service = AsyncMock()
        events_service.subscribe = AsyncMock()
        events_service.unsubscribe = AsyncMock()
        events_service.publish = AsyncMock()

        entities_service = MagicMock()
        documents_service = MagicMock()
        db_service = MagicMock()

        def get_service(name):
            services = {
                "events": events_service,
                "entities": entities_service,
                "documents": documents_service,
                "database": db_service,
                "db": db_service,
            }
            return services.get(name)

        frame.get_service = MagicMock(side_effect=get_service)
        return frame

    @pytest.mark.asyncio
    async def test_initialize_minimal(self, mock_frame):
        """Test initializing shard with minimal services."""
        shard = GraphShard()

        await shard.initialize(mock_frame)

        # Components should be created
        assert shard.builder is not None
        assert shard.algorithms is not None
        assert shard.exporter is not None
        assert shard.storage is not None

    @pytest.mark.asyncio
    async def test_initialize_with_all_services(self, mock_frame_with_services):
        """Test initializing shard with all services."""
        shard = GraphShard()

        await shard.initialize(mock_frame_with_services)

        # All components created
        assert shard.builder is not None
        assert shard.algorithms is not None
        assert shard.exporter is not None
        assert shard.storage is not None

        # Event subscriptions registered
        events_service = mock_frame_with_services.get_service("events")
        assert events_service.subscribe.called
        assert events_service.subscribe.call_count == 3

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_frame_with_services):
        """Test shard shutdown."""
        shard = GraphShard()
        await shard.initialize(mock_frame_with_services)

        # Add some cache data
        shard.storage._cache["proj1"] = Graph(project_id="proj1")

        await shard.shutdown()

        # Components cleared
        assert shard.builder is None
        assert shard.algorithms is None
        assert shard.exporter is None
        assert shard.storage is None

        # Events unsubscribed
        events_service = mock_frame_with_services.get_service("events")
        assert events_service.unsubscribe.called

    def test_get_routes(self):
        """Test getting API routes."""
        shard = GraphShard()
        router = shard.get_routes()

        assert router is not None
        assert hasattr(router, "routes")


class TestGraphShardEventHandlers:
    """Test shard event handlers."""

    @pytest_asyncio.fixture
    async def initialized_shard(self):
        """Create initialized shard."""
        shard = GraphShard()
        frame = MagicMock()

        events_service = AsyncMock()
        events_service.subscribe = AsyncMock()
        events_service.unsubscribe = AsyncMock()

        def get_service(name):
            if name == "events":
                return events_service
            return None

        frame.get_service = MagicMock(side_effect=get_service)

        await shard.initialize(frame)
        return shard

    @pytest.mark.asyncio
    async def test_on_entity_created(self, initialized_shard):
        """Test entity created event handler."""
        # Add graph to cache
        initialized_shard.storage._cache["proj1"] = Graph(project_id="proj1")

        event_data = {
            "entity_id": "ent1",
            "project_id": "proj1",
        }

        await initialized_shard._on_entity_created(event_data)

        # Cache should be invalidated
        assert "proj1" not in initialized_shard.storage._cache

    @pytest.mark.asyncio
    async def test_on_entity_created_missing_data(self, initialized_shard):
        """Test entity created event with missing data."""
        event_data = {"entity_id": "ent1"}

        # Should not raise error
        await initialized_shard._on_entity_created(event_data)

    @pytest.mark.asyncio
    async def test_on_entities_merged(self, initialized_shard):
        """Test entities merged event handler."""
        # Add graph to cache
        initialized_shard.storage._cache["proj1"] = Graph(project_id="proj1")

        event_data = {
            "source_entity_id": "ent1",
            "target_entity_id": "ent2",
            "project_id": "proj1",
        }

        await initialized_shard._on_entities_merged(event_data)

        # Cache should be invalidated
        assert "proj1" not in initialized_shard.storage._cache

    @pytest.mark.asyncio
    async def test_on_document_deleted(self, initialized_shard):
        """Test document deleted event handler."""
        # Add graph to cache
        initialized_shard.storage._cache["proj1"] = Graph(project_id="proj1")

        event_data = {
            "document_id": "doc1",
            "project_id": "proj1",
        }

        await initialized_shard._on_document_deleted(event_data)

        # Cache should be invalidated
        assert "proj1" not in initialized_shard.storage._cache


class TestGraphShardPublicAPI:
    """Test shard public API methods."""

    @pytest_asyncio.fixture
    async def initialized_shard(self):
        """Create initialized shard with mocked services."""
        shard = GraphShard()
        frame = MagicMock()

        entities_service = MagicMock()
        documents_service = MagicMock()

        def get_service(name):
            if name == "entities":
                return entities_service
            elif name == "documents":
                return documents_service
            return None

        frame.get_service = MagicMock(side_effect=get_service)

        await shard.initialize(frame)
        return shard

    @pytest.mark.asyncio
    async def test_build_graph(self, initialized_shard):
        """Test building graph via public API."""
        graph = await initialized_shard.build_graph(
            project_id="proj1",
            min_co_occurrence=2,
        )

        assert graph is not None
        assert graph.project_id == "proj1"
        assert isinstance(graph.nodes, list)
        assert isinstance(graph.edges, list)

        # Graph should be cached
        assert "proj1" in initialized_shard.storage._cache

    @pytest.mark.asyncio
    async def test_build_graph_with_filters(self, initialized_shard):
        """Test building graph with filters."""
        graph = await initialized_shard.build_graph(
            project_id="proj1",
            document_ids=["doc1", "doc2"],
            entity_types=["person"],
            min_co_occurrence=3,
        )

        assert graph.project_id == "proj1"

    @pytest.mark.asyncio
    async def test_find_path(self, initialized_shard):
        """Test finding path between entities."""
        # Build a graph first
        graph = await initialized_shard.build_graph("proj1")

        # Try to find path (may not exist in mock data)
        if len(graph.nodes) >= 2:
            source = graph.nodes[0].id
            target = graph.nodes[1].id

            path = await initialized_shard.find_path(
                project_id="proj1",
                source=source,
                target=target,
            )

            # Path may or may not exist depending on mock data
            if path:
                assert path.source_entity_id == source
                assert path.target_entity_id == target

    @pytest.mark.asyncio
    async def test_find_path_not_initialized(self):
        """Test find_path raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.find_path("proj1", "e1", "e2")

    @pytest.mark.asyncio
    async def test_calculate_centrality(self, initialized_shard):
        """Test calculating centrality."""
        # Build graph first
        await initialized_shard.build_graph("proj1")

        # Calculate PageRank
        results = await initialized_shard.calculate_centrality(
            project_id="proj1",
            metric="pagerank",
            limit=10,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_calculate_centrality_degree(self, initialized_shard):
        """Test calculating degree centrality."""
        await initialized_shard.build_graph("proj1")

        results = await initialized_shard.calculate_centrality(
            project_id="proj1",
            metric="degree",
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_calculate_centrality_betweenness(self, initialized_shard):
        """Test calculating betweenness centrality."""
        await initialized_shard.build_graph("proj1")

        results = await initialized_shard.calculate_centrality(
            project_id="proj1",
            metric="betweenness",
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_calculate_centrality_invalid_metric(self, initialized_shard):
        """Test calculating centrality with invalid metric."""
        await initialized_shard.build_graph("proj1")

        with pytest.raises(ValueError, match="Unknown metric"):
            await initialized_shard.calculate_centrality(
                project_id="proj1",
                metric="invalid",
            )

    @pytest.mark.asyncio
    async def test_detect_communities(self, initialized_shard):
        """Test detecting communities."""
        await initialized_shard.build_graph("proj1")

        communities, modularity = await initialized_shard.detect_communities(
            project_id="proj1",
            min_size=2,
        )

        assert isinstance(communities, list)
        assert isinstance(modularity, float)

    @pytest.mark.asyncio
    async def test_get_neighbors(self, initialized_shard):
        """Test getting entity neighbors."""
        graph = await initialized_shard.build_graph("proj1")

        if len(graph.nodes) > 0:
            entity_id = graph.nodes[0].id

            result = await initialized_shard.get_neighbors(
                entity_id=entity_id,
                project_id="proj1",
                depth=1,
            )

            assert "entity_id" in result
            assert "neighbors" in result

    @pytest.mark.asyncio
    async def test_export_graph_json(self, initialized_shard):
        """Test exporting graph as JSON."""
        await initialized_shard.build_graph("proj1")

        data = await initialized_shard.export_graph(
            project_id="proj1",
            format="json",
        )

        assert isinstance(data, str)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_export_graph_graphml(self, initialized_shard):
        """Test exporting graph as GraphML."""
        await initialized_shard.build_graph("proj1")

        data = await initialized_shard.export_graph(
            project_id="proj1",
            format="graphml",
        )

        assert isinstance(data, str)
        assert "graphml" in data

    @pytest.mark.asyncio
    async def test_export_graph_gexf(self, initialized_shard):
        """Test exporting graph as GEXF."""
        await initialized_shard.build_graph("proj1")

        data = await initialized_shard.export_graph(
            project_id="proj1",
            format="gexf",
        )

        assert isinstance(data, str)
        assert "gexf" in data

    @pytest.mark.asyncio
    async def test_calculate_statistics(self, initialized_shard):
        """Test calculating graph statistics."""
        await initialized_shard.build_graph("proj1")

        stats = await initialized_shard.calculate_statistics("proj1")

        assert stats.project_id == "proj1"
        assert stats.node_count >= 0
        assert stats.edge_count >= 0
        assert 0.0 <= stats.density <= 1.0

    def test_get_statistics_sync_not_implemented(self, initialized_shard):
        """Test sync get_statistics raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            initialized_shard.get_statistics("proj1")


class TestGraphShardEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_build_graph_not_initialized(self):
        """Test build_graph raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.build_graph("proj1")

    @pytest.mark.asyncio
    async def test_calculate_centrality_not_initialized(self):
        """Test calculate_centrality raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.calculate_centrality("proj1")

    @pytest.mark.asyncio
    async def test_detect_communities_not_initialized(self):
        """Test detect_communities raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.detect_communities("proj1")

    @pytest.mark.asyncio
    async def test_get_neighbors_not_initialized(self):
        """Test get_neighbors raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_neighbors("e1", "proj1")

    @pytest.mark.asyncio
    async def test_export_graph_not_initialized(self):
        """Test export_graph raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.export_graph("proj1")

    @pytest.mark.asyncio
    async def test_calculate_statistics_not_initialized(self):
        """Test calculate_statistics raises error if not initialized."""
        shard = GraphShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.calculate_statistics("proj1")
