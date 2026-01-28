"""
Projects Shard - FastAPI Routes

REST API endpoints for project workspace management.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .models import ProjectRole, ProjectStatus

logger = logging.getLogger(__name__)

try:
    from arkham_frame.auth import (
        current_optional_user,
        current_active_user,
        require_system_admin,
        require_project_member,
        require_project_admin,
    )
except ImportError:
    async def current_optional_user():
        return None
    async def current_active_user():
        return None
    async def require_system_admin():
        return None
    async def require_project_member():
        return None
    async def require_project_admin():
        return None

router = APIRouter(prefix="/api/projects", tags=["projects"])

# === Pydantic Request/Response Models ===


class ProjectCreate(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Project description")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = Field(
        default=None,
        description="Embedding model for this project (default: all-MiniLM-L6-v2)"
    )
    create_collections: bool = Field(
        default=True,
        description="Whether to create vector collections for this project"
    )


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


def _get_shard(request: Request):
    """Get the projects shard instance from app state."""
    shard = getattr(request.app.state, "projects_shard", None)
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
async def health_check(request: Request):
    """Health check endpoint."""
    shard = _get_shard(request)
    return HealthResponse(status="healthy", version=shard.version)


@router.get("/count", response_model=CountResponse)
async def get_projects_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get count of projects user is a member of (used for badge)."""
    from arkham_frame.auth.project_auth import get_user_projects
    from .models import ProjectFilter, ProjectStatus
    
    shard = _get_shard(request)
    
    if user:
        # Only count projects user is a member of
        user_project_ids = await get_user_projects(user, request)
        if status:
            # Filter by status too
            all_projects = await shard.list_projects(
                filter=ProjectFilter(status=ProjectStatus(status)),
                limit=10000,
                offset=0
            )
            filtered = [p for p in all_projects if p.id in user_project_ids]
            count = len(filtered)
        else:
            count = len(user_project_ids)
    else:
        count = await shard.get_count(status=status)
    
    return CountResponse(count=count)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    user: Optional[Any] = Depends(current_optional_user),
    status: Optional[ProjectStatus] = Query(None),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: Optional[int] = Query(None, ge=1, le=500),
    offset: Optional[int] = Query(None, ge=0),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=500),
):
    """List projects with optional filtering. When authenticated, filters by tenant and membership.
    Only returns projects the user is a member of.
    Accepts either limit/offset or page/page_size (page_size wins over limit when both sent).
    """
    from .models import ProjectFilter
    from arkham_frame.auth.project_auth import get_user_projects

    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)

    if page is not None and page_size is not None:
        limit = page_size
        offset = (page - 1) * page_size
    else:
        limit = limit if limit is not None else 50
        offset = offset if offset is not None else 0

    filter = ProjectFilter(
        status=status,
        search_text=search,
    )

    projects = await shard.list_projects(filter=filter, limit=limit, offset=offset)
    
    # Filter to only projects user is a member of
    if user:
        user_project_ids = await get_user_projects(user, request)
        projects = [p for p in projects if p.id in user_project_ids]
    
    # Recalculate total based on filtered projects
    total = len(projects) if user else await shard.get_count(status=status.value if status else None)

    return ProjectListResponse(
        projects=[_project_to_response(p) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


# === Embedding Model Endpoints (must be before /{project_id} routes) ===


class EmbeddingModelInfo(BaseModel):
    """Information about an embedding model."""
    name: str
    dimensions: int
    description: str


@router.get("/embedding-models", response_model=List[EmbeddingModelInfo])
def list_embedding_models():
    """List available embedding models."""
    from .shard import KNOWN_EMBEDDING_MODELS

    models = [
        EmbeddingModelInfo(
            name=name,
            dimensions=info["dimensions"],
            description=info["description"],
        )
        for name, info in KNOWN_EMBEDDING_MODELS.items()
    ]
    return models


# === Project CRUD Endpoints ===


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    req: Request,
    request: ProjectCreate,
    user: Optional[Any] = Depends(current_active_user),
):
    """Create a new project with optional embedding model and vector collections.

    Requires system admin role. Projects have no owner - all access is via member roles (VIEWER, EDITOR, ADMIN).
    When the request includes a valid JWT, the creating user is added as an ADMIN member,
    and all tenant admins are added as ADMIN members.
    
    Raises:
        400: If project would be created without any members
        403: If user is not a system admin
    """
    # Require system admin for project creation
    await require_system_admin(user)
    # Set request.state.user and tenant context so shard/context see the current user
    if user is not None:
        req.state.user = user
        try:
            from arkham_frame.middleware.tenant import set_current_tenant_id
            set_current_tenant_id(getattr(user, "tenant_id", None))
        except Exception:
            pass

    shard = _get_shard(req)

    # Resolve creator_id and tenant_id from authenticated user when available
    creator_id = None
    tenant_id = None
    if user is not None:
        creator_id = str(user.id)
        tenant_id = getattr(user, "tenant_id", None)

    try:
        project = await shard.create_project(
            name=request.name,
            description=request.description,
            creator_id=creator_id,
            status=request.status,
            settings=request.settings,
            metadata=request.metadata,
            embedding_model=request.embedding_model,
            create_collections=request.create_collections,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get a specific project by ID. Requires project membership."""
    if user:
        # Verify user is a member of the project
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)
    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    req: Request,
    project_id: str,
    request: ProjectUpdate,
    user: Optional[Any] = Depends(current_active_user),
):
    """Update a project. Requires system admin role."""
    await require_system_admin(user)
    
    shard = _get_shard(req)

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
async def delete_project(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Delete a project. Requires system admin role."""
    await require_system_admin(user)
    
    shard = _get_shard(request)

    success = await shard.delete_project(project_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Archive a project. Requires system admin role."""
    await require_system_admin(user)
    
    shard = _get_shard(request)

    project = await shard.update_project(
        project_id=project_id,
        status=ProjectStatus.ARCHIVED,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


@router.post("/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Restore an archived project. Requires system admin role."""
    await require_system_admin(user)
    
    shard = _get_shard(request)

    project = await shard.update_project(
        project_id=project_id,
        status=ProjectStatus.ACTIVE,
    )

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return _project_to_response(project)


# === Document Endpoints ===


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def get_project_documents(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get all documents in a project. Requires project membership."""
    if user:
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    logger.debug(f"GET documents for project {project_id}, tenant_hint={tenant_hint}, user={user is not None}")
    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        logger.warning(f"Project {project_id} not found (tenant_hint={tenant_hint})")
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    docs = await shard.list_documents(project_id)
    return [_document_to_response(d) for d in docs]


@router.post("/{project_id}/documents", response_model=DocumentResponse, status_code=201)
async def add_project_document(
    req: Request,
    project_id: str,
    request: DocumentAdd,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Add a document to a project."""
    _set_request_user_and_tenant(req, user)
    shard = _get_shard(req)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    doc = await shard.add_document(
        project_id=project_id,
        document_id=request.document_id,
        added_by=request.added_by,
    )

    return _document_to_response(doc)


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
async def remove_project_document(request: Request, project_id: str, document_id: str):
    """Remove a document from a project."""
    shard = _get_shard(request)

    success = await shard.remove_document(project_id, document_id)

    if not success:
        raise HTTPException(status_code=404, detail="Document association not found")


# === Member Endpoints ===


def _set_request_user_and_tenant(req: Request, user: Optional[Any]) -> None:
    """Set request.state.user and tenant context when user is present (so get_project finds by tenant)."""
    if user is not None:
        req.state.user = user
        try:
            from arkham_frame.middleware.tenant import set_current_tenant_id
            set_current_tenant_id(getattr(user, "tenant_id", None))
        except Exception:
            pass


def _tenant_id_from_user(user: Optional[Any]) -> Optional[Any]:
    """Return tenant_id from user for use in get_project(tenant_id_override)."""
    if user is None:
        return None
    return getattr(user, "tenant_id", None)


@router.get("/{project_id}/members", response_model=List[MemberResponse])
async def get_project_members(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get all members of a project. Requires project membership."""
    if user:
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    # Verify project exists (pass tenant so resolution works when context is set from this request)
    logger.debug(f"GET members for project {project_id}, tenant_hint={tenant_hint}, user={user is not None}")
    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        logger.warning(f"Project {project_id} not found (tenant_hint={tenant_hint})")
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    members = await shard.list_members(project_id)
    return [_member_to_response(m) for m in members]


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=201)
async def add_project_member(
    req: Request,
    project_id: str,
    request: MemberAdd,
    user: Optional[Any] = Depends(current_active_user),
):
    """Add a member to a project. Requires system admin or project admin role."""
    if user:
        # System admins can add members to any project
        # Project admins can add members to their projects
        try:
            from arkham_frame.auth.models import UserRole
            if user.role == UserRole.ADMIN:
                # System admin, allow
                pass
            else:
                # Check if user is project admin
                await require_project_admin(project_id, user, req)
        except HTTPException:
            # If not project admin, check if system admin
            await require_system_admin(user)
    
    _set_request_user_and_tenant(req, user)
    shard = _get_shard(req)
    tenant_hint = _tenant_id_from_user(user)

    # Verify project exists (explicit tenant_id_override so lookup sees same tenant as this request)
    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    member = await shard.add_member(
        project_id=project_id,
        user_id=request.user_id,
        role=request.role,
    )

    return _member_to_response(member)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    request: Request,
    project_id: str,
    user_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Remove a member from a project. Requires system admin or project admin role. Cannot remove last member."""
    if user:
        # System admins can remove members from any project
        # Project admins can remove members from their projects
        try:
            from arkham_frame.auth.models import UserRole
            if user.role == UserRole.ADMIN:
                # System admin, allow
                pass
            else:
                # Check if user is project admin
                await require_project_admin(project_id, user, request)
        except HTTPException:
            # If not project admin, check if system admin
            await require_system_admin(user)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    # Verify project exists for tenant
    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    members = await shard.list_members(project_id)
    if len(members) <= 1 and any(m.user_id == user_id for m in members):
        raise HTTPException(
            status_code=400,
            detail="Project must have at least one member. Add another member before removing this one.",
        )

    success = await shard.remove_member(project_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Member not found")


# === Activity Endpoint ===


@router.get("/{project_id}/activity", response_model=List[ActivityResponse])
async def get_project_activity(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get activity log for a project. Requires project membership."""
    if user:
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    activities = await shard.get_activity(project_id, limit=limit, offset=offset)
    return [_activity_to_response(a) for a in activities]


# === Embedding Model Request/Response Models ===


class EmbeddingModelUpdate(BaseModel):
    """Request to update embedding model."""
    model: str
    wipe_collections: bool = Field(
        default=False,
        description="If True and dimensions differ, wipe and recreate collections"
    )


class EmbeddingModelResponse(BaseModel):
    """Response for embedding model operations."""
    success: bool
    message: str = ""
    current_model: Optional[str] = None
    current_dimensions: Optional[int] = None
    requires_wipe: bool = False
    previous_model: Optional[str] = None
    new_model: Optional[str] = None
    wiped: bool = False


class CollectionStatsResponse(BaseModel):
    """Response for collection statistics."""
    available: bool
    collections: Dict[str, Any]


@router.get("/{project_id}/embedding-model")
async def get_project_embedding_model(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get the embedding model configuration for a project. Requires project membership."""
    if user:
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    from .shard import KNOWN_EMBEDDING_MODELS, DEFAULT_EMBEDDING_MODEL

    model = project.settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
    dimensions = project.settings.get(
        "embedding_dimensions",
        KNOWN_EMBEDDING_MODELS.get(model, {}).get("dimensions", 384)
    )

    return {
        "project_id": project_id,
        "embedding_model": model,
        "embedding_dimensions": dimensions,
        "description": KNOWN_EMBEDDING_MODELS.get(model, {}).get("description", ""),
    }


@router.put("/{project_id}/embedding-model", response_model=EmbeddingModelResponse)
async def update_project_embedding_model(
    req: Request,
    project_id: str,
    request: EmbeddingModelUpdate,
    user: Optional[Any] = Depends(current_active_user),
):
    """
    Update the embedding model for a project. Requires system admin or project admin role.

    If the new model has different dimensions, you must set wipe_collections=True
    to confirm deletion of existing vectors.
    """
    if user:
        # System admins or project admins can update embedding model
        try:
            from arkham_frame.auth.models import UserRole
            if user.role == UserRole.ADMIN:
                # System admin, allow
                pass
            else:
                await require_project_admin(project_id, user, req)
        except HTTPException:
            await require_system_admin(user)
    
    _set_request_user_and_tenant(req, user)
    shard = _get_shard(req)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    result = await shard.update_project_embedding_model(
        project_id=project_id,
        new_model=request.model,
        wipe_collections=request.wipe_collections,
    )

    if not result.get("success") and result.get("requires_wipe"):
        return EmbeddingModelResponse(
            success=False,
            message=result.get("message", "Model change requires wiping collections"),
            current_model=result.get("current_model"),
            current_dimensions=result.get("current_dimensions"),
            requires_wipe=True,
        )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to update embedding model")
        )

    return EmbeddingModelResponse(
        success=True,
        message="Embedding model updated successfully",
        previous_model=result.get("previous_model"),
        new_model=result.get("new_model"),
        wiped=result.get("wiped", False),
    )


# === Collection Endpoints ===


@router.get("/{project_id}/collections", response_model=CollectionStatsResponse)
async def get_project_collections(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_optional_user),
):
    """Get vector collection statistics for a project. Requires project membership."""
    if user:
        await require_project_member(project_id, user, request)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    stats = await shard.get_project_collection_stats(project_id)

    return CollectionStatsResponse(
        available=stats.get("available", False),
        collections=stats.get("collections", {}),
    )


@router.post("/{project_id}/collections/create")
async def create_project_collections(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Create vector collections for a project (if not already created). Requires system admin or project admin role."""
    if user:
        try:
            from arkham_frame.auth.models import UserRole
            if user.role == UserRole.ADMIN:
                # System admin, allow
                pass
            else:
                await require_project_admin(project_id, user, request)
        except HTTPException:
            await require_system_admin(user)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    from .shard import DEFAULT_EMBEDDING_MODEL
    model = project.settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)

    results = await shard.create_project_collections(project_id, model)

    return {
        "project_id": project_id,
        "created": results,
        "embedding_model": model,
    }


@router.delete("/{project_id}/collections")
async def delete_project_collections(
    request: Request,
    project_id: str,
    user: Optional[Any] = Depends(current_active_user),
):
    """Delete all vector collections for a project. Requires system admin or project admin role."""
    if user:
        try:
            from arkham_frame.auth.models import UserRole
            if user.role == UserRole.ADMIN:
                # System admin, allow
                pass
            else:
                await require_project_admin(project_id, user, request)
        except HTTPException:
            await require_system_admin(user)
    
    _set_request_user_and_tenant(request, user)
    shard = _get_shard(request)
    tenant_hint = _tenant_id_from_user(user)

    project = await shard.get_project(project_id, tenant_id_override=tenant_hint)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    results = await shard.delete_project_collections(project_id)

    return {
        "project_id": project_id,
        "deleted": results,
    }
