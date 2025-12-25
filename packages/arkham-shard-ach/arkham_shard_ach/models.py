"""Data models for the ACH Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ConsistencyRating(Enum):
    """Evidence consistency with hypothesis ratings."""
    HIGHLY_CONSISTENT = "++"
    CONSISTENT = "+"
    NEUTRAL = "N"
    INCONSISTENT = "-"
    HIGHLY_INCONSISTENT = "--"
    NOT_APPLICABLE = "N/A"

    @property
    def score(self) -> float:
        """Convert rating to numeric score for calculations."""
        return {
            "++": 2.0,
            "+": 1.0,
            "N": 0.0,
            "-": -1.0,
            "--": -2.0,
            "N/A": 0.0,
        }[self.value]

    @property
    def weight(self) -> float:
        """Weight for scoring (N/A has zero weight)."""
        return 0.0 if self.value == "N/A" else 1.0


class EvidenceType(Enum):
    """Type of evidence."""
    FACT = "fact"
    TESTIMONY = "testimony"
    DOCUMENT = "document"
    PHYSICAL = "physical"
    CIRCUMSTANTIAL = "circumstantial"
    INFERENCE = "inference"


class MatrixStatus(Enum):
    """Status of an ACH matrix."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Hypothesis:
    """A hypothesis in an ACH matrix."""
    id: str
    matrix_id: str
    title: str
    description: str = ""

    # Position in matrix
    column_index: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None

    # For tracking
    is_lead: bool = False  # Is this the leading hypothesis?
    notes: str = ""


@dataclass
class Evidence:
    """Evidence item in an ACH matrix."""
    id: str
    matrix_id: str
    description: str

    # Evidence details
    source: str = ""
    evidence_type: EvidenceType = EvidenceType.FACT
    credibility: float = 1.0  # 0.0 to 1.0
    relevance: float = 1.0    # 0.0 to 1.0

    # Position in matrix
    row_index: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None

    # Linked documents
    document_ids: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Rating:
    """
    A single cell in the ACH matrix.
    Represents how consistent an evidence item is with a hypothesis.
    """
    matrix_id: str
    evidence_id: str
    hypothesis_id: str
    rating: ConsistencyRating

    # Justification
    reasoning: str = ""
    confidence: float = 1.0  # 0.0 to 1.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None

    @property
    def weighted_score(self) -> float:
        """Calculate weighted score for this rating."""
        return self.rating.score * self.confidence * self.rating.weight


@dataclass
class HypothesisScore:
    """Calculated score for a hypothesis."""
    hypothesis_id: str

    # Basic scores
    consistency_score: float = 0.0      # Sum of all ratings
    inconsistency_count: int = 0        # Count of - and --
    weighted_score: float = 0.0         # Weighted by evidence credibility

    # Normalized scores (0-100)
    normalized_score: float = 0.0

    # Rankings
    rank: int = 0  # 1 = best, higher = worse

    # Metadata
    evidence_count: int = 0
    calculation_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ACHMatrix:
    """An ACH matrix for analyzing competing hypotheses."""
    id: str
    title: str
    description: str = ""

    # Status
    status: MatrixStatus = MatrixStatus.DRAFT

    # Collections (stored in memory during use)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    ratings: list[Rating] = field(default_factory=list)
    scores: list[HypothesisScore] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None

    # Analysis context
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        """Get a hypothesis by ID."""
        for h in self.hypotheses:
            if h.id == hypothesis_id:
                return h
        return None

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        """Get evidence by ID."""
        for e in self.evidence:
            if e.id == evidence_id:
                return e
        return None

    def get_rating(self, evidence_id: str, hypothesis_id: str) -> Rating | None:
        """Get rating for specific evidence-hypothesis pair."""
        for r in self.ratings:
            if r.evidence_id == evidence_id and r.hypothesis_id == hypothesis_id:
                return r
        return None

    def get_score(self, hypothesis_id: str) -> HypothesisScore | None:
        """Get score for a hypothesis."""
        for s in self.scores:
            if s.hypothesis_id == hypothesis_id:
                return s
        return None

    @property
    def leading_hypothesis(self) -> Hypothesis | None:
        """Get the hypothesis with the best score."""
        if not self.scores:
            return None

        best_score = min(self.scores, key=lambda s: s.rank)
        return self.get_hypothesis(best_score.hypothesis_id)


@dataclass
class DevilsAdvocateChallenge:
    """A devil's advocate challenge to the leading hypothesis."""
    matrix_id: str
    hypothesis_id: str

    # Challenge content
    challenge_text: str
    alternative_interpretation: str
    weaknesses_identified: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)

    # Suggested evidence to seek
    recommended_investigations: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    model_used: str | None = None


@dataclass
class MatrixExport:
    """Export format for an ACH matrix."""
    matrix: ACHMatrix
    format: str  # "json", "csv", "html", "markdown"
    content: str | dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.utcnow)
