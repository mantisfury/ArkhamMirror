"""
Letters Shard - Data Models

Pydantic models and dataclasses for letter generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class LetterType(str, Enum):
    """Type of letter to generate."""
    FOIA = "foia"                       # FOIA request
    COMPLAINT = "complaint"             # Formal complaint
    DEMAND = "demand"                   # Demand letter
    NOTICE = "notice"                   # Notice letter
    COVER = "cover"                     # Cover letter
    INQUIRY = "inquiry"                 # Information inquiry
    RESPONSE = "response"               # Response letter
    CUSTOM = "custom"                   # Custom letter type


class LetterStatus(str, Enum):
    """Status of letter."""
    DRAFT = "draft"                     # Work in progress
    REVIEW = "review"                   # Ready for review
    FINALIZED = "finalized"             # Finalized, ready to send
    SENT = "sent"                       # Marked as sent


class ExportFormat(str, Enum):
    """Export format for letters."""
    PDF = "pdf"                         # PDF document
    DOCX = "docx"                       # Microsoft Word document
    HTML = "html"                       # HTML format
    MARKDOWN = "markdown"               # Markdown format
    TXT = "txt"                         # Plain text


# === Dataclasses ===

@dataclass
class Letter:
    """
    A formal letter document.

    Letters are generated from templates with placeholder substitution
    and can be exported to various formats.
    """
    id: str
    title: str
    letter_type: LetterType
    status: LetterStatus = LetterStatus.DRAFT

    # Content
    content: str = ""                   # Letter body content
    template_id: Optional[str] = None   # Template used (if any)

    # Recipients and sender
    recipient_name: Optional[str] = None
    recipient_address: Optional[str] = None
    recipient_email: Optional[str] = None
    sender_name: Optional[str] = None
    sender_address: Optional[str] = None
    sender_email: Optional[str] = None

    # Subject and reference
    subject: Optional[str] = None
    reference_number: Optional[str] = None
    re_line: Optional[str] = None       # RE: line for legal letters

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    # Export tracking
    last_export_format: Optional[ExportFormat] = None
    last_export_path: Optional[str] = None
    last_exported_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LetterTemplate:
    """
    A reusable letter template.

    Templates contain placeholder variables that are replaced
    with actual values when generating a letter.
    """
    id: str
    name: str
    letter_type: LetterType
    description: str

    # Template content
    content_template: str               # Template with {{placeholders}}
    subject_template: Optional[str] = None  # Subject line template

    # Placeholders
    placeholders: List[str] = field(default_factory=list)  # Available placeholders
    required_placeholders: List[str] = field(default_factory=list)  # Must be filled

    # Default values
    default_sender_name: Optional[str] = None
    default_sender_address: Optional[str] = None
    default_sender_email: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LetterExportResult:
    """
    Result of letter export operation.
    """
    letter_id: str
    success: bool
    export_format: ExportFormat
    file_path: Optional[str] = None
    file_size: Optional[int] = None     # Bytes
    processing_time_ms: float = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class LetterStatistics:
    """
    Statistics about letters in the system.
    """
    total_letters: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)

    total_templates: int = 0
    by_template_type: Dict[str, int] = field(default_factory=dict)

    letters_last_24h: int = 0
    letters_last_7d: int = 0
    letters_last_30d: int = 0

    total_exports: int = 0
    by_export_format: Dict[str, int] = field(default_factory=dict)


@dataclass
class LetterFilter:
    """
    Filter criteria for letter queries.
    """
    status: Optional[LetterStatus] = None
    letter_type: Optional[LetterType] = None
    template_id: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search_text: Optional[str] = None   # Search in title, content, recipient


@dataclass
class PlaceholderValue:
    """
    A placeholder and its value for template rendering.
    """
    key: str                            # Placeholder key (without {{ }})
    value: str                          # Value to substitute
    required: bool = False              # Is this placeholder required?
