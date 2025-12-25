"""
ArkhamMirror Shattered Frame - Services

Core services that Frame provides to shards.
"""

from .config import ConfigService
from .database import (
    DatabaseService,
    DatabaseError,
    SchemaNotFoundError,
    SchemaExistsError,
    QueryExecutionError,
)
from .documents import (
    DocumentService,
    DocumentNotFoundError,
    DocumentError,
    DocumentStatus,
    Document,
    Chunk,
    Page,
    SearchResult,
    BatchResult,
)
from .entities import (
    EntityService,
    EntityNotFoundError,
    CanonicalNotFoundError,
    RelationshipNotFoundError,
    EntityError,
    Entity,
    CanonicalEntity,
    EntityRelationship,
    CoOccurrence,
    EntityType,
    RelationshipType,
)
from .projects import (
    ProjectService,
    ProjectNotFoundError,
    ProjectExistsError,
    ProjectError,
    Project,
    ProjectStats,
)
from .vectors import (
    VectorService,
    VectorServiceError,
    VectorStoreUnavailableError,
    CollectionNotFoundError,
    CollectionExistsError,
    EmbeddingError,
    VectorDimensionError,
    VectorPoint,
    CollectionInfo,
    SearchResult as VectorSearchResult,
    DistanceMetric,
    EMBEDDING_DIMENSIONS,
)
from .llm import (
    LLMService,
    LLMError,
    LLMUnavailableError,
    LLMRequestError,
    JSONExtractionError,
    PromptNotFoundError,
    LLMResponse,
    StreamChunk,
    PromptTemplate,
)
from .chunks import (
    ChunkService,
    ChunkServiceError,
    TokenizerError,
    TextChunk,
    ChunkConfig,
    ChunkStrategy,
)
from .events import EventBus, EventValidationError, EventDeliveryError
from .workers import WorkerService, WorkerError, WorkerNotFoundError, QueueUnavailableError
from .resources import (
    ResourceService,
    ResourceError,
    GPUMemoryError,
    CPUAllocationError,
    ResourceTier,
    SystemResources,
    PoolConfig,
)
from .storage import (
    StorageService,
    StorageError,
    FileNotFoundError as StorageFileNotFoundError,
    StorageFullError,
    InvalidPathError,
    FileInfo,
    StorageStats,
)

__all__ = [
    # Services
    "ConfigService",
    "DatabaseService",
    "DocumentService",
    "EntityService",
    "ProjectService",
    "VectorService",
    "LLMService",
    "ChunkService",
    "EventBus",
    "WorkerService",
    "ResourceService",
    "StorageService",
    # Entity types and enums
    "EntityType",
    "RelationshipType",
    "Entity",
    "CanonicalEntity",
    "EntityRelationship",
    "CoOccurrence",
    # Vector types
    "VectorPoint",
    "CollectionInfo",
    "VectorSearchResult",
    "DistanceMetric",
    "EMBEDDING_DIMENSIONS",
    # LLM types
    "LLMResponse",
    "StreamChunk",
    "PromptTemplate",
    # Chunk types
    "TextChunk",
    "ChunkConfig",
    "ChunkStrategy",
    # Resource types
    "ResourceTier",
    "SystemResources",
    "PoolConfig",
    # Storage types
    "FileInfo",
    "StorageStats",
    # Document types
    "DocumentStatus",
    "Document",
    "Chunk",
    "Page",
    "SearchResult",
    "BatchResult",
    # Project types
    "Project",
    "ProjectStats",
    # Exceptions
    "DatabaseError",
    "SchemaNotFoundError",
    "SchemaExistsError",
    "QueryExecutionError",
    "DocumentNotFoundError",
    "DocumentError",
    "EntityNotFoundError",
    "CanonicalNotFoundError",
    "RelationshipNotFoundError",
    "EntityError",
    "ProjectNotFoundError",
    "ProjectExistsError",
    "ProjectError",
    "VectorServiceError",
    "VectorStoreUnavailableError",
    "CollectionNotFoundError",
    "CollectionExistsError",
    "EmbeddingError",
    "VectorDimensionError",
    "LLMError",
    "LLMUnavailableError",
    "LLMRequestError",
    "JSONExtractionError",
    "PromptNotFoundError",
    "ChunkServiceError",
    "TokenizerError",
    "EventValidationError",
    "EventDeliveryError",
    "WorkerError",
    "WorkerNotFoundError",
    "QueueUnavailableError",
    "ResourceError",
    "GPUMemoryError",
    "CPUAllocationError",
    "StorageError",
    "StorageFileNotFoundError",
    "StorageFullError",
    "InvalidPathError",
]
