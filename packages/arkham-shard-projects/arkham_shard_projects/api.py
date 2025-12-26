"""
Projects Shard - FastAPI Routes

REST API endpoints for project workspace management.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .models import ProjectRole, ProjectStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])

# === Pydantic Request/Response Models ===


class ProjectCreate(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Project description")
    owner_id: str = Field(default="system", description="Project owner")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    """Request model for updating a project."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Response model for a project."""
    id: str
    name: str
    description: str
    status: str
    owner_id: str
    created_at: str
    updated_at: str
    settings: Dict[str, Any]
    metadata: Dict[str, Any]
    member_count: int
    document_count: int


class ProjectListResponse(BaseModel):
    """Response model for listing projects."""
    projects: List[ProjectResponse]
    total: int
    limit: int
    offset: int


class MemberAdd(BaseModel):
    """Request model for adding a member."""
    user_id: str
    role: ProjectRole = ProjectRole.VIEWER


class MemberResponse(BaseModel):
    """Response model for a project member."""
    id: str
    project_id: str
    user_id: str
    role: str
    added_at: str
    added_by: str


class DocumentAdd(BaseModel):
    """Request model for adding a document."""
    document_id: str
    added_by: str = "system"


class DocumentResponse(BaseModel):
    """Response model for a project document."""
    id: str
    project_id: str
    document_id: str
    added_at: str
    added_by: str


class ActivityResponse(BaseModel):
    """Response model for project activity."""
    id: str
    project_id: str
    action: str
    actor_id: str
    target_type: str
    target_id: str
    timestamp: str
    details: Dict[str, Any]


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str


# === Helper Functions ===


def _get_shard():
    """Get the projects shard instance from the frame."""
    from arkham_frame import get_frame
    frame = get_frame()
    shard = frame.get_shard("projects")
    if not shard:
        raise HTTPException(status_code=503, detail="Projects shard not available")
    return shard


def _project_to_response(project) -> ProjectResponse:
    """Convert Project object to response model."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        settings=project.settings,
        metadata=project.metadata,
        member_count=project.member_count,
        document_count=project.document_count,
    )


def _member_to_response(member) -> MemberResponse:
    """Convert ProjectMember object to response model."""
    return MemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role.value,
        added_at=member.added_at.isoformat(),
        added_by=member.added_by,
    )


def _document_to_response(doc) -> DocumentResponse:
    """Convert ProjectDocument object to response model."""
    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        document_id=doc.document_id,
        added_at=doc.added_at.isoformat(),
        added_by=doc.added_by,
    )


def _activity_to_response(activity) -> ActivityResponse:
    """Convert ProjectActivity object to response model."""
    return ActivityResponse(
        id=activity.id,
        project_id=activity.project_id,
        action=activity.action,
        actor_id=activity.actor_id,
        target_type=activity.target_type,
        target_id=activity.target_id,
        timestamp=activity.timestamp.isoformat(),
        details=activity.details,
    )


# === Endpoints ===


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    shard = _get_shard()
    return HealthResponse(status="healthy", version=shard.version)


@router.get("/count", response_model=CountResponse)
async def get_projects_count(
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of projects (used for badge)."""
    shard = _get_shard()
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    status: Optional[ProjectStatus] = Query(None),
    owner_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List projects with optional filtering."""
    from .models import ProjectFilter

    shard = _get_shard()

    filter = ProjectFilter(
        status=status,
        owner_id=owner_id,
        search_text=search,
    )

    projects = await shard.list_projects(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status=status.value if status else None)

    return ProjectListResponse(
        projects=[_project_to_response(p) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(request: ProjectCreate):
    """Create a new project."""
    shard = _get_shard()

    project = await shard.create_project(
        name=request.name,
        description=request.description,
        owner_id=request.owner_id,
        status=request.status,
        settings=request.settings,
        metadata=request.metadata,
    )

    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a specific project by ID."""
    shard = _get_shard()
    project = await shard.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, request: ProjectUpdate):
    """Update a project."""
    shard = _get_shard()

    project = await shard.update_project(
        project_id=project_id,
        name=request.name,
        description=request.description,
        status=request.status,
        settings=request.settings,
        metadata=request.metadata,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str):
    """Delete a project."""
    shard = _get_shard()

    success = await shard.delete_project(project_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(project_id: str):
    """Archive a project."""
    shard = _get_shard()

    project = await shard.update_project(
        project_id=project_id,
        status=ProjectStatus.ARCHIVED,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


@router.post("/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(project_id: str):
    """Restore an archived project."""
    shard = _get_shard()

    project = await shard.update_project(
        project_id=project_id,
        status=ProjectStatus.ACTIVE,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


# === Document Endpoints ===


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def get_project_documents(project_id: str):
    """Get all documents in a project."""
    shard = _get_shard()

    # Verify project exists
    project = await shard.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Stub: return empty list
    return []


@router.post("/{project_id}/documents", response_model=DocumentResponse, status_code=201)
async def add_project_document(project_id: str, request: DocumentAdd):
    """Add a document to a project."""
    shard = _get_shard()

    # Verify project exists
    project = await shard.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    doc = await shard.add_document(
        project_id=project_id,
        document_id=request.document_id,
        added_by=request.added_by,
    )

    return _document_to_response(doc)


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
async def remove_project_document(project_id: str, document_id: str):
    """Remove a document from a project."""
    shard = _get_shard()

    success = await shard.remove_document(project_id, document_id)

    if not success:
        raise HTTPException(status_code=404, detail="Document association not found")


# === Member Endpoints ===


@router.get("/{project_id}/members", response_model=List[MemberResponse])
async def get_project_members(project_id: str):
    """Get all members of a project."""
    shard = _get_shard()

    # Verify project exists
    project = await shard.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Stub: return empty list
    return []


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=201)
async def add_project_member(project_id: str, request: MemberAdd):
    """Add a member to a project."""
    shard = _get_shard()

    # Verify project exists
    project = await shard.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    member = await shard.add_member(
        project_id=project_id,
        user_id=request.user_id,
        role=request.role,
    )

    return _member_to_response(member)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(project_id: str, user_id: str):
    """Remove a member from a project."""
    shard = _get_shard()

    success = await shard.remove_member(project_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Member not found")


# === Activity Endpoint ===


@router.get("/{project_id}/activity", response_model=List[ActivityResponse])
async def get_project_activity(
    project_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get activity log for a project."""
    shard = _get_shard()

    # Verify project exists
    project = await shard.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    activities = await shard.get_activity(project_id, limit=limit, offset=offset)
    return [_activity_to_response(a) for a in activities]
