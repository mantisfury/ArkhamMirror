"""Data models for the Embed Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EmbedStatus(Enum):
    """Status of embedding operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EmbedRequest:
    """Request to embed a single text."""
    text: str
    doc_id: str | None = None
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchEmbedRequest:
    """Request to embed multiple texts."""
    texts: list[str]
    doc_ids: list[str] | None = None
    chunk_ids: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResult:
    """Result of a single text embedding."""
    embedding: list[float]
    dimensions: int
    model: str
    doc_id: str | None = None
    chunk_id: str | None = None
    text_length: int = 0
    success: bool = True
    error: str | None = None


@dataclass
class BatchEmbedResult:
    """Result of batch text embedding."""
    embeddings: list[list[float]]
    dimensions: int
    model: str
    count: int
    success: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass
class SimilarityRequest:
    """Request to calculate similarity between texts."""
    text1: str
    text2: str
    method: str = "cosine"  # "cosine", "euclidean", "dot"


@dataclass
class SimilarityResult:
    """Result of similarity calculation."""
    similarity: float
    method: str
    success: bool = True
    error: str | None = None


@dataclass
class NearestRequest:
    """Request to find nearest neighbors in vector space."""
    query: str | list[float]  # Text or pre-computed embedding
    limit: int = 10
    min_similarity: float = 0.5
    collection: str = "documents"  # Qdrant collection name
    filters: dict[str, Any] | None = None


@dataclass
class NearestResult:
    """Result of nearest neighbor search."""
    neighbors: list[dict[str, Any]]
    total: int
    query_dimensions: int
    success: bool = True
    error: str | None = None


@dataclass
class EmbedConfig:
    """Configuration for embedding operations."""
    model: str
    device: str  # "cpu", "cuda", "auto"
    batch_size: int = 32
    max_length: int = 512
    normalize: bool = True
    cache_size: int = 1000


@dataclass
class ModelInfo:
    """Information about an embedding model."""
    name: str
    dimensions: int
    max_length: int
    size_mb: float
    loaded: bool = False
    device: str | None = None
    description: str = ""


@dataclass
class DocumentEmbedRequest:
    """Request to embed all chunks of a document."""
    doc_id: str
    force: bool = False  # Re-embed even if already embedded
    chunk_size: int = 512
    chunk_overlap: int = 50
