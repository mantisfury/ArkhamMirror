"""
EntityService - Entity extraction, canonical management, and relationships.

Entities are named things (people, places, organizations, etc.) extracted
from documents. Canonical entities provide deduplication and disambiguation.
"""

from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Standard entity types."""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    DATE = "DATE"
    MONEY = "MONEY"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    DOCUMENT = "DOCUMENT"
    CONCEPT = "CONCEPT"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    """Standard relationship types."""
    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    MEMBER_OF = "MEMBER_OF"
    OWNS = "OWNS"
    RELATED_TO = "RELATED_TO"
    MENTIONED_WITH = "MENTIONED_WITH"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    SAME_AS = "SAME_AS"
    PART_OF = "PART_OF"
    OTHER = "OTHER"


@dataclass
class Entity:
    """An extracted entity from a document."""
    id: str
    text: str
    entity_type: EntityType
    document_id: str
    chunk_id: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    confidence: float = 1.0
    canonical_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": self.confidence,
            "canonical_id": self.canonical_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        entity_type = data.get("entity_type", "OTHER")
        if isinstance(entity_type, str):
            try:
                entity_type = EntityType(entity_type)
            except ValueError:
                entity_type = EntityType.OTHER

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            id=data["id"],
            text=data["text"],
            entity_type=entity_type,
            document_id=data["document_id"],
            chunk_id=data.get("chunk_id"),
            start_offset=data.get("start_offset"),
            end_offset=data.get("end_offset"),
            confidence=data.get("confidence", 1.0),
            canonical_id=data.get("canonical_id"),
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.utcnow(),
        )


@dataclass
class CanonicalEntity:
    """A canonical (deduplicated) entity."""
    id: str
    name: str
    entity_type: EntityType
    aliases: List[str] = field(default_factory=list)
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type,
            "aliases": self.aliases,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalEntity":
        entity_type = data.get("entity_type", "OTHER")
        if isinstance(entity_type, str):
            try:
                entity_type = EntityType(entity_type)
            except ValueError:
                entity_type = EntityType.OTHER

        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data["id"],
            name=data["name"],
            entity_type=entity_type,
            aliases=data.get("aliases", []),
            description=data.get("description"),
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),
        )


@dataclass
class EntityRelationship:
    """A relationship between two entities."""
    id: str
    source_id: str  # Can be entity_id or canonical_id
    target_id: str  # Can be entity_id or canonical_id
    relationship_type: RelationshipType
    confidence: float = 1.0
    document_id: Optional[str] = None  # Source document if extracted
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value if isinstance(self.relationship_type, RelationshipType) else self.relationship_type,
            "confidence": self.confidence,
            "document_id": self.document_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityRelationship":
        rel_type = data.get("relationship_type", "OTHER")
        if isinstance(rel_type, str):
            try:
                rel_type = RelationshipType(rel_type)
            except ValueError:
                rel_type = RelationshipType.OTHER

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            relationship_type=rel_type,
            confidence=data.get("confidence", 1.0),
            document_id=data.get("document_id"),
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.utcnow(),
        )


@dataclass
class CoOccurrence:
    """Co-occurrence of two entities within a context window."""
    entity1_id: str
    entity2_id: str
    count: int
    documents: List[str]  # Document IDs where they co-occur
    contexts: List[str] = field(default_factory=list)  # Sample text contexts


class EntityError(Exception):
    """Base entity error."""
    pass


class EntityNotFoundError(EntityError):
    """Entity not found."""
    def __init__(self, entity_id: str):
        super().__init__(f"Entity not found: {entity_id}")
        self.entity_id = entity_id


class CanonicalNotFoundError(EntityError):
    """Canonical entity not found."""
    def __init__(self, canonical_id: str):
        super().__init__(f"Canonical entity not found: {canonical_id}")
        self.canonical_id = canonical_id


class RelationshipNotFoundError(EntityError):
    """Relationship not found."""
    def __init__(self, relationship_id: str):
        super().__init__(f"Relationship not found: {relationship_id}")
        self.relationship_id = relationship_id


class EntityService:
    """
    Entity service for extraction, storage, and relationship management.

    Tables:
        - arkham_frame.entities: Extracted entity mentions
        - arkham_frame.canonical_entities: Deduplicated canonical entities
        - arkham_frame.entity_relationships: Relationships between entities
    """

    def __init__(self, db=None, config=None):
        self.db = db
        self.config = config
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize entity tables."""
        if not self.db or not self.db._connected:
            logger.warning("Database not available, EntityService running in limited mode")
            self._initialized = True
            return

        try:
            from sqlalchemy import text

            with self.db._engine.connect() as conn:
                # Ensure schema exists
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS arkham_frame"))

                # Create entities table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS arkham_frame.entities (
                        id VARCHAR(36) PRIMARY KEY,
                        text TEXT NOT NULL,
                        entity_type VARCHAR(50) NOT NULL,
                        document_id VARCHAR(36) NOT NULL,
                        chunk_id VARCHAR(36),
                        start_offset INTEGER,
                        end_offset INTEGER,
                        confidence FLOAT DEFAULT 1.0,
                        canonical_id VARCHAR(36),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # Create canonical_entities table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS arkham_frame.canonical_entities (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(500) NOT NULL,
                        entity_type VARCHAR(50) NOT NULL,
                        aliases JSONB DEFAULT '[]',
                        description TEXT,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # Create entity_relationships table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS arkham_frame.entity_relationships (
                        id VARCHAR(36) PRIMARY KEY,
                        source_id VARCHAR(36) NOT NULL,
                        target_id VARCHAR(36) NOT NULL,
                        relationship_type VARCHAR(50) NOT NULL,
                        confidence FLOAT DEFAULT 1.0,
                        document_id VARCHAR(36),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # Create indexes
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_entities_document
                    ON arkham_frame.entities(document_id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_entities_type
                    ON arkham_frame.entities(entity_type)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_entities_canonical
                    ON arkham_frame.entities(canonical_id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_entities_text
                    ON arkham_frame.entities(text)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_canonical_name
                    ON arkham_frame.canonical_entities(name)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_canonical_type
                    ON arkham_frame.canonical_entities(entity_type)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_relationships_source
                    ON arkham_frame.entity_relationships(source_id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_relationships_target
                    ON arkham_frame.entity_relationships(target_id)
                """))

                conn.commit()

            self._initialized = True
            logger.info("EntityService initialized with database tables")

        except Exception as e:
            logger.error(f"Failed to initialize EntityService tables: {e}")
            self._initialized = True  # Continue in limited mode

    # =========================================================================
    # Entity CRUD
    # =========================================================================

    async def create_entity(
        self,
        text: str,
        entity_type: EntityType,
        document_id: str,
        chunk_id: Optional[str] = None,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
        confidence: float = 1.0,
        canonical_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        """Create a new entity."""
        entity = Entity(
            id=str(uuid.uuid4()),
            text=text,
            entity_type=entity_type,
            document_id=document_id,
            chunk_id=chunk_id,
            start_offset=start_offset,
            end_offset=end_offset,
            confidence=confidence,
            canonical_id=canonical_id,
            metadata=metadata or {},
        )

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text as sql_text
                import json

                with self.db._engine.connect() as conn:
                    conn.execute(sql_text("""
                        INSERT INTO arkham_frame.entities
                        (id, text, entity_type, document_id, chunk_id, start_offset,
                         end_offset, confidence, canonical_id, metadata, created_at)
                        VALUES (:id, :text, :entity_type, :document_id, :chunk_id,
                                :start_offset, :end_offset, :confidence, :canonical_id,
                                :metadata, :created_at)
                    """), {
                        "id": entity.id,
                        "text": entity.text,
                        "entity_type": entity.entity_type.value,
                        "document_id": entity.document_id,
                        "chunk_id": entity.chunk_id,
                        "start_offset": entity.start_offset,
                        "end_offset": entity.end_offset,
                        "confidence": entity.confidence,
                        "canonical_id": entity.canonical_id,
                        "metadata": json.dumps(entity.metadata),
                        "created_at": entity.created_at,
                    })
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to save entity to database: {e}")

        logger.debug(f"Created entity: {entity.id} ({entity.text})")
        return entity

    async def create_entities_batch(
        self,
        entities: List[Dict[str, Any]],
    ) -> List[Entity]:
        """Create multiple entities in batch."""
        created = []
        for entity_data in entities:
            entity_type = entity_data.get("entity_type", EntityType.OTHER)
            if isinstance(entity_type, str):
                try:
                    entity_type = EntityType(entity_type)
                except ValueError:
                    entity_type = EntityType.OTHER

            entity = await self.create_entity(
                text=entity_data["text"],
                entity_type=entity_type,
                document_id=entity_data["document_id"],
                chunk_id=entity_data.get("chunk_id"),
                start_offset=entity_data.get("start_offset"),
                end_offset=entity_data.get("end_offset"),
                confidence=entity_data.get("confidence", 1.0),
                canonical_id=entity_data.get("canonical_id"),
                metadata=entity_data.get("metadata"),
            )
            created.append(entity)

        logger.info(f"Created {len(created)} entities in batch")
        return created

    async def get_entity(self, entity_id: str) -> Entity:
        """Get an entity by ID."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT id, text, entity_type, document_id, chunk_id,
                               start_offset, end_offset, confidence, canonical_id,
                               metadata, created_at
                        FROM arkham_frame.entities
                        WHERE id = :id
                    """), {"id": entity_id})

                    row = result.fetchone()
                    if row:
                        metadata = row[9]
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        return Entity(
                            id=row[0],
                            text=row[1],
                            entity_type=EntityType(row[2]) if row[2] in [e.value for e in EntityType] else EntityType.OTHER,
                            document_id=row[3],
                            chunk_id=row[4],
                            start_offset=row[5],
                            end_offset=row[6],
                            confidence=row[7],
                            canonical_id=row[8],
                            metadata=metadata or {},
                            created_at=row[10],
                        )
            except Exception as e:
                logger.error(f"Failed to get entity from database: {e}")

        raise EntityNotFoundError(entity_id)

    async def update_entity(
        self,
        entity_id: str,
        updates: Dict[str, Any],
    ) -> Entity:
        """Update an entity."""
        entity = await self.get_entity(entity_id)

        # Apply updates
        if "text" in updates:
            entity.text = updates["text"]
        if "entity_type" in updates:
            entity_type = updates["entity_type"]
            if isinstance(entity_type, str):
                entity.entity_type = EntityType(entity_type)
            else:
                entity.entity_type = entity_type
        if "confidence" in updates:
            entity.confidence = updates["confidence"]
        if "canonical_id" in updates:
            entity.canonical_id = updates["canonical_id"]
        if "metadata" in updates:
            entity.metadata.update(updates["metadata"])

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE arkham_frame.entities
                        SET text = :text, entity_type = :entity_type,
                            confidence = :confidence, canonical_id = :canonical_id,
                            metadata = :metadata
                        WHERE id = :id
                    """), {
                        "id": entity.id,
                        "text": entity.text,
                        "entity_type": entity.entity_type.value,
                        "confidence": entity.confidence,
                        "canonical_id": entity.canonical_id,
                        "metadata": json.dumps(entity.metadata),
                    })
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to update entity in database: {e}")

        return entity

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        DELETE FROM arkham_frame.entities WHERE id = :id
                    """), {"id": entity_id})
                    conn.commit()
                    return result.rowcount > 0
            except Exception as e:
                logger.error(f"Failed to delete entity from database: {e}")
                return False
        return False

    async def list_entities(
        self,
        offset: int = 0,
        limit: int = 50,
        entity_type: Optional[EntityType] = None,
        document_id: Optional[str] = None,
        canonical_id: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> List[Entity]:
        """List entities with filters."""
        entities = []

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                query = """
                    SELECT id, text, entity_type, document_id, chunk_id,
                           start_offset, end_offset, confidence, canonical_id,
                           metadata, created_at
                    FROM arkham_frame.entities
                    WHERE 1=1
                """
                params = {"offset": offset, "limit": limit}

                if entity_type:
                    query += " AND entity_type = :entity_type"
                    params["entity_type"] = entity_type.value if isinstance(entity_type, EntityType) else entity_type
                if document_id:
                    query += " AND document_id = :document_id"
                    params["document_id"] = document_id
                if canonical_id:
                    query += " AND canonical_id = :canonical_id"
                    params["canonical_id"] = canonical_id
                if search_text:
                    query += " AND text ILIKE :search_text"
                    params["search_text"] = f"%{search_text}%"

                query += " ORDER BY created_at DESC OFFSET :offset LIMIT :limit"

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)

                    for row in result:
                        metadata = row[9]
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        entities.append(Entity(
                            id=row[0],
                            text=row[1],
                            entity_type=EntityType(row[2]) if row[2] in [e.value for e in EntityType] else EntityType.OTHER,
                            document_id=row[3],
                            chunk_id=row[4],
                            start_offset=row[5],
                            end_offset=row[6],
                            confidence=row[7],
                            canonical_id=row[8],
                            metadata=metadata or {},
                            created_at=row[10],
                        ))
            except Exception as e:
                logger.error(f"Failed to list entities from database: {e}")

        return entities

    async def count_entities(
        self,
        entity_type: Optional[EntityType] = None,
        document_id: Optional[str] = None,
    ) -> int:
        """Count entities with optional filters."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                query = "SELECT COUNT(*) FROM arkham_frame.entities WHERE 1=1"
                params = {}

                if entity_type:
                    query += " AND entity_type = :entity_type"
                    params["entity_type"] = entity_type.value if isinstance(entity_type, EntityType) else entity_type
                if document_id:
                    query += " AND document_id = :document_id"
                    params["document_id"] = document_id

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    return result.scalar() or 0
            except Exception as e:
                logger.error(f"Failed to count entities: {e}")
        return 0

    async def get_entities_for_document(self, document_id: str) -> List[Entity]:
        """Get all entities from a specific document."""
        return await self.list_entities(document_id=document_id, limit=10000)

    # =========================================================================
    # Canonical Entity Management
    # =========================================================================

    async def create_canonical(
        self,
        name: str,
        entity_type: EntityType,
        aliases: Optional[List[str]] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanonicalEntity:
        """Create a canonical entity."""
        canonical = CanonicalEntity(
            id=str(uuid.uuid4()),
            name=name,
            entity_type=entity_type,
            aliases=aliases or [],
            description=description,
            metadata=metadata or {},
        )

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO arkham_frame.canonical_entities
                        (id, name, entity_type, aliases, description, metadata,
                         created_at, updated_at)
                        VALUES (:id, :name, :entity_type, :aliases, :description,
                                :metadata, :created_at, :updated_at)
                    """), {
                        "id": canonical.id,
                        "name": canonical.name,
                        "entity_type": canonical.entity_type.value,
                        "aliases": json.dumps(canonical.aliases),
                        "description": canonical.description,
                        "metadata": json.dumps(canonical.metadata),
                        "created_at": canonical.created_at,
                        "updated_at": canonical.updated_at,
                    })
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to save canonical entity to database: {e}")

        logger.debug(f"Created canonical entity: {canonical.id} ({canonical.name})")
        return canonical

    async def get_canonical(self, canonical_id: str) -> CanonicalEntity:
        """Get a canonical entity by ID."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT id, name, entity_type, aliases, description,
                               metadata, created_at, updated_at
                        FROM arkham_frame.canonical_entities
                        WHERE id = :id
                    """), {"id": canonical_id})

                    row = result.fetchone()
                    if row:
                        aliases = row[3]
                        metadata = row[5]
                        if isinstance(aliases, str):
                            aliases = json.loads(aliases)
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        return CanonicalEntity(
                            id=row[0],
                            name=row[1],
                            entity_type=EntityType(row[2]) if row[2] in [e.value for e in EntityType] else EntityType.OTHER,
                            aliases=aliases or [],
                            description=row[4],
                            metadata=metadata or {},
                            created_at=row[6],
                            updated_at=row[7],
                        )
            except Exception as e:
                logger.error(f"Failed to get canonical entity from database: {e}")

        raise CanonicalNotFoundError(canonical_id)

    async def update_canonical(
        self,
        canonical_id: str,
        updates: Dict[str, Any],
    ) -> CanonicalEntity:
        """Update a canonical entity."""
        canonical = await self.get_canonical(canonical_id)

        if "name" in updates:
            canonical.name = updates["name"]
        if "entity_type" in updates:
            entity_type = updates["entity_type"]
            if isinstance(entity_type, str):
                canonical.entity_type = EntityType(entity_type)
            else:
                canonical.entity_type = entity_type
        if "aliases" in updates:
            canonical.aliases = updates["aliases"]
        if "description" in updates:
            canonical.description = updates["description"]
        if "metadata" in updates:
            canonical.metadata.update(updates["metadata"])

        canonical.updated_at = datetime.utcnow()

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE arkham_frame.canonical_entities
                        SET name = :name, entity_type = :entity_type,
                            aliases = :aliases, description = :description,
                            metadata = :metadata, updated_at = :updated_at
                        WHERE id = :id
                    """), {
                        "id": canonical.id,
                        "name": canonical.name,
                        "entity_type": canonical.entity_type.value,
                        "aliases": json.dumps(canonical.aliases),
                        "description": canonical.description,
                        "metadata": json.dumps(canonical.metadata),
                        "updated_at": canonical.updated_at,
                    })
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to update canonical entity in database: {e}")

        return canonical

    async def delete_canonical(self, canonical_id: str) -> bool:
        """Delete a canonical entity and unlink all entities."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                with self.db._engine.connect() as conn:
                    # Unlink entities first
                    conn.execute(text("""
                        UPDATE arkham_frame.entities
                        SET canonical_id = NULL
                        WHERE canonical_id = :canonical_id
                    """), {"canonical_id": canonical_id})

                    # Delete canonical
                    result = conn.execute(text("""
                        DELETE FROM arkham_frame.canonical_entities
                        WHERE id = :id
                    """), {"id": canonical_id})
                    conn.commit()
                    return result.rowcount > 0
            except Exception as e:
                logger.error(f"Failed to delete canonical entity: {e}")
                return False
        return False

    async def list_canonicals(
        self,
        offset: int = 0,
        limit: int = 50,
        entity_type: Optional[EntityType] = None,
        search_text: Optional[str] = None,
    ) -> List[CanonicalEntity]:
        """List canonical entities."""
        canonicals = []

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                query = """
                    SELECT id, name, entity_type, aliases, description,
                           metadata, created_at, updated_at
                    FROM arkham_frame.canonical_entities
                    WHERE 1=1
                """
                params = {"offset": offset, "limit": limit}

                if entity_type:
                    query += " AND entity_type = :entity_type"
                    params["entity_type"] = entity_type.value if isinstance(entity_type, EntityType) else entity_type
                if search_text:
                    query += " AND (name ILIKE :search_text OR :search_text = ANY(aliases))"
                    params["search_text"] = f"%{search_text}%"

                query += " ORDER BY name ASC OFFSET :offset LIMIT :limit"

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)

                    for row in result:
                        aliases = row[3]
                        metadata = row[5]
                        if isinstance(aliases, str):
                            aliases = json.loads(aliases)
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        canonicals.append(CanonicalEntity(
                            id=row[0],
                            name=row[1],
                            entity_type=EntityType(row[2]) if row[2] in [e.value for e in EntityType] else EntityType.OTHER,
                            aliases=aliases or [],
                            description=row[4],
                            metadata=metadata or {},
                            created_at=row[6],
                            updated_at=row[7],
                        ))
            except Exception as e:
                logger.error(f"Failed to list canonical entities: {e}")

        return canonicals

    async def link_to_canonical(
        self,
        entity_id: str,
        canonical_id: str,
    ) -> Entity:
        """Link an entity to a canonical entity."""
        # Verify canonical exists
        await self.get_canonical(canonical_id)

        # Update entity
        return await self.update_entity(entity_id, {"canonical_id": canonical_id})

    async def unlink_from_canonical(self, entity_id: str) -> Entity:
        """Unlink an entity from its canonical entity."""
        return await self.update_entity(entity_id, {"canonical_id": None})

    async def merge_canonicals(
        self,
        target_id: str,
        source_ids: List[str],
    ) -> CanonicalEntity:
        """
        Merge multiple canonical entities into one.

        All entities linked to source canonicals will be relinked to target.
        Source canonicals will be deleted.
        """
        target = await self.get_canonical(target_id)

        for source_id in source_ids:
            try:
                source = await self.get_canonical(source_id)

                # Merge aliases
                for alias in source.aliases:
                    if alias not in target.aliases:
                        target.aliases.append(alias)

                # Add source name as alias
                if source.name not in target.aliases and source.name != target.name:
                    target.aliases.append(source.name)

                # Relink all entities from source to target
                if self.db and self.db._connected:
                    from sqlalchemy import text
                    with self.db._engine.connect() as conn:
                        conn.execute(text("""
                            UPDATE arkham_frame.entities
                            SET canonical_id = :target_id
                            WHERE canonical_id = :source_id
                        """), {"target_id": target_id, "source_id": source_id})
                        conn.commit()

                # Delete source canonical
                await self.delete_canonical(source_id)

            except CanonicalNotFoundError:
                logger.warning(f"Source canonical not found during merge: {source_id}")

        # Save updated target
        return await self.update_canonical(target_id, {
            "aliases": target.aliases,
        })

    async def find_or_create_canonical(
        self,
        name: str,
        entity_type: EntityType,
    ) -> CanonicalEntity:
        """Find an existing canonical by name/alias or create new."""
        # Search by name
        canonicals = await self.list_canonicals(search_text=name, entity_type=entity_type, limit=1)
        if canonicals:
            return canonicals[0]

        # Create new
        return await self.create_canonical(name=name, entity_type=entity_type)

    # =========================================================================
    # Relationship Management
    # =========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        confidence: float = 1.0,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EntityRelationship:
        """Create a relationship between entities."""
        relationship = EntityRelationship(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            confidence=confidence,
            document_id=document_id,
            metadata=metadata or {},
        )

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO arkham_frame.entity_relationships
                        (id, source_id, target_id, relationship_type, confidence,
                         document_id, metadata, created_at)
                        VALUES (:id, :source_id, :target_id, :relationship_type,
                                :confidence, :document_id, :metadata, :created_at)
                    """), {
                        "id": relationship.id,
                        "source_id": relationship.source_id,
                        "target_id": relationship.target_id,
                        "relationship_type": relationship.relationship_type.value,
                        "confidence": relationship.confidence,
                        "document_id": relationship.document_id,
                        "metadata": json.dumps(relationship.metadata),
                        "created_at": relationship.created_at,
                    })
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to save relationship to database: {e}")

        logger.debug(f"Created relationship: {source_id} -> {target_id} ({relationship_type})")
        return relationship

    async def get_relationship(self, relationship_id: str) -> EntityRelationship:
        """Get a relationship by ID."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT id, source_id, target_id, relationship_type,
                               confidence, document_id, metadata, created_at
                        FROM arkham_frame.entity_relationships
                        WHERE id = :id
                    """), {"id": relationship_id})

                    row = result.fetchone()
                    if row:
                        metadata = row[6]
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        return EntityRelationship(
                            id=row[0],
                            source_id=row[1],
                            target_id=row[2],
                            relationship_type=RelationshipType(row[3]) if row[3] in [r.value for r in RelationshipType] else RelationshipType.OTHER,
                            confidence=row[4],
                            document_id=row[5],
                            metadata=metadata or {},
                            created_at=row[7],
                        )
            except Exception as e:
                logger.error(f"Failed to get relationship from database: {e}")

        raise RelationshipNotFoundError(relationship_id)

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        DELETE FROM arkham_frame.entity_relationships
                        WHERE id = :id
                    """), {"id": relationship_id})
                    conn.commit()
                    return result.rowcount > 0
            except Exception as e:
                logger.error(f"Failed to delete relationship: {e}")
                return False
        return False

    async def get_relationships(
        self,
        entity_id: str,
        direction: str = "both",  # "outgoing", "incoming", or "both"
        relationship_type: Optional[RelationshipType] = None,
    ) -> List[EntityRelationship]:
        """Get relationships for an entity."""
        relationships = []

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                if direction == "outgoing":
                    query = """
                        SELECT id, source_id, target_id, relationship_type,
                               confidence, document_id, metadata, created_at
                        FROM arkham_frame.entity_relationships
                        WHERE source_id = :entity_id
                    """
                elif direction == "incoming":
                    query = """
                        SELECT id, source_id, target_id, relationship_type,
                               confidence, document_id, metadata, created_at
                        FROM arkham_frame.entity_relationships
                        WHERE target_id = :entity_id
                    """
                else:  # both
                    query = """
                        SELECT id, source_id, target_id, relationship_type,
                               confidence, document_id, metadata, created_at
                        FROM arkham_frame.entity_relationships
                        WHERE source_id = :entity_id OR target_id = :entity_id
                    """

                params = {"entity_id": entity_id}

                if relationship_type:
                    query += " AND relationship_type = :rel_type"
                    params["rel_type"] = relationship_type.value if isinstance(relationship_type, RelationshipType) else relationship_type

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)

                    for row in result:
                        metadata = row[6]
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        relationships.append(EntityRelationship(
                            id=row[0],
                            source_id=row[1],
                            target_id=row[2],
                            relationship_type=RelationshipType(row[3]) if row[3] in [r.value for r in RelationshipType] else RelationshipType.OTHER,
                            confidence=row[4],
                            document_id=row[5],
                            metadata=metadata or {},
                            created_at=row[7],
                        ))
            except Exception as e:
                logger.error(f"Failed to get relationships: {e}")

        return relationships

    async def list_all_relationships(
        self,
        offset: int = 0,
        limit: int = 50,
        relationship_type: Optional[RelationshipType] = None,
    ) -> List[EntityRelationship]:
        """List all relationships with pagination."""
        relationships = []

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                query = """
                    SELECT id, source_id, target_id, relationship_type,
                           confidence, document_id, metadata, created_at
                    FROM arkham_frame.entity_relationships
                    WHERE 1=1
                """
                params = {"offset": offset, "limit": limit}

                if relationship_type:
                    query += " AND relationship_type = :rel_type"
                    params["rel_type"] = relationship_type.value if isinstance(relationship_type, RelationshipType) else relationship_type

                query += " ORDER BY created_at DESC OFFSET :offset LIMIT :limit"

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)

                    for row in result:
                        metadata = row[6]
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)

                        relationships.append(EntityRelationship(
                            id=row[0],
                            source_id=row[1],
                            target_id=row[2],
                            relationship_type=RelationshipType(row[3]) if row[3] in [r.value for r in RelationshipType] else RelationshipType.OTHER,
                            confidence=row[4],
                            document_id=row[5],
                            metadata=metadata or {},
                            created_at=row[7],
                        ))
            except Exception as e:
                logger.error(f"Failed to list all relationships: {e}")

        return relationships

    async def count_relationships(
        self,
        relationship_type: Optional[RelationshipType] = None,
    ) -> int:
        """Count relationships with optional type filter."""
        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                query = "SELECT COUNT(*) FROM arkham_frame.entity_relationships WHERE 1=1"
                params = {}

                if relationship_type:
                    query += " AND relationship_type = :rel_type"
                    params["rel_type"] = relationship_type.value if isinstance(relationship_type, RelationshipType) else relationship_type

                with self.db._engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    return result.scalar() or 0
            except Exception as e:
                logger.error(f"Failed to count relationships: {e}")
        return 0

    async def get_relationship_stats(self) -> Dict[str, Any]:
        """Get relationship statistics."""
        stats = {
            "total": 0,
            "by_type": {},
        }

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                with self.db._engine.connect() as conn:
                    # Total relationships
                    result = conn.execute(text("SELECT COUNT(*) FROM arkham_frame.entity_relationships"))
                    stats["total"] = result.scalar() or 0

                    # Relationships by type
                    result = conn.execute(text("""
                        SELECT relationship_type, COUNT(*)
                        FROM arkham_frame.entity_relationships
                        GROUP BY relationship_type
                    """))
                    for row in result:
                        stats["by_type"][row[0]] = row[1]

            except Exception as e:
                logger.error(f"Failed to get relationship stats: {e}")

        return stats

    # =========================================================================
    # Co-occurrence Analysis
    # =========================================================================

    async def get_cooccurrences(
        self,
        entity_id: str,
        limit: int = 20,
        min_count: int = 1,
    ) -> List[CoOccurrence]:
        """
        Get entities that co-occur with the given entity.

        Co-occurrence is defined as appearing in the same document or chunk.
        """
        cooccurrences = []

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text
                import json

                # Find co-occurring entities by document
                with self.db._engine.connect() as conn:
                    result = conn.execute(text("""
                        WITH target_docs AS (
                            SELECT DISTINCT document_id
                            FROM arkham_frame.entities
                            WHERE id = :entity_id
                        )
                        SELECT
                            e.id,
                            e.text,
                            COUNT(DISTINCT e.document_id) as doc_count,
                            array_agg(DISTINCT e.document_id) as documents
                        FROM arkham_frame.entities e
                        JOIN target_docs td ON e.document_id = td.document_id
                        WHERE e.id != :entity_id
                        GROUP BY e.id, e.text
                        HAVING COUNT(DISTINCT e.document_id) >= :min_count
                        ORDER BY doc_count DESC
                        LIMIT :limit
                    """), {
                        "entity_id": entity_id,
                        "min_count": min_count,
                        "limit": limit,
                    })

                    for row in result:
                        documents = row[3]
                        if isinstance(documents, str):
                            documents = json.loads(documents)

                        cooccurrences.append(CoOccurrence(
                            entity1_id=entity_id,
                            entity2_id=row[0],
                            count=row[2],
                            documents=documents or [],
                        ))
            except Exception as e:
                logger.error(f"Failed to get co-occurrences: {e}")

        return cooccurrences

    async def get_entity_network(
        self,
        entity_id: str,
        depth: int = 1,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """
        Get a network of related entities.

        Returns nodes and edges for graph visualization.
        """
        nodes = {}
        edges = []
        visited: Set[str] = set()

        async def expand_node(eid: str, current_depth: int):
            if eid in visited or current_depth > depth or len(nodes) >= max_nodes:
                return

            visited.add(eid)

            try:
                entity = await self.get_entity(eid)
                nodes[eid] = {
                    "id": eid,
                    "label": entity.text,
                    "type": entity.entity_type.value,
                }

                # Get relationships
                relationships = await self.get_relationships(eid)
                for rel in relationships:
                    edges.append({
                        "source": rel.source_id,
                        "target": rel.target_id,
                        "type": rel.relationship_type.value,
                    })

                    # Expand connected nodes
                    next_id = rel.target_id if rel.source_id == eid else rel.source_id
                    await expand_node(next_id, current_depth + 1)

            except EntityNotFoundError:
                pass

        await expand_node(entity_id, 0)

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get entity service statistics."""
        stats = {
            "total_entities": 0,
            "total_canonicals": 0,
            "total_relationships": 0,
            "entities_by_type": {},
            "linked_entities": 0,
        }

        if self.db and self.db._connected:
            try:
                from sqlalchemy import text

                with self.db._engine.connect() as conn:
                    # Total entities
                    result = conn.execute(text("SELECT COUNT(*) FROM arkham_frame.entities"))
                    stats["total_entities"] = result.scalar() or 0

                    # Total canonicals
                    result = conn.execute(text("SELECT COUNT(*) FROM arkham_frame.canonical_entities"))
                    stats["total_canonicals"] = result.scalar() or 0

                    # Total relationships
                    result = conn.execute(text("SELECT COUNT(*) FROM arkham_frame.entity_relationships"))
                    stats["total_relationships"] = result.scalar() or 0

                    # Entities by type
                    result = conn.execute(text("""
                        SELECT entity_type, COUNT(*)
                        FROM arkham_frame.entities
                        GROUP BY entity_type
                    """))
                    for row in result:
                        stats["entities_by_type"][row[0]] = row[1]

                    # Linked entities
                    result = conn.execute(text("""
                        SELECT COUNT(*)
                        FROM arkham_frame.entities
                        WHERE canonical_id IS NOT NULL
                    """))
                    stats["linked_entities"] = result.scalar() or 0

            except Exception as e:
                logger.error(f"Failed to get entity stats: {e}")

        return stats
