"""
Frame-level API endpoints.

Provides Shell integration endpoints:
- /api/frame/badges - Aggregated badge counts from all shards
- /api/frame/health - Frame health status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

try:
    from arkham_frame.auth import current_optional_user
except ImportError:
    async def current_optional_user():
        return None

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/badges")
async def get_all_badges(
    user = Depends(current_optional_user)
) -> Dict[str, Any]:
    """
    Aggregate badge counts from all loaded shards, filtered by user's project memberships.

    Returns a dictionary mapping badge keys to badge info:
    - Main nav badges: "{shardName}" -> {count, type}
    - Sub-route badges: "{shardName}:{subRouteId}" -> {count, type}

    Shards must implement get_badge_count() and/or get_subroute_badge_count(sub_id).
    """
    from ..main import get_frame
    from ..auth.project_auth import get_user_projects

    frame = get_frame()
    badges: Dict[str, Any] = {}
    
    # Get user's projects for filtering
    user_project_ids = None
    if user:
        user_project_ids = await get_user_projects(user, None)

    for name, shard in frame.shards.items():
        manifest = getattr(shard, "manifest", None)
        if not manifest:
            continue

        # Get navigation config
        nav = None
        if hasattr(manifest, "navigation") and manifest.navigation:
            nav = manifest.navigation
        elif isinstance(manifest, dict) and "navigation" in manifest:
            nav = manifest["navigation"]

        if not nav:
            continue

        # Main nav badge
        badge_endpoint = getattr(nav, "badge_endpoint", None) if hasattr(nav, "badge_endpoint") else nav.get("badge_endpoint")
        badge_type = getattr(nav, "badge_type", "count") if hasattr(nav, "badge_type") else nav.get("badge_type", "count")

        if badge_endpoint:
            try:
                # Check if shard has get_badge_count method
                if hasattr(shard, "get_badge_count"):
                    count = await shard.get_badge_count()
                    badges[name] = {
                        "count": count,
                        "type": badge_type or "count"
                    }
            except Exception as e:
                logger.warning(f"Failed to get badge for {name}: {e}")

        # Sub-route badges
        sub_routes = getattr(nav, "sub_routes", []) if hasattr(nav, "sub_routes") else nav.get("sub_routes", [])

        for sub in sub_routes:
            sub_badge_endpoint = sub.badge_endpoint if hasattr(sub, "badge_endpoint") else sub.get("badge_endpoint")
            sub_badge_type = sub.badge_type if hasattr(sub, "badge_type") else sub.get("badge_type", "count")
            sub_id = sub.id if hasattr(sub, "id") else sub.get("id")

            if sub_badge_endpoint and sub_id:
                try:
                    if hasattr(shard, "get_subroute_badge_count"):
                        count = await shard.get_subroute_badge_count(sub_id)
                        badges[f"{name}:{sub_id}"] = {
                            "count": count,
                            "type": sub_badge_type or "count"
                        }
                except Exception as e:
                    logger.warning(f"Failed to get badge for {name}:{sub_id}: {e}")

    return badges


@router.get("/health")
async def get_frame_health() -> Dict[str, Any]:
    """Get Frame health status for connection monitoring."""
    from ..main import get_frame

    try:
        frame = get_frame()
        return {
            "status": "healthy",
            "version": "0.1.0",
            "services": {
                "config": frame.config is not None,
                "database": frame.db is not None,
                "vectors": frame.vectors is not None,
                "llm": frame.llm is not None,
                "events": frame.events is not None,
            },
            "shards": list(frame.shards.keys()),
            "shard_count": len(frame.shards),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.get("/state")
async def get_frame_state() -> Dict[str, Any]:
    """Get detailed Frame state."""
    from ..main import get_frame

    frame = get_frame()
    return frame.get_state()


# === Active Project Management ===
# Moved from /api/projects/active to /api/frame/active-project
# This is frame-specific state management, not project CRUD


class SetActiveProjectRequest(BaseModel):
    """Request body for setting active project."""
    project_id: Optional[str] = None


def _project_to_dict(project) -> Dict[str, Any]:
    """Convert a Project dataclass to a dictionary with all expected fields."""
    from dataclasses import asdict
    result = asdict(project)
    # Convert datetime objects to ISO strings
    if "created_at" in result and result["created_at"]:
        result["created_at"] = result["created_at"].isoformat()
    if "updated_at" in result and result["updated_at"]:
        result["updated_at"] = result["updated_at"].isoformat()
    # Get status from settings if available
    settings = result.get('settings') or {}
    result['status'] = settings.get('status', 'active')
    # Add fields expected by UI (with defaults if missing)
    result.setdefault('member_count', 0)
    result.setdefault('document_count', 0)
    return result


@router.get("/active-project")
async def get_active_project(
    user = Depends(current_optional_user)
) -> Dict[str, Any]:
    """Get the currently active project for the authenticated user."""
    from ..main import get_frame

    frame = get_frame()
    # Normalize UUID to lowercase string for consistent lookup
    user_id = str(user.id).lower().strip() if user else None

    if not user_id:
        return {
            "active": False,
            "project_id": None,
            "project": None,
            "collections": await frame.get_project_collections(),
        }

    active_project_id = await frame.get_active_project_id(user_id)
    if not active_project_id:
        return {
            "active": False,
            "project_id": None,
            "project": None,
            "collections": await frame.get_project_collections(user_id=user_id),
        }

    # Get project details - try projects shard first, then fall back to ProjectService
    project = None
    projects_shard = frame.shards.get("projects")
    
    if projects_shard:
        try:
            proj = await projects_shard.get_project(active_project_id)
            if proj:
                # Convert Project dataclass to dict
                project = {
                    "id": proj.id,
                    "name": proj.name,
                    "description": proj.description,
                    "status": proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
                    "created_at": proj.created_at.isoformat() if hasattr(proj.created_at, 'isoformat') else str(proj.created_at),
                    "updated_at": proj.updated_at.isoformat() if hasattr(proj.updated_at, 'isoformat') else str(proj.updated_at),
                    "settings": proj.settings,
                    "metadata": proj.metadata,
                    "member_count": proj.member_count,
                    "document_count": proj.document_count,
                }
        except Exception:
            pass
    
    if not project and frame.projects:
        try:
            proj = await frame.projects.get_project(active_project_id)
            project = _project_to_dict(proj)
        except Exception:
            pass

    return {
        "active": True,
        "project_id": active_project_id,
        "project": project,
        "collections": await frame.get_project_collections(project_id=active_project_id),
    }


@router.put("/active-project")
async def set_active_project(
    request: SetActiveProjectRequest,
    user = Depends(current_optional_user)
) -> Dict[str, Any]:
    """Set the active project for the authenticated user."""
    from ..main import get_frame
    from ..services import ProjectNotFoundError

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to set active project"
        )

    frame = get_frame()
    # Normalize UUID to lowercase string for consistent storage
    user_id = str(user.id).lower().strip()

    if request.project_id is None:
        # Clear active project
        await frame.set_active_project(user_id, None)
        return {
            "success": True,
            "active": False,
            "project_id": None,
            "project": None,
            "collections": await frame.get_project_collections(user_id=user_id),
            "message": "Active project cleared - using global collections",
        }

    # Verify project exists and user is a member - try projects shard first
    projects_shard = frame.shards.get("projects")
    project = None
    
    if projects_shard:
        try:
            proj = await projects_shard.get_project(request.project_id)
            if proj:
                # Verify user is a member of the project
                members = await projects_shard.list_members(request.project_id)
                user_ids = [m.user_id for m in members]
                if str(user_id) not in user_ids:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access denied: You are not a member of project {request.project_id}"
                    )
                
                project = {
                    "id": proj.id,
                    "name": proj.name,
                    "description": proj.description,
                    "status": proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
                    "created_at": proj.created_at.isoformat() if hasattr(proj.created_at, 'isoformat') else str(proj.created_at),
                    "updated_at": proj.updated_at.isoformat() if hasattr(proj.updated_at, 'isoformat') else str(proj.updated_at),
                    "settings": proj.settings,
                    "metadata": proj.metadata,
                    "member_count": proj.member_count,
                    "document_count": proj.document_count,
                }
        except HTTPException:
            raise
        except Exception:
            pass
    
    if not project and frame.projects:
        try:
            await frame.projects.get_project(request.project_id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Project {request.project_id} not found"
            )

    # Set active project
    success = await frame.set_active_project(user_id, request.project_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to set active project {request.project_id}"
        )

    # Get project details for response
    if not project:
        if projects_shard:
            try:
                proj = await projects_shard.get_project(request.project_id)
                if proj:
                    project = {
                        "id": proj.id,
                        "name": proj.name,
                        "description": proj.description,
                        "status": proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
                        "created_at": proj.created_at.isoformat() if hasattr(proj.created_at, 'isoformat') else str(proj.created_at),
                        "updated_at": proj.updated_at.isoformat() if hasattr(proj.updated_at, 'isoformat') else str(proj.updated_at),
                        "settings": proj.settings,
                        "metadata": proj.metadata,
                        "member_count": proj.member_count,
                        "document_count": proj.document_count,
                    }
            except Exception:
                pass
        
        if not project and frame.projects:
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
        "collections": await frame.get_project_collections(project_id=request.project_id),
        "message": f"Active project set to {project['name'] if project else request.project_id}",
    }
