"""Contradictions Shard API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import (
    AnalyzeRequest,
    BatchAnalyzeRequest,
    ClaimsRequest,
    UpdateStatusRequest,
    AddNotesRequest,
    ContradictionResult,
    ContradictionList,
    StatsResponse,
    ClaimExtractionResult,
    ContradictionStatus,
    Severity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contradictions", tags=["contradictions"])

# These get set by the shard on initialization
_detector = None
_storage = None
_event_bus = None
_chain_detector = None


def init_api(detector, storage, event_bus, chain_detector):
    """Initialize API with shard dependencies."""
    global _detector, _storage, _event_bus, _chain_detector
    _detector = detector
    _storage = storage
    _event_bus = event_bus
    _chain_detector = chain_detector


# --- Helper Functions ---


def _contradiction_to_result(contradiction) -> ContradictionResult:
    """Convert Contradiction to ContradictionResult."""
    return ContradictionResult(
        id=contradiction.id,
        doc_a_id=contradiction.doc_a_id,
        doc_b_id=contradiction.doc_b_id,
        claim_a=contradiction.claim_a,
        claim_b=contradiction.claim_b,
        contradiction_type=contradiction.contradiction_type.value,
        severity=contradiction.severity.value,
        status=contradiction.status.value,
        explanation=contradiction.explanation,
        confidence_score=contradiction.confidence_score,
        created_at=contradiction.created_at.isoformat(),
        analyst_notes=contradiction.analyst_notes,
        chain_id=contradiction.chain_id,
    )


# --- Endpoints ---


@router.post("/analyze")
async def analyze_documents(request: AnalyzeRequest):
    """
    Analyze two documents for contradictions.

    Performs multi-stage analysis:
    1. Extract claims from both documents
    2. Find semantically similar claim pairs
    3. Verify contradictions using LLM (if enabled)
    4. Store detected contradictions
    """
    if not _detector or not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    logger.info(f"Analyzing documents: {request.doc_a_id} vs {request.doc_b_id}")

    # TODO: Fetch actual document content from Frame
    # For now, this is a placeholder
    doc_a_text = f"Document {request.doc_a_id} content"
    doc_b_text = f"Document {request.doc_b_id} content"

    # Extract claims
    if request.use_llm:
        claims_a = await _detector.extract_claims_llm(doc_a_text, request.doc_a_id)
        claims_b = await _detector.extract_claims_llm(doc_b_text, request.doc_b_id)
    else:
        claims_a = _detector.extract_claims_simple(doc_a_text, request.doc_a_id)
        claims_b = _detector.extract_claims_simple(doc_b_text, request.doc_b_id)

    # Find similar claim pairs
    similar_pairs = await _detector.find_similar_claims(
        claims_a, claims_b, threshold=request.threshold
    )

    # Verify contradictions
    contradictions = []
    for claim_a, claim_b, similarity in similar_pairs:
        contradiction = await _detector.verify_contradiction(claim_a, claim_b, similarity)
        if contradiction:
            _storage.create(contradiction)
            contradictions.append(contradiction)

    # Emit event
    if _event_bus and contradictions:
        await _event_bus.emit(
            "contradictions.detected",
            {
                "doc_a_id": request.doc_a_id,
                "doc_b_id": request.doc_b_id,
                "count": len(contradictions),
                "contradiction_ids": [c.id for c in contradictions],
            },
            source="contradictions-shard",
        )

    return {
        "doc_a_id": request.doc_a_id,
        "doc_b_id": request.doc_b_id,
        "contradictions": [_contradiction_to_result(c) for c in contradictions],
        "count": len(contradictions),
    }


@router.post("/batch")
async def batch_analyze(request: BatchAnalyzeRequest):
    """
    Analyze multiple document pairs for contradictions.

    Useful for batch processing or full corpus analysis.
    """
    if not _detector or not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    logger.info(f"Batch analyzing {len(request.document_pairs)} document pairs")

    all_contradictions = []

    for doc_a_id, doc_b_id in request.document_pairs:
        # Reuse single document analysis
        try:
            result = await analyze_documents(
                AnalyzeRequest(
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                    threshold=request.threshold,
                    use_llm=request.use_llm,
                )
            )
            all_contradictions.extend(result["contradictions"])
        except Exception as e:
            logger.error(f"Failed to analyze {doc_a_id} vs {doc_b_id}: {e}")

    return {
        "pairs_analyzed": len(request.document_pairs),
        "contradictions": all_contradictions,
        "count": len(all_contradictions),
    }


@router.get("/document/{doc_id}")
async def get_document_contradictions(
    doc_id: str,
    include_chains: bool = Query(False, description="Include contradictions in same chain"),
):
    """
    Get contradictions involving a specific document.

    Args:
        doc_id: Document ID
        include_chains: Include contradictions in same chains
    """
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    contradictions = _storage.get_by_document(doc_id, include_related=include_chains)

    return {
        "document_id": doc_id,
        "contradictions": [_contradiction_to_result(c) for c in contradictions],
        "count": len(contradictions),
    }


@router.get("/list")
async def list_contradictions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
):
    """
    List all contradictions with pagination and filtering.
    """
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    # Parse filters
    status_filter = None
    if status:
        try:
            status_filter = ContradictionStatus[status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    severity_filter = None
    if severity:
        try:
            severity_filter = Severity[severity.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    # Get contradictions
    contradictions, total = _storage.list_all(
        page=page,
        page_size=page_size,
        status=status_filter,
        severity=severity_filter,
    )

    return ContradictionList(
        contradictions=[_contradiction_to_result(c) for c in contradictions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contradiction_id}")
async def get_contradiction(contradiction_id: str):
    """Get specific contradiction details."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    contradiction = _storage.get(contradiction_id)
    if not contradiction:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    return _contradiction_to_result(contradiction)


@router.put("/{contradiction_id}/status")
async def update_status(contradiction_id: str, request: UpdateStatusRequest):
    """
    Update contradiction status.

    Supports analyst workflow: confirmed, dismissed, investigating.
    """
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    # Parse status
    try:
        status = ContradictionStatus[request.status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    # Update
    contradiction = _storage.update_status(
        contradiction_id, status, analyst_id=request.analyst_id
    )

    if not contradiction:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    # Add notes if provided
    if request.notes:
        _storage.add_note(contradiction_id, request.notes, request.analyst_id)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "contradictions.status_updated",
            {
                "contradiction_id": contradiction_id,
                "status": status.value,
                "analyst_id": request.analyst_id,
            },
            source="contradictions-shard",
        )

        # Special events for confirmed/dismissed
        if status == ContradictionStatus.CONFIRMED:
            await _event_bus.emit(
                "contradictions.confirmed",
                {"contradiction_id": contradiction_id},
                source="contradictions-shard",
            )
        elif status == ContradictionStatus.DISMISSED:
            await _event_bus.emit(
                "contradictions.dismissed",
                {"contradiction_id": contradiction_id},
                source="contradictions-shard",
            )

    return _contradiction_to_result(contradiction)


@router.post("/{contradiction_id}/notes")
async def add_notes(contradiction_id: str, request: AddNotesRequest):
    """Add analyst notes to a contradiction."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    contradiction = _storage.add_note(
        contradiction_id, request.notes, analyst_id=request.analyst_id
    )

    if not contradiction:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    return _contradiction_to_result(contradiction)


@router.post("/claims")
async def extract_claims(request: ClaimsRequest):
    """
    Extract and compare claims from text.

    Useful for ad-hoc analysis of text snippets.
    """
    if not _detector:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    # Extract claims
    if request.use_llm:
        claims = await _detector.extract_claims_llm(request.text, request.document_id)
    else:
        claims = _detector.extract_claims_simple(request.text, request.document_id)

    # Convert to dict format
    claims_data = [
        {
            "id": claim.id,
            "text": claim.text,
            "location": claim.location,
            "type": claim.claim_type,
            "confidence": claim.confidence,
        }
        for claim in claims
    ]

    return ClaimExtractionResult(
        claims=claims_data,
        count=len(claims),
        document_id=request.document_id,
    )


@router.get("/stats")
async def get_statistics():
    """Get contradiction statistics."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    stats = _storage.get_statistics()
    return StatsResponse(**stats)


@router.post("/detect-chains")
async def detect_chains():
    """
    Detect contradiction chains across all contradictions.

    A chain exists when: A contradicts B, B contradicts C, etc.
    """
    if not _storage or not _chain_detector:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    # Get all confirmed or detected contradictions
    contradictions = _storage.search(
        status=None  # All statuses except dismissed
    )
    contradictions = [
        c for c in contradictions
        if c.status != ContradictionStatus.DISMISSED
    ]

    # Detect chains
    chains = _chain_detector.detect_chains(contradictions)

    # Create chain objects
    from .models import ContradictionChain
    import uuid

    created_chains = []
    for chain_ids in chains:
        chain = ContradictionChain(
            id=str(uuid.uuid4()),
            contradiction_ids=chain_ids,
            description=f"Chain of {len(chain_ids)} contradictions",
        )
        _storage.create_chain(chain)
        created_chains.append(chain)

    # Emit event
    if _event_bus and created_chains:
        await _event_bus.emit(
            "contradictions.chain_detected",
            {
                "chains_count": len(created_chains),
                "chain_ids": [c.id for c in created_chains],
            },
            source="contradictions-shard",
        )

    return {
        "chains_detected": len(created_chains),
        "chains": [
            {
                "id": chain.id,
                "contradiction_count": len(chain.contradiction_ids),
                "contradictions": chain.contradiction_ids,
            }
            for chain in created_chains
        ],
    }


@router.get("/chains")
async def list_chains():
    """List all detected contradiction chains."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    chains = _storage.list_chains()

    return {
        "count": len(chains),
        "chains": [
            {
                "id": chain.id,
                "contradiction_count": len(chain.contradiction_ids),
                "contradictions": chain.contradiction_ids,
                "description": chain.description,
                "severity": chain.severity.value,
                "created_at": chain.created_at.isoformat(),
            }
            for chain in chains
        ],
    }


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str):
    """Get details of a specific contradiction chain."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    chain = _storage.get_chain(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Chain not found: {chain_id}")

    # Get all contradictions in chain
    contradictions = _storage.get_chain_contradictions(chain_id)

    return {
        "id": chain.id,
        "description": chain.description,
        "severity": chain.severity.value,
        "contradiction_count": len(contradictions),
        "contradictions": [_contradiction_to_result(c) for c in contradictions],
        "created_at": chain.created_at.isoformat(),
        "updated_at": chain.updated_at.isoformat(),
    }


@router.delete("/{contradiction_id}")
async def delete_contradiction(contradiction_id: str):
    """Delete a contradiction (admin operation)."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    success = _storage.delete(contradiction_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    return {"status": "deleted", "contradiction_id": contradiction_id}
