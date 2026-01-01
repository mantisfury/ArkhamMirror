"""Database storage for anomalies."""

import json
import logging
from typing import Any, Dict, List, Optional
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
    Uses database persistence when available, falls back to in-memory.
    """

    def __init__(self, db=None):
        """
        Initialize the store.

        Args:
            db: Database service from frame (optional)
        """
        self._db = db
        # Fallback in-memory storage when database is not available
        self._anomalies: Dict[str, Anomaly] = {}
        self._patterns: Dict[str, AnomalyPattern] = {}
        self._notes: Dict[str, List[AnalystNote]] = {}

    async def create_anomaly(self, anomaly: Anomaly) -> Anomaly:
        """
        Store a new anomaly.

        Args:
            anomaly: Anomaly to store

        Returns:
            Stored anomaly
        """
        if self._db:
            await self._save_anomaly_to_db(anomaly)
        else:
            self._anomalies[anomaly.id] = anomaly

        logger.debug(f"Stored anomaly {anomaly.id} for doc {anomaly.doc_id}")
        return anomaly

    async def get_anomaly(self, anomaly_id: str) -> Optional[Anomaly]:
        """
        Get an anomaly by ID.

        Args:
            anomaly_id: Anomaly ID

        Returns:
            Anomaly or None if not found
        """
        if self._db:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_anomalies WHERE id = :id",
                {"id": anomaly_id}
            )
            return self._row_to_anomaly(row) if row else None
        else:
            return self._anomalies.get(anomaly_id)

    async def update_anomaly(self, anomaly: Anomaly) -> Anomaly:
        """
        Update an existing anomaly.

        Args:
            anomaly: Updated anomaly

        Returns:
            Updated anomaly
        """
        anomaly.updated_at = datetime.utcnow()

        if self._db:
            await self._save_anomaly_to_db(anomaly, update=True)
        else:
            self._anomalies[anomaly.id] = anomaly

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
        if self._db:
            # Delete associated notes first
            await self._db.execute(
                "DELETE FROM arkham_anomaly_notes WHERE anomaly_id = :id",
                {"id": anomaly_id}
            )
            # Delete the anomaly
            result = await self._db.execute(
                "DELETE FROM arkham_anomalies WHERE id = :id",
                {"id": anomaly_id}
            )
            logger.debug(f"Deleted anomaly {anomaly_id}")
            return True
        else:
            if anomaly_id in self._anomalies:
                del self._anomalies[anomaly_id]
                if anomaly_id in self._notes:
                    del self._notes[anomaly_id]
                logger.debug(f"Deleted anomaly {anomaly_id}")
                return True
            return False

    async def list_anomalies(
        self,
        offset: int = 0,
        limit: int = 20,
        anomaly_type: Optional[AnomalyType] = None,
        status: Optional[AnomalyStatus] = None,
        severity: Optional[SeverityLevel] = None,
        doc_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> tuple[List[Anomaly], int]:
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
        if self._db:
            # Build dynamic WHERE clause
            where_clauses = ["1=1"]
            params: Dict[str, Any] = {}

            if anomaly_type:
                where_clauses.append("anomaly_type = :anomaly_type")
                params["anomaly_type"] = anomaly_type.value
            if status:
                where_clauses.append("status = :status")
                params["status"] = status.value
            if severity:
                where_clauses.append("severity = :severity")
                params["severity"] = severity.value
            if doc_id:
                where_clauses.append("doc_id = :doc_id")
                params["doc_id"] = doc_id
            if project_id:
                where_clauses.append("project_id = :project_id")
                params["project_id"] = project_id

            where_sql = " AND ".join(where_clauses)

            # Get total count
            count_row = await self._db.fetch_one(
                f"SELECT COUNT(*) as count FROM arkham_anomalies WHERE {where_sql}",
                params
            )
            total = count_row["count"] if count_row else 0

            # Get paginated results
            params["limit"] = limit
            params["offset"] = offset
            rows = await self._db.fetch_all(
                f"""SELECT * FROM arkham_anomalies
                    WHERE {where_sql}
                    ORDER BY detected_at DESC
                    LIMIT :limit OFFSET :offset""",
                params
            )

            anomalies = [self._row_to_anomaly(row) for row in rows]
            return anomalies, total
        else:
            # In-memory filtering
            filtered = list(self._anomalies.values())

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
            result = filtered[offset:offset + limit]

            return result, total

    async def get_anomalies_by_doc(self, doc_id: str) -> List[Anomaly]:
        """
        Get all anomalies for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of anomalies
        """
        if self._db:
            rows = await self._db.fetch_all(
                """SELECT * FROM arkham_anomalies
                   WHERE doc_id = :doc_id
                   ORDER BY detected_at DESC""",
                {"doc_id": doc_id}
            )
            return [self._row_to_anomaly(row) for row in rows]
        else:
            anomalies = [a for a in self._anomalies.values() if a.doc_id == doc_id]
            anomalies.sort(key=lambda a: a.detected_at, reverse=True)
            return anomalies

    async def update_status(
        self,
        anomaly_id: str,
        status: AnomalyStatus,
        reviewed_by: Optional[str] = None,
        notes: str = "",
    ) -> Optional[Anomaly]:
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
        anomaly = await self.get_anomaly(anomaly_id)
        if not anomaly:
            return None

        anomaly.status = status
        anomaly.reviewed_by = reviewed_by
        anomaly.reviewed_at = datetime.utcnow()
        anomaly.updated_at = datetime.utcnow()

        if notes:
            anomaly.notes = notes

        if self._db:
            await self._db.execute(
                """UPDATE arkham_anomalies SET
                    status = :status,
                    reviewed_by = :reviewed_by,
                    reviewed_at = :reviewed_at,
                    updated_at = :updated_at,
                    notes = :notes
                   WHERE id = :id""",
                {
                    "id": anomaly_id,
                    "status": status.value,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": anomaly.reviewed_at.isoformat(),
                    "updated_at": anomaly.updated_at.isoformat(),
                    "notes": notes,
                }
            )
        else:
            self._anomalies[anomaly_id] = anomaly

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
        if self._db:
            await self._db.execute(
                """INSERT INTO arkham_anomaly_notes (id, anomaly_id, author, content, created_at)
                   VALUES (:id, :anomaly_id, :author, :content, :created_at)""",
                {
                    "id": note.id,
                    "anomaly_id": note.anomaly_id,
                    "author": note.author,
                    "content": note.content,
                    "created_at": note.created_at.isoformat(),
                }
            )
        else:
            if note.anomaly_id not in self._notes:
                self._notes[note.anomaly_id] = []
            self._notes[note.anomaly_id].append(note)

        logger.debug(f"Added note to anomaly {note.anomaly_id}")
        return note

    async def get_notes(self, anomaly_id: str) -> List[AnalystNote]:
        """
        Get all notes for an anomaly.

        Args:
            anomaly_id: Anomaly ID

        Returns:
            List of notes
        """
        if self._db:
            rows = await self._db.fetch_all(
                """SELECT * FROM arkham_anomaly_notes
                   WHERE anomaly_id = :anomaly_id
                   ORDER BY created_at DESC""",
                {"anomaly_id": anomaly_id}
            )
            return [self._row_to_note(row) for row in rows]
        else:
            return self._notes.get(anomaly_id, [])

    async def create_pattern(self, pattern: AnomalyPattern) -> AnomalyPattern:
        """
        Store an anomaly pattern.

        Args:
            pattern: Pattern to store

        Returns:
            Stored pattern
        """
        if self._db:
            await self._db.execute(
                """INSERT INTO arkham_anomaly_patterns
                   (id, pattern_type, description, anomaly_ids, doc_ids, frequency, confidence, detected_at, notes)
                   VALUES (:id, :pattern_type, :description, :anomaly_ids, :doc_ids, :frequency, :confidence, :detected_at, :notes)""",
                {
                    "id": pattern.id,
                    "pattern_type": pattern.pattern_type,
                    "description": pattern.description,
                    "anomaly_ids": json.dumps(pattern.anomaly_ids),
                    "doc_ids": json.dumps(pattern.doc_ids),
                    "frequency": pattern.frequency,
                    "confidence": pattern.confidence,
                    "detected_at": pattern.detected_at.isoformat(),
                    "notes": pattern.notes,
                }
            )
        else:
            self._patterns[pattern.id] = pattern

        logger.debug(f"Stored pattern {pattern.id}")
        return pattern

    async def get_pattern(self, pattern_id: str) -> Optional[AnomalyPattern]:
        """
        Get a pattern by ID.

        Args:
            pattern_id: Pattern ID

        Returns:
            Pattern or None if not found
        """
        if self._db:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_anomaly_patterns WHERE id = :id",
                {"id": pattern_id}
            )
            return self._row_to_pattern(row) if row else None
        else:
            return self._patterns.get(pattern_id)

    async def list_patterns(self) -> List[AnomalyPattern]:
        """
        List all patterns.

        Returns:
            List of patterns
        """
        if self._db:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_anomaly_patterns ORDER BY detected_at DESC"
            )
            return [self._row_to_pattern(row) for row in rows]
        else:
            patterns = list(self._patterns.values())
            patterns.sort(key=lambda p: p.detected_at, reverse=True)
            return patterns

    async def get_stats(self) -> AnomalyStats:
        """
        Calculate anomaly statistics.

        Returns:
            Statistics object
        """
        if self._db:
            # Total anomalies
            total_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies"
            )
            total = total_row["count"] if total_row else 0

            # Count by type
            type_rows = await self._db.fetch_all(
                "SELECT anomaly_type, COUNT(*) as count FROM arkham_anomalies GROUP BY anomaly_type"
            )
            by_type = {row["anomaly_type"]: row["count"] for row in type_rows}

            # Count by status
            status_rows = await self._db.fetch_all(
                "SELECT status, COUNT(*) as count FROM arkham_anomalies GROUP BY status"
            )
            by_status = {row["status"]: row["count"] for row in status_rows}

            # Count by severity
            severity_rows = await self._db.fetch_all(
                "SELECT severity, COUNT(*) as count FROM arkham_anomalies GROUP BY severity"
            )
            by_severity = {row["severity"]: row["count"] for row in severity_rows}

            # Recent activity (last 24 hours)
            now = datetime.utcnow()
            last_24h = (now - timedelta(hours=24)).isoformat()

            detected_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies WHERE detected_at >= :since",
                {"since": last_24h}
            )
            detected_last_24h = detected_row["count"] if detected_row else 0

            confirmed_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies WHERE status = 'confirmed' AND reviewed_at >= :since",
                {"since": last_24h}
            )
            confirmed_last_24h = confirmed_row["count"] if confirmed_row else 0

            dismissed_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies WHERE status = 'dismissed' AND reviewed_at >= :since",
                {"since": last_24h}
            )
            dismissed_last_24h = dismissed_row["count"] if dismissed_row else 0

            # Quality metrics
            reviewed_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies WHERE status IN ('confirmed', 'dismissed', 'false_positive')"
            )
            reviewed_count = reviewed_row["count"] if reviewed_row else 0

            fp_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_anomalies WHERE status = 'false_positive'"
            )
            fp_count = fp_row["count"] if fp_row else 0

            false_positive_rate = fp_count / reviewed_count if reviewed_count > 0 else 0.0

            avg_row = await self._db.fetch_one(
                "SELECT AVG(confidence) as avg FROM arkham_anomalies"
            )
            avg_confidence = avg_row["avg"] if avg_row and avg_row["avg"] else 0.0

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
        else:
            # In-memory stats calculation
            all_anomalies = list(self._anomalies.values())
            total = len(all_anomalies)

            by_type = {}
            for anomaly_type in AnomalyType:
                count = len([a for a in all_anomalies if a.anomaly_type == anomaly_type])
                by_type[anomaly_type.value] = count

            by_status = {}
            for status in AnomalyStatus:
                count = len([a for a in all_anomalies if a.status == status])
                by_status[status.value] = count

            by_severity = {}
            for severity in SeverityLevel:
                count = len([a for a in all_anomalies if a.severity == severity])
                by_severity[severity.value] = count

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

    async def get_facets(self) -> Dict[str, Any]:
        """
        Get facet counts for filtering.

        Returns:
            Dictionary of facet counts
        """
        if self._db:
            facets = {
                'types': {},
                'statuses': {},
                'severities': {},
            }

            type_rows = await self._db.fetch_all(
                "SELECT anomaly_type, COUNT(*) as count FROM arkham_anomalies GROUP BY anomaly_type"
            )
            for row in type_rows:
                facets['types'][row["anomaly_type"]] = row["count"]

            status_rows = await self._db.fetch_all(
                "SELECT status, COUNT(*) as count FROM arkham_anomalies GROUP BY status"
            )
            for row in status_rows:
                facets['statuses'][row["status"]] = row["count"]

            severity_rows = await self._db.fetch_all(
                "SELECT severity, COUNT(*) as count FROM arkham_anomalies GROUP BY severity"
            )
            for row in severity_rows:
                facets['severities'][row["severity"]] = row["count"]

            return facets
        else:
            all_anomalies = list(self._anomalies.values())

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

    # === Private Helper Methods ===

    async def _save_anomaly_to_db(self, anomaly: Anomaly, update: bool = False) -> None:
        """Save an anomaly to the database."""
        params = {
            "id": anomaly.id,
            "doc_id": anomaly.doc_id,
            "project_id": getattr(anomaly, 'project_id', None),
            "anomaly_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "status": anomaly.status.value,
            "score": anomaly.score,
            "confidence": anomaly.confidence,
            "title": getattr(anomaly, 'title', None),
            "description": getattr(anomaly, 'description', None),
            "explanation": anomaly.explanation,
            "field_name": anomaly.field_name,
            "expected_range": anomaly.expected_range,
            "actual_value": anomaly.actual_value,
            "evidence": json.dumps(getattr(anomaly, 'evidence', {})),
            "details": json.dumps(anomaly.details),
            "tags": json.dumps(anomaly.tags),
            "metadata": json.dumps(getattr(anomaly, 'metadata', {})),
            "detected_at": anomaly.detected_at.isoformat(),
            "reviewed_at": anomaly.reviewed_at.isoformat() if anomaly.reviewed_at else None,
            "reviewed_by": anomaly.reviewed_by,
            "notes": anomaly.notes,
            "created_at": getattr(anomaly, 'created_at', anomaly.detected_at).isoformat(),
            "updated_at": anomaly.updated_at.isoformat(),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_anomalies SET
                    doc_id = :doc_id,
                    project_id = :project_id,
                    anomaly_type = :anomaly_type,
                    severity = :severity,
                    status = :status,
                    score = :score,
                    confidence = :confidence,
                    title = :title,
                    description = :description,
                    explanation = :explanation,
                    field_name = :field_name,
                    expected_range = :expected_range,
                    actual_value = :actual_value,
                    evidence = :evidence,
                    details = :details,
                    tags = :tags,
                    metadata = :metadata,
                    detected_at = :detected_at,
                    reviewed_at = :reviewed_at,
                    reviewed_by = :reviewed_by,
                    notes = :notes,
                    updated_at = :updated_at
                WHERE id = :id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_anomalies (
                    id, doc_id, project_id, anomaly_type, severity, status,
                    score, confidence, title, description, explanation,
                    field_name, expected_range, actual_value,
                    evidence, details, tags, metadata,
                    detected_at, reviewed_at, reviewed_by, notes,
                    created_at, updated_at
                ) VALUES (
                    :id, :doc_id, :project_id, :anomaly_type, :severity, :status,
                    :score, :confidence, :title, :description, :explanation,
                    :field_name, :expected_range, :actual_value,
                    :evidence, :details, :tags, :metadata,
                    :detected_at, :reviewed_at, :reviewed_by, :notes,
                    :created_at, :updated_at
                )
            """, params)

    def _row_to_anomaly(self, row: Dict[str, Any]) -> Anomaly:
        """Convert database row to Anomaly object."""
        return Anomaly(
            id=row["id"],
            doc_id=row["doc_id"],
            anomaly_type=AnomalyType(row["anomaly_type"]),
            status=AnomalyStatus(row["status"]),
            score=row["score"] or 0.0,
            severity=SeverityLevel(row["severity"]),
            confidence=row["confidence"] or 1.0,
            explanation=row["explanation"] or "",
            details=json.loads(row["details"] or "{}"),
            field_name=row["field_name"],
            expected_range=row["expected_range"],
            actual_value=row["actual_value"],
            detected_at=datetime.fromisoformat(row["detected_at"]) if row["detected_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            reviewed_by=row["reviewed_by"],
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            notes=row["notes"] or "",
            tags=json.loads(row["tags"] or "[]"),
        )

    def _row_to_note(self, row: Dict[str, Any]) -> AnalystNote:
        """Convert database row to AnalystNote object."""
        return AnalystNote(
            id=row["id"],
            anomaly_id=row["anomaly_id"],
            author=row["author"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        )

    def _row_to_pattern(self, row: Dict[str, Any]) -> AnomalyPattern:
        """Convert database row to AnomalyPattern object."""
        return AnomalyPattern(
            id=row["id"],
            pattern_type=row["pattern_type"],
            description=row["description"] or "",
            anomaly_ids=json.loads(row["anomaly_ids"] or "[]"),
            doc_ids=json.loads(row["doc_ids"] or "[]"),
            frequency=row["frequency"] or 0,
            confidence=row["confidence"] or 1.0,
            detected_at=datetime.fromisoformat(row["detected_at"]) if row["detected_at"] else datetime.utcnow(),
            notes=row["notes"] or "",
        )
