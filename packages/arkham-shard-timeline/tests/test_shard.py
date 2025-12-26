"""
Timeline Shard - Shard Tests

Tests for the TimelineShard class.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from arkham_shard_timeline.shard import TimelineShard
from arkham_shard_timeline.models import (
    MergeStrategy,
    DateRange,
    ConflictType,
    EntityTimeline,
    ExtractionContext,
)


class TestShardMetadata:
    """Tests for shard metadata."""

    def test_shard_name(self):
        """Test shard name."""
        shard = TimelineShard()
        assert shard.name == "timeline"

    def test_shard_version(self):
        """Test shard version."""
        shard = TimelineShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = TimelineShard()
        assert "timeline" in shard.description.lower() or "temporal" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)
        return frame

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        mock = MagicMock()
        mock.subscribe = MagicMock()
        mock.unsubscribe = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_initialize_creates_extractor(self, mock_frame):
        """Test initialization creates date extractor."""
        shard = TimelineShard()
        await shard.initialize(mock_frame)

        assert shard.extractor is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_merger(self, mock_frame):
        """Test initialization creates timeline merger."""
        shard = TimelineShard()
        await shard.initialize(mock_frame)

        assert shard.merger is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_conflict_detector(self, mock_frame):
        """Test initialization creates conflict detector."""
        shard = TimelineShard()
        await shard.initialize(mock_frame)

        assert shard.conflict_detector is not None

    @pytest.mark.asyncio
    async def test_initialize_gets_services(self, mock_frame, mock_event_bus):
        """Test initialization gets Frame services."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
            "database": MagicMock(),
            "documents": MagicMock(),
        }.get(name)

        shard = TimelineShard()
        await shard.initialize(mock_frame)

        # Should have requested services
        mock_frame.get_service.assert_any_call("database")
        mock_frame.get_service.assert_any_call("events")

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame, mock_event_bus):
        """Test initialization subscribes to events."""
        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = TimelineShard()
        await shard.initialize(mock_frame)

        # Should subscribe to events
        assert mock_event_bus.subscribe.call_count == 3

    @pytest.mark.asyncio
    async def test_initialize_without_services(self, mock_frame):
        """Test initialization without optional services."""
        mock_frame.get_service.return_value = None

        shard = TimelineShard()
        await shard.initialize(mock_frame)

        # Should complete without error
        assert shard.extractor is not None


class TestShardShutdown:
    """Tests for shard shutdown."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)
        return frame

    @pytest.mark.asyncio
    async def test_shutdown_clears_components(self, mock_frame):
        """Test shutdown clears all components."""
        shard = TimelineShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.extractor is None
        assert shard.merger is None
        assert shard.conflict_detector is None

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_events(self, mock_frame):
        """Test shutdown unsubscribes from events."""
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = MagicMock()
        mock_event_bus.unsubscribe = MagicMock()

        mock_frame.get_service.side_effect = lambda name: {
            "events": mock_event_bus,
        }.get(name)

        shard = TimelineShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert mock_event_bus.unsubscribe.call_count == 3


class TestGetRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test get_routes returns the FastAPI router."""
        shard = TimelineShard()
        routes = shard.get_routes()

        assert routes is not None


class TestEventHandlers:
    """Tests for shard event handlers."""

    @pytest.fixture
    def initialized_shard(self):
        """Create initialized shard with mocks."""
        shard = TimelineShard()
        shard.frame = MagicMock()
        shard.extractor = MagicMock()
        shard.merger = MagicMock()
        shard.conflict_detector = MagicMock()
        shard.database_service = None
        shard.documents_service = None
        return shard

    @pytest.mark.asyncio
    async def test_on_document_indexed(self, initialized_shard):
        """Test handling document indexed event."""
        event = {"doc_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_document_indexed(event)

    @pytest.mark.asyncio
    async def test_on_document_deleted(self, initialized_shard):
        """Test handling document deleted event."""
        event = {"doc_id": "doc-123"}

        # Should not raise
        await initialized_shard._on_document_deleted(event)

    @pytest.mark.asyncio
    async def test_on_entity_created(self, initialized_shard):
        """Test handling entity created event."""
        event = {"entity_id": "entity-123"}

        # Should not raise
        await initialized_shard._on_entity_created(event)


class TestPublicExtractTimelineAPI:
    """Tests for shard public extract_timeline method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create initialized shard with mocks."""
        shard = TimelineShard()
        shard.frame = MagicMock()
        shard.extractor = MagicMock()
        shard.extractor.extract_events = MagicMock(return_value=[])
        shard.merger = MagicMock()
        shard.conflict_detector = MagicMock()
        shard.database_service = None
        shard.documents_service = MagicMock()
        shard.documents_service.get_document = AsyncMock(return_value={"text": "Test text"})
        return shard

    @pytest.mark.asyncio
    async def test_extract_timeline_basic(self, initialized_shard):
        """Test basic extract_timeline call."""
        events = await initialized_shard.extract_timeline("doc-123")

        assert events == []
        initialized_shard.extractor.extract_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_timeline_with_context(self, initialized_shard):
        """Test extract_timeline with custom context."""
        context = ExtractionContext(reference_date=datetime(2024, 6, 15))
        events = await initialized_shard.extract_timeline("doc-123", context)

        assert events == []

    @pytest.mark.asyncio
    async def test_extract_timeline_no_documents_service(self, initialized_shard):
        """Test extract_timeline without documents service."""
        initialized_shard.documents_service = None

        events = await initialized_shard.extract_timeline("doc-123")

        assert events == []


class TestPublicMergeTimelinesAPI:
    """Tests for shard public merge_timelines method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create initialized shard with mocks."""
        shard = TimelineShard()
        shard.frame = MagicMock()
        shard.extractor = MagicMock()
        shard.merger = MagicMock()
        shard.merger.merge = MagicMock()
        shard.conflict_detector = MagicMock()
        shard.database_service = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_merge_timelines_basic(self, initialized_shard):
        """Test basic merge_timelines call."""
        result = await initialized_shard.merge_timelines(["doc-1", "doc-2"])

        initialized_shard.merger.merge.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_timelines_with_strategy(self, initialized_shard):
        """Test merge_timelines with custom strategy."""
        result = await initialized_shard.merge_timelines(
            ["doc-1", "doc-2"],
            strategy=MergeStrategy.DEDUPLICATED,
        )

        initialized_shard.merger.merge.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_timelines_no_database(self, initialized_shard):
        """Test merge_timelines without database service."""
        initialized_shard.database_service = None

        result = await initialized_shard.merge_timelines(["doc-1"])

        assert result is None


class TestPublicDetectConflictsAPI:
    """Tests for shard public detect_conflicts method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create initialized shard with mocks."""
        shard = TimelineShard()
        shard.frame = MagicMock()
        shard.extractor = MagicMock()
        shard.merger = MagicMock()
        shard.conflict_detector = MagicMock()
        shard.conflict_detector.tolerance_days = 0
        shard.conflict_detector.detect_conflicts = MagicMock(return_value=[])
        shard.database_service = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_detect_conflicts_basic(self, initialized_shard):
        """Test basic detect_conflicts call."""
        conflicts = await initialized_shard.detect_conflicts(["doc-1", "doc-2"])

        assert conflicts == []

    @pytest.mark.asyncio
    async def test_detect_conflicts_with_types(self, initialized_shard):
        """Test detect_conflicts with specific types."""
        conflicts = await initialized_shard.detect_conflicts(
            ["doc-1"],
            conflict_types=[ConflictType.CONTRADICTION],
        )

        assert conflicts == []

    @pytest.mark.asyncio
    async def test_detect_conflicts_with_tolerance(self, initialized_shard):
        """Test detect_conflicts with custom tolerance."""
        conflicts = await initialized_shard.detect_conflicts(
            ["doc-1"],
            tolerance_days=5,
        )

        assert conflicts == []

    @pytest.mark.asyncio
    async def test_detect_conflicts_no_database(self, initialized_shard):
        """Test detect_conflicts without database."""
        initialized_shard.database_service = None

        conflicts = await initialized_shard.detect_conflicts(["doc-1"])

        assert conflicts == []


class TestPublicGetEntityTimelineAPI:
    """Tests for shard public get_entity_timeline method."""

    @pytest.fixture
    def initialized_shard(self):
        """Create initialized shard with mocks."""
        shard = TimelineShard()
        shard.frame = MagicMock()
        shard.extractor = MagicMock()
        shard.merger = MagicMock()
        shard.conflict_detector = MagicMock()
        shard.database_service = MagicMock()
        shard.entities_service = None
        return shard

    @pytest.mark.asyncio
    async def test_get_entity_timeline_basic(self, initialized_shard):
        """Test basic get_entity_timeline call."""
        timeline = await initialized_shard.get_entity_timeline("entity-123")

        assert isinstance(timeline, EntityTimeline)
        assert timeline.entity_id == "entity-123"

    @pytest.mark.asyncio
    async def test_get_entity_timeline_with_date_range(self, initialized_shard):
        """Test get_entity_timeline with date range."""
        date_range = DateRange(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 12, 31),
        )
        timeline = await initialized_shard.get_entity_timeline(
            "entity-123",
            date_range=date_range,
        )

        assert isinstance(timeline, EntityTimeline)

    @pytest.mark.asyncio
    async def test_get_entity_timeline_include_related(self, initialized_shard):
        """Test get_entity_timeline with related entities."""
        timeline = await initialized_shard.get_entity_timeline(
            "entity-123",
            include_related=True,
        )

        assert isinstance(timeline, EntityTimeline)

    @pytest.mark.asyncio
    async def test_get_entity_timeline_no_database(self, initialized_shard):
        """Test get_entity_timeline without database."""
        initialized_shard.database_service = None

        timeline = await initialized_shard.get_entity_timeline("entity-123")

        assert isinstance(timeline, EntityTimeline)
        assert timeline.events == []
        assert timeline.count == 0
