"""
EntityService - Entity access.
"""

from typing import Optional, List, Dict, Any


class EntityNotFoundError(Exception):
    """Entity not found."""
    def __init__(self, entity_id: str):
        super().__init__(f"Entity not found: {entity_id}")


class EntityService:
    """Entity access service."""

    def __init__(self, db=None, config=None):
        self.db = db
        self.config = config

    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity by ID."""
        return None

    async def list_entities(
        self,
        offset: int = 0,
        limit: int = 50,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List entities with pagination."""
        return []
