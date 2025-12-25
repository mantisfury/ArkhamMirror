"""
Event models for Frame event bus.

Session-based persistence for debugging.
Truncated on Frame startup.
"""

from datetime import datetime
import uuid

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from arkham_frame.models.base import Base


class Event(Base):
    """
    Event bus event record.

    Stored for debugging during session.
    Truncated on Frame startup.
    """
    __tablename__ = "events"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(255), nullable=False)  # e.g., "document.processed"
    source = Column(String(255), nullable=False)  # Who emitted
    payload = Column(JSONB, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    sequence = Column(Integer, nullable=False)  # Monotonically increasing per source
    correlation_id = Column(UUID(as_uuid=True))
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShardRegistry(Base):
    """
    Registry of installed shards.
    """
    __tablename__ = "shard_registry"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)  # e.g., "arkham-shard-ach"
    version = Column(String(20), nullable=False)
    schema_name = Column(String(50), nullable=False)  # e.g., "ach"
    enabled = Column(Boolean, default=True)
    manifest = Column(JSONB, nullable=False)  # Full shard.yaml as JSON
    installed_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class IngestionError(Base):
    """
    Error tracking for document processing pipeline.
    """
    __tablename__ = "ingestion_errors"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer)  # Soft reference to documents
    chunk_id = Column(Integer)  # Soft reference to chunks
    stage = Column(String(50), nullable=False)  # ocr, chunking, embedding, entity, llm_enrich
    error_type = Column(String(100), nullable=False)  # timeout, parse_error, connection, validation
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    is_resolved = Column(Integer, default=0)  # 0 = unresolved, 1 = resolved
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchemaVersion(Base):
    """
    Schema versioning for migrations.
    """
    __tablename__ = "schema_version"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    version = Column(String(20), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)
