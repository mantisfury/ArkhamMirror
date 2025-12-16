from pydantic import BaseModel
from typing import List, Optional


class ContradictionEvidence(BaseModel):
    text: str
    document_id: int
    chunk_id: Optional[int] = None
    page_number: Optional[int] = None
    # Phase 3 fields
    extracted_claim: Optional[str] = None
    claim_type: Optional[str] = None
    evidence_confidence: Optional[float] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None


class Contradiction(BaseModel):
    id: int
    entity_name: str
    description: str
    severity: str
    status: str
    confidence: float
    created_at: Optional[str] = None
    evidence: List[ContradictionEvidence]

    # Phase 3 fields
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    chain_id: Optional[int] = None
    chain_position: Optional[int] = None
    detection_method: Optional[str] = "llm"
    llm_model: Optional[str] = None
    user_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
