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


class ResetDatabaseRequest(BaseModel):
    confirm: bool = False


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


# === Database ===

@router.get("/database")
async def get_database_info() -> Dict[str, Any]:
    """Get database information."""
    shard = get_dashboard_shard()
    return await shard.get_database_info()


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


# === Events ===

@router.get("/events")
async def get_events(
    limit: int = Query(default=50, le=500),
) -> Dict[str, Any]:
    """Get recent events."""
    shard = get_dashboard_shard()
    events = await shard.get_events(limit=limit)
    return {"events": events}


@router.get("/errors")
async def get_errors(
    limit: int = Query(default=50, le=500),
) -> Dict[str, Any]:
    """Get recent error events."""
    shard = get_dashboard_shard()
    errors = await shard.get_errors(limit=limit)
    return {"errors": errors}
