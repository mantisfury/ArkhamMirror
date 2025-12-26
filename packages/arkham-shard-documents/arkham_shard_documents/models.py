"""Data models for the Documents Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DocumentStatus(Enum):
    """Document processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ViewMode(Enum):
    """Document view mode."""
    METADATA = "metadata"
    CONTENT = "content"
    CHUNKS = "chunks"
    ENTITIES = "entities"


class ChunkDisplayMode(Enum):
    """Chunk display mode preference."""
    COMPACT = "compact"
    DETAILED = "detailed"
    CONTEXT = "context"


@dataclass
class DocumentRecord:
    """
    Internal document record model.

    Used for database operations and internal processing.
    """
    id: str
    title: str
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus

    # Content metadata
    page_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    word_count: int = 0

    # Relationships
    project_id: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    # Processing info
    processing_error: Optional[str] = None


@dataclass
class ViewingRecord:
    """
    Record of a document viewing event.

    Tracks when users view documents for analytics and history.
    """
    id: str
    document_id: str
    user_id: Optional[str]
    viewed_at: datetime = field(default_factory=datetime.utcnow)

    # View context
    view_mode: ViewMode = ViewMode.CONTENT
    page_number: Optional[int] = None
    duration_seconds: Optional[int] = None


@dataclass
class CustomMetadataField:
    """
    User-defined metadata field.

    Allows users to add custom metadata fields to documents.
    """
    id: str
    field_name: str
    field_type: str  # text, number, date, boolean, tags
    description: str = ""
    required: bool = False
    default_value: Optional[Any] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserPreferences:
    """
    User preferences for document viewing.

    Stored per-user to customize the viewing experience.
    """
    user_id: str

    # Viewer preferences
    viewer_zoom: float = 1.0
    show_metadata: bool = True
    chunk_display_mode: ChunkDisplayMode = ChunkDisplayMode.DETAILED

    # Display preferences
    items_per_page: int = 20
    default_sort: str = "created_at"
    default_sort_order: str = "desc"

    # Filter presets
    default_filter: Optional[str] = None
    saved_filters: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentPage:
    """
    Individual page of a multi-page document.

    Represents a single page with its content and metadata.
    """
    document_id: str
    page_number: int
    content: str

    # Page metadata
    word_count: int = 0
    has_images: bool = False
    ocr_confidence: Optional[float] = None

    # Rendering
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class DocumentChunkRecord:
    """
    Document chunk record.

    Represents a chunk of document text created during processing.
    """
    id: str
    document_id: str
    chunk_index: int
    content: str

    # Chunk metadata
    page_number: Optional[int] = None
    token_count: int
    word_count: int
    char_count: int

    # Embeddings
    embedding_id: Optional[str] = None
    has_embedding: bool = False

    # Context
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EntityOccurrence:
    """
    Single occurrence of an entity in a document.
    """
    document_id: str
    entity_id: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None

    # Position in text
    start_offset: int = 0
    end_offset: int = 0

    # Context
    context_before: str = ""
    context_after: str = ""
    sentence: str = ""


@dataclass
class DocumentEntity:
    """
    Entity extracted from a document.

    Aggregates all occurrences of an entity across the document.
    """
    id: str
    document_id: str
    entity_type: str  # PERSON, ORG, GPE, DATE, EVENT, etc.
    text: str
    normalized_text: str

    # Recognition metadata
    confidence: float = 1.0
    source: str = "ner"  # ner, manual, inferred

    # Occurrences
    occurrence_count: int = 0
    occurrences: List[EntityOccurrence] = field(default_factory=list)

    # Context samples
    context_samples: List[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentFilter:
    """
    Filter criteria for document queries.
    """
    status: Optional[DocumentStatus] = None
    file_type: Optional[str] = None
    project_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Date range
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    # Search
    search_query: Optional[str] = None

    # Pagination
    page: int = 1
    page_size: int = 20
    sort_field: str = "created_at"
    sort_order: str = "desc"


@dataclass
class DocumentStatistics:
    """
    Aggregate statistics about documents.
    """
    # Counts
    total_documents: int = 0
    uploaded_count: int = 0
    processing_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    archived_count: int = 0

    # Sizes
    total_size_bytes: int = 0
    average_size_bytes: int = 0

    # Content
    total_pages: int = 0
    total_chunks: int = 0
    total_entities: int = 0

    # File types
    file_type_counts: Dict[str, int] = field(default_factory=dict)

    # Recent activity
    documents_added_today: int = 0
    documents_processed_today: int = 0

    computed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BatchOperationResult:
    """
    Result of a batch operation on documents.
    """
    success: bool
    processed: int
    failed: int
    errors: List[str] = field(default_factory=list)
    message: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
