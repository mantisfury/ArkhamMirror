"""
Contradictions Shard - Shard Tests

Tests for the ContradictionsShard class including initialization,
lifecycle, and public API.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_contradictions.shard import ContradictionsShard
from arkham_shard_contradictions.models import ContradictionStatus


class TestShardMetadata:
    """Tests for shard metadata and manifest."""

    def test_shard_name(self):
        """Test shard name."""
        shard = ContradictionsShard()
        assert shard.name == "contradictions"

    def test_shard_version(self):
        """Test shard version."""
        shard = ContradictionsShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = ContradictionsShard()
        assert "contradiction" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock()
        return frame

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        mock = MagicMock()
        mock.subscribe = AsyncMock()
        mock.unsubscribe = AsyncMock()
        return mock

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        return MagicMock()

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        return MagicMock()

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_initialize_creates_detector(self, mock_frame):
        """Test that initialization creates detector."""
        mock_frame.get_service.return_value = None

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard.detector is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_chain_detector(self, mock_frame):
        """Test that initialization creates chain detector."""
        mock_frame.get_service.return_value = None

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard.chain_detector is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_storage(self, mock_frame):
        """Test that initialization creates storage."""
        mock_frame.get_service.return_value = None

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard.storage is not None

    @pytest.mark.asyncio
    async def test_initialize_gets_event_bus(self, mock_frame, mock_event_bus):
        """Test initialization gets event bus."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard._event_bus == mock_event_bus

    @pytest.mark.asyncio
    async def test_initialize_gets_llm_service(self, mock_frame, mock_llm_service):
        """Test initialization gets LLM service."""
        mock_frame.get_service.side_effect = lambda name: {
            "llm": mock_llm_service,
        }.get(name)

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard._llm_service == mock_llm_service

    @pytest.mark.asyncio
    async def test_initialize_gets_embedding_service(
        self, mock_frame, mock_embedding_service
    ):
        """Test initialization gets embedding service."""
        mock_frame.get_service.side_effect = lambda name: {
            "embeddings": mock_embedding_service,
        }.get(name)

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        assert shard._embedding_service == mock_embedding_service

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame, mock_event_bus):
        """Test that initialization subscribes to events."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        # Should subscribe to 3 events
        assert mock_event_bus.subscribe.call_count == 3
        event_names = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
        assert "document.ingested" in event_names
        assert "document.updated" in event_names
        assert "llm.analysis.completed" in event_names

    @pytest.mark.asyncio
    async def test_initialize_without_services(self, mock_frame):
        """Test initialization when services unavailable."""
        mock_frame.get_service.return_value = None

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)

        # Should complete without errors
        assert shard.detector is not None
        assert shard.storage is not None


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
        mock_event_bus.subscribe = AsyncMock()
        mock_event_bus.unsubscribe = AsyncMock()

        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        # Should unsubscribe from 3 events
        assert mock_event_bus.unsubscribe.call_count == 3

    @pytest.mark.asyncio
    async def test_shutdown_clears_components(self, mock_frame):
        """Test that shutdown clears all components."""
        mock_frame.get_service.return_value = None

        shard = ContradictionsShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.detector is None
        assert shard.chain_detector is None
        assert shard.storage is None


class TestShardRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the FastAPI router."""
        shard = ContradictionsShard()
        routes = shard.get_routes()
        assert routes is not None


class TestEventHandlers:
    """Tests for shard event handlers."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = ContradictionsShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.chain_detector = MagicMock()
        shard.storage = MagicMock()
        shard._event_bus = MagicMock()
        shard._worker_service = None
        return shard

    @pytest.mark.asyncio
    async def test_on_document_ingested(self, initialized_shard):
        """Test handling document ingested event."""
        event = {"document_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_document_ingested(event)

    @pytest.mark.asyncio
    async def test_on_document_ingested_no_doc_id(self, initialized_shard):
        """Test handling event with no document_id."""
        event = {}

        # Should not raise
        await initialized_shard._on_document_ingested(event)

    @pytest.mark.asyncio
    async def test_on_document_updated(self, initialized_shard):
        """Test handling document updated event."""
        event = {"document_id": "doc-456"}

        # Should not raise
        await initialized_shard._on_document_updated(event)

    @pytest.mark.asyncio
    async def test_on_llm_analysis_completed(self, initialized_shard):
        """Test handling LLM analysis completed event."""
        event = {"job_id": "job-123", "result": {}}

        # Should not raise
        await initialized_shard._on_llm_analysis_completed(event)


class TestPublicAnalyzePairAPI:
    """Tests for shard public analyze_pair method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock detector and storage."""
        shard = ContradictionsShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.detector.extract_claims_simple = MagicMock(return_value=[])
        shard.detector.extract_claims_llm = AsyncMock(return_value=[])
        shard.detector.find_similar_claims = AsyncMock(return_value=[])
        shard.detector.verify_contradiction = AsyncMock(return_value=None)
        shard.storage = MagicMock()
        shard._llm_service = None
        return shard

    @pytest.mark.asyncio
    async def test_analyze_pair_requires_init(self):
        """Test analyze_pair requires initialization."""
        shard = ContradictionsShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.analyze_pair("doc-1", "doc-2")

    @pytest.mark.asyncio
    async def test_analyze_pair_basic(self, initialized_shard):
        """Test basic analyze_pair call."""
        result = await initialized_shard.analyze_pair("doc-1", "doc-2")
        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_pair_with_threshold(self, initialized_shard):
        """Test analyze_pair with custom threshold."""
        result = await initialized_shard.analyze_pair(
            "doc-1", "doc-2", threshold=0.5
        )
        assert result == []


class TestPublicGetDocumentContradictionsAPI:
    """Tests for shard public get_document_contradictions method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock storage."""
        shard = ContradictionsShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.storage = MagicMock()
        shard.storage.get_by_document = MagicMock(return_value=[])
        return shard

    def test_get_document_contradictions_requires_init(self):
        """Test get_document_contradictions requires initialization."""
        shard = ContradictionsShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            shard.get_document_contradictions("doc-123")

    def test_get_document_contradictions_basic(self, initialized_shard):
        """Test basic get_document_contradictions call."""
        result = initialized_shard.get_document_contradictions("doc-123")
        initialized_shard.storage.get_by_document.assert_called_with("doc-123")
        assert result == []


class TestPublicGetStatisticsAPI:
    """Tests for shard public get_statistics method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock storage."""
        shard = ContradictionsShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.storage = MagicMock()
        shard.storage.get_statistics = MagicMock(return_value={
            "total_contradictions": 50,
            "by_status": {"detected": 30, "confirmed": 20},
            "by_severity": {"high": 10, "medium": 40},
            "by_type": {"direct": 25, "temporal": 25},
            "chains_detected": 3,
            "recent_count": 5,
        })
        return shard

    def test_get_statistics_requires_init(self):
        """Test get_statistics requires initialization."""
        shard = ContradictionsShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            shard.get_statistics()

    def test_get_statistics_basic(self, initialized_shard):
        """Test basic get_statistics call."""
        result = initialized_shard.get_statistics()

        assert result["total_contradictions"] == 50
        assert result["by_status"]["confirmed"] == 20
        assert result["chains_detected"] == 3


class TestPublicDetectChainsAPI:
    """Tests for shard public detect_chains method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock chain detector and storage."""
        shard = ContradictionsShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.chain_detector = MagicMock()
        shard.chain_detector.detect_chains = MagicMock(return_value=[])
        shard.storage = MagicMock()
        shard.storage.search = MagicMock(return_value=[])
        shard.storage.create_chain = MagicMock(side_effect=lambda c: c)
        return shard

    @pytest.mark.asyncio
    async def test_detect_chains_requires_init(self):
        """Test detect_chains requires initialization."""
        shard = ContradictionsShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.detect_chains()

    @pytest.mark.asyncio
    async def test_detect_chains_basic(self, initialized_shard):
        """Test basic detect_chains call."""
        result = await initialized_shard.detect_chains()
        assert result == []
