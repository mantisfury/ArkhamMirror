"""
Project API endpoints.
"""

from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter()


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _project_to_dict(project) -> Dict[str, Any]:
    """Convert a Project dataclass to a dictionary with all expected fields."""
    result = asdict(project)
    # Convert datetime objects to ISO strings
    if "created_at" in result and result["created_at"]:
        result["created_at"] = result["created_at"].isoformat()
    if "updated_at" in result and result["updated_at"]:
        result["updated_at"] = result["updated_at"].isoformat()
    # Get status from settings if available
    settings = result.get('settings') or {}
    result['status'] = settings.get('status', 'active')
    result['owner_id'] = settings.get('owner_id', 'system')
    # Add fields expected by UI (with defaults if missing)
    result.setdefault('member_count', 0)
    result.setdefault('document_count', 0)
    return result


class SetActiveProjectRequest(BaseModel):
    """Request body for setting active project."""
    project_id: Optional[str] = None


class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""
    name: str
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    create_collections: bool = True


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("/")
@router.get("/list")
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    # Also accept limit/offset for backwards compatibility
    limit: Optional[int] = Query(default=None, le=200),
    offset: Optional[int] = Query(default=None, ge=0),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List all projects with pagination."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    # Use page/page_size if limit/offset not provided
    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size

    projects, total = await frame.projects.list_projects(
        limit=effective_limit,
        offset=effective_offset,
    )

    # Convert to dict (fields are added by _project_to_dict)
    project_dicts = [_project_to_dict(p) for p in projects]

    return {
        "items": project_dicts,
        "total": total,
        "page": page,
        "page_size": page_size,
        # Also include for backwards compat
        "projects": project_dicts,
        "limit": effective_limit,
        "offset": effective_offset,
    }


# === Active Project Endpoints (must be before /{project_id} routes) ===


@router.get("/active")
async def get_active_project() -> Dict[str, Any]:
    """Get the currently active project."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.active_project_id:
        return {
            "active": False,
            "project_id": None,
            "project": None,
            "collections": frame.get_project_collections(),
        }

    # Get project details
    project = None
    if frame.projects:
        try:
            proj = await frame.projects.get_project(frame.active_project_id)
            project = _project_to_dict(proj)
        except Exception:
            pass

    return {
        "active": True,
        "project_id": frame.active_project_id,
        "project": project,
        "collections": frame.get_project_collections(),
    }


@router.put("/active")
async def set_active_project(request: SetActiveProjectRequest) -> Dict[str, Any]:
    """Set the active project for routing operations."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if request.project_id is None:
        # Clear active project
        await frame.set_active_project(None)
        return {
            "success": True,
            "active": False,
            "project_id": None,
            "project": None,
            "collections": frame.get_project_collections(),
            "message": "Active project cleared - using global collections",
        }

    # Verify project exists
    if frame.projects:
        try:
            await frame.projects.get_project(request.project_id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Project {request.project_id} not found"
            )

    # Set active project
    success = await frame.set_active_project(request.project_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to set active project {request.project_id}"
        )

    # Get project details
    project = None
    if frame.projects:
        try:
            proj = await frame.projects.get_project(request.project_id)
            project = _project_to_dict(proj)
        except Exception:
            pass

    return {
        "success": True,
        "active": True,
        "project_id": request.project_id,
        "project": project,
        "collections": frame.get_project_collections(),
        "message": f"Active project set to {project['name'] if project else request.project_id}",
    }


@router.post("/")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """Create a new project with optional embedding model and vector collections."""
    from ..main import get_frame
    from ..services import ProjectExistsError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    # Determine embedding model and dimensions
    embedding_model = request.embedding_model or DEFAULT_EMBEDDING_MODEL
    model_info = KNOWN_EMBEDDING_MODELS.get(embedding_model, KNOWN_EMBEDDING_MODELS[DEFAULT_EMBEDDING_MODEL])
    embedding_dimensions = model_info["dimensions"]

    # Build settings with embedding config
    settings = {
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
    }

    try:
        project = await frame.projects.create_project(
            name=request.name,
            description=request.description or "",
            settings=settings,
        )

        # Create project-scoped vector collections if requested
        if request.create_collections and hasattr(frame, "vectors") and frame.vectors:
            collection_prefix = f"project_{project.id}"
            collection_types = ["documents", "chunks", "entities"]

            for coll_type in collection_types:
                collection_name = f"{collection_prefix}_{coll_type}"
                try:
                    await frame.vectors.create_collection(
                        name=collection_name,
                        vector_size=embedding_dimensions,
                    )
                except Exception as e:
                    # Log but don't fail project creation
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Failed to create collection {collection_name}: {e}"
                    )

        return _project_to_dict(project)
    except ProjectExistsError:
        raise HTTPException(status_code=409, detail=f"Project '{request.name}' already exists")


# === Embedding Models (must be before /{project_id} routes) ===


class EmbeddingModelInfo(BaseModel):
    """Information about an embedding model."""
    name: str
    dimensions: int
    description: str


# Known embedding models with their dimensions
KNOWN_EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": {"dimensions": 384, "description": "Fast, lightweight (384D)"},
    "BAAI/bge-m3": {"dimensions": 1024, "description": "High quality, multilingual (1024D)"},
    "all-mpnet-base-v2": {"dimensions": 768, "description": "Balanced quality (768D)"},
    "paraphrase-MiniLM-L6-v2": {"dimensions": 384, "description": "Paraphrase optimized (384D)"},
}


@router.get("/embedding-models", response_model=List[EmbeddingModelInfo])
def list_embedding_models():
    """List available embedding models."""
    return [
        EmbeddingModelInfo(
            name=name,
            dimensions=info["dimensions"],
            description=info["description"],
        )
        for name, info in KNOWN_EMBEDDING_MODELS.items()
    ]


@router.get("/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """Get a project by ID."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        project = await frame.projects.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        return _project_to_dict(project)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


async def _do_update_project(project_id: str, request: UpdateProjectRequest) -> Dict[str, Any]:
    """Internal update implementation."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        project = await frame.projects.update_project(
            project_id=project_id,
            name=request.name,
            description=request.description,
        )
        return _project_to_dict(project)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.patch("/{project_id}")
async def update_project_patch(project_id: str, request: UpdateProjectRequest) -> Dict[str, Any]:
    """Update a project (PATCH)."""
    return await _do_update_project(project_id, request)


@router.put("/{project_id}")
async def update_project_put(project_id: str, request: UpdateProjectRequest) -> Dict[str, Any]:
    """Update a project (PUT)."""
    return await _do_update_project(project_id, request)


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> Dict[str, str]:
    """Delete a project and its vector collections."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    # Delete vector collections first
    if hasattr(frame, "vectors") and frame.vectors:
        collection_prefix = f"project_{project_id}"
        collection_types = ["documents", "chunks", "entities"]

        for coll_type in collection_types:
            collection_name = f"{collection_prefix}_{coll_type}"
            try:
                await frame.vectors.delete_collection(collection_name)
            except Exception:
                pass  # Collection may not exist

    try:
        await frame.projects.delete_project(project_id)
        return {"status": "deleted", "project_id": project_id}
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.post("/{project_id}/archive")
async def archive_project(project_id: str) -> Dict[str, Any]:
    """Archive a project (sets status to archived)."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        # Update project settings with archived status
        project = await frame.projects.get_project(project_id)
        settings = project.settings or {}
        settings['status'] = 'archived'
        await frame.projects.update_project(project_id=project_id, settings=settings)
        project = await frame.projects.get_project(project_id)
        return _project_to_dict(project)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.post("/{project_id}/restore")
async def restore_project(project_id: str) -> Dict[str, Any]:
    """Restore an archived project (sets status to active)."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        # Update project settings with active status
        project = await frame.projects.get_project(project_id)
        settings = project.settings or {}
        settings['status'] = 'active'
        await frame.projects.update_project(project_id=project_id, settings=settings)
        project = await frame.projects.get_project(project_id)
        return _project_to_dict(project)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/{project_id}/stats")
async def get_project_stats(project_id: str) -> Dict[str, Any]:
    """Get statistics for a project."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        stats = await frame.projects.get_project_stats(project_id)
        return stats
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/{project_id}/embedding-model")
async def get_project_embedding_model(project_id: str) -> Dict[str, Any]:
    """Get the embedding model configuration for a project."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        project = await frame.projects.get_project(project_id)
        settings = project.settings or {}
        model = settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        dimensions = settings.get(
            "embedding_dimensions",
            KNOWN_EMBEDDING_MODELS.get(model, {}).get("dimensions", 384)
        )

        return {
            "project_id": project_id,
            "embedding_model": model,
            "embedding_dimensions": dimensions,
            "description": KNOWN_EMBEDDING_MODELS.get(model, {}).get("description", ""),
        }
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


class EmbeddingModelUpdate(BaseModel):
    """Request to update embedding model."""
    model: str
    wipe_collections: bool = False


@router.put("/{project_id}/embedding-model")
async def update_project_embedding_model(
    project_id: str,
    request: EmbeddingModelUpdate,
) -> Dict[str, Any]:
    """Update the embedding model for a project."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    if request.model not in KNOWN_EMBEDDING_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown embedding model: {request.model}")

    try:
        project = await frame.projects.get_project(project_id)
        settings = project.settings or {}
        current_model = settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        current_dims = KNOWN_EMBEDDING_MODELS.get(current_model, {}).get("dimensions", 384)
        new_dims = KNOWN_EMBEDDING_MODELS.get(request.model, {}).get("dimensions", 384)

        # Check if dimensions differ
        if current_dims != new_dims and not request.wipe_collections:
            return {
                "success": False,
                "message": "Model change requires wiping collections (dimensions differ)",
                "current_model": current_model,
                "current_dimensions": current_dims,
                "new_dimensions": new_dims,
                "requires_wipe": True,
            }

        # Wipe collections if requested
        if request.wipe_collections and hasattr(frame, "vectors") and frame.vectors:
            collection_prefix = f"project_{project_id}"
            for coll_type in ["documents", "chunks", "entities"]:
                collection_name = f"{collection_prefix}_{coll_type}"
                try:
                    await frame.vectors.delete_collection(collection_name)
                    await frame.vectors.create_collection(
                        name=collection_name,
                        vector_size=new_dims,
                    )
                except Exception:
                    pass

        # Update project settings
        settings["embedding_model"] = request.model
        settings["embedding_dimensions"] = new_dims

        await frame.projects.update_project(
            project_id=project_id,
            settings=settings,
        )

        return {
            "success": True,
            "message": "Embedding model updated successfully",
            "previous_model": current_model,
            "new_model": request.model,
            "wiped": request.wipe_collections,
        }
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/{project_id}/collections")
async def get_project_collections(project_id: str) -> Dict[str, Any]:
    """Get vector collection statistics for a project."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        # Verify project exists
        await frame.projects.get_project(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if not hasattr(frame, "vectors") or not frame.vectors:
        return {"available": False, "collections": {}}

    collection_prefix = f"project_{project_id}"
    collection_types = ["documents", "chunks", "entities"]
    collections = {}

    for coll_type in collection_types:
        collection_name = f"{collection_prefix}_{coll_type}"
        try:
            info = await frame.vectors.get_collection(collection_name)
            if info:
                collections[coll_type] = {
                    "name": collection_name,
                    "vector_count": info.points_count,
                    "dimensions": info.vector_size,
                    "exists": True,
                }
            else:
                collections[coll_type] = {
                    "name": collection_name,
                    "exists": False,
                }
        except Exception as e:
            # Collection doesn't exist or other error
            collections[coll_type] = {
                "name": collection_name,
                "exists": False,
            }

    return {"available": True, "collections": collections}
