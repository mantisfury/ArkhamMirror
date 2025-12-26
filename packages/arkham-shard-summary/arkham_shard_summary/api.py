"""
Summary Shard API Routes

FastAPI endpoints for summary generation and management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .models import (
    Summary,
    SummaryType,
    SummaryStatus,
    SourceType,
    SummaryLength,
    SummaryRequest,
    SummaryResult,
    SummaryFilter,
    SummaryStatistics,
    BatchSummaryRequest,
    BatchSummaryResult,
)

router = APIRouter(prefix="/api/summary", tags=["summary"])

# Global shard instance (set by shard initialization)
_shard = None


def init_api(shard):
    """Initialize API with shard instance."""
    global _shard
    _shard = shard


def get_shard():
    """Get the shard instance."""
    if _shard is None:
        raise HTTPException(status_code=503, detail="Summary shard not initialized")
    return _shard


# === Pydantic API Models ===

class SummaryCreate(BaseModel):
    """Request to create a new summary."""
    source_type: SourceType
    source_ids: List[str] = Field(..., min_items=1, description="IDs of sources to summarize")
    summary_type: SummaryType = SummaryType.DETAILED
    target_length: SummaryLength = SummaryLength.MEDIUM
    focus_areas: List[str] = Field(default_factory=list)
    exclude_topics: List[str] = Field(default_factory=list)
    include_key_points: bool = True
    include_title: bool = True
    tags: List[str] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    """Summary response model."""
    id: str
    summary_type: str
    status: str
    source_type: str
    source_ids: List[str]
    content: str
    key_points: List[str]
    title: Optional[str]
    model_used: Optional[str]
    token_count: int
    word_count: int
    target_length: str
    confidence: float
    processing_time_ms: float
    created_at: str
    tags: List[str]


class SummaryListResponse(BaseModel):
    """Paginated summary list response."""
    items: List[SummaryResponse]
    total: int
    page: int
    page_size: int


class CountResponse(BaseModel):
    """Count response for badge."""
    count: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    shard: str
    llm_available: bool


class CapabilitiesResponse(BaseModel):
    """Capabilities response."""
    llm_available: bool
    workers_available: bool
    summary_types: List[str]
    source_types: List[str]
    target_lengths: List[str]


class SummaryTypesResponse(BaseModel):
    """Available summary types."""
    types: List[dict]


class BatchCreate(BaseModel):
    """Batch summary creation request."""
    requests: List[SummaryCreate]
    parallel: bool = False
    stop_on_error: bool = False


class BatchResponse(BaseModel):
    """Batch operation response."""
    total: int
    successful: int
    failed: int
    summaries: List[SummaryResult]
    errors: List[str]
    total_processing_time_ms: float


# === API Endpoints ===

@router.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.

    Returns service status and LLM availability.
    """
    shard = get_shard()
    return {
        "status": "healthy",
        "shard": "summary",
        "llm_available": shard.llm_available,
    }


@router.get("/count", response_model=CountResponse)
async def get_count():
    """
    Get total summary count (for navigation badge).

    Returns:
        Count of all summaries in system
    """
    shard = get_shard()
    count = await shard.get_count()
    return {"count": count}


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities():
    """
    Get shard capabilities.

    Shows what features are available based on service availability.
    """
    shard = get_shard()
    return {
        "llm_available": shard.llm_available,
        "workers_available": shard._workers is not None,
        "summary_types": [t.value for t in SummaryType],
        "source_types": [t.value for t in SourceType],
        "target_lengths": [t.value for t in SummaryLength],
    }


@router.get("/types", response_model=SummaryTypesResponse)
async def get_types():
    """
    Get available summary types with descriptions.

    Returns:
        List of summary types and their descriptions
    """
    types = [
        {
            "value": SummaryType.BRIEF.value,
            "label": "Brief",
            "description": "Short 1-2 sentence summary",
        },
        {
            "value": SummaryType.DETAILED.value,
            "label": "Detailed",
            "description": "Comprehensive multi-paragraph summary",
        },
        {
            "value": SummaryType.EXECUTIVE.value,
            "label": "Executive",
            "description": "Executive summary with key findings",
        },
        {
            "value": SummaryType.BULLET_POINTS.value,
            "label": "Bullet Points",
            "description": "Key points as bullet list",
        },
        {
            "value": SummaryType.ABSTRACT.value,
            "label": "Abstract",
            "description": "Academic-style abstract",
        },
    ]
    return {"types": types}


@router.get("/", response_model=SummaryListResponse)
async def list_summaries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    summary_type: Optional[str] = Query(None, description="Filter by summary type"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    q: Optional[str] = Query(None, description="Search in summary content"),
):
    """
    List all summaries with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (1-100)
        summary_type: Filter by summary type
        source_type: Filter by source type
        source_id: Filter by specific source ID
        status: Filter by status
        q: Search query for content

    Returns:
        Paginated list of summaries
    """
    shard = get_shard()

    # Build filter
    filter = SummaryFilter()
    if summary_type:
        try:
            filter.summary_type = SummaryType(summary_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid summary_type: {summary_type}")

    if source_type:
        try:
            filter.source_type = SourceType(source_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source_type: {source_type}")

    if source_id:
        filter.source_id = source_id

    if status:
        try:
            filter.status = SummaryStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if q:
        filter.search_text = q

    # Get summaries
    summaries = await shard.list_summaries(filter, page, page_size)
    total = await shard.get_count()

    # Convert to response model
    items = [
        SummaryResponse(
            id=s.id,
            summary_type=s.summary_type.value,
            status=s.status.value,
            source_type=s.source_type.value,
            source_ids=s.source_ids,
            content=s.content,
            key_points=s.key_points,
            title=s.title,
            model_used=s.model_used,
            token_count=s.token_count,
            word_count=s.word_count,
            target_length=s.target_length.value,
            confidence=s.confidence,
            processing_time_ms=s.processing_time_ms,
            created_at=s.created_at.isoformat(),
            tags=s.tags,
        )
        for s in summaries
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/", response_model=SummaryResult)
async def create_summary(request: SummaryCreate):
    """
    Generate a new summary.

    Args:
        request: Summary creation request

    Returns:
        Generated summary result
    """
    shard = get_shard()

    # Convert to internal request model
    summary_request = SummaryRequest(
        source_type=request.source_type,
        source_ids=request.source_ids,
        summary_type=request.summary_type,
        target_length=request.target_length,
        focus_areas=request.focus_areas,
        exclude_topics=request.exclude_topics,
        include_key_points=request.include_key_points,
        include_title=request.include_title,
        tags=request.tags,
    )

    result = await shard.generate_summary(summary_request)
    return result


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(summary_id: str):
    """
    Get a summary by ID.

    Args:
        summary_id: Summary identifier

    Returns:
        Summary details
    """
    shard = get_shard()
    summary = await shard.get_summary(summary_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    return SummaryResponse(
        id=summary.id,
        summary_type=summary.summary_type.value,
        status=summary.status.value,
        source_type=summary.source_type.value,
        source_ids=summary.source_ids,
        content=summary.content,
        key_points=summary.key_points,
        title=summary.title,
        model_used=summary.model_used,
        token_count=summary.token_count,
        word_count=summary.word_count,
        target_length=summary.target_length.value,
        confidence=summary.confidence,
        processing_time_ms=summary.processing_time_ms,
        created_at=summary.created_at.isoformat(),
        tags=summary.tags,
    )


@router.delete("/{summary_id}")
async def delete_summary(summary_id: str):
    """
    Delete a summary.

    Args:
        summary_id: Summary identifier

    Returns:
        Success status
    """
    shard = get_shard()
    deleted = await shard.delete_summary(summary_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")

    return {"deleted": True, "summary_id": summary_id}


@router.post("/batch", response_model=BatchResponse)
async def create_batch_summaries(request: BatchCreate):
    """
    Generate summaries for multiple sources in batch.

    Args:
        request: Batch summary request

    Returns:
        Batch operation results
    """
    shard = get_shard()

    # Convert requests
    summary_requests = [
        SummaryRequest(
            source_type=req.source_type,
            source_ids=req.source_ids,
            summary_type=req.summary_type,
            target_length=req.target_length,
            focus_areas=req.focus_areas,
            exclude_topics=req.exclude_topics,
            include_key_points=req.include_key_points,
            include_title=req.include_title,
            tags=req.tags,
        )
        for req in request.requests
    ]

    batch_request = BatchSummaryRequest(
        requests=summary_requests,
        parallel=request.parallel,
        stop_on_error=request.stop_on_error,
    )

    result = await shard.generate_batch_summaries(batch_request)
    return result


@router.get("/document/{doc_id}", response_model=SummaryResponse)
async def get_or_generate_document_summary(
    doc_id: str,
    summary_type: str = Query("detailed", description="Type of summary"),
    regenerate: bool = Query(False, description="Force regeneration"),
):
    """
    Get existing summary for a document or generate new one.

    Args:
        doc_id: Document identifier
        summary_type: Type of summary to generate
        regenerate: Force regeneration even if exists

    Returns:
        Summary for the document
    """
    shard = get_shard()

    # Check for existing summary
    if not regenerate:
        filter = SummaryFilter(
            source_type=SourceType.DOCUMENT,
            source_id=doc_id,
        )
        summaries = await shard.list_summaries(filter, page=1, page_size=1)
        if summaries:
            summary = summaries[0]
            return SummaryResponse(
                id=summary.id,
                summary_type=summary.summary_type.value,
                status=summary.status.value,
                source_type=summary.source_type.value,
                source_ids=summary.source_ids,
                content=summary.content,
                key_points=summary.key_points,
                title=summary.title,
                model_used=summary.model_used,
                token_count=summary.token_count,
                word_count=summary.word_count,
                target_length=summary.target_length.value,
                confidence=summary.confidence,
                processing_time_ms=summary.processing_time_ms,
                created_at=summary.created_at.isoformat(),
                tags=summary.tags,
            )

    # Generate new summary
    try:
        summary_type_enum = SummaryType(summary_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid summary_type: {summary_type}")

    request = SummaryRequest(
        source_type=SourceType.DOCUMENT,
        source_ids=[doc_id],
        summary_type=summary_type_enum,
    )

    result = await shard.generate_summary(request)

    if result.status == SummaryStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail=result.error_message or "Summary generation failed",
        )

    # Fetch the created summary
    summary = await shard.get_summary(result.summary_id)
    if not summary:
        raise HTTPException(status_code=500, detail="Summary created but not found")

    return SummaryResponse(
        id=summary.id,
        summary_type=summary.summary_type.value,
        status=summary.status.value,
        source_type=summary.source_type.value,
        source_ids=summary.source_ids,
        content=summary.content,
        key_points=summary.key_points,
        title=summary.title,
        model_used=summary.model_used,
        token_count=summary.token_count,
        word_count=summary.word_count,
        target_length=summary.target_length.value,
        confidence=summary.confidence,
        processing_time_ms=summary.processing_time_ms,
        created_at=summary.created_at.isoformat(),
        tags=summary.tags,
    )


@router.get("/stats", response_model=SummaryStatistics)
async def get_statistics():
    """
    Get summary statistics.

    Returns:
        Aggregate statistics about all summaries
    """
    shard = get_shard()
    stats = await shard.get_statistics()
    return stats
