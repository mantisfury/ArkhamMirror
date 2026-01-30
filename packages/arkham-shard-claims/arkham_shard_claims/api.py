"""
Claims Shard - FastAPI Routes

REST API endpoints for claim management.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

try:
    from arkham_frame.auth import current_active_user, require_project_member
except ImportError:
    # Fallback if auth not available
    async def current_active_user():
        return None
    async def require_project_member(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

from .models import (
    ClaimStatus,
    ClaimType,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
    ExtractionMethod,
)

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

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


async def _require_active_project_id(request: Request, shard, user: Any) -> str:
    """
    Resolve the user's active project_id and validate membership.

    Returns project_id (string). Raises HTTPException if none.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    frame = getattr(shard, "frame", None) or getattr(shard, "_frame", None)
    if not frame or not hasattr(frame, "get_active_project_id"):
        raise HTTPException(status_code=503, detail="Frame project service not available")

    user_id_str = str(getattr(user, "id", "")).lower().strip()
    project_id = await frame.get_active_project_id(user_id_str)
    if not project_id:
        raise HTTPException(status_code=400, detail="No active project selected")

    await require_project_member(str(project_id), user, request)
    return str(project_id)


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
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user = Depends(current_active_user),
):
    """List claims with optional filtering. All claims are scoped to the active project."""
    from .models import ClaimFilter

    shard = _get_shard(request)

    # Use project_id from query param if provided, otherwise use active project
    if not project_id and shard.frame:
        project_id = await shard.frame.get_active_project_id(str(user.id))
        logger.debug(f"Using active project from frame: {project_id}")
    
    # If no project_id, return empty results (claims are project-scoped)
    if not project_id:
        logger.debug(f"No project_id available. Returning empty results.")
        return ClaimListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
        )
    
    # Verify user is a member of the project
    await require_project_member(str(project_id), user, request)

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

    claims = await shard.list_claims(filter=filter, limit=limit, offset=offset, project_id=project_id)
    total = await shard.get_count(status=status.value if status else None, project_id=project_id)

    return ClaimListResponse(
        items=[_claim_to_response(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ClaimResponse, status_code=201)
async def create_claim(request: Request, body: ClaimCreate):
    """Create a new claim."""
    with log_operation("claims.create", claim_type=body.claim_type.value if hasattr(body.claim_type, 'value') else str(body.claim_type)) as event:
        try:
            if event:
                event.context("shard", "claims")
                event.context("operation", "create")
                event.input(
                    claim_type=body.claim_type.value if hasattr(body.claim_type, 'value') else str(body.claim_type),
                    source_document_id=body.source_document_id,
                    confidence=body.confidence,
                    entity_count=len(body.entity_ids) if body.entity_ids else 0,
                    has_metadata=body.metadata is not None,
                )

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

            if event:
                event.output(
                    claim_id=claim.id,
                    status=claim.status.value if hasattr(claim.status, 'value') else str(claim.status),
                    evidence_count=claim.evidence_count,
                )

            return _claim_to_response(claim)
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


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
    with log_operation("claims.update_status", claim_id=claim_id) as event:
        try:
            if event:
                event.context("shard", "claims")
                event.context("operation", "update_status")
                event.input(
                    claim_id=claim_id,
                    new_status=body.status.value if hasattr(body.status, 'value') else str(body.status),
                    has_notes=body.notes is not None,
                )

            shard = _get_shard(request)

            claim = await shard.update_claim_status(
                claim_id=claim_id,
                status=body.status,
                notes=body.notes,
            )

            if not claim:
                raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

            if event:
                event.output(
                    claim_id=claim.id,
                    status=claim.status.value if hasattr(claim.status, 'value') else str(claim.status),
                    verified_at=claim.verified_at.isoformat() if claim.verified_at else None,
                )

            return _claim_to_response(claim)
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


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
    with log_operation("claims.add_evidence", claim_id=claim_id) as event:
        try:
            if event:
                event.context("shard", "claims")
                event.context("operation", "add_evidence")
                event.input(
                    claim_id=claim_id,
                    evidence_type=body.evidence_type.value if hasattr(body.evidence_type, 'value') else str(body.evidence_type),
                    relationship=body.relationship.value if hasattr(body.relationship, 'value') else str(body.relationship),
                    strength=body.strength.value if hasattr(body.strength, 'value') else str(body.strength),
                    reference_id=body.reference_id,
                )

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

            if event:
                event.output(
                    evidence_id=evidence.id,
                    claim_id=claim_id,
                    evidence_count=claim.evidence_count,
                    supporting_count=claim.supporting_count,
                    refuting_count=claim.refuting_count,
                )

            return _evidence_to_response(evidence)
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


# === Extraction Endpoints ===


@router.post("/extract", response_model=ExtractionResponse)
async def extract_claims(request: Request, body: ExtractionRequest):
    """Extract claims from text using LLM."""
    with log_operation("claims.extract", document_id=body.document_id) as event:
        try:
            start_time = time.time()
            
            if event:
                event.context("shard", "claims")
                event.context("operation", "extract")
                event.input(
                    document_id=body.document_id,
                    extraction_model=body.extraction_model,
                    text_length=len(body.text) if body.text else 0,
                )

            shard = _get_shard(request)

            result = await shard.extract_claims_from_text(
                text=body.text,
                document_id=body.document_id,
                extraction_model=body.extraction_model,
            )

            if event:
                event.output(
                    total_extracted=result.total_extracted,
                    extraction_method=result.extraction_method.value if hasattr(result.extraction_method, 'value') else str(result.extraction_method),
                    extraction_model=result.extraction_model,
                    processing_time_ms=result.processing_time_ms,
                    error_count=len(result.errors) if result.errors else 0,
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
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


@router.post("/extract-from-document/{document_id}", response_model=ExtractionResponse)
async def extract_claims_from_document(request: Request, document_id: str):
    """
    Extract claims from a document by ID.

    Fetches the document content from the database and extracts claims using LLM.
    """
    with log_operation("claims.extract_from_document", document_id=document_id) as event:
        try:
            start_time = time.time()
            
            if event:
                event.context("shard", "claims")
                event.context("operation", "extract_from_document")
                event.input(document_id=document_id)

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

            if event:
                event.context("chunk_count", len(chunks))
                event.context("text_length", len(text))

            # Extract claims
            result = await shard.extract_claims_from_text(
                text=text,
                document_id=document_id,
            )

            if event:
                event.output(
                    total_extracted=result.total_extracted,
                    extraction_method=result.extraction_method.value if hasattr(result.extraction_method, 'value') else str(result.extraction_method),
                    extraction_model=result.extraction_model,
                    processing_time_ms=result.processing_time_ms,
                    error_count=len(result.errors) if result.errors else 0,
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
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


# === Backfill Evidence Endpoint ===


@router.post("/backfill-evidence")
async def backfill_source_evidence(request: Request):
    """
    Backfill source document evidence for existing claims.

    Finds claims with source_document_id but no evidence linked,
    and creates evidence entries linking them to their source documents.
    """
    shard = _get_shard(request)
    db = shard._db
    if not db:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Find claims with source_document_id but no evidence
    claims_without_evidence = await db.fetch_all(
        """SELECT c.id, c.source_document_id, c.source_context
           FROM arkham_claims c
           LEFT JOIN arkham_claim_evidence e ON c.id = e.claim_id
           WHERE c.source_document_id IS NOT NULL
           AND e.id IS NULL""",
        {},
    )

    linked_count = 0
    for row in claims_without_evidence:
        claim_id = row["id"]
        doc_id = row["source_document_id"]
        source_context = row.get("source_context")

        # Get document filename (frame uses filename, not title)
        doc_row = await db.fetch_one(
            "SELECT filename FROM arkham_frame.documents WHERE id = :doc_id",
            {"doc_id": doc_id},
        )
        doc_title = None
        if doc_row:
            doc_title = doc_row.get("filename") or "Source Document"

        # Create evidence link
        await shard.add_evidence(
            claim_id=claim_id,
            evidence_type=EvidenceType.DOCUMENT,
            reference_id=doc_id,
            reference_title=doc_title,
            relationship=EvidenceRelationship.SUPPORTS,
            strength=EvidenceStrength.MODERATE,
            excerpt=source_context,
            notes="Source document from which this claim was extracted (backfilled)",
            added_by="backfill",
        )
        linked_count += 1

    return {
        "message": f"Backfilled evidence for {linked_count} claims",
        "claims_updated": linked_count,
    }


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


# === AI Junior Analyst ===


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""

    target_id: str
    context: Dict[str, Any] = {}
    depth: str = "quick"
    session_id: Optional[str] = None
    message: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for claim analysis.

    Provides streaming AI analysis of claims, evidence, and verification status.
    """
    shard = _get_shard(request)
    frame = shard.frame
    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(status_code=503, detail="AI Analyst service not available")

    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Map depth string to enum
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.DETAILED,
        "detailed": AnalysisDepth.DETAILED,
        "deep": AnalysisDepth.DETAILED,
    }
    depth = depth_map.get(body.depth, AnalysisDepth.QUICK)

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=m["role"], content=m["content"])
            for m in body.conversation_history
        ]

    # Create analysis request
    analysis_request = AnalysisRequest(
        shard="claims",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Return streaming response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
