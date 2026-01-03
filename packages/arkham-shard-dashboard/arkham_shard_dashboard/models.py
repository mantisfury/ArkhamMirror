"""
Dashboard Shard - Pydantic Models

Models for system monitoring and dashboard controls.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """Status of a frame service."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    INITIALIZING = "initializing"


class ServiceHealth(BaseModel):
    """Health status of a service."""
    available: bool = False
    status: ServiceStatus = ServiceStatus.UNAVAILABLE
    info: Optional[Dict[str, Any]] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)


class SystemHealth(BaseModel):
    """Overall system health status."""
    database: ServiceHealth = Field(default_factory=ServiceHealth)
    vectors: ServiceHealth = Field(default_factory=ServiceHealth)
    llm: ServiceHealth = Field(default_factory=ServiceHealth)
    workers: ServiceHealth = Field(default_factory=ServiceHealth)
    events: ServiceHealth = Field(default_factory=ServiceHealth)
    storage: ServiceHealth = Field(default_factory=ServiceHealth)


class LLMConfig(BaseModel):
    """LLM service configuration."""
    endpoint: Optional[str] = None
    model: Optional[str] = None
    available: bool = False
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class UpdateLLMRequest(BaseModel):
    """Request to update LLM configuration."""
    endpoint: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)


class SetFallbackModelsRequest(BaseModel):
    """Request to configure OpenRouter fallback models."""
    models: List[str] = Field(
        default_factory=list,
        description="List of model IDs in priority order for fallback routing"
    )
    enabled: bool = Field(
        default=True,
        description="Enable or disable fallback routing"
    )


class LLMTestResult(BaseModel):
    """Result of LLM connection test."""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class DatabaseInfo(BaseModel):
    """Database information."""
    available: bool = False
    url: Optional[str] = None  # Truncated for security
    schemas: List[str] = Field(default_factory=list)
    size_mb: Optional[float] = None
    table_count: Optional[int] = None


class MigrationResult(BaseModel):
    """Result of database migration."""
    success: bool
    message: str
    migrations_applied: int = 0
    errors: List[str] = Field(default_factory=list)


class ResetDatabaseRequest(BaseModel):
    """Request to reset database (requires confirmation)."""
    confirm: bool = False


class VacuumResult(BaseModel):
    """Result of VACUUM operation."""
    success: bool
    message: str
    space_reclaimed_mb: Optional[float] = None


class WorkerInfo(BaseModel):
    """Information about a worker."""
    id: str
    queue: str
    status: str
    started_at: Optional[datetime] = None
    jobs_processed: int = 0
    current_job: Optional[str] = None


class QueueStats(BaseModel):
    """Statistics for a worker queue."""
    queue: str
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    workers_active: int = 0
    workers_max: int = 0


class ScaleWorkersRequest(BaseModel):
    """Request to scale workers."""
    queue: str
    count: int = Field(ge=0, le=100)


class ScaleWorkersResult(BaseModel):
    """Result of scaling workers."""
    success: bool
    queue: str
    target_count: int
    current_count: int = 0
    message: Optional[str] = None


class StartWorkerRequest(BaseModel):
    """Request to start a worker."""
    queue: str


class StartWorkerResult(BaseModel):
    """Result of starting a worker."""
    success: bool
    worker_id: Optional[str] = None
    queue: str
    error: Optional[str] = None


class StopWorkerRequest(BaseModel):
    """Request to stop a worker."""
    worker_id: str


class StopWorkerResult(BaseModel):
    """Result of stopping a worker."""
    success: bool
    worker_id: str
    error: Optional[str] = None


class EventInfo(BaseModel):
    """Information about a system event."""
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EventListResponse(BaseModel):
    """Response for event listing."""
    events: List[EventInfo]
    total: int = 0


class ErrorInfo(BaseModel):
    """Information about a system error."""
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None


class ErrorListResponse(BaseModel):
    """Response for error listing."""
    errors: List[ErrorInfo]
    total: int = 0


class ShardInfo(BaseModel):
    """Information about a loaded shard."""
    name: str
    version: str
    description: str
    api_prefix: str
    category: str
    status: str = "active"


class SystemInfo(BaseModel):
    """Overall system information."""
    frame_version: str = "0.1.0"
    shards_loaded: int = 0
    shards: List[ShardInfo] = Field(default_factory=list)
    uptime_seconds: float = 0
    started_at: Optional[datetime] = None


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_documents: int = 0
    total_entities: int = 0
    total_projects: int = 0
    jobs_pending: int = 0
    jobs_processing: int = 0
    errors_last_hour: int = 0
    services_healthy: int = 0
    services_total: int = 6
