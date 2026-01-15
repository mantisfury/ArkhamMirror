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
    REGEX = "regex"


class RegexFlag(Enum):
    """Regex flags for pattern matching."""
    CASE_INSENSITIVE = "case_insensitive"
    MULTILINE = "multiline"
    DOTALL = "dotall"


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


# --- Regex Search Models ---


@dataclass
class RegexMatch:
    """Individual regex match result."""
    document_id: str
    document_title: str
    page_number: int | None
    chunk_id: str | None
    match_text: str
    context: str
    start_offset: int
    end_offset: int
    line_number: int | None = None


@dataclass
class RegexSearchQuery:
    """Regex search query parameters."""
    pattern: str
    flags: list[str] = field(default_factory=list)
    project_id: str | None = None
    document_ids: list[str] | None = None
    limit: int = 100
    offset: int = 0
    highlight: bool = True
    context_chars: int = 100


@dataclass
class RegexSearchResult:
    """Regex search result container."""
    pattern: str
    matches: list[RegexMatch] = field(default_factory=list)
    total_matches: int = 0
    total_chunks_with_matches: int = 0
    documents_searched: int = 0
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class RegexPreset:
    """Predefined regex pattern."""
    id: str
    name: str
    pattern: str
    description: str
    category: str  # pii, contact, financial, technical, custom
    flags: list[str] = field(default_factory=list)
    is_system: bool = True
