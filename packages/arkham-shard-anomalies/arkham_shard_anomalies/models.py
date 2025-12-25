"""Data models for the Anomalies Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AnomalyType(Enum):
    """Type of anomaly detected."""
    CONTENT = "content"  # Semantically distant from corpus
    METADATA = "metadata"  # Unusual file properties
    TEMPORAL = "temporal"  # Unexpected dates/time references
    STRUCTURAL = "structural"  # Unusual document structure
    STATISTICAL = "statistical"  # Unusual word frequencies, patterns
    RED_FLAG = "red_flag"  # Sensitive content indicators


class AnomalyStatus(Enum):
    """Status of an anomaly in analyst workflow."""
    DETECTED = "detected"  # Newly detected
    CONFIRMED = "confirmed"  # Analyst confirmed as anomalous
    DISMISSED = "dismissed"  # Analyst dismissed as normal
    FALSE_POSITIVE = "false_positive"  # Algorithm error


class SeverityLevel(Enum):
    """Severity level of anomaly."""
    CRITICAL = "critical"  # Highly anomalous, needs immediate attention
    HIGH = "high"  # Significantly anomalous
    MEDIUM = "medium"  # Moderately anomalous
    LOW = "low"  # Slightly anomalous


@dataclass
class Anomaly:
    """An anomaly detected in a document."""
    id: str
    doc_id: str
    anomaly_type: AnomalyType
    status: AnomalyStatus = AnomalyStatus.DETECTED

    # Scoring
    score: float = 0.0  # Anomaly score (higher = more anomalous)
    severity: SeverityLevel = SeverityLevel.MEDIUM
    confidence: float = 1.0  # Confidence in detection (0.0 to 1.0)

    # Details
    explanation: str = ""  # Human-readable explanation
    details: dict[str, Any] = field(default_factory=dict)  # Technical details

    # Context
    field_name: str | None = None  # Specific field that is anomalous
    expected_range: str | None = None  # What was expected
    actual_value: str | None = None  # What was found

    # Metadata
    detected_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    # Analyst notes
    notes: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class AnomalyPattern:
    """A pattern of anomalies across multiple documents."""
    id: str
    pattern_type: str
    description: str

    # Related anomalies
    anomaly_ids: list[str] = field(default_factory=list)
    doc_ids: list[str] = field(default_factory=list)

    # Pattern details
    frequency: int = 0  # How many times this pattern appears
    confidence: float = 1.0

    # Metadata
    detected_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class OutlierResult:
    """Result of outlier detection analysis."""
    doc_id: str
    is_outlier: bool

    # Distance metrics
    distance_from_centroid: float = 0.0
    z_score: float = 0.0

    # Context
    cluster_id: str | None = None
    nearest_neighbors: list[str] = field(default_factory=list)

    # Metadata
    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DetectionConfig:
    """Configuration for anomaly detection."""
    # Statistical thresholds
    z_score_threshold: float = 3.0  # Standard deviations for outlier
    min_cluster_distance: float = 0.7  # Cosine distance threshold

    # Detection toggles
    detect_content: bool = True
    detect_metadata: bool = True
    detect_temporal: bool = True
    detect_structural: bool = True
    detect_statistical: bool = True
    detect_red_flags: bool = True

    # Red flag patterns
    money_patterns: bool = True
    date_patterns: bool = True
    name_patterns: bool = True
    sensitive_keywords: bool = True

    # Processing
    batch_size: int = 100
    min_confidence: float = 0.5


@dataclass
class DetectRequest:
    """Request to run anomaly detection."""
    project_id: str | None = None
    doc_ids: list[str] = field(default_factory=list)  # Empty = all docs
    config: DetectionConfig = field(default_factory=DetectionConfig)


@dataclass
class PatternRequest:
    """Request to detect unusual patterns."""
    anomaly_ids: list[str] = field(default_factory=list)  # Empty = all anomalies
    min_frequency: int = 2  # Minimum occurrences to be a pattern
    pattern_types: list[str] = field(default_factory=list)  # Empty = all types


@dataclass
class AnomalyResult:
    """Result of anomaly detection operation."""
    anomalies_detected: int
    anomalies: list[Anomaly] = field(default_factory=list)
    duration_ms: float = 0.0
    config_used: DetectionConfig | None = None


@dataclass
class AnomalyList:
    """Paginated list of anomalies."""
    total: int
    items: list[Anomaly] = field(default_factory=list)
    offset: int = 0
    limit: int = 20
    has_more: bool = False

    # Facets for filtering
    facets: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyStats:
    """Statistics about detected anomalies."""
    total_anomalies: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)

    # Recent activity
    detected_last_24h: int = 0
    confirmed_last_24h: int = 0
    dismissed_last_24h: int = 0

    # Quality metrics
    false_positive_rate: float = 0.0
    avg_confidence: float = 0.0

    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StatusUpdate:
    """Update to anomaly status."""
    status: AnomalyStatus
    notes: str = ""
    reviewed_by: str | None = None


@dataclass
class AnalystNote:
    """Note added by analyst to an anomaly."""
    id: str
    anomaly_id: str
    author: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
