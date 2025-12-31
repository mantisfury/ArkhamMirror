"""Data models for the Entities Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(Enum):
    """Supported entity types."""

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


class RelationshipType(Enum):
    """Supported relationship types between entities."""

    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    MEMBER_OF = "MEMBER_OF"
    OWNS = "OWNS"
    RELATED_TO = "RELATED_TO"
    MENTIONED_WITH = "MENTIONED_WITH"


@dataclass
class Entity:
    """An entity extracted from documents."""

    id: str
    name: str
    entity_type: EntityType

    # Canonical entity reference (if this is a duplicate)
    canonical_id: str | None = None

    # Alternative names
    aliases: list[str] = field(default_factory=list)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Mention count - how many times this entity appears across documents
    mention_count: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_canonical(self) -> bool:
        """Check if this is a canonical entity (not merged)."""
        return self.canonical_id is None

    @property
    def display_name(self) -> str:
        """Get display name with aliases."""
        if self.aliases:
            return f"{self.name} ({', '.join(self.aliases[:2])})"
        return self.name


@dataclass
class EntityMention:
    """A mention of an entity in a document."""

    id: str
    entity_id: str
    document_id: str
    mention_text: str

    # Position in document
    start_offset: int = 0
    end_offset: int = 0

    # Confidence of extraction
    confidence: float = 1.0

    # Timestamp
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EntityRelationship:
    """A relationship between two entities."""

    id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType

    # Confidence of relationship
    confidence: float = 1.0

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Mention count - how many times this entity appears across documents
    mention_count: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_bidirectional(self) -> bool:
        """Check if relationship type is bidirectional."""
        # Most relationships are directional except MENTIONED_WITH
        return self.relationship_type == RelationshipType.MENTIONED_WITH


@dataclass
class EntityMergeCandidate:
    """A candidate pair of entities for merging."""

    entity_a_id: str
    entity_a_name: str
    entity_b_id: str
    entity_b_name: str

    # Similarity score (0.0 to 1.0)
    similarity_score: float

    # Reason for suggestion
    reason: str = ""

    # Common mentions or documents
    common_mentions: int = 0
    common_documents: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entity_a": {"id": self.entity_a_id, "name": self.entity_a_name},
            "entity_b": {"id": self.entity_b_id, "name": self.entity_b_name},
            "similarity_score": self.similarity_score,
            "reason": self.reason,
            "common_mentions": self.common_mentions,
            "common_documents": self.common_documents,
        }
