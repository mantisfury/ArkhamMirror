"""Temporal conflict detection."""

import logging
import uuid
from datetime import timedelta
from typing import Optional

from .models import (
    TimelineEvent,
    TemporalConflict,
    ConflictType,
    ConflictSeverity,
)

logger = logging.getLogger(__name__)


class ConflictDetector:
    """
    Detects temporal conflicts between timeline events.

    Identifies:
    - Contradictions: Same event with different dates
    - Inconsistencies: Illogical date sequences
    - Gaps: Missing timeline segments
    - Overlaps: Incompatible simultaneous events
    """

    def __init__(self, tolerance_days: int = 0):
        """
        Initialize conflict detector.

        Args:
            tolerance_days: Days of tolerance for date matching (0 = exact)
        """
        self.tolerance_days = tolerance_days

    def detect_conflicts(
        self,
        events: list[TimelineEvent],
        conflict_types: Optional[list[ConflictType]] = None
    ) -> list[TemporalConflict]:
        """
        Detect all conflicts in a set of events.

        Args:
            events: Timeline events to analyze
            conflict_types: Types of conflicts to detect (None = all)

        Returns:
            List of detected conflicts
        """
        if conflict_types is None:
            conflict_types = list(ConflictType)

        conflicts = []

        if ConflictType.CONTRADICTION in conflict_types:
            conflicts.extend(self._detect_contradictions(events))

        if ConflictType.INCONSISTENCY in conflict_types:
            conflicts.extend(self._detect_inconsistencies(events))

        if ConflictType.GAP in conflict_types:
            conflicts.extend(self._detect_gaps(events))

        if ConflictType.OVERLAP in conflict_types:
            conflicts.extend(self._detect_overlaps(events))

        return conflicts

    def _detect_contradictions(
        self,
        events: list[TimelineEvent]
    ) -> list[TemporalConflict]:
        """
        Detect contradictory dates for similar events.

        Two events are contradictory if they refer to the same occurrence
        but have significantly different dates.
        """
        conflicts = []

        # Group events by document
        by_document = {}
        for event in events:
            if event.document_id not in by_document:
                by_document[event.document_id] = []
            by_document[event.document_id].append(event)

        # Compare events across documents
        doc_ids = list(by_document.keys())
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                doc1_events = by_document[doc_ids[i]]
                doc2_events = by_document[doc_ids[j]]

                for event1 in doc1_events:
                    for event2 in doc2_events:
                        # Check if events might refer to same occurrence
                        if self._are_similar_events(event1, event2):
                            # Check if dates contradict
                            if not self._dates_match(event1.date_start, event2.date_start):
                                severity = self._assess_severity(event1, event2)

                                conflict = TemporalConflict(
                                    id=str(uuid.uuid4()),
                                    type=ConflictType.CONTRADICTION,
                                    severity=severity,
                                    events=[event1.id, event2.id],
                                    description=(
                                        f"Contradictory dates: Event in {event1.document_id} "
                                        f"claims {event1.date_start.date()}, but event in "
                                        f"{event2.document_id} claims {event2.date_start.date()}"
                                    ),
                                    documents=[event1.document_id, event2.document_id],
                                    suggested_resolution="verify_source",
                                    metadata={
                                        "date_diff_days": abs(
                                            (event1.date_start - event2.date_start).days
                                        ),
                                        "text1": event1.text,
                                        "text2": event2.text,
                                    }
                                )
                                conflicts.append(conflict)

        return conflicts

    def _detect_inconsistencies(
        self,
        events: list[TimelineEvent]
    ) -> list[TemporalConflict]:
        """
        Detect logically inconsistent date sequences.

        For example:
        - Event A happens after Event B, but dates show opposite
        - Deadlines that have already passed
        - Future events described in past tense
        """
        conflicts = []

        # Sort events by document
        by_document = {}
        for event in events:
            if event.document_id not in by_document:
                by_document[event.document_id] = []
            by_document[event.document_id].append(event)

        for doc_id, doc_events in by_document.items():
            # Sort by position in text
            sorted_events = sorted(
                [e for e in doc_events if e.span],
                key=lambda e: e.span[0]
            )

            # Check for temporal markers that indicate sequence
            for i in range(len(sorted_events) - 1):
                event1 = sorted_events[i]
                event2 = sorted_events[i + 1]

                # Look for sequence markers between events
                if event1.span and event2.span:
                    # Extract text between events
                    # (This is a simplified check - in practice would need access to full text)

                    # Check if dates are in logical order
                    # If event2 has markers like "before", "earlier", "previously"
                    # but date is later, that's inconsistent
                    if event2.date_start < event1.date_start:
                        # Check for temporal markers
                        markers_later = ["later", "after", "following", "next", "then"]
                        markers_earlier = ["before", "earlier", "previously", "prior"]

                        # This is a simplified heuristic
                        # Real implementation would analyze text context
                        if any(marker in event2.text.lower() for marker in markers_later):
                            conflict = TemporalConflict(
                                id=str(uuid.uuid4()),
                                type=ConflictType.INCONSISTENCY,
                                severity=ConflictSeverity.MEDIUM,
                                events=[event1.id, event2.id],
                                description=(
                                    f"Inconsistent sequence: Event 2 appears to be after Event 1 "
                                    f"but has earlier date ({event2.date_start.date()} vs "
                                    f"{event1.date_start.date()})"
                                ),
                                documents=[doc_id],
                                suggested_resolution="review_context",
                                metadata={
                                    "text1": event1.text,
                                    "text2": event2.text,
                                }
                            )
                            conflicts.append(conflict)

        return conflicts

    def _detect_gaps(
        self,
        events: list[TimelineEvent]
    ) -> list[TemporalConflict]:
        """
        Detect unexpected gaps in timeline.

        Identifies periods where events are expected but missing,
        based on patterns in the data.
        """
        conflicts = []

        if len(events) < 3:
            return conflicts  # Need enough events to establish pattern

        # Sort events chronologically
        sorted_events = sorted(events, key=lambda e: e.date_start)

        # Calculate typical gap between events
        gaps = []
        for i in range(len(sorted_events) - 1):
            gap_days = (sorted_events[i + 1].date_start - sorted_events[i].date_start).days
            gaps.append(gap_days)

        if not gaps:
            return conflicts

        # Calculate median gap
        sorted_gaps = sorted(gaps)
        median_gap = sorted_gaps[len(sorted_gaps) // 2]

        # Look for gaps much larger than median
        threshold = median_gap * 3  # 3x median is suspicious

        for i in range(len(sorted_events) - 1):
            gap_days = (sorted_events[i + 1].date_start - sorted_events[i].date_start).days

            if gap_days > threshold and gap_days > 30:  # At least 30 days
                conflict = TemporalConflict(
                    id=str(uuid.uuid4()),
                    type=ConflictType.GAP,
                    severity=ConflictSeverity.LOW,
                    events=[sorted_events[i].id, sorted_events[i + 1].id],
                    description=(
                        f"Unexpected {gap_days}-day gap between events "
                        f"({sorted_events[i].date_start.date()} to "
                        f"{sorted_events[i + 1].date_start.date()})"
                    ),
                    documents=list(set([sorted_events[i].document_id, sorted_events[i + 1].document_id])),
                    suggested_resolution="check_for_missing_data",
                    metadata={
                        "gap_days": gap_days,
                        "median_gap": median_gap,
                    }
                )
                conflicts.append(conflict)

        return conflicts

    def _detect_overlaps(
        self,
        events: list[TimelineEvent]
    ) -> list[TemporalConflict]:
        """
        Detect incompatible overlapping events.

        Events that cannot logically occur simultaneously.
        """
        conflicts = []

        # This is a simplified implementation
        # Real implementation would need semantic understanding
        # of whether events can co-occur

        # For now, check for events with same entities at same time
        # from different documents claiming different things

        entity_events = {}
        for event in events:
            if event.entities:
                for entity_id in event.entities:
                    if entity_id not in entity_events:
                        entity_events[entity_id] = []
                    entity_events[entity_id].append(event)

        for entity_id, entity_event_list in entity_events.items():
            # Check for simultaneous events from different documents
            for i in range(len(entity_event_list)):
                for j in range(i + 1, len(entity_event_list)):
                    event1 = entity_event_list[i]
                    event2 = entity_event_list[j]

                    # Skip if same document
                    if event1.document_id == event2.document_id:
                        continue

                    # Check if events overlap in time
                    if self._dates_match(event1.date_start, event2.date_start):
                        # This is a simplified check
                        # Real implementation would analyze whether events are compatible
                        conflict = TemporalConflict(
                            id=str(uuid.uuid4()),
                            type=ConflictType.OVERLAP,
                            severity=ConflictSeverity.LOW,
                            events=[event1.id, event2.id],
                            description=(
                                f"Potentially overlapping events for entity {entity_id} "
                                f"around {event1.date_start.date()}"
                            ),
                            documents=[event1.document_id, event2.document_id],
                            suggested_resolution="review_compatibility",
                            metadata={
                                "entity_id": entity_id,
                                "text1": event1.text,
                                "text2": event2.text,
                            }
                        )
                        conflicts.append(conflict)

        return conflicts

    def _are_similar_events(
        self,
        event1: TimelineEvent,
        event2: TimelineEvent
    ) -> bool:
        """
        Check if two events might refer to the same occurrence.

        Uses heuristics:
        - Similar text
        - Common entities
        - Similar dates (within reasonable range)
        """
        # Check for common entities
        common_entities = set(event1.entities) & set(event2.entities)
        if common_entities:
            return True

        # Check for similar text (simplified - would use embeddings in production)
        text1_words = set(event1.text.lower().split())
        text2_words = set(event2.text.lower().split())
        overlap = len(text1_words & text2_words)
        if overlap >= 2:  # At least 2 words in common
            return True

        # Check if dates are close enough to be plausibly the same event
        days_diff = abs((event1.date_start - event2.date_start).days)
        if days_diff <= 7:  # Within a week
            return True

        return False

    def _dates_match(
        self,
        date1,
        date2
    ) -> bool:
        """
        Check if two dates match within tolerance.

        Args:
            date1: First datetime
            date2: Second datetime

        Returns:
            True if dates match within tolerance
        """
        diff_days = abs((date1 - date2).days)
        return diff_days <= self.tolerance_days

    def _assess_severity(
        self,
        event1: TimelineEvent,
        event2: TimelineEvent
    ) -> ConflictSeverity:
        """
        Assess the severity of a conflict between two events.

        Args:
            event1: First event
            event2: Second event

        Returns:
            Severity level
        """
        days_diff = abs((event1.date_start - event2.date_start).days)

        # Consider confidence levels
        avg_confidence = (event1.confidence + event2.confidence) / 2

        # High confidence events with large discrepancy = critical
        if avg_confidence > 0.9 and days_diff > 30:
            return ConflictSeverity.CRITICAL

        # Large discrepancy = high severity
        if days_diff > 90:
            return ConflictSeverity.HIGH

        # Moderate discrepancy = medium severity
        if days_diff > 7:
            return ConflictSeverity.MEDIUM

        # Small discrepancy = low severity
        return ConflictSeverity.LOW
