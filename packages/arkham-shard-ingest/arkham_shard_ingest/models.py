"""Data models for the Ingest Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class FileCategory(Enum):
    """High-level file categories."""
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


class ImageQuality(Enum):
    """Image quality classification."""
    CLEAN = "clean"      # Direct to OCR
    FIXABLE = "fixable"  # Light preprocessing needed
    MESSY = "messy"      # Heavy preprocessing or smart OCR


class JobPriority(Enum):
    """Job priority levels."""
    USER = 1      # User-initiated uploads (highest)
    BATCH = 2     # Batch imports
    REPROCESS = 3 # Re-processing requests


class JobStatus(Enum):
    """Job processing status."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"  # Failed after all retries


@dataclass
class FileInfo:
    """Information about an ingested file."""
    path: Path
    original_name: str
    size_bytes: int
    mime_type: str
    category: FileCategory
    extension: str

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    checksum: str | None = None

    # For images
    width: int | None = None
    height: int | None = None
    dpi: int | None = None

    # For documents
    page_count: int | None = None


@dataclass
class ImageQualityScore:
    """
    Quality assessment for images.
    Used to route to appropriate OCR worker.
    """
    dpi: int
    skew_angle: float      # degrees
    contrast_ratio: float  # 0.0 - 1.0
    is_grayscale: bool
    compression_ratio: float
    has_noise: bool
    layout_complexity: str  # simple | table | mixed | complex

    # Analysis time
    analysis_ms: float = 0.0

    @property
    def classification(self) -> ImageQuality:
        """Classify as CLEAN, FIXABLE, or MESSY."""
        issues = 0

        if self.dpi < 150:
            issues += 1
        if abs(self.skew_angle) > 2.0:
            issues += 1
        if self.contrast_ratio < 0.4:
            issues += 1
        if self.has_noise:
            issues += 1

        if issues == 0:
            return ImageQuality.CLEAN
        elif issues <= 2 and self.layout_complexity in ("simple", "table"):
            return ImageQuality.FIXABLE
        else:
            return ImageQuality.MESSY

    @property
    def issues(self) -> list[str]:
        """List of detected issues."""
        result = []
        if self.dpi < 150:
            result.append(f"low_dpi:{self.dpi}")
        if abs(self.skew_angle) > 2.0:
            result.append(f"skewed:{self.skew_angle:.1f}deg")
        if self.contrast_ratio < 0.4:
            result.append(f"low_contrast:{self.contrast_ratio:.2f}")
        if self.has_noise:
            result.append("noisy")
        if self.layout_complexity in ("mixed", "complex"):
            result.append(f"complex_layout:{self.layout_complexity}")
        return result


@dataclass
class IngestJob:
    """A job in the ingest pipeline."""
    id: str
    file_info: FileInfo
    priority: JobPriority
    status: JobStatus = JobStatus.PENDING

    # Routing
    worker_route: list[str] = field(default_factory=list)
    current_worker: str | None = None

    # For images
    quality_score: ImageQualityScore | None = None

    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries


@dataclass
class IngestBatch:
    """A batch of files being ingested together."""
    id: str
    jobs: list[IngestJob] = field(default_factory=list)
    priority: JobPriority = JobPriority.BATCH

    # Progress
    total_files: int = 0
    completed: int = 0
    failed: int = 0

    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def pending(self) -> int:
        return self.total_files - self.completed - self.failed

    @property
    def is_complete(self) -> bool:
        return self.pending == 0
