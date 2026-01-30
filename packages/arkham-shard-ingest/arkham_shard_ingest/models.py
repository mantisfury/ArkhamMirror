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

    # Extension vs detected mime: True if file extension matches detected mime_type
    extension_fidelity: bool = True

    # Filesystem stat times (from path.stat())
    access_time: datetime | None = None
    modification_time: datetime | None = None
    creation_time: datetime | None = None

    # For images
    width: int | None = None
    height: int | None = None
    dpi: int | None = None

    # For documents
    page_count: int | None = None

    # True for archive formats (zip, tar, 7z, rar, etc.) and container formats (docx, xlsx, jar, etc.)
    is_archive: bool = False


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
    is_blank: bool = False  # True if page appears blank/near-blank

    # Analysis time
    analysis_ms: float = 0.0

    # DPI thresholds for downscaling
    DOWNSCALE_THRESHOLD_DPI: int = 200
    TARGET_DPI: int = 150

    @property
    def needs_downscale(self) -> bool:
        """Check if image should be downscaled for OCR (memory optimization)."""
        return self.dpi > self.DOWNSCALE_THRESHOLD_DPI

    @property
    def downscale_factor(self) -> float:
        """Calculate downscale factor to reach target DPI."""
        if not self.needs_downscale:
            return 1.0
        return self.TARGET_DPI / self.dpi

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

    # Project association
    project_id: str | None = None

    # Optional upload metadata (stored in document metadata)
    original_file_path: str | None = None  # Path when available (e.g. path-based ingest)
    provenance: dict[str, Any] | None = None  # source_url, source_description, custodian, acquisition_date, etc.

    # Archive handling
    extract_archives: bool = False  # If True and file is a typical archive (zip, tar, etc.), extract and queue members
    from_archive: bool = False  # True if this file was extracted from an archive
    source_archive_document_id: str | None = None  # Document ID of the parent archive (when from_archive=True)
    archive_member_path: str | None = None  # Path within the archive (when from_archive=True)

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
