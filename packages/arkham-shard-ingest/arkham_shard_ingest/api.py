"""Ingest Shard API endpoints."""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .models import JobPriority, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

# These get set by the shard on initialization
_intake_manager = None
_job_dispatcher = None
_event_bus = None


def init_api(intake_manager, job_dispatcher, event_bus):
    """Initialize API with shard dependencies."""
    global _intake_manager, _job_dispatcher, _event_bus
    _intake_manager = intake_manager
    _job_dispatcher = job_dispatcher
    _event_bus = event_bus


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
):
    """
    Upload a single file for ingestion.

    The file is classified, quality-assessed (for images), and queued
    for processing through the appropriate worker pipeline.
    """
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    try:
        job_priority = JobPriority[priority.upper()]
    except KeyError:
        job_priority = JobPriority.USER

    job = await _intake_manager.receive_file(
        file=file.file,
        filename=file.filename,
        priority=job_priority,
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
):
    """
    Upload multiple files as a batch.

    All files are processed together and tracked as a single batch.
    """
    if not _intake_manager:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    try:
        job_priority = JobPriority[priority.upper()]
    except KeyError:
        job_priority = JobPriority.BATCH

    file_tuples = [(f.file, f.filename) for f in files]
    batch = await _intake_manager.receive_batch(file_tuples, job_priority)

    # Dispatch all jobs
    for job in batch.jobs:
        await _job_dispatcher.dispatch(job)

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

    batch = await _intake_manager.receive_path(
        path=path,
        priority=job_priority,
        recursive=request.recursive,
    )

    # Dispatch all jobs
    for job in batch.jobs:
        await _job_dispatcher.dispatch(job)

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
