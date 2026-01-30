"""
Patterns Shard - API Routes

FastAPI routes for pattern detection and analysis.
"""

import time
from typing import Any, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .models import (
    CorrelationRequest,
    CorrelationResult,
    Pattern,
    PatternAnalysisRequest,
    PatternAnalysisResult,
    PatternCreate,
    PatternFilter,
    PatternListResponse,
    PatternMatch,
    PatternMatchCreate,
    PatternMatchListResponse,
    PatternStatistics,
    PatternStatus,
    PatternType,
    PatternUpdate,
    DetectionMethod,
)

if TYPE_CHECKING:
    from .shard import PatternsShard

# Auth / project scoping
try:
    from arkham_frame.auth import current_active_user, require_project_member
except ImportError:
    async def current_active_user():
        return None

    async def require_project_member(*args, **kwargs):
        return None

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

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def get_shard(request: Request) -> "PatternsShard":
    """Get the shard instance from app state."""
    shard = getattr(request.app.state, "patterns_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Patterns shard not available")
    return shard


async def _require_active_project_id(request: Request, shard: "PatternsShard", user: Any) -> str:
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


# === Health & Status ===

@router.get("/health")
async def health(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)
    return {
        "status": "healthy",
        "shard": shard.name,
        "version": shard.version,
        "initialized": shard._initialized,
    }


@router.get("/count")
async def get_count(request: Request, status: Optional[str] = None):
    """Get pattern count (for navigation badge)."""
    shard = get_shard(request)
    count = await shard.get_count(status)
    return {"count": count}


@router.get("/stats", response_model=PatternStatistics)
async def get_statistics(request: Request):
    """Get pattern statistics."""
    shard = get_shard(request)
    return await shard.get_statistics()


@router.get("/capabilities")
async def get_capabilities(request: Request):
    """Get available capabilities based on services."""
    shard = get_shard(request)
    return {
        "llm_available": shard._llm is not None and shard._llm.is_available() if shard._llm else False,
        "vectors_available": shard._vectors is not None,
        "workers_available": shard._workers is not None,
        "pattern_types": [t.value for t in PatternType],
        "detection_methods": [m.value for m in DetectionMethod],
    }


# === Patterns CRUD ===

@router.get("/", response_model=PatternListResponse)
async def list_patterns(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    pattern_type: Optional[PatternType] = None,
    status: Optional[PatternStatus] = None,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_matches: Optional[int] = Query(None, ge=0),
    detection_method: Optional[DetectionMethod] = None,
    q: Optional[str] = None,
):
    """List patterns with optional filtering."""
    shard = get_shard(request)

    filter_obj = PatternFilter(
        pattern_type=pattern_type,
        status=status,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_matches=min_matches,
        detection_method=detection_method,
        search_text=q,
    )

    offset = (page - 1) * page_size
    patterns = await shard.list_patterns(
        filter=filter_obj,
        limit=page_size,
        offset=offset,
        sort=sort,
        order=order,
    )

    # Get total count for pagination
    total = await shard.get_count(status.value if status else None)

    return PatternListResponse(
        items=patterns,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=Pattern)
async def create_pattern(body: PatternCreate, request: Request):
    """Create a new pattern."""
    with log_operation("patterns.create", pattern_type=body.pattern_type.value if hasattr(body.pattern_type, 'value') else str(body.pattern_type)) as event:
        try:
            if event:
                event.context("shard", "patterns")
                event.context("operation", "create")
                event.input(
                    pattern_type=body.pattern_type.value if hasattr(body.pattern_type, 'value') else str(body.pattern_type),
                    name=body.name,
                    confidence=body.confidence,
                    has_metadata=body.metadata is not None,
                )

            shard = get_shard(request)
            pattern = await shard.create_pattern(
                name=body.name,
                description=body.description,
                pattern_type=body.pattern_type,
                criteria=body.criteria,
                confidence=body.confidence,
                metadata=body.metadata,
            )

            if event:
                event.output(
                    pattern_id=pattern.id,
                    status=pattern.status.value if hasattr(pattern.status, 'value') else str(pattern.status),
                )

            return pattern
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


@router.get("/{pattern_id}", response_model=Pattern)
async def get_pattern(pattern_id: str, request: Request):
    """Get a pattern by ID."""
    shard = get_shard(request)
    pattern = await shard.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.put("/{pattern_id}", response_model=Pattern)
async def update_pattern(pattern_id: str, body: PatternUpdate, request: Request):
    """Update a pattern."""
    shard = get_shard(request)
    pattern = await shard.update_pattern(
        pattern_id=pattern_id,
        name=body.name,
        description=body.description,
        criteria=body.criteria,
        confidence=body.confidence,
        status=body.status,
        metadata=body.metadata,
    )
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.delete("/{pattern_id}")
async def delete_pattern(pattern_id: str, request: Request):
    """Delete a pattern."""
    shard = get_shard(request)
    success = await shard.delete_pattern(pattern_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return {"deleted": True, "pattern_id": pattern_id}


@router.post("/{pattern_id}/confirm", response_model=Pattern)
async def confirm_pattern(pattern_id: str, request: Request, notes: Optional[str] = None):
    """Confirm a pattern as valid."""
    shard = get_shard(request)
    pattern = await shard.confirm_pattern(pattern_id, notes)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.post("/{pattern_id}/dismiss", response_model=Pattern)
async def dismiss_pattern(pattern_id: str, request: Request, notes: Optional[str] = None):
    """Dismiss a pattern as noise/false positive."""
    shard = get_shard(request)
    pattern = await shard.dismiss_pattern(pattern_id, notes)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


# === Pattern Matches ===

@router.get("/{pattern_id}/matches", response_model=PatternMatchListResponse)
async def get_pattern_matches(
    pattern_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get matches for a pattern."""
    shard = get_shard(request)

    # Verify pattern exists
    pattern = await shard.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    offset = (page - 1) * page_size
    matches = await shard.get_pattern_matches(
        pattern_id=pattern_id,
        limit=page_size,
        offset=offset,
    )

    total = await shard.get_match_count(pattern_id)

    return PatternMatchListResponse(
        items=matches,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{pattern_id}/matches", response_model=PatternMatch)
async def add_match(pattern_id: str, body: PatternMatchCreate, request: Request):
    """Add a match to a pattern."""
    shard = get_shard(request)

    # Verify pattern exists
    pattern = await shard.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    return await shard.add_match(pattern_id, body)


@router.delete("/{pattern_id}/matches/{match_id}")
async def remove_match(pattern_id: str, match_id: str, request: Request):
    """Remove a match from a pattern."""
    shard = get_shard(request)
    success = await shard.remove_match(pattern_id, match_id)
    return {"removed": success, "match_id": match_id}


# === Analysis ===

@router.post("/analyze", response_model=PatternAnalysisResult)
async def analyze_for_patterns(
    body: PatternAnalysisRequest,
    request: Request,
    user=Depends(current_active_user),
):
    """Analyze documents or text for patterns."""
    with log_operation("patterns.analyze") as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "patterns")
                event.context("operation", "analyze")
                event.input(
                    document_count=len(body.document_ids) if body.document_ids else 0,
                    has_text=body.text is not None,
                    pattern_types=len(body.pattern_types) if body.pattern_types else 0,
                    min_confidence=body.min_confidence,
                )

            shard = get_shard(request)
            active_project_id = await _require_active_project_id(request, shard, user)
            result = await shard.analyze_documents(body, project_id=active_project_id)

            duration_ms = (time.time() - start_time) * 1000

            if event:
                event.output(
                    patterns_found=len(result.patterns) if result.patterns else 0,
                    matches_found=len(result.matches) if result.matches else 0,
                    duration_ms=duration_ms,
                )

            return result
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


@router.post("/detect", response_model=PatternAnalysisResult)
async def detect_patterns(
    request: Request,
    text: str,
    pattern_types: Optional[str] = None,
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
):
    """Detect patterns in provided text."""
    with log_operation("patterns.detect") as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "patterns")
                event.context("operation", "detect")
                event.input(
                    text_length=len(text) if text else 0,
                    pattern_types=pattern_types,
                    min_confidence=min_confidence,
                )

            shard = get_shard(request)

            types = None
            if pattern_types:
                types = [PatternType(t.strip()) for t in pattern_types.split(",")]

            analysis_request = PatternAnalysisRequest(
                text=text,
                pattern_types=types,
                min_confidence=min_confidence,
            )

            result = await shard.analyze_documents(analysis_request)

            duration_ms = (time.time() - start_time) * 1000

            if event:
                event.output(
                    patterns_found=len(result.patterns) if result.patterns else 0,
                    matches_found=len(result.matches) if result.matches else 0,
                    duration_ms=duration_ms,
                )

            return result
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


@router.post("/correlate", response_model=CorrelationResult)
async def find_correlations(body: CorrelationRequest, request: Request):
    """Find correlations between entities."""
    with log_operation("patterns.correlate") as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "patterns")
                event.context("operation", "correlate")
                event.input(
                    entity_count=len(body.entity_ids) if body.entity_ids else 0,
                    document_count=len(body.document_ids) if body.document_ids else 0,
                )

            shard = get_shard(request)
            result = await shard.find_correlations(body)

            duration_ms = (time.time() - start_time) * 1000

            if event:
                event.output(
                    correlation_count=len(result.correlations) if result.correlations else 0,
                    duration_ms=duration_ms,
                )

            return result
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


# === Batch Operations ===

@router.post("/batch/confirm")
async def batch_confirm(pattern_ids: list[str], request: Request):
    """Confirm multiple patterns."""
    shard = get_shard(request)
    results = []
    for pattern_id in pattern_ids:
        pattern = await shard.confirm_pattern(pattern_id)
        results.append({
            "pattern_id": pattern_id,
            "success": pattern is not None,
        })
    return {
        "processed": len(pattern_ids),
        "results": results,
    }


@router.post("/batch/dismiss")
async def batch_dismiss(pattern_ids: list[str], request: Request):
    """Dismiss multiple patterns."""
    shard = get_shard(request)
    results = []
    for pattern_id in pattern_ids:
        pattern = await shard.dismiss_pattern(pattern_id)
        results.append({
            "pattern_id": pattern_id,
            "success": pattern is not None,
        })
    return {
        "processed": len(pattern_ids),
        "results": results,
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
    AI Junior Analyst endpoint for pattern analysis.

    Provides AI-powered interpretation of patterns including:
    - Pattern significance assessment
    - Correlation interpretation
    - Trend analysis
    - Predictive insights
    - Related pattern discovery
    """
    shard = get_shard(request)
    frame = shard.frame

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
        shard="patterns",
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
