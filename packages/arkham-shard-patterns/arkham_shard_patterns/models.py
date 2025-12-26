"""
Patterns Shard - Pydantic Models

Models for cross-document pattern detection and analysis.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Types of patterns that can be detected."""
    RECURRING_THEME = "recurring_theme"      # Theme appearing in multiple documents
    BEHAVIORAL = "behavioral"                 # Consistent behavior of an entity
    TEMPORAL = "temporal"                     # Time-based pattern (cycles, sequences)
    CORRELATION = "correlation"               # Statistical correlation between entities
    LINGUISTIC = "linguistic"                 # Language/style pattern
    STRUCTURAL = "structural"                 # Document structure pattern
    CUSTOM = "custom"                         # User-defined pattern


class PatternStatus(str, Enum):
    """Status of a detected pattern."""
    DETECTED = "detected"       # Automatically detected, pending review
    CONFIRMED = "confirmed"     # Manually confirmed as valid
    DISMISSED = "dismissed"     # Dismissed as noise/false positive
    ARCHIVED = "archived"       # No longer active but preserved


class DetectionMethod(str, Enum):
    """How the pattern was detected."""
    MANUAL = "manual"           # User-reported pattern
    AUTOMATED = "automated"     # System-detected pattern
    LLM = "llm"                 # LLM-assisted detection
    HYBRID = "hybrid"           # Combination of methods


class SourceType(str, Enum):
    """Type of source that matched a pattern."""
    DOCUMENT = "document"
    ENTITY = "entity"
    CLAIM = "claim"
    EVENT = "event"
    CHUNK = "chunk"


class PatternCriteria(BaseModel):
    """Criteria for matching a pattern."""
    keywords: Optional[List[str]] = Field(default_factory=list)
    regex_patterns: Optional[List[str]] = Field(default_factory=list)
    entity_types: Optional[List[str]] = Field(default_factory=list)
    entity_ids: Optional[List[str]] = Field(default_factory=list)
    min_occurrences: int = Field(default=2)
    time_window_days: Optional[int] = None
    similarity_threshold: float = Field(default=0.8)
    custom_rules: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Pattern(BaseModel):
    """A detected pattern across documents."""
    id: str
    name: str
    description: str
    pattern_type: PatternType
    status: PatternStatus = PatternStatus.DETECTED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    match_count: int = Field(default=0)
    document_count: int = Field(default=0)
    entity_count: int = Field(default=0)

    first_detected: datetime = Field(default_factory=datetime.utcnow)
    last_matched: Optional[datetime] = None

    detection_method: DetectionMethod = DetectionMethod.MANUAL
    detection_model: Optional[str] = None

    criteria: PatternCriteria = Field(default_factory=PatternCriteria)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")

    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class PatternCreate(BaseModel):
    """Request to create a new pattern."""
    name: str
    description: str
    pattern_type: PatternType
    criteria: Optional[PatternCriteria] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class PatternUpdate(BaseModel):
    """Request to update a pattern."""
    name: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[PatternCriteria] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: Optional[PatternStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class PatternMatch(BaseModel):
    """A match of a pattern in a source."""
    id: str
    pattern_id: str

    source_type: SourceType
    source_id: str
    source_title: Optional[str] = None

    match_score: float = Field(default=1.0, ge=0.0, le=1.0)
    excerpt: Optional[str] = None
    context: Optional[str] = None

    start_char: Optional[int] = None
    end_char: Optional[int] = None

    matched_at: datetime = Field(default_factory=datetime.utcnow)
    matched_by: str = Field(default="system")

    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class PatternMatchCreate(BaseModel):
    """Request to add a match to a pattern."""
    source_type: SourceType
    source_id: str
    source_title: Optional[str] = None
    match_score: float = Field(default=1.0, ge=0.0, le=1.0)
    excerpt: Optional[str] = None
    context: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class PatternFilter(BaseModel):
    """Filter criteria for listing patterns."""
    pattern_type: Optional[PatternType] = None
    status: Optional[PatternStatus] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    min_matches: Optional[int] = None
    detection_method: Optional[DetectionMethod] = None
    search_text: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


class PatternAnalysisRequest(BaseModel):
    """Request to analyze documents for patterns."""
    document_ids: Optional[List[str]] = None
    text: Optional[str] = None
    pattern_types: Optional[List[PatternType]] = None
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    max_patterns: int = Field(default=20, ge=1, le=100)


class PatternAnalysisResult(BaseModel):
    """Result of pattern analysis."""
    patterns_detected: List[Pattern] = Field(default_factory=list)
    matches_found: List[PatternMatch] = Field(default_factory=list)
    documents_analyzed: int = 0
    processing_time_ms: float = 0.0
    errors: List[str] = Field(default_factory=list)


class CorrelationRequest(BaseModel):
    """Request to find correlations between entities."""
    entity_ids: List[str]
    time_window_days: Optional[int] = Field(default=90)
    min_occurrences: int = Field(default=3)
    correlation_types: Optional[List[str]] = None


class Correlation(BaseModel):
    """A detected correlation between entities."""
    entity_id_1: str
    entity_id_2: str
    correlation_score: float = Field(ge=-1.0, le=1.0)
    co_occurrence_count: int
    document_ids: List[str] = Field(default_factory=list)
    correlation_type: str
    description: str


class CorrelationResult(BaseModel):
    """Result of correlation analysis."""
    correlations: List[Correlation] = Field(default_factory=list)
    entities_analyzed: int = 0
    processing_time_ms: float = 0.0


class PatternStatistics(BaseModel):
    """Statistics about patterns in the system."""
    total_patterns: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_detection_method: Dict[str, int] = Field(default_factory=dict)
    total_matches: int = 0
    avg_confidence: float = 0.0
    avg_matches_per_pattern: float = 0.0
    patterns_confirmed: int = 0
    patterns_dismissed: int = 0
    patterns_pending_review: int = 0


class PatternListResponse(BaseModel):
    """Response for pattern listing."""
    items: List[Pattern]
    total: int
    page: int
    page_size: int


class PatternMatchListResponse(BaseModel):
    """Response for match listing."""
    items: List[PatternMatch]
    total: int
    page: int
    page_size: int
