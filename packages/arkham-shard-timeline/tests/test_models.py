"""
Timeline Shard - Model Tests

Tests for the data models used by the Timeline shard.
"""

import pytest
from datetime import datetime
from dataclasses import asdict

from arkham_shard_timeline.models import (
    EventType,
    DatePrecision,
    ConflictType,
    ConflictSeverity,
    MergeStrategy,
    TimelineEvent,
    DateRange,
    ExtractionContext,
    NormalizedDate,
    TemporalConflict,
    TimelineStats,
    MergeResult,
    ExtractionResult,
    TimelineQuery,
    EntityTimeline,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_all_values_present(self):
        """Test all expected event types exist."""
        assert EventType.OCCURRENCE.value == "occurrence"
        assert EventType.REFERENCE.value == "reference"
        assert EventType.DEADLINE.value == "deadline"
        assert EventType.PERIOD.value == "period"

    def test_enum_count(self):
        """Test correct number of event types."""
        assert len(EventType) == 4


class TestDatePrecision:
    """Tests for DatePrecision enum."""

    def test_all_values_present(self):
        """Test all precision levels exist."""
        assert DatePrecision.EXACT.value == "exact"
        assert DatePrecision.DAY.value == "day"
        assert DatePrecision.WEEK.value == "week"
        assert DatePrecision.MONTH.value == "month"
        assert DatePrecision.QUARTER.value == "quarter"
        assert DatePrecision.YEAR.value == "year"
        assert DatePrecision.DECADE.value == "decade"
        assert DatePrecision.CENTURY.value == "century"
        assert DatePrecision.APPROXIMATE.value == "approximate"

    def test_enum_count(self):
        """Test correct number of precision levels."""
        assert len(DatePrecision) == 9


class TestConflictType:
    """Tests for ConflictType enum."""

    def test_all_values_present(self):
        """Test all conflict types exist."""
        assert ConflictType.CONTRADICTION.value == "contradiction"
        assert ConflictType.INCONSISTENCY.value == "inconsistency"
        assert ConflictType.GAP.value == "gap"
        assert ConflictType.OVERLAP.value == "overlap"

    def test_enum_count(self):
        """Test correct number of conflict types."""
        assert len(ConflictType) == 4


class TestConflictSeverity:
    """Tests for ConflictSeverity enum."""

    def test_all_values_present(self):
        """Test all severity levels exist."""
        assert ConflictSeverity.LOW.value == "low"
        assert ConflictSeverity.MEDIUM.value == "medium"
        assert ConflictSeverity.HIGH.value == "high"
        assert ConflictSeverity.CRITICAL.value == "critical"

    def test_enum_count(self):
        """Test correct number of severity levels."""
        assert len(ConflictSeverity) == 4


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_all_values_present(self):
        """Test all merge strategies exist."""
        assert MergeStrategy.CHRONOLOGICAL.value == "chronological"
        assert MergeStrategy.DEDUPLICATED.value == "deduplicated"
        assert MergeStrategy.CONSOLIDATED.value == "consolidated"
        assert MergeStrategy.SOURCE_PRIORITY.value == "source_priority"

    def test_enum_count(self):
        """Test correct number of merge strategies."""
        assert len(MergeStrategy) == 4


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    @pytest.fixture
    def sample_event(self):
        """Create sample timeline event."""
        return TimelineEvent(
            id="event-123",
            document_id="doc-456",
            text="Meeting on January 15, 2024",
            date_start=datetime(2024, 1, 15),
        )

    def test_basic_creation(self, sample_event):
        """Test basic event creation."""
        assert sample_event.id == "event-123"
        assert sample_event.document_id == "doc-456"
        assert sample_event.text == "Meeting on January 15, 2024"
        assert sample_event.date_start == datetime(2024, 1, 15)

    def test_default_values(self, sample_event):
        """Test default values are set correctly."""
        assert sample_event.date_end is None
        assert sample_event.precision == DatePrecision.DAY
        assert sample_event.confidence == 1.0
        assert sample_event.entities == []
        assert sample_event.event_type == EventType.OCCURRENCE
        assert sample_event.span is None
        assert sample_event.metadata == {}

    def test_full_creation(self):
        """Test event creation with all fields."""
        event = TimelineEvent(
            id="event-789",
            document_id="doc-101",
            text="Project deadline",
            date_start=datetime(2024, 3, 1),
            date_end=datetime(2024, 3, 31),
            precision=DatePrecision.MONTH,
            confidence=0.85,
            entities=["entity-1", "entity-2"],
            event_type=EventType.DEADLINE,
            span=(100, 150),
            metadata={"source": "calendar"},
        )

        assert event.date_end == datetime(2024, 3, 31)
        assert event.precision == DatePrecision.MONTH
        assert event.confidence == 0.85
        assert len(event.entities) == 2
        assert event.event_type == EventType.DEADLINE
        assert event.span == (100, 150)
        assert event.metadata["source"] == "calendar"

    def test_as_dict(self, sample_event):
        """Test conversion to dict."""
        data = asdict(sample_event)

        assert data["id"] == "event-123"
        assert data["document_id"] == "doc-456"
        assert "date_start" in data


class TestDateRange:
    """Tests for DateRange dataclass."""

    def test_empty_range(self):
        """Test empty date range."""
        date_range = DateRange()
        assert date_range.start is None
        assert date_range.end is None

    def test_start_only(self):
        """Test range with only start date."""
        date_range = DateRange(start=datetime(2024, 1, 1))
        assert date_range.start == datetime(2024, 1, 1)
        assert date_range.end is None

    def test_end_only(self):
        """Test range with only end date."""
        date_range = DateRange(end=datetime(2024, 12, 31))
        assert date_range.start is None
        assert date_range.end == datetime(2024, 12, 31)

    def test_full_range(self):
        """Test complete date range."""
        date_range = DateRange(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 12, 31),
        )
        assert date_range.start == datetime(2024, 1, 1)
        assert date_range.end == datetime(2024, 12, 31)


class TestExtractionContext:
    """Tests for ExtractionContext dataclass."""

    def test_default_values(self):
        """Test default extraction context."""
        context = ExtractionContext()
        assert context.reference_date is None
        assert context.timezone == "UTC"
        assert context.prefer_future is False
        assert context.metadata == {}

    def test_with_reference_date(self):
        """Test context with reference date."""
        ref_date = datetime(2024, 6, 15)
        context = ExtractionContext(reference_date=ref_date)
        assert context.reference_date == ref_date

    def test_with_timezone(self):
        """Test context with timezone."""
        context = ExtractionContext(timezone="America/New_York")
        assert context.timezone == "America/New_York"

    def test_prefer_future(self):
        """Test context with prefer_future flag."""
        context = ExtractionContext(prefer_future=True)
        assert context.prefer_future is True

    def test_with_metadata(self):
        """Test context with metadata."""
        context = ExtractionContext(metadata={"source": "parser"})
        assert context.metadata["source"] == "parser"


class TestNormalizedDate:
    """Tests for NormalizedDate dataclass."""

    def test_basic_creation(self):
        """Test basic normalized date."""
        normalized = NormalizedDate(
            original="Jan 15, 2024",
            normalized=datetime(2024, 1, 15),
            precision=DatePrecision.DAY,
            confidence=0.95,
        )
        assert normalized.original == "Jan 15, 2024"
        assert normalized.normalized == datetime(2024, 1, 15)
        assert normalized.precision == DatePrecision.DAY
        assert normalized.confidence == 0.95

    def test_default_values(self):
        """Test default values."""
        normalized = NormalizedDate(
            original="2024",
            normalized=datetime(2024, 6, 30),
            precision=DatePrecision.YEAR,
            confidence=0.7,
        )
        assert normalized.is_range is False
        assert normalized.range_end is None

    def test_range_date(self):
        """Test normalized date that is a range."""
        normalized = NormalizedDate(
            original="Q1 2024",
            normalized=datetime(2024, 1, 1),
            precision=DatePrecision.QUARTER,
            confidence=0.9,
            is_range=True,
            range_end=datetime(2024, 3, 31),
        )
        assert normalized.is_range is True
        assert normalized.range_end == datetime(2024, 3, 31)


class TestTemporalConflict:
    """Tests for TemporalConflict dataclass."""

    def test_basic_creation(self):
        """Test basic conflict creation."""
        conflict = TemporalConflict(
            id="conflict-123",
            type=ConflictType.CONTRADICTION,
            severity=ConflictSeverity.HIGH,
            events=["event-1", "event-2"],
            description="Conflicting dates detected",
            documents=["doc-1", "doc-2"],
        )
        assert conflict.id == "conflict-123"
        assert conflict.type == ConflictType.CONTRADICTION
        assert conflict.severity == ConflictSeverity.HIGH
        assert len(conflict.events) == 2
        assert len(conflict.documents) == 2

    def test_default_values(self):
        """Test default values."""
        conflict = TemporalConflict(
            id="c-1",
            type=ConflictType.GAP,
            severity=ConflictSeverity.LOW,
            events=["e-1"],
            description="Gap detected",
            documents=["d-1"],
        )
        assert conflict.suggested_resolution is None
        assert conflict.metadata == {}

    def test_with_resolution(self):
        """Test conflict with suggested resolution."""
        conflict = TemporalConflict(
            id="c-2",
            type=ConflictType.INCONSISTENCY,
            severity=ConflictSeverity.MEDIUM,
            events=["e-1", "e-2"],
            description="Inconsistent sequence",
            documents=["d-1"],
            suggested_resolution="Review document context",
        )
        assert conflict.suggested_resolution == "Review document context"


class TestTimelineStats:
    """Tests for TimelineStats dataclass."""

    def test_basic_creation(self):
        """Test basic stats creation."""
        stats = TimelineStats(
            total_events=100,
            total_documents=10,
            date_range=DateRange(
                start=datetime(2020, 1, 1),
                end=datetime(2024, 12, 31),
            ),
        )
        assert stats.total_events == 100
        assert stats.total_documents == 10
        assert stats.date_range.start == datetime(2020, 1, 1)

    def test_default_values(self):
        """Test default values."""
        stats = TimelineStats(
            total_events=50,
            total_documents=5,
            date_range=DateRange(),
        )
        assert stats.by_precision == {}
        assert stats.by_type == {}
        assert stats.avg_confidence == 0.0
        assert stats.conflicts_detected == 0
        assert stats.metadata == {}

    def test_with_breakdowns(self):
        """Test stats with breakdowns."""
        stats = TimelineStats(
            total_events=100,
            total_documents=10,
            date_range=DateRange(),
            by_precision={"day": 60, "month": 30, "year": 10},
            by_type={"occurrence": 70, "reference": 30},
            avg_confidence=0.85,
            conflicts_detected=5,
        )
        assert stats.by_precision["day"] == 60
        assert stats.by_type["occurrence"] == 70
        assert stats.avg_confidence == 0.85
        assert stats.conflicts_detected == 5


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_basic_creation(self):
        """Test basic merge result."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="d-1",
                text="Event 1",
                date_start=datetime(2024, 1, 15),
            )
        ]
        result = MergeResult(
            events=events,
            count=1,
            sources={"d-1": 1},
            date_range=DateRange(start=datetime(2024, 1, 15)),
        )
        assert len(result.events) == 1
        assert result.count == 1
        assert result.sources["d-1"] == 1

    def test_default_values(self):
        """Test default values."""
        result = MergeResult(
            events=[],
            count=0,
            sources={},
            date_range=DateRange(),
        )
        assert result.duplicates_removed == 0
        assert result.conflicts_found == 0
        assert result.metadata == {}

    def test_with_all_fields(self):
        """Test with all fields populated."""
        result = MergeResult(
            events=[],
            count=100,
            sources={"d-1": 50, "d-2": 50},
            date_range=DateRange(
                start=datetime(2020, 1, 1),
                end=datetime(2024, 12, 31),
            ),
            duplicates_removed=15,
            conflicts_found=3,
            metadata={"strategy": "deduplicated"},
        )
        assert result.duplicates_removed == 15
        assert result.conflicts_found == 3
        assert result.metadata["strategy"] == "deduplicated"


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_basic_creation(self):
        """Test basic extraction result."""
        result = ExtractionResult(
            events=[],
            count=0,
        )
        assert result.events == []
        assert result.count == 0

    def test_default_values(self):
        """Test default values."""
        result = ExtractionResult(events=[], count=0)
        assert result.duration_ms == 0.0
        assert result.errors == []
        assert result.metadata == {}

    def test_with_events_and_errors(self):
        """Test with events and errors."""
        event = TimelineEvent(
            id="e-1",
            document_id="d-1",
            text="Test",
            date_start=datetime(2024, 1, 1),
        )
        result = ExtractionResult(
            events=[event],
            count=1,
            duration_ms=123.45,
            errors=["Failed to parse one date"],
        )
        assert len(result.events) == 1
        assert result.duration_ms == 123.45
        assert len(result.errors) == 1


class TestTimelineQuery:
    """Tests for TimelineQuery dataclass."""

    def test_default_values(self):
        """Test default query values."""
        query = TimelineQuery()
        assert query.document_ids is None
        assert query.entity_ids is None
        assert query.event_types is None
        assert query.date_range is None
        assert query.min_confidence == 0.0
        assert query.limit == 100
        assert query.offset == 0

    def test_with_document_ids(self):
        """Test query with document IDs."""
        query = TimelineQuery(document_ids=["d-1", "d-2", "d-3"])
        assert len(query.document_ids) == 3

    def test_with_entity_ids(self):
        """Test query with entity IDs."""
        query = TimelineQuery(entity_ids=["entity-1", "entity-2"])
        assert len(query.entity_ids) == 2

    def test_with_event_types(self):
        """Test query with event types."""
        query = TimelineQuery(
            event_types=[EventType.OCCURRENCE, EventType.DEADLINE]
        )
        assert len(query.event_types) == 2

    def test_with_date_range(self):
        """Test query with date range."""
        query = TimelineQuery(
            date_range=DateRange(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
            )
        )
        assert query.date_range.start == datetime(2024, 1, 1)
        assert query.date_range.end == datetime(2024, 12, 31)

    def test_with_pagination(self):
        """Test query with pagination."""
        query = TimelineQuery(
            min_confidence=0.8,
            limit=50,
            offset=100,
        )
        assert query.min_confidence == 0.8
        assert query.limit == 50
        assert query.offset == 100


class TestEntityTimeline:
    """Tests for EntityTimeline dataclass."""

    def test_basic_creation(self):
        """Test basic entity timeline."""
        timeline = EntityTimeline(
            entity_id="entity-123",
            events=[],
            count=0,
            date_range=DateRange(),
        )
        assert timeline.entity_id == "entity-123"
        assert timeline.events == []
        assert timeline.count == 0

    def test_default_values(self):
        """Test default values."""
        timeline = EntityTimeline(
            entity_id="e-1",
            events=[],
            count=0,
            date_range=DateRange(),
        )
        assert timeline.related_entities == []
        assert timeline.metadata == {}

    def test_with_events(self):
        """Test timeline with events."""
        events = [
            TimelineEvent(
                id="event-1",
                document_id="doc-1",
                text="Event 1",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="event-2",
                document_id="doc-2",
                text="Event 2",
                date_start=datetime(2024, 6, 15),
            ),
        ]
        timeline = EntityTimeline(
            entity_id="entity-123",
            events=events,
            count=2,
            date_range=DateRange(
                start=datetime(2024, 1, 15),
                end=datetime(2024, 6, 15),
            ),
            related_entities=["entity-456", "entity-789"],
        )
        assert len(timeline.events) == 2
        assert timeline.count == 2
        assert len(timeline.related_entities) == 2
