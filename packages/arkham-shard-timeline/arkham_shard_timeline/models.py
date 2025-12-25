"""Data models for the Timeline Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(Enum):
    """Timeline event types."""
    OCCURRENCE = "occurrence"  # Event that happened
    REFERENCE = "reference"    # Reference to a date
    DEADLINE = "deadline"      # Future deadline or target date
    PERIOD = "period"          # Time period or range


class DatePrecision(Enum):
    """Date precision levels."""
    EXACT = "exact"          # Exact timestamp
    DAY = "day"              # Day precision
    WEEK = "week"            # Week precision
    MONTH = "month"          # Month precision
    QUARTER = "quarter"      # Quarter precision
    YEAR = "year"            # Year precision
    DECADE = "decade"        # Decade precision
    CENTURY = "century"      # Century precision
    APPROXIMATE = "approximate"  # Approximate/fuzzy


class ConflictType(Enum):
    """Types of temporal conflicts."""
    CONTRADICTION = "contradiction"      # Direct contradiction
    INCONSISTENCY = "inconsistency"      # Logical inconsistency
    GAP = "gap"                          # Missing timeline segment
    OVERLAP = "overlap"                  # Incompatible overlap


class ConflictSeverity(Enum):
    """Conflict severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MergeStrategy(Enum):
    """Timeline merge strategies."""
    CHRONOLOGICAL = "chronological"      # Simple chronological sort
    DEDUPLICATED = "deduplicated"        # Remove duplicates
    CONSOLIDATED = "consolidated"        # Merge similar events
    SOURCE_PRIORITY = "source_priority"  # Prioritize certain sources


@dataclass
class TimelineEvent:
    """
    A temporal event extracted from a document.

    Attributes:
        id: Unique event identifier
        document_id: Source document ID
        text: Original text mentioning the date
        date_start: Normalized start datetime
        date_end: Normalized end datetime (for periods)
        precision: Date precision level
        confidence: Extraction confidence (0-1)
        entities: Entity IDs mentioned in event
        event_type: Type of temporal event
        span: Character span in source text (start, end)
        metadata: Additional context and data
    """
    id: str
    document_id: str
    text: str
    date_start: datetime
    date_end: Optional[datetime] = None
    precision: DatePrecision = DatePrecision.DAY
    confidence: float = 1.0
    entities: list[str] = field(default_factory=list)
    event_type: EventType = EventType.OCCURRENCE
    span: Optional[tuple[int, int]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DateRange:
    """Date range for filtering."""
    start: Optional[datetime] = None
    end: Optional[datetime] = None


@dataclass
class ExtractionContext:
    """Context for date extraction."""
    reference_date: Optional[datetime] = None  # Reference for relative dates
    timezone: str = "UTC"
    prefer_future: bool = False  # For ambiguous relative dates
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedDate:
    """Result of date normalization."""
    original: str
    normalized: datetime
    precision: DatePrecision
    confidence: float
    is_range: bool = False
    range_end: Optional[datetime] = None


@dataclass
class TemporalConflict:
    """
    A detected temporal conflict between events.

    Attributes:
        id: Unique conflict identifier
        type: Type of conflict
        severity: Severity level
        events: Event IDs involved
        description: Human-readable description
        documents: Document IDs involved
        suggested_resolution: Suggested way to resolve
        metadata: Additional context
    """
    id: str
    type: ConflictType
    severity: ConflictSeverity
    events: list[str]
    description: str
    documents: list[str]
    suggested_resolution: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineStats:
    """Statistics about a timeline."""
    total_events: int
    total_documents: int
    date_range: DateRange
    by_precision: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    conflicts_detected: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MergeResult:
    """Result of merging timelines."""
    events: list[TimelineEvent]
    count: int
    sources: dict[str, int]  # document_id -> event_count
    date_range: DateRange
    duplicates_removed: int = 0
    conflicts_found: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of event extraction."""
    events: list[TimelineEvent]
    count: int
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineQuery:
    """Query parameters for timeline retrieval."""
    document_ids: Optional[list[str]] = None
    entity_ids: Optional[list[str]] = None
    event_types: Optional[list[EventType]] = None
    date_range: Optional[DateRange] = None
    min_confidence: float = 0.0
    limit: int = 100
    offset: int = 0


@dataclass
class EntityTimeline:
    """Timeline for a specific entity."""
    entity_id: str
    events: list[TimelineEvent]
    count: int
    date_range: DateRange
    related_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
