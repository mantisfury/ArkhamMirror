"""Database operations for contradiction storage."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from .models import (
    Contradiction,
    ContradictionChain,
    ContradictionStatus,
    Severity,
    ContradictionType,
)

logger = logging.getLogger(__name__)


class ContradictionStore:
    """
    Storage layer for contradictions.

    Uses the Frame's database service for persistence.
    Falls back to in-memory storage when database is unavailable.
    """

    def __init__(self, db_service):
        """
        Initialize the store.

        Args:
            db_service: Frame database service
        """
        self._db = db_service
        # In-memory fallback when database is unavailable
        self._contradictions: dict[str, Contradiction] = {}
        self._chains: dict[str, ContradictionChain] = {}

    def _use_db(self) -> bool:
        """Check if database is available."""
        return self._db is not None

    def _row_to_contradiction(self, row: dict) -> Contradiction:
        """Convert a database row to a Contradiction object."""
        # Parse JSON fields
        analyst_notes = json.loads(row.get("analyst_notes", "[]") or "[]")
        related_contradictions = json.loads(row.get("related_contradictions", "[]") or "[]")
        tags = json.loads(row.get("tags", "[]") or "[]")
        metadata = json.loads(row.get("metadata", "{}") or "{}")

        # Parse datetime fields
        created_at = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow()
        updated_at = datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow()
        confirmed_at = datetime.fromisoformat(row["confirmed_at"]) if row.get("confirmed_at") else None

        return Contradiction(
            id=row["id"],
            doc_a_id=row["doc_a_id"],
            doc_b_id=row["doc_b_id"],
            claim_a=row["claim_a"],
            claim_b=row["claim_b"],
            claim_a_location=row.get("claim_a_location", ""),
            claim_b_location=row.get("claim_b_location", ""),
            contradiction_type=ContradictionType(row.get("contradiction_type", "direct")),
            severity=Severity(row.get("severity", "medium")),
            status=ContradictionStatus(row.get("status", "detected")),
            explanation=row.get("explanation", ""),
            confidence_score=float(row.get("confidence_score", 0.0)),
            detected_by=row.get("detected_by", "system"),
            analyst_notes=analyst_notes,
            chain_id=row.get("chain_id"),
            related_contradictions=related_contradictions,
            tags=tags,
            metadata=metadata,
            confirmed_by=row.get("confirmed_by"),
            confirmed_at=confirmed_at,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _row_to_chain(self, row: dict) -> ContradictionChain:
        """Convert a database row to a ContradictionChain object."""
        contradiction_ids = json.loads(row.get("contradiction_ids", "[]") or "[]")
        created_at = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow()
        updated_at = datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow()

        return ContradictionChain(
            id=row["id"],
            contradiction_ids=contradiction_ids,
            description=row.get("description", ""),
            severity=Severity(row.get("severity", "medium")),
            created_at=created_at,
            updated_at=updated_at,
        )

    # --- CRUD Operations ---

    async def create(self, contradiction: Contradiction) -> Contradiction:
        """
        Save a new contradiction.

        Args:
            contradiction: Contradiction to save

        Returns:
            Saved contradiction
        """
        if not self._use_db():
            self._contradictions[contradiction.id] = contradiction
            logger.info(f"Created contradiction (in-memory): {contradiction.id}")
            return contradiction

        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """
            INSERT INTO arkham_contradictions.contradictions
            (id, doc_a_id, doc_b_id, claim_a, claim_b, claim_a_location, claim_b_location,
             contradiction_type, severity, status, explanation, confidence_score, detected_by,
             analyst_notes, chain_id, related_contradictions, tags, metadata,
             confirmed_by, confirmed_at, created_at, updated_at)
            VALUES (:id, :doc_a_id, :doc_b_id, :claim_a, :claim_b, :claim_a_location, :claim_b_location,
                    :contradiction_type, :severity, :status, :explanation, :confidence_score, :detected_by,
                    :analyst_notes, :chain_id, :related_contradictions, :tags, :metadata,
                    :confirmed_by, :confirmed_at, :created_at, :updated_at)
            """,
            {
                "id": contradiction.id,
                "doc_a_id": contradiction.doc_a_id,
                "doc_b_id": contradiction.doc_b_id,
                "claim_a": contradiction.claim_a,
                "claim_b": contradiction.claim_b,
                "claim_a_location": contradiction.claim_a_location,
                "claim_b_location": contradiction.claim_b_location,
                "contradiction_type": contradiction.contradiction_type.value,
                "severity": contradiction.severity.value,
                "status": contradiction.status.value,
                "explanation": contradiction.explanation,
                "confidence_score": contradiction.confidence_score,
                "detected_by": contradiction.detected_by,
                "analyst_notes": json.dumps(contradiction.analyst_notes),
                "chain_id": contradiction.chain_id,
                "related_contradictions": json.dumps(contradiction.related_contradictions),
                "tags": json.dumps(contradiction.tags),
                "metadata": json.dumps(contradiction.metadata),
                "confirmed_by": contradiction.confirmed_by,
                "confirmed_at": contradiction.confirmed_at.isoformat() if contradiction.confirmed_at else None,
                "created_at": contradiction.created_at.isoformat() if contradiction.created_at else now,
                "updated_at": now,
            }
        )
        logger.info(f"Created contradiction: {contradiction.id}")
        return contradiction

    async def get(self, contradiction_id: str) -> Contradiction | None:
        """
        Get a contradiction by ID.

        Args:
            contradiction_id: Contradiction ID

        Returns:
            Contradiction or None if not found
        """
        if not self._use_db():
            return self._contradictions.get(contradiction_id)

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_contradictions.contradictions WHERE id = :id",
            {"id": contradiction_id}
        )

        if not row:
            return None

        return self._row_to_contradiction(dict(row))

    async def update(self, contradiction: Contradiction) -> Contradiction:
        """
        Update a contradiction.

        Args:
            contradiction: Contradiction to update

        Returns:
            Updated contradiction
        """
        contradiction.updated_at = datetime.utcnow()

        if not self._use_db():
            self._contradictions[contradiction.id] = contradiction
            logger.info(f"Updated contradiction (in-memory): {contradiction.id}")
            return contradiction

        await self._db.execute(
            """
            UPDATE arkham_contradictions.contradictions SET
                doc_a_id = :doc_a_id,
                doc_b_id = :doc_b_id,
                claim_a = :claim_a,
                claim_b = :claim_b,
                claim_a_location = :claim_a_location,
                claim_b_location = :claim_b_location,
                contradiction_type = :contradiction_type,
                severity = :severity,
                status = :status,
                explanation = :explanation,
                confidence_score = :confidence_score,
                detected_by = :detected_by,
                analyst_notes = :analyst_notes,
                chain_id = :chain_id,
                related_contradictions = :related_contradictions,
                tags = :tags,
                metadata = :metadata,
                confirmed_by = :confirmed_by,
                confirmed_at = :confirmed_at,
                updated_at = :updated_at
            WHERE id = :id
            """,
            {
                "id": contradiction.id,
                "doc_a_id": contradiction.doc_a_id,
                "doc_b_id": contradiction.doc_b_id,
                "claim_a": contradiction.claim_a,
                "claim_b": contradiction.claim_b,
                "claim_a_location": contradiction.claim_a_location,
                "claim_b_location": contradiction.claim_b_location,
                "contradiction_type": contradiction.contradiction_type.value,
                "severity": contradiction.severity.value,
                "status": contradiction.status.value,
                "explanation": contradiction.explanation,
                "confidence_score": contradiction.confidence_score,
                "detected_by": contradiction.detected_by,
                "analyst_notes": json.dumps(contradiction.analyst_notes),
                "chain_id": contradiction.chain_id,
                "related_contradictions": json.dumps(contradiction.related_contradictions),
                "tags": json.dumps(contradiction.tags),
                "metadata": json.dumps(contradiction.metadata),
                "confirmed_by": contradiction.confirmed_by,
                "confirmed_at": contradiction.confirmed_at.isoformat() if contradiction.confirmed_at else None,
                "updated_at": contradiction.updated_at.isoformat(),
            }
        )
        logger.info(f"Updated contradiction: {contradiction.id}")
        return contradiction

    async def delete(self, contradiction_id: str) -> bool:
        """
        Delete a contradiction.

        Args:
            contradiction_id: Contradiction ID

        Returns:
            True if deleted, False if not found
        """
        if not self._use_db():
            if contradiction_id in self._contradictions:
                del self._contradictions[contradiction_id]
                logger.info(f"Deleted contradiction (in-memory): {contradiction_id}")
                return True
            return False

        # Check if exists first
        existing = await self.get(contradiction_id)
        if not existing:
            return False

        await self._db.execute(
            "DELETE FROM arkham_contradictions.contradictions WHERE id = :id",
            {"id": contradiction_id}
        )
        logger.info(f"Deleted contradiction: {contradiction_id}")
        return True

    # --- Query Methods ---

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 50,
        status: ContradictionStatus | None = None,
        severity: Severity | None = None,
    ) -> tuple[list[Contradiction], int]:
        """
        List contradictions with optional filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            status: Filter by status
            severity: Filter by severity

        Returns:
            Tuple of (contradictions list, total count)
        """
        if not self._use_db():
            # In-memory filtering
            contradictions = list(self._contradictions.values())

            if status:
                contradictions = [c for c in contradictions if c.status == status]

            if severity:
                contradictions = [c for c in contradictions if c.severity == severity]

            total = len(contradictions)

            # Sort by created_at descending
            contradictions.sort(key=lambda c: c.created_at, reverse=True)

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            contradictions = contradictions[start:end]

            return contradictions, total

        # Build query with filters
        where_clauses = []
        params: dict[str, Any] = {}

        if status:
            where_clauses.append("status = :status")
            params["status"] = status.value

        if severity:
            where_clauses.append("severity = :severity")
            params["severity"] = severity.value

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions WHERE {where_sql}",
            params
        )
        total = count_row["cnt"] if count_row else 0

        # Get paginated results
        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        rows = await self._db.fetch_all(
            f"""
            SELECT * FROM arkham_contradictions.contradictions
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """,
            params
        )

        contradictions = [self._row_to_contradiction(dict(row)) for row in rows]
        return contradictions, total

    async def get_by_document(
        self, document_id: str, include_related: bool = False
    ) -> list[Contradiction]:
        """
        Get contradictions involving a specific document.

        Args:
            document_id: Document ID
            include_related: Include contradictions in same chain

        Returns:
            List of contradictions
        """
        if not self._use_db():
            contradictions = [
                c for c in self._contradictions.values()
                if c.doc_a_id == document_id or c.doc_b_id == document_id
            ]

            if include_related:
                # Include contradictions in same chains
                chains = set()
                for c in contradictions:
                    if c.chain_id:
                        chains.add(c.chain_id)

                for chain_id in chains:
                    chain_contradictions = [
                        c for c in self._contradictions.values()
                        if c.chain_id == chain_id
                    ]
                    contradictions.extend(chain_contradictions)

                # Remove duplicates
                seen = set()
                contradictions = [
                    c for c in contradictions
                    if not (c.id in seen or seen.add(c.id))
                ]

            return contradictions

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_contradictions.contradictions
            WHERE doc_a_id = :doc_id OR doc_b_id = :doc_id
            ORDER BY created_at DESC
            """,
            {"doc_id": document_id}
        )

        contradictions = [self._row_to_contradiction(dict(row)) for row in rows]

        if include_related:
            # Get chain IDs
            chain_ids = set(c.chain_id for c in contradictions if c.chain_id)

            for chain_id in chain_ids:
                chain_rows = await self._db.fetch_all(
                    """
                    SELECT * FROM arkham_contradictions.contradictions
                    WHERE chain_id = :chain_id
                    """,
                    {"chain_id": chain_id}
                )
                for row in chain_rows:
                    c = self._row_to_contradiction(dict(row))
                    if c.id not in {existing.id for existing in contradictions}:
                        contradictions.append(c)

        return contradictions

    async def get_by_status(self, status: ContradictionStatus) -> list[Contradiction]:
        """
        Get contradictions by status.

        Args:
            status: Status to filter by

        Returns:
            List of contradictions
        """
        if not self._use_db():
            return [c for c in self._contradictions.values() if c.status == status]

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_contradictions.contradictions WHERE status = :status ORDER BY created_at DESC",
            {"status": status.value}
        )
        return [self._row_to_contradiction(dict(row)) for row in rows]

    async def get_by_severity(self, severity: Severity) -> list[Contradiction]:
        """
        Get contradictions by severity.

        Args:
            severity: Severity to filter by

        Returns:
            List of contradictions
        """
        if not self._use_db():
            return [c for c in self._contradictions.values() if c.severity == severity]

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_contradictions.contradictions WHERE severity = :severity ORDER BY created_at DESC",
            {"severity": severity.value}
        )
        return [self._row_to_contradiction(dict(row)) for row in rows]

    async def search(
        self,
        query: str | None = None,
        document_ids: list[str] | None = None,
        status: ContradictionStatus | None = None,
        severity: Severity | None = None,
        min_confidence: float | None = None,
    ) -> list[Contradiction]:
        """
        Search contradictions with multiple filters.

        Args:
            query: Text search in claims/explanations
            document_ids: Filter by document IDs
            status: Filter by status
            severity: Filter by severity
            min_confidence: Minimum confidence score

        Returns:
            List of matching contradictions
        """
        if not self._use_db():
            contradictions = list(self._contradictions.values())

            if query:
                query_lower = query.lower()
                contradictions = [
                    c for c in contradictions
                    if query_lower in c.claim_a.lower()
                    or query_lower in c.claim_b.lower()
                    or query_lower in c.explanation.lower()
                ]

            if document_ids:
                contradictions = [
                    c for c in contradictions
                    if c.doc_a_id in document_ids or c.doc_b_id in document_ids
                ]

            if status:
                contradictions = [c for c in contradictions if c.status == status]

            if severity:
                contradictions = [c for c in contradictions if c.severity == severity]

            if min_confidence is not None:
                contradictions = [
                    c for c in contradictions if c.confidence_score >= min_confidence
                ]

            return contradictions

        # Build query with filters
        where_clauses = []
        params: dict[str, Any] = {}

        if query:
            where_clauses.append(
                "(LOWER(claim_a) LIKE :query OR LOWER(claim_b) LIKE :query OR LOWER(explanation) LIKE :query)"
            )
            params["query"] = f"%{query.lower()}%"

        if status:
            where_clauses.append("status = :status")
            params["status"] = status.value

        if severity:
            where_clauses.append("severity = :severity")
            params["severity"] = severity.value

        if min_confidence is not None:
            where_clauses.append("confidence_score >= :min_confidence")
            params["min_confidence"] = min_confidence

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        rows = await self._db.fetch_all(
            f"""
            SELECT * FROM arkham_contradictions.contradictions
            WHERE {where_sql}
            ORDER BY created_at DESC
            """,
            params
        )

        contradictions = [self._row_to_contradiction(dict(row)) for row in rows]

        # Filter by document_ids in memory (more complex SQL)
        if document_ids:
            contradictions = [
                c for c in contradictions
                if c.doc_a_id in document_ids or c.doc_b_id in document_ids
            ]

        return contradictions

    # --- Statistics ---

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get contradiction statistics.

        Returns:
            Statistics dictionary
        """
        if not self._use_db():
            contradictions = list(self._contradictions.values())

            # Count by status
            by_status = {}
            for status in ContradictionStatus:
                count = sum(1 for c in contradictions if c.status == status)
                by_status[status.value] = count

            # Count by severity
            by_severity = {}
            for severity in Severity:
                count = sum(1 for c in contradictions if c.severity == severity)
                by_severity[severity.value] = count

            # Count by type
            by_type = {}
            for ctype in ContradictionType:
                count = sum(1 for c in contradictions if c.contradiction_type == ctype)
                by_type[ctype.value] = count

            # Count chains
            chains_count = len(set(c.chain_id for c in contradictions if c.chain_id))

            # Recent contradictions (last 24 hours)
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_count = sum(1 for c in contradictions if c.created_at >= cutoff)

            return {
                "total_contradictions": len(contradictions),
                "by_status": by_status,
                "by_severity": by_severity,
                "by_type": by_type,
                "chains_detected": chains_count,
                "recent_count": recent_count,
            }

        # Database statistics
        total_row = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions"
        )
        total = total_row["cnt"] if total_row else 0

        # Count by status
        by_status = {}
        for status in ContradictionStatus:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions WHERE status = :status",
                {"status": status.value}
            )
            by_status[status.value] = row["cnt"] if row else 0

        # Count by severity
        by_severity = {}
        for severity in Severity:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions WHERE severity = :severity",
                {"severity": severity.value}
            )
            by_severity[severity.value] = row["cnt"] if row else 0

        # Count by type
        by_type = {}
        for ctype in ContradictionType:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions WHERE contradiction_type = :ctype",
                {"ctype": ctype.value}
            )
            by_type[ctype.value] = row["cnt"] if row else 0

        # Count chains
        chain_row = await self._db.fetch_one(
            "SELECT COUNT(DISTINCT chain_id) as cnt FROM arkham_contradictions.contradictions WHERE chain_id IS NOT NULL"
        )
        chains_count = chain_row["cnt"] if chain_row else 0

        # Recent contradictions (last 24 hours)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        recent_row = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM arkham_contradictions.contradictions WHERE created_at >= :cutoff",
            {"cutoff": cutoff}
        )
        recent_count = recent_row["cnt"] if recent_row else 0

        return {
            "total_contradictions": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "by_type": by_type,
            "chains_detected": chains_count,
            "recent_count": recent_count,
        }

    # --- Chain Operations ---

    async def create_chain(self, chain: ContradictionChain) -> ContradictionChain:
        """
        Create a contradiction chain.

        Args:
            chain: Chain to create

        Returns:
            Created chain
        """
        if not self._use_db():
            self._chains[chain.id] = chain

            # Update contradictions with chain ID
            for contradiction_id in chain.contradiction_ids:
                contradiction = self._contradictions.get(contradiction_id)
                if contradiction:
                    contradiction.chain_id = chain.id
                    contradiction.updated_at = datetime.utcnow()

            logger.info(f"Created chain (in-memory): {chain.id} with {len(chain.contradiction_ids)} contradictions")
            return chain

        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """
            INSERT INTO arkham_contradictions.chains
            (id, contradiction_ids, description, severity, created_at, updated_at)
            VALUES (:id, :contradiction_ids, :description, :severity, :created_at, :updated_at)
            """,
            {
                "id": chain.id,
                "contradiction_ids": json.dumps(chain.contradiction_ids),
                "description": chain.description,
                "severity": chain.severity.value,
                "created_at": chain.created_at.isoformat() if chain.created_at else now,
                "updated_at": now,
            }
        )

        # Update contradictions with chain ID
        for contradiction_id in chain.contradiction_ids:
            await self._db.execute(
                """
                UPDATE arkham_contradictions.contradictions
                SET chain_id = :chain_id, updated_at = :updated_at
                WHERE id = :id
                """,
                {"chain_id": chain.id, "id": contradiction_id, "updated_at": now}
            )

        logger.info(f"Created chain: {chain.id} with {len(chain.contradiction_ids)} contradictions")
        return chain

    async def get_chain(self, chain_id: str) -> ContradictionChain | None:
        """
        Get a chain by ID.

        Args:
            chain_id: Chain ID

        Returns:
            Chain or None if not found
        """
        if not self._use_db():
            return self._chains.get(chain_id)

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_contradictions.chains WHERE id = :id",
            {"id": chain_id}
        )

        if not row:
            return None

        return self._row_to_chain(dict(row))

    async def get_chain_contradictions(self, chain_id: str) -> list[Contradiction]:
        """
        Get all contradictions in a chain.

        Args:
            chain_id: Chain ID

        Returns:
            List of contradictions
        """
        if not self._use_db():
            return [
                c for c in self._contradictions.values()
                if c.chain_id == chain_id
            ]

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_contradictions.contradictions WHERE chain_id = :chain_id ORDER BY created_at DESC",
            {"chain_id": chain_id}
        )
        return [self._row_to_contradiction(dict(row)) for row in rows]

    async def list_chains(self) -> list[ContradictionChain]:
        """
        List all contradiction chains.

        Returns:
            List of chains
        """
        if not self._use_db():
            return list(self._chains.values())

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_contradictions.chains ORDER BY created_at DESC"
        )
        return [self._row_to_chain(dict(row)) for row in rows]

    # --- Analyst Workflow ---

    async def add_note(
        self, contradiction_id: str, note: str, analyst_id: str | None = None
    ) -> Contradiction | None:
        """
        Add analyst note to contradiction.

        Args:
            contradiction_id: Contradiction ID
            note: Note text
            analyst_id: Analyst identifier

        Returns:
            Updated contradiction or None if not found
        """
        contradiction = await self.get(contradiction_id)
        if not contradiction:
            return None

        note_entry = f"[{datetime.utcnow().isoformat()}]"
        if analyst_id:
            note_entry += f" [{analyst_id}]"
        note_entry += f" {note}"

        contradiction.analyst_notes.append(note_entry)
        contradiction.updated_at = datetime.utcnow()

        if not self._use_db():
            logger.info(f"Added note to contradiction (in-memory): {contradiction_id}")
            return contradiction

        await self._db.execute(
            """
            UPDATE arkham_contradictions.contradictions
            SET analyst_notes = :analyst_notes, updated_at = :updated_at
            WHERE id = :id
            """,
            {
                "id": contradiction_id,
                "analyst_notes": json.dumps(contradiction.analyst_notes),
                "updated_at": contradiction.updated_at.isoformat(),
            }
        )

        logger.info(f"Added note to contradiction: {contradiction_id}")
        return contradiction

    async def update_status(
        self,
        contradiction_id: str,
        status: ContradictionStatus,
        analyst_id: str | None = None,
    ) -> Contradiction | None:
        """
        Update contradiction status.

        Args:
            contradiction_id: Contradiction ID
            status: New status
            analyst_id: Analyst identifier

        Returns:
            Updated contradiction or None if not found
        """
        contradiction = await self.get(contradiction_id)
        if not contradiction:
            return None

        old_status = contradiction.status
        contradiction.status = status
        contradiction.updated_at = datetime.utcnow()

        if status == ContradictionStatus.CONFIRMED:
            contradiction.confirmed_by = analyst_id
            contradiction.confirmed_at = datetime.utcnow()

        if not self._use_db():
            logger.info(
                f"Updated contradiction {contradiction_id} status (in-memory): {old_status.value} -> {status.value}"
            )
            return contradiction

        await self._db.execute(
            """
            UPDATE arkham_contradictions.contradictions
            SET status = :status, confirmed_by = :confirmed_by, confirmed_at = :confirmed_at, updated_at = :updated_at
            WHERE id = :id
            """,
            {
                "id": contradiction_id,
                "status": status.value,
                "confirmed_by": contradiction.confirmed_by,
                "confirmed_at": contradiction.confirmed_at.isoformat() if contradiction.confirmed_at else None,
                "updated_at": contradiction.updated_at.isoformat(),
            }
        )

        logger.info(
            f"Updated contradiction {contradiction_id} status: {old_status.value} -> {status.value}"
        )
        return contradiction

    # --- Bulk Operations ---

    async def bulk_create(self, contradictions: list[Contradiction]) -> int:
        """
        Bulk create contradictions.

        Args:
            contradictions: List of contradictions

        Returns:
            Number of contradictions created
        """
        for contradiction in contradictions:
            await self.create(contradiction)

        logger.info(f"Bulk created {len(contradictions)} contradictions")
        return len(contradictions)

    async def bulk_update_status(
        self, contradiction_ids: list[str], status: ContradictionStatus
    ) -> int:
        """
        Bulk update contradiction statuses.

        Args:
            contradiction_ids: List of contradiction IDs
            status: New status

        Returns:
            Number of contradictions updated
        """
        count = 0
        for contradiction_id in contradiction_ids:
            result = await self.update_status(contradiction_id, status)
            if result:
                count += 1

        logger.info(f"Bulk updated {count} contradictions to status: {status.value}")
        return count
