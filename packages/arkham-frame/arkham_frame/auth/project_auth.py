"""
Project Authorization Helpers

Provides dependency functions for verifying project membership and admin roles.
"""

import logging
from typing import List, Optional
from fastapi import HTTPException, status

try:
    from arkham_frame.auth.models import User
except ImportError:
    User = None

logger = logging.getLogger(__name__)


async def require_project_member(project_id: str, user: User, request=None) -> None:
    """
    Verify that the user is a member of the specified project.
    
    Raises:
        HTTPException: 403 if user is not a member, 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for project access"
        )
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project ID is required"
        )
    
    # Get projects shard from request or frame
    projects_shard = None
    if request:
        projects_shard = getattr(request.app.state, 'projects_shard', None)
    
    if not projects_shard:
        # Try to get from frame
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
        except Exception:
            pass
    
    if not projects_shard:
        # No projects shard available - allow access (fallback for deployments without projects)
        logger.warning("Projects shard not available, skipping membership check")
        return
    
    try:
        members = await projects_shard.list_members(project_id)
        user_ids = [m.user_id for m in members]
        
        if str(user.id) not in user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not a member of project {project_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to verify project membership: {e}")
        # If project doesn't exist or other error, raise 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )


async def require_project_admin(project_id: str, user: User, request=None) -> None:
    """
    Verify that the user is an ADMIN member of the specified project.
    
    Raises:
        HTTPException: 403 if user is not an admin member, 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project ID is required"
        )
    
    # First check if user is a member
    await require_project_member(project_id, user, request)
    
    # Get projects shard
    projects_shard = None
    if request:
        projects_shard = getattr(request.app.state, 'projects_shard', None)
    
    if not projects_shard:
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
        except Exception:
            pass
    
    if not projects_shard:
        logger.warning("Projects shard not available, skipping admin check")
        return
    
    try:
        members = await projects_shard.list_members(project_id)
        user_member = next((m for m in members if m.user_id == str(user.id)), None)
        
        if not user_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not a member of project {project_id}"
            )
        
        # Check if role is ADMIN (compare string value)
        if user_member.role.value != "admin" if hasattr(user_member.role, 'value') else user_member.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Admin role required for project {project_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to verify project admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify project admin role"
        )


async def require_system_admin(user: User) -> None:
    """
    Verify that the user has system-level admin role.
    
    Raises:
        HTTPException: 403 if user is not a system admin, 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        from arkham_frame.auth.models import UserRole
        
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System admin role required"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to verify system admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify admin role"
        )


async def get_user_projects(user: User, request=None) -> List[str]:
    """
    Get list of project IDs that the user is a member of.
    
    Args:
        user: User object
        request: FastAPI Request object (optional)
        
    Returns:
        List of project IDs
    """
    if not user:
        return []
    
    # Get projects shard
    projects_shard = None
    if request:
        projects_shard = getattr(request.app.state, 'projects_shard', None)
    
    if not projects_shard:
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
        except Exception:
            pass
    
    if not projects_shard:
        return []
    
    try:
        # Get all projects user is a member of
        # Query project_members table for user_id
        db = getattr(projects_shard, '_db', None)
        if not db:
            return []
        
        rows = await db.fetch_all(
            "SELECT DISTINCT project_id FROM arkham_project_members WHERE user_id = ?",
            [str(user.id)]
        )
        return [row["project_id"] for row in rows]
    except Exception as e:
        logger.warning(f"Failed to get user projects: {e}")
        return []


async def can_access_project(project_id: str, user: User, request=None) -> bool:
    """
    Check if user can access a project (is a member).
    
    Returns:
        True if user is a member, False otherwise
    """
    try:
        await require_project_member(project_id, user, request)
        return True
    except HTTPException:
        return False
