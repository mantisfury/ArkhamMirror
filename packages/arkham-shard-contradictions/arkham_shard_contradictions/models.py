"""Data models for the Contradictions Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel


class ContradictionStatus(Enum):
    """Status of a detected contradiction."""
    DETECTED = "detected"  # Initially detected by system
    CONFIRMED = "confirmed"  # Confirmed by analyst
    DISMISSED = "dismissed"  # Dismissed as false positive
    INVESTIGATING = "investigating"  # Under active investigation


class Severity(Enum):
    """Severity level of contradiction."""
    HIGH = "high"  # Direct, clear contradiction
    MEDIUM = "medium"  # Moderate contradiction with some ambiguity
    LOW = "low"  # Minor discrepancy or potential contradiction


class ContradictionType(Enum):
    """Type of contradiction detected."""
    DIRECT = "direct"  # "X happened" vs "X did not happen"
    TEMPORAL = "temporal"  # Different dates/times for same event
    NUMERIC = "numeric"  # Different figures/amounts
    ENTITY = "entity"  # Different people/places attributed
    LOGICAL = "logical"  # Logically incompatible statements
    CONTEXTUAL = "contextual"  # Contradictory in specific context


@dataclass
class Contradiction:
    """A detected contradiction between two documents."""
    id: str

    # Documents involved
    doc_a_id: str
    doc_b_id: str

    # Claims that contradict
    claim_a: str
    claim_b: str

    # Claim locations in documents
    claim_a_location: str = ""  # Page/chunk reference
    claim_b_location: str = ""

    # Classification
    contradiction_type: ContradictionType = ContradictionType.DIRECT
    severity: Severity = Severity.MEDIUM
    status: ContradictionStatus = ContradictionStatus.DETECTED

    # Analysis
    explanation: str = ""
    confidence_score: float = 0.0  # 0.0 to 1.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    detected_by: str = "system"  # "system", "llm", "analyst"

    # Analyst workflow
    analyst_notes: list[str] = field(default_factory=list)
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None

    # Chain detection
    chain_id: str | None = None  # If part of a contradiction chain
    related_contradictions: list[str] = field(default_factory=list)

    # Additional context
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Claim:
    """An extracted claim from a document."""
    id: str
    document_id: str
    text: str

    # Location
    chunk_id: str | None = None
    page_number: int | None = None
    location: str = ""

    # Classification
    claim_type: str = "fact"  # "fact", "opinion", "prediction", "attribution"

    # Extraction
    embedding: list[float] | None = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    extraction_method: str = "system"  # "system", "llm", "manual"

    # Metadata
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContradictionChain:
    """A chain of related contradictions."""
    id: str
    contradiction_ids: list[str]

    # Analysis
    description: str = ""
    severity: Severity = Severity.MEDIUM

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# --- Pydantic Request/Response Models ---


class AnalyzeRequest(BaseModel):
    """Request to analyze documents for contradictions."""
    doc_a_id: str
    doc_b_id: str
    threshold: float = 0.7  # Similarity threshold for claim matching
    use_llm: bool = True  # Use LLM for verification


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple document pairs."""
    document_pairs: list[tuple[str, str]]
    threshold: float = 0.7
    use_llm: bool = True
    async_mode: bool = False  # If True, use llm-analysis worker for background processing


class ClaimsRequest(BaseModel):
    """Request to extract claims from text."""
    text: str
    document_id: str | None = None
    use_llm: bool = True


class UpdateStatusRequest(BaseModel):
    """Request to update contradiction status."""
    status: str  # Will be converted to ContradictionStatus
    notes: str = ""
    analyst_id: str | None = None


class AddNotesRequest(BaseModel):
    """Request to add analyst notes."""
    notes: str
    analyst_id: str | None = None


class ContradictionResult(BaseModel):
    """Response containing contradiction details."""
    id: str
    doc_a_id: str
    doc_b_id: str
    claim_a: str
    claim_b: str
    contradiction_type: str
    severity: str
    status: str
    explanation: str
    confidence_score: float
    created_at: str
    analyst_notes: list[str] = []
    chain_id: str | None = None


class ContradictionList(BaseModel):
    """Response containing list of contradictions."""
    contradictions: list[ContradictionResult]
    total: int
    page: int = 1
    page_size: int = 50


class StatsResponse(BaseModel):
    """Contradiction statistics."""
    total_contradictions: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_type: dict[str, int]
    chains_detected: int
    recent_count: int  # Count in last 24 hours


class ClaimExtractionResult(BaseModel):
    """Result of claim extraction."""
    claims: list[dict[str, Any]]
    count: int
    document_id: str | None = None
