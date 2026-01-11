"""Contradictions Shard API endpoints."""

import logging
from typing import Annotated, Any, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import ContradictionsShard

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
_db = None
_worker_service = None


def init_api(detector, storage, event_bus, chain_detector, worker_service=None):
    """Initialize API with shard dependencies."""
    global _detector, _storage, _event_bus, _chain_detector, _worker_service
    _detector = detector
    _storage = storage
    _event_bus = event_bus
    _chain_detector = chain_detector
    _worker_service = worker_service


def get_shard(request: Request) -> "ContradictionsShard":
    """Get the contradictions shard instance from app state."""
    shard = getattr(request.app.state, "contradictions_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Contradictions shard not available")
    return shard


def set_db_service(db_service):
    """Set the database service for document fetching."""
    global _db
    _db = db_service


async def _get_document_content(doc_id: str) -> dict | None:
    """
    Fetch document content from Frame database.

    Gets document metadata and combines chunk text for content.

    Args:
        doc_id: Document ID to fetch

    Returns:
        Dict with id, content, title or None if not found
    """
    if not _db:
        logger.warning("Database service not available for document fetching")
        return None

    try:
        # Get document metadata
        doc_result = await _db.fetch_one(
            "SELECT id, filename FROM arkham_frame.documents WHERE id = :id",
            {"id": doc_id}
        )

        if not doc_result:
            logger.warning(f"Document not found: {doc_id}")
            return None

        # Get all chunks for the document, ordered by chunk_index
        chunks = await _db.fetch_all(
            """SELECT text FROM arkham_frame.chunks
               WHERE document_id = :id
               ORDER BY chunk_index""",
            {"id": doc_id}
        )

        # Combine chunk text
        content = "\n\n".join(c["text"] for c in chunks if c.get("text"))

        if not content:
            logger.warning(f"Document {doc_id} has no chunk content")
            return None

        return {
            "id": doc_id,
            "content": content,
            "title": doc_result.get("filename", f"Document {doc_id}")
        }

    except Exception as e:
        logger.error(f"Failed to fetch document {doc_id}: {e}")
        return None


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

    # Fetch actual document content from Frame
    doc_a = await _get_document_content(request.doc_a_id)
    doc_b = await _get_document_content(request.doc_b_id)

    if not doc_a:
        raise HTTPException(status_code=404, detail=f"Document not found: {request.doc_a_id}")
    if not doc_b:
        raise HTTPException(status_code=404, detail=f"Document not found: {request.doc_b_id}")

    doc_a_text = doc_a["content"]
    doc_b_text = doc_b["content"]

    logger.info(f"Fetched documents: {doc_a.get('title')} ({len(doc_a_text)} chars) vs {doc_b.get('title')} ({len(doc_b_text)} chars)")

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
            await _storage.create(contradiction)
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

    Set async_mode=True to use background workers for large batches.
    In async mode, returns job IDs instead of immediate results.
    """
    import uuid

    if not _detector or not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    logger.info(f"Batch analyzing {len(request.document_pairs)} document pairs (async={request.async_mode})")

    # Async mode: use llm-analysis worker for background processing
    if request.async_mode:
        if not _worker_service:
            raise HTTPException(
                status_code=503,
                detail="Worker service not available for async mode"
            )

        job_ids = []
        for doc_a_id, doc_b_id in request.document_pairs:
            job_id = str(uuid.uuid4())
            try:
                # Fetch document content for the worker
                doc_a = await _get_document_content(doc_a_id)
                doc_b = await _get_document_content(doc_b_id)

                if not doc_a or not doc_b:
                    logger.warning(f"Skipping pair {doc_a_id}/{doc_b_id}: document not found")
                    continue

                # Enqueue to llm-analysis worker
                await _worker_service.enqueue(
                    pool="llm-analysis",
                    job_id=job_id,
                    job_type="find_contradictions",
                    payload={
                        "operation": "find_contradictions",
                        "text_a": doc_a["content"],
                        "text_b": doc_b["content"],
                        "context": f"Document A: {doc_a.get('title', doc_a_id)}, Document B: {doc_b.get('title', doc_b_id)}",
                        # Metadata for result processing
                        "_doc_a_id": doc_a_id,
                        "_doc_b_id": doc_b_id,
                        "_threshold": request.threshold,
                    },
                    priority=5,
                )
                job_ids.append({
                    "job_id": job_id,
                    "doc_a_id": doc_a_id,
                    "doc_b_id": doc_b_id,
                })
            except Exception as e:
                logger.error(f"Failed to enqueue {doc_a_id} vs {doc_b_id}: {e}")

        return {
            "async": True,
            "pairs_queued": len(job_ids),
            "jobs": job_ids,
            "message": f"Queued {len(job_ids)} pairs for background analysis. Poll /api/contradictions/jobs/<job_id> for results.",
        }

    # Sync mode: process sequentially
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
        "async": False,
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

    contradictions = await _storage.get_by_document(doc_id, include_related=include_chains)

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
    contradictions, total = await _storage.list_all(
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

    stats = await _storage.get_statistics()
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
    contradictions = await _storage.search(
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
        await _storage.create_chain(chain)
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

    chains = await _storage.list_chains()

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

    chain = await _storage.get_chain(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Chain not found: {chain_id}")

    # Get all contradictions in chain
    contradictions = await _storage.get_chain_contradictions(chain_id)

    return {
        "id": chain.id,
        "description": chain.description,
        "severity": chain.severity.value,
        "contradiction_count": len(contradictions),
        "contradictions": [_contradiction_to_result(c) for c in contradictions],
        "created_at": chain.created_at.isoformat(),
        "updated_at": chain.updated_at.isoformat(),
    }


# NOTE: These non-parameterized routes MUST be defined BEFORE /{contradiction_id}
# to avoid FastAPI treating "count" or "pending" as an ID


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status and result of an async analysis job.

    Use this to poll for results after submitting a batch request with async_mode=True.
    """
    if not _worker_service:
        raise HTTPException(status_code=503, detail="Worker service not available")

    try:
        job = await _worker_service.get_job_from_db(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        response = {
            "job_id": job_id,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

        if job.status == "completed":
            response["result"] = job.result
            response["completed_at"] = job.completed_at.isoformat() if job.completed_at else None
        elif job.status in ("failed", "dead"):
            response["error"] = job.error

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {e}")


@router.get("/count")
async def get_count():
    """Get total contradiction count (for navigation badge)."""
    if not _storage:
        return {"count": 0}

    stats = await _storage.get_statistics()
    return {"count": stats.get("total_contradictions", 0)}


@router.get("/pending/count")
async def get_pending_count():
    """Get pending contradiction count (for navigation badge)."""
    if not _storage:
        return {"count": 0}

    stats = await _storage.get_statistics()
    by_status = stats.get("by_status", {})
    # Pending = detected + investigating (not yet confirmed/dismissed)
    pending = by_status.get("detected", 0) + by_status.get("investigating", 0)
    return {"count": pending}


@router.get("/{contradiction_id}")
async def get_contradiction(contradiction_id: str):
    """Get specific contradiction details."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    contradiction = await _storage.get(contradiction_id)
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
    contradiction = await _storage.update_status(
        contradiction_id, status, analyst_id=request.analyst_id
    )

    if not contradiction:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    # Add notes if provided
    if request.notes:
        await _storage.add_note(contradiction_id, request.notes, request.analyst_id)

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

    contradiction = await _storage.add_note(
        contradiction_id, request.notes, analyst_id=request.analyst_id
    )

    if not contradiction:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    return _contradiction_to_result(contradiction)


@router.delete("/{contradiction_id}")
async def delete_contradiction(contradiction_id: str):
    """Delete a contradiction (admin operation)."""
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    success = await _storage.delete(contradiction_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    return {"status": "deleted", "contradiction_id": contradiction_id}


class BulkStatusRequest(BaseModel):
    """Request model for bulk status update."""
    contradiction_ids: list[str]
    status: str
    analyst_id: str | None = None
    notes: str | None = None


@router.post("/bulk-status")
async def bulk_update_status(request: BulkStatusRequest):
    """
    Update status for multiple contradictions at once.

    Useful for bulk triage operations (confirm all, dismiss all, etc.).
    """
    if not _storage:
        raise HTTPException(status_code=503, detail="Contradiction service not initialized")

    # Parse status
    try:
        status = ContradictionStatus[request.status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    updated = []
    failed = []

    for contradiction_id in request.contradiction_ids:
        try:
            contradiction = await _storage.update_status(
                contradiction_id, status, analyst_id=request.analyst_id
            )
            if contradiction:
                if request.notes:
                    await _storage.add_note(contradiction_id, request.notes, request.analyst_id)
                updated.append(contradiction_id)
            else:
                failed.append({"id": contradiction_id, "error": "Not found"})
        except Exception as e:
            failed.append({"id": contradiction_id, "error": str(e)})

    # Emit bulk event
    if _event_bus and updated:
        await _event_bus.emit(
            "contradictions.bulk_status_updated",
            {
                "contradiction_ids": updated,
                "status": status.value,
                "count": len(updated),
                "analyst_id": request.analyst_id,
            },
            source="contradictions-shard",
        )

    return {
        "updated": len(updated),
        "failed": len(failed),
        "updated_ids": updated,
        "failures": failed,
    }


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""
    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: str | None = None
    message: str | None = None
    conversation_history: list[dict[str, str]] | None = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for contradiction analysis.

    Provides AI-powered interpretation of contradictions including:
    - Contradiction significance assessment
    - Resolution suggestions
    - Source reliability comparison
    - Chain of contradiction analysis
    - Contextual interpretation
    """
    shard = get_shard(request)
    frame = shard._frame

    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(
            status_code=503,
            detail="AI Analyst service not available"
        )

    # Build context from request
    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Parse depth
    try:
        depth = AnalysisDepth(body.depth)
    except ValueError:
        depth = AnalysisDepth.QUICK

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=msg["role"], content=msg["content"])
            for msg in body.conversation_history
        ]

    analysis_request = AnalysisRequest(
        shard="contradictions",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Stream the response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
