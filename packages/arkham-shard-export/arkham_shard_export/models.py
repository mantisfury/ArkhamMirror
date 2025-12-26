"""
Export Shard - Data Models

Pydantic models and dataclasses for export management.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"


class ExportStatus(str, Enum):
    """Status of an export job."""
    PENDING = "pending"           # Job created, not yet started
    PROCESSING = "processing"     # Job in progress
    COMPLETED = "completed"       # Job finished successfully
    FAILED = "failed"             # Job failed with error
    CANCELLED = "cancelled"       # Job cancelled by user


class ExportTarget(str, Enum):
    """Type of data to export."""
    DOCUMENTS = "documents"       # Document records
    ENTITIES = "entities"         # Extracted entities
    CLAIMS = "claims"             # Claims with evidence
    TIMELINE = "timeline"         # Timeline events
    GRAPH = "graph"               # Graph nodes and edges
    MATRIX = "matrix"             # ACH matrix data
    CUSTOM = "custom"             # Custom query result


# === Dataclasses ===

@dataclass
class ExportOptions:
    """
    Options for customizing export output.
    """
    include_metadata: bool = True                    # Include system metadata
    include_relationships: bool = True               # Include related entities
    date_range_start: Optional[datetime] = None      # Filter start date
    date_range_end: Optional[datetime] = None        # Filter end date
    entity_types: Optional[List[str]] = None         # Filter by entity types
    flatten: bool = False                            # Flatten nested structures (CSV)
    max_records: Optional[int] = None                # Limit number of records
    sort_by: Optional[str] = None                    # Sort field
    sort_order: str = "asc"                          # asc or desc


@dataclass
class ExportJob:
    """
    An export job that generates a file.
    """
    id: str
    format: ExportFormat
    target: ExportTarget
    status: ExportStatus = ExportStatus.PENDING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # File information
    file_path: Optional[str] = None                  # Server file path
    file_size: Optional[int] = None                  # Size in bytes
    download_url: Optional[str] = None               # Download URL
    expires_at: Optional[datetime] = None            # File expiration time

    # Job details
    error: Optional[str] = None                      # Error message if failed
    filters: Dict[str, Any] = field(default_factory=dict)
    options: Optional[ExportOptions] = None

    # Metadata
    record_count: int = 0                            # Number of records exported
    processing_time_ms: float = 0                    # Processing time
    created_by: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportResult:
    """
    Result of an export operation.
    """
    job_id: str
    success: bool
    file_path: Optional[str] = None
    file_size: int = 0
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    record_count: int = 0
    processing_time_ms: float = 0
    error: Optional[str] = None


@dataclass
class ExportStatistics:
    """
    Statistics about export operations.
    """
    total_jobs: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_format: Dict[str, int] = field(default_factory=dict)
    by_target: Dict[str, int] = field(default_factory=dict)

    jobs_pending: int = 0
    jobs_processing: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0

    total_records_exported: int = 0
    total_file_size_bytes: int = 0
    avg_processing_time_ms: float = 0.0

    oldest_pending_job: Optional[datetime] = None


@dataclass
class ExportFilter:
    """
    Filter criteria for export job queries.
    """
    status: Optional[ExportStatus] = None
    format: Optional[ExportFormat] = None
    target: Optional[ExportTarget] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    created_by: Optional[str] = None


@dataclass
class FormatInfo:
    """
    Information about an export format.
    """
    format: ExportFormat
    name: str
    description: str
    file_extension: str
    mime_type: str
    supports_flatten: bool = False
    supports_metadata: bool = True
    max_records: Optional[int] = None
    placeholder: bool = False                        # True if not fully implemented


@dataclass
class TargetInfo:
    """
    Information about an export target.
    """
    target: ExportTarget
    name: str
    description: str
    available_formats: List[ExportFormat]
    estimated_record_count: int = 0
    supports_filters: bool = True
