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
from .documents import DocumentService, DocumentNotFoundError
from .entities import EntityService, EntityNotFoundError
from .projects import ProjectService, ProjectNotFoundError, ProjectExistsError
from .vectors import VectorService, VectorServiceError, VectorStoreUnavailableError, EmbeddingError
from .llm import LLMService, LLMError, LLMUnavailableError, LLMRequestError, JSONExtractionError
from .events import EventBus, EventValidationError, EventDeliveryError
from .workers import WorkerService, WorkerError, WorkerNotFoundError, QueueUnavailableError

__all__ = [
    # Services
    "ConfigService",
    "DatabaseService",
    "DocumentService",
    "EntityService",
    "ProjectService",
    "VectorService",
    "LLMService",
    "EventBus",
    "WorkerService",
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
]
