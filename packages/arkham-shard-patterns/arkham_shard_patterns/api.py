"""
Patterns Shard - API Routes

FastAPI routes for pattern detection and analysis.
"""

from typing import Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request

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

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def get_shard(request: Request) -> "PatternsShard":
    """Get the shard instance from app state."""
    shard = getattr(request.app.state, "patterns_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Patterns shard not available")
    return shard


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
    shard = get_shard(request)
    return await shard.create_pattern(
        name=body.name,
        description=body.description,
        pattern_type=body.pattern_type,
        criteria=body.criteria,
        confidence=body.confidence,
        metadata=body.metadata,
    )


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
async def analyze_for_patterns(body: PatternAnalysisRequest, request: Request):
    """Analyze documents or text for patterns."""
    shard = get_shard(request)
    return await shard.analyze_documents(body)


@router.post("/detect", response_model=PatternAnalysisResult)
async def detect_patterns(
    request: Request,
    text: str,
    pattern_types: Optional[str] = None,
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
):
    """Detect patterns in provided text."""
    shard = get_shard(request)

    types = None
    if pattern_types:
        types = [PatternType(t.strip()) for t in pattern_types.split(",")]

    analysis_request = PatternAnalysisRequest(
        text=text,
        pattern_types=types,
        min_confidence=min_confidence,
    )

    return await shard.analyze_documents(analysis_request)


@router.post("/correlate", response_model=CorrelationResult)
async def find_correlations(body: CorrelationRequest, request: Request):
    """Find correlations between entities."""
    shard = get_shard(request)
    return await shard.find_correlations(body)


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
