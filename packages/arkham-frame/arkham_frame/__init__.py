"""
ArkhamMirror Shattered Frame

The core infrastructure for document intelligence.
Provides services that shards consume through a unified API.
"""

__version__ = "0.1.0"

# Shard interface
from .shard_interface import ArkhamShard, ShardManifest

# Frame class
from .frame import ArkhamFrame, get_frame

# Services
from .services import ConfigService

# Exceptions
from .services import (
    # Database
    DatabaseError,
    SchemaNotFoundError,
    SchemaExistsError,
    QueryExecutionError,
    # Documents
    DocumentNotFoundError,
    # Entities
    EntityNotFoundError,
    # Projects
    ProjectNotFoundError,
    ProjectExistsError,
    # Vectors
    VectorServiceError,
    VectorStoreUnavailableError,
    EmbeddingError,
    # LLM
    LLMError,
    LLMUnavailableError,
    LLMRequestError,
    JSONExtractionError,
    # Events
    EventValidationError,
    EventDeliveryError,
    # Workers
    WorkerError,
    WorkerNotFoundError,
    QueueUnavailableError,
)

# Pipeline
from .pipeline import (
    PipelineStage,
    PipelineError,
    StageResult,
    IngestStage,
    OCRStage,
    ParseStage,
    EmbedStage,
    PipelineCoordinator,
)

# Logging utilities (re-exported from arkham-logging)
try:
    from arkham_logging import (
        get_logger,
        create_wide_event,
        log_operation,
        log_error_with_context,
        format_error_message,
        emit_wide_error,
        get_trace_id,
        set_trace_id,
        generate_trace_id,
    )
    from arkham_logging.tracing import TracingContext
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    import logging
    get_logger = logging.getLogger
    create_wide_event = None
    log_operation = None
    log_error_with_context = None
    format_error_message = None
    emit_wide_error = None
    get_trace_id = None
    set_trace_id = None
    generate_trace_id = None
    TracingContext = None

__all__ = [
    # Version
    "__version__",
    # Shard interface
    "ArkhamShard",
    "ShardManifest",
    # Frame
    "ArkhamFrame",
    "get_frame",
    # Services
    "ConfigService",
    # Exceptions
    "DatabaseError",
    "SchemaNotFoundError",
    "SchemaExistsError",
    "QueryExecutionError",
    "DocumentNotFoundError",
    "EntityNotFoundError",
    "ProjectNotFoundError",
    "ProjectExistsError",
    "VectorServiceError",
    "VectorStoreUnavailableError",
    "EmbeddingError",
    "LLMError",
    "LLMUnavailableError",
    "LLMRequestError",
    "JSONExtractionError",
    "EventValidationError",
    "EventDeliveryError",
    "WorkerError",
    "WorkerNotFoundError",
    "QueueUnavailableError",
    # Pipeline
    "PipelineStage",
    "PipelineError",
    "StageResult",
    "IngestStage",
    "OCRStage",
    "ParseStage",
    "EmbedStage",
    "PipelineCoordinator",
    # Logging
    "get_logger",
    "create_wide_event",
    "log_operation",
    "log_error_with_context",
    "format_error_message",
    "emit_wide_error",
    "get_trace_id",
    "set_trace_id",
    "generate_trace_id",
    "TracingContext",
    "LOGGING_AVAILABLE",
]
