"""Database operations for contradiction storage."""

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
    """

    def __init__(self, db_service):
        """
        Initialize the store.

        Args:
            db_service: Frame database service
        """
        self.db = db_service
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure contradiction tables exist in database."""
        # This would typically be handled by migrations
        # For now, we'll use in-memory storage as fallback
        self._contradictions: dict[str, Contradiction] = {}
        self._chains: dict[str, ContradictionChain] = {}

    # --- CRUD Operations ---

    def create(self, contradiction: Contradiction) -> Contradiction:
        """
        Save a new contradiction.

        Args:
            contradiction: Contradiction to save

        Returns:
            Saved contradiction
        """
        self._contradictions[contradiction.id] = contradiction
        logger.info(f"Created contradiction: {contradiction.id}")
        return contradiction

    def get(self, contradiction_id: str) -> Contradiction | None:
        """
        Get a contradiction by ID.

        Args:
            contradiction_id: Contradiction ID

        Returns:
            Contradiction or None if not found
        """
        return self._contradictions.get(contradiction_id)

    def update(self, contradiction: Contradiction) -> Contradiction:
        """
        Update a contradiction.

        Args:
            contradiction: Contradiction to update

        Returns:
            Updated contradiction
        """
        contradiction.updated_at = datetime.utcnow()
        self._contradictions[contradiction.id] = contradiction
        logger.info(f"Updated contradiction: {contradiction.id}")
        return contradiction

    def delete(self, contradiction_id: str) -> bool:
        """
        Delete a contradiction.

        Args:
            contradiction_id: Contradiction ID

        Returns:
            True if deleted, False if not found
        """
        if contradiction_id in self._contradictions:
            del self._contradictions[contradiction_id]
            logger.info(f"Deleted contradiction: {contradiction_id}")
            return True
        return False

    # --- Query Methods ---

    def list_all(
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
        # Filter
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

    def get_by_document(
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

    def get_by_status(self, status: ContradictionStatus) -> list[Contradiction]:
        """
        Get contradictions by status.

        Args:
            status: Status to filter by

        Returns:
            List of contradictions
        """
        return [c for c in self._contradictions.values() if c.status == status]

    def get_by_severity(self, severity: Severity) -> list[Contradiction]:
        """
        Get contradictions by severity.

        Args:
            severity: Severity to filter by

        Returns:
            List of contradictions
        """
        return [c for c in self._contradictions.values() if c.severity == severity]

    def search(
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

    # --- Statistics ---

    def get_statistics(self) -> dict[str, Any]:
        """
        Get contradiction statistics.

        Returns:
            Statistics dictionary
        """
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

    # --- Chain Operations ---

    def create_chain(self, chain: ContradictionChain) -> ContradictionChain:
        """
        Create a contradiction chain.

        Args:
            chain: Chain to create

        Returns:
            Created chain
        """
        self._chains[chain.id] = chain

        # Update contradictions with chain ID
        for contradiction_id in chain.contradiction_ids:
            contradiction = self._contradictions.get(contradiction_id)
            if contradiction:
                contradiction.chain_id = chain.id
                contradiction.updated_at = datetime.utcnow()

        logger.info(f"Created chain: {chain.id} with {len(chain.contradiction_ids)} contradictions")
        return chain

    def get_chain(self, chain_id: str) -> ContradictionChain | None:
        """
        Get a chain by ID.

        Args:
            chain_id: Chain ID

        Returns:
            Chain or None if not found
        """
        return self._chains.get(chain_id)

    def get_chain_contradictions(self, chain_id: str) -> list[Contradiction]:
        """
        Get all contradictions in a chain.

        Args:
            chain_id: Chain ID

        Returns:
            List of contradictions
        """
        return [
            c for c in self._contradictions.values()
            if c.chain_id == chain_id
        ]

    def list_chains(self) -> list[ContradictionChain]:
        """
        List all contradiction chains.

        Returns:
            List of chains
        """
        return list(self._chains.values())

    # --- Analyst Workflow ---

    def add_note(
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
        contradiction = self._contradictions.get(contradiction_id)
        if not contradiction:
            return None

        note_entry = f"[{datetime.utcnow().isoformat()}]"
        if analyst_id:
            note_entry += f" [{analyst_id}]"
        note_entry += f" {note}"

        contradiction.analyst_notes.append(note_entry)
        contradiction.updated_at = datetime.utcnow()

        logger.info(f"Added note to contradiction: {contradiction_id}")
        return contradiction

    def update_status(
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
        contradiction = self._contradictions.get(contradiction_id)
        if not contradiction:
            return None

        old_status = contradiction.status
        contradiction.status = status
        contradiction.updated_at = datetime.utcnow()

        if status == ContradictionStatus.CONFIRMED:
            contradiction.confirmed_by = analyst_id
            contradiction.confirmed_at = datetime.utcnow()

        logger.info(
            f"Updated contradiction {contradiction_id} status: {old_status.value} -> {status.value}"
        )
        return contradiction

    # --- Bulk Operations ---

    def bulk_create(self, contradictions: list[Contradiction]) -> int:
        """
        Bulk create contradictions.

        Args:
            contradictions: List of contradictions

        Returns:
            Number of contradictions created
        """
        for contradiction in contradictions:
            self._contradictions[contradiction.id] = contradiction

        logger.info(f"Bulk created {len(contradictions)} contradictions")
        return len(contradictions)

    def bulk_update_status(
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
            contradiction = self._contradictions.get(contradiction_id)
            if contradiction:
                contradiction.status = status
                contradiction.updated_at = datetime.utcnow()
                count += 1

        logger.info(f"Bulk updated {count} contradictions to status: {status.value}")
        return count
