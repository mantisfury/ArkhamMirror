"""
Entity models for Frame.

These models define the schema for arkham_frame entities and relationships.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float,
    ForeignKey
)
from sqlalchemy.orm import relationship

from arkham_frame.models.base import Base, TimestampMixin


class CanonicalEntity(Base, TimestampMixin):
    """
    Unique real-world entities across all documents.

    Multiple entity mentions may refer to the same canonical entity.
    """
    __tablename__ = "canonical_entities"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String(500), nullable=False)
    label = Column(String(50), nullable=False)  # PERSON, ORG, GPE, DATE, etc.
    aliases = Column(Text)  # JSON list of variations
    total_mentions = Column(Integer, default=0)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Geospatial
    latitude = Column(Float)
    longitude = Column(Float)
    resolved_address = Column(String(500))

    # Relationships
    mentions = relationship("Entity", back_populates="canonical_entity")


class Entity(Base):
    """
    Individual entity mentions in documents.

    Links to canonical entity for deduplication.
    """
    __tablename__ = "entities"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("arkham_frame.documents.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(Integer, ForeignKey("arkham_frame.chunks.id", ondelete="SET NULL"))
    canonical_entity_id = Column(Integer, ForeignKey("arkham_frame.canonical_entities.id", ondelete="SET NULL"))
    text = Column(String(500))
    label = Column(String(50))
    count = Column(Integer, default=1)
    start_char = Column(Integer)
    end_char = Column(Integer)

    # Relationships
    document = relationship("Document", foreign_keys=[doc_id])
    chunk = relationship("Chunk", back_populates="entities")
    canonical_entity = relationship("CanonicalEntity", back_populates="mentions")


class EntityRelationship(Base, TimestampMixin):
    """
    Relationships between canonical entities.

    Based on co-occurrence or explicit relationship extraction.
    """
    __tablename__ = "entity_relationships"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    entity1_id = Column(Integer, ForeignKey("arkham_frame.canonical_entities.id", ondelete="CASCADE"), nullable=False)
    entity2_id = Column(Integer, ForeignKey("arkham_frame.canonical_entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(100), default="co-occurrence")
    strength = Column(Float, default=1.0)
    co_occurrence_count = Column(Integer, default=1)
    doc_id = Column(Integer, ForeignKey("arkham_frame.documents.id", ondelete="SET NULL"))

    # Relationships
    entity1 = relationship("CanonicalEntity", foreign_keys=[entity1_id])
    entity2 = relationship("CanonicalEntity", foreign_keys=[entity2_id])
