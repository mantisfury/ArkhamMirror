"""Database storage for anomalies."""

import logging
from typing import Any
from datetime import datetime, timedelta

from .models import (
    Anomaly,
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    AnomalyPattern,
    AnomalyStats,
    AnalystNote,
)

logger = logging.getLogger(__name__)


class AnomalyStore:
    """
    Storage layer for anomaly data.

    Manages CRUD operations for anomalies and related data.
    In a real implementation, this would use SQLAlchemy or similar.
    For now, it's an in-memory store.
    """

    def __init__(self):
        """Initialize the store."""
        self.anomalies: dict[str, Anomaly] = {}
        self.patterns: dict[str, AnomalyPattern] = {}
        self.notes: dict[str, list[AnalystNote]] = {}  # anomaly_id -> notes

    async def create_anomaly(self, anomaly: Anomaly) -> Anomaly:
        """
        Store a new anomaly.

        Args:
            anomaly: Anomaly to store

        Returns:
            Stored anomaly
        """
        self.anomalies[anomaly.id] = anomaly
        logger.debug(f"Stored anomaly {anomaly.id} for doc {anomaly.doc_id}")
        return anomaly

    async def get_anomaly(self, anomaly_id: str) -> Anomaly | None:
        """
        Get an anomaly by ID.

        Args:
            anomaly_id: Anomaly ID

        Returns:
            Anomaly or None if not found
        """
        return self.anomalies.get(anomaly_id)

    async def update_anomaly(self, anomaly: Anomaly) -> Anomaly:
        """
        Update an existing anomaly.

        Args:
            anomaly: Updated anomaly

        Returns:
            Updated anomaly
        """
        anomaly.updated_at = datetime.utcnow()
        self.anomalies[anomaly.id] = anomaly
        logger.debug(f"Updated anomaly {anomaly.id}")
        return anomaly

    async def delete_anomaly(self, anomaly_id: str) -> bool:
        """
        Delete an anomaly.

        Args:
            anomaly_id: Anomaly ID

        Returns:
            True if deleted, False if not found
        """
        if anomaly_id in self.anomalies:
            del self.anomalies[anomaly_id]
            if anomaly_id in self.notes:
                del self.notes[anomaly_id]
            logger.debug(f"Deleted anomaly {anomaly_id}")
            return True
        return False

    async def list_anomalies(
        self,
        offset: int = 0,
        limit: int = 20,
        anomaly_type: AnomalyType | None = None,
        status: AnomalyStatus | None = None,
        severity: SeverityLevel | None = None,
        doc_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[list[Anomaly], int]:
        """
        List anomalies with filtering and pagination.

        Args:
            offset: Pagination offset
            limit: Maximum results
            anomaly_type: Filter by type
            status: Filter by status
            severity: Filter by severity
            doc_id: Filter by document ID
            project_id: Filter by project ID

        Returns:
            Tuple of (anomalies, total_count)
        """
        # Filter
        filtered = list(self.anomalies.values())

        if anomaly_type:
            filtered = [a for a in filtered if a.anomaly_type == anomaly_type]
        if status:
            filtered = [a for a in filtered if a.status == status]
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        if doc_id:
            filtered = [a for a in filtered if a.doc_id == doc_id]

        # Sort by detected_at descending
        filtered.sort(key=lambda a: a.detected_at, reverse=True)

        total = len(filtered)

        # Paginate
        result = filtered[offset:offset + limit]

        return result, total

    async def get_anomalies_by_doc(self, doc_id: str) -> list[Anomaly]:
        """
        Get all anomalies for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of anomalies
        """
        anomalies = [a for a in self.anomalies.values() if a.doc_id == doc_id]
        anomalies.sort(key=lambda a: a.detected_at, reverse=True)
        return anomalies

    async def update_status(
        self,
        anomaly_id: str,
        status: AnomalyStatus,
        reviewed_by: str | None = None,
        notes: str = "",
    ) -> Anomaly | None:
        """
        Update anomaly status.

        Args:
            anomaly_id: Anomaly ID
            status: New status
            reviewed_by: Reviewer identifier
            notes: Review notes

        Returns:
            Updated anomaly or None if not found
        """
        anomaly = self.anomalies.get(anomaly_id)
        if not anomaly:
            return None

        anomaly.status = status
        anomaly.reviewed_by = reviewed_by
        anomaly.reviewed_at = datetime.utcnow()
        anomaly.updated_at = datetime.utcnow()

        if notes:
            anomaly.notes = notes

        self.anomalies[anomaly_id] = anomaly
        logger.debug(f"Updated status for anomaly {anomaly_id} to {status.value}")

        return anomaly

    async def add_note(self, note: AnalystNote) -> AnalystNote:
        """
        Add an analyst note to an anomaly.

        Args:
            note: Note to add

        Returns:
            Stored note
        """
        if note.anomaly_id not in self.notes:
            self.notes[note.anomaly_id] = []

        self.notes[note.anomaly_id].append(note)
        logger.debug(f"Added note to anomaly {note.anomaly_id}")

        return note

    async def get_notes(self, anomaly_id: str) -> list[AnalystNote]:
        """
        Get all notes for an anomaly.

        Args:
            anomaly_id: Anomaly ID

        Returns:
            List of notes
        """
        return self.notes.get(anomaly_id, [])

    async def create_pattern(self, pattern: AnomalyPattern) -> AnomalyPattern:
        """
        Store an anomaly pattern.

        Args:
            pattern: Pattern to store

        Returns:
            Stored pattern
        """
        self.patterns[pattern.id] = pattern
        logger.debug(f"Stored pattern {pattern.id}")
        return pattern

    async def get_pattern(self, pattern_id: str) -> AnomalyPattern | None:
        """
        Get a pattern by ID.

        Args:
            pattern_id: Pattern ID

        Returns:
            Pattern or None if not found
        """
        return self.patterns.get(pattern_id)

    async def list_patterns(self) -> list[AnomalyPattern]:
        """
        List all patterns.

        Returns:
            List of patterns
        """
        patterns = list(self.patterns.values())
        patterns.sort(key=lambda p: p.detected_at, reverse=True)
        return patterns

    async def get_stats(self) -> AnomalyStats:
        """
        Calculate anomaly statistics.

        Returns:
            Statistics object
        """
        all_anomalies = list(self.anomalies.values())
        total = len(all_anomalies)

        # Count by type
        by_type = {}
        for anomaly_type in AnomalyType:
            count = len([a for a in all_anomalies if a.anomaly_type == anomaly_type])
            by_type[anomaly_type.value] = count

        # Count by status
        by_status = {}
        for status in AnomalyStatus:
            count = len([a for a in all_anomalies if a.status == status])
            by_status[status.value] = count

        # Count by severity
        by_severity = {}
        for severity in SeverityLevel:
            count = len([a for a in all_anomalies if a.severity == severity])
            by_severity[severity.value] = count

        # Recent activity
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)

        detected_last_24h = len([a for a in all_anomalies if a.detected_at >= last_24h])
        confirmed_last_24h = len([
            a for a in all_anomalies
            if a.status == AnomalyStatus.CONFIRMED and a.reviewed_at and a.reviewed_at >= last_24h
        ])
        dismissed_last_24h = len([
            a for a in all_anomalies
            if a.status == AnomalyStatus.DISMISSED and a.reviewed_at and a.reviewed_at >= last_24h
        ])

        # Quality metrics
        reviewed = [a for a in all_anomalies if a.status in {AnomalyStatus.CONFIRMED, AnomalyStatus.FALSE_POSITIVE, AnomalyStatus.DISMISSED}]
        false_positives = [a for a in all_anomalies if a.status == AnomalyStatus.FALSE_POSITIVE]

        false_positive_rate = len(false_positives) / len(reviewed) if reviewed else 0.0
        avg_confidence = sum(a.confidence for a in all_anomalies) / total if total else 0.0

        return AnomalyStats(
            total_anomalies=total,
            by_type=by_type,
            by_status=by_status,
            by_severity=by_severity,
            detected_last_24h=detected_last_24h,
            confirmed_last_24h=confirmed_last_24h,
            dismissed_last_24h=dismissed_last_24h,
            false_positive_rate=false_positive_rate,
            avg_confidence=avg_confidence,
        )

    async def get_facets(self) -> dict[str, Any]:
        """
        Get facet counts for filtering.

        Returns:
            Dictionary of facet counts
        """
        all_anomalies = list(self.anomalies.values())

        facets = {
            'types': {},
            'statuses': {},
            'severities': {},
        }

        for anomaly_type in AnomalyType:
            count = len([a for a in all_anomalies if a.anomaly_type == anomaly_type])
            facets['types'][anomaly_type.value] = count

        for status in AnomalyStatus:
            count = len([a for a in all_anomalies if a.status == status])
            facets['statuses'][status.value] = count

        for severity in SeverityLevel:
            count = len([a for a in all_anomalies if a.severity == severity])
            facets['severities'][severity.value] = count

        return facets
