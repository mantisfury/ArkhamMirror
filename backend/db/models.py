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

    # PDF Metadata (forensic information)
    pdf_author = Column(String, nullable=True)
    pdf_creator = Column(String, nullable=True)  # Application that created original
    pdf_producer = Column(String, nullable=True)  # PDF generation software
    pdf_subject = Column(String, nullable=True)
    pdf_keywords = Column(String, nullable=True)
    pdf_creation_date = Column(DateTime, nullable=True)
    pdf_modification_date = Column(DateTime, nullable=True)
    pdf_version = Column(String, nullable=True)
    is_encrypted = Column(Integer, default=0)  # 0 = false, 1 = true
    file_size_bytes = Column(Integer, nullable=True)


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
    canonical_entity_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=True)
    text = Column(String)
    label = Column(String)
    count = Column(Integer, default=1)


class CanonicalEntity(Base):
    """
    Represents a unique real-world entity across all documents.
    Multiple Entity records can link to one CanonicalEntity.
    """
    __tablename__ = "canonical_entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String, nullable=False, index=True)  # Best name representation
    label = Column(String, nullable=False)  # PERSON, ORG, GPE, etc.
    aliases = Column(Text, nullable=True)  # JSON list of known variations
    total_mentions = Column(Integer, default=0)  # Aggregate count across all docs
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Geospatial data
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    resolved_address = Column(String, nullable=True)  # Full address returned by geocoder


class EntityRelationship(Base):
    """
    Tracks co-occurrences and relationships between canonical entities.
    """
    __tablename__ = "entity_relationships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity1_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=False)
    entity2_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=False)
    relationship_type = Column(String, default="co-occurrence")  # Future: extract semantic relations
    strength = Column(Float, default=1.0)  # Number of co-occurrences or confidence score
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # Where they appeared together
    created_at = Column(DateTime, default=datetime.utcnow)


class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"))
    score = Column(Float)
    reason = Column(Text)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExtractedTable(Base):
    """
    Stores metadata and content of tables extracted from documents.
    """
    __tablename__ = "extracted_tables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_num = Column(Integer, nullable=False)
    table_index = Column(Integer, default=0)  # Index on page (multiple tables per page)
    row_count = Column(Integer, nullable=False)
    col_count = Column(Integer, nullable=False)
    headers = Column(Text, nullable=True)  # JSON list of column headers
    csv_path = Column(String, nullable=True)  # Path to exported CSV
    text_content = Column(Text, nullable=True)  # Plain text representation for search
    created_at = Column(DateTime, default=datetime.utcnow)


class TimelineEvent(Base):
    """
    Stores extracted events with temporal information from documents.
    Events can be linked to entities and documents for relationship tracking.
    """
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=True)
    event_date = Column(DateTime, nullable=True)  # Extracted/parsed date
    event_date_text = Column(String, nullable=True)  # Original date string from text
    date_precision = Column(String, default="day")  # day, month, year, approximate
    description = Column(Text, nullable=False)  # Event description
    event_type = Column(String, nullable=True)  # meeting, transaction, communication, etc.
    confidence = Column(Float, default=0.5)  # 0-1 confidence in extraction
    extraction_method = Column(String, default="llm")  # llm, regex, spacy
    context = Column(Text, nullable=True)  # Surrounding text for verification
    created_at = Column(DateTime, default=datetime.utcnow)


class DateMention(Base):
    """
    Stores all date references found in text for precise temporal tracking.
    More granular than TimelineEvent - captures every date mention.
    """
    __tablename__ = "date_mentions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    date_text = Column(String, nullable=False)  # Original text ("March 15, 2023")
    parsed_date = Column(DateTime, nullable=True)  # Parsed datetime object
    date_type = Column(String, default="explicit")  # explicit, relative, approximate
    context_before = Column(Text, nullable=True)  # 50 chars before
    context_after = Column(Text, nullable=True)  # 50 chars after
    created_at = Column(DateTime, default=datetime.utcnow)


class SensitiveDataMatch(Base):
    """
    Stores detected sensitive data patterns (SSN, credit cards, emails, etc.).
    Used for regex search and security analysis.
    """
    __tablename__ = "sensitive_data_matches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    pattern_type = Column(String, nullable=False)  # ssn, credit_card, email, etc.
    match_text = Column(String, nullable=False)  # Actual matched text
    confidence = Column(Float, default=1.0)  # 0-1 confidence score
    start_pos = Column(Integer, nullable=False)  # Position in chunk text
    end_pos = Column(Integer, nullable=False)
    context_before = Column(Text, nullable=True)  # 30 chars before
    context_after = Column(Text, nullable=True)  # 30 chars after
    created_at = Column(DateTime, default=datetime.utcnow)
