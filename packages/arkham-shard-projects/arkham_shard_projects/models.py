"""
Projects Shard - Data Models

Pydantic models and dataclasses for project workspace management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class ProjectStatus(str, Enum):
    """Status of a project in its lifecycle."""
    ACTIVE = "active"           # Currently in progress
    ARCHIVED = "archived"       # Completed or inactive
    COMPLETED = "completed"     # Successfully finished
    ON_HOLD = "on_hold"         # Temporarily paused


class ProjectRole(str, Enum):
    """Role of a member within a project."""
    OWNER = "owner"             # Full control over project
    ADMIN = "admin"             # Manage members and settings
    EDITOR = "editor"           # Add/edit content
    VIEWER = "viewer"           # Read-only access


# === Dataclasses ===

@dataclass
class Project:
    """
    A project workspace that groups related documents, entities, and analyses.

    Projects provide organizational structure and access control via member roles.
    All access is managed through ProjectMember records with VIEWER, EDITOR, or ADMIN roles.
    """
    id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE

    # Multi-tenancy
    tenant_id: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Settings and metadata
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Statistics
    member_count: int = 0
    document_count: int = 0


@dataclass
class ProjectMember:
    """
    A member of a project with a specific role.

    Members have role-based access to project resources.
    """
    id: str
    project_id: str
    user_id: str
    role: ProjectRole = ProjectRole.VIEWER

    # Audit trail
    added_at: datetime = field(default_factory=datetime.utcnow)
    added_by: str = "system"


@dataclass
class ProjectDocument:
    """
    Association between a project and a document.

    Tracks when and by whom documents were added to projects.
    """
    id: str
    project_id: str
    document_id: str

    # Audit trail
    added_at: datetime = field(default_factory=datetime.utcnow)
    added_by: str = "system"


@dataclass
class ProjectActivity:
    """
    Activity log entry for a project.

    Tracks all changes and actions within a project.
    """
    id: str
    project_id: str
    action: str                          # e.g., "created", "member_added"
    actor_id: str                        # User who performed the action

    # Target of the action
    target_type: str = "project"         # project, member, document, etc.
    target_id: str = ""

    # Timestamp and details
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectStatistics:
    """
    Statistics about projects in the system.
    """
    total_projects: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)

    total_members: int = 0
    total_documents: int = 0

    avg_members_per_project: float = 0.0
    avg_documents_per_project: float = 0.0

    projects_with_activity: int = 0
    recent_activity_count: int = 0


@dataclass
class ProjectFilter:
    """
    Filter criteria for project queries.
    """
    status: Optional[ProjectStatus] = None
    member_id: Optional[str] = None
    has_documents: Optional[bool] = None
    search_text: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
