"""
Reports Shard - Data Models

Pydantic models and dataclasses for report generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class ReportType(str, Enum):
    """Type of report to generate."""
    SUMMARY = "summary"                     # System-wide summary
    ENTITY_PROFILE = "entity_profile"       # Entity profile report
    TIMELINE = "timeline"                   # Timeline report
    CONTRADICTION = "contradiction"         # Contradiction analysis
    ACH_ANALYSIS = "ach_analysis"           # ACH analysis report
    CUSTOM = "custom"                       # Custom user-defined report


class ReportStatus(str, Enum):
    """Status of report generation."""
    PENDING = "pending"         # Queued for generation
    GENERATING = "generating"   # Currently being generated
    COMPLETED = "completed"     # Successfully generated
    FAILED = "failed"           # Generation failed


class ReportFormat(str, Enum):
    """Output format for reports."""
    HTML = "html"               # Rich HTML format
    PDF = "pdf"                 # PDF document
    MARKDOWN = "markdown"       # Markdown format
    JSON = "json"               # Structured JSON data


# === Dataclasses ===

@dataclass
class Report:
    """
    A generated analytical report.

    Reports aggregate data from multiple sources and present
    it in various formats for analysis and export.
    """
    id: str
    report_type: ReportType
    title: str
    status: ReportStatus = ReportStatus.PENDING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Generation parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Output
    output_format: ReportFormat = ReportFormat.HTML
    file_path: Optional[str] = None
    file_size: Optional[int] = None          # Bytes

    # Error tracking
    error: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportTemplate:
    """
    A reusable report template.

    Templates define report structure, parameters, and
    generation logic for consistent reporting.
    """
    id: str
    name: str
    report_type: ReportType
    description: str

    # Template configuration
    parameters_schema: Dict[str, Any] = field(default_factory=dict)  # JSON schema
    default_format: ReportFormat = ReportFormat.HTML
    template_content: str = ""               # Template markup/code

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSchedule:
    """
    A scheduled report generation.

    Schedules automate periodic report generation.
    """
    id: str
    template_id: str
    cron_expression: str                     # Cron schedule (e.g., "0 9 * * 1")
    enabled: bool = True

    # Execution tracking
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    # Generation parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    output_format: ReportFormat = ReportFormat.HTML

    # Retention
    retention_days: int = 30                 # Keep reports for N days

    # Delivery (future feature)
    email_recipients: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedSection:
    """
    A section within a generated report.

    Reports are composed of hierarchical sections with
    content, charts, and tables.
    """
    title: str
    content: str = ""                        # Section content (text/HTML/markdown)

    # Visualizations
    charts: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)

    # Hierarchy
    subsections: List['GeneratedSection'] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportGenerationResult:
    """
    Result of report generation.
    """
    report_id: str
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    processing_time_ms: float = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReportStatistics:
    """
    Statistics about reports in the system.
    """
    total_reports: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_format: Dict[str, int] = field(default_factory=dict)

    total_templates: int = 0
    total_schedules: int = 0
    active_schedules: int = 0

    total_file_size_bytes: int = 0
    avg_generation_time_ms: float = 0.0

    reports_last_24h: int = 0
    reports_last_7d: int = 0
    reports_last_30d: int = 0


@dataclass
class ReportFilter:
    """
    Filter criteria for report queries.
    """
    status: Optional[ReportStatus] = None
    report_type: Optional[ReportType] = None
    output_format: Optional[ReportFormat] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search_text: Optional[str] = None
