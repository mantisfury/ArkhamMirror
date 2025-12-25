"""
Entity API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional

router = APIRouter()


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List entities with optional filtering."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.entities:
        raise HTTPException(status_code=503, detail="Entity service unavailable")

    entities = await frame.entities.list_entities(
        entity_type=entity_type,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )

    return {
        "entities": entities,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{entity_id}")
async def get_entity(entity_id: str) -> Dict[str, Any]:
    """Get an entity by ID."""
    from ..main import get_frame
    from ..services import EntityNotFoundError

    frame = get_frame()

    if not frame.entities:
        raise HTTPException(status_code=503, detail="Entity service unavailable")

    try:
        entity = await frame.entities.get_entity(entity_id)
        return entity
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(
    entity_id: str,
    limit: int = Query(default=50, le=200),
) -> Dict[str, Any]:
    """Get relationships for an entity."""
    from ..main import get_frame
    from ..services import EntityNotFoundError

    frame = get_frame()

    if not frame.entities:
        raise HTTPException(status_code=503, detail="Entity service unavailable")

    try:
        relationships = await frame.entities.get_relationships(entity_id, limit=limit)
        return {
            "entity_id": entity_id,
            "relationships": relationships,
        }
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")


@router.get("/{entity_id}/documents")
async def get_entity_documents(
    entity_id: str,
    limit: int = Query(default=50, le=200),
) -> Dict[str, Any]:
    """Get documents mentioning an entity."""
    from ..main import get_frame
    from ..services import EntityNotFoundError

    frame = get_frame()

    if not frame.entities:
        raise HTTPException(status_code=503, detail="Entity service unavailable")

    try:
        documents = await frame.entities.get_entity_documents(entity_id, limit=limit)
        return {
            "entity_id": entity_id,
            "documents": documents,
        }
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
