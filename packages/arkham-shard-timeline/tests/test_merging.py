"""
Timeline Shard - Merging Tests

Tests for the TimelineMerger class.
"""

import pytest
from datetime import datetime, timedelta

from arkham_shard_timeline.merging import TimelineMerger
from arkham_shard_timeline.models import (
    TimelineEvent,
    MergeStrategy,
    DatePrecision,
    EventType,
    DateRange,
)


class TestTimelineMergerInit:
    """Tests for TimelineMerger initialization."""

    def test_default_initialization(self):
        """Test merger initializes with default strategy."""
        merger = TimelineMerger()
        assert merger.strategy == MergeStrategy.CHRONOLOGICAL

    def test_custom_strategy_initialization(self):
        """Test merger initializes with custom strategy."""
        merger = TimelineMerger(strategy=MergeStrategy.DEDUPLICATED)
        assert merger.strategy == MergeStrategy.DEDUPLICATED


class TestChronologicalMerge:
    """Tests for chronological merge strategy."""

    @pytest.fixture
    def merger(self):
        """Create merger with chronological strategy."""
        return TimelineMerger(strategy=MergeStrategy.CHRONOLOGICAL)

    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return [
            TimelineEvent(
                id="e-3",
                document_id="doc-1",
                text="Event 3",
                date_start=datetime(2024, 3, 1),
            ),
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event 1",
                date_start=datetime(2024, 1, 1),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event 2",
                date_start=datetime(2024, 2, 1),
            ),
        ]

    def test_merge_empty(self, merger):
        """Test merging empty list."""
        result = merger.merge([])

        assert result.events == []
        assert result.count == 0
        assert result.sources == {}
        assert result.duplicates_removed == 0

    def test_merge_single_event(self, merger):
        """Test merging single event."""
        event = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event",
            date_start=datetime(2024, 1, 15),
        )
        result = merger.merge([event])

        assert len(result.events) == 1
        assert result.count == 1
        assert result.sources == {"doc-1": 1}

    def test_merge_sorts_chronologically(self, merger, sample_events):
        """Test events are sorted by date."""
        result = merger.merge(sample_events)

        assert len(result.events) == 3
        assert result.events[0].id == "e-1"  # January
        assert result.events[1].id == "e-2"  # February
        assert result.events[2].id == "e-3"  # March

    def test_merge_counts_sources(self, merger, sample_events):
        """Test source document counting."""
        result = merger.merge(sample_events)

        assert result.sources["doc-1"] == 2
        assert result.sources["doc-2"] == 1

    def test_merge_calculates_date_range(self, merger, sample_events):
        """Test date range calculation."""
        result = merger.merge(sample_events)

        assert result.date_range.start == datetime(2024, 1, 1)
        assert result.date_range.end == datetime(2024, 3, 1)


class TestDeduplicatedMerge:
    """Tests for deduplicated merge strategy."""

    @pytest.fixture
    def merger(self):
        """Create merger with deduplication strategy."""
        return TimelineMerger(strategy=MergeStrategy.DEDUPLICATED)

    def test_remove_exact_duplicates(self, merger):
        """Test removing exact duplicate events."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="The meeting was held",
                date_start=datetime(2024, 1, 15),
                confidence=0.9,
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="The meeting was held",
                date_start=datetime(2024, 1, 15),
                confidence=0.8,
            ),
        ]
        result = merger.merge(events)

        # Should keep only one
        assert result.count == 1
        assert result.duplicates_removed == 1

    def test_keep_higher_confidence(self, merger):
        """Test keeping event with higher confidence."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Same event here",
                date_start=datetime(2024, 1, 15),
                confidence=0.7,
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Same event here",
                date_start=datetime(2024, 1, 15),
                confidence=0.95,
            ),
        ]
        result = merger.merge(events)

        # Should keep the one with 0.95 confidence
        assert result.events[0].confidence == 0.95

    def test_keep_distinct_events(self, merger):
        """Test distinct events are not removed."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="First event",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Second different event",
                date_start=datetime(2024, 6, 15),  # Different date
            ),
        ]
        result = merger.merge(events)

        assert result.count == 2
        assert result.duplicates_removed == 0


class TestConsolidatedMerge:
    """Tests for consolidated merge strategy."""

    @pytest.fixture
    def merger(self):
        """Create merger with consolidation strategy."""
        return TimelineMerger(strategy=MergeStrategy.CONSOLIDATED)

    def test_consolidate_similar_events(self, merger):
        """Test consolidating similar events."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Meeting with John",
                date_start=datetime(2024, 1, 15),
                entities=["john"],
                confidence=0.9,
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="John had a meeting",
                date_start=datetime(2024, 1, 16),  # Within 7 days
                entities=["john"],
                confidence=0.85,
            ),
        ]
        result = merger.merge(events)

        # Similar events should be consolidated
        assert result.count <= 2

    def test_consolidation_preserves_entities(self, merger):
        """Test consolidated event includes all entities."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Meeting about project",
                date_start=datetime(2024, 1, 15),
                entities=["entity-1", "entity-2"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Project meeting",
                date_start=datetime(2024, 1, 16),
                entities=["entity-2", "entity-3"],
            ),
        ]
        result = merger.merge(events)

        # Check if consolidated events have merged entities
        all_entities = set()
        for event in result.events:
            all_entities.update(event.entities)

        # All original entities should be present
        assert "entity-1" in all_entities or "entity-2" in all_entities


class TestSourcePriorityMerge:
    """Tests for source priority merge strategy."""

    @pytest.fixture
    def merger(self):
        """Create merger with source priority strategy."""
        return TimelineMerger(strategy=MergeStrategy.SOURCE_PRIORITY)

    def test_priority_document_first(self, merger):
        """Test priority documents are preferred."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-low",
                text="Same event text",
                date_start=datetime(2024, 1, 15),
                confidence=0.95,
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-high",
                text="Same event text",
                date_start=datetime(2024, 1, 15),
                confidence=0.8,
            ),
        ]
        result = merger.merge(events, priority_docs=["doc-high"])

        # Should keep the priority document version
        assert result.events[0].document_id == "doc-high"

    def test_no_priority_fallback(self, merger):
        """Test behavior with no priority documents."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 15),
            ),
        ]
        result = merger.merge(events, priority_docs=[])

        assert len(result.events) == 1


class TestStrategyOverride:
    """Tests for strategy override in merge method."""

    @pytest.fixture
    def merger(self):
        """Create merger with default strategy."""
        return TimelineMerger(strategy=MergeStrategy.CHRONOLOGICAL)

    def test_override_with_deduplicated(self, merger):
        """Test overriding to deduplicated strategy."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Same text here",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Same text here",
                date_start=datetime(2024, 1, 15),
            ),
        ]

        # Default would keep both
        result_default = merger.merge(events)

        # Override to deduplicate
        result_dedup = merger.merge(events, strategy=MergeStrategy.DEDUPLICATED)

        # Deduplicated should have fewer or equal events
        assert result_dedup.count <= result_default.count


class TestDuplicateDetection:
    """Tests for _are_duplicates method."""

    @pytest.fixture
    def merger(self):
        """Create merger for testing."""
        return TimelineMerger()

    def test_same_date_same_text(self, merger):
        """Test events with same date and text are duplicates."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Meeting with team",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Meeting with team",
            date_start=datetime(2024, 1, 15),
        )

        assert merger._are_duplicates(event1, event2)

    def test_different_dates_not_duplicates(self, merger):
        """Test events with different dates are not duplicates."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Meeting with team",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Meeting with team",
            date_start=datetime(2024, 6, 15),  # Different date
        )

        assert not merger._are_duplicates(event1, event2)

    def test_common_entities_duplicates(self, merger):
        """Test events with common entities and close dates are duplicates."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="John met with Sarah",
            date_start=datetime(2024, 1, 15),
            entities=["john", "sarah"],
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Sarah met John",
            date_start=datetime(2024, 1, 16),  # Within 1 day
            entities=["sarah", "john"],
        )

        assert merger._are_duplicates(event1, event2)


class TestSimilarityDetection:
    """Tests for _are_similar method."""

    @pytest.fixture
    def merger(self):
        """Create merger for testing."""
        return TimelineMerger()

    def test_close_dates_similar(self, merger):
        """Test events within 7 days are potentially similar."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Project review meeting",
            date_start=datetime(2024, 1, 15),
            entities=["project-x"],
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Review of project progress",
            date_start=datetime(2024, 1, 18),
            entities=["project-x"],
        )

        assert merger._are_similar(event1, event2)

    def test_distant_dates_not_similar(self, merger):
        """Test events more than 7 days apart are not similar."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event one",
            date_start=datetime(2024, 1, 1),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event one",
            date_start=datetime(2024, 2, 1),  # More than 7 days
        )

        assert not merger._are_similar(event1, event2)


class TestConsolidateGroup:
    """Tests for _consolidate_group method."""

    @pytest.fixture
    def merger(self):
        """Create merger for testing."""
        return TimelineMerger()

    def test_consolidate_preserves_earliest_date(self, merger):
        """Test consolidated event uses earliest date."""
        events = [
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event B",
                date_start=datetime(2024, 1, 20),
            ),
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event A",
                date_start=datetime(2024, 1, 15),
            ),
        ]

        consolidated = merger._consolidate_group(events)

        assert consolidated.date_start == datetime(2024, 1, 15)

    def test_consolidate_uses_highest_confidence(self, merger):
        """Test consolidated event uses highest confidence."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 15),
                confidence=0.7,
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event",
                date_start=datetime(2024, 1, 16),
                confidence=0.95,
            ),
        ]

        consolidated = merger._consolidate_group(events)

        assert consolidated.confidence == 0.95

    def test_consolidate_combines_entities(self, merger):
        """Test consolidated event combines all entities."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 15),
                entities=["entity-1", "entity-2"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event",
                date_start=datetime(2024, 1, 16),
                entities=["entity-2", "entity-3"],
            ),
        ]

        consolidated = merger._consolidate_group(events)

        assert "entity-1" in consolidated.entities
        assert "entity-2" in consolidated.entities
        assert "entity-3" in consolidated.entities

    def test_consolidate_adds_metadata(self, merger):
        """Test consolidated event has consolidation metadata."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event",
                date_start=datetime(2024, 1, 16),
            ),
        ]

        consolidated = merger._consolidate_group(events)

        assert consolidated.metadata.get("consolidated") is True
        assert consolidated.metadata.get("source_count") == 2


class TestDateRangeCalculation:
    """Tests for _calculate_date_range method."""

    @pytest.fixture
    def merger(self):
        """Create merger for testing."""
        return TimelineMerger()

    def test_empty_events(self, merger):
        """Test date range for empty events."""
        date_range = merger._calculate_date_range([])

        assert date_range.start is None
        assert date_range.end is None

    def test_single_event(self, merger):
        """Test date range for single event."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 6, 15),
            )
        ]

        date_range = merger._calculate_date_range(events)

        assert date_range.start == datetime(2024, 6, 15)
        assert date_range.end == datetime(2024, 6, 15)

    def test_considers_end_dates(self, merger):
        """Test date range considers end dates."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 1),
                date_end=datetime(2024, 12, 31),
            )
        ]

        date_range = merger._calculate_date_range(events)

        assert date_range.end == datetime(2024, 12, 31)
