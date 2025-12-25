"""Timeline merging and consolidation."""

import logging
from datetime import datetime
from typing import Optional

from .models import (
    TimelineEvent,
    MergeStrategy,
    MergeResult,
    DateRange,
)

logger = logging.getLogger(__name__)


class TimelineMerger:
    """
    Merges timelines from multiple documents.

    Supports various merge strategies:
    - Chronological: Simple date-based sorting
    - Deduplicated: Remove duplicate events
    - Consolidated: Merge similar events
    - Source-prioritized: Prefer certain documents
    """

    def __init__(self, strategy: MergeStrategy = MergeStrategy.CHRONOLOGICAL):
        """
        Initialize timeline merger.

        Args:
            strategy: Merge strategy to use
        """
        self.strategy = strategy

    def merge(
        self,
        events: list[TimelineEvent],
        strategy: Optional[MergeStrategy] = None,
        priority_docs: Optional[list[str]] = None
    ) -> MergeResult:
        """
        Merge timeline events.

        Args:
            events: Events to merge
            strategy: Override default strategy
            priority_docs: Document IDs to prioritize (for SOURCE_PRIORITY strategy)

        Returns:
            MergeResult with merged events
        """
        if not events:
            return MergeResult(
                events=[],
                count=0,
                sources={},
                date_range=DateRange(),
                duplicates_removed=0,
            )

        strategy = strategy or self.strategy

        # Count sources
        sources = {}
        for event in events:
            sources[event.document_id] = sources.get(event.document_id, 0) + 1

        # Apply strategy
        if strategy == MergeStrategy.CHRONOLOGICAL:
            merged_events = self._merge_chronological(events)
            duplicates_removed = 0

        elif strategy == MergeStrategy.DEDUPLICATED:
            merged_events, duplicates_removed = self._merge_deduplicated(events)

        elif strategy == MergeStrategy.CONSOLIDATED:
            merged_events, duplicates_removed = self._merge_consolidated(events)

        elif strategy == MergeStrategy.SOURCE_PRIORITY:
            merged_events = self._merge_source_priority(events, priority_docs or [])
            duplicates_removed = 0

        else:
            merged_events = self._merge_chronological(events)
            duplicates_removed = 0

        # Calculate date range
        date_range = self._calculate_date_range(merged_events)

        return MergeResult(
            events=merged_events,
            count=len(merged_events),
            sources=sources,
            date_range=date_range,
            duplicates_removed=duplicates_removed,
        )

    def _merge_chronological(
        self,
        events: list[TimelineEvent]
    ) -> list[TimelineEvent]:
        """
        Simple chronological merge - just sort by date.

        Args:
            events: Events to merge

        Returns:
            Sorted events
        """
        return sorted(events, key=lambda e: e.date_start)

    def _merge_deduplicated(
        self,
        events: list[TimelineEvent]
    ) -> tuple[list[TimelineEvent], int]:
        """
        Merge with deduplication - remove duplicate events.

        Args:
            events: Events to merge

        Returns:
            Tuple of (deduplicated events, count of duplicates removed)
        """
        # Sort chronologically
        sorted_events = sorted(events, key=lambda e: e.date_start)

        deduplicated = []
        removed_count = 0

        for event in sorted_events:
            # Check if this event is a duplicate of any existing event
            is_duplicate = False

            for existing in deduplicated:
                if self._are_duplicates(event, existing):
                    is_duplicate = True
                    removed_count += 1

                    # Keep the one with higher confidence
                    if event.confidence > existing.confidence:
                        # Replace existing with this one
                        idx = deduplicated.index(existing)
                        deduplicated[idx] = event

                    break

            if not is_duplicate:
                deduplicated.append(event)

        return deduplicated, removed_count

    def _merge_consolidated(
        self,
        events: list[TimelineEvent]
    ) -> tuple[list[TimelineEvent], int]:
        """
        Merge with consolidation - merge similar events into composite events.

        Args:
            events: Events to merge

        Returns:
            Tuple of (consolidated events, count of events merged)
        """
        # First deduplicate
        deduplicated, dup_count = self._merge_deduplicated(events)

        # Then group similar events
        groups = []
        merged_count = 0

        for event in deduplicated:
            # Find group for this event
            found_group = False

            for group in groups:
                # Check if event is similar to any in group
                if any(self._are_similar(event, e) for e in group):
                    group.append(event)
                    found_group = True
                    merged_count += 1
                    break

            if not found_group:
                groups.append([event])

        # Consolidate each group into single event
        consolidated = []
        for group in groups:
            if len(group) == 1:
                consolidated.append(group[0])
            else:
                consolidated_event = self._consolidate_group(group)
                consolidated.append(consolidated_event)

        return sorted(consolidated, key=lambda e: e.date_start), merged_count

    def _merge_source_priority(
        self,
        events: list[TimelineEvent],
        priority_docs: list[str]
    ) -> list[TimelineEvent]:
        """
        Merge with source prioritization - prefer events from certain documents.

        Args:
            events: Events to merge
            priority_docs: Document IDs in priority order (highest first)

        Returns:
            Merged events with priorities applied
        """
        # Assign priority scores
        events_with_priority = []
        for event in events:
            if event.document_id in priority_docs:
                priority = len(priority_docs) - priority_docs.index(event.document_id)
            else:
                priority = 0

            events_with_priority.append((priority, event))

        # Sort by date, then by priority (higher priority first)
        sorted_events = sorted(
            events_with_priority,
            key=lambda x: (x[1].date_start, -x[0])
        )

        # Remove duplicates, keeping higher priority versions
        deduplicated = []
        for priority, event in sorted_events:
            # Check for duplicates
            is_duplicate = False
            for existing_priority, existing in deduplicated:
                if self._are_duplicates(event, existing):
                    is_duplicate = True
                    # Keep higher priority version
                    if priority > existing_priority:
                        idx = deduplicated.index((existing_priority, existing))
                        deduplicated[idx] = (priority, event)
                    break

            if not is_duplicate:
                deduplicated.append((priority, event))

        # Extract just the events
        return [event for priority, event in deduplicated]

    def _are_duplicates(
        self,
        event1: TimelineEvent,
        event2: TimelineEvent
    ) -> bool:
        """
        Check if two events are duplicates.

        Events are duplicates if they have:
        - Same date (within 1 day)
        - Very similar text
        - Same entities
        """
        # Check date similarity
        days_diff = abs((event1.date_start - event2.date_start).days)
        if days_diff > 1:
            return False

        # Check entity overlap
        if event1.entities and event2.entities:
            common_entities = set(event1.entities) & set(event2.entities)
            if not common_entities:
                return False

        # Check text similarity (simplified)
        text1_words = set(event1.text.lower().split())
        text2_words = set(event2.text.lower().split())

        if not text1_words or not text2_words:
            return False

        overlap = len(text1_words & text2_words)
        union = len(text1_words | text2_words)

        # Jaccard similarity > 0.7
        similarity = overlap / union if union > 0 else 0

        return similarity > 0.7

    def _are_similar(
        self,
        event1: TimelineEvent,
        event2: TimelineEvent
    ) -> bool:
        """
        Check if two events are similar enough to consolidate.

        Events are similar if they have:
        - Close dates (within 7 days)
        - Some common entities
        - Some text overlap
        """
        # Check date proximity
        days_diff = abs((event1.date_start - event2.date_start).days)
        if days_diff > 7:
            return False

        # Check for any entity overlap
        if event1.entities and event2.entities:
            common_entities = set(event1.entities) & set(event2.entities)
            if common_entities:
                return True

        # Check text similarity
        text1_words = set(event1.text.lower().split())
        text2_words = set(event2.text.lower().split())

        if not text1_words or not text2_words:
            return False

        overlap = len(text1_words & text2_words)
        min_size = min(len(text1_words), len(text2_words))

        # At least 30% overlap
        similarity = overlap / min_size if min_size > 0 else 0

        return similarity > 0.3

    def _consolidate_group(
        self,
        group: list[TimelineEvent]
    ) -> TimelineEvent:
        """
        Consolidate a group of similar events into one composite event.

        Args:
            group: Events to consolidate

        Returns:
            Consolidated event
        """
        # Use earliest date as primary
        sorted_group = sorted(group, key=lambda e: e.date_start)
        primary = sorted_group[0]

        # Collect all unique entities
        all_entities = set()
        for event in group:
            all_entities.update(event.entities)

        # Collect all document IDs
        all_docs = list(set(event.document_id for event in group))

        # Use highest confidence
        max_confidence = max(event.confidence for event in group)

        # Combine text (first 3 unique texts)
        texts = []
        for event in sorted_group:
            if event.text not in texts:
                texts.append(event.text)
            if len(texts) >= 3:
                break

        combined_text = " | ".join(texts)

        # Create consolidated event
        consolidated = TimelineEvent(
            id=primary.id,  # Use primary ID
            document_id=primary.document_id,  # Use primary document
            text=combined_text,
            date_start=primary.date_start,
            date_end=primary.date_end,
            precision=primary.precision,
            confidence=max_confidence,
            entities=list(all_entities),
            event_type=primary.event_type,
            span=primary.span,
            metadata={
                "consolidated": True,
                "source_count": len(group),
                "source_documents": all_docs,
                "original_events": [e.id for e in group],
            }
        )

        return consolidated

    def _calculate_date_range(
        self,
        events: list[TimelineEvent]
    ) -> DateRange:
        """
        Calculate the date range covered by events.

        Args:
            events: Timeline events

        Returns:
            DateRange object
        """
        if not events:
            return DateRange()

        earliest = min(event.date_start for event in events)

        # For latest, consider end dates too
        latest_candidates = [event.date_start for event in events]
        for event in events:
            if event.date_end:
                latest_candidates.append(event.date_end)

        latest = max(latest_candidates)

        return DateRange(start=earliest, end=latest)
