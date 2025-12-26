"""Entities Shard API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/entities", tags=["entities"])

# These get set by the shard on initialization
_db = None
_event_bus = None
_vectors_service = None
_entity_service = None


def init_api(db, event_bus, vectors_service, entity_service):
    """Initialize API with shard dependencies."""
    global _db, _event_bus, _vectors_service, _entity_service
    _db = db
    _event_bus = event_bus
    _vectors_service = vectors_service
    _entity_service = entity_service

    if vectors_service:
        logger.info("Entities API: Vector service available for merge suggestions")
    else:
        logger.info("Entities API: Vector service not available")


# --- Request/Response Models ---


class EntityResponse(BaseModel):
    """Entity detail response."""

    id: str
    name: str
    entity_type: str
    canonical_id: str | None = None
    aliases: list[str] = []
    metadata: dict = {}
    mention_count: int = 0
    created_at: str
    updated_at: str


class EntityListResponse(BaseModel):
    """Paginated entity list response."""

    items: list[EntityResponse]
    total: int
    page: int
    page_size: int


class UpdateEntityRequest(BaseModel):
    """Request to update an entity."""

    name: str | None = None
    entity_type: str | None = None
    aliases: list[str] | None = None
    metadata: dict | None = None


class MergeEntitiesRequest(BaseModel):
    """Request to merge multiple entities."""

    entity_ids: list[str]
    canonical_id: str
    canonical_name: str | None = None


class CreateRelationshipRequest(BaseModel):
    """Request to create a relationship."""

    source_id: str
    target_id: str
    relationship_type: str
    confidence: float = 1.0
    metadata: dict = {}


class RelationshipResponse(BaseModel):
    """Relationship response."""

    id: str
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    metadata: dict
    created_at: str


class MentionResponse(BaseModel):
    """Entity mention response."""

    id: str
    entity_id: str
    document_id: str
    mention_text: str
    start_offset: int
    end_offset: int
    confidence: float
    created_at: str


class MergeCandidateResponse(BaseModel):
    """Merge candidate suggestion."""

    entity_a: dict
    entity_b: dict
    similarity_score: float
    reason: str
    common_mentions: int
    common_documents: int


# --- Endpoints ---


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "shard": "entities",
        "vectors_available": _vectors_service is not None,
        "entity_service_available": _entity_service is not None,
    }


@router.get("/items", response_model=EntityListResponse)
async def list_entities(
    page: int = 1,
    page_size: int = 20,
    sort: str = "name",
    order: str = "asc",
    q: Annotated[str | None, Query(description="Search query")] = None,
    filter: Annotated[str | None, Query(description="Entity type filter")] = None,
    show_merged: Annotated[bool, Query(description="Include merged entities")] = False,
):
    """
    List all entities with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        sort: Sort field (name, entity_type, created_at, mention_count)
        order: Sort order (asc, desc)
        q: Search query for entity name
        filter: Filter by entity type (PERSON, ORGANIZATION, etc.)
        show_merged: Include entities that have been merged
    """
    # Stub implementation
    logger.debug(
        f"Listing entities: page={page}, size={page_size}, filter={filter}, search={q}"
    )

    # Validation
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    # Stub: Would query database with filters
    # Example query logic:
    # - Filter by entity_type if provided
    # - Filter by canonical_id IS NULL if show_merged=False
    # - Search name/aliases with q parameter
    # - Apply sorting
    # - Paginate results

    return EntityListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.get("/items/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str):
    """
    Get a single entity by ID.

    Args:
        entity_id: Entity UUID

    Returns:
        Entity details with mention count
    """
    # Stub implementation
    logger.debug(f"Getting entity: {entity_id}")

    # Stub: Would query database
    # If entity not found, raise 404
    raise HTTPException(status_code=404, detail="Entity not found")


@router.put("/items/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: str, request: UpdateEntityRequest):
    """
    Update an entity.

    Args:
        entity_id: Entity UUID
        request: Update data

    Returns:
        Updated entity
    """
    # Stub implementation
    logger.debug(f"Updating entity: {entity_id}")

    # Stub: Would update entity in database
    # Would publish event: entities.entity.edited
    if _event_bus:
        # await _event_bus.emit(
        #     "entities.entity.edited",
        #     {"entity_id": entity_id, "changes": request.dict(exclude_unset=True)},
        #     source="entities",
        # )
        pass

    raise HTTPException(status_code=404, detail="Entity not found")


@router.delete("/items/{entity_id}")
async def delete_entity(entity_id: str):
    """
    Delete an entity.

    Args:
        entity_id: Entity UUID

    Returns:
        Deletion confirmation
    """
    # Stub implementation
    logger.debug(f"Deleting entity: {entity_id}")

    # Stub: Would delete entity from database
    # Would cascade delete mentions and relationships

    return {"deleted": True, "entity_id": entity_id}


@router.get("/count")
async def get_count(
    filter: Annotated[str | None, Query(description="Entity type filter")] = None,
):
    """
    Get total entity count (for badge).

    Args:
        filter: Optional entity type filter

    Returns:
        Count object
    """
    # Stub implementation
    logger.debug(f"Getting entity count: filter={filter}")

    # Stub: Would count entities in database
    # Would filter by entity_type if provided
    # Would exclude merged entities (canonical_id IS NULL)

    return {"count": 0}


# --- Merge Endpoints ---


@router.get("/duplicates", response_model=list[MergeCandidateResponse])
async def get_duplicates(
    entity_type: Annotated[str | None, Query(description="Entity type filter")] = None,
    threshold: Annotated[float, Query(description="Similarity threshold")] = 0.8,
):
    """
    Get potential duplicate entities for merging.

    Args:
        entity_type: Filter by entity type
        threshold: Similarity threshold (0.0-1.0)

    Returns:
        List of merge candidate pairs
    """
    # Stub implementation
    logger.debug(f"Finding duplicates: type={entity_type}, threshold={threshold}")

    # Stub: Would find similar entities
    # - Use string similarity (Levenshtein, fuzzy matching)
    # - Use vector similarity if vectors service available
    # - Check for common mentions/documents
    # - Return candidates above threshold

    return []


@router.get("/merge-suggestions", response_model=list[MergeCandidateResponse])
async def get_merge_suggestions(
    entity_id: Annotated[str | None, Query(description="Get suggestions for specific entity")] = None,
    limit: Annotated[int, Query(description="Max suggestions to return")] = 10,
):
    """
    Get AI-suggested entity merges (requires vectors service).

    Args:
        entity_id: Optional specific entity to find matches for
        limit: Maximum number of suggestions

    Returns:
        List of suggested merges
    """
    if not _vectors_service:
        raise HTTPException(
            status_code=503,
            detail="Vector service not available - merge suggestions disabled",
        )

    # Stub implementation
    logger.debug(f"Getting merge suggestions: entity_id={entity_id}, limit={limit}")

    # Stub: Would use vector similarity to find candidates
    # - Embed entity names and context
    # - Find nearest neighbors in vector space
    # - Filter by entity type
    # - Return top matches

    return []


@router.post("/merge")
async def merge_entities(request: MergeEntitiesRequest):
    """
    Merge multiple entities into a canonical entity.

    Args:
        request: Merge request with entity IDs and canonical ID

    Returns:
        Merged entity details
    """
    # Stub implementation
    logger.debug(
        f"Merging entities {request.entity_ids} into {request.canonical_id}"
    )

    # Stub: Would perform merge
    # - Update non-canonical entities to set canonical_id
    # - Update entity name if canonical_name provided
    # - Migrate all mentions to canonical entity
    # - Preserve all relationships
    # - Merge aliases

    # Would publish event: entities.entity.merged
    if _event_bus:
        # await _event_bus.emit(
        #     "entities.entity.merged",
        #     {
        #         "canonical_id": request.canonical_id,
        #         "merged_ids": request.entity_ids,
        #         "canonical_name": request.canonical_name,
        #     },
        #     source="entities",
        # )
        pass

    return {
        "success": True,
        "canonical_id": request.canonical_id,
        "merged_count": len(request.entity_ids),
    }


# --- Relationship Endpoints ---


@router.get("/relationships", response_model=list[RelationshipResponse])
async def list_relationships(
    page: int = 1,
    page_size: int = 20,
    entity_id: Annotated[str | None, Query(description="Filter by entity")] = None,
    relationship_type: Annotated[
        str | None, Query(description="Filter by relationship type")
    ] = None,
):
    """
    List entity relationships.

    Args:
        page: Page number
        page_size: Items per page
        entity_id: Filter by source or target entity
        relationship_type: Filter by relationship type

    Returns:
        List of relationships
    """
    # Stub implementation
    logger.debug(
        f"Listing relationships: entity={entity_id}, type={relationship_type}"
    )

    # Stub: Would query relationships table
    # - Filter by source_id OR target_id if entity_id provided
    # - Filter by relationship_type if provided
    # - Paginate results

    return []


@router.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(request: CreateRelationshipRequest):
    """
    Create a relationship between two entities.

    Args:
        request: Relationship data

    Returns:
        Created relationship
    """
    # Stub implementation
    logger.debug(
        f"Creating relationship: {request.source_id} -{request.relationship_type}-> {request.target_id}"
    )

    # Stub: Would create relationship in database
    # - Validate source and target entities exist
    # - Create relationship record
    # - Return created relationship

    # Would publish event: entities.relationship.created
    if _event_bus:
        # await _event_bus.emit(
        #     "entities.relationship.created",
        #     {
        #         "relationship_id": "new-id",
        #         "source_id": request.source_id,
        #         "target_id": request.target_id,
        #         "relationship_type": request.relationship_type,
        #     },
        #     source="entities",
        # )
        pass

    raise HTTPException(status_code=404, detail="Entity not found")


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(relationship_id: str):
    """
    Delete a relationship.

    Args:
        relationship_id: Relationship UUID

    Returns:
        Deletion confirmation
    """
    # Stub implementation
    logger.debug(f"Deleting relationship: {relationship_id}")

    # Stub: Would delete relationship from database

    # Would publish event: entities.relationship.deleted
    if _event_bus:
        # await _event_bus.emit(
        #     "entities.relationship.deleted",
        #     {"relationship_id": relationship_id},
        #     source="entities",
        # )
        pass

    return {"deleted": True, "relationship_id": relationship_id}


@router.get("/{entity_id}/relationships", response_model=list[RelationshipResponse])
async def get_entity_relationships(entity_id: str):
    """
    Get all relationships for a specific entity.

    Args:
        entity_id: Entity UUID

    Returns:
        List of relationships where entity is source or target
    """
    # Stub implementation
    logger.debug(f"Getting relationships for entity: {entity_id}")

    # Stub: Would query relationships where source_id OR target_id = entity_id

    return []


# --- Mention Endpoints ---


@router.get("/{entity_id}/mentions", response_model=list[MentionResponse])
async def get_entity_mentions(
    entity_id: str,
    page: int = 1,
    page_size: int = 50,
):
    """
    Get all mentions for a specific entity.

    Args:
        entity_id: Entity UUID
        page: Page number
        page_size: Items per page

    Returns:
        List of mentions with document references
    """
    # Stub implementation
    logger.debug(f"Getting mentions for entity: {entity_id}")

    # Stub: Would query mentions table
    # - Filter by entity_id
    # - Include canonical entity mentions if this entity is merged
    # - Order by created_at DESC
    # - Paginate results

    # Would publish event: entities.entity.viewed
    if _event_bus:
        # await _event_bus.emit(
        #     "entities.entity.viewed",
        #     {"entity_id": entity_id},
        #     source="entities",
        # )
        pass

    return []


# --- Batch Operations ---


@router.post("/batch/merge")
async def batch_merge(requests: list[MergeEntitiesRequest]):
    """
    Perform multiple merge operations in batch.

    Args:
        requests: List of merge requests

    Returns:
        Batch operation results
    """
    # Stub implementation
    logger.debug(f"Batch merging {len(requests)} entity groups")

    # Stub: Would perform each merge in transaction
    # - Process all merges
    # - Return success/failure for each

    return {
        "success": True,
        "processed": len(requests),
        "failed": 0,
        "errors": [],
    }
