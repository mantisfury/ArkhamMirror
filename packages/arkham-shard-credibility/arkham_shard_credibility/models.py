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
