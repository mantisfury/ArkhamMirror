"""
Project API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter()


class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""
    name: str
    description: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("/")
async def list_projects(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List all projects."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    projects = await frame.projects.list_projects(limit=limit, offset=offset)

    return {
        "projects": projects,
        "limit": limit,
        "offset": offset,
    }


@router.post("/")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """Create a new project."""
    from ..main import get_frame
    from ..services import ProjectExistsError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        project = await frame.projects.create_project(
            name=request.name,
            description=request.description,
        )
        return project
    except ProjectExistsError:
        raise HTTPException(status_code=409, detail=f"Project '{request.name}' already exists")


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
        return project
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.patch("/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest) -> Dict[str, Any]:
    """Update a project."""
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
        return project
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> Dict[str, str]:
    """Delete a project."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    frame = get_frame()

    if not frame.projects:
        raise HTTPException(status_code=503, detail="Project service unavailable")

    try:
        await frame.projects.delete_project(project_id)
        return {"status": "deleted", "project_id": project_id}
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
