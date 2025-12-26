"""Entities Shard - Entity Browser and Management."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router

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

        logger.info("Entities Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Entities Shard...")

        # Unsubscribe from events
        if self._event_bus:
            # await self._event_bus.unsubscribe("parse.entity.created", self._on_entity_created)
            # await self._event_bus.unsubscribe("parse.entity.updated", self._on_entity_updated)
            pass

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
        - arkham_entities schema
        - entities table (entity records)
        - mentions table (entity mentions in documents)
        - relationships table (entity-to-entity relationships)
        """
        if not self._db:
            return

        # NOTE: This is a stub - actual implementation would create tables
        logger.info("Creating entities schema (stub)")

        # Example schema creation (not executed in blueprint):
        # await self._db.execute("""
        #     CREATE SCHEMA IF NOT EXISTS arkham_entities;
        #
        #     CREATE TABLE IF NOT EXISTS arkham_entities.entities (
        #         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        #         name TEXT NOT NULL,
        #         entity_type TEXT NOT NULL,
        #         canonical_id UUID REFERENCES arkham_entities.entities(id),
        #         aliases TEXT[] DEFAULT '{}',
        #         metadata JSONB DEFAULT '{}',
        #         created_at TIMESTAMPTZ DEFAULT NOW(),
        #         updated_at TIMESTAMPTZ DEFAULT NOW()
        #     );
        #
        #     CREATE TABLE IF NOT EXISTS arkham_entities.mentions (
        #         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        #         entity_id UUID REFERENCES arkham_entities.entities(id) ON DELETE CASCADE,
        #         document_id UUID,
        #         mention_text TEXT NOT NULL,
        #         confidence FLOAT DEFAULT 1.0,
        #         start_offset INT,
        #         end_offset INT,
        #         created_at TIMESTAMPTZ DEFAULT NOW()
        #     );
        #
        #     CREATE TABLE IF NOT EXISTS arkham_entities.relationships (
        #         id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        #         source_id UUID REFERENCES arkham_entities.entities(id) ON DELETE CASCADE,
        #         target_id UUID REFERENCES arkham_entities.entities(id) ON DELETE CASCADE,
        #         relationship_type TEXT NOT NULL,
        #         confidence FLOAT DEFAULT 1.0,
        #         metadata JSONB DEFAULT '{}',
        #         created_at TIMESTAMPTZ DEFAULT NOW(),
        #         updated_at TIMESTAMPTZ DEFAULT NOW()
        #     );
        #
        #     CREATE INDEX IF NOT EXISTS idx_entities_type ON arkham_entities.entities(entity_type);
        #     CREATE INDEX IF NOT EXISTS idx_entities_canonical ON arkham_entities.entities(canonical_id);
        #     CREATE INDEX IF NOT EXISTS idx_mentions_entity ON arkham_entities.mentions(entity_id);
        #     CREATE INDEX IF NOT EXISTS idx_mentions_document ON arkham_entities.mentions(document_id);
        #     CREATE INDEX IF NOT EXISTS idx_relationships_source ON arkham_entities.relationships(source_id);
        #     CREATE INDEX IF NOT EXISTS idx_relationships_target ON arkham_entities.relationships(target_id);
        # """)

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

    async def get_entity(self, entity_id: str) -> dict | None:
        """
        Public method to get an entity by ID.

        Args:
            entity_id: Entity UUID

        Returns:
            Entity dict or None if not found
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Stub: Would query database
        logger.debug(f"Getting entity: {entity_id}")
        return None

    async def get_entity_mentions(self, entity_id: str) -> list[dict]:
        """
        Public method to get all mentions for an entity.

        Args:
            entity_id: Entity UUID

        Returns:
            List of mention dicts
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Stub: Would query mentions table
        logger.debug(f"Getting mentions for entity: {entity_id}")
        return []

    async def merge_entities(
        self, entity_ids: list[str], canonical_id: str, canonical_name: str | None = None
    ) -> dict:
        """
        Public method to merge duplicate entities.

        Args:
            entity_ids: List of entity IDs to merge
            canonical_id: ID of the canonical entity to keep
            canonical_name: Optional new name for canonical entity

        Returns:
            Merged entity dict
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Stub: Would perform merge operation
        logger.debug(f"Merging entities {entity_ids} into {canonical_id}")

        # Would publish event: entities.entity.merged
        if self._event_bus:
            # await self._event_bus.emit(
            #     "entities.entity.merged",
            #     {
            #         "canonical_id": canonical_id,
            #         "merged_ids": entity_ids,
            #         "canonical_name": canonical_name,
            #     },
            #     source=self.name,
            # )
            pass

        return {}

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> dict:
        """
        Public method to create a relationship between entities.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relationship_type: Type of relationship (WORKS_FOR, LOCATED_IN, etc.)
            confidence: Confidence score (0.0-1.0)
            metadata: Additional relationship metadata

        Returns:
            Created relationship dict
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Stub: Would create relationship in database
        logger.debug(f"Creating relationship: {source_id} -{relationship_type}-> {target_id}")

        # Would publish event: entities.relationship.created
        if self._event_bus:
            # await self._event_bus.emit(
            #     "entities.relationship.created",
            #     {
            #         "source_id": source_id,
            #         "target_id": target_id,
            #         "relationship_type": relationship_type,
            #     },
            #     source=self.name,
            # )
            pass

        return {}
