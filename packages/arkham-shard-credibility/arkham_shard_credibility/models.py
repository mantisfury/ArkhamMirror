"""
Credibility Shard - Data Models

Pydantic models and dataclasses for credibility assessment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class SourceType(str, Enum):
    """Type of source being assessed for credibility."""
    DOCUMENT = "document"           # Document credibility
    ENTITY = "entity"               # Entity reliability
    WEBSITE = "website"             # Website trustworthiness
    PUBLICATION = "publication"     # Publication reputation
    PERSON = "person"               # Individual credibility
    ORGANIZATION = "organization"   # Organizational reliability


class AssessmentMethod(str, Enum):
    """Method used to assess credibility."""
    MANUAL = "manual"               # Human analyst assessment
    AUTOMATED = "automated"         # LLM-generated assessment
    HYBRID = "hybrid"               # Combined human + AI assessment


class CredibilityLevel(str, Enum):
    """Credibility score classification."""
    UNRELIABLE = "unreliable"       # 0-20: Not trustworthy
    LOW = "low"                     # 21-40: Limited credibility
    MEDIUM = "medium"               # 41-60: Moderate credibility
    HIGH = "high"                   # 61-80: High credibility
    VERIFIED = "verified"           # 81-100: Verified/authoritative


class FactorType(str, Enum):
    """Standard credibility factor types."""
    SOURCE_RELIABILITY = "source_reliability"       # Track record of accuracy
    EVIDENCE_QUALITY = "evidence_quality"           # Quality of supporting evidence
    BIAS_ASSESSMENT = "bias_assessment"             # Political/ideological bias
    EXPERTISE = "expertise"                         # Subject matter expertise
    TIMELINESS = "timeliness"                       # Recency and relevance
    INDEPENDENCE = "independence"                   # Editorial independence
    TRANSPARENCY = "transparency"                   # Source disclosure
    CUSTOM = "custom"                               # User-defined factor


# === Dataclasses ===

@dataclass
class CredibilityFactor:
    """
    A factor contributing to credibility score.

    Each factor has a type, weight (importance), and score.
    """
    factor_type: str                    # Factor type (from FactorType or custom)
    weight: float                       # Importance (0.0-1.0)
    score: int                          # Factor score (0-100)
    notes: Optional[str] = None         # Explanation/justification


@dataclass
class CredibilityAssessment:
    """
    A credibility assessment for a source.

    Assessments evaluate the trustworthiness and reliability of sources
    using configurable factors and produce a 0-100 credibility score.
    """
    id: str
    source_type: SourceType             # Type of source
    source_id: str                      # ID of the source
    score: int                          # Overall credibility score (0-100)
    confidence: float                   # Assessment confidence (0.0-1.0)

    # Factors contributing to score
    factors: List[CredibilityFactor] = field(default_factory=list)

    # Assessment metadata
    assessed_by: AssessmentMethod = AssessmentMethod.MANUAL
    assessor_id: Optional[str] = None   # ID of analyst or system
    notes: Optional[str] = None         # Assessment notes

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def level(self) -> CredibilityLevel:
        """Get credibility level based on score."""
        if self.score <= 20:
            return CredibilityLevel.UNRELIABLE
        elif self.score <= 40:
            return CredibilityLevel.LOW
        elif self.score <= 60:
            return CredibilityLevel.MEDIUM
        elif self.score <= 80:
            return CredibilityLevel.HIGH
        else:
            return CredibilityLevel.VERIFIED


@dataclass
class SourceCredibility:
    """
    Aggregate credibility for a source across all assessments.
    """
    source_type: SourceType
    source_id: str
    avg_score: float                    # Average of all assessments
    assessment_count: int               # Number of assessments
    latest_score: int                   # Most recent assessment score
    latest_confidence: float            # Most recent assessment confidence
    latest_assessment_id: str           # ID of latest assessment
    latest_assessed_at: datetime

    @property
    def level(self) -> CredibilityLevel:
        """Get credibility level based on average score."""
        score = int(self.avg_score)
        if score <= 20:
            return CredibilityLevel.UNRELIABLE
        elif score <= 40:
            return CredibilityLevel.LOW
        elif score <= 60:
            return CredibilityLevel.MEDIUM
        elif score <= 80:
            return CredibilityLevel.HIGH
        else:
            return CredibilityLevel.VERIFIED


@dataclass
class CredibilityCalculation:
    """
    Result of a credibility calculation.
    """
    source_type: SourceType
    source_id: str
    calculated_score: int               # Calculated credibility score
    confidence: float                   # Calculation confidence
    factors: List[CredibilityFactor]    # Factors used in calculation
    method: AssessmentMethod            # Calculation method
    processing_time_ms: float           # Processing time
    notes: Optional[str] = None         # Calculation notes
    errors: List[str] = field(default_factory=list)


@dataclass
class CredibilityStatistics:
    """
    Statistics about credibility assessments.
    """
    total_assessments: int = 0
    by_source_type: Dict[str, int] = field(default_factory=dict)
    by_level: Dict[str, int] = field(default_factory=dict)
    by_method: Dict[str, int] = field(default_factory=dict)

    avg_score: float = 0.0
    avg_confidence: float = 0.0

    unreliable_count: int = 0           # Score <= 20
    low_count: int = 0                  # Score 21-40
    medium_count: int = 0               # Score 41-60
    high_count: int = 0                 # Score 61-80
    verified_count: int = 0             # Score 81-100

    sources_assessed: int = 0           # Unique sources
    avg_assessments_per_source: float = 0.0


@dataclass
class CredibilityFilter:
    """
    Filter criteria for credibility queries.
    """
    source_type: Optional[SourceType] = None
    source_id: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    level: Optional[CredibilityLevel] = None
    assessed_by: Optional[AssessmentMethod] = None
    assessor_id: Optional[str] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


@dataclass
class StandardFactor:
    """
    Definition of a standard credibility factor.
    """
    factor_type: str
    default_weight: float
    description: str
    scoring_guidance: str


# Standard factor definitions
STANDARD_FACTORS: List[StandardFactor] = [
    StandardFactor(
        factor_type=FactorType.SOURCE_RELIABILITY.value,
        default_weight=0.25,
        description="Track record of accuracy and reliability",
        scoring_guidance="100: Flawless track record, 80: Very reliable, 60: Generally reliable, 40: Some issues, 20: Many errors, 0: Consistently unreliable"
    ),
    StandardFactor(
        factor_type=FactorType.EVIDENCE_QUALITY.value,
        default_weight=0.20,
        description="Quality and verifiability of evidence",
        scoring_guidance="100: Primary sources with full documentation, 80: Strong secondary sources, 60: Mixed sources, 40: Limited documentation, 20: Weak evidence, 0: No evidence"
    ),
    StandardFactor(
        factor_type=FactorType.BIAS_ASSESSMENT.value,
        default_weight=0.15,
        description="Political, ideological, or financial bias",
        scoring_guidance="100: No detected bias, 80: Minimal bias, 60: Moderate bias disclosed, 40: Significant bias, 20: Heavy bias, 0: Extreme bias"
    ),
    StandardFactor(
        factor_type=FactorType.EXPERTISE.value,
        default_weight=0.15,
        description="Subject matter expertise and credentials",
        scoring_guidance="100: Recognized expert, 80: Strong credentials, 60: Adequate expertise, 40: Limited expertise, 20: Questionable expertise, 0: No expertise"
    ),
    StandardFactor(
        factor_type=FactorType.TIMELINESS.value,
        default_weight=0.10,
        description="Recency and temporal relevance",
        scoring_guidance="100: Current/up-to-date, 80: Recent, 60: Somewhat dated, 40: Old information, 20: Outdated, 0: Obsolete"
    ),
    StandardFactor(
        factor_type=FactorType.INDEPENDENCE.value,
        default_weight=0.10,
        description="Editorial independence and autonomy",
        scoring_guidance="100: Fully independent, 80: Mostly independent, 60: Some influence, 40: Significant influence, 20: Heavily influenced, 0: Controlled"
    ),
    StandardFactor(
        factor_type=FactorType.TRANSPARENCY.value,
        default_weight=0.05,
        description="Source disclosure and methodology transparency",
        scoring_guidance="100: Fully transparent, 80: Very transparent, 60: Adequate transparency, 40: Limited transparency, 20: Opaque, 0: No transparency"
    ),
]


@dataclass
class CredibilityHistory:
    """
    Historical credibility assessments for a source.
    """
    source_type: SourceType
    source_id: str
    assessments: List[CredibilityAssessment]
    score_trend: str = "stable"         # "improving", "declining", "stable", "volatile"
    avg_score: float = 0.0
    min_score: int = 0
    max_score: int = 100


# =============================================================================
# DECEPTION DETECTION (MOM/POP/MOSES/EVE Framework)
# =============================================================================

class DeceptionChecklistType(str, Enum):
    """The four deception detection checklists."""
    MOM = "mom"      # Motive, Opportunity, Means
    POP = "pop"      # Past Opposition Practices
    MOSES = "moses"  # Manipulability of Sources
    EVE = "eve"      # Evaluation of Evidence


class DeceptionRisk(str, Enum):
    """Overall deception risk level."""
    MINIMAL = "minimal"       # 0-20: Very unlikely to be deception
    LOW = "low"              # 21-40: Some minor indicators
    MODERATE = "moderate"    # 41-60: Notable deception indicators
    HIGH = "high"            # 61-80: Significant deception risk
    CRITICAL = "critical"    # 81-100: Strong indicators of deception


class IndicatorStrength(str, Enum):
    """Strength of a deception indicator."""
    NONE = "none"          # No indicator present
    WEAK = "weak"          # Minor/circumstantial
    MODERATE = "moderate"  # Notable indicator
    STRONG = "strong"      # Clear indicator
    CONCLUSIVE = "conclusive"  # Definitive indicator


@dataclass
class DeceptionIndicator:
    """
    A single indicator from a deception checklist.

    Each checklist (MOM, POP, MOSES, EVE) contains multiple indicators.
    """
    id: str
    checklist: DeceptionChecklistType  # Which checklist this belongs to
    question: str                       # The diagnostic question
    answer: Optional[str] = None        # Analyst's answer/assessment
    strength: IndicatorStrength = IndicatorStrength.NONE
    confidence: float = 0.0             # How confident in this assessment (0-1)
    evidence_ids: List[str] = field(default_factory=list)  # Supporting evidence
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "checklist": self.checklist.value,
            "question": self.question,
            "answer": self.answer,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
            "notes": self.notes,
        }


@dataclass
class DeceptionChecklist:
    """
    A completed deception checklist assessment.

    Contains all indicators for one checklist type (MOM, POP, MOSES, or EVE).
    """
    checklist_type: DeceptionChecklistType
    indicators: List[DeceptionIndicator] = field(default_factory=list)
    overall_score: int = 0                  # 0-100 score for this checklist
    risk_level: str = "minimal"             # Derived risk level
    summary: Optional[str] = None           # LLM-generated or manual summary
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checklist_type": self.checklist_type.value,
            "indicators": [i.to_dict() for i in self.indicators],
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def calculate_score(self) -> int:
        """Calculate checklist score from indicators."""
        if not self.indicators:
            return 0

        strength_scores = {
            IndicatorStrength.NONE: 0,
            IndicatorStrength.WEAK: 25,
            IndicatorStrength.MODERATE: 50,
            IndicatorStrength.STRONG: 75,
            IndicatorStrength.CONCLUSIVE: 100,
        }

        total = sum(
            strength_scores.get(ind.strength, 0) * ind.confidence
            for ind in self.indicators
        )
        max_possible = len(self.indicators) * 100
        return int((total / max_possible) * 100) if max_possible > 0 else 0


@dataclass
class DeceptionAssessment:
    """
    A complete deception detection assessment for a source.

    Contains all four checklists (MOM, POP, MOSES, EVE) and produces
    an overall deception risk score.
    """
    id: str
    source_type: SourceType
    source_id: str
    source_name: Optional[str] = None       # Human-readable source name

    # The four checklists
    mom_checklist: Optional[DeceptionChecklist] = None
    pop_checklist: Optional[DeceptionChecklist] = None
    moses_checklist: Optional[DeceptionChecklist] = None
    eve_checklist: Optional[DeceptionChecklist] = None

    # Aggregate scores
    overall_score: int = 0              # 0-100 deception risk score
    risk_level: DeceptionRisk = DeceptionRisk.MINIMAL
    confidence: float = 0.0             # Overall assessment confidence

    # Integration with main credibility
    linked_assessment_id: Optional[str] = None  # Link to CredibilityAssessment
    affects_credibility: bool = True    # Whether to factor into credibility score
    credibility_weight: float = 0.3     # Weight in credibility calculation

    # Assessment metadata
    assessed_by: AssessmentMethod = AssessmentMethod.MANUAL
    assessor_id: Optional[str] = None
    summary: Optional[str] = None       # Overall assessment summary
    red_flags: List[str] = field(default_factory=list)  # Key concerns

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def completed_checklists(self) -> int:
        """Count how many checklists have been completed."""
        count = 0
        if self.mom_checklist and self.mom_checklist.completed_at:
            count += 1
        if self.pop_checklist and self.pop_checklist.completed_at:
            count += 1
        if self.moses_checklist and self.moses_checklist.completed_at:
            count += 1
        if self.eve_checklist and self.eve_checklist.completed_at:
            count += 1
        return count

    def calculate_overall_score(self) -> int:
        """Calculate overall deception risk from completed checklists."""
        scores = []
        weights = {
            'mom': 0.35,    # MOM most heavily weighted
            'eve': 0.25,    # Evidence evaluation second
            'moses': 0.25,  # Manipulability third
            'pop': 0.15,    # Past practices least (often unknown)
        }

        if self.mom_checklist and self.mom_checklist.completed_at:
            scores.append(('mom', self.mom_checklist.overall_score))
        if self.pop_checklist and self.pop_checklist.completed_at:
            scores.append(('pop', self.pop_checklist.overall_score))
        if self.moses_checklist and self.moses_checklist.completed_at:
            scores.append(('moses', self.moses_checklist.overall_score))
        if self.eve_checklist and self.eve_checklist.completed_at:
            scores.append(('eve', self.eve_checklist.overall_score))

        if not scores:
            return 0

        # Normalize weights for completed checklists
        total_weight = sum(weights[s[0]] for s in scores)
        weighted_sum = sum(weights[s[0]] * s[1] for s in scores)

        return int(weighted_sum / total_weight) if total_weight > 0 else 0

    def get_risk_level(self, score: int) -> DeceptionRisk:
        """Get risk level from score."""
        if score <= 20:
            return DeceptionRisk.MINIMAL
        elif score <= 40:
            return DeceptionRisk.LOW
        elif score <= 60:
            return DeceptionRisk.MODERATE
        elif score <= 80:
            return DeceptionRisk.HIGH
        else:
            return DeceptionRisk.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "mom_checklist": self.mom_checklist.to_dict() if self.mom_checklist else None,
            "pop_checklist": self.pop_checklist.to_dict() if self.pop_checklist else None,
            "moses_checklist": self.moses_checklist.to_dict() if self.moses_checklist else None,
            "eve_checklist": self.eve_checklist.to_dict() if self.eve_checklist else None,
            "overall_score": self.overall_score,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "completed_checklists": self.completed_checklists,
            "linked_assessment_id": self.linked_assessment_id,
            "affects_credibility": self.affects_credibility,
            "credibility_weight": self.credibility_weight,
            "assessed_by": self.assessed_by.value,
            "assessor_id": self.assessor_id,
            "summary": self.summary,
            "red_flags": self.red_flags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# =============================================================================
# STANDARD DECEPTION INDICATORS
# =============================================================================

@dataclass
class StandardIndicator:
    """Definition of a standard deception indicator."""
    id: str
    checklist: DeceptionChecklistType
    question: str
    guidance: str
    category: str  # Sub-category within checklist


# MOM Indicators (Motive, Opportunity, Means)
MOM_INDICATORS: List[StandardIndicator] = [
    # Motive
    StandardIndicator(
        id="mom_motive_gain",
        checklist=DeceptionChecklistType.MOM,
        question="Does the source have something to gain from deceiving us?",
        guidance="Consider financial, political, personal, or organizational incentives",
        category="motive"
    ),
    StandardIndicator(
        id="mom_motive_harm",
        checklist=DeceptionChecklistType.MOM,
        question="Does the source have reason to want to harm us or our mission?",
        guidance="Consider adversarial relationships, competition, revenge motivations",
        category="motive"
    ),
    StandardIndicator(
        id="mom_motive_protect",
        checklist=DeceptionChecklistType.MOM,
        question="Is the source protecting someone or something through deception?",
        guidance="Consider loyalty, self-preservation, covering for others",
        category="motive"
    ),
    # Opportunity
    StandardIndicator(
        id="mom_opportunity_access",
        checklist=DeceptionChecklistType.MOM,
        question="Did the source have access to plant or manipulate this information?",
        guidance="Evaluate the source's access to information channels",
        category="opportunity"
    ),
    StandardIndicator(
        id="mom_opportunity_time",
        checklist=DeceptionChecklistType.MOM,
        question="Did the source have sufficient time to fabricate this information?",
        guidance="Consider timing of when information was provided vs. events",
        category="opportunity"
    ),
    # Means
    StandardIndicator(
        id="mom_means_capability",
        checklist=DeceptionChecklistType.MOM,
        question="Does the source have the capability to create convincing deception?",
        guidance="Technical skills, resources, sophistication level",
        category="means"
    ),
    StandardIndicator(
        id="mom_means_resources",
        checklist=DeceptionChecklistType.MOM,
        question="Does the source have resources to sustain a deception operation?",
        guidance="Financial backing, support network, infrastructure",
        category="means"
    ),
]

# POP Indicators (Past Opposition Practices)
POP_INDICATORS: List[StandardIndicator] = [
    StandardIndicator(
        id="pop_history_source",
        checklist=DeceptionChecklistType.POP,
        question="Has this specific source been caught deceiving before?",
        guidance="Check historical record of this source",
        category="history"
    ),
    StandardIndicator(
        id="pop_history_org",
        checklist=DeceptionChecklistType.POP,
        question="Has the source's organization/affiliation used deception?",
        guidance="Organizational track record, institutional practices",
        category="history"
    ),
    StandardIndicator(
        id="pop_tactics_match",
        checklist=DeceptionChecklistType.POP,
        question="Does this information match known deception tactics?",
        guidance="Compare to documented deception methods and patterns",
        category="tactics"
    ),
    StandardIndicator(
        id="pop_timing_pattern",
        checklist=DeceptionChecklistType.POP,
        question="Is the timing consistent with past deception campaigns?",
        guidance="Historical pattern analysis of when deceptions occur",
        category="timing"
    ),
    StandardIndicator(
        id="pop_target_match",
        checklist=DeceptionChecklistType.POP,
        question="Are we a typical target for deception by this source?",
        guidance="Historical targeting patterns of the adversary",
        category="targeting"
    ),
]

# MOSES Indicators (Manipulability of Sources)
MOSES_INDICATORS: List[StandardIndicator] = [
    StandardIndicator(
        id="moses_chain_length",
        checklist=DeceptionChecklistType.MOSES,
        question="How many intermediaries are in the information chain?",
        guidance="More intermediaries = more manipulation opportunities",
        category="chain"
    ),
    StandardIndicator(
        id="moses_chain_integrity",
        checklist=DeceptionChecklistType.MOSES,
        question="Can we verify the integrity of the information chain?",
        guidance="Chain of custody, transmission security",
        category="chain"
    ),
    StandardIndicator(
        id="moses_source_vulnerable",
        checklist=DeceptionChecklistType.MOSES,
        question="Is the source vulnerable to manipulation by others?",
        guidance="Coercion, blackmail, ideological manipulation potential",
        category="vulnerability"
    ),
    StandardIndicator(
        id="moses_witting_unwitting",
        checklist=DeceptionChecklistType.MOSES,
        question="Could the source be an unwitting conduit for deception?",
        guidance="Is source aware they might be passing false info?",
        category="awareness"
    ),
    StandardIndicator(
        id="moses_single_point",
        checklist=DeceptionChecklistType.MOSES,
        question="Is this a single point of failure for this intelligence?",
        guidance="No independent corroboration = higher manipulation risk",
        category="corroboration"
    ),
    StandardIndicator(
        id="moses_technical_compromise",
        checklist=DeceptionChecklistType.MOSES,
        question="Could the technical channel be compromised?",
        guidance="SIGINT intercept, digital manipulation, spoofing",
        category="technical"
    ),
]

# EVE Indicators (Evaluation of Evidence)
EVE_INDICATORS: List[StandardIndicator] = [
    StandardIndicator(
        id="eve_internal_consistency",
        checklist=DeceptionChecklistType.EVE,
        question="Is the evidence internally consistent?",
        guidance="Check for contradictions within the evidence itself",
        category="consistency"
    ),
    StandardIndicator(
        id="eve_external_consistency",
        checklist=DeceptionChecklistType.EVE,
        question="Is the evidence consistent with other sources?",
        guidance="Compare to independent reporting",
        category="consistency"
    ),
    StandardIndicator(
        id="eve_too_good",
        checklist=DeceptionChecklistType.EVE,
        question="Does the evidence seem 'too good to be true'?",
        guidance="Suspiciously complete, convenient, or perfectly aligned",
        category="quality"
    ),
    StandardIndicator(
        id="eve_verifiable",
        checklist=DeceptionChecklistType.EVE,
        question="Can key claims in the evidence be independently verified?",
        guidance="Testable predictions, checkable facts",
        category="verifiability"
    ),
    StandardIndicator(
        id="eve_provenance",
        checklist=DeceptionChecklistType.EVE,
        question="Is the provenance of the evidence clear and credible?",
        guidance="Source, chain of custody, original context",
        category="provenance"
    ),
    StandardIndicator(
        id="eve_technical_markers",
        checklist=DeceptionChecklistType.EVE,
        question="Are there technical indicators of fabrication?",
        guidance="Metadata anomalies, editing artifacts, anachronisms",
        category="technical"
    ),
    StandardIndicator(
        id="eve_logical_coherence",
        checklist=DeceptionChecklistType.EVE,
        question="Is the evidence logically coherent with known facts?",
        guidance="Does it make sense given what we know?",
        category="logic"
    ),
]

# Combined indicator lookup
ALL_DECEPTION_INDICATORS: Dict[DeceptionChecklistType, List[StandardIndicator]] = {
    DeceptionChecklistType.MOM: MOM_INDICATORS,
    DeceptionChecklistType.POP: POP_INDICATORS,
    DeceptionChecklistType.MOSES: MOSES_INDICATORS,
    DeceptionChecklistType.EVE: EVE_INDICATORS,
}


def get_indicators_for_checklist(checklist_type: DeceptionChecklistType) -> List[StandardIndicator]:
    """Get standard indicators for a checklist type."""
    return ALL_DECEPTION_INDICATORS.get(checklist_type, [])


def create_empty_checklist(checklist_type: DeceptionChecklistType) -> DeceptionChecklist:
    """Create an empty checklist with all standard indicators."""
    indicators = [
        DeceptionIndicator(
            id=ind.id,
            checklist=ind.checklist,
            question=ind.question,
        )
        for ind in get_indicators_for_checklist(checklist_type)
    ]
    return DeceptionChecklist(
        checklist_type=checklist_type,
        indicators=indicators,
    )
