from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")  # active, archived, completed
    priority = Column(String, default="medium")  # high, medium, low
    tags = Column(Text, nullable=True)  # JSON list of tags
    color = Column(String, default="#3b82f6")  # Hex color for UI
    lead_investigator = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

    __table_args__ = (
        UniqueConstraint("document_id", "page_num", name="uq_page_ocr_doc_page"),
    )


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"))
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Entity(Base):
    """
    Represents an entity mention found in a document.
    Links to a chunk for context and optionally to a canonical entity for deduplication.
    """

    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"))
    chunk_id = Column(
        Integer, ForeignKey("chunks.id"), nullable=True
    )  # For context tracking
    canonical_entity_id = Column(
        Integer, ForeignKey("canonical_entities.id"), nullable=True
    )
    text = Column(String)
    label = Column(String)
    count = Column(Integer, default=1)


# Alias for backward compatibility with services expecting EntityMention
EntityMention = Entity


class CanonicalEntity(Base):
    """
    Represents a unique real-world entity across all documents.
    Multiple Entity records can link to one CanonicalEntity.
    """

    __tablename__ = "canonical_entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(
        String, nullable=False, index=True
    )  # Best name representation
    label = Column(String, nullable=False)  # PERSON, ORG, GPE, etc.
    aliases = Column(Text, nullable=True)  # JSON list of known variations
    total_mentions = Column(Integer, default=0)  # Aggregate count across all docs
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Geospatial data
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    resolved_address = Column(
        String, nullable=True
    )  # Full address returned by geocoder


class EntityRelationship(Base):
    """
    Tracks co-occurrences and relationships between canonical entities.
    """

    __tablename__ = "entity_relationships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity1_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=False)
    entity2_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=False)
    relationship_type = Column(
        String, default="co-occurrence"
    )  # Future: extract semantic relations
    strength = Column(
        Float, default=1.0
    )  # Number of co-occurrences or confidence score
    co_occurrence_count = Column(
        Integer, default=1
    )  # Count of co-occurrences (used by services)
    doc_id = Column(
        Integer, ForeignKey("documents.id"), nullable=True
    )  # Where they appeared together
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
    event_type = Column(
        String, nullable=True
    )  # meeting, transaction, communication, etc.
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


class EntityMergeAudit(Base):
    """
    Tracks entity merge operations for audit and potential undo.
    Records which canonical entities were merged and when.
    """

    __tablename__ = "entity_merge_audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kept_canonical_id = Column(
        Integer, nullable=False
    )  # Not FK since entity may be deleted later
    merged_canonical_id = Column(
        Integer, nullable=False
    )  # The entity that was merged away
    kept_name = Column(String, nullable=False)
    merged_name = Column(String, nullable=False)
    label = Column(String, nullable=False)
    entities_affected = Column(
        Integer, default=0
    )  # How many entity mentions were updated
    relationships_affected = Column(
        Integer, default=0
    )  # How many relationships were updated
    merged_at = Column(DateTime, default=datetime.utcnow)
    merge_type = Column(String, default="manual")  # manual or automatic
    user_note = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    affected_entity_ids = Column(Text, nullable=True)  # JSON list of Entity IDs moved


class Contradiction(Base):
    """
    Represents a detected contradiction or conflict between statements in the corpus.
    Can be entity-centric or general.
    """

    __tablename__ = "contradictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("canonical_entities.id"), nullable=True)
    description = Column(Text, nullable=False)  # Summary of the conflict
    severity = Column(String, default="Medium")  # High, Medium, Low
    status = Column(String, default="Open")  # Open, Resolved, False Positive
    confidence = Column(Float, default=0.0)  # 0.0 - 1.0
    created_at = Column(DateTime, default=datetime.utcnow)
    resolution_note = Column(Text, nullable=True)

    # Phase 3 fields
    category = Column(String, default="factual")  # factual, temporal, numerical, etc.
    tags = Column(Text, nullable=True)  # JSON list of tags
    chain_id = Column(String, nullable=True)  # ID for related contradiction chains
    chain_position = Column(Integer, nullable=True)  # Position in chain
    detection_method = Column(String, default="llm")  # llm, rule-based, user
    llm_model = Column(String, nullable=True)  # Model used for detection
    user_notes = Column(Text, nullable=True)  # User annotations
    reviewed_at = Column(DateTime, nullable=True)  # When user reviewed
    involved_entity_ids = Column(Text, nullable=True)  # JSON list of entity IDs


class ContradictionEvidence(Base):
    """
    Supporting evidence for a detected contradiction.
    Links a specific text chunk to a contradiction record.
    """

    __tablename__ = "contradiction_evidence"
    id = Column(Integer, primary_key=True, autoincrement=True)
    contradiction_id = Column(Integer, ForeignKey("contradictions.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=True)
    text_chunk = Column(Text, nullable=False)  # The specific quote
    page_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ContradictionBatch(Base):
    """
    Tracks batch processing state for contradiction detection.
    Each batch represents a set of entities to analyze for contradictions.
    """

    __tablename__ = "contradiction_batch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_number = Column(Integer, nullable=False, unique=True)
    status = Column(String, default="pending")  # pending, running, complete, failed
    entity_offset = Column(Integer, default=0)  # Starting entity index
    entity_count = Column(Integer, default=0)  # Number of entities in this batch
    contradictions_found = Column(Integer, default=0)  # Count of contradictions found
    job_id = Column(String, nullable=True)  # RQ job ID for tracking
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime, default=datetime.utcnow)


class EntityAnalysisCache(Base):
    """
    Caches analysis state for entities to avoid re-processing unchanged content.
    Used by contradiction detection to skip entities that haven't changed.
    """

    __tablename__ = "entity_analysis_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(
        Integer,
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    content_hash = Column(String, nullable=False)  # Hash of related chunk content
    last_analyzed_at = Column(DateTime, default=datetime.utcnow)
    chunk_count = Column(Integer, default=0)  # Number of chunks analyzed
    contradiction_count = Column(Integer, default=0)  # Contradictions found


class IngestionError(Base):
    """
    Tracks errors during document ingestion stages.
    Provides centralized error logging for troubleshooting and retry logic.
    """

    __tablename__ = "ingestion_errors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    chunk_id = Column(
        Integer, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    stage = Column(
        String, nullable=False
    )  # ocr, chunking, embedding, entity, llm_enrich, table
    error_type = Column(
        String, nullable=False
    )  # timeout, parse_error, connection, validation
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    is_resolved = Column(Integer, default=0)  # 0=unresolved, 1=resolved
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntityFilterRule(Base):
    """
    Stores patterns for filtering noisy entities during extraction.
    Supports regex patterns for flexible matching.
    """

    __tablename__ = "entity_filter_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(String, nullable=False)
    is_regex = Column(Integer, default=1)  # 1=regex, 0=literal
    created_by = Column(String, default="system")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FactComparisonCache(Base):
    """
    Caches fact comparison analysis results to avoid expensive re-analysis.
    Uses a hash of document/entity IDs as the cache key.
    Results expire after 24 hours.
    """

    __tablename__ = "fact_comparison_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(
        String(64), unique=True, index=True, nullable=False
    )  # SHA-256 hash of sorted doc/entity IDs
    results_json = Column(Text, nullable=False)  # JSON-serialized analysis results
    entity_count = Column(Integer, default=0)  # Number of entities analyzed
    fact_count = Column(Integer, default=0)  # Total facts found
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # Cache expiration time


class AnomalyKeyword(Base):
    """
    Configurable keywords for anomaly detection.
    Allows users to define suspicious terms and their weights.
    """

    __tablename__ = "anomaly_keywords"
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, nullable=False)
    weight = Column(Float, default=0.2)
    is_active = Column(Integer, default=1)  # 0=disabled, 1=enabled
    created_at = Column(DateTime, default=datetime.utcnow)
