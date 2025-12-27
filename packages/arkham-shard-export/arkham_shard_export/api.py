"""
Export Shard - FastAPI Routes

REST API endpoints for export management.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .models import (
    ExportFormat,
    ExportStatus,
    ExportTarget,
)

if TYPE_CHECKING:
    from .shard import ExportShard

router = APIRouter(prefix="/api/export", tags=["export"])


# === Helper to get shard instance ===

def get_shard(request: Request) -> "ExportShard":
    """Get the export shard instance from app state."""
    shard = getattr(request.app.state, "export_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Export shard not available")
    return shard


# === Pydantic Request/Response Models ===


class ExportOptionsRequest(BaseModel):
    """Request model for export options."""
    include_metadata: bool = Field(default=True)
    include_relationships: bool = Field(default=True)
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    entity_types: Optional[List[str]] = None
    flatten: bool = Field(default=False)
    max_records: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: str = Field(default="asc")


class ExportJobCreate(BaseModel):
    """Request model for creating an export job."""
    format: ExportFormat = Field(..., description="Export format")
    target: ExportTarget = Field(..., description="Data target to export")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    options: Optional[ExportOptionsRequest] = None


class ExportJobResponse(BaseModel):
    """Response model for an export job."""
    id: str
    format: str
    target: str
    status: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    download_url: Optional[str]
    expires_at: Optional[str]
    error: Optional[str]
    filters: Dict[str, Any]
    record_count: int
    processing_time_ms: float
    created_by: str
    metadata: Dict[str, Any]


class ExportJobListResponse(BaseModel):
    """Response model for listing export jobs."""
    jobs: List[ExportJobResponse]
    total: int
    limit: int
    offset: int


class FormatInfoResponse(BaseModel):
    """Response model for format information."""
    format: str
    name: str
    description: str
    file_extension: str
    mime_type: str
    supports_flatten: bool
    supports_metadata: bool
    max_records: Optional[int]
    placeholder: bool


class TargetInfoResponse(BaseModel):
    """Response model for target information."""
    target: str
    name: str
    description: str
    available_formats: List[str]
    estimated_record_count: int
    supports_filters: bool


class StatisticsResponse(BaseModel):
    """Response model for export statistics."""
    total_jobs: int
    by_status: Dict[str, int]
    by_format: Dict[str, int]
    by_target: Dict[str, int]
    jobs_pending: int
    jobs_processing: int
    jobs_completed: int
    jobs_failed: int
    total_records_exported: int
    total_file_size_bytes: int
    avg_processing_time_ms: float
    oldest_pending_job: Optional[str]


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class PreviewRequest(BaseModel):
    """Request model for export preview."""
    format: ExportFormat
    target: ExportTarget
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    options: Optional[ExportOptionsRequest] = None
    max_preview_records: int = Field(default=10, ge=1, le=100)


class PreviewResponse(BaseModel):
    """Response model for export preview."""
    format: str
    target: str
    estimated_record_count: int
    preview_records: List[Dict[str, Any]]
    estimated_file_size_bytes: int


# === Helper Functions ===


def _job_to_response(job) -> ExportJobResponse:
    """Convert ExportJob object to response model."""
    return ExportJobResponse(
        id=job.id,
        format=job.format.value,
        target=job.target.value,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        file_path=job.file_path,
        file_size=job.file_size,
        download_url=job.download_url,
        expires_at=job.expires_at.isoformat() if job.expires_at else None,
        error=job.error,
        filters=job.filters,
        record_count=job.record_count,
        processing_time_ms=job.processing_time_ms,
        created_by=job.created_by,
        metadata=job.metadata,
    )


# === Endpoints ===


@router.get("/count", response_model=CountResponse)
async def get_export_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of export jobs (used for badge)."""
    shard = get_shard(request)
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


@router.get("/jobs", response_model=ExportJobListResponse)
async def list_jobs(
    request: Request,
    status: Optional[ExportStatus] = Query(None),
    format: Optional[ExportFormat] = Query(None),
    target: Optional[ExportTarget] = Query(None),
    created_by: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List export jobs with optional filtering."""
    from .models import ExportFilter

    shard = get_shard(request)

    filter = ExportFilter(
        status=status,
        format=format,
        target=target,
        created_by=created_by,
    )

    jobs = await shard.list_jobs(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count()

    return ExportJobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/jobs", response_model=ExportJobResponse, status_code=201)
async def create_job(body: ExportJobCreate, request: Request):
    """Create a new export job."""
    from .models import ExportOptions

    shard = get_shard(request)

    # Convert request options to ExportOptions
    options = None
    if body.options:
        from datetime import datetime
        options = ExportOptions(
            include_metadata=body.options.include_metadata,
            include_relationships=body.options.include_relationships,
            date_range_start=datetime.fromisoformat(body.options.date_range_start) if body.options.date_range_start else None,
            date_range_end=datetime.fromisoformat(body.options.date_range_end) if body.options.date_range_end else None,
            entity_types=body.options.entity_types,
            flatten=body.options.flatten,
            max_records=body.options.max_records,
            sort_by=body.options.sort_by,
            sort_order=body.options.sort_order,
        )

    job = await shard.create_export_job(
        format=body.format,
        target=body.target,
        filters=body.filters,
        options=options,
    )

    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=ExportJobResponse)
async def get_job(job_id: str, request: Request):
    """Get a specific export job by ID."""
    shard = get_shard(request)
    job = await shard.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Export job {job_id} not found")

    return _job_to_response(job)


@router.delete("/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str, request: Request):
    """Cancel a pending export job."""
    shard = get_shard(request)

    job = await shard.cancel_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Export job {job_id} not found")


@router.get("/jobs/{job_id}/download")
async def download_job(job_id: str, request: Request):
    """Download the export file for a completed job."""
    shard = get_shard(request)

    job = await shard.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Export job {job_id} not found")

    if job.status != ExportStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Export job is not completed (status: {job.status.value})",
        )

    if not job.file_path:
        raise HTTPException(status_code=404, detail="Export file not found")

    # Check expiration
    from datetime import datetime
    if job.expires_at and datetime.utcnow() > job.expires_at:
        raise HTTPException(status_code=410, detail="Export file has expired")

    # Emit download event
    if shard._events:
        await shard._events.emit(
            "export.file.downloaded",
            {"job_id": job_id, "file_path": job.file_path},
            source=shard.name,
        )

    # Return file
    import os
    filename = os.path.basename(job.file_path)
    return FileResponse(
        path=job.file_path,
        filename=filename,
        media_type=_get_mime_type(job.format),
    )


@router.get("/formats", response_model=List[FormatInfoResponse])
async def get_formats(request: Request):
    """Get list of supported export formats."""
    shard = get_shard(request)
    formats = shard.get_supported_formats()

    return [
        FormatInfoResponse(
            format=f.format.value,
            name=f.name,
            description=f.description,
            file_extension=f.file_extension,
            mime_type=f.mime_type,
            supports_flatten=f.supports_flatten,
            supports_metadata=f.supports_metadata,
            max_records=f.max_records,
            placeholder=f.placeholder,
        )
        for f in formats
    ]


@router.get("/targets", response_model=List[TargetInfoResponse])
async def get_targets(request: Request):
    """Get list of available export targets."""
    shard = get_shard(request)
    targets = shard.get_export_targets()

    return [
        TargetInfoResponse(
            target=t.target.value,
            name=t.name,
            description=t.description,
            available_formats=[f.value for f in t.available_formats],
            estimated_record_count=t.estimated_record_count,
            supports_filters=t.supports_filters,
        )
        for t in targets
    ]


@router.post("/preview", response_model=PreviewResponse)
async def preview_export(body: PreviewRequest, request: Request):
    """Preview export without creating a file."""
    # Stub implementation
    return PreviewResponse(
        format=body.format.value,
        target=body.target.value,
        estimated_record_count=0,
        preview_records=[],
        estimated_file_size_bytes=0,
    )


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics(request: Request):
    """Get export statistics."""
    shard = get_shard(request)
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_jobs=stats.total_jobs,
        by_status=stats.by_status,
        by_format=stats.by_format,
        by_target=stats.by_target,
        jobs_pending=stats.jobs_pending,
        jobs_processing=stats.jobs_processing,
        jobs_completed=stats.jobs_completed,
        jobs_failed=stats.jobs_failed,
        total_records_exported=stats.total_records_exported,
        total_file_size_bytes=stats.total_file_size_bytes,
        avg_processing_time_ms=stats.avg_processing_time_ms,
        oldest_pending_job=stats.oldest_pending_job.isoformat() if stats.oldest_pending_job else None,
    )


# === Helper Functions ===


def _get_mime_type(format: ExportFormat) -> str:
    """Get MIME type for export format."""
    mime_types = {
        ExportFormat.JSON: "application/json",
        ExportFormat.CSV: "text/csv",
        ExportFormat.PDF: "application/pdf",
        ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ExportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mime_types.get(format, "application/octet-stream")
