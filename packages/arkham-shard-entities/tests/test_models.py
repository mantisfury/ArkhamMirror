"""Tests for entities shard data models."""

import pytest
from datetime import datetime
from arkham_shard_entities.models import (
    EntityType,
    RelationshipType,
    Entity,
    EntityMention,
    EntityRelationship,
    EntityMergeCandidate,
)


class TestEntityType:
    """Test EntityType enum."""

    def test_entity_type_values(self):
        """Test all entity types have correct values."""
        assert EntityType.PERSON.value == "PERSON"
        assert EntityType.ORGANIZATION.value == "ORGANIZATION"
        assert EntityType.LOCATION.value == "LOCATION"
        assert EntityType.DATE.value == "DATE"
        assert EntityType.MONEY.value == "MONEY"
        assert EntityType.EVENT.value == "EVENT"
        assert EntityType.PRODUCT.value == "PRODUCT"
        assert EntityType.DOCUMENT.value == "DOCUMENT"
        assert EntityType.CONCEPT.value == "CONCEPT"
        assert EntityType.OTHER.value == "OTHER"

    def test_entity_type_count(self):
        """Test we have all expected entity types."""
        assert len(EntityType) == 10


class TestRelationshipType:
    """Test RelationshipType enum."""

    def test_relationship_type_values(self):
        """Test all relationship types have correct values."""
        assert RelationshipType.WORKS_FOR.value == "WORKS_FOR"
        assert RelationshipType.LOCATED_IN.value == "LOCATED_IN"
        assert RelationshipType.MEMBER_OF.value == "MEMBER_OF"
        assert RelationshipType.OWNS.value == "OWNS"
        assert RelationshipType.RELATED_TO.value == "RELATED_TO"
        assert RelationshipType.MENTIONED_WITH.value == "MENTIONED_WITH"

    def test_relationship_type_count(self):
        """Test we have all expected relationship types."""
        assert len(RelationshipType) == 6


class TestEntity:
    """Test Entity dataclass."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
        )
        assert entity.id == "test-id"
        assert entity.name == "John Doe"
        assert entity.entity_type == EntityType.PERSON
        assert entity.canonical_id is None
        assert entity.aliases == []
        assert entity.metadata == {}
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)

    def test_entity_with_aliases(self):
        """Test entity with aliases."""
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
            aliases=["Johnny", "J. Doe"],
        )
        assert len(entity.aliases) == 2
        assert "Johnny" in entity.aliases
        assert "J. Doe" in entity.aliases

    def test_entity_with_metadata(self):
        """Test entity with metadata."""
        metadata = {"age": 30, "occupation": "Engineer"}
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
            metadata=metadata,
        )
        assert entity.metadata["age"] == 30
        assert entity.metadata["occupation"] == "Engineer"

    def test_entity_canonical_reference(self):
        """Test entity with canonical reference."""
        entity = Entity(
            id="test-id",
            name="Johnny",
            entity_type=EntityType.PERSON,
            canonical_id="canonical-id",
        )
        assert entity.canonical_id == "canonical-id"

    def test_is_canonical_property(self):
        """Test is_canonical property."""
        # Canonical entity (no canonical_id)
        canonical = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
        )
        assert canonical.is_canonical is True

        # Non-canonical entity (has canonical_id)
        merged = Entity(
            id="test-id-2",
            name="Johnny",
            entity_type=EntityType.PERSON,
            canonical_id="test-id",
        )
        assert merged.is_canonical is False

    def test_display_name_no_aliases(self):
        """Test display_name with no aliases."""
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
        )
        assert entity.display_name == "John Doe"

    def test_display_name_with_aliases(self):
        """Test display_name with aliases."""
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
            aliases=["Johnny", "J. Doe"],
        )
        assert entity.display_name == "John Doe (Johnny, J. Doe)"

    def test_display_name_many_aliases(self):
        """Test display_name with many aliases (only shows first 2)."""
        entity = Entity(
            id="test-id",
            name="John Doe",
            entity_type=EntityType.PERSON,
            aliases=["Johnny", "J. Doe", "JD", "John"],
        )
        # Should only show first 2 aliases
        assert entity.display_name == "John Doe (Johnny, J. Doe)"


class TestEntityMention:
    """Test EntityMention dataclass."""

    def test_mention_creation(self):
        """Test basic mention creation."""
        mention = EntityMention(
            id="mention-id",
            entity_id="entity-id",
            document_id="doc-id",
            mention_text="John Doe",
        )
        assert mention.id == "mention-id"
        assert mention.entity_id == "entity-id"
        assert mention.document_id == "doc-id"
        assert mention.mention_text == "John Doe"
        assert mention.start_offset == 0
        assert mention.end_offset == 0
        assert mention.confidence == 1.0
        assert isinstance(mention.created_at, datetime)

    def test_mention_with_positions(self):
        """Test mention with document positions."""
        mention = EntityMention(
            id="mention-id",
            entity_id="entity-id",
            document_id="doc-id",
            mention_text="John Doe",
            start_offset=100,
            end_offset=108,
        )
        assert mention.start_offset == 100
        assert mention.end_offset == 108

    def test_mention_with_confidence(self):
        """Test mention with confidence score."""
        mention = EntityMention(
            id="mention-id",
            entity_id="entity-id",
            document_id="doc-id",
            mention_text="John Doe",
            confidence=0.85,
        )
        assert mention.confidence == 0.85


class TestEntityRelationship:
    """Test EntityRelationship dataclass."""

    def test_relationship_creation(self):
        """Test basic relationship creation."""
        rel = EntityRelationship(
            id="rel-id",
            source_id="person-id",
            target_id="org-id",
            relationship_type=RelationshipType.WORKS_FOR,
        )
        assert rel.id == "rel-id"
        assert rel.source_id == "person-id"
        assert rel.target_id == "org-id"
        assert rel.relationship_type == RelationshipType.WORKS_FOR
        assert rel.confidence == 1.0
        assert rel.metadata == {}
        assert isinstance(rel.created_at, datetime)
        assert isinstance(rel.updated_at, datetime)

    def test_relationship_with_confidence(self):
        """Test relationship with confidence score."""
        rel = EntityRelationship(
            id="rel-id",
            source_id="person-id",
            target_id="org-id",
            relationship_type=RelationshipType.WORKS_FOR,
            confidence=0.75,
        )
        assert rel.confidence == 0.75

    def test_relationship_with_metadata(self):
        """Test relationship with metadata."""
        metadata = {"start_date": "2020-01-01", "position": "Engineer"}
        rel = EntityRelationship(
            id="rel-id",
            source_id="person-id",
            target_id="org-id",
            relationship_type=RelationshipType.WORKS_FOR,
            metadata=metadata,
        )
        assert rel.metadata["start_date"] == "2020-01-01"
        assert rel.metadata["position"] == "Engineer"

    def test_is_bidirectional_mentioned_with(self):
        """Test is_bidirectional for MENTIONED_WITH."""
        rel = EntityRelationship(
            id="rel-id",
            source_id="entity-1",
            target_id="entity-2",
            relationship_type=RelationshipType.MENTIONED_WITH,
        )
        assert rel.is_bidirectional is True

    def test_is_bidirectional_directional_types(self):
        """Test is_bidirectional for directional relationships."""
        # WORKS_FOR is directional
        rel1 = EntityRelationship(
            id="rel-id",
            source_id="person-id",
            target_id="org-id",
            relationship_type=RelationshipType.WORKS_FOR,
        )
        assert rel1.is_bidirectional is False

        # LOCATED_IN is directional
        rel2 = EntityRelationship(
            id="rel-id",
            source_id="entity-id",
            target_id="location-id",
            relationship_type=RelationshipType.LOCATED_IN,
        )
        assert rel2.is_bidirectional is False


class TestEntityMergeCandidate:
    """Test EntityMergeCandidate dataclass."""

    def test_merge_candidate_creation(self):
        """Test basic merge candidate creation."""
        candidate = EntityMergeCandidate(
            entity_a_id="entity-1",
            entity_a_name="John Doe",
            entity_b_id="entity-2",
            entity_b_name="Johnny Doe",
            similarity_score=0.92,
        )
        assert candidate.entity_a_id == "entity-1"
        assert candidate.entity_a_name == "John Doe"
        assert candidate.entity_b_id == "entity-2"
        assert candidate.entity_b_name == "Johnny Doe"
        assert candidate.similarity_score == 0.92
        assert candidate.reason == ""
        assert candidate.common_mentions == 0
        assert candidate.common_documents == 0

    def test_merge_candidate_with_details(self):
        """Test merge candidate with reason and common data."""
        candidate = EntityMergeCandidate(
            entity_a_id="entity-1",
            entity_a_name="John Doe",
            entity_b_id="entity-2",
            entity_b_name="Johnny Doe",
            similarity_score=0.92,
            reason="Similar names, both PERSON type",
            common_mentions=5,
            common_documents=3,
        )
        assert candidate.reason == "Similar names, both PERSON type"
        assert candidate.common_mentions == 5
        assert candidate.common_documents == 3

    def test_merge_candidate_to_dict(self):
        """Test to_dict conversion."""
        candidate = EntityMergeCandidate(
            entity_a_id="entity-1",
            entity_a_name="John Doe",
            entity_b_id="entity-2",
            entity_b_name="Johnny Doe",
            similarity_score=0.92,
            reason="Similar names",
            common_mentions=5,
            common_documents=3,
        )
        result = candidate.to_dict()

        assert isinstance(result, dict)
        assert result["entity_a"]["id"] == "entity-1"
        assert result["entity_a"]["name"] == "John Doe"
        assert result["entity_b"]["id"] == "entity-2"
        assert result["entity_b"]["name"] == "Johnny Doe"
        assert result["similarity_score"] == 0.92
        assert result["reason"] == "Similar names"
        assert result["common_mentions"] == 5
        assert result["common_documents"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
