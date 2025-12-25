"""Data models for the Parse Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(Enum):
    """Entity types recognized by NER."""
    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "GPE"
    FACILITY = "FAC"
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    LAW = "LAW"
    LANGUAGE = "LANGUAGE"
    NORP = "NORP"  # Nationalities, religious/political groups
    CARDINAL = "CARDINAL"
    ORDINAL = "ORDINAL"
    QUANTITY = "QUANTITY"
    WORK_OF_ART = "WORK_OF_ART"
    OTHER = "OTHER"


class EntityConfidence(Enum):
    """Confidence level for entity extraction."""
    HIGH = "high"      # 0.8+
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"        # < 0.5


@dataclass
class EntityMention:
    """
    A single mention of an entity in text.

    Example: "Apple" in "Apple announced new products"
    """
    text: str
    entity_type: EntityType
    start_char: int
    end_char: int
    confidence: float

    # Context
    sentence: str | None = None

    # Metadata
    source_doc_id: str | None = None
    source_chunk_id: str | None = None

    @property
    def confidence_level(self) -> EntityConfidence:
        if self.confidence >= 0.8:
            return EntityConfidence.HIGH
        elif self.confidence >= 0.5:
            return EntityConfidence.MEDIUM
        return EntityConfidence.LOW


@dataclass
class Entity:
    """
    A canonical entity with all its mentions.

    Example: "Apple Inc." with mentions "Apple", "AAPL", "the company"
    """
    id: str
    canonical_name: str
    entity_type: EntityType
    mentions: list[EntityMention] = field(default_factory=list)

    # Attributes
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    # Relationships
    related_entities: list[str] = field(default_factory=list)

    # Metadata
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    mention_count: int = 0
    confidence: float = 1.0


@dataclass
class EntityRelationship:
    """Relationship between two entities."""
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float

    # Evidence
    evidence_text: str | None = None
    source_doc_id: str | None = None

    # Metadata
    extracted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DateMention:
    """A date or time reference extracted from text."""
    text: str
    normalized_date: datetime | None
    date_type: str  # absolute | relative | range
    confidence: float

    # Context
    context: str | None = None
    start_char: int = 0
    end_char: int = 0

    # Source
    source_doc_id: str | None = None
    source_chunk_id: str | None = None


@dataclass
class LocationMention:
    """A geographic location mention."""
    text: str
    location_type: str  # city | state | country | address

    # Geocoding
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    region: str | None = None

    # Confidence
    confidence: float = 1.0

    # Source
    source_doc_id: str | None = None
    start_char: int = 0
    end_char: int = 0


@dataclass
class TextChunk:
    """A chunk of text ready for embedding."""
    id: str
    text: str
    chunk_index: int

    # Source
    document_id: str
    page_number: int | None = None

    # Chunking metadata
    chunk_method: str = "semantic"  # semantic | fixed | sentence
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0

    # Extracted entities in this chunk
    entities: list[EntityMention] = field(default_factory=list)
    dates: list[DateMention] = field(default_factory=list)
    locations: list[LocationMention] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ParseResult:
    """Result of parsing a document."""
    document_id: str

    # Extracted data
    entities: list[EntityMention] = field(default_factory=list)
    dates: list[DateMention] = field(default_factory=list)
    locations: list[LocationMention] = field(default_factory=list)
    relationships: list[EntityRelationship] = field(default_factory=list)
    chunks: list[TextChunk] = field(default_factory=list)

    # Statistics
    total_entities: int = 0
    total_chunks: int = 0
    processing_time_ms: float = 0.0

    # Status
    status: str = "completed"
    error: str | None = None

    # Metadata
    parsed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EntityLinkingResult:
    """Result of linking entity mentions to canonical entities."""
    mention: EntityMention
    canonical_entity_id: str | None
    confidence: float

    # Why this linking was chosen
    reason: str = "exact_match"  # exact_match | fuzzy_match | context | coreference
    alternatives: list[tuple[str, float]] = field(default_factory=list)
