"""Entities Shard - Entity Browser and Management."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .models import Entity, EntityType

logger = logging.getLogger(__name__)


class EntitiesShard(ArkhamShard):
    """
    Entity browser and management shard for ArkhamFrame.

    Provides comprehensive entity management including:
    - Entity browsing with type filtering
    - Entity detail views with mention tracking
    - Duplicate entity merging
    - Entity relationship management
    - Canonical entity resolution

    Handles:
    - Entity CRUD operations
    - Merge duplicate entities into canonical form
    - Create and manage relationships between entities
    - Track entity mentions across documents
    - Integration with parse shard for new entities

    Events Published:
        - entities.entity.viewed
        - entities.entity.merged
        - entities.entity.edited
        - entities.relationship.created
        - entities.relationship.deleted

    Events Subscribed:
        - parse.entity.created (from parse shard)
        - parse.entity.updated
    """

    name = "entities"
    version = "0.1.0"
    description = "Entity browser with merge/link/edit capabilities for entity resolution workflow"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self._frame = None
        self._db = None
        self._event_bus = None
        self._vectors_service = None
        self._entity_service = None

        # Cache for entities
        self._entity_cache: Dict[str, Entity] = {}

    async def initialize(self, frame) -> None:
        """
        Initialize the Entities shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Entities Shard...")

        # Get required services
        self._db = frame.get_service("database")
        self._event_bus = frame.get_service("events")

        if not self._db:
            raise RuntimeError("Entities Shard: Database service required")

        # Get optional services
        self._vectors_service = frame.get_service("vectors")
        self._entity_service = frame.get_service("entities")

        if not self._vectors_service:
            logger.warning("Vectors service not available - merge suggestions disabled")

        if not self._entity_service:
            logger.info("EntityService not available - using basic entity management")

        # Create database schema
        await self._create_schema()

        # Subscribe to events from parse shard
        if self._event_bus:
            # Subscribe to entity extraction events from parse shard
            # await self._event_bus.subscribe("parse.entity.created", self._on_entity_created)
            # await self._event_bus.subscribe("parse.entity.updated", self._on_entity_updated)
            logger.info("Subscribed to parse shard entity events")

        # Initialize API with our services
        init_api(
            db=self._db,
            event_bus=self._event_bus,
            vectors_service=self._vectors_service,
            entity_service=self._entity_service,
        )

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.entities_shard = self

        logger.info("Entities Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Entities Shard...")

        # Unsubscribe from events
        if self._event_bus:
            # await self._event_bus.unsubscribe("parse.entity.created", self._on_entity_created)
            # await self._event_bus.unsubscribe("parse.entity.updated", self._on_entity_updated)
            pass

        # Clear caches
        self._entity_cache.clear()

        # Clear service references
        self._db = None
        self._event_bus = None
        self._vectors_service = None
        self._entity_service = None

        logger.info("Entities Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _create_schema(self) -> None:
        """
        Create database schema for entities.

        Creates:
        - entities table (entity records)
        - mentions table (entity mentions in documents)
        - relationships table (entity-to-entity relationships)
        """
        if not self._db:
            return

        # Create entities table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                canonical_id TEXT,
                aliases JSONB DEFAULT '[]',
                metadata JSONB DEFAULT '{}',
                mention_count INTEGER DEFAULT 0,
                document_ids JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create mentions table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_entity_mentions (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                mention_text TEXT NOT NULL,
                confidence FLOAT DEFAULT 1.0,
                start_offset INTEGER DEFAULT 0,
                end_offset INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create relationships table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_entity_relationships (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                confidence FLOAT DEFAULT 1.0,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_type
            ON arkham_entities(entity_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_name
            ON arkham_entities(name)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_canonical
            ON arkham_entities(canonical_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_mention_count
            ON arkham_entities(mention_count DESC)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentions_entity
            ON arkham_entity_mentions(entity_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentions_document
            ON arkham_entity_mentions(document_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_source
            ON arkham_entity_relationships(source_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_target
            ON arkham_entity_relationships(target_id)
        """)

        logger.info("Entities database schema created")

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default

    def _row_to_entity(self, row: Dict[str, Any]) -> Entity:
        """Convert database row to Entity object."""
        # Parse JSONB fields
        aliases = self._parse_jsonb(row.get("aliases"), [])
        metadata = self._parse_jsonb(row.get("metadata"), {})

        # Parse entity type
        entity_type_str = row.get("entity_type", "OTHER")
        try:
            entity_type = EntityType(entity_type_str)
        except ValueError:
            entity_type = EntityType.OTHER

        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=entity_type,
            canonical_id=row.get("canonical_id"),
            aliases=aliases,
            metadata=metadata,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    # --- Event Handlers (stubs) ---

    async def _on_entity_created(self, event: dict):
        """
        Handle entity created event from parse shard.

        Args:
            event: Event data containing entity information
        """
        # Stub: Would process new entity from parse shard
        logger.debug(f"Entity created event received: {event}")
        pass

    async def _on_entity_updated(self, event: dict):
        """
        Handle entity updated event from parse shard.

        Args:
            event: Event data containing updated entity information
        """
        # Stub: Would update entity information
        logger.debug(f"Entity updated event received: {event}")
        pass

    # --- Public API for other shards (via Frame) ---

    async def list_entities(
        self,
        search: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        show_merged: bool = False
    ) -> List[Entity]:
        """
        List entities with optional filtering.

        Args:
            search: Search query for entity name
            entity_type: Filter by entity type
            limit: Maximum number of results
            offset: Number of results to skip
            show_merged: Include merged entities

        Returns:
            List of Entity objects
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Build query with filters
        query = "SELECT * FROM arkham_entities WHERE 1=1"
        params: Dict[str, Any] = {}

        # Filter out merged entities by default
        if not show_merged:
            query += " AND canonical_id IS NULL"

        # Filter by entity type
        if entity_type:
            query += " AND entity_type = :entity_type"
            params["entity_type"] = entity_type

        # Search by name
        if search:
            query += " AND name ILIKE :search"
            params["search"] = f"%{search}%"

        # Order and limit
        query += " ORDER BY mention_count DESC, name ASC"
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)

        entities = [self._row_to_entity(row) for row in rows]

        # Update cache
        for entity in entities:
            self._entity_cache[entity.id] = entity

        return entities

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """
        Public method to get an entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity object or None if not found
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Check cache first
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        # Query database
        row = await self._db.fetch_one(
            "SELECT * FROM arkham_entities WHERE id = :id",
            {"id": entity_id}
        )

        if row:
            entity = self._row_to_entity(row)
            self._entity_cache[entity_id] = entity
            return entity

        return None

    async def get_entity_mentions(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Public method to get all mentions for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of mention dicts
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_entity_mentions
            WHERE entity_id = :entity_id
            ORDER BY created_at DESC
            """,
            {"entity_id": entity_id}
        )

        mentions = []
        for row in rows:
            mentions.append({
                "id": row["id"],
                "entity_id": row["entity_id"],
                "document_id": row["document_id"],
                "mention_text": row["mention_text"],
                "confidence": row.get("confidence", 1.0),
                "start_offset": row.get("start_offset", 0),
                "end_offset": row.get("end_offset", 0),
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            })

        return mentions

    async def merge_entities(
        self, source_id: str, target_id: str
    ) -> Dict[str, Any]:
        """
        Merge source entity into target entity.

        Args:
            source_id: ID of entity to merge (will be marked as merged)
            target_id: ID of canonical entity to merge into

        Returns:
            Updated canonical entity dict
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Mark source entity as merged into target
        await self._db.execute(
            """
            UPDATE arkham_entities
            SET canonical_id = :target_id, updated_at = :updated_at
            WHERE id = :source_id
            """,
            {
                "source_id": source_id,
                "target_id": target_id,
                "updated_at": datetime.utcnow(),
            }
        )

        # Update mentions to point to canonical entity
        await self._db.execute(
            """
            UPDATE arkham_entity_mentions
            SET entity_id = :target_id
            WHERE entity_id = :source_id
            """,
            {"source_id": source_id, "target_id": target_id}
        )

        # Recalculate mention count for target
        count_row = await self._db.fetch_one(
            """
            SELECT COUNT(*) as count FROM arkham_entity_mentions
            WHERE entity_id = :target_id
            """,
            {"target_id": target_id}
        )
        mention_count = count_row["count"] if count_row else 0

        await self._db.execute(
            """
            UPDATE arkham_entities
            SET mention_count = :count, updated_at = :updated_at
            WHERE id = :target_id
            """,
            {"target_id": target_id, "count": mention_count, "updated_at": datetime.utcnow()}
        )

        # Clear cache
        if source_id in self._entity_cache:
            del self._entity_cache[source_id]
        if target_id in self._entity_cache:
            del self._entity_cache[target_id]

        # Publish event
        if self._event_bus:
            await self._event_bus.publish("entities.entity.merged", {
                "source_id": source_id,
                "target_id": target_id,
                "mention_count": mention_count,
            })

        # Return updated canonical entity
        target = await self.get_entity(target_id)
        return {
            "id": target.id,
            "name": target.name,
            "entity_type": target.entity_type.value,
            "mention_count": mention_count,
        } if target else {}

    async def get_entity_stats(self) -> Dict[str, Any]:
        """
        Get entity statistics by type.

        Returns:
            Dict with counts by entity type
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        rows = await self._db.fetch_all(
            """
            SELECT entity_type, COUNT(*) as count
            FROM arkham_entities
            WHERE canonical_id IS NULL
            GROUP BY entity_type
            ORDER BY count DESC
            """
        )

        stats = {}
        total = 0
        for row in rows:
            entity_type = row["entity_type"]
            count = row["count"]
            stats[entity_type] = count
            total += count

        stats["TOTAL"] = total
        return stats

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a relationship between entities.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relationship_type: Type of relationship
            confidence: Confidence score (0.0-1.0)
            metadata: Additional relationship metadata

        Returns:
            Created relationship dict
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        import uuid
        relationship_id = str(uuid.uuid4())

        await self._db.execute(
            """
            INSERT INTO arkham_entity_relationships
            (id, source_id, target_id, relationship_type, confidence, metadata)
            VALUES (:id, :source_id, :target_id, :relationship_type, :confidence, :metadata)
            """,
            {
                "id": relationship_id,
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                "confidence": confidence,
                "metadata": json.dumps(metadata or {}),
            }
        )

        # Publish event
        if self._event_bus:
            await self._event_bus.publish("entities.relationship.created", {
                "relationship_id": relationship_id,
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
            })

        return {
            "id": relationship_id,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "confidence": confidence,
            "metadata": metadata or {},
        }
