# Entities Shard - Wiring Plan

## Current State Summary

The Entities shard has database schema creation and API structure, but the **actual entity data comes from the parse shard**, not from this shard's own storage. This shard is primarily a **viewer/manager** for entities extracted elsewhere.

### What Exists
- **Backend**:
  - Complete shard structure in `shard.py` (607 lines)
  - Full API endpoints in `api.py` (597 lines)
  - Database schema creation (`arkham_entities`, `arkham_entity_mentions`, `arkham_entity_relationships`)
  - Models in `models.py` (143 lines)

- **Frontend**:
  - Complete UI in `EntitiesPage.tsx` with search/filtering
  - Type-specific icons (Person, Organization, Location, etc.)
  - Entity detail view with mentions display

### What's Missing

1. **Entity Population**: Schema exists but no mechanism to populate entities from parse shard
2. **Event Subscription**: Event handlers are stubbed out (commented)
3. **Merge Functionality**: API exists but backend merge logic is incomplete
4. **Relationship Management**: API exists but no real relationship creation

## Specific Missing Pieces

### Backend Files to Modify

#### 1. `arkham_shard_entities/shard.py`
**Lines 93-96**: Uncomment and implement event subscriptions

**Current**:
```python
if self._event_bus:
    # Subscribe to entity extraction events from parse shard
    # await self._event_bus.subscribe("parse.entity.created", self._on_entity_created)
    # await self._event_bus.subscribe("parse.entity.updated", self._on_entity_updated)
    logger.info("Subscribed to parse shard entity events")
```

**Replace with**:
```python
if self._event_bus:
    # Subscribe to entity extraction events from parse shard
    await self._event_bus.subscribe("parse.entity.extracted", self._on_entity_extracted)
    await self._event_bus.subscribe("parse.entities.batch", self._on_entities_batch)
    logger.info("Subscribed to parse shard entity events")
```

**Add event handler methods**:
```python
async def _on_entity_extracted(self, event: dict) -> None:
    """
    Handle entity extraction from parse shard.

    Event payload:
        {
            "document_id": str,
            "entities": [
                {
                    "text": str,
                    "entity_type": str,
                    "start_offset": int,
                    "end_offset": int,
                    "confidence": float
                }
            ]
        }
    """
    document_id = event.get("document_id")
    entities = event.get("entities", [])

    if not document_id or not entities:
        return

    logger.info(f"Received {len(entities)} entities from document {document_id}")

    for entity_data in entities:
        await self._store_entity_mention(
            document_id=document_id,
            entity_text=entity_data["text"],
            entity_type=entity_data["entity_type"],
            start_offset=entity_data["start_offset"],
            end_offset=entity_data["end_offset"],
            confidence=entity_data.get("confidence", 1.0),
        )

async def _on_entities_batch(self, event: dict) -> None:
    """Handle batch entity extraction."""
    batch = event.get("batch", [])
    for doc_entities in batch:
        await self._on_entity_extracted(doc_entities)

async def _store_entity_mention(
    self,
    document_id: str,
    entity_text: str,
    entity_type: str,
    start_offset: int,
    end_offset: int,
    confidence: float,
) -> None:
    """
    Store an entity mention and create/update the entity record.

    This implements entity resolution:
    1. Check if entity already exists (by text and type)
    2. If not, create new entity
    3. Create mention record linking entity to document
    """
    if not self._db:
        return

    import uuid
    from datetime import datetime

    # Normalize entity text (strip, lowercase for matching)
    normalized_text = entity_text.strip()
    search_key = normalized_text.lower()

    # Check if entity exists
    existing = await self._db.fetch_one("""
        SELECT id, name FROM arkham_entities
        WHERE LOWER(name) = ? AND entity_type = ?
    """, [search_key, entity_type])

    if existing:
        entity_id = existing["id"]
        logger.debug(f"Found existing entity: {entity_id} for '{entity_text}'")
    else:
        # Create new entity
        entity_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await self._db.execute("""
            INSERT INTO arkham_entities (
                id, name, entity_type, canonical_id,
                aliases, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            entity_id,
            normalized_text,
            entity_type,
            None,  # canonical_id - for merge resolution
            "[]",  # aliases (JSON array)
            "{}",  # metadata
            now,
            now,
        ])
        logger.debug(f"Created new entity: {entity_id} for '{entity_text}'")

    # Create mention record
    mention_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await self._db.execute("""
        INSERT INTO arkham_entity_mentions (
            id, entity_id, document_id,
            mention_text, start_offset, end_offset,
            confidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        mention_id,
        entity_id,
        document_id,
        entity_text,  # Original text (with case)
        start_offset,
        end_offset,
        confidence,
        now,
    ])

    # Emit event
    if self._event_bus:
        await self._event_bus.emit(
            "entities.entity.mentioned",
            {
                "entity_id": entity_id,
                "document_id": document_id,
                "mention_id": mention_id,
                "text": entity_text,
                "entity_type": entity_type,
            },
            source="entities-shard",
        )
```

#### 2. `arkham_shard_entities/api.py`
**Lines 150-250**: Verify list endpoint returns real data

The list endpoint at line 152 (`@router.get("/items")`) should already work if entities are in the database. However, we need to ensure:

**Check/Add** (around line 152):
```python
@router.get("/items")
async def list_entities(
    request: Request,
    q: str | None = None,
    filter: str | None = None,  # entity_type filter
    page: int = 1,
    page_size: int = 50,
):
    """List entities with search and filtering."""
    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Build query
    conditions = ["1=1"]
    params = []

    # Search by name
    if q:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{q.lower()}%")

    # Filter by type
    if filter:
        conditions.append("entity_type = ?")
        params.append(filter)

    where_clause = " AND ".join(conditions)

    # Get total count
    count_result = await shard._db.fetch_one(
        f"SELECT COUNT(*) as count FROM arkham_entities WHERE {where_clause}",
        params
    )
    total = count_result["count"]

    # Get paginated results with mention counts
    offset = (page - 1) * page_size
    rows = await shard._db.fetch_all(f"""
        SELECT
            e.*,
            COUNT(DISTINCT m.id) as mention_count
        FROM arkham_entities e
        LEFT JOIN arkham_entity_mentions m ON e.id = m.entity_id
        WHERE {where_clause}
        GROUP BY e.id
        ORDER BY e.name ASC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])

    items = []
    for row in rows:
        items.append(EntityResponse(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            canonical_id=row["canonical_id"],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            mention_count=row["mention_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))

    return EntityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
```

**Lines 400-450**: Implement merge functionality

**Current**: Merge endpoint exists but may not have full logic

**Add/Verify**:
```python
@router.post("/merge")
async def merge_entities(request: Request, merge_request: MergeEntitiesRequest):
    """
    Merge multiple entities into a canonical entity.

    All mentions of merged entities are updated to point to the canonical entity.
    """
    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    if len(merge_request.entity_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 entities required for merge")

    canonical_id = merge_request.canonical_id
    canonical_name = merge_request.canonical_name

    # Verify all entities exist
    for entity_id in merge_request.entity_ids:
        entity = await shard._db.fetch_one(
            "SELECT id FROM arkham_entities WHERE id = ?", [entity_id]
        )
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    # Get canonical entity
    canonical = await shard._db.fetch_one(
        "SELECT * FROM arkham_entities WHERE id = ?", [canonical_id]
    )
    if not canonical:
        raise HTTPException(status_code=404, detail=f"Canonical entity not found: {canonical_id}")

    # Update canonical entity name if provided
    if canonical_name:
        await shard._db.execute(
            "UPDATE arkham_entities SET name = ?, updated_at = ? WHERE id = ?",
            [canonical_name, datetime.utcnow().isoformat(), canonical_id]
        )

    # Merge process
    merged_count = 0
    for entity_id in merge_request.entity_ids:
        if entity_id == canonical_id:
            continue  # Skip canonical itself

        # Update all mentions to point to canonical
        await shard._db.execute(
            "UPDATE arkham_entity_mentions SET entity_id = ? WHERE entity_id = ?",
            [canonical_id, entity_id]
        )

        # Mark entity as merged (set canonical_id)
        await shard._db.execute(
            "UPDATE arkham_entities SET canonical_id = ?, updated_at = ? WHERE id = ?",
            [canonical_id, datetime.utcnow().isoformat(), entity_id]
        )

        merged_count += 1

    # Emit event
    if shard._event_bus:
        await shard._event_bus.emit(
            "entities.entity.merged",
            {
                "canonical_id": canonical_id,
                "merged_ids": [e for e in merge_request.entity_ids if e != canonical_id],
                "count": merged_count,
            },
            source="entities-shard",
        )

    return {
        "status": "merged",
        "canonical_id": canonical_id,
        "merged_count": merged_count,
    }
```

### Frontend Changes

**None required** - frontend is already complete and will work once backend returns data.

## Implementation Steps

### Step 1: Implement Event Handlers (MEDIUM)
**Files**: `arkham_shard_entities/shard.py`
- Uncomment event subscriptions
- Implement `_on_entity_extracted()` handler
- Implement `_on_entities_batch()` handler
- Implement `_store_entity_mention()` with entity resolution

**Estimated time**: 1.5 hours

### Step 2: Verify List Endpoint (SMALL)
**Files**: `arkham_shard_entities/api.py`
- Ensure `/items` endpoint has proper SQL queries
- Add mention count aggregation
- Test search and filtering

**Estimated time**: 30 minutes

### Step 3: Implement Merge Functionality (MEDIUM)
**Files**: `arkham_shard_entities/api.py`
- Complete merge endpoint logic
- Update mentions to canonical entity
- Handle edge cases (merging into self, etc.)
- Emit merge events

**Estimated time**: 1 hour

### Step 4: Test Integration with Parse Shard (MEDIUM)
**Testing**:
- Upload document via ingest
- Verify parse shard extracts entities
- Verify entities shard receives events
- Check entities appear in database and UI
- Test search and filtering
- Test entity merge workflow

**Estimated time**: 1 hour

## Overall Complexity: MEDIUM

**Total estimated time**: 4 hours

**Dependencies**:
- Parse shard must emit `parse.entity.extracted` events
- Frame database service (already available)
- Frame event bus (already available)
- Optional: Vectors service for merge suggestions (already handled)

**Risk areas**:
- Entity resolution logic (case sensitivity, whitespace handling)
- Parse shard may not be emitting entity events yet
- Duplicate entities if resolution fails
- Merge logic must be transactional to avoid data corruption
