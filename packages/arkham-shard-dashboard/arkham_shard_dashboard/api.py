"""
Dashboard API routes.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# Request models
class UpdateLLMRequest(BaseModel):
    endpoint: Optional[str] = None
    model: Optional[str] = None


class ScaleWorkersRequest(BaseModel):
    queue: str
    count: int


class StartWorkerRequest(BaseModel):
    queue: str


class StopWorkerRequest(BaseModel):
    worker_id: str


class StopAllWorkersRequest(BaseModel):
    pool: Optional[str] = None


class ClearQueueRequest(BaseModel):
    pool: str
    status: Optional[str] = None  # None = pending only


class RetryFailedRequest(BaseModel):
    pool: str
    job_ids: Optional[List[str]] = None  # None = retry all failed


class CancelJobRequest(BaseModel):
    job_id: str


class ResetDatabaseRequest(BaseModel):
    confirm: bool = False


class SetFallbackModelsRequest(BaseModel):
    """Request to configure OpenRouter fallback models."""
    models: List[str] = []
    enabled: bool = True


# Helper to get shard instance
def get_dashboard_shard():
    """Get the dashboard shard from the Frame."""
    from arkham_frame import get_frame

    frame = get_frame()
    if "dashboard" not in frame.shards:
        raise HTTPException(status_code=503, detail="Dashboard shard not loaded")
    return frame.shards["dashboard"]


# === Health ===

@router.get("/health")
async def get_health() -> Dict[str, Any]:
    """Get service health status."""
    shard = get_dashboard_shard()
    return await shard.get_service_health()


# === LLM Configuration ===

@router.get("/llm")
async def get_llm_config() -> Dict[str, Any]:
    """Get LLM configuration."""
    shard = get_dashboard_shard()
    return await shard.get_llm_config()


@router.post("/llm")
async def update_llm_config(request: UpdateLLMRequest) -> Dict[str, Any]:
    """Update LLM configuration."""
    shard = get_dashboard_shard()
    return await shard.update_llm_config(
        endpoint=request.endpoint,
        model=request.model,
    )


@router.post("/llm/test")
async def test_llm_connection() -> Dict[str, Any]:
    """Test LLM connection."""
    shard = get_dashboard_shard()
    return await shard.test_llm_connection()


@router.post("/llm/reset")
async def reset_llm_config() -> Dict[str, Any]:
    """Reset LLM configuration to defaults."""
    shard = get_dashboard_shard()
    return await shard.reset_llm_config()


@router.post("/llm/fallback")
async def set_fallback_models(request: SetFallbackModelsRequest) -> Dict[str, Any]:
    """
    Configure OpenRouter fallback models for intelligent routing.
    
    When enabled, requests will automatically fall back to the next model
    if the primary model fails (quota exceeded, rate limited, etc).
    """
    shard = get_dashboard_shard()
    return await shard.set_fallback_models(
        models=request.models,
        enabled=request.enabled,
    )


@router.get("/llm/fallback")
async def get_fallback_models() -> Dict[str, Any]:
    """Get current fallback model configuration."""
    shard = get_dashboard_shard()
    return await shard.get_fallback_models()


# === Database ===

@router.get("/database")
async def get_database_info() -> Dict[str, Any]:
    """Get database information."""
    shard = get_dashboard_shard()
    return await shard.get_database_info()


@router.get("/database/stats")
async def get_database_stats() -> Dict[str, Any]:
    """Get detailed database statistics."""
    shard = get_dashboard_shard()
    return await shard.get_database_stats()


@router.get("/database/tables/{schema}")
async def get_table_info(schema: str) -> Dict[str, Any]:
    """Get table information for a schema."""
    shard = get_dashboard_shard()
    tables = await shard.get_table_info(schema)
    return {"schema": schema, "tables": tables}


@router.post("/database/migrate")
async def run_migrations() -> Dict[str, Any]:
    """Run database migrations."""
    shard = get_dashboard_shard()
    return await shard.run_migrations()


@router.post("/database/reset")
async def reset_database(request: ResetDatabaseRequest) -> Dict[str, Any]:
    """Reset database (requires confirmation)."""
    shard = get_dashboard_shard()
    return await shard.reset_database(confirm=request.confirm)


@router.post("/database/vacuum")
async def vacuum_database() -> Dict[str, Any]:
    """Run VACUUM ANALYZE on database."""
    shard = get_dashboard_shard()
    return await shard.vacuum_database()


# === Workers ===

@router.get("/workers")
async def get_workers() -> Dict[str, Any]:
    """Get active workers."""
    shard = get_dashboard_shard()
    workers = await shard.get_workers()
    return {"workers": workers}


@router.get("/queues")
async def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    shard = get_dashboard_shard()
    stats = await shard.get_queue_stats()
    return {"queues": stats}


@router.post("/workers/scale")
async def scale_workers(request: ScaleWorkersRequest) -> Dict[str, Any]:
    """Scale workers for a queue."""
    shard = get_dashboard_shard()
    return await shard.scale_workers(queue=request.queue, count=request.count)


@router.post("/workers/start")
async def start_worker(request: StartWorkerRequest) -> Dict[str, Any]:
    """Start a worker for a queue."""
    shard = get_dashboard_shard()
    return await shard.start_worker(queue=request.queue)


@router.post("/workers/stop")
async def stop_worker(request: StopWorkerRequest) -> Dict[str, Any]:
    """Stop a worker."""
    shard = get_dashboard_shard()
    return await shard.stop_worker(worker_id=request.worker_id)


@router.post("/workers/stop-all")
async def stop_all_workers(request: StopAllWorkersRequest) -> Dict[str, Any]:
    """Stop all workers, optionally filtered by pool."""
    shard = get_dashboard_shard()
    return await shard.stop_all_workers(pool=request.pool)


@router.get("/pools")
async def get_pools() -> Dict[str, Any]:
    """Get information about all worker pools."""
    shard = get_dashboard_shard()
    pools = await shard.get_pool_info()
    return {"pools": pools}


@router.get("/jobs")
async def get_jobs(
    pool: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> Dict[str, Any]:
    """Get jobs with optional filtering."""
    shard = get_dashboard_shard()
    jobs = await shard.get_jobs(pool=pool, status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/queues/clear")
async def clear_queue(request: ClearQueueRequest) -> Dict[str, Any]:
    """Clear jobs from a queue."""
    shard = get_dashboard_shard()
    return await shard.clear_queue(pool=request.pool, status=request.status)


@router.post("/jobs/retry")
async def retry_failed_jobs(request: RetryFailedRequest) -> Dict[str, Any]:
    """Retry failed jobs."""
    shard = get_dashboard_shard()
    return await shard.retry_failed_jobs(pool=request.pool, job_ids=request.job_ids)


@router.post("/jobs/cancel")
async def cancel_job(request: CancelJobRequest) -> Dict[str, Any]:
    """Cancel a job."""
    shard = get_dashboard_shard()
    return await shard.cancel_job(job_id=request.job_id)


# === Events ===

@router.get("/events")
async def get_events(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    source: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Get recent events with optional filtering."""
    shard = get_dashboard_shard()
    events = await shard.get_events(
        limit=limit,
        offset=offset,
        source=source,
        event_type=event_type,
    )
    total = await shard.get_event_count(source=source, event_type=event_type)
    return {"events": events, "count": len(events), "total": total}


@router.get("/events/types")
async def get_event_types() -> Dict[str, Any]:
    """Get list of unique event types."""
    shard = get_dashboard_shard()
    types = await shard.get_event_types()
    return {"types": types}


@router.get("/events/sources")
async def get_event_sources() -> Dict[str, Any]:
    """Get list of unique event sources."""
    shard = get_dashboard_shard()
    sources = await shard.get_event_sources()
    return {"sources": sources}


@router.post("/events/clear")
async def clear_events() -> Dict[str, Any]:
    """Clear event history."""
    shard = get_dashboard_shard()
    return await shard.clear_events()


@router.get("/errors")
async def get_errors(
    limit: int = Query(default=50, le=500),
) -> Dict[str, Any]:
    """Get recent error events."""
    shard = get_dashboard_shard()
    errors = await shard.get_errors(limit=limit)
    return {"errors": errors, "count": len(errors)}
