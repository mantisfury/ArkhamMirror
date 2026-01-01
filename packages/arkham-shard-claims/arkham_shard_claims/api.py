"""
Claims Shard - FastAPI Routes

REST API endpoints for claim management.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .models import (
    ClaimStatus,
    ClaimType,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
    ExtractionMethod,
)

router = APIRouter(prefix="/api/claims", tags=["claims"])

# === Pydantic Request/Response Models ===


class ClaimCreate(BaseModel):
    """Request model for creating a claim."""
    text: str = Field(..., description="The claim text")
    claim_type: ClaimType = Field(default=ClaimType.FACTUAL)
    source_document_id: Optional[str] = None
    source_start_char: Optional[int] = None
    source_end_char: Optional[int] = None
    source_context: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    entity_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ClaimResponse(BaseModel):
    """Response model for a claim."""
    id: str
    text: str
    claim_type: str
    status: str
    confidence: float
    source_document_id: Optional[str]
    source_start_char: Optional[int]
    source_end_char: Optional[int]
    source_context: Optional[str]
    extracted_by: str
    extraction_model: Optional[str]
    entity_ids: List[str]
    evidence_count: int
    supporting_count: int
    refuting_count: int
    created_at: str
    updated_at: str
    verified_at: Optional[str]
    metadata: Dict[str, Any]


class ClaimListResponse(BaseModel):
    """Response model for listing claims."""
    items: List[ClaimResponse]
    total: int
    page: int
    page_size: int


class StatusUpdateRequest(BaseModel):
    """Request model for updating claim status."""
    status: ClaimStatus
    notes: Optional[str] = None


class EvidenceCreate(BaseModel):
    """Request model for adding evidence."""
    evidence_type: EvidenceType
    reference_id: str
    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    reference_title: Optional[str] = None
    excerpt: Optional[str] = None
    notes: Optional[str] = None


class EvidenceResponse(BaseModel):
    """Response model for evidence."""
    id: str
    claim_id: str
    evidence_type: str
    reference_id: str
    reference_title: Optional[str]
    relationship: str
    strength: str
    excerpt: Optional[str]
    notes: Optional[str]
    added_by: str
    added_at: str
    metadata: Dict[str, Any]


class ExtractionRequest(BaseModel):
    """Request model for claim extraction."""
    text: str = Field(..., description="Text to extract claims from")
    document_id: Optional[str] = None
    extraction_model: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Response model for extraction results."""
    claims: List[ClaimResponse]
    source_document_id: Optional[str]
    extraction_method: str
    extraction_model: Optional[str]
    total_extracted: int
    processing_time_ms: float
    errors: List[str]


class SimilarityRequest(BaseModel):
    """Request model for finding similar claims."""
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)


class ClaimMatchResponse(BaseModel):
    """Response model for claim matches."""
    claim_id: str
    matched_claim_id: str
    similarity_score: float
    match_type: str
    suggested_action: str


class MergeRequest(BaseModel):
    """Request model for merging claims."""
    claim_ids_to_merge: List[str]


class MergeResponse(BaseModel):
    """Response model for merge results."""
    primary_claim_id: str
    merged_claim_ids: List[str]
    evidence_transferred: int
    entities_merged: int


class StatisticsResponse(BaseModel):
    """Response model for claim statistics."""
    total_claims: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_extraction_method: Dict[str, int]
    total_evidence: int
    evidence_supporting: int
    evidence_refuting: int
    claims_with_evidence: int
    claims_without_evidence: int
    avg_confidence: float
    avg_evidence_per_claim: float


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


# === Helper Functions ===


def _get_shard(request):
    """Get the claims shard instance from app state."""
    shard = getattr(request.app.state, "claims_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Claims shard not available")
    return shard


def _claim_to_response(claim) -> ClaimResponse:
    """Convert Claim object to response model."""
    return ClaimResponse(
        id=claim.id,
        text=claim.text,
        claim_type=claim.claim_type.value,
        status=claim.status.value,
        confidence=claim.confidence,
        source_document_id=claim.source_document_id,
        source_start_char=claim.source_start_char,
        source_end_char=claim.source_end_char,
        source_context=claim.source_context,
        extracted_by=claim.extracted_by.value,
        extraction_model=claim.extraction_model,
        entity_ids=claim.entity_ids,
        evidence_count=claim.evidence_count,
        supporting_count=claim.supporting_count,
        refuting_count=claim.refuting_count,
        created_at=claim.created_at.isoformat(),
        updated_at=claim.updated_at.isoformat(),
        verified_at=claim.verified_at.isoformat() if claim.verified_at else None,
        metadata=claim.metadata,
    )


def _evidence_to_response(evidence) -> EvidenceResponse:
    """Convert Evidence object to response model."""
    return EvidenceResponse(
        id=evidence.id,
        claim_id=evidence.claim_id,
        evidence_type=evidence.evidence_type.value,
        reference_id=evidence.reference_id,
        reference_title=evidence.reference_title,
        relationship=evidence.relationship.value,
        strength=evidence.strength.value,
        excerpt=evidence.excerpt,
        notes=evidence.notes,
        added_by=evidence.added_by,
        added_at=evidence.added_at.isoformat(),
        metadata=evidence.metadata,
    )


# === Endpoints ===


@router.get("/count", response_model=CountResponse)
async def get_claims_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of claims (used for badge)."""
    shard = _get_shard(request)
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


@router.get("/", response_model=ClaimListResponse)
async def list_claims(
    request: Request,
    status: Optional[ClaimStatus] = Query(None),
    claim_type: Optional[ClaimType] = Query(None),
    document_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    extracted_by: Optional[ExtractionMethod] = Query(None),
    has_evidence: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search in claim text"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
):
    """List claims with optional filtering."""
    from .models import ClaimFilter

    shard = _get_shard(request)

    # Convert page/page_size to limit/offset
    limit = page_size
    offset = (page - 1) * page_size

    filter = ClaimFilter(
        status=status,
        claim_type=claim_type,
        document_id=document_id,
        entity_id=entity_id,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        extracted_by=extracted_by,
        has_evidence=has_evidence,
        search_text=search,
    )

    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status=status.value if status else None)

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ClaimResponse, status_code=201)
async def create_claim(request: Request, body: ClaimCreate):
    """Create a new claim."""
    shard = _get_shard(request)

    claim = await shard.create_claim(
        text=body.text,
        claim_type=body.claim_type,
        source_document_id=body.source_document_id,
        source_start_char=body.source_start_char,
        source_end_char=body.source_end_char,
        source_context=body.source_context,
        confidence=body.confidence,
        entity_ids=body.entity_ids,
        metadata=body.metadata,
    )

    return _claim_to_response(claim)


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(request: Request, claim_id: str):
    """Get a specific claim by ID."""
    shard = _get_shard(request)
    claim = await shard.get_claim(claim_id)

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    return _claim_to_response(claim)


@router.patch("/{claim_id}/status", response_model=ClaimResponse)
async def update_claim_status(request: Request, claim_id: str, body: StatusUpdateRequest):
    """Update the status of a claim."""
    shard = _get_shard(request)

    claim = await shard.update_claim_status(
        claim_id=claim_id,
        status=body.status,
        notes=body.notes,
    )

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    return _claim_to_response(claim)


@router.delete("/{claim_id}", status_code=204)
async def delete_claim(request: Request, claim_id: str):
    """Delete a claim (marks as retracted)."""
    shard = _get_shard(request)

    claim = await shard.update_claim_status(
        claim_id=claim_id,
        status=ClaimStatus.RETRACTED,
        notes="Deleted by user",
    )

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")


# === Evidence Endpoints ===


@router.get("/{claim_id}/evidence", response_model=List[EvidenceResponse])
async def get_claim_evidence(request: Request, claim_id: str):
    """Get all evidence for a claim."""
    shard = _get_shard(request)

    # Verify claim exists
    claim = await shard.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    evidence = await shard.get_claim_evidence(claim_id)
    return [_evidence_to_response(e) for e in evidence]


@router.post("/{claim_id}/evidence", response_model=EvidenceResponse, status_code=201)
async def add_claim_evidence(request: Request, claim_id: str, body: EvidenceCreate):
    """Add evidence to a claim."""
    shard = _get_shard(request)

    # Verify claim exists
    claim = await shard.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    evidence = await shard.add_evidence(
        claim_id=claim_id,
        evidence_type=body.evidence_type,
        reference_id=body.reference_id,
        relationship=body.relationship,
        strength=body.strength,
        reference_title=body.reference_title,
        excerpt=body.excerpt,
        notes=body.notes,
    )

    return _evidence_to_response(evidence)


# === Extraction Endpoints ===


@router.post("/extract", response_model=ExtractionResponse)
async def extract_claims(request: Request, body: ExtractionRequest):
    """Extract claims from text using LLM."""
    shard = _get_shard(request)

    result = await shard.extract_claims_from_text(
        text=body.text,
        document_id=body.document_id,
        extraction_model=body.extraction_model,
    )

    return ExtractionResponse(
        claims=[_claim_to_response(c) for c in result.claims],
        source_document_id=result.source_document_id,
        extraction_method=result.extraction_method.value,
        extraction_model=result.extraction_model,
        total_extracted=result.total_extracted,
        processing_time_ms=result.processing_time_ms,
        errors=result.errors,
    )


@router.post("/extract-from-document/{document_id}", response_model=ExtractionResponse)
async def extract_claims_from_document(request: Request, document_id: str):
    """
    Extract claims from a document by ID.

    Fetches the document content from the database and extracts claims using LLM.
    """
    shard = _get_shard(request)

    # Get database service to fetch document content
    db = shard._db
    if not db:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Fetch document chunks to get text content
    chunks = await db.fetch_all(
        """SELECT text FROM arkham_frame.chunks
           WHERE document_id = :doc_id
           ORDER BY chunk_index""",
        {"doc_id": document_id}
    )

    if not chunks:
        raise HTTPException(status_code=404, detail=f"No content found for document {document_id}")

    # Combine chunk text
    text = "\n\n".join(c["text"] for c in chunks if c.get("text"))

    if not text.strip():
        raise HTTPException(status_code=404, detail=f"Document {document_id} has no text content")

    # Extract claims
    result = await shard.extract_claims_from_text(
        text=text,
        document_id=document_id,
    )

    return ExtractionResponse(
        claims=[_claim_to_response(c) for c in result.claims],
        source_document_id=result.source_document_id,
        extraction_method=result.extraction_method.value,
        extraction_model=result.extraction_model,
        total_extracted=result.total_extracted,
        processing_time_ms=result.processing_time_ms,
        errors=result.errors,
    )


# === Similarity & Deduplication Endpoints ===


@router.post("/{claim_id}/similar", response_model=List[ClaimMatchResponse])
async def find_similar_claims(request: Request, claim_id: str, body: SimilarityRequest):
    """Find claims similar to the given claim."""
    shard = _get_shard(request)

    # Verify claim exists
    claim = await shard.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    matches = await shard.find_similar_claims(
        claim_id=claim_id,
        threshold=body.threshold,
        limit=body.limit,
    )

    return [
        ClaimMatchResponse(
            claim_id=m.claim_id,
            matched_claim_id=m.matched_claim_id,
            similarity_score=m.similarity_score,
            match_type=m.match_type,
            suggested_action=m.suggested_action,
        )
        for m in matches
    ]


@router.post("/{claim_id}/merge", response_model=MergeResponse)
async def merge_claims(request: Request, claim_id: str, body: MergeRequest):
    """Merge duplicate claims into a primary claim."""
    shard = _get_shard(request)

    # Verify primary claim exists
    claim = await shard.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    result = await shard.merge_claims(
        primary_claim_id=claim_id,
        claim_ids_to_merge=body.claim_ids_to_merge,
    )

    return MergeResponse(
        primary_claim_id=result.primary_claim_id,
        merged_claim_ids=result.merged_claim_ids,
        evidence_transferred=result.evidence_transferred,
        entities_merged=result.entities_merged,
    )


# === Statistics Endpoints ===


@router.get("/stats/overview", response_model=StatisticsResponse)
async def get_statistics(request: Request):
    """Get statistics about claims in the system."""
    shard = _get_shard(request)
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_claims=stats.total_claims,
        by_status=stats.by_status,
        by_type=stats.by_type,
        by_extraction_method=stats.by_extraction_method,
        total_evidence=stats.total_evidence,
        evidence_supporting=stats.evidence_supporting,
        evidence_refuting=stats.evidence_refuting,
        claims_with_evidence=stats.claims_with_evidence,
        claims_without_evidence=stats.claims_without_evidence,
        avg_confidence=stats.avg_confidence,
        avg_evidence_per_claim=stats.avg_evidence_per_claim,
    )


# === Filtered List Endpoints (for sub-routes) ===


@router.get("/status/unverified", response_model=ClaimListResponse)
async def list_unverified_claims(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List unverified claims."""
    from .models import ClaimFilter

    shard = _get_shard(request)
    limit = page_size
    offset = (page - 1) * page_size
    filter = ClaimFilter(status=ClaimStatus.UNVERIFIED)
    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="unverified")

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/status/verified", response_model=ClaimListResponse)
async def list_verified_claims(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List verified claims."""
    from .models import ClaimFilter

    shard = _get_shard(request)
    limit = page_size
    offset = (page - 1) * page_size
    filter = ClaimFilter(status=ClaimStatus.VERIFIED)
    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="verified")

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/status/disputed", response_model=ClaimListResponse)
async def list_disputed_claims(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List disputed claims."""
    from .models import ClaimFilter

    shard = _get_shard(request)
    limit = page_size
    offset = (page - 1) * page_size
    filter = ClaimFilter(status=ClaimStatus.DISPUTED)
    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="disputed")

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
    )


# === Document-based Endpoints ===


@router.get("/by-document/{document_id}", response_model=ClaimListResponse)
async def list_claims_by_document(
    request: Request,
    document_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List claims extracted from a specific document."""
    from .models import ClaimFilter

    shard = _get_shard(request)
    limit = page_size
    offset = (page - 1) * page_size
    filter = ClaimFilter(document_id=document_id)
    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=len(claims),
        page=page,
        page_size=page_size,
    )


# === Entity-based Endpoints ===


@router.get("/by-entity/{entity_id}", response_model=ClaimListResponse)
async def list_claims_by_entity(
    request: Request,
    entity_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List claims linked to a specific entity."""
    from .models import ClaimFilter

    shard = _get_shard(request)
    limit = page_size
    offset = (page - 1) * page_size
    filter = ClaimFilter(entity_id=entity_id)
    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset)

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=len(claims),
        page=page,
        page_size=page_size,
    )
