"""
Parse Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime
from dataclasses import fields

from arkham_shard_parse.models import (
    # Enums
    EntityType,
    EntityConfidence,
    # Dataclasses
    EntityMention,
    Entity,
    EntityRelationship,
    DateMention,
    LocationMention,
    TextChunk,
    ParseResult,
    EntityLinkingResult,
)


class TestEntityTypeEnum:
    """Tests for EntityType enum."""

    def test_all_values_exist(self):
        """Verify all expected entity type values exist."""
        assert EntityType.PERSON.value == "PERSON"
        assert EntityType.ORGANIZATION.value == "ORG"
        assert EntityType.LOCATION.value == "GPE"
        assert EntityType.FACILITY.value == "FAC"
        assert EntityType.DATE.value == "DATE"
        assert EntityType.TIME.value == "TIME"
        assert EntityType.MONEY.value == "MONEY"
        assert EntityType.PERCENT.value == "PERCENT"
        assert EntityType.PRODUCT.value == "PRODUCT"
        assert EntityType.EVENT.value == "EVENT"
        assert EntityType.LAW.value == "LAW"
        assert EntityType.LANGUAGE.value == "LANGUAGE"
        assert EntityType.NORP.value == "NORP"
        assert EntityType.CARDINAL.value == "CARDINAL"
        assert EntityType.ORDINAL.value == "ORDINAL"
        assert EntityType.QUANTITY.value == "QUANTITY"
        assert EntityType.WORK_OF_ART.value == "WORK_OF_ART"
        assert EntityType.OTHER.value == "OTHER"

    def test_enum_count(self):
        """Verify total number of entity types."""
        assert len(EntityType) == 18


class TestEntityConfidenceEnum:
    """Tests for EntityConfidence enum."""

    def test_all_values_exist(self):
        """Verify all expected confidence values exist."""
        assert EntityConfidence.HIGH.value == "high"
        assert EntityConfidence.MEDIUM.value == "medium"
        assert EntityConfidence.LOW.value == "low"

    def test_enum_count(self):
        """Verify total number of confidence levels."""
        assert len(EntityConfidence) == 3


class TestEntityMentionDataclass:
    """Tests for EntityMention dataclass."""

    def test_minimal_creation(self):
        """Test creating entity mention with minimal fields."""
        mention = EntityMention(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=10,
            confidence=0.9,
        )
        assert mention.text == "John Smith"
        assert mention.entity_type == EntityType.PERSON
        assert mention.start_char == 0
        assert mention.end_char == 10
        assert mention.confidence == 0.9

    def test_full_creation(self):
        """Test creating entity mention with all fields."""
        mention = EntityMention(
            text="Apple Inc",
            entity_type=EntityType.ORGANIZATION,
            start_char=20,
            end_char=29,
            confidence=0.85,
            sentence="Apple Inc announced new products today.",
            source_doc_id="doc-123",
            source_chunk_id="chunk-456",
        )
        assert mention.sentence == "Apple Inc announced new products today."
        assert mention.source_doc_id == "doc-123"
        assert mention.source_chunk_id == "chunk-456"

    def test_confidence_level_high(self):
        """Test confidence_level property for high confidence."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.9,
        )
        assert mention.confidence_level == EntityConfidence.HIGH

    def test_confidence_level_high_boundary(self):
        """Test confidence_level at exactly 0.8 threshold."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.8,
        )
        assert mention.confidence_level == EntityConfidence.HIGH

    def test_confidence_level_medium(self):
        """Test confidence_level property for medium confidence."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.65,
        )
        assert mention.confidence_level == EntityConfidence.MEDIUM

    def test_confidence_level_medium_boundary(self):
        """Test confidence_level at exactly 0.5 threshold."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.5,
        )
        assert mention.confidence_level == EntityConfidence.MEDIUM

    def test_confidence_level_low(self):
        """Test confidence_level property for low confidence."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.3,
        )
        assert mention.confidence_level == EntityConfidence.LOW

    def test_default_values(self):
        """Test that default values are set correctly."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.9,
        )
        assert mention.sentence is None
        assert mention.source_doc_id is None
        assert mention.source_chunk_id is None


class TestEntityDataclass:
    """Tests for Entity dataclass."""

    def test_minimal_creation(self):
        """Test creating entity with minimal fields."""
        entity = Entity(
            id="ent-123",
            canonical_name="John Smith",
            entity_type=EntityType.PERSON,
        )
        assert entity.id == "ent-123"
        assert entity.canonical_name == "John Smith"
        assert entity.entity_type == EntityType.PERSON

    def test_full_creation(self):
        """Test creating entity with all fields."""
        now = datetime.utcnow()
        mention = EntityMention(
            text="John",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.9,
        )
        entity = Entity(
            id="ent-456",
            canonical_name="John Smith",
            entity_type=EntityType.PERSON,
            mentions=[mention],
            aliases=["John", "J. Smith", "Mr. Smith"],
            attributes={"title": "CEO", "age": 45},
            related_entities=["ent-789", "ent-012"],
            first_seen=now,
            last_seen=now,
            mention_count=10,
            confidence=0.95,
        )
        assert len(entity.mentions) == 1
        assert len(entity.aliases) == 3
        assert entity.attributes["title"] == "CEO"
        assert len(entity.related_entities) == 2
        assert entity.mention_count == 10
        assert entity.confidence == 0.95

    def test_default_values(self):
        """Test that default values are set correctly."""
        entity = Entity(
            id="ent-123",
            canonical_name="Test",
            entity_type=EntityType.PERSON,
        )
        assert entity.mentions == []
        assert entity.aliases == []
        assert entity.attributes == {}
        assert entity.related_entities == []
        assert entity.mention_count == 0
        assert entity.confidence == 1.0
        assert entity.first_seen is not None
        assert entity.last_seen is not None


class TestEntityRelationshipDataclass:
    """Tests for EntityRelationship dataclass."""

    def test_minimal_creation(self):
        """Test creating relationship with minimal fields."""
        relationship = EntityRelationship(
            source_entity_id="ent-123",
            target_entity_id="ent-456",
            relation_type="employment",
            confidence=0.8,
        )
        assert relationship.source_entity_id == "ent-123"
        assert relationship.target_entity_id == "ent-456"
        assert relationship.relation_type == "employment"
        assert relationship.confidence == 0.8

    def test_full_creation(self):
        """Test creating relationship with all fields."""
        now = datetime.utcnow()
        relationship = EntityRelationship(
            source_entity_id="ent-123",
            target_entity_id="ent-456",
            relation_type="ownership",
            confidence=0.9,
            evidence_text="Apple acquired Beats",
            source_doc_id="doc-789",
            extracted_at=now,
        )
        assert relationship.evidence_text == "Apple acquired Beats"
        assert relationship.source_doc_id == "doc-789"
        assert relationship.extracted_at == now

    def test_default_values(self):
        """Test that default values are set correctly."""
        relationship = EntityRelationship(
            source_entity_id="ent-123",
            target_entity_id="ent-456",
            relation_type="association",
            confidence=0.7,
        )
        assert relationship.evidence_text is None
        assert relationship.source_doc_id is None
        assert relationship.extracted_at is not None


class TestDateMentionDataclass:
    """Tests for DateMention dataclass."""

    def test_absolute_date(self):
        """Test creating an absolute date mention."""
        date = datetime(2024, 1, 15)
        mention = DateMention(
            text="January 15, 2024",
            normalized_date=date,
            date_type="absolute",
            confidence=0.9,
        )
        assert mention.text == "January 15, 2024"
        assert mention.normalized_date == date
        assert mention.date_type == "absolute"
        assert mention.confidence == 0.9

    def test_relative_date(self):
        """Test creating a relative date mention."""
        mention = DateMention(
            text="yesterday",
            normalized_date=None,
            date_type="relative",
            confidence=0.7,
        )
        assert mention.text == "yesterday"
        assert mention.normalized_date is None
        assert mention.date_type == "relative"

    def test_date_range(self):
        """Test creating a date range mention."""
        mention = DateMention(
            text="from Jan 1 to Jan 31",
            normalized_date=None,
            date_type="range",
            confidence=0.6,
            context="The event runs from Jan 1 to Jan 31.",
        )
        assert mention.date_type == "range"
        assert mention.context is not None

    def test_full_creation(self):
        """Test creating date mention with all fields."""
        date = datetime(2024, 6, 15)
        mention = DateMention(
            text="2024-06-15",
            normalized_date=date,
            date_type="absolute",
            confidence=0.95,
            context="The deadline is 2024-06-15.",
            start_char=16,
            end_char=26,
            source_doc_id="doc-123",
            source_chunk_id="chunk-456",
        )
        assert mention.start_char == 16
        assert mention.end_char == 26
        assert mention.source_doc_id == "doc-123"
        assert mention.source_chunk_id == "chunk-456"

    def test_default_values(self):
        """Test that default values are set correctly."""
        mention = DateMention(
            text="today",
            normalized_date=None,
            date_type="relative",
            confidence=0.7,
        )
        assert mention.context is None
        assert mention.start_char == 0
        assert mention.end_char == 0
        assert mention.source_doc_id is None
        assert mention.source_chunk_id is None


class TestLocationMentionDataclass:
    """Tests for LocationMention dataclass."""

    def test_minimal_creation(self):
        """Test creating location mention with minimal fields."""
        location = LocationMention(
            text="New York",
            location_type="city",
        )
        assert location.text == "New York"
        assert location.location_type == "city"

    def test_geocoded_location(self):
        """Test creating location with geocoding data."""
        location = LocationMention(
            text="San Francisco, CA",
            location_type="city",
            latitude=37.7749,
            longitude=-122.4194,
            country="United States",
            region="California",
            confidence=0.95,
        )
        assert location.latitude == 37.7749
        assert location.longitude == -122.4194
        assert location.country == "United States"
        assert location.region == "California"

    def test_country_location(self):
        """Test creating a country location."""
        location = LocationMention(
            text="France",
            location_type="country",
            country="France",
            confidence=0.99,
        )
        assert location.location_type == "country"
        assert location.country == "France"

    def test_address_location(self):
        """Test creating an address location."""
        location = LocationMention(
            text="123 Main Street, Boston, MA",
            location_type="address",
            source_doc_id="doc-123",
            start_char=50,
            end_char=77,
        )
        assert location.location_type == "address"
        assert location.source_doc_id == "doc-123"

    def test_default_values(self):
        """Test that default values are set correctly."""
        location = LocationMention(
            text="Unknown Place",
            location_type="city",
        )
        assert location.latitude is None
        assert location.longitude is None
        assert location.country is None
        assert location.region is None
        assert location.confidence == 1.0
        assert location.source_doc_id is None
        assert location.start_char == 0
        assert location.end_char == 0


class TestTextChunkDataclass:
    """Tests for TextChunk dataclass."""

    def test_minimal_creation(self):
        """Test creating text chunk with minimal fields."""
        chunk = TextChunk(
            id="chunk-123",
            text="This is a sample text chunk.",
            chunk_index=0,
            document_id="doc-456",
        )
        assert chunk.id == "chunk-123"
        assert chunk.text == "This is a sample text chunk."
        assert chunk.chunk_index == 0
        assert chunk.document_id == "doc-456"

    def test_full_creation(self):
        """Test creating text chunk with all fields."""
        entity = EntityMention(
            text="Apple",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=5,
            confidence=0.9,
        )
        date = DateMention(
            text="2024-01-15",
            normalized_date=datetime(2024, 1, 15),
            date_type="absolute",
            confidence=0.9,
        )
        location = LocationMention(
            text="Cupertino",
            location_type="city",
        )

        now = datetime.utcnow()
        chunk = TextChunk(
            id="chunk-456",
            text="Apple announced news from Cupertino on 2024-01-15.",
            chunk_index=5,
            document_id="doc-789",
            page_number=3,
            chunk_method="semantic",
            char_start=1000,
            char_end=1050,
            token_count=9,
            entities=[entity],
            dates=[date],
            locations=[location],
            created_at=now,
        )
        assert chunk.page_number == 3
        assert chunk.chunk_method == "semantic"
        assert chunk.char_start == 1000
        assert chunk.char_end == 1050
        assert chunk.token_count == 9
        assert len(chunk.entities) == 1
        assert len(chunk.dates) == 1
        assert len(chunk.locations) == 1

    def test_default_values(self):
        """Test that default values are set correctly."""
        chunk = TextChunk(
            id="chunk-123",
            text="Sample text",
            chunk_index=0,
            document_id="doc-456",
        )
        assert chunk.page_number is None
        assert chunk.chunk_method == "semantic"
        assert chunk.char_start == 0
        assert chunk.char_end == 0
        assert chunk.token_count == 0
        assert chunk.entities == []
        assert chunk.dates == []
        assert chunk.locations == []
        assert chunk.created_at is not None


class TestParseResultDataclass:
    """Tests for ParseResult dataclass."""

    def test_minimal_creation(self):
        """Test creating parse result with minimal fields."""
        result = ParseResult(document_id="doc-123")
        assert result.document_id == "doc-123"

    def test_full_creation(self):
        """Test creating parse result with all fields."""
        entity = EntityMention(
            text="Apple",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=5,
            confidence=0.9,
        )
        date = DateMention(
            text="2024-01-15",
            normalized_date=datetime(2024, 1, 15),
            date_type="absolute",
            confidence=0.9,
        )
        location = LocationMention(
            text="Cupertino",
            location_type="city",
        )
        relationship = EntityRelationship(
            source_entity_id="ent-1",
            target_entity_id="ent-2",
            relation_type="location",
            confidence=0.8,
        )
        chunk = TextChunk(
            id="chunk-1",
            text="Sample chunk",
            chunk_index=0,
            document_id="doc-123",
        )

        now = datetime.utcnow()
        result = ParseResult(
            document_id="doc-123",
            entities=[entity],
            dates=[date],
            locations=[location],
            relationships=[relationship],
            chunks=[chunk],
            total_entities=1,
            total_chunks=1,
            processing_time_ms=150.5,
            status="completed",
            error=None,
            parsed_at=now,
        )
        assert len(result.entities) == 1
        assert len(result.dates) == 1
        assert len(result.locations) == 1
        assert len(result.relationships) == 1
        assert len(result.chunks) == 1
        assert result.total_entities == 1
        assert result.total_chunks == 1
        assert result.processing_time_ms == 150.5
        assert result.status == "completed"

    def test_error_result(self):
        """Test creating a failed parse result."""
        result = ParseResult(
            document_id="doc-123",
            status="failed",
            error="Document not found",
        )
        assert result.status == "failed"
        assert result.error == "Document not found"

    def test_default_values(self):
        """Test that default values are set correctly."""
        result = ParseResult(document_id="doc-123")
        assert result.entities == []
        assert result.dates == []
        assert result.locations == []
        assert result.relationships == []
        assert result.chunks == []
        assert result.total_entities == 0
        assert result.total_chunks == 0
        assert result.processing_time_ms == 0.0
        assert result.status == "completed"
        assert result.error is None
        assert result.parsed_at is not None


class TestEntityLinkingResultDataclass:
    """Tests for EntityLinkingResult dataclass."""

    def test_exact_match(self):
        """Test entity linking with exact match."""
        mention = EntityMention(
            text="Apple Inc",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=9,
            confidence=0.9,
        )
        result = EntityLinkingResult(
            mention=mention,
            canonical_entity_id="ent-apple-123",
            confidence=1.0,
            reason="exact_match",
        )
        assert result.mention == mention
        assert result.canonical_entity_id == "ent-apple-123"
        assert result.confidence == 1.0
        assert result.reason == "exact_match"

    def test_fuzzy_match(self):
        """Test entity linking with fuzzy match."""
        mention = EntityMention(
            text="Apple",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=5,
            confidence=0.85,
        )
        result = EntityLinkingResult(
            mention=mention,
            canonical_entity_id="ent-apple-123",
            confidence=0.8,
            reason="fuzzy_match",
            alternatives=[
                ("ent-apple-456", 0.6),
                ("ent-applebees", 0.4),
            ],
        )
        assert result.confidence == 0.8
        assert result.reason == "fuzzy_match"
        assert len(result.alternatives) == 2

    def test_no_match(self):
        """Test entity linking with no match."""
        mention = EntityMention(
            text="Unknown Corp",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=12,
            confidence=0.7,
        )
        result = EntityLinkingResult(
            mention=mention,
            canonical_entity_id=None,
            confidence=0.0,
            reason="no_match",
        )
        assert result.canonical_entity_id is None
        assert result.confidence == 0.0
        assert result.reason == "no_match"

    def test_coreference_linking(self):
        """Test entity linking via coreference."""
        mention = EntityMention(
            text="the company",
            entity_type=EntityType.ORGANIZATION,
            start_char=50,
            end_char=61,
            confidence=0.6,
        )
        result = EntityLinkingResult(
            mention=mention,
            canonical_entity_id="ent-apple-123",
            confidence=0.7,
            reason="coreference",
        )
        assert result.reason == "coreference"

    def test_default_values(self):
        """Test that default values are set correctly."""
        mention = EntityMention(
            text="Test",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=4,
            confidence=0.9,
        )
        result = EntityLinkingResult(
            mention=mention,
            canonical_entity_id="ent-123",
            confidence=0.9,
        )
        assert result.reason == "exact_match"
        assert result.alternatives == []
