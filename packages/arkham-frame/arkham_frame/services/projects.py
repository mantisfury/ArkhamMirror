"""
ProjectService - Project management.
"""

from typing import Optional, List, Dict, Any


class ProjectNotFoundError(Exception):
    """Project not found."""
    def __init__(self, project_id: str):
        super().__init__(f"Project not found: {project_id}")


class ProjectExistsError(Exception):
    """Project already exists."""
    def __init__(self, name: str):
        super().__init__(f"Project already exists: {name}")


class ProjectService:
    """Project management service."""

    def __init__(self, db=None, config=None):
        self.db = db
        self.config = config

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a project by ID."""
        return None

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        return []

    async def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new project."""
        return {"id": "new", "name": name, "description": description}
