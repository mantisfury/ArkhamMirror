"""ACH Matrix operations and management."""

import uuid
from datetime import datetime
from typing import Dict

from .models import (
    ACHMatrix,
    Hypothesis,
    Evidence,
    Rating,
    MatrixStatus,
    ConsistencyRating,
)


class MatrixManager:
    """
    Manages ACH matrices in memory.

    In a production implementation, this would interface with a database
    service from the Frame. For now, it's in-memory storage.
    """

    def __init__(self):
        self._matrices: Dict[str, ACHMatrix] = {}

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
        return matrix

    def get_matrix(self, matrix_id: str) -> ACHMatrix | None:
        """Get a matrix by ID."""
        return self._matrices.get(matrix_id)

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
        return matrix

    def delete_matrix(self, matrix_id: str) -> bool:
        """Delete a matrix."""
        if matrix_id in self._matrices:
            del self._matrices[matrix_id]
            return True
        return False

    def list_matrices(
        self,
        project_id: str | None = None,
        status: MatrixStatus | None = None,
    ) -> list[ACHMatrix]:
        """List matrices with optional filtering."""
        matrices = list(self._matrices.values())

        if project_id:
            matrices = [m for m in matrices if m.project_id == project_id]

        if status:
            matrices = [m for m in matrices if m.status == status]

        return sorted(matrices, key=lambda m: m.created_at, reverse=True)

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
        }
