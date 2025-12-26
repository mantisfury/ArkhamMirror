"""
Claims Shard - Data Models

Pydantic models and dataclasses for claim management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class ClaimStatus(str, Enum):
    """Status of a claim in the verification workflow."""
    UNVERIFIED = "unverified"     # Newly extracted, not yet reviewed
    VERIFIED = "verified"         # Confirmed with supporting evidence
    DISPUTED = "disputed"         # Contradicted by other evidence
    RETRACTED = "retracted"       # Claim withdrawn/corrected
    UNCERTAIN = "uncertain"       # Evidence is inconclusive


class ClaimType(str, Enum):
    """Type classification for claims."""
    FACTUAL = "factual"           # Verifiable statement of fact
    OPINION = "opinion"           # Subjective statement
    PREDICTION = "prediction"     # Future-oriented claim
    QUANTITATIVE = "quantitative" # Numerical/statistical claim
    ATTRIBUTION = "attribution"   # Quote or attributed statement
    OTHER = "other"


class EvidenceType(str, Enum):
    """Type of evidence linked to a claim."""
    DOCUMENT = "document"         # Evidence from a document
    ENTITY = "entity"             # Evidence from an entity record
    EXTERNAL = "external"         # External source (URL, citation)
    CLAIM = "claim"               # Another claim as evidence


class EvidenceRelationship(str, Enum):
    """How evidence relates to a claim."""
    SUPPORTS = "supports"         # Evidence supports the claim
    REFUTES = "refutes"           # Evidence contradicts the claim
    RELATED = "related"           # Evidence is related but neutral


class EvidenceStrength(str, Enum):
    """Strength/quality of evidence."""
    STRONG = "strong"             # Definitive evidence
    MODERATE = "moderate"         # Reasonable evidence
    WEAK = "weak"                 # Circumstantial/limited evidence


class ExtractionMethod(str, Enum):
    """How the claim was extracted."""
    MANUAL = "manual"             # User created manually
    LLM = "llm"                   # Extracted by LLM
    RULE = "rule"                 # Extracted by rule-based system
    IMPORTED = "imported"         # Imported from external source


# === Dataclasses ===

@dataclass
class Claim:
    """
    A factual assertion extracted from a document.

    Claims are the foundation for fact-checking and contradiction detection.
    """
    id: str
    text: str                                    # The claim text
    claim_type: ClaimType = ClaimType.FACTUAL
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: float = 1.0                      # Extraction confidence (0-1)

    # Source information
    source_document_id: Optional[str] = None     # Document claim was extracted from
    source_start_char: Optional[int] = None      # Position in source document
    source_end_char: Optional[int] = None
    source_context: Optional[str] = None         # Surrounding text for context

    # Extraction metadata
    extracted_by: ExtractionMethod = ExtractionMethod.MANUAL
    extraction_model: Optional[str] = None       # LLM model used if applicable

    # Relationships
    entity_ids: List[str] = field(default_factory=list)  # Linked entities
    evidence_count: int = 0                      # Number of linked evidence items
    supporting_count: int = 0                    # Evidence supporting
    refuting_count: int = 0                      # Evidence refuting

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """
    Evidence linked to a claim.

    Evidence can support or refute a claim, with varying strength.
    """
    id: str
    claim_id: str
    evidence_type: EvidenceType
    reference_id: str                            # ID of the evidence source
    reference_title: Optional[str] = None        # Title for display

    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS
    strength: EvidenceStrength = EvidenceStrength.MODERATE

    # Context
    excerpt: Optional[str] = None                # Relevant excerpt from evidence
    notes: Optional[str] = None                  # Analyst notes

    # Metadata
    added_by: str = "system"
    added_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimExtractionResult:
    """
    Result of claim extraction from text or document.
    """
    claims: List[Claim]
    source_document_id: Optional[str] = None
    extraction_method: ExtractionMethod = ExtractionMethod.LLM
    extraction_model: Optional[str] = None
    total_extracted: int = 0
    processing_time_ms: float = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ClaimMatch:
    """
    A match between two similar claims.
    """
    claim_id: str
    matched_claim_id: str
    similarity_score: float                      # 0-1 similarity
    match_type: str = "semantic"                 # semantic, exact, fuzzy
    suggested_action: str = "review"             # review, merge, ignore


@dataclass
class ClaimMergeResult:
    """
    Result of merging duplicate claims.
    """
    primary_claim_id: str                        # The surviving claim
    merged_claim_ids: List[str]                  # Claims that were merged
    evidence_transferred: int                    # Evidence items moved
    entities_merged: int                         # Entity links consolidated


@dataclass
class ClaimStatistics:
    """
    Statistics about claims in the system.
    """
    total_claims: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_extraction_method: Dict[str, int] = field(default_factory=dict)

    total_evidence: int = 0
    evidence_supporting: int = 0
    evidence_refuting: int = 0

    claims_with_evidence: int = 0
    claims_without_evidence: int = 0

    avg_confidence: float = 0.0
    avg_evidence_per_claim: float = 0.0


@dataclass
class ClaimFilter:
    """
    Filter criteria for claim queries.
    """
    status: Optional[ClaimStatus] = None
    claim_type: Optional[ClaimType] = None
    document_id: Optional[str] = None
    entity_id: Optional[str] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    extracted_by: Optional[ExtractionMethod] = None
    has_evidence: Optional[bool] = None
    search_text: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
