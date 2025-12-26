"""
Packets Shard - Data Models

Pydantic models and dataclasses for packet management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class PacketStatus(str, Enum):
    """Status of a packet in the workflow."""
    DRAFT = "draft"               # In progress, editable
    FINALIZED = "finalized"       # Locked, ready for sharing
    SHARED = "shared"             # Actively shared with others
    ARCHIVED = "archived"         # Inactive, preserved for records


class PacketVisibility(str, Enum):
    """Visibility/access level for a packet."""
    PRIVATE = "private"           # Creator only
    TEAM = "team"                 # Team members
    PUBLIC = "public"             # Anyone with link


class ContentType(str, Enum):
    """Type of content that can be added to a packet."""
    DOCUMENT = "document"         # Full documents
    ENTITY = "entity"             # Entity records
    CLAIM = "claim"               # Claims with evidence
    EVIDENCE_CHAIN = "evidence_chain"  # Evidence graphs
    MATRIX = "matrix"             # ACH matrices
    TIMELINE = "timeline"         # Timeline visualizations
    REPORT = "report"             # Generated reports


class SharePermission(str, Enum):
    """Permission level for packet shares."""
    VIEW = "view"                 # Read-only access
    COMMENT = "comment"           # Can add comments
    EDIT = "edit"                 # Can modify (draft only)


class ExportFormat(str, Enum):
    """Export format for packets."""
    ZIP = "zip"                   # ZIP archive
    TAR_GZ = "tar.gz"             # Compressed tar
    JSON = "json"                 # JSON bundle


# === Dataclasses ===

@dataclass
class Packet:
    """
    An investigation packet bundling related materials.

    Packets organize documents, entities, analyses, and other materials
    into shareable, exportable units.
    """
    id: str
    name: str                                    # Packet name
    description: str = ""                        # Description
    status: PacketStatus = PacketStatus.DRAFT
    visibility: PacketVisibility = PacketVisibility.PRIVATE

    # Ownership
    created_by: str = "system"                   # Creator user ID
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Versioning
    version: int = 1                             # Current version number

    # Content metadata
    contents_count: int = 0                      # Number of items
    size_bytes: int = 0                          # Total size
    checksum: Optional[str] = None               # Content hash

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PacketContent:
    """
    Content item within a packet.

    References external content (documents, entities, etc.) and includes
    ordering and metadata for display.
    """
    id: str
    packet_id: str
    content_type: ContentType
    content_id: str                              # ID of referenced item
    content_title: str                           # Display title
    added_at: datetime = field(default_factory=datetime.utcnow)
    added_by: str = "system"                     # User who added
    order: int = 0                               # Display order


@dataclass
class PacketShare:
    """
    A share grant for a packet.

    Enables controlled access to packets with expiration and permissions.
    """
    id: str
    packet_id: str
    shared_with: str                             # User ID or "public"
    permissions: SharePermission = SharePermission.VIEW
    shared_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_token: str = ""                       # Shareable token


@dataclass
class PacketVersion:
    """
    A version snapshot of a packet.

    Captures packet state at a point in time for version control.
    """
    id: str
    packet_id: str
    version_number: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    changes_summary: str = ""
    snapshot_path: str = ""                      # Path to version snapshot


@dataclass
class PacketExportResult:
    """
    Result of packet export operation.
    """
    packet_id: str
    export_format: ExportFormat
    file_path: str                               # Path to exported file
    file_size_bytes: int
    exported_at: datetime = field(default_factory=datetime.utcnow)
    contents_exported: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class PacketImportResult:
    """
    Result of packet import operation.
    """
    packet_id: str
    import_source: str                           # Source file path
    imported_at: datetime = field(default_factory=datetime.utcnow)
    contents_imported: int = 0
    merge_mode: str = "replace"                  # replace, merge, skip
    errors: List[str] = field(default_factory=list)


@dataclass
class PacketStatistics:
    """
    Statistics about packets in the system.
    """
    total_packets: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_visibility: Dict[str, int] = field(default_factory=dict)

    total_contents: int = 0
    by_content_type: Dict[str, int] = field(default_factory=dict)

    total_shares: int = 0
    active_shares: int = 0
    expired_shares: int = 0

    total_versions: int = 0
    avg_contents_per_packet: float = 0.0
    avg_size_bytes: float = 0.0


@dataclass
class PacketFilter:
    """
    Filter criteria for packet queries.
    """
    status: Optional[PacketStatus] = None
    visibility: Optional[PacketVisibility] = None
    created_by: Optional[str] = None
    search_text: Optional[str] = None
    has_contents: Optional[bool] = None
    min_version: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
