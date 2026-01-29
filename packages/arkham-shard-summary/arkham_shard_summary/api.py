"""
Summary Shard API Routes

FastAPI endpoints for summary generation and management.
"""

import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
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

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None

router = APIRouter(prefix="/api/summary", tags=["summary"])

# Auth / project scoping
try:
    from arkham_frame.auth import current_active_user, require_project_member
except ImportError:
    async def current_active_user():
        return None

    async def require_project_member(*args, **kwargs):
        return None


def get_shard(request: Request):
    """Get the shard instance from app state."""
    shard = getattr(request.app.state, "summary_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Summary shard not available")
    return shard


async def _require_active_project_id(request: Request, shard, user) -> str:
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
    async_mode: bool = False  # If True, use llm-enrich worker for background processing


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
async def health(request: Request):
    """
    Health check endpoint.

    Returns service status and LLM availability.
    """
    shard = get_shard(request)
    return {
        "status": "healthy",
        "shard": "summary",
        "llm_available": shard.llm_available,
    }


@router.get("/count", response_model=CountResponse)
async def get_count(request: Request):
    """
    Get total summary count (for navigation badge).

    Returns:
        Count of all summaries in system
    """
    shard = get_shard(request)
    count = await shard.get_count()
    return {"count": count}


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(request: Request):
    """
    Get shard capabilities.

    Shows what features are available based on service availability.
    """
    shard = get_shard(request)
    return {
        "llm_available": shard.llm_available,
        "workers_available": shard._workers is not None,
        "summary_types": [t.value for t in SummaryType],
        "source_types": [t.value for t in SourceType],
        "target_lengths": [t.value for t in SummaryLength],
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    """
    Get status and result of an async summarization job.

    Use this to poll for results after submitting a batch request with async_mode=True.
    """
    shard = get_shard(request)

    if not shard._workers:
        raise HTTPException(status_code=503, detail="Worker service not available")

    try:
        job = await shard._workers.get_job_from_db(job_id)
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


@router.get("/stats", response_model=SummaryStatistics)
async def get_statistics(request: Request):
    """
    Get summary statistics.

    Returns:
        Aggregate statistics about all summaries
    """
    shard = get_shard(request)
    stats = await shard.get_statistics()
    return stats


@router.get("/", response_model=SummaryListResponse)
async def list_summaries(
    request: Request,
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
    shard = get_shard(request)

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
async def create_summary(body: SummaryCreate, request: Request):
    """
    Generate a new summary.

    Args:
        body: Summary creation request

    Returns:
        Generated summary result
    """
    with log_operation("summary.generate", source_type=body.source_type.value if hasattr(body.source_type, 'value') else str(body.source_type), source_count=len(body.source_ids)) as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "summary")
                event.context("operation", "generate")
                event.input(
                    source_type=body.source_type.value if hasattr(body.source_type, 'value') else str(body.source_type),
                    source_count=len(body.source_ids),
                    summary_type=body.summary_type.value if hasattr(body.summary_type, 'value') else str(body.summary_type),
                    target_length=body.target_length.value if hasattr(body.target_length, 'value') else str(body.target_length),
                    include_key_points=body.include_key_points,
                    include_title=body.include_title,
                    focus_areas_count=len(body.focus_areas),
                    exclude_topics_count=len(body.exclude_topics),
                )

            shard = get_shard(request)

            # Convert to internal request model
            summary_request = SummaryRequest(
                source_type=body.source_type,
                source_ids=body.source_ids,
                summary_type=body.summary_type,
                target_length=body.target_length,
                focus_areas=body.focus_areas,
                exclude_topics=body.exclude_topics,
                include_key_points=body.include_key_points,
                include_title=body.include_title,
                tags=body.tags,
            )

            result = await shard.generate_summary(summary_request)

            duration_ms = (time.time() - start_time) * 1000

            if event:
                event.output(
                    summary_id=result.summary_id,
                    status=result.status.value if hasattr(result.status, 'value') else str(result.status),
                    processing_time_ms=result.processing_time_ms if hasattr(result, 'processing_time_ms') else duration_ms,
                )

            return result
        except Exception as e:
            if event:
                event.error(str(e), exc_info=True)
            raise


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(summary_id: str, request: Request):
    """
    Get a summary by ID.

    Args:
        summary_id: Summary identifier

    Returns:
        Summary details
    """
    shard = get_shard(request)
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
async def delete_summary(summary_id: str, request: Request):
    """
    Delete a summary.

    Args:
        summary_id: Summary identifier

    Returns:
        Success status
    """
    shard = get_shard(request)
    deleted = await shard.delete_summary(summary_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")

    return {"deleted": True, "summary_id": summary_id}


@router.post("/batch", response_model=BatchResponse)
async def create_batch_summaries(body: BatchCreate, request: Request):
    """
    Generate summaries for multiple sources in batch.

    Args:
        body: Batch summary request

    Returns:
        Batch operation results
    """
    shard = get_shard(request)

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
        for req in body.requests
    ]

    batch_request = BatchSummaryRequest(
        requests=summary_requests,
        parallel=body.parallel,
        stop_on_error=body.stop_on_error,
        async_mode=body.async_mode,
    )

    result = await shard.generate_batch_summaries(batch_request)
    return result


@router.get("/document/{doc_id}", response_model=SummaryResponse)
async def get_or_generate_document_summary(
    doc_id: str,
    request: Request,
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
    shard = get_shard(request)

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

    summary_request = SummaryRequest(
        source_type=SourceType.DOCUMENT,
        source_ids=[doc_id],
        summary_type=summary_type_enum,
    )

    result = await shard.generate_summary(summary_request)

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


# === Source Browser Endpoints ===


class SourceItem(BaseModel):
    """Source item for picker."""
    id: str
    name: str
    type: str
    preview: str = ""
    created_at: Optional[str] = None
    metadata: dict = {}


class SourceListResponse(BaseModel):
    """Source list response."""
    items: List[SourceItem]
    total: int
    page: int
    page_size: int


@router.get("/sources/documents", response_model=SourceListResponse)
async def browse_documents(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user=Depends(current_active_user),
):
    """
    Browse available documents for summarization.

    Returns list of documents that can be selected for summary generation.
    """
    shard = get_shard(request)
    db = shard._db

    if not db:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    # Build query for documents
    offset = (page - 1) * page_size
    items = []
    total = 0

    try:
        # Try arkham_frame.documents first
        count_query = "SELECT COUNT(*) as count FROM arkham_frame.documents WHERE 1=1"
        query = """
            SELECT id, filename, mime_type, file_size, created_at, status, metadata
            FROM arkham_frame.documents
            WHERE 1=1
        """
        params = {}

        if q:
            query += " AND filename ILIKE :q"
            count_query += " AND filename ILIKE :q"
            params["q"] = f"%{q}%"

        if not project_id:
            project_id = await _require_active_project_id(request, shard, user)
        else:
            await require_project_member(str(project_id), user, request)

        if project_id:
            query += " AND project_id = :project_id"
            count_query += " AND project_id = :project_id"
            params["project_id"] = project_id

        # Get total count
        count_row = await db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        # Get items
        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
        rows = await db.fetch_all(query, params)

        for row in rows:
            items.append(SourceItem(
                id=row["id"],
                name=row.get("filename", "Untitled"),
                type=row.get("mime_type", "document"),
                preview=f"Size: {row.get('file_size', 0)} bytes | Status: {row.get('status', 'unknown')}",
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
                metadata={
                    "file_size": row.get("file_size", 0),
                    "status": row.get("status", "unknown"),
                }
            ))

    except Exception as e:
        # Try arkham_frame.documents as fallback
        try:
            count_query = "SELECT COUNT(*) as count FROM arkham_frame.documents WHERE 1=1"
            query = """
                SELECT id, file_name, file_type, file_size, created_at
                FROM arkham_frame.documents
                WHERE 1=1
            """
            params = {}

            if q:
                query += " AND file_name ILIKE :q"
                count_query += " AND file_name ILIKE :q"
                params["q"] = f"%{q}%"

            count_row = await db.fetch_one(count_query, params)
            total = count_row["count"] if count_row else 0

            query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
            rows = await db.fetch_all(query, params)

            for row in rows:
                items.append(SourceItem(
                    id=row["id"],
                    name=row.get("file_name", "Untitled"),
                    type=row.get("file_type", "document"),
                    preview=f"Size: {row.get('file_size', 0)} bytes",
                    created_at=row["created_at"].isoformat() if row.get("created_at") else None,
                    metadata={
                        "file_size": row.get("file_size", 0),
                    }
                ))
        except Exception:
            pass

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sources/entities", response_model=SourceListResponse)
async def browse_entities(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user = Depends(current_active_user),
):
    """
    Browse available entities for summarization. Scoped to active project.
    """
    shard = get_shard(request)
    db = shard._db

    if not db:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    offset = (page - 1) * page_size
    items = []
    total = 0

    try:
        # Get active project_id if not provided
        if not project_id:
            project_id = await _require_active_project_id(request, shard, user)
        else:
            await require_project_member(str(project_id), user, request)

        count_query = "SELECT COUNT(*) as count FROM arkham_entities WHERE 1=1"
        query = """
            SELECT id, name, entity_type, mention_count, created_at
            FROM arkham_entities
            WHERE 1=1
        """
        params = {}

        if project_id:
            query += " AND project_id = :project_id"
            count_query += " AND project_id = :project_id"
            params["project_id"] = project_id

        if q:
            query += " AND name ILIKE :q"
            count_query += " AND name ILIKE :q"
            params["q"] = f"%{q}%"

        if entity_type:
            query += " AND entity_type = :entity_type"
            count_query += " AND entity_type = :entity_type"
            params["entity_type"] = entity_type

        count_row = await db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        query += f" ORDER BY mention_count DESC LIMIT {page_size} OFFSET {offset}"
        rows = await db.fetch_all(query, params)

        for row in rows:
            items.append(SourceItem(
                id=row["id"],
                name=row.get("name", "Unknown"),
                type=row.get("entity_type", "entity"),
                preview=f"Mentions: {row.get('mention_count', 0)}",
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
                metadata={
                    "entity_type": row.get("entity_type"),
                    "mention_count": row.get("mention_count", 0),
                }
            ))
    except Exception:
        pass

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sources/projects", response_model=SourceListResponse)
async def browse_projects(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query"),
):
    """
    Browse available projects for summarization.
    """
    shard = get_shard(request)
    db = shard._db

    if not db:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    offset = (page - 1) * page_size
    items = []
    total = 0

    try:
        count_query = "SELECT COUNT(*) as count FROM arkham_projects WHERE 1=1"
        query = """
            SELECT id, name, description, status, document_count, created_at
            FROM arkham_projects
            WHERE 1=1
        """
        params = {}

        if q:
            query += " AND (name ILIKE :q OR description ILIKE :q)"
            count_query += " AND (name ILIKE :q OR description ILIKE :q)"
            params["q"] = f"%{q}%"

        count_row = await db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
        rows = await db.fetch_all(query, params)

        for row in rows:
            desc = row.get("description", "")
            preview = desc[:100] + "..." if len(desc) > 100 else desc
            items.append(SourceItem(
                id=row["id"],
                name=row.get("name", "Untitled"),
                type="project",
                preview=preview or f"Documents: {row.get('document_count', 0)}",
                created_at=row["created_at"] if row.get("created_at") else None,
                metadata={
                    "status": row.get("status"),
                    "document_count": row.get("document_count", 0),
                }
            ))
    except Exception:
        pass

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sources/claims", response_model=SourceListResponse)
async def browse_claims(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user = Depends(current_active_user),
):
    """
    Browse available claims for summarization. Scoped to active project.
    """
    shard = get_shard(request)
    db = shard._db

    if not db:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    offset = (page - 1) * page_size
    items = []
    total = 0

    try:
        # Get active project_id if not provided
        if not project_id:
            project_id = await _require_active_project_id(request, shard, user)
        else:
            await require_project_member(str(project_id), user, request)

        count_query = "SELECT COUNT(*) as count FROM arkham_claims WHERE 1=1"
        query = """
            SELECT id, text, claim_type, status, confidence, created_at
            FROM arkham_claims
            WHERE 1=1
        """
        params = {}

        if project_id:
            query += " AND project_id = :project_id"
            count_query += " AND project_id = :project_id"
            params["project_id"] = project_id

        if q:
            query += " AND text ILIKE :q"
            count_query += " AND text ILIKE :q"
            params["q"] = f"%{q}%"

        if status:
            query += " AND status = :status"
            count_query += " AND status = :status"
            params["status"] = status

        count_row = await db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
        rows = await db.fetch_all(query, params)

        for row in rows:
            text = row.get("text", "")
            preview = text[:100] + "..." if len(text) > 100 else text
            items.append(SourceItem(
                id=row["id"],
                name=preview,
                type=row.get("claim_type", "claim"),
                preview=f"Status: {row.get('status', 'unknown')} | Confidence: {row.get('confidence', 1.0) * 100:.0f}%",
                created_at=row["created_at"] if row.get("created_at") else None,
                metadata={
                    "claim_type": row.get("claim_type"),
                    "status": row.get("status"),
                    "confidence": row.get("confidence", 1.0),
                }
            ))
    except Exception:
        pass

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sources/timeline", response_model=SourceListResponse)
async def browse_timeline_events(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search query"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user = Depends(current_active_user),
):
    """
    Browse available timeline events for summarization. Scoped to active project.
    """
    shard = get_shard(request)
    db = shard._db

    if not db:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    offset = (page - 1) * page_size
    items = []
    total = 0

    try:
        # Get active project_id if not provided
        if not project_id:
            project_id = await _require_active_project_id(request, shard, user)
        else:
            await require_project_member(str(project_id), user, request)

        # Filter timeline events by project via document join
        count_query = """
            SELECT COUNT(*) as count FROM arkham_timeline_events e
            INNER JOIN arkham_frame.documents d ON e.document_id = d.id
            WHERE d.project_id = :project_id
        """
        query = """
            SELECT e.id, e.text, e.event_type, e.date_start, e.confidence, e.created_at
            FROM arkham_timeline_events e
            INNER JOIN arkham_frame.documents d ON e.document_id = d.id
            WHERE d.project_id = :project_id
        """
        params = {"project_id": project_id}

        if q:
            query += " AND e.text ILIKE :q"
            count_query += " AND e.text ILIKE :q"
            params["q"] = f"%{q}%"

        if event_type:
            query += " AND e.event_type = :event_type"
            count_query += " AND e.event_type = :event_type"
            params["event_type"] = event_type

        count_row = await db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        query += f" ORDER BY date_start DESC LIMIT {page_size} OFFSET {offset}"
        rows = await db.fetch_all(query, params)

        for row in rows:
            text = row.get("text", "")
            preview = text[:80] + "..." if len(text) > 80 else text
            date_str = str(row.get("date_start", "Unknown date"))
            items.append(SourceItem(
                id=row["id"],
                name=preview,
                type=row.get("event_type", "event"),
                preview=f"Date: {date_str}",
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
                metadata={
                    "event_type": row.get("event_type"),
                    "date_start": date_str,
                    "confidence": row.get("confidence", 1.0),
                }
            ))
    except Exception:
        pass

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/quick-summary/{doc_id}")
async def quick_summary(
    doc_id: str,
    request: Request,
    summary_type: str = Query("brief", description="Summary type"),
    target_length: str = Query("short", description="Target length"),
):
    """
    Generate a quick summary for a single document.

    This is a convenience endpoint for quick one-click summarization.
    """
    with log_operation("summary.quick", document_id=doc_id) as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "summary")
                event.context("operation", "quick_summary")
                event.input(
                    document_id=doc_id,
                    summary_type=summary_type,
                    target_length=target_length,
                )

            shard = get_shard(request)

            try:
                summary_type_enum = SummaryType(summary_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid summary_type: {summary_type}")

            try:
                target_length_enum = SummaryLength(target_length)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid target_length: {target_length}")

            # Generate summary
            summary_request = SummaryRequest(
                source_type=SourceType.DOCUMENT,
                source_ids=[doc_id],
                summary_type=summary_type_enum,
                target_length=target_length_enum,
                include_key_points=True,
                include_title=True,
                tags=["quick-summary"],
            )

            result = await shard.generate_summary(summary_request)

            duration_ms = (time.time() - start_time) * 1000

            if result.status == SummaryStatus.FAILED:
                if event:
                    event.error(result.error_message or "Summary generation failed", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=result.error_message or "Summary generation failed",
                )

            if event:
                event.output(
                    summary_id=result.summary_id,
                    status=result.status.value if hasattr(result.status, 'value') else str(result.status),
                    processing_time_ms=result.processing_time_ms if hasattr(result, 'processing_time_ms') else duration_ms,
                )

            return result
        except Exception as e:
            if event:
                event.error(str(e), exc_info=True)
            raise
