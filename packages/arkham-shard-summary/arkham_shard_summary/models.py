"""
Summary Shard - Data Models

Pydantic models and dataclasses for auto-summarization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class SummaryType(str, Enum):
    """Type of summary to generate."""
    BRIEF = "brief"                   # Short 1-2 sentence summary
    DETAILED = "detailed"             # Comprehensive multi-paragraph summary
    EXECUTIVE = "executive"           # Executive summary with key findings
    BULLET_POINTS = "bullet_points"   # Key points as bullet list
    ABSTRACT = "abstract"             # Academic-style abstract


class SourceType(str, Enum):
    """Type of source being summarized."""
    DOCUMENT = "document"             # Single document
    DOCUMENTS = "documents"           # Collection of documents
    ENTITY = "entity"                 # Entity with related documents
    PROJECT = "project"               # Entire project
    CLAIM_SET = "claim_set"           # Set of related claims
    TIMELINE = "timeline"             # Timeline of events
    ANALYSIS = "analysis"             # Analysis result (ACH, etc.)


class SummaryStatus(str, Enum):
    """Status of summary generation."""
    PENDING = "pending"               # Queued for generation
    GENERATING = "generating"         # Currently being generated
    COMPLETED = "completed"           # Successfully generated
    FAILED = "failed"                 # Generation failed
    STALE = "stale"                   # Source content has changed


class SummaryLength(str, Enum):
    """Target length for summary."""
    VERY_SHORT = "very_short"         # ~50 words
    SHORT = "short"                   # ~100 words
    MEDIUM = "medium"                 # ~250 words
    LONG = "long"                     # ~500 words
    VERY_LONG = "very_long"           # ~1000 words


# === Dataclasses ===

@dataclass
class Summary:
    """
    A generated summary of content.

    Summaries can be of various types (brief, detailed, executive, etc.)
    and can summarize single or multiple sources.
    """
    id: str
    summary_type: SummaryType = SummaryType.DETAILED
    status: SummaryStatus = SummaryStatus.COMPLETED

    # Source information
    source_type: SourceType = SourceType.DOCUMENT
    source_ids: List[str] = field(default_factory=list)  # IDs of source items
    source_titles: List[str] = field(default_factory=list)  # Titles for display

    # Summary content
    content: str = ""                                    # The summary text
    key_points: List[str] = field(default_factory=list)  # Extracted key points
    title: Optional[str] = None                          # Auto-generated title

    # Generation metadata
    model_used: Optional[str] = None                     # LLM model used
    token_count: int = 0                                 # Approximate token count
    word_count: int = 0                                  # Word count
    target_length: SummaryLength = SummaryLength.MEDIUM

    # Quality metrics
    confidence: float = 1.0                              # Confidence in summary (0-1)
    completeness: float = 1.0                            # Coverage of source (0-1)

    # Focus areas (optional constraints)
    focus_areas: List[str] = field(default_factory=list)  # Specific topics to focus on
    exclude_topics: List[str] = field(default_factory=list)  # Topics to exclude

    # Processing
    processing_time_ms: float = 0                        # Time to generate
    error_message: Optional[str] = None                  # Error if failed

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    source_updated_at: Optional[datetime] = None         # When source was last updated

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SummaryRequest:
    """
    Request to generate a summary.
    """
    source_type: SourceType
    source_ids: List[str]
    summary_type: SummaryType = SummaryType.DETAILED
    target_length: SummaryLength = SummaryLength.MEDIUM

    # Optional constraints
    focus_areas: List[str] = field(default_factory=list)
    exclude_topics: List[str] = field(default_factory=list)
    max_tokens: Optional[int] = None

    # Options
    include_key_points: bool = True
    include_title: bool = True

    # Metadata
    tags: List[str] = field(default_factory=list)


@dataclass
class SummaryResult:
    """
    Result of summary generation.
    """
    summary_id: str
    status: SummaryStatus

    # Generated content
    content: str = ""
    key_points: List[str] = field(default_factory=list)
    title: Optional[str] = None

    # Metrics
    token_count: int = 0
    word_count: int = 0
    processing_time_ms: float = 0
    confidence: float = 1.0

    # Error handling
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class BatchSummaryRequest:
    """
    Request to generate summaries for multiple sources.
    """
    requests: List[SummaryRequest]
    parallel: bool = False                               # Generate in parallel
    stop_on_error: bool = False                          # Stop if one fails


@dataclass
class BatchSummaryResult:
    """
    Result of batch summary generation.
    """
    total: int
    successful: int
    failed: int
    summaries: List[SummaryResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_processing_time_ms: float = 0


@dataclass
class SummaryUpdate:
    """
    Update to an existing summary.
    """
    summary_type: Optional[SummaryType] = None
    target_length: Optional[SummaryLength] = None
    focus_areas: Optional[List[str]] = None
    exclude_topics: Optional[List[str]] = None
    regenerate: bool = False                             # Force regeneration


@dataclass
class SummaryFilter:
    """
    Filter criteria for summary queries.
    """
    summary_type: Optional[SummaryType] = None
    source_type: Optional[SourceType] = None
    source_id: Optional[str] = None
    status: Optional[SummaryStatus] = None
    model_used: Optional[str] = None
    min_confidence: Optional[float] = None
    tags: Optional[List[str]] = None
    search_text: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


@dataclass
class SummaryStatistics:
    """
    Statistics about summaries in the system.
    """
    total_summaries: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_source_type: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    by_model: Dict[str, int] = field(default_factory=dict)

    # Quality metrics
    avg_confidence: float = 0.0
    avg_completeness: float = 0.0
    avg_word_count: float = 0.0
    avg_processing_time_ms: float = 0.0

    # Recent activity
    generated_last_24h: int = 0
    failed_last_24h: int = 0

    # Content stats
    total_words_generated: int = 0
    total_tokens_used: int = 0


@dataclass
class KeyPoint:
    """
    A key point extracted from a summary or source.
    """
    text: str
    importance: float = 1.0                              # Importance score (0-1)
    source_reference: Optional[str] = None               # Reference to source
    page_number: Optional[int] = None
    section: Optional[str] = None


@dataclass
class SummaryTemplate:
    """
    Template for generating structured summaries.
    """
    id: str
    name: str
    description: str

    # Template structure
    sections: List[str] = field(default_factory=list)   # Section names
    prompt_template: str = ""                            # Template for LLM prompt

    # Target configuration
    default_type: SummaryType = SummaryType.DETAILED
    default_length: SummaryLength = SummaryLength.MEDIUM

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SummaryComparison:
    """
    Comparison between two summaries.
    """
    summary_id_1: str
    summary_id_2: str

    # Similarity metrics
    similarity_score: float = 0.0                        # 0-1 similarity
    common_points: List[str] = field(default_factory=list)
    unique_to_1: List[str] = field(default_factory=list)
    unique_to_2: List[str] = field(default_factory=list)

    # Analysis
    notes: str = ""


@dataclass
class RegenerationTrigger:
    """
    Criteria for auto-regenerating summaries when source changes.
    """
    enabled: bool = True
    min_change_threshold: float = 0.1                    # Minimum change to trigger (0-1)
    auto_regenerate: bool = False                        # Auto-regenerate vs mark stale
    preserve_previous: bool = True                       # Keep previous version
