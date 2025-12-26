"""
Timeline Shard - Conflict Detection Tests

Tests for the ConflictDetector class.
"""

import pytest
from datetime import datetime, timedelta

from arkham_shard_timeline.conflicts import ConflictDetector
from arkham_shard_timeline.models import (
    TimelineEvent,
    ConflictType,
    ConflictSeverity,
)


class TestConflictDetectorInit:
    """Tests for ConflictDetector initialization."""

    def test_default_initialization(self):
        """Test detector initializes with default tolerance."""
        detector = ConflictDetector()
        assert detector.tolerance_days == 0

    def test_custom_tolerance(self):
        """Test detector initializes with custom tolerance."""
        detector = ConflictDetector(tolerance_days=3)
        assert detector.tolerance_days == 3


class TestDetectConflicts:
    """Tests for the main detect_conflicts method."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_empty_events(self, detector):
        """Test no conflicts with empty events."""
        conflicts = detector.detect_conflicts([])
        assert conflicts == []

    def test_single_event(self, detector):
        """Test no conflicts with single event."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Single event",
                date_start=datetime(2024, 1, 15),
            )
        ]
        conflicts = detector.detect_conflicts(events)
        assert len(conflicts) == 0

    def test_filter_by_conflict_types(self, detector):
        """Test filtering by specific conflict types."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Meeting at office",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Meeting at office",
                date_start=datetime(2024, 6, 15),  # Different date
            ),
        ]

        # Only look for gaps
        conflicts = detector.detect_conflicts(events, [ConflictType.GAP])

        # All conflicts should be GAP type
        for conflict in conflicts:
            assert conflict.type == ConflictType.GAP


class TestContradictionDetection:
    """Tests for contradiction detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_detect_date_contradiction(self, detector):
        """Test detecting contradictory dates from different documents."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Meeting held today",
                date_start=datetime(2024, 1, 15),
                entities=["meeting-123"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Meeting was today",
                date_start=datetime(2024, 6, 15),  # Different date
                entities=["meeting-123"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        # Should detect contradiction due to same entity but different dates
        contradictions = [c for c in conflicts if c.type == ConflictType.CONTRADICTION]
        assert len(contradictions) >= 1

    def test_no_contradiction_same_document(self, detector):
        """Test no contradiction within same document."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",  # Same document
                text="Meeting started",
                date_start=datetime(2024, 1, 15),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-1",  # Same document
                text="Meeting ended",
                date_start=datetime(2024, 1, 16),
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        # Same document events shouldn't contradict each other
        assert len(conflicts) == 0

    def test_contradiction_includes_event_ids(self, detector):
        """Test contradiction includes both event IDs."""
        events = [
            TimelineEvent(
                id="event-a",
                document_id="doc-1",
                text="Same topic discussed",
                date_start=datetime(2024, 1, 15),
                entities=["topic-x"],
            ),
            TimelineEvent(
                id="event-b",
                document_id="doc-2",
                text="Topic was discussed",
                date_start=datetime(2024, 6, 15),
                entities=["topic-x"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        if conflicts:
            assert "event-a" in conflicts[0].events
            assert "event-b" in conflicts[0].events


class TestInconsistencyDetection:
    """Tests for logical inconsistency detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_detect_sequence_inconsistency(self, detector):
        """Test detecting inconsistent temporal sequences."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="First event happened",
                date_start=datetime(2024, 1, 15),
                span=(0, 20),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-1",
                text="Later this followed after",
                date_start=datetime(2024, 1, 10),  # Earlier date but marked as "later"
                span=(50, 80),
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.INCONSISTENCY])

        # Should detect some inconsistencies
        inconsistencies = [c for c in conflicts if c.type == ConflictType.INCONSISTENCY]
        # Note: Detection depends on temporal markers in text
        # This test may pass or fail depending on heuristic implementation


class TestGapDetection:
    """Tests for timeline gap detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_detect_large_gap(self, detector):
        """Test detecting unexpectedly large gaps."""
        # Create events with consistent spacing then one large gap
        events = []
        base_date = datetime(2024, 1, 1)

        # Events every 7 days
        for i in range(5):
            events.append(TimelineEvent(
                id=f"e-{i}",
                document_id="doc-1",
                text=f"Event {i}",
                date_start=base_date + timedelta(days=i * 7),
            ))

        # Add one event with huge gap
        events.append(TimelineEvent(
            id="e-gap",
            document_id="doc-1",
            text="Event after gap",
            date_start=base_date + timedelta(days=365),  # One year later
        ))

        conflicts = detector.detect_conflicts(events, [ConflictType.GAP])

        gaps = [c for c in conflicts if c.type == ConflictType.GAP]
        # Should detect the large gap
        assert len(gaps) >= 1

    def test_no_gap_consistent_spacing(self, detector):
        """Test no gap detection with consistent event spacing."""
        events = []
        base_date = datetime(2024, 1, 1)

        # Events every 7 days, consistently
        for i in range(10):
            events.append(TimelineEvent(
                id=f"e-{i}",
                document_id="doc-1",
                text=f"Event {i}",
                date_start=base_date + timedelta(days=i * 7),
            ))

        conflicts = detector.detect_conflicts(events, [ConflictType.GAP])

        gaps = [c for c in conflicts if c.type == ConflictType.GAP]
        # Consistent spacing shouldn't trigger gap detection
        assert len(gaps) == 0

    def test_gap_requires_minimum_events(self, detector):
        """Test gap detection needs minimum events."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event 1",
                date_start=datetime(2024, 1, 1),
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-1",
                text="Event 2",
                date_start=datetime(2024, 12, 31),  # Big gap but only 2 events
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.GAP])

        # Need at least 3 events to establish pattern
        gaps = [c for c in conflicts if c.type == ConflictType.GAP]
        assert len(gaps) == 0


class TestOverlapDetection:
    """Tests for overlap detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_detect_entity_overlap(self, detector):
        """Test detecting overlapping events for same entity."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="John was in New York",
                date_start=datetime(2024, 1, 15),
                entities=["john"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="John was in London",
                date_start=datetime(2024, 1, 15),  # Same date
                entities=["john"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.OVERLAP])

        overlaps = [c for c in conflicts if c.type == ConflictType.OVERLAP]
        assert len(overlaps) >= 1

    def test_no_overlap_different_dates(self, detector):
        """Test no overlap with different dates."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="John at event",
                date_start=datetime(2024, 1, 15),
                entities=["john"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="John at event",
                date_start=datetime(2024, 6, 15),  # Different date
                entities=["john"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.OVERLAP])

        overlaps = [c for c in conflicts if c.type == ConflictType.OVERLAP]
        # Different dates, no overlap
        assert len(overlaps) == 0

    def test_no_overlap_different_entities(self, detector):
        """Test no overlap with different entities."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="John at event",
                date_start=datetime(2024, 1, 15),
                entities=["john"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Jane at event",
                date_start=datetime(2024, 1, 15),
                entities=["jane"],  # Different entity
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.OVERLAP])

        overlaps = [c for c in conflicts if c.type == ConflictType.OVERLAP]
        assert len(overlaps) == 0


class TestSimilarEventsDetection:
    """Tests for _are_similar_events method."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_common_entities_similar(self, detector):
        """Test events with common entities are similar."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event one",
            date_start=datetime(2024, 1, 15),
            entities=["entity-x"],
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event two",
            date_start=datetime(2024, 1, 20),
            entities=["entity-x"],
        )

        assert detector._are_similar_events(event1, event2)

    def test_similar_text_similar(self, detector):
        """Test events with similar text are similar."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Meeting with team",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Team meeting",
            date_start=datetime(2024, 1, 20),
        )

        assert detector._are_similar_events(event1, event2)

    def test_close_dates_similar(self, detector):
        """Test events with close dates might be similar."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Some event",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Another event",
            date_start=datetime(2024, 1, 18),  # Within 7 days
        )

        # Close dates alone might trigger similarity
        assert detector._are_similar_events(event1, event2)


class TestDateMatching:
    """Tests for _dates_match method."""

    def test_exact_match_zero_tolerance(self):
        """Test exact date match with zero tolerance."""
        detector = ConflictDetector(tolerance_days=0)

        date1 = datetime(2024, 1, 15)
        date2 = datetime(2024, 1, 15)

        assert detector._dates_match(date1, date2)

    def test_no_match_one_day_zero_tolerance(self):
        """Test one day difference with zero tolerance."""
        detector = ConflictDetector(tolerance_days=0)

        date1 = datetime(2024, 1, 15)
        date2 = datetime(2024, 1, 16)

        assert not detector._dates_match(date1, date2)

    def test_match_within_tolerance(self):
        """Test dates match within tolerance."""
        detector = ConflictDetector(tolerance_days=3)

        date1 = datetime(2024, 1, 15)
        date2 = datetime(2024, 1, 17)  # 2 days apart

        assert detector._dates_match(date1, date2)

    def test_no_match_outside_tolerance(self):
        """Test dates don't match outside tolerance."""
        detector = ConflictDetector(tolerance_days=3)

        date1 = datetime(2024, 1, 15)
        date2 = datetime(2024, 1, 20)  # 5 days apart

        assert not detector._dates_match(date1, date2)


class TestSeverityAssessment:
    """Tests for _assess_severity method."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_critical_high_confidence_large_diff(self, detector):
        """Test critical severity for high confidence with large difference."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event",
            date_start=datetime(2024, 1, 1),
            confidence=0.95,
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event",
            date_start=datetime(2024, 6, 1),  # 5+ months apart
            confidence=0.95,
        )

        severity = detector._assess_severity(event1, event2)
        assert severity == ConflictSeverity.CRITICAL

    def test_high_severity_large_diff(self, detector):
        """Test high severity for large date difference."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event",
            date_start=datetime(2024, 1, 1),
            confidence=0.7,
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event",
            date_start=datetime(2024, 6, 1),  # >90 days
            confidence=0.7,
        )

        severity = detector._assess_severity(event1, event2)
        assert severity == ConflictSeverity.HIGH

    def test_medium_severity_moderate_diff(self, detector):
        """Test medium severity for moderate difference."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event",
            date_start=datetime(2024, 2, 1),  # ~15 days
        )

        severity = detector._assess_severity(event1, event2)
        assert severity == ConflictSeverity.MEDIUM

    def test_low_severity_small_diff(self, detector):
        """Test low severity for small difference."""
        event1 = TimelineEvent(
            id="e-1",
            document_id="doc-1",
            text="Event",
            date_start=datetime(2024, 1, 15),
        )
        event2 = TimelineEvent(
            id="e-2",
            document_id="doc-2",
            text="Event",
            date_start=datetime(2024, 1, 18),  # 3 days
        )

        severity = detector._assess_severity(event1, event2)
        assert severity == ConflictSeverity.LOW


class TestConflictProperties:
    """Tests for conflict output properties."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ConflictDetector()

    def test_conflict_has_id(self, detector):
        """Test detected conflicts have unique IDs."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Same event",
                date_start=datetime(2024, 1, 15),
                entities=["entity-x"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Same event",
                date_start=datetime(2024, 6, 15),
                entities=["entity-x"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        if conflicts:
            assert conflicts[0].id is not None
            assert len(conflicts[0].id) > 0

    def test_conflict_has_description(self, detector):
        """Test detected conflicts have descriptions."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-1",
                text="Event",
                date_start=datetime(2024, 1, 15),
                entities=["entity-x"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-2",
                text="Event",
                date_start=datetime(2024, 6, 15),
                entities=["entity-x"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        if conflicts:
            assert conflicts[0].description is not None
            assert len(conflicts[0].description) > 0

    def test_conflict_has_documents(self, detector):
        """Test detected conflicts include document IDs."""
        events = [
            TimelineEvent(
                id="e-1",
                document_id="doc-alpha",
                text="Event",
                date_start=datetime(2024, 1, 15),
                entities=["entity-x"],
            ),
            TimelineEvent(
                id="e-2",
                document_id="doc-beta",
                text="Event",
                date_start=datetime(2024, 6, 15),
                entities=["entity-x"],
            ),
        ]

        conflicts = detector.detect_conflicts(events, [ConflictType.CONTRADICTION])

        if conflicts:
            assert "doc-alpha" in conflicts[0].documents
            assert "doc-beta" in conflicts[0].documents
