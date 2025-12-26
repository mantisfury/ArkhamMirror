"""
ArkhamMirror Dashboard Shard

System monitoring, LLM configuration, database controls, and worker management.
"""

__version__ = "0.1.0"

from .shard import DashboardShard
from .models import (
    ServiceStatus,
    ServiceHealth,
    SystemHealth,
    LLMConfig,
    UpdateLLMRequest,
    LLMTestResult,
    DatabaseInfo,
    MigrationResult,
    ResetDatabaseRequest,
    VacuumResult,
    WorkerInfo,
    QueueStats,
    ScaleWorkersRequest,
    ScaleWorkersResult,
    StartWorkerRequest,
    StartWorkerResult,
    StopWorkerRequest,
    StopWorkerResult,
    EventInfo,
    EventListResponse,
    ErrorInfo,
    ErrorListResponse,
    ShardInfo,
    SystemInfo,
    DashboardStats,
)

__all__ = [
    "DashboardShard",
    "__version__",
    # Service models
    "ServiceStatus",
    "ServiceHealth",
    "SystemHealth",
    # LLM models
    "LLMConfig",
    "UpdateLLMRequest",
    "LLMTestResult",
    # Database models
    "DatabaseInfo",
    "MigrationResult",
    "ResetDatabaseRequest",
    "VacuumResult",
    # Worker models
    "WorkerInfo",
    "QueueStats",
    "ScaleWorkersRequest",
    "ScaleWorkersResult",
    "StartWorkerRequest",
    "StartWorkerResult",
    "StopWorkerRequest",
    "StopWorkerResult",
    # Event models
    "EventInfo",
    "EventListResponse",
    "ErrorInfo",
    "ErrorListResponse",
    # System models
    "ShardInfo",
    "SystemInfo",
    "DashboardStats",
]
