from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Cluster(Base):
    __tablename__ = "clusters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    label = Column(Integer, nullable=False)  # HDBSCAN label (-1 is noise)
    name = Column(String, nullable=True)  # Auto-generated name
    description = Column(Text, nullable=True)  # LLM generated summary
    size = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id"), nullable=True
    )  # Nullable for backward compatibility/default
    cluster_id = Column(Integer, ForeignKey("clusters.id"), nullable=True)
    title = Column(String, nullable=True)
    path = Column(String, nullable=False)
    source_path = Column(String, nullable=True)  # Original folder structure
    file_hash = Column(String, unique=True, index=True)  # Deduplication
    doc_type = Column(String, default="unknown")
    created_at = Column(DateTime, default=datetime.utcnow)
    tags = Column(String, default="")
    status = Column(String, default="pending")  # pending, processing, complete, failed
    num_pages = Column(Integer, default=0)


class MiniDoc(Base):
    __tablename__ = "minidocs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    minidoc_id = Column(String, unique=True, index=True)  # file_hash__part_N
    page_start = Column(Integer)
    page_end = Column(Integer)
    status = Column(String, default="pending_ocr")  # pending_ocr, ocr_done, parsed
    created_at = Column(DateTime, default=datetime.utcnow)


class PageOCR(Base):
    __tablename__ = "page_ocr"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_num = Column(Integer)
    checksum = Column(String)  # image checksum
    text = Column(Text)
    ocr_meta = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    # Unique constraint on (document_id, page_num) is recommended but we'll enforce in logic for now


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"))
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"))
    text = Column(String)
    label = Column(String)
    count = Column(Integer, default=1)


class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"))
    score = Column(Float)
    reason = Column(Text)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
