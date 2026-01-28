"""Entities Shard API endpoints."""

import logging
from typing import Annotated, Any, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import EntitiesShard

try:
    from arkham_frame.auth import (
        current_active_user,
        current_optional_user,
        require_project_member,
    )
except ImportError:
    async def current_active_user():
        return None
    async def current_optional_user():
        return None
    async def require_project_member():
        return None

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


def get_shard(request: Request) -> "EntitiesShard":
    """Get the entities shard instance from app state."""
    shard = getattr(request.app.state, "entities_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Entities shard not available")
    return shard


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


# --- Helper Functions ---


def entity_to_response(entity) -> EntityResponse:
    """Convert Entity dataclass to EntityResponse."""
    return EntityResponse(
        id=entity.id,
        name=entity.name,
        entity_type=entity.entity_type.value,
        canonical_id=entity.canonical_id,
        aliases=entity.aliases,
        metadata=entity.metadata,
        mention_count=getattr(entity, 'mention_count', 0),
        created_at=entity.created_at.isoformat() if entity.created_at else "",
        updated_at=entity.updated_at.isoformat() if entity.updated_at else "",
    )


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
    request: Request,
    page: int = 1,
    page_size: int = 20,
    sort: str = "name",
    order: str = "asc",
    q: Annotated[str | None, Query(description="Search query")] = None,
    filter: Annotated[str | None, Query(description="Entity type filter")] = None,
    show_merged: Annotated[bool, Query(description="Include merged entities")] = False,
    project_id: Optional[str] = Query(None, description="Filter by project"),
    user = Depends(current_active_user),
):
    """
    List all entities with pagination and filtering.

    All entities are scoped to the active project for data isolation.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        sort: Sort field (name, entity_type, created_at, mention_count)
        order: Sort order (asc, desc)
        q: Search query for entity name
        filter: Filter by entity type (PERSON, ORGANIZATION, etc.)
        show_merged: Include entities that have been merged
        project_id: Project ID to filter by (defaults to active project)
    """
    logger.debug(f"list_entities called by user {user.id if user else 'None'}, project_id param={project_id}")
    
    shard = get_shard(request)
    
    # Use project_id from query param if provided, otherwise use active project
    if not project_id and shard.frame:
        project_id = await shard.frame.get_active_project_id(str(user.id))
        logger.debug(f"Using active project from frame: {project_id}")
    
    # If no project_id, return empty results (entities are project-scoped)
    if not project_id:
        logger.debug(f"No project_id available. Returning empty results. Query param was: {request.query_params.get('project_id')}")
        return EntityListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
        )
    
    # Verify user is a member of the project
    await require_project_member(project_id, user, request)
    
    logger.debug(f"Using project_id: {project_id}")

    # Validation
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    # Get entities from shard (scoped to project)
    entities = await shard.list_entities(
        search=q,
        entity_type=filter,
        limit=page_size,
        offset=offset,
        show_merged=show_merged,
        project_id=project_id
    )

    # Get total count for accurate pagination (scoped to project)
    total = await shard.count_entities(
        search=q,
        entity_type=filter,
        show_merged=show_merged,
        project_id=project_id
    )

    return EntityListResponse(
        items=[entity_to_response(e) for e in entities],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/items/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    request: Request,
    user = Depends(current_active_user),
):
    """
    Get a single entity by ID.

    Args:
        entity_id: Entity ID

    Returns:
        Entity details with mention count
    """
    shard = get_shard(request)
    entity = await shard.get_entity(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    
    # Verify user is a member of the entity's project
    if entity.project_id:
        await require_project_member(entity.project_id, user, request)

    return entity_to_response(entity)


@router.put("/items/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: str, update_request: UpdateEntityRequest, request: Request):
    """
    Update an entity.

    Args:
        entity_id: Entity UUID
        update_request: Update data

    Returns:
        Updated entity
    """
    if not _entity_service:
        raise HTTPException(status_code=503, detail="Entity service not available")

    try:
        # Build updates dict from request
        updates = {}
        if update_request.name is not None:
            updates["text"] = update_request.name
        if update_request.entity_type is not None:
            updates["entity_type"] = update_request.entity_type
        if update_request.metadata is not None:
            updates["metadata"] = update_request.metadata

        # Update via EntityService
        updated = await _entity_service.update_entity(entity_id, updates)

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "entities.entity.edited",
                {"entity_id": entity_id, "changes": updates},
                source="entities-shard",
            )

        return EntityResponse(
            id=updated.id,
            name=updated.text,
            entity_type=updated.entity_type.value if hasattr(updated.entity_type, 'value') else str(updated.entity_type),
            canonical_id=updated.canonical_id,
            aliases=[],
            metadata=updated.metadata or {},
            mention_count=0,
            created_at=updated.created_at.isoformat() if updated.created_at else "",
            updated_at=updated.created_at.isoformat() if updated.created_at else "",
        )

    except Exception as e:
        logger.error(f"Failed to update entity {entity_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")


@router.delete("/items/{entity_id}")
async def delete_entity(entity_id: str):
    """
    Delete an entity.

    Args:
        entity_id: Entity UUID

    Returns:
        Deletion confirmation
    """
    if not _entity_service:
        raise HTTPException(status_code=503, detail="Entity service not available")

    try:
        deleted = await _entity_service.delete_entity(entity_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "entities.entity.deleted",
                {"entity_id": entity_id},
                source="entities-shard",
            )

        return {"deleted": True, "entity_id": entity_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count")
async def get_count(
    request: Request,
    filter: Annotated[str | None, Query(description="Entity type filter")] = None,
    project_id: Optional[str] = Query(None, description="Filter by project"),
):
    """
    Get total entity count (for badge).

    Args:
        filter: Optional entity type filter
        project_id: Project ID to filter by (defaults to active project)

    Returns:
        Count object
    """
    shard = get_shard(request)
    
    # Use project_id from query param if provided, otherwise use active project
    if not project_id and shard.frame:
        project_id = shard.frame.active_project_id
    
    stats = await shard.get_entity_stats(project_id=project_id)

    if filter and filter in stats:
        return {"count": stats[filter]}

    return {"count": stats.get("TOTAL", 0)}


# --- Merge Endpoints ---


@router.get("/duplicates", response_model=list[MergeCandidateResponse])
async def get_duplicates(
    request: Request,
    entity_type: Annotated[str | None, Query(description="Entity type filter")] = None,
    threshold: Annotated[float, Query(description="Similarity threshold")] = 0.8,
    limit: Annotated[int, Query(description="Max candidates to return")] = 50,
    project_id: Optional[str] = Query(None, description="Filter by project"),
):
    """
    Get potential duplicate entities for merging.

    Uses fuzzy string matching to find entities with similar names.

    Args:
        entity_type: Filter by entity type
        threshold: Similarity threshold (0.0-1.0)
        limit: Maximum candidates to return
        project_id: Project ID to filter by (defaults to active project)

    Returns:
        List of merge candidate pairs
    """
    shard = get_shard(request)

    # Use project_id from query param if provided, otherwise use active project
    if not project_id and shard.frame:
        project_id = shard.frame.active_project_id

    try:
        # Get all entities (we'll compare them) - scoped to project
        entities = await shard.list_entities(
            entity_type=entity_type,
            limit=500,  # Reasonable limit for comparison
            show_merged=False,
            project_id=project_id,
        )

        if len(entities) < 2:
            return []

        # Find duplicates using fuzzy string matching
        candidates = []
        seen_pairs = set()

        for i, entity_a in enumerate(entities):
            for entity_b in entities[i + 1:]:
                # Skip if different types (unless no type filter)
                if entity_a.entity_type != entity_b.entity_type:
                    continue

                # Skip if already seen this pair
                pair_key = tuple(sorted([entity_a.id, entity_b.id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Calculate similarity
                similarity = _calculate_similarity(entity_a.name, entity_b.name)

                if similarity >= threshold:
                    candidates.append(MergeCandidateResponse(
                        entity_a={
                            "id": entity_a.id,
                            "name": entity_a.name,
                            "entity_type": entity_a.entity_type.value if hasattr(entity_a.entity_type, 'value') else str(entity_a.entity_type),
                        },
                        entity_b={
                            "id": entity_b.id,
                            "name": entity_b.name,
                            "entity_type": entity_b.entity_type.value if hasattr(entity_b.entity_type, 'value') else str(entity_b.entity_type),
                        },
                        similarity_score=similarity,
                        reason=_get_similarity_reason(entity_a.name, entity_b.name, similarity),
                        common_mentions=0,
                        common_documents=0,
                    ))

                    if len(candidates) >= limit:
                        break

            if len(candidates) >= limit:
                break

        # Sort by similarity score descending
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)

        return candidates[:limit]

    except Exception as e:
        logger.error(f"Failed to find duplicates: {e}")
        return []


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings using multiple methods.

    Returns a score between 0.0 and 1.0.
    """
    if not str1 or not str2:
        return 0.0

    # Normalize strings
    s1 = str1.lower().strip()
    s2 = str2.lower().strip()

    # Exact match
    if s1 == s2:
        return 1.0

    # Check if one contains the other
    if s1 in s2 or s2 in s1:
        shorter = min(len(s1), len(s2))
        longer = max(len(s1), len(s2))
        return shorter / longer * 0.95  # High score but not perfect

    # Levenshtein distance-based similarity
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0

    return 1.0 - (distance / max_len)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _get_similarity_reason(name1: str, name2: str, score: float) -> str:
    """Generate a human-readable reason for the similarity."""
    s1 = name1.lower().strip()
    s2 = name2.lower().strip()

    if s1 == s2:
        return "Exact match (case-insensitive)"
    elif s1 in s2:
        return f"'{name1}' is contained in '{name2}'"
    elif s2 in s1:
        return f"'{name2}' is contained in '{name1}'"
    elif score >= 0.9:
        return "Very similar names (possible typo)"
    elif score >= 0.8:
        return "Similar names (likely same entity)"
    else:
        return "Moderately similar names"


@router.get("/merge-suggestions", response_model=list[MergeCandidateResponse])
async def get_merge_suggestions(
    request: Request,
    entity_id: Annotated[str | None, Query(description="Get suggestions for specific entity")] = None,
    limit: Annotated[int, Query(description="Max suggestions to return")] = 10,
):
    """
    Get AI-suggested entity merges using vector similarity.

    If vectors service is not available, falls back to fuzzy string matching.

    Args:
        entity_id: Optional specific entity to find matches for
        limit: Maximum number of suggestions

    Returns:
        List of suggested merges
    """
    shard = get_shard(request)

    try:
        # If specific entity requested, find similar entities to it
        if entity_id:
            target_entity = await shard.get_entity(entity_id)
            if not target_entity:
                raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

            # Get project_id for filtering
            project_id = None
            if shard.frame:
                project_id = shard.frame.active_project_id
            
            # Get entities of same type (scoped to project)
            entities = await shard.list_entities(
                entity_type=target_entity.entity_type.value if hasattr(target_entity.entity_type, 'value') else str(target_entity.entity_type),
                limit=200,
                show_merged=False,
                project_id=project_id,
            )

            # Find similar entities
            candidates = []
            for entity in entities:
                if entity.id == entity_id:
                    continue

                # Use vector similarity if available
                if _vectors_service:
                    try:
                        similarity = await _get_vector_similarity(
                            target_entity.name, entity.name
                        )
                    except Exception:
                        similarity = _calculate_similarity(target_entity.name, entity.name)
                else:
                    similarity = _calculate_similarity(target_entity.name, entity.name)

                if similarity >= 0.7:  # Lower threshold for suggestions
                    candidates.append(MergeCandidateResponse(
                        entity_a={
                            "id": target_entity.id,
                            "name": target_entity.name,
                            "entity_type": target_entity.entity_type.value if hasattr(target_entity.entity_type, 'value') else str(target_entity.entity_type),
                        },
                        entity_b={
                            "id": entity.id,
                            "name": entity.name,
                            "entity_type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                        },
                        similarity_score=similarity,
                        reason="Vector similarity" if _vectors_service else "Name similarity",
                        common_mentions=0,
                        common_documents=0,
                    ))

            candidates.sort(key=lambda x: x.similarity_score, reverse=True)
            return candidates[:limit]

        # No specific entity - return general duplicate suggestions
        # Fall back to duplicates endpoint logic with lower threshold
        project_id = None
        if shard.frame:
            project_id = shard.frame.active_project_id
        
        entities = await shard.list_entities(limit=300, show_merged=False, project_id=project_id)

        if len(entities) < 2:
            return []

        candidates = []
        seen_pairs = set()

        for i, entity_a in enumerate(entities):
            for entity_b in entities[i + 1:]:
                if entity_a.entity_type != entity_b.entity_type:
                    continue

                pair_key = tuple(sorted([entity_a.id, entity_b.id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                similarity = _calculate_similarity(entity_a.name, entity_b.name)

                if similarity >= 0.75:
                    candidates.append(MergeCandidateResponse(
                        entity_a={
                            "id": entity_a.id,
                            "name": entity_a.name,
                            "entity_type": entity_a.entity_type.value if hasattr(entity_a.entity_type, 'value') else str(entity_a.entity_type),
                        },
                        entity_b={
                            "id": entity_b.id,
                            "name": entity_b.name,
                            "entity_type": entity_b.entity_type.value if hasattr(entity_b.entity_type, 'value') else str(entity_b.entity_type),
                        },
                        similarity_score=similarity,
                        reason=_get_similarity_reason(entity_a.name, entity_b.name, similarity),
                        common_mentions=0,
                        common_documents=0,
                    ))

                    if len(candidates) >= limit * 2:
                        break

            if len(candidates) >= limit * 2:
                break

        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates[:limit]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get merge suggestions: {e}")
        return []


async def _get_vector_similarity(text1: str, text2: str) -> float:
    """Get similarity between two texts using vector embeddings."""
    if not _vectors_service:
        return _calculate_similarity(text1, text2)

    try:
        # Embed both texts
        embeddings = await _vectors_service.embed_texts([text1, text2])
        if len(embeddings) != 2:
            return _calculate_similarity(text1, text2)

        # Calculate cosine similarity
        import math
        vec1, vec2 = embeddings[0], embeddings[1]

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    except Exception as e:
        logger.warning(f"Vector similarity failed, falling back to string similarity: {e}")
        return _calculate_similarity(text1, text2)


@router.post("/merge")
async def merge_entities(merge_request: MergeEntitiesRequest, request: Request):
    """
    Merge multiple entities into a canonical entity.

    Args:
        merge_request: Merge request with entity IDs and canonical ID

    Returns:
        Merged entity details
    """
    shard = get_shard(request)

    # Merge each entity into the canonical one
    for entity_id in merge_request.entity_ids:
        if entity_id != merge_request.canonical_id:
            await shard.merge_entities(entity_id, merge_request.canonical_id)

    # Get the updated canonical entity
    canonical = await shard.get_entity(merge_request.canonical_id)

    return {
        "success": True,
        "canonical_id": merge_request.canonical_id,
        "merged_count": len([eid for eid in merge_request.entity_ids if eid != merge_request.canonical_id]),
        "canonical_entity": entity_to_response(canonical) if canonical else None,
    }


# --- Relationship Endpoints ---


@router.get("/relationships", response_model=list[RelationshipResponse])
async def list_relationships(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    entity_id: Annotated[str | None, Query(description="Filter by entity")] = None,
    relationship_type: Annotated[
        str | None, Query(description="Filter by relationship type")
    ] = None,
):
    """
    List entity relationships from shard's arkham_entity_relationships table.

    Args:
        page: Page number
        page_size: Items per page
        entity_id: Filter by source or target entity
        relationship_type: Filter by relationship type

    Returns:
        List of relationships
    """
    shard = get_shard(request)

    try:
        if entity_id:
            # Get relationships for a specific entity
            relationships = await shard.get_entity_relationships(
                entity_id,
                direction="both",
                relationship_type=relationship_type,
            )
        else:
            # Get all relationships with pagination
            relationships = await shard.list_relationships(
                offset=(page - 1) * page_size,
                limit=page_size,
                relationship_type=relationship_type,
            )

        return [
            RelationshipResponse(
                id=rel["id"],
                source_id=rel["source_id"],
                target_id=rel["target_id"],
                relationship_type=rel["relationship_type"],
                confidence=rel.get("confidence", 1.0),
                metadata=rel.get("metadata", {}),
                created_at=rel["created_at"].isoformat() if rel.get("created_at") else "",
            )
            for rel in relationships
        ]

    except Exception as e:
        logger.error(f"Failed to list relationships: {e}")
        return []


@router.get("/relationships/types")
async def get_relationship_types():
    """Get available relationship types."""
    return {
        "types": [
            {"value": "WORKS_FOR", "label": "Works For", "description": "Employment relationship"},
            {"value": "LOCATED_IN", "label": "Located In", "description": "Geographic location"},
            {"value": "MEMBER_OF", "label": "Member Of", "description": "Membership in organization"},
            {"value": "OWNS", "label": "Owns", "description": "Ownership relationship"},
            {"value": "RELATED_TO", "label": "Related To", "description": "General relationship"},
            {"value": "MENTIONED_WITH", "label": "Mentioned With", "description": "Co-occurrence in documents"},
            {"value": "PARENT_OF", "label": "Parent Of", "description": "Hierarchical parent"},
            {"value": "CHILD_OF", "label": "Child Of", "description": "Hierarchical child"},
            {"value": "SAME_AS", "label": "Same As", "description": "Identity relationship"},
            {"value": "PART_OF", "label": "Part Of", "description": "Component relationship"},
            {"value": "OTHER", "label": "Other", "description": "Other relationship type"},
        ]
    }


@router.get("/relationships/stats")
async def get_relationship_stats():
    """Get relationship statistics."""
    if not _entity_service:
        return {"total": 0, "by_type": {}}

    try:
        stats = await _entity_service.get_relationship_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get relationship stats: {e}")
        return {"total": 0, "by_type": {}}


@router.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(rel_request: CreateRelationshipRequest):
    """
    Create a relationship between two entities.

    Args:
        rel_request: Relationship data

    Returns:
        Created relationship
    """
    if not _entity_service:
        raise HTTPException(status_code=503, detail="Entity service not available")

    try:
        from arkham_frame.services.entities import RelationshipType

        # Convert relationship type string to enum
        try:
            rel_type = RelationshipType(rel_request.relationship_type)
        except ValueError:
            rel_type = RelationshipType.OTHER

        # Create relationship via EntityService
        relationship = await _entity_service.create_relationship(
            source_id=rel_request.source_id,
            target_id=rel_request.target_id,
            relationship_type=rel_type,
            confidence=rel_request.confidence,
            metadata=rel_request.metadata,
        )

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "entities.relationship.created",
                {
                    "relationship_id": relationship.id,
                    "source_id": relationship.source_id,
                    "target_id": relationship.target_id,
                    "relationship_type": relationship.relationship_type.value,
                },
                source="entities-shard",
            )

        return RelationshipResponse(
            id=relationship.id,
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            relationship_type=relationship.relationship_type.value if hasattr(relationship.relationship_type, 'value') else str(relationship.relationship_type),
            confidence=relationship.confidence,
            metadata=relationship.metadata or {},
            created_at=relationship.created_at.isoformat() if relationship.created_at else "",
        )

    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(relationship_id: str):
    """
    Delete a relationship.

    Args:
        relationship_id: Relationship UUID

    Returns:
        Deletion confirmation
    """
    if not _entity_service:
        raise HTTPException(status_code=503, detail="Entity service not available")

    try:
        deleted = await _entity_service.delete_relationship(relationship_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Relationship not found: {relationship_id}")

        # Publish event
        if _event_bus:
            await _event_bus.emit(
                "entities.relationship.deleted",
                {"relationship_id": relationship_id},
                source="entities-shard",
            )

        return {"deleted": True, "relationship_id": relationship_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete relationship {relationship_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}/relationships", response_model=list[RelationshipResponse])
async def get_entity_relationships(entity_id: str, request: Request):
    """
    Get all relationships for a specific entity from shard's table.

    Args:
        entity_id: Entity UUID

    Returns:
        List of relationships where entity is source or target
    """
    shard = get_shard(request)

    try:
        relationships = await shard.get_entity_relationships(
            entity_id,
            direction="both",
        )

        return [
            RelationshipResponse(
                id=rel["id"],
                source_id=rel["source_id"],
                target_id=rel["target_id"],
                relationship_type=rel["relationship_type"],
                confidence=rel.get("confidence", 1.0),
                metadata=rel.get("metadata", {}),
                created_at=rel["created_at"].isoformat() if rel.get("created_at") else "",
            )
            for rel in relationships
        ]

    except Exception as e:
        logger.error(f"Failed to get relationships for entity {entity_id}: {e}")
        return []


# --- Mention Endpoints ---


@router.get("/{entity_id}/mentions", response_model=list[MentionResponse])
async def get_entity_mentions(
    entity_id: str,
    request: Request,
    page: int = 1,
    page_size: int = 50,
):
    """
    Get all mentions for a specific entity.

    Args:
        entity_id: Entity ID
        page: Page number
        page_size: Items per page

    Returns:
        List of mentions with document references
    """
    shard = get_shard(request)
    mentions_data = await shard.get_entity_mentions(entity_id)

    # Publish event
    if _event_bus:
        await _event_bus.emit("entities.entity.viewed", {"entity_id": entity_id}, source="entities-shard")

    # Convert to response models
    mentions = []
    for mention in mentions_data:
        mentions.append(MentionResponse(
            id=mention["id"],
            entity_id=mention["entity_id"],
            document_id=mention["document_id"],
            mention_text=mention["mention_text"],
            confidence=mention["confidence"],
            start_offset=mention["start_offset"],
            end_offset=mention["end_offset"],
            created_at=mention["created_at"] or "",
        ))

    # Simple pagination
    start = (page - 1) * page_size
    end = start + page_size
    return mentions[start:end]


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


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""

    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: str | None = None
    message: str | None = None
    conversation_history: list[dict[str, str]] | None = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for entity analysis.

    Provides streaming AI analysis of entities, relationships, and patterns.
    """
    shard = get_shard(request)
    frame = shard._frame
    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(status_code=503, detail="AI Analyst service not available")

    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Map depth string to enum
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.DETAILED,
        "detailed": AnalysisDepth.DETAILED,
        "deep": AnalysisDepth.DETAILED,
    }
    depth = depth_map.get(body.depth, AnalysisDepth.QUICK)

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=m["role"], content=m["content"])
            for m in body.conversation_history
        ]

    # Create analysis request
    analysis_request = AnalysisRequest(
        shard="entities",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Return streaming response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
