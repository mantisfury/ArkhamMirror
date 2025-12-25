"""
Document models for Frame.

These models define the schema for arkham_frame.documents and related tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, BigInteger,
    SmallInteger, ForeignKey
)
from sqlalchemy.orm import relationship

from arkham_frame.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """Project container for documents."""
    __tablename__ = "projects"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")  # active, archived, completed
    priority = Column(String(20), default="medium")  # high, medium, low
    tags = Column(Text)  # JSON list
    color = Column(String(20), default="#3b82f6")
    lead_investigator = Column(String(255))
    notes = Column(Text)

    # Relationships
    documents = relationship("Document", back_populates="project")


class Cluster(Base, TimestampMixin):
    """Document cluster for grouping related documents."""
    __tablename__ = "clusters"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("arkham_frame.projects.id"))
    label = Column(Integer, nullable=False)  # HDBSCAN label (-1 is noise)
    name = Column(String(255))
    description = Column(Text)  # LLM-generated summary
    size = Column(Integer, default=0)

    # Relationships
    project = relationship("Project")
    documents = relationship("Document", back_populates="cluster")


class Document(Base, TimestampMixin):
    """Main document entity."""
    __tablename__ = "documents"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("arkham_frame.projects.id"))
    cluster_id = Column(Integer, ForeignKey("arkham_frame.clusters.id"))
    title = Column(String(500))
    path = Column(String(1000), nullable=False)
    source_path = Column(String(1000))  # Original folder structure
    file_hash = Column(String(64), unique=True)  # SHA-256 for deduplication
    doc_type = Column(String(50), default="unknown")
    tags = Column(String(500), default="")
    status = Column(String(50), default="pending")  # pending, processing, complete, failed
    num_pages = Column(Integer, default=0)

    # PDF Metadata (forensic)
    pdf_author = Column(String(255))
    pdf_creator = Column(String(255))
    pdf_producer = Column(String(255))
    pdf_subject = Column(String(500))
    pdf_keywords = Column(String(500))
    pdf_creation_date = Column(DateTime)
    pdf_modification_date = Column(DateTime)
    pdf_version = Column(String(20))
    is_encrypted = Column(SmallInteger, default=0)
    file_size_bytes = Column(BigInteger)

    # Relationships
    project = relationship("Project", back_populates="documents")
    cluster = relationship("Cluster", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    page_ocr = relationship("PageOCR", back_populates="document", cascade="all, delete-orphan")
    minidocs = relationship("MiniDoc", back_populates="document", cascade="all, delete-orphan")


class MiniDoc(Base, TimestampMixin):
    """Document splitting tracking (for large documents split into parts)."""
    __tablename__ = "minidocs"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("arkham_frame.documents.id", ondelete="CASCADE"), nullable=False)
    minidoc_id = Column(String(255), unique=True)  # file_hash__part_N
    page_start = Column(Integer)
    page_end = Column(Integer)
    status = Column(String(50), default="pending_ocr")  # pending_ocr, ocr_done, parsed

    # Relationships
    document = relationship("Document", back_populates="minidocs")


class PageOCR(Base, TimestampMixin):
    """OCR results per page."""
    __tablename__ = "page_ocr"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("arkham_frame.documents.id", ondelete="CASCADE"), nullable=False)
    page_num = Column(Integer, nullable=False)
    checksum = Column(String(64))  # Image checksum
    text = Column(Text)
    ocr_meta = Column(Text)  # JSON metadata

    # Relationships
    document = relationship("Document", back_populates="page_ocr")


class Chunk(Base, TimestampMixin):
    """Text chunks for embedding and search."""
    __tablename__ = "chunks"
    __table_args__ = {"schema": "arkham_frame"}

    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("arkham_frame.documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    page_number = Column(Integer)  # For better context

    # Relationships
    document = relationship("Document", back_populates="chunks")
    entities = relationship("Entity", back_populates="chunk")
