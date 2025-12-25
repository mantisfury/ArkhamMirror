"""Data models for the Search Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SearchMode(Enum):
    """Search mode options."""
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    KEYWORD = "keyword"


class SortBy(Enum):
    """Sort options for search results."""
    RELEVANCE = "relevance"
    DATE = "date"
    TITLE = "title"


class SortOrder(Enum):
    """Sort order options."""
    DESC = "desc"
    ASC = "asc"


@dataclass
class DateRangeFilter:
    """Date range filter."""
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class SearchFilters:
    """Search filters."""
    date_range: DateRangeFilter | None = None
    entity_ids: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    file_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_score: float = 0.0


@dataclass
class SearchQuery:
    """Search query parameters."""
    query: str
    mode: SearchMode = SearchMode.HYBRID
    filters: SearchFilters | None = None
    limit: int = 20
    offset: int = 0
    sort_by: SortBy = SortBy.RELEVANCE
    sort_order: SortOrder = SortOrder.DESC

    # Hybrid search weights
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3


@dataclass
class SearchResultItem:
    """Individual search result."""
    doc_id: str
    chunk_id: str | None
    title: str
    excerpt: str
    score: float

    # Metadata
    file_type: str | None = None
    created_at: datetime | None = None
    page_number: int | None = None

    # Highlighted content
    highlights: list[str] = field(default_factory=list)

    # Additional context
    entities: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result container."""
    query: str
    mode: SearchMode
    total: int
    items: list[SearchResultItem] = field(default_factory=list)

    # Timing
    duration_ms: float = 0.0

    # Aggregations
    facets: dict[str, Any] = field(default_factory=dict)

    # Pagination
    offset: int = 0
    limit: int = 20
    has_more: bool = False


@dataclass
class SuggestionItem:
    """Autocomplete suggestion item."""
    text: str
    score: float
    type: str  # "entity" | "document" | "term"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimilarityRequest:
    """Request for finding similar documents."""
    doc_id: str
    limit: int = 10
    min_similarity: float = 0.5
    filters: SearchFilters | None = None
