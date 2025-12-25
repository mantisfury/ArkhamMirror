"""
Scheduler API endpoints.

Provides REST API for scheduled job management.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter()


class CronJobRequest(BaseModel):
    """Request body for scheduling a cron job."""
    name: str = Field(..., description="Job name")
    func_name: str = Field(..., description="Registered function name")
    cron_expression: Optional[str] = Field(None, description="Cron expression (e.g., '0 * * * *')")
    hour: Optional[str] = Field(None, description="Hour pattern (0-23)")
    minute: Optional[str] = Field(None, description="Minute pattern (0-59)")
    second: Optional[str] = Field(None, description="Second pattern (0-59)")
    day_of_week: Optional[str] = Field(None, description="Day of week (0-6 or mon-sun)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class IntervalJobRequest(BaseModel):
    """Request body for scheduling an interval job."""
    name: str = Field(..., description="Job name")
    func_name: str = Field(..., description="Registered function name")
    weeks: int = Field(0, ge=0, description="Weeks between runs")
    days: int = Field(0, ge=0, description="Days between runs")
    hours: int = Field(0, ge=0, description="Hours between runs")
    minutes: int = Field(0, ge=0, description="Minutes between runs")
    seconds: int = Field(0, ge=0, description="Seconds between runs")
    start_date: Optional[datetime] = Field(None, description="First run time")
    end_date: Optional[datetime] = Field(None, description="Last run time")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class OnceJobRequest(BaseModel):
    """Request body for scheduling a one-time job."""
    name: str = Field(..., description="Job name")
    func_name: str = Field(..., description="Registered function name")
    run_date: datetime = Field(..., description="When to run the job")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


@router.get("/")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
) -> Dict[str, Any]:
    """List all scheduled jobs."""
    from ..main import get_frame
    from ..services.scheduler import JobStatus

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    filter_status = None
    if status:
        try:
            filter_status = JobStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    jobs = scheduler_service.list_jobs(status=filter_status)

    return {
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "func_name": j.func_name,
                "trigger_type": j.trigger_type.value,
                "trigger_config": j.trigger_config,
                "status": j.status.value,
                "created_at": j.created_at.isoformat(),
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "next_run": j.next_run.isoformat() if j.next_run else None,
                "run_count": j.run_count,
                "error_count": j.error_count,
            }
            for j in jobs
        ],
        "count": len(jobs),
    }


@router.get("/functions")
async def list_registered_functions() -> Dict[str, Any]:
    """List registered job functions."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    return {
        "functions": list(scheduler_service._job_funcs.keys()),
        "count": len(scheduler_service._job_funcs),
    }


@router.post("/cron")
async def schedule_cron_job(request: CronJobRequest) -> Dict[str, Any]:
    """Schedule a cron-style job."""
    from ..main import get_frame
    from ..services.scheduler import InvalidScheduleError

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    try:
        job = scheduler_service.schedule_cron(
            name=request.name,
            func_name=request.func_name,
            cron_expression=request.cron_expression,
            hour=request.hour,
            minute=request.minute,
            second=request.second,
            day_of_week=request.day_of_week,
            metadata=request.metadata,
        )

        return {
            "id": job.id,
            "name": job.name,
            "trigger_type": job.trigger_type.value,
            "trigger_config": job.trigger_config,
            "created_at": job.created_at.isoformat(),
        }

    except InvalidScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/interval")
async def schedule_interval_job(request: IntervalJobRequest) -> Dict[str, Any]:
    """Schedule an interval-based job."""
    from ..main import get_frame
    from ..services.scheduler import InvalidScheduleError

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    try:
        job = scheduler_service.schedule_interval(
            name=request.name,
            func_name=request.func_name,
            weeks=request.weeks,
            days=request.days,
            hours=request.hours,
            minutes=request.minutes,
            seconds=request.seconds,
            start_date=request.start_date,
            end_date=request.end_date,
            metadata=request.metadata,
        )

        return {
            "id": job.id,
            "name": job.name,
            "trigger_type": job.trigger_type.value,
            "trigger_config": job.trigger_config,
            "next_run": job.next_run.isoformat() if job.next_run else None,
            "created_at": job.created_at.isoformat(),
        }

    except InvalidScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/once")
async def schedule_once_job(request: OnceJobRequest) -> Dict[str, Any]:
    """Schedule a one-time job."""
    from ..main import get_frame
    from ..services.scheduler import InvalidScheduleError

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    try:
        job = scheduler_service.schedule_once(
            name=request.name,
            func_name=request.func_name,
            run_date=request.run_date,
            metadata=request.metadata,
        )

        return {
            "id": job.id,
            "name": job.name,
            "trigger_type": job.trigger_type.value,
            "next_run": job.next_run.isoformat() if job.next_run else None,
            "created_at": job.created_at.isoformat(),
        }

    except InvalidScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    """Get a specific job."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    job = scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return {
        "id": job.id,
        "name": job.name,
        "func_name": job.func_name,
        "trigger_type": job.trigger_type.value,
        "trigger_config": job.trigger_config,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "last_run": job.last_run.isoformat() if job.last_run else None,
        "next_run": job.next_run.isoformat() if job.next_run else None,
        "run_count": job.run_count,
        "error_count": job.error_count,
        "metadata": job.metadata,
    }


@router.post("/{job_id}/pause")
async def pause_job(job_id: str) -> Dict[str, Any]:
    """Pause a scheduled job."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    if not scheduler_service.pause_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return {"id": job_id, "status": "paused"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: str) -> Dict[str, Any]:
    """Resume a paused job."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    if not scheduler_service.resume_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found or not paused")

    return {"id": job_id, "status": "pending"}


@router.delete("/{job_id}")
async def remove_job(job_id: str) -> Dict[str, Any]:
    """Remove a scheduled job."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    if not scheduler_service.remove_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return {"removed": job_id}


@router.get("/{job_id}/history")
async def get_job_history(
    job_id: str,
    limit: int = Query(100, le=1000),
) -> Dict[str, Any]:
    """Get execution history for a specific job."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    history = scheduler_service.get_history(job_id=job_id, limit=limit)

    return {
        "history": [
            {
                "job_id": r.job_id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat(),
                "status": r.status.value,
                "execution_time_ms": r.execution_time_ms,
                "error": r.error,
            }
            for r in history
        ],
        "count": len(history),
    }


@router.get("/history/all")
async def get_all_history(
    limit: int = Query(100, le=1000),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> Dict[str, Any]:
    """Get execution history for all jobs."""
    from ..main import get_frame
    from ..services.scheduler import JobStatus

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    filter_status = None
    if status:
        try:
            filter_status = JobStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    history = scheduler_service.get_history(limit=limit, status=filter_status)

    return {
        "history": [
            {
                "job_id": r.job_id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat(),
                "status": r.status.value,
                "execution_time_ms": r.execution_time_ms,
                "error": r.error,
            }
            for r in history
        ],
        "count": len(history),
    }


@router.get("/stats")
async def get_scheduler_stats() -> Dict[str, Any]:
    """Get scheduler statistics."""
    from ..main import get_frame

    frame = get_frame()
    scheduler_service = frame.get_service("scheduler")

    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    return scheduler_service.get_stats()
