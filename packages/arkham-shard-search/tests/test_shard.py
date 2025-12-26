"""
Search Shard - Shard Tests

Tests for the SearchShard class including initialization,
lifecycle, and public API.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from arkham_shard_search.shard import SearchShard
from arkham_shard_search.models import SearchMode


class TestShardMetadata:
    """Tests for shard metadata and manifest."""

    def test_shard_name(self):
        """Test shard name."""
        shard = SearchShard()
        assert shard.name == "search"

    def test_shard_version(self):
        """Test shard version."""
        shard = SearchShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = SearchShard()
        assert "search" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock()
        return frame

    @pytest.fixture
    def mock_vectors_service(self):
        """Create mock vectors service."""
        return MagicMock()

    @pytest.fixture
    def mock_database_service(self):
        """Create mock database service."""
        return MagicMock()

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        mock = MagicMock()
        mock.subscribe = MagicMock()
        mock.unsubscribe = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_initialize_creates_semantic_engine(
        self, mock_frame, mock_vectors_service
    ):
        """Test that initialization creates semantic engine when vectors available."""
        mock_frame.get_service.side_effect = lambda name: {
            "vectors": mock_vectors_service,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert shard.semantic_engine is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_keyword_engine(
        self, mock_frame, mock_database_service
    ):
        """Test that initialization creates keyword engine when database available."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_database_service,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert shard.keyword_engine is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_hybrid_engine(
        self, mock_frame, mock_vectors_service, mock_database_service
    ):
        """Test that initialization creates hybrid engine when both available."""
        mock_frame.get_service.side_effect = lambda name: {
            "vectors": mock_vectors_service,
            "database": mock_database_service,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert shard.hybrid_engine is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_filter_optimizer(
        self, mock_frame, mock_database_service
    ):
        """Test that initialization creates filter optimizer."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_database_service,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert shard.filter_optimizer is not None

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(
        self, mock_frame, mock_event_bus
    ):
        """Test that initialization subscribes to events."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert mock_event_bus.subscribe.call_count == 2
        event_names = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
        assert "documents.indexed" in event_names
        assert "documents.deleted" in event_names

    @pytest.mark.asyncio
    async def test_initialize_without_services(self, mock_frame):
        """Test initialization when services are unavailable."""
        mock_frame.get_service.return_value = None

        shard = SearchShard()
        await shard.initialize(mock_frame)

        # Should complete without errors
        assert shard.semantic_engine is None
        assert shard.keyword_engine is None
        assert shard.hybrid_engine is None

    @pytest.mark.asyncio
    async def test_initialize_uses_db_fallback(self, mock_frame, mock_database_service):
        """Test initialization tries 'db' if 'database' returns None."""
        mock_frame.get_service.side_effect = lambda name: {
            "db": mock_database_service,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)

        assert shard.keyword_engine is not None


class TestShardShutdown:
    """Tests for shard shutdown."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock()
        return frame

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_events(self, mock_frame):
        """Test that shutdown unsubscribes from events."""
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = MagicMock()
        mock_event_bus.unsubscribe = MagicMock()

        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert mock_event_bus.unsubscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_clears_engines(self, mock_frame):
        """Test that shutdown clears all engines."""
        mock_vectors = MagicMock()
        mock_db = MagicMock()

        mock_frame.get_service.side_effect = lambda name: {
            "vectors": mock_vectors,
            "database": mock_db,
        }.get(name)

        shard = SearchShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.semantic_engine is None
        assert shard.keyword_engine is None
        assert shard.hybrid_engine is None
        assert shard.filter_optimizer is None


class TestShardRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the FastAPI router."""
        shard = SearchShard()
        routes = shard.get_routes()
        assert routes is not None


class TestEventHandlers:
    """Tests for shard event handlers."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.semantic_engine = MagicMock()
        shard.keyword_engine = MagicMock()
        shard.hybrid_engine = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_on_document_indexed(self, initialized_shard):
        """Test handling document indexed event."""
        event = {"doc_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_document_indexed(event)

    @pytest.mark.asyncio
    async def test_on_document_indexed_no_doc_id(self, initialized_shard):
        """Test handling document indexed event with no doc_id."""
        event = {}

        # Should not raise
        await initialized_shard._on_document_indexed(event)

    @pytest.mark.asyncio
    async def test_on_document_deleted(self, initialized_shard):
        """Test handling document deleted event."""
        event = {"doc_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_document_deleted(event)


class TestPublicSearchAPI:
    """Tests for shard public search method."""

    @pytest.fixture
    def mock_semantic_engine(self):
        """Create mock semantic engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_keyword_engine(self):
        """Create mock keyword engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_hybrid_engine(self):
        """Create mock hybrid engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def initialized_shard(self, mock_semantic_engine, mock_keyword_engine, mock_hybrid_engine):
        """Create shard with mock engines."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.semantic_engine = mock_semantic_engine
        shard.keyword_engine = mock_keyword_engine
        shard.hybrid_engine = mock_hybrid_engine
        return shard

    @pytest.mark.asyncio
    async def test_search_hybrid_default(self, initialized_shard, mock_hybrid_engine):
        """Test search uses hybrid mode by default."""
        await initialized_shard.search("test query")
        mock_hybrid_engine.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_semantic_mode(self, initialized_shard, mock_semantic_engine):
        """Test search uses semantic engine when specified."""
        await initialized_shard.search("test query", mode="semantic")
        mock_semantic_engine.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_keyword_mode(self, initialized_shard, mock_keyword_engine):
        """Test search uses keyword engine when specified."""
        await initialized_shard.search("test query", mode="keyword")
        mock_keyword_engine.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_invalid_mode_defaults_hybrid(
        self, initialized_shard, mock_hybrid_engine
    ):
        """Test search with invalid mode defaults to hybrid."""
        await initialized_shard.search("test query", mode="invalid")
        mock_hybrid_engine.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_limit(self, initialized_shard, mock_hybrid_engine):
        """Test search passes limit parameter."""
        await initialized_shard.search("test query", limit=50)

        call_args = mock_hybrid_engine.search.call_args
        query = call_args[0][0]
        assert query.limit == 50

    @pytest.mark.asyncio
    async def test_search_no_engine_returns_empty(self):
        """Test search returns empty when no engine available."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.semantic_engine = None
        shard.keyword_engine = None
        shard.hybrid_engine = None

        results = await shard.search("test query")
        assert results == []


class TestPublicFindSimilarAPI:
    """Tests for shard public find_similar method."""

    @pytest.fixture
    def mock_semantic_engine(self):
        """Create mock semantic engine."""
        mock = MagicMock()
        mock.find_similar = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def initialized_shard(self, mock_semantic_engine):
        """Create shard with mock semantic engine."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.semantic_engine = mock_semantic_engine
        return shard

    @pytest.mark.asyncio
    async def test_find_similar_basic(self, initialized_shard, mock_semantic_engine):
        """Test find_similar calls semantic engine."""
        await initialized_shard.find_similar("doc-123")

        mock_semantic_engine.find_similar.assert_called_once_with(
            doc_id="doc-123",
            limit=10,
            min_similarity=0.5,
        )

    @pytest.mark.asyncio
    async def test_find_similar_with_options(self, initialized_shard, mock_semantic_engine):
        """Test find_similar passes options."""
        await initialized_shard.find_similar("doc-123", limit=20, min_similarity=0.7)

        mock_semantic_engine.find_similar.assert_called_once_with(
            doc_id="doc-123",
            limit=20,
            min_similarity=0.7,
        )

    @pytest.mark.asyncio
    async def test_find_similar_no_engine_returns_empty(self):
        """Test find_similar returns empty when no engine available."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.semantic_engine = None

        results = await shard.find_similar("doc-123")
        assert results == []


class TestSearchQueryConstruction:
    """Tests for SearchQuery construction in public API."""

    @pytest.fixture
    def mock_hybrid_engine(self):
        """Create mock hybrid engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def initialized_shard(self, mock_hybrid_engine):
        """Create shard with mock engines."""
        shard = SearchShard()
        shard.frame = MagicMock()
        shard.hybrid_engine = mock_hybrid_engine
        return shard

    @pytest.mark.asyncio
    async def test_query_has_correct_mode(self, initialized_shard, mock_hybrid_engine):
        """Test query has correct search mode."""
        await initialized_shard.search("test", mode="hybrid")

        call_args = mock_hybrid_engine.search.call_args
        query = call_args[0][0]
        assert query.mode == SearchMode.HYBRID

    @pytest.mark.asyncio
    async def test_query_has_query_text(self, initialized_shard, mock_hybrid_engine):
        """Test query has the query text."""
        await initialized_shard.search("my search query")

        call_args = mock_hybrid_engine.search.call_args
        query = call_args[0][0]
        assert query.query == "my search query"
