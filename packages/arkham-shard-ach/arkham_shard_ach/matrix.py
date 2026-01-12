"""ACH Matrix operations and management."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from .models import (
    ACHMatrix,
    Hypothesis,
    Evidence,
    Rating,
    MatrixStatus,
    ConsistencyRating,
)

if TYPE_CHECKING:
    from .shard import ACHShard

logger = logging.getLogger(__name__)


class MatrixManager:
    """
    Manages ACH matrices with in-memory caching and database persistence.

    Uses an in-memory cache for performance while persisting changes to
    the database through the shard's persistence methods. When a matrix
    is requested, it's first checked in the cache. If not found, it's
    loaded from the database and cached.
    """

    def __init__(self, shard: Optional["ACHShard"] = None):
        """
        Initialize the MatrixManager.

        Args:
            shard: Optional reference to the ACHShard for database persistence.
                   If not provided, persistence is disabled and matrices are
                   stored only in memory.
        """
        self._matrices: Dict[str, ACHMatrix] = {}
        self._shard: Optional["ACHShard"] = shard

    def set_shard(self, shard: "ACHShard") -> None:
        """
        Set the shard reference for database persistence.

        Args:
            shard: The ACHShard instance to use for persistence
        """
        self._shard = shard
        logger.debug("MatrixManager: shard reference set for persistence")

    def _run_async(self, coro):
        """
        Run an async coroutine from sync context.

        Uses the existing event loop if available, otherwise creates one.
        This allows the MatrixManager's sync methods to call the shard's
        async persistence methods.

        IMPORTANT: When called from an async context, this schedules the task
        and adds it to a background task set. The task will complete but may
        not finish before the current request ends. For critical saves,
        use the async save methods directly from async code.
        """
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - schedule task and ensure it completes
            task = loop.create_task(coro)
            # Add callback to log errors since we can't await here
            def log_result(t):
                try:
                    t.result()
                except Exception as e:
                    logger.error(f"Async persistence failed: {e}")
            task.add_done_callback(log_result)
            return task
        except RuntimeError:
            # No running loop, create one (sync context)
            return asyncio.run(coro)

    async def save_matrix_async(self, matrix: ACHMatrix) -> None:
        """Async method to save a matrix - use from async code for guaranteed persistence."""
        if self._shard:
            await self._shard._save_matrix(matrix)

    async def save_hypothesis_async(self, hypothesis: Hypothesis) -> None:
        """Async method to save a hypothesis - use from async code for guaranteed persistence."""
        if self._shard:
            await self._shard._save_hypothesis(hypothesis)

    async def save_evidence_async(self, evidence: Evidence) -> None:
        """Async method to save evidence - use from async code for guaranteed persistence."""
        if self._shard:
            await self._shard._save_evidence(evidence)

    async def save_rating_async(self, rating: Rating) -> None:
        """Async method to save a rating - use from async code for guaranteed persistence."""
        if self._shard:
            await self._shard._upsert_rating(rating)

    def create_matrix(
        self,
        title: str,
        description: str = "",
        created_by: str | None = None,
        project_id: str | None = None,
    ) -> ACHMatrix:
        """Create a new ACH matrix."""
        matrix_id = str(uuid.uuid4())

        matrix = ACHMatrix(
            id=matrix_id,
            title=title,
            description=description,
            status=MatrixStatus.DRAFT,
            created_by=created_by,
            project_id=project_id,
        )

        self._matrices[matrix_id] = matrix

        # Persist to database
        if self._shard:
            try:
                self._run_async(self._shard._save_matrix(matrix))
            except Exception as e:
                logger.error(f"Failed to persist matrix {matrix_id}: {e}")

        return matrix

    def get_matrix(self, matrix_id: str) -> ACHMatrix | None:
        """Get a matrix by ID, loading from database if not in cache."""
        # Check cache first
        if matrix_id in self._matrices:
            return self._matrices[matrix_id]

        # Try to load from database
        if self._shard:
            try:
                result = self._run_async(self._shard._load_matrix(matrix_id))
                # Handle both Task and direct result
                if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                    # In async context, we can't block - return None for now
                    # The async API should be used instead
                    logger.debug(f"Matrix {matrix_id} not in cache, async load required")
                    return None
                if result:
                    self._matrices[matrix_id] = result
                    return result
            except Exception as e:
                logger.error(f"Failed to load matrix {matrix_id} from database: {e}")

        return None

    async def get_matrix_async(self, matrix_id: str) -> ACHMatrix | None:
        """Get a matrix by ID asynchronously, loading from database if not in cache."""
        # Check cache first
        if matrix_id in self._matrices:
            return self._matrices[matrix_id]

        # Try to load from database
        if self._shard:
            try:
                matrix = await self._shard._load_matrix(matrix_id)
                if matrix:
                    self._matrices[matrix_id] = matrix
                    return matrix
            except Exception as e:
                logger.error(f"Failed to load matrix {matrix_id} from database: {e}")

        return None

    def update_matrix(
        self,
        matrix_id: str,
        title: str | None = None,
        description: str | None = None,
        status: MatrixStatus | None = None,
        notes: str | None = None,
    ) -> ACHMatrix | None:
        """Update matrix metadata."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        if title is not None:
            matrix.title = title
        if description is not None:
            matrix.description = description
        if status is not None:
            matrix.status = status
        if notes is not None:
            matrix.notes = notes

        matrix.updated_at = datetime.utcnow()

        # Persist to database
        if self._shard:
            try:
                self._run_async(self._shard._save_matrix(matrix))
            except Exception as e:
                logger.error(f"Failed to persist matrix update {matrix_id}: {e}")

        return matrix

    def delete_matrix(self, matrix_id: str) -> bool:
        """Delete a matrix from cache and database."""
        # Delete from database first
        if self._shard:
            try:
                self._run_async(self._shard._delete_matrix_from_db(matrix_id))
            except Exception as e:
                logger.error(f"Failed to delete matrix {matrix_id} from database: {e}")

        # Delete from cache
        if matrix_id in self._matrices:
            del self._matrices[matrix_id]
            return True
        return False

    def list_matrices(
        self,
        project_id: str | None = None,
        status: MatrixStatus | None = None,
    ) -> list[ACHMatrix]:
        """List matrices with optional filtering (from cache only)."""
        matrices = list(self._matrices.values())

        if project_id:
            matrices = [m for m in matrices if m.project_id == project_id]

        if status:
            matrices = [m for m in matrices if m.status == status]

        return sorted(matrices, key=lambda m: m.created_at, reverse=True)

    async def list_matrices_async(
        self,
        project_id: str | None = None,
        status: MatrixStatus | None = None,
    ) -> list[ACHMatrix]:
        """List matrices from database with optional filtering."""
        if self._shard:
            try:
                status_str = status.value if status else None
                matrices = await self._shard._load_all_matrices(
                    project_id=project_id,
                    status=status_str
                )
                # Update cache with loaded matrices
                for matrix in matrices:
                    self._matrices[matrix.id] = matrix
                return matrices
            except Exception as e:
                logger.error(f"Failed to load matrices from database: {e}")

        # Fallback to cache
        return self.list_matrices(project_id=project_id, status=status)

    def add_hypothesis(
        self,
        matrix_id: str,
        title: str,
        description: str = "",
        author: str | None = None,
    ) -> Hypothesis | None:
        """Add a hypothesis to a matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        hypothesis_id = str(uuid.uuid4())
        column_index = len(matrix.hypotheses)

        hypothesis = Hypothesis(
            id=hypothesis_id,
            matrix_id=matrix_id,
            title=title,
            description=description,
            column_index=column_index,
            author=author,
        )

        matrix.hypotheses.append(hypothesis)
        matrix.updated_at = datetime.utcnow()

        # Persist to database
        if self._shard:
            try:
                self._run_async(self._shard._save_hypothesis(hypothesis))
            except Exception as e:
                logger.error(f"Failed to persist hypothesis {hypothesis_id}: {e}")

        return hypothesis

    def remove_hypothesis(self, matrix_id: str, hypothesis_id: str) -> bool:
        """Remove a hypothesis from a matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return False

        # Remove hypothesis
        matrix.hypotheses = [h for h in matrix.hypotheses if h.id != hypothesis_id]

        # Remove associated ratings
        matrix.ratings = [
            r for r in matrix.ratings if r.hypothesis_id != hypothesis_id
        ]

        # Remove associated scores
        matrix.scores = [s for s in matrix.scores if s.hypothesis_id != hypothesis_id]

        # Reindex columns
        for i, h in enumerate(matrix.hypotheses):
            h.column_index = i

        matrix.updated_at = datetime.utcnow()

        # Persist deletion to database
        if self._shard:
            try:
                # Delete hypothesis and its ratings
                self._run_async(self._shard._delete_hypothesis(hypothesis_id))
                # Update column indexes for remaining hypotheses
                self._run_async(self._shard._update_hypothesis_indexes(matrix_id, matrix.hypotheses))
            except Exception as e:
                logger.error(f"Failed to persist hypothesis deletion {hypothesis_id}: {e}")

        return True

    def add_evidence(
        self,
        matrix_id: str,
        description: str,
        source: str = "",
        evidence_type: str = "fact",
        credibility: float = 1.0,
        relevance: float = 1.0,
        author: str | None = None,
        document_ids: list[str] | None = None,
    ) -> Evidence | None:
        """Add evidence to a matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        from .models import EvidenceType

        evidence_id = str(uuid.uuid4())
        row_index = len(matrix.evidence)

        # Parse evidence type
        try:
            ev_type = EvidenceType[evidence_type.upper()]
        except (KeyError, AttributeError):
            ev_type = EvidenceType.FACT

        evidence = Evidence(
            id=evidence_id,
            matrix_id=matrix_id,
            description=description,
            source=source,
            evidence_type=ev_type,
            credibility=max(0.0, min(1.0, credibility)),
            relevance=max(0.0, min(1.0, relevance)),
            row_index=row_index,
            author=author,
            document_ids=document_ids or [],
        )

        matrix.evidence.append(evidence)
        matrix.updated_at = datetime.utcnow()

        # Persist to database
        if self._shard:
            try:
                self._run_async(self._shard._save_evidence(evidence))
            except Exception as e:
                logger.error(f"Failed to persist evidence {evidence_id}: {e}")

        return evidence

    def remove_evidence(self, matrix_id: str, evidence_id: str) -> bool:
        """Remove evidence from a matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return False

        # Remove evidence
        matrix.evidence = [e for e in matrix.evidence if e.id != evidence_id]

        # Remove associated ratings
        matrix.ratings = [r for r in matrix.ratings if r.evidence_id != evidence_id]

        # Reindex rows
        for i, e in enumerate(matrix.evidence):
            e.row_index = i

        matrix.updated_at = datetime.utcnow()

        # Persist deletion to database
        if self._shard:
            try:
                # Delete evidence and its ratings
                self._run_async(self._shard._delete_evidence(evidence_id))
                # Update row indexes for remaining evidence
                self._run_async(self._shard._update_evidence_indexes(matrix_id, matrix.evidence))
            except Exception as e:
                logger.error(f"Failed to persist evidence deletion {evidence_id}: {e}")

        return True

    def set_rating(
        self,
        matrix_id: str,
        evidence_id: str,
        hypothesis_id: str,
        rating: ConsistencyRating,
        reasoning: str = "",
        confidence: float = 1.0,
        author: str | None = None,
    ) -> Rating | None:
        """Set or update a rating in the matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        # Verify evidence and hypothesis exist
        if not matrix.get_evidence(evidence_id):
            return None
        if not matrix.get_hypothesis(hypothesis_id):
            return None

        # Check if rating exists
        existing = matrix.get_rating(evidence_id, hypothesis_id)

        if existing:
            # Update existing rating
            existing.rating = rating
            existing.reasoning = reasoning
            existing.confidence = max(0.0, min(1.0, confidence))
            existing.updated_at = datetime.utcnow()
            if author:
                existing.author = author
            rating_obj = existing
        else:
            # Create new rating
            rating_obj = Rating(
                matrix_id=matrix_id,
                evidence_id=evidence_id,
                hypothesis_id=hypothesis_id,
                rating=rating,
                reasoning=reasoning,
                confidence=max(0.0, min(1.0, confidence)),
                author=author,
            )
            matrix.ratings.append(rating_obj)

        matrix.updated_at = datetime.utcnow()

        # Persist to database
        if self._shard:
            try:
                self._run_async(self._shard._upsert_rating(rating_obj))
            except Exception as e:
                logger.error(f"Failed to persist rating: {e}")

        return rating_obj

    def get_matrix_data(self, matrix_id: str) -> dict | None:
        """
        Get matrix in a structured format for API responses.

        Returns:
            Dictionary with matrix data organized by hypotheses and evidence.
        """
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        return {
            "id": matrix.id,
            "title": matrix.title,
            "description": matrix.description,
            "status": matrix.status.value,
            "created_at": matrix.created_at.isoformat(),
            "updated_at": matrix.updated_at.isoformat(),
            "created_by": matrix.created_by,
            "project_id": matrix.project_id,
            "tags": matrix.tags,
            "notes": matrix.notes,
            "hypotheses": [
                {
                    "id": h.id,
                    "title": h.title,
                    "description": h.description,
                    "column_index": h.column_index,
                    "is_lead": h.is_lead,
                    "notes": h.notes,
                }
                for h in sorted(matrix.hypotheses, key=lambda x: x.column_index)
            ],
            "evidence": [
                {
                    "id": e.id,
                    "description": e.description,
                    "source": e.source,
                    "type": e.evidence_type.value,
                    "credibility": e.credibility,
                    "relevance": e.relevance,
                    "row_index": e.row_index,
                    "document_ids": e.document_ids,
                    "notes": e.notes,
                }
                for e in sorted(matrix.evidence, key=lambda x: x.row_index)
            ],
            "ratings": [
                {
                    "evidence_id": r.evidence_id,
                    "hypothesis_id": r.hypothesis_id,
                    "rating": r.rating.value,
                    "reasoning": r.reasoning,
                    "confidence": r.confidence,
                }
                for r in matrix.ratings
            ],
            "scores": [
                {
                    "hypothesis_id": s.hypothesis_id,
                    "consistency_score": s.consistency_score,
                    "inconsistency_count": s.inconsistency_count,
                    "weighted_score": s.weighted_score,
                    "normalized_score": s.normalized_score,
                    "rank": s.rank,
                    "evidence_count": s.evidence_count,
                }
                for s in sorted(matrix.scores, key=lambda x: x.rank)
            ],
            "linked_document_ids": matrix.linked_document_ids,
        }
