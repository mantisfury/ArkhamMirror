"""
Pydantic models for ACH (Analysis of Competing Hypotheses) feature.
Used for data transfer between service layer and UI state.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ACHRatingModel(BaseModel):
    """A single rating in the ACH matrix."""

    id: int
    hypothesis_id: int
    evidence_id: int
    rating: str  # CC, C, N, I, II, or ""
    notes: Optional[str] = None


class ACHEvidenceModel(BaseModel):
    """An evidence item in an ACH analysis."""

    id: int
    label: str
    description: str
    display_order: int = 0
    evidence_type: str = "fact"  # fact, testimony, document, assumption, argument
    reliability: str = "medium"  # high, medium, low
    source: Optional[str] = None
    source_document_id: Optional[int] = None
    diagnosticity_score: float = 0.0
    is_critical: bool = False
    created_at: Optional[str] = None

    # Ratings for this evidence across all hypotheses (keyed by hypothesis_id)
    ratings: Dict[int, str] = {}


class ACHHypothesisModel(BaseModel):
    """A hypothesis in an ACH analysis."""

    id: int
    label: str
    description: str
    display_order: int = 0
    color: str = "#3b82f6"
    inconsistency_score: float = 0.0
    future_indicators: Optional[str] = None
    indicator_timeframe: Optional[str] = None
    created_at: Optional[str] = None


class ACHMilestoneModel(BaseModel):
    """A future indicator milestone."""

    id: int
    hypothesis_id: int
    hypothesis_label: str
    description: str
    expected_by: Optional[str] = None
    observed: int = 0  # 0=pending, 1=observed, -1=contradicted
    observed_date: Optional[str] = None
    observation_notes: Optional[str] = None
    created_at: Optional[str] = None


class ACHAnalysisModel(BaseModel):
    """A complete ACH analysis session."""

    id: int
    project_id: Optional[int] = None
    title: str
    focus_question: str
    description: Optional[str] = None
    status: str = "draft"  # draft, in_progress, complete, archived
    sensitivity_notes: Optional[str] = None
    key_assumptions: Optional[List[str]] = None
    current_step: int = 1
    steps_completed: List[int] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Nested data (populated when loading full analysis)
    hypotheses: List[ACHHypothesisModel] = []
    evidence: List[ACHEvidenceModel] = []
    hypothesis_count: int = 0
    evidence_count: int = 0


class ACHAnalysisSummary(BaseModel):
    """Summary view of an ACH analysis for list display."""

    id: int
    title: str
    focus_question: str
    status: str
    current_step: int
    hypothesis_count: int
    evidence_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ACHMatrixCell(BaseModel):
    """A cell in the ACH matrix display."""

    evidence_id: int
    hypothesis_id: int
    rating: str
    notes: Optional[str] = None


class ACHScoreResult(BaseModel):
    """Scoring result for a hypothesis."""

    hypothesis_id: int
    label: str
    description: str
    color: str
    inconsistency_score: float
    rank: int  # 1 = best (lowest inconsistency)


class ACHDiagnosticityResult(BaseModel):
    """Diagnosticity analysis result for evidence."""

    evidence_id: int
    label: str
    description: str
    diagnosticity_score: float
    is_high_diagnostic: bool
    is_low_diagnostic: bool
    rating_variance: float


class ACHConsistencyCheck(BaseModel):
    """Result of a consistency check."""

    check_type: str  # null_hypothesis, adversarial, incomplete_ratings
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ACHExportData(BaseModel):
    """Data structure for exporting an ACH analysis."""

    analysis: ACHAnalysisModel
    matrix: List[Dict[str, Any]]  # Evidence rows with hypothesis ratings
    scores: List[ACHScoreResult]
    diagnosticity: List[ACHDiagnosticityResult]
    consistency_checks: List[ACHConsistencyCheck]
    milestones: List[ACHMilestoneModel]
