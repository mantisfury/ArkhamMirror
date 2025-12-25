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
]
