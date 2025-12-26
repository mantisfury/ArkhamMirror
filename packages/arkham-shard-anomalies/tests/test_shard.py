"""
Anomalies Shard - Shard Tests

Tests for the AnomaliesShard class including initialization,
lifecycle, and public API.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_anomalies.shard import AnomaliesShard
from arkham_shard_anomalies.models import DetectionConfig, AnomalyType


class TestShardMetadata:
    """Tests for shard metadata and manifest."""

    def test_shard_name(self):
        """Test shard name."""
        shard = AnomaliesShard()
        assert shard.name == "anomalies"

    def test_shard_version(self):
        """Test shard version."""
        shard = AnomaliesShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = AnomaliesShard()
        assert "anomal" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock()
        return frame

    @pytest.fixture
    def mock_vector_service(self):
        """Create mock vector service."""
        return MagicMock()

    @pytest.fixture
    def mock_db_service(self):
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
    async def test_initialize_creates_detector(self, mock_frame):
        """Test that initialization creates detector."""
        mock_frame.get_service.return_value = None

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert shard.detector is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_store(self, mock_frame):
        """Test that initialization creates store."""
        mock_frame.get_service.return_value = None

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert shard.store is not None

    @pytest.mark.asyncio
    async def test_initialize_gets_vector_service(
        self, mock_frame, mock_vector_service
    ):
        """Test initialization gets vector service."""
        mock_frame.get_service.side_effect = lambda name: {
            "vectors": mock_vector_service,
        }.get(name)

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert shard._vector_service == mock_vector_service

    @pytest.mark.asyncio
    async def test_initialize_gets_db_service(
        self, mock_frame, mock_db_service
    ):
        """Test initialization gets database service."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db_service,
        }.get(name)

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert shard._db_service == mock_db_service

    @pytest.mark.asyncio
    async def test_initialize_tries_db_fallback(
        self, mock_frame, mock_db_service
    ):
        """Test initialization tries 'db' if 'database' returns None."""
        mock_frame.get_service.side_effect = lambda name: {
            "db": mock_db_service,
        }.get(name)

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert shard._db_service == mock_db_service

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(
        self, mock_frame, mock_event_bus
    ):
        """Test that initialization subscribes to events."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        assert mock_event_bus.subscribe.call_count == 2
        event_names = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
        assert "embeddings.created" in event_names
        assert "documents.indexed" in event_names

    @pytest.mark.asyncio
    async def test_initialize_without_services(self, mock_frame):
        """Test initialization when services unavailable."""
        mock_frame.get_service.return_value = None

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)

        # Should complete without errors
        assert shard.detector is not None
        assert shard.store is not None


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

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert mock_event_bus.unsubscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_clears_components(self, mock_frame):
        """Test that shutdown clears all components."""
        mock_frame.get_service.return_value = None

        shard = AnomaliesShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.detector is None
        assert shard.store is None


class TestShardRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the FastAPI router."""
        shard = AnomaliesShard()
        routes = shard.get_routes()
        assert routes is not None


class TestEventHandlers:
    """Tests for shard event handlers."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = AnomaliesShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.store = MagicMock()
        shard._event_bus = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_on_embedding_created(self, initialized_shard):
        """Test handling embedding created event."""
        event = {"doc_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_embedding_created(event)

    @pytest.mark.asyncio
    async def test_on_embedding_created_no_doc_id(self, initialized_shard):
        """Test handling event with no doc_id."""
        event = {}

        # Should not raise
        await initialized_shard._on_embedding_created(event)

    @pytest.mark.asyncio
    async def test_on_document_indexed(self, initialized_shard):
        """Test handling document indexed event."""
        event = {"doc_id": "doc-456"}

        # Should not raise
        await initialized_shard._on_document_indexed(event)


class TestPublicDetectAPI:
    """Tests for shard public detect_anomalies method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock detector."""
        shard = AnomaliesShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.store = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_detect_anomalies_requires_init(self):
        """Test detect_anomalies requires initialization."""
        shard = AnomaliesShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.detect_anomalies()

    @pytest.mark.asyncio
    async def test_detect_anomalies_basic(self, initialized_shard):
        """Test basic detect_anomalies call."""
        result = await initialized_shard.detect_anomalies()
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_with_doc_ids(self, initialized_shard):
        """Test detect_anomalies with specific documents."""
        result = await initialized_shard.detect_anomalies(
            doc_ids=["doc-1", "doc-2", "doc-3"]
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_with_config(self, initialized_shard):
        """Test detect_anomalies with custom config."""
        config = DetectionConfig(z_score_threshold=2.5)
        result = await initialized_shard.detect_anomalies(config=config)
        assert result == []


class TestPublicGetAnomaliesAPI:
    """Tests for shard public get_anomalies_for_document method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock store."""
        shard = AnomaliesShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.store = MagicMock()
        shard.store.get_anomalies_by_doc = AsyncMock(return_value=[])
        return shard

    @pytest.mark.asyncio
    async def test_get_anomalies_requires_init(self):
        """Test get_anomalies_for_document requires initialization."""
        shard = AnomaliesShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_anomalies_for_document("doc-123")

    @pytest.mark.asyncio
    async def test_get_anomalies_basic(self, initialized_shard):
        """Test basic get_anomalies_for_document call."""
        result = await initialized_shard.get_anomalies_for_document("doc-123")
        initialized_shard.store.get_anomalies_by_doc.assert_called_with("doc-123")
        assert result == []


class TestPublicCheckDocumentAPI:
    """Tests for shard public check_document method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock detector and store."""
        shard = AnomaliesShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.detector.detect_statistical_anomalies.return_value = []
        shard.detector.detect_red_flags.return_value = []
        shard.detector.detect_metadata_anomalies.return_value = []
        shard.store = MagicMock()
        shard.store.create_anomaly = AsyncMock()
        shard._event_bus = None
        return shard

    @pytest.mark.asyncio
    async def test_check_document_requires_init(self):
        """Test check_document requires initialization."""
        shard = AnomaliesShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.check_document("doc-123", "text", {})

    @pytest.mark.asyncio
    async def test_check_document_basic(self, initialized_shard):
        """Test basic check_document call."""
        result = await initialized_shard.check_document(
            doc_id="doc-123",
            text="Sample document text",
            metadata={},
        )

        initialized_shard.detector.detect_statistical_anomalies.assert_called_once()
        initialized_shard.detector.detect_red_flags.assert_called_once()
        initialized_shard.detector.detect_metadata_anomalies.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_check_document_stores_anomalies(self, initialized_shard):
        """Test check_document stores detected anomalies."""
        from arkham_shard_anomalies.models import Anomaly

        anomaly = Anomaly(
            id="anom-1",
            doc_id="doc-123",
            anomaly_type=AnomalyType.RED_FLAG,
        )
        initialized_shard.detector.detect_red_flags.return_value = [anomaly]

        await initialized_shard.check_document(
            doc_id="doc-123",
            text="This is confidential",
            metadata={},
        )

        initialized_shard.store.create_anomaly.assert_called_once_with(anomaly)

    @pytest.mark.asyncio
    async def test_check_document_emits_event(self, initialized_shard):
        """Test check_document emits event when anomalies found."""
        from arkham_shard_anomalies.models import Anomaly

        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        initialized_shard._event_bus = mock_event_bus

        anomaly = Anomaly(
            id="anom-1",
            doc_id="doc-123",
            anomaly_type=AnomalyType.RED_FLAG,
        )
        initialized_shard.detector.detect_red_flags.return_value = [anomaly]

        await initialized_shard.check_document(
            doc_id="doc-123",
            text="This is confidential",
            metadata={},
        )

        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "anomalies.detected"
        assert call_args[0][1]["doc_id"] == "doc-123"
        assert call_args[0][1]["count"] == 1


class TestPublicStatisticsAPI:
    """Tests for shard public get_statistics method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create shard with mock store."""
        from arkham_shard_anomalies.models import AnomalyStats

        shard = AnomaliesShard()
        shard._frame = MagicMock()
        shard.detector = MagicMock()
        shard.store = MagicMock()
        shard.store.get_stats = AsyncMock(return_value=AnomalyStats(
            total_anomalies=50,
            by_type={"content": 20, "red_flag": 30},
            by_status={"detected": 40, "confirmed": 10},
            by_severity={"high": 15, "medium": 35},
            detected_last_24h=5,
            confirmed_last_24h=2,
            dismissed_last_24h=1,
            false_positive_rate=0.1,
            avg_confidence=0.85,
        ))
        return shard

    @pytest.mark.asyncio
    async def test_get_statistics_requires_init(self):
        """Test get_statistics requires initialization."""
        shard = AnomaliesShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_statistics()

    @pytest.mark.asyncio
    async def test_get_statistics_basic(self, initialized_shard):
        """Test basic get_statistics call."""
        result = await initialized_shard.get_statistics()

        assert result["total_anomalies"] == 50
        assert result["by_type"]["content"] == 20
        assert result["by_status"]["detected"] == 40
        assert result["by_severity"]["high"] == 15
        assert result["recent_activity"]["detected_last_24h"] == 5
        assert result["quality_metrics"]["false_positive_rate"] == 0.1
