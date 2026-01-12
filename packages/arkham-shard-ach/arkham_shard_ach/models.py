"""Data models for the ACH Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EvidenceRelevance(str, Enum):
    """How extracted evidence relates to a hypothesis."""
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"


class ExtractionMethod(str, Enum):
    """How evidence was added to the matrix."""
    MANUAL = "manual"
    CORPUS = "corpus"
    AI_SUGGESTED = "ai_suggested"


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
    column_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None
    is_lead: bool = False
    notes: str = ""


@dataclass
class Evidence:
    """Evidence item in an ACH matrix."""
    id: str
    matrix_id: str
    description: str
    source: str = ""
    evidence_type: EvidenceType = EvidenceType.FACT
    credibility: float = 1.0
    relevance: float = 1.0
    row_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None
    document_ids: list[str] = field(default_factory=list)
    notes: str = ""
    # Corpus extraction fields
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    source_page_number: int | None = None
    source_quote: str | None = None
    extraction_method: str = "manual"
    similarity_score: float | None = None


@dataclass
class ExtractedEvidence:
    """Evidence extracted from corpus search (before user acceptance)."""
    quote: str
    source_document_id: str
    source_document_name: str
    source_chunk_id: str
    page_number: int | None
    relevance: EvidenceRelevance
    explanation: str
    hypothesis_id: str
    similarity_score: float
    verified: bool = False
    possible_duplicate: str | None = None


@dataclass
class SearchScope:
    """Scope for corpus search."""
    project_id: str | None = None
    document_ids: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    mime_types: list[str] | None = None
    exclude_documents: list[str] | None = None


@dataclass
class CorpusSearchConfig:
    """Configuration for corpus search."""
    chunk_limit: int = 30
    min_similarity: float = 0.5
    max_chunks_per_document: int = 5
    dedupe_threshold: float = 0.9
    batch_size: int = 10


@dataclass
class Rating:
    """A single cell in the ACH matrix."""
    matrix_id: str
    evidence_id: str
    hypothesis_id: str
    rating: ConsistencyRating
    reasoning: str = ""
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str | None = None

    @property
    def weighted_score(self) -> float:
        return self.rating.score * self.confidence * self.rating.weight


@dataclass
class HypothesisScore:
    """Calculated score for a hypothesis."""
    hypothesis_id: str
    consistency_score: float = 0.0
    inconsistency_count: int = 0
    weighted_score: float = 0.0
    normalized_score: float = 0.0
    rank: int = 0
    evidence_count: int = 0
    calculation_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ACHMatrix:
    """An ACH matrix for analyzing competing hypotheses."""
    id: str
    title: str
    description: str = ""
    status: MatrixStatus = MatrixStatus.DRAFT
    hypotheses: list[Hypothesis] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    ratings: list[Rating] = field(default_factory=list)
    scores: list[HypothesisScore] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    # Manually linked documents for corpus search scope
    linked_document_ids: list[str] = field(default_factory=list)

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        for h in self.hypotheses:
            if h.id == hypothesis_id:
                return h
        return None

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        for e in self.evidence:
            if e.id == evidence_id:
                return e
        return None

    def get_rating(self, evidence_id: str, hypothesis_id: str) -> Rating | None:
        for r in self.ratings:
            if r.evidence_id == evidence_id and r.hypothesis_id == hypothesis_id:
                return r
        return None

    def get_score(self, hypothesis_id: str) -> HypothesisScore | None:
        for s in self.scores:
            if s.hypothesis_id == hypothesis_id:
                return s
        return None

    @property
    def leading_hypothesis(self) -> Hypothesis | None:
        if not self.scores:
            return None
        best_score = min(self.scores, key=lambda s: s.rank)
        return self.get_hypothesis(best_score.hypothesis_id)


@dataclass
class DevilsAdvocateChallenge:
    """A devil's advocate challenge to the leading hypothesis."""
    matrix_id: str
    hypothesis_id: str
    challenge_text: str
    alternative_interpretation: str
    weaknesses_identified: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    recommended_investigations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    model_used: str | None = None


@dataclass
class MatrixExport:
    """Export format for an ACH matrix."""
    matrix: ACHMatrix
    format: str
    content: str | bytes | dict[str, Any]  # bytes for PDF binary content
    generated_at: datetime = field(default_factory=datetime.utcnow)


# ============================================
# Premortem Analysis Models
# ============================================

class FailureModeType(str, Enum):
    """Type of failure mode identified in premortem analysis."""
    MISINTERPRETATION = "misinterpretation"
    MISSED_EVIDENCE = "missed_evidence"
    FAILED_ASSUMPTION = "failed_assumption"
    DECEPTION = "deception"
    ALTERNATIVE_EXPLANATION = "alternative_explanation"


class PremortemConversionType(str, Enum):
    """What a failure mode can be converted to."""
    HYPOTHESIS = "hypothesis"
    MILESTONE = "milestone"
    ASSUMPTION = "assumption"


@dataclass
class FailureMode:
    """A single failure mode identified during premortem analysis."""
    id: str
    premortem_id: str
    failure_type: FailureModeType
    description: str
    likelihood: str = "medium"  # low, medium, high
    early_warning_indicator: str = ""
    mitigation_action: str = ""
    converted_to: PremortemConversionType | None = None
    converted_id: str | None = None  # ID of hypothesis/milestone/assumption created
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PremortemAnalysis:
    """A premortem analysis result for a hypothesis."""
    id: str
    matrix_id: str
    hypothesis_id: str
    hypothesis_title: str
    scenario_description: str  # "It's 6 months from now..."
    failure_modes: list[FailureMode] = field(default_factory=list)
    overall_vulnerability: str = "medium"  # low, medium, high
    key_risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    model_used: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None


# ============================================
# Cone of Plausibility Models
# ============================================

class ScenarioStatus(str, Enum):
    """Status of a scenario in the cone."""
    ACTIVE = "active"
    OCCURRED = "occurred"
    RULED_OUT = "ruled_out"
    CONVERTED = "converted"  # Converted to ACH hypothesis


@dataclass
class ScenarioIndicator:
    """An indicator to watch for a scenario."""
    id: str
    scenario_id: str
    description: str
    is_triggered: bool = False
    triggered_at: datetime | None = None
    notes: str = ""


@dataclass
class ScenarioDriver:
    """A key driver/variable that causes scenario branching."""
    id: str
    tree_id: str
    name: str
    description: str = ""
    current_state: str = ""
    possible_states: list[str] = field(default_factory=list)


@dataclass
class ScenarioNode:
    """A single scenario node in the cone of plausibility tree."""
    id: str
    tree_id: str
    parent_id: str | None  # None for root "NOW" node
    title: str
    description: str = ""
    probability: float = 0.0  # 0.0 to 1.0
    timeframe: str = ""  # e.g., "3-6 months"
    key_drivers: list[str] = field(default_factory=list)  # Driver IDs
    trigger_conditions: list[str] = field(default_factory=list)
    indicators: list[ScenarioIndicator] = field(default_factory=list)
    status: ScenarioStatus = ScenarioStatus.ACTIVE
    converted_hypothesis_id: str | None = None
    depth: int = 0  # 0 = NOW, 1 = first branch, etc.
    branch_order: int = 0  # Order among siblings
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class ScenarioTree:
    """A cone of plausibility tree for scenario planning."""
    id: str
    matrix_id: str
    title: str
    description: str = ""
    situation_summary: str = ""  # Current situation description
    root_node_id: str | None = None
    nodes: list[ScenarioNode] = field(default_factory=list)
    drivers: list[ScenarioDriver] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None
    model_used: str | None = None

    def get_node(self, node_id: str) -> ScenarioNode | None:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_children(self, parent_id: str | None) -> list[ScenarioNode]:
        """Get child nodes of a parent."""
        return sorted(
            [n for n in self.nodes if n.parent_id == parent_id],
            key=lambda n: n.branch_order
        )

    def get_root(self) -> ScenarioNode | None:
        """Get the root 'NOW' node."""
        if self.root_node_id:
            return self.get_node(self.root_node_id)
        # Fallback: find node with no parent
        for node in self.nodes:
            if node.parent_id is None:
                return node
        return None

    @property
    def total_scenarios(self) -> int:
        """Count total scenarios (excluding root)."""
        return len([n for n in self.nodes if n.parent_id is not None])

    @property
    def active_scenarios(self) -> list[ScenarioNode]:
        """Get all active scenarios."""
        return [n for n in self.nodes if n.status == ScenarioStatus.ACTIVE]
