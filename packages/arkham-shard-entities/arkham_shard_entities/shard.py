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
            logger.warning("EntityService not available - entity management disabled")
        else:
            logger.info("Using Frame's EntityService for entity management")

        # Create database schema
        await self._create_schema()

        # Subscribe to events from parse shard
        if self._event_bus:
            await self._event_bus.subscribe("parse.entity.extracted", self._on_entity_extracted)
            await self._event_bus.subscribe("parse.relationships.extracted", self._on_relationships_extracted)
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
            await self._event_bus.unsubscribe("parse.entity.extracted", self._on_entity_extracted)
            await self._event_bus.unsubscribe("parse.relationships.extracted", self._on_relationships_extracted)

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

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY[
                    'arkham_entities',
                    'arkham_entity_mentions',
                    'arkham_entity_relationships'
                ];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_entities_tenant
            ON arkham_entities(tenant_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_entity_mentions_tenant
            ON arkham_entity_mentions(tenant_id)
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
            mention_count=row.get("mention_count", 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    # --- Entity Filtering ---

    # Minimum requirements for valid entities
    _MIN_ENTITY_LENGTH = 2
    _MIN_WORD_LENGTH_FOR_SINGLE_WORD = 3
    _MAX_ENTITY_LENGTH = 200

    def _is_valid_entity(self, entity_text: str, entity_type: str) -> bool:
        """
        Filter out garbage/noise entities that don't provide analytical value.

        Filters entities like "1", "24/7", single characters, common words,
        pure punctuation, etc. that clutter analysis.

        Args:
            entity_text: The entity text to validate
            entity_type: The entity type (PERSON, ORG, etc.)

        Returns:
            True if entity should be kept, False if it should be filtered out
        """
        import re

        # Basic length checks
        if len(entity_text) < self._MIN_ENTITY_LENGTH:
            return False
        if len(entity_text) > self._MAX_ENTITY_LENGTH:
            return False

        # Normalize for pattern matching
        text_lower = entity_text.lower().strip()

        # Garbage patterns that indicate noise entities
        garbage_patterns = [
            r"^\d+$",  # Pure numbers: "1", "24", "100"
            r"^\d+/\d+$",  # Fractions/ratios: "24/7", "1/2"
            r"^\d+:\d+$",  # Times: "10:30", "24:00"
            r"^\d+[.,]\d+$",  # Decimals: "1.5", "3,000"
            r"^\d+%$",  # Percentages: "50%"
            r"^[$]\d+",  # Currency: "$100"
            r"^\d+[$]",  # Currency: "100$"
            r"^.{1,2}$",  # Single or double characters
            r"^\d+(st|nd|rd|th)$",  # Ordinals: "1st", "2nd"
        ]

        for pattern in garbage_patterns:
            if re.match(pattern, text_lower, re.IGNORECASE):
                logger.debug(f"Filtered entity '{entity_text}' - matched garbage pattern")
                return False

        # Common noise words to filter
        noise_words = {
            # Articles and conjunctions
            "the", "a", "an", "and", "or", "but", "if", "then",
            # Be verbs
            "is", "are", "was", "were", "be", "been", "being",
            # Pronouns
            "this", "that", "these", "those", "it", "its",
            "he", "she", "they", "we", "you", "i", "my", "your", "his", "her",
            # Question words
            "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
            # Quantifiers
            "all", "any", "both", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only",
            # Time words
            "today", "tomorrow", "yesterday", "now", "then", "soon", "later",
            "always", "never",
            # Days
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            # Months (often extracted as entities incorrectly)
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            # Ordinals
            "first", "second", "third", "fourth", "fifth",
            "sixth", "seventh", "eighth", "ninth", "tenth",
            # Common abbreviations
            "etc", "vs", "mr", "mrs", "ms", "dr", "jr", "sr", "inc", "llc", "ltd", "corp",
        }

        if text_lower in noise_words:
            logger.debug(f"Filtered entity '{entity_text}' - common noise word")
            return False

        # Single word entities need to be substantial
        words = entity_text.split()
        if len(words) == 1:
            # Single word must be at least N characters
            if len(entity_text) < self._MIN_WORD_LENGTH_FOR_SINGLE_WORD:
                logger.debug(f"Filtered entity '{entity_text}' - single word too short")
                return False
            # Single word shouldn't be all digits
            if entity_text.isdigit():
                logger.debug(f"Filtered entity '{entity_text}' - pure numeric")
                return False
            # Filter generic terms for specific entity types
            if entity_type in ("PERSON", "ORG", "GPE", "ORGANIZATION"):
                generic_terms = {
                    "company", "group", "team", "organization", "department",
                    "person", "individual", "someone", "anyone", "everyone",
                    "city", "town", "country", "state", "place", "location",
                    "office", "building", "center", "centre", "area", "region",
                }
                if text_lower in generic_terms:
                    logger.debug(f"Filtered entity '{entity_text}' - generic term for {entity_type}")
                    return False

        # Filter entities that are mostly punctuation or special characters
        alpha_count = sum(1 for c in entity_text if c.isalpha())
        if alpha_count == 0 or (alpha_count / len(entity_text)) < 0.5:
            logger.debug(f"Filtered entity '{entity_text}' - low alphabetic ratio")
            return False

        # Entity passes all filters
        return True

    # --- Event Handlers ---

    async def _on_entity_extracted(self, event: dict):
        """
        Handle entity extraction event from parse shard.

        Populates arkham_entities and arkham_entity_mentions tables.
        Applies smart filtering to remove noise/garbage entities.

        Args:
            event: Event data with document_id and entities list
        """
        import uuid

        # EventBus wraps events with payload
        payload = event.get("payload", event)
        document_id = payload.get("document_id")
        entities = payload.get("entities", [])

        if not document_id or not entities:
            logger.debug(f"No document_id or entities in event: {event}")
            return

        if not self._db:
            logger.warning("Database not available for entity storage")
            return

        # Filter entities before processing
        original_count = len(entities)
        filtered_entities = [
            e for e in entities
            if self._is_valid_entity(e.get("text", "").strip(), e.get("entity_type", "OTHER"))
        ]
        filtered_count = original_count - len(filtered_entities)

        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count}/{original_count} noise entities for document {document_id}")

        logger.info(f"Processing {len(filtered_entities)} entities for document {document_id}")

        for entity_data in filtered_entities:
            try:
                entity_text = entity_data.get("text", "").strip()
                entity_type = entity_data.get("entity_type", "OTHER")

                if not entity_text:
                    continue

                # Check if entity already exists (case-insensitive match)
                existing = await self._db.fetch_one(
                    """
                    SELECT id, name, document_ids FROM arkham_entities
                    WHERE LOWER(name) = LOWER(:name) AND entity_type = :entity_type
                    """,
                    {"name": entity_text, "entity_type": entity_type}
                )

                if existing:
                    entity_id = existing["id"]
                    # Update document_ids if not already present
                    doc_ids = self._parse_jsonb(existing["document_ids"], [])
                    if document_id not in doc_ids:
                        doc_ids.append(document_id)
                        await self._db.execute(
                            """
                            UPDATE arkham_entities
                            SET document_ids = :doc_ids, mention_count = mention_count + 1, updated_at = CURRENT_TIMESTAMP
                            WHERE id = :id
                            """,
                            {"id": entity_id, "doc_ids": json.dumps(doc_ids)}
                        )
                else:
                    # Create new entity
                    entity_id = str(uuid.uuid4())
                    await self._db.execute(
                        """
                        INSERT INTO arkham_entities (id, name, entity_type, document_ids, mention_count, created_at, updated_at)
                        VALUES (:id, :name, :entity_type, :doc_ids, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        {
                            "id": entity_id,
                            "name": entity_text,
                            "entity_type": entity_type,
                            "doc_ids": json.dumps([document_id]),
                        }
                    )

                # Create mention record
                mention_id = str(uuid.uuid4())
                await self._db.execute(
                    """
                    INSERT INTO arkham_entity_mentions (id, entity_id, document_id, mention_text, confidence, start_offset, end_offset, created_at)
                    VALUES (:id, :entity_id, :doc_id, :text, :conf, :start, :end, CURRENT_TIMESTAMP)
                    """,
                    {
                        "id": mention_id,
                        "entity_id": entity_id,
                        "doc_id": document_id,
                        "text": entity_text,
                        "conf": entity_data.get("confidence", 0.85),
                        "start": entity_data.get("start_offset", 0),
                        "end": entity_data.get("end_offset", 0),
                    }
                )

            except Exception as e:
                logger.error(f"Failed to store entity '{entity_data.get('text', 'unknown')}': {e}")

        logger.info(f"Stored {len(entities)} entities and mentions for document {document_id}")

    async def _on_relationships_extracted(self, event: dict):
        """
        Handle relationship extraction event from parse shard.

        Populates arkham_entity_relationships table.

        Args:
            event: Event data with document_id and relationships list
        """
        import uuid

        # EventBus wraps events with payload
        payload = event.get("payload", event)
        document_id = payload.get("document_id")
        relationships = payload.get("relationships", [])

        if not document_id or not relationships:
            return

        if not self._db:
            logger.warning("Database not available for relationship storage")
            return

        logger.info(f"Processing {len(relationships)} relationships for document {document_id}")

        for rel_data in relationships:
            try:
                source_text = rel_data.get("source_entity", "").strip()
                target_text = rel_data.get("target_entity", "").strip()
                rel_type = rel_data.get("relation_type", "RELATED_TO")

                if not source_text or not target_text:
                    continue

                # Find source entity ID by name
                source_row = await self._db.fetch_one(
                    "SELECT id FROM arkham_entities WHERE LOWER(name) = LOWER(:name)",
                    {"name": source_text}
                )
                # Find target entity ID by name
                target_row = await self._db.fetch_one(
                    "SELECT id FROM arkham_entities WHERE LOWER(name) = LOWER(:name)",
                    {"name": target_text}
                )

                if not source_row or not target_row:
                    logger.debug(f"Could not find entities for relationship: {source_text} -> {target_text}")
                    continue

                source_id = source_row["id"]
                target_id = target_row["id"]

                # Check if relationship already exists
                existing = await self._db.fetch_one(
                    """
                    SELECT id FROM arkham_entity_relationships
                    WHERE source_id = :src AND target_id = :tgt AND relationship_type = :rel_type
                    """,
                    {"src": source_id, "tgt": target_id, "rel_type": rel_type}
                )

                if not existing:
                    rel_id = str(uuid.uuid4())
                    metadata = {"document_id": document_id, "evidence": rel_data.get("evidence_text")}
                    await self._db.execute(
                        """
                        INSERT INTO arkham_entity_relationships
                        (id, source_id, target_id, relationship_type, confidence, metadata, created_at, updated_at)
                        VALUES (:id, :src, :tgt, :rel_type, :conf, :meta, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        {
                            "id": rel_id,
                            "src": source_id,
                            "tgt": target_id,
                            "rel_type": rel_type,
                            "conf": rel_data.get("confidence", 0.5),
                            "meta": json.dumps(metadata),
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to store relationship: {e}")

        logger.info(f"Stored relationships for document {document_id}")

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

        Queries from shard's arkham_entities table which has aggregated
        entity data with mention_count.

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

        # Query from shard's arkham_entities table (has aggregated data with mention_count)
        query = "SELECT * FROM arkham_entities WHERE 1=1"
        params: Dict[str, Any] = {}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

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
        # Check cache first
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        # Use Frame's EntityService if available
        if self._entity_service:
            try:
                fe = await self._entity_service.get_entity(entity_id)
                entity = Entity(
                    id=fe.id,
                    name=fe.text,
                    entity_type=EntityType(fe.entity_type.value) if hasattr(fe.entity_type, 'value') else EntityType.OTHER,
                    canonical_id=fe.canonical_id,
                    aliases=[],
                    metadata=fe.metadata or {},
                    created_at=fe.created_at,
                    updated_at=fe.created_at,
                )
                self._entity_cache[entity_id] = entity
                return entity
            except Exception:
                return None

        # Fallback to direct DB query
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Build query with tenant filtering
        query = "SELECT * FROM arkham_entities WHERE id = :id"
        params: Dict[str, Any] = {"id": entity_id}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db.fetch_one(query, params)

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

        # Build query with tenant filtering
        query = """
            SELECT * FROM arkham_entity_mentions
            WHERE entity_id = :entity_id
        """
        params: Dict[str, Any] = {"entity_id": entity_id}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        query += " ORDER BY created_at DESC"

        rows = await self._db.fetch_all(query, params)

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
        # Use Frame's EntityService if available
        if self._entity_service:
            try:
                # Link source to target (marks source as merged)
                await self._entity_service.link_to_canonical(source_id, target_id)

                # Clear cache
                if source_id in self._entity_cache:
                    del self._entity_cache[source_id]
                if target_id in self._entity_cache:
                    del self._entity_cache[target_id]

                # Publish event
                if self._event_bus:
                    await self._event_bus.emit("entities.entity.merged", {
                        "source_id": source_id,
                        "target_id": target_id,
                    }, source="entities-shard")

                # Return updated canonical entity
                target = await self.get_entity(target_id)
                return {
                    "id": target.id,
                    "name": target.name,
                    "entity_type": target.entity_type.value,
                    "mention_count": 0,
                } if target else {}

            except Exception as e:
                logger.error(f"Failed to merge entities via EntityService: {e}")
                # Fall through to direct DB method

        # Fallback to direct DB query
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
            await self._event_bus.emit("entities.entity.merged", {
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
        # Use Frame's EntityService if available
        if self._entity_service:
            service_stats = await self._entity_service.get_stats()
            # Convert to expected format
            stats = service_stats.get("entities_by_type", {})
            stats["TOTAL"] = service_stats.get("total_entities", 0)
            return stats

        # Fallback to direct DB query
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        # Build query with tenant filtering
        query = """
            SELECT entity_type, COUNT(*) as count
            FROM arkham_entities
            WHERE canonical_id IS NULL
        """
        params: Dict[str, Any] = {}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        query += " GROUP BY entity_type ORDER BY count DESC"

        rows = await self._db.fetch_all(query, params)

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
            await self._event_bus.emit("entities.relationship.created", {
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

    async def list_relationships(
        self,
        offset: int = 0,
        limit: int = 50,
        relationship_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all relationships with optional filtering.

        Args:
            offset: Number of results to skip
            limit: Maximum number of results
            relationship_type: Filter by relationship type

        Returns:
            List of relationship dicts
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        query = """
            SELECT r.*,
                   s.name as source_name, s.entity_type as source_type,
                   t.name as target_name, t.entity_type as target_type
            FROM arkham_entity_relationships r
            LEFT JOIN arkham_entities s ON r.source_id = s.id
            LEFT JOIN arkham_entities t ON r.target_id = t.id
            WHERE 1=1
        """
        params: Dict[str, Any] = {}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND r.tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
            params["rel_type"] = relationship_type

        query += " ORDER BY r.created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)

        relationships = []
        for row in rows:
            rel = {
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relationship_type": row["relationship_type"],
                "confidence": row.get("confidence", 1.0),
                "metadata": self._parse_jsonb(row.get("metadata"), {}),
                "created_at": row.get("created_at"),
                "source_name": row.get("source_name"),
                "source_type": row.get("source_type"),
                "target_name": row.get("target_name"),
                "target_type": row.get("target_type"),
            }
            relationships.append(rel)

        return relationships

    async def get_entity_relationships(
        self,
        entity_id: str,
        direction: str = "both",
        relationship_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get relationships for a specific entity.

        Args:
            entity_id: Entity ID
            direction: 'outgoing', 'incoming', or 'both'
            relationship_type: Filter by relationship type

        Returns:
            List of relationship dicts
        """
        if not self._db:
            raise RuntimeError("Entities Shard not initialized")

        if direction == "outgoing":
            where_clause = "r.source_id = :entity_id"
        elif direction == "incoming":
            where_clause = "r.target_id = :entity_id"
        else:
            where_clause = "(r.source_id = :entity_id OR r.target_id = :entity_id)"

        query = f"""
            SELECT r.*,
                   s.name as source_name, s.entity_type as source_type,
                   t.name as target_name, t.entity_type as target_type
            FROM arkham_entity_relationships r
            LEFT JOIN arkham_entities s ON r.source_id = s.id
            LEFT JOIN arkham_entities t ON r.target_id = t.id
            WHERE {where_clause}
        """
        params: Dict[str, Any] = {"entity_id": entity_id}

        # Add tenant filtering if tenant context is available
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND r.tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
            params["rel_type"] = relationship_type

        query += " ORDER BY r.created_at DESC"

        rows = await self._db.fetch_all(query, params)

        relationships = []
        for row in rows:
            rel = {
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relationship_type": row["relationship_type"],
                "confidence": row.get("confidence", 1.0),
                "metadata": self._parse_jsonb(row.get("metadata"), {}),
                "created_at": row.get("created_at"),
                "source_name": row.get("source_name"),
                "source_type": row.get("source_type"),
                "target_name": row.get("target_name"),
                "target_type": row.get("target_type"),
            }
            relationships.append(rel)

        return relationships
