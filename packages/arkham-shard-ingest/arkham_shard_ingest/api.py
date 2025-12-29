"""Ingest Shard API endpoints."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .models import JobPriority, JobStatus

# Batch staggering configuration
BATCH_STAGGER_THRESHOLD = 10  # Start staggering after this many jobs
BATCH_STAGGER_SIZE = 10  # Jobs between stagger pauses
BATCH_STAGGER_DELAY = 0.5  # Seconds to pause

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

# These get set by the shard on initialization
_intake_manager = None
_job_dispatcher = None
_event_bus = None
_config = None


def init_api(intake_manager, job_dispatcher, event_bus, config=None):
    """Initialize API with shard dependencies."""
    global _intake_manager, _job_dispatcher, _event_bus, _config
    _intake_manager = intake_manager
    _job_dispatcher = job_dispatcher
    _event_bus = event_bus
    _config = config


# --- Request/Response Models ---


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    category: str
    status: str
    route: list[str]
    quality: dict | None = None


class BatchUploadResponse(BaseModel):
    batch_id: str
    total_files: int
    jobs: list[UploadResponse]
    failed: int


class JobStatusResponse(BaseModel):
    job_id: str
    filename: str
    status: str
    current_worker: str | None
    route: list[str]
    route_position: int
    quality: dict | None
    error: str | None
    retry_count: int
    created_at: str
    started_at: str | None
    completed_at: str | None


class BatchStatusResponse(BaseModel):
    batch_id: str
    total_files: int
    completed: int
    failed: int
    pending: int
    jobs: list[JobStatusResponse]


class IngestPathRequest(BaseModel):
    path: str
    recursive: bool = True
    priority: str = "batch"
    ocr_mode: str = "auto"


class QueueStatsResponse(BaseModel):
    pending: int
    processing: int
    completed: int
    failed: int
    by_priority: dict[str, int]


# --- Endpoints ---


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    priority: str = Form("user"),
    ocr_mode: str = Form("auto"),
):
    """
    Upload a single file for ingestion.

    The file is classified, quality-assessed (for images), and queued
    for processing through the appropriate worker pipeline.

    Args:
        file: File to upload
        priority: Job priority (user, batch, reprocess)
        ocr_mode: OCR routing mode (auto, paddle_only, qwen_only)
    """
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    try:
        job_priority = JobPriority[priority.upper()]
    except KeyError:
        job_priority = JobPriority.USER

    # Validate ocr_mode
    valid_ocr_modes = ("auto", "paddle_only", "qwen_only")
    if ocr_mode not in valid_ocr_modes:
        ocr_mode = "auto"

    job = await _intake_manager.receive_file(
        file=file.file,
        filename=file.filename,
        priority=job_priority,
        ocr_mode=ocr_mode,
    )

    # Dispatch to workers
    await _job_dispatcher.dispatch(job)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ingest.file.queued",
            {
                "job_id": job.id,
                "filename": file.filename,
                "category": job.file_info.category.value,
            },
            source="ingest-shard",
        )

    return UploadResponse(
        job_id=job.id,
        filename=job.file_info.original_name,
        category=job.file_info.category.value,
        status=job.status.value,
        route=job.worker_route,
        quality=(
            {
                "classification": job.quality_score.classification.value,
                "issues": job.quality_score.issues,
                "dpi": job.quality_score.dpi,
                "skew": round(job.quality_score.skew_angle, 2),
                "contrast": round(job.quality_score.contrast_ratio, 2),
                "layout": job.quality_score.layout_complexity,
            }
            if job.quality_score
            else None
        ),
    )


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch(
    files: list[UploadFile] = File(...),
    priority: str = Form("batch"),
    ocr_mode: str = Form("auto"),
):
    """
    Upload multiple files as a batch.

    All files are processed together and tracked as a single batch.

    Args:
        files: Files to upload
        priority: Job priority (user, batch, reprocess)
        ocr_mode: OCR routing mode (auto, paddle_only, qwen_only)
    """
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    try:
        job_priority = JobPriority[priority.upper()]
    except KeyError:
        job_priority = JobPriority.BATCH

    # Validate ocr_mode
    valid_ocr_modes = ("auto", "paddle_only", "qwen_only")
    if ocr_mode not in valid_ocr_modes:
        ocr_mode = "auto"

    file_tuples = [(f.file, f.filename) for f in files]
    batch = await _intake_manager.receive_batch(file_tuples, job_priority, ocr_mode=ocr_mode)

    # Dispatch all jobs with staggering for large batches
    use_staggering = len(batch.jobs) > BATCH_STAGGER_THRESHOLD
    for i, job in enumerate(batch.jobs):
        await _job_dispatcher.dispatch(job)
        # Stagger: pause every BATCH_STAGGER_SIZE jobs to prevent GPU overload
        if use_staggering and (i + 1) % BATCH_STAGGER_SIZE == 0:
            await asyncio.sleep(BATCH_STAGGER_DELAY)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ingest.batch.queued",
            {
                "batch_id": batch.id,
                "total_files": batch.total_files,
                "failed": batch.failed,
            },
            source="ingest-shard",
        )

    return BatchUploadResponse(
        batch_id=batch.id,
        total_files=batch.total_files,
        jobs=[
            UploadResponse(
                job_id=j.id,
                filename=j.file_info.original_name,
                category=j.file_info.category.value,
                status=j.status.value,
                route=j.worker_route,
                quality=(
                    {
                        "classification": j.quality_score.classification.value,
                        "issues": j.quality_score.issues,
                    }
                    if j.quality_score
                    else None
                ),
            )
            for j in batch.jobs
        ],
        failed=batch.failed,
    )


@router.post("/ingest-path", response_model=BatchUploadResponse)
async def ingest_from_path(request: IngestPathRequest):
    """
    Ingest files from a local filesystem path.

    Can be a single file or a directory. If directory, optionally
    recurses into subdirectories.

    Args:
        request: Contains path, recursive, priority, and ocr_mode settings
    """
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    try:
        job_priority = JobPriority[request.priority.upper()]
    except KeyError:
        job_priority = JobPriority.BATCH

    # Validate ocr_mode
    valid_ocr_modes = ("auto", "paddle_only", "qwen_only")
    ocr_mode = request.ocr_mode if request.ocr_mode in valid_ocr_modes else "auto"

    batch = await _intake_manager.receive_path(
        path=path,
        priority=job_priority,
        recursive=request.recursive,
        ocr_mode=ocr_mode,
    )

    # Dispatch all jobs with staggering for large batches
    use_staggering = len(batch.jobs) > BATCH_STAGGER_THRESHOLD
    for i, job in enumerate(batch.jobs):
        await _job_dispatcher.dispatch(job)
        if use_staggering and (i + 1) % BATCH_STAGGER_SIZE == 0:
            await asyncio.sleep(BATCH_STAGGER_DELAY)

    return BatchUploadResponse(
        batch_id=batch.id,
        total_files=batch.total_files,
        jobs=[
            UploadResponse(
                job_id=j.id,
                filename=j.file_info.original_name,
                category=j.file_info.category.value,
                status=j.status.value,
                route=j.worker_route,
            )
            for j in batch.jobs
        ],
        failed=batch.failed,
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    job = _intake_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Calculate route position
    try:
        route_pos = job.worker_route.index(job.current_worker) if job.current_worker else 0
    except ValueError:
        route_pos = 0

    return JobStatusResponse(
        job_id=job.id,
        filename=job.file_info.original_name,
        status=job.status.value,
        current_worker=job.current_worker,
        route=job.worker_route,
        route_position=route_pos,
        quality=(
            {
                "classification": job.quality_score.classification.value,
                "issues": job.quality_score.issues,
            }
            if job.quality_score
            else None
        ),
        error=job.error,
        retry_count=job.retry_count,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str):
    """Get status of a batch."""
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    batch = _intake_manager.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    return BatchStatusResponse(
        batch_id=batch.id,
        total_files=batch.total_files,
        completed=batch.completed,
        failed=batch.failed,
        pending=batch.pending,
        jobs=[
            JobStatusResponse(
                job_id=j.id,
                filename=j.file_info.original_name,
                status=j.status.value,
                current_worker=j.current_worker,
                route=j.worker_route,
                route_position=0,
                quality=None,
                error=j.error,
                retry_count=j.retry_count,
                created_at=j.created_at.isoformat(),
                started_at=j.started_at.isoformat() if j.started_at else None,
                completed_at=j.completed_at.isoformat() if j.completed_at else None,
            )
            for j in batch.jobs
        ],
    )


@router.post("/job/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry a failed job."""
    if not _intake_manager or not _job_dispatcher:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    job = _intake_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status not in (JobStatus.FAILED, JobStatus.DEAD):
        raise HTTPException(status_code=400, detail=f"Job is not in failed state: {job.status.value}")

    success = await _job_dispatcher.retry(job)
    if not success:
        raise HTTPException(status_code=400, detail="Max retries exceeded")

    return {"status": "retrying", "job_id": job_id}


@router.get("/queue", response_model=QueueStatsResponse)
async def get_queue_stats():
    """Get ingest queue statistics."""
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    jobs = list(_intake_manager._jobs.values())

    by_status = {}
    by_priority = {"user": 0, "batch": 0, "reprocess": 0}

    for job in jobs:
        status = job.status.value
        by_status[status] = by_status.get(status, 0) + 1

        priority_name = job.priority.name.lower()
        by_priority[priority_name] = by_priority.get(priority_name, 0) + 1

    return QueueStatsResponse(
        pending=by_status.get("pending", 0) + by_status.get("queued", 0),
        processing=by_status.get("processing", 0),
        completed=by_status.get("completed", 0),
        failed=by_status.get("failed", 0) + by_status.get("dead", 0),
        by_priority=by_priority,
    )


@router.get("/pending")
async def get_pending_jobs(limit: int = 50):
    """Get list of pending jobs."""
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    jobs = _intake_manager.get_pending_jobs(limit=limit)

    return {
        "count": len(jobs),
        "jobs": [
            {
                "job_id": j.id,
                "filename": j.file_info.original_name,
                "category": j.file_info.category.value,
                "priority": j.priority.name.lower(),
                "route": j.worker_route,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
    }


# --- Settings Endpoints ---


class IngestSettingsResponse(BaseModel):
    """Current ingest pipeline settings."""

    # Ingest settings
    ingest_ocr_mode: str = "auto"
    ingest_max_file_size_mb: int = 100
    ingest_min_file_size_bytes: int = 100
    ingest_enable_validation: bool = True
    ingest_enable_deduplication: bool = True
    ingest_enable_downscale: bool = True
    ingest_skip_blank_pages: bool = True

    # OCR settings
    ocr_parallel_pages: int = 4
    ocr_confidence_threshold: float = 0.8
    ocr_enable_escalation: bool = True
    ocr_enable_cache: bool = True
    ocr_cache_ttl_days: int = 7


class IngestSettingsUpdate(BaseModel):
    """Partial settings update."""

    ingest_ocr_mode: str | None = None
    ingest_max_file_size_mb: int | None = None
    ingest_min_file_size_bytes: int | None = None
    ingest_enable_validation: bool | None = None
    ingest_enable_deduplication: bool | None = None
    ingest_enable_downscale: bool | None = None
    ingest_skip_blank_pages: bool | None = None
    ocr_parallel_pages: int | None = None
    ocr_confidence_threshold: float | None = None
    ocr_enable_escalation: bool | None = None
    ocr_enable_cache: bool | None = None
    ocr_cache_ttl_days: int | None = None


@router.get("/settings", response_model=IngestSettingsResponse)
async def get_ingest_settings():
    """Get current ingest pipeline settings."""
    if not _config:
        raise HTTPException(status_code=503, detail="Config service not initialized")

    return IngestSettingsResponse(
        ingest_ocr_mode=_config.get("ingest_ocr_mode", "auto"),
        ingest_max_file_size_mb=_config.get("ingest_max_file_size_mb", 100),
        ingest_min_file_size_bytes=_config.get("ingest_min_file_size_bytes", 100),
        ingest_enable_validation=_config.get("ingest_enable_validation", True),
        ingest_enable_deduplication=_config.get("ingest_enable_deduplication", True),
        ingest_enable_downscale=_config.get("ingest_enable_downscale", True),
        ingest_skip_blank_pages=_config.get("ingest_skip_blank_pages", True),
        ocr_parallel_pages=_config.get("ocr_parallel_pages", 4),
        ocr_confidence_threshold=_config.get("ocr_confidence_threshold", 0.8),
        ocr_enable_escalation=_config.get("ocr_enable_escalation", True),
        ocr_enable_cache=_config.get("ocr_enable_cache", True),
        ocr_cache_ttl_days=_config.get("ocr_cache_ttl_days", 7),
    )


@router.patch("/settings", response_model=IngestSettingsResponse)
async def update_ingest_settings(settings: IngestSettingsUpdate):
    """
    Update ingest pipeline settings.

    Only provided fields are updated. Settings take effect for new jobs.
    Existing jobs in queue are not affected.
    """
    if not _config:
        raise HTTPException(status_code=503, detail="Config service not initialized")

    # Update only provided fields
    update_dict = settings.model_dump(exclude_none=True)

    for key, value in update_dict.items():
        _config.set(key, value)

        # Also update the intake manager if it's running
        if _intake_manager:
            if key == "ingest_enable_deduplication":
                _intake_manager.enable_deduplication = value
            elif key == "ingest_enable_downscale":
                _intake_manager.enable_downscale = value
            elif key == "ingest_skip_blank_pages":
                _intake_manager.skip_blank_pages = value
            elif key == "ingest_enable_validation":
                _intake_manager.enable_validation = value
            elif key == "ingest_min_file_size_bytes":
                _intake_manager.min_file_size = value
            elif key == "ingest_max_file_size_mb":
                _intake_manager.max_file_size = value * 1024 * 1024
            elif key == "ingest_ocr_mode":
                _intake_manager.ocr_mode = value

    # Emit event for settings change
    if _event_bus:
        await _event_bus.emit(
            "ingest.settings.updated",
            {"updated_keys": list(update_dict.keys())},
            source="ingest-shard",
        )

    # Return current settings
    return await get_ingest_settings()
