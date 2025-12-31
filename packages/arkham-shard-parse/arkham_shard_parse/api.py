"""Parse Shard API endpoints."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parse", tags=["parse"])

# These get set by the shard on initialization
_ner_extractor = None
_date_extractor = None
_location_extractor = None
_relation_extractor = None
_entity_linker = None
_coref_resolver = None
_chunker = None
_worker_service = None
_event_bus = None
_parse_shard = None  # Reference to the shard itself for direct calls


def init_api(
    ner_extractor,
    date_extractor,
    location_extractor,
    relation_extractor,
    entity_linker,
    coref_resolver,
    chunker,
    worker_service,
    event_bus,
    parse_shard=None,
):
    """Initialize API with shard dependencies."""
    global _ner_extractor, _date_extractor, _location_extractor, _relation_extractor
    global _entity_linker, _coref_resolver, _chunker, _worker_service, _event_bus, _parse_shard

    _ner_extractor = ner_extractor
    _date_extractor = date_extractor
    _location_extractor = location_extractor
    _relation_extractor = relation_extractor
    _entity_linker = entity_linker
    _coref_resolver = coref_resolver
    _chunker = chunker
    _worker_service = worker_service
    _event_bus = event_bus
    _parse_shard = parse_shard


# --- Request/Response Models ---


class ParseTextRequest(BaseModel):
    text: str
    doc_id: str | None = None
    extract_entities: bool = True
    extract_dates: bool = True
    extract_locations: bool = True
    extract_relationships: bool = True


class ParseTextResponse(BaseModel):
    entities: list[dict]
    dates: list[dict]
    locations: list[dict]
    relationships: list[dict]
    total_entities: int
    total_dates: int
    total_locations: int
    processing_time_ms: float


class ParseDocumentResponse(BaseModel):
    document_id: str
    entities: list[dict]
    dates: list[dict]
    chunks: list[dict]
    total_entities: int
    total_chunks: int
    status: str
    processing_time_ms: float


class ChunkTextRequest(BaseModel):
    text: str
    chunk_size: int = 500
    overlap: int = 50
    method: str = "sentence"


class ChunkTextResponse(BaseModel):
    chunks: list[dict]
    total_chunks: int
    total_chars: int


class ChunkingConfigResponse(BaseModel):
    chunk_size: int
    chunk_overlap: int
    chunk_method: str
    available_methods: list[str]


class UpdateChunkingConfigRequest(BaseModel):
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_method: str | None = None


class EntityLinkRequest(BaseModel):
    entities: list[dict]


class EntityLinkResponse(BaseModel):
    linked_entities: list[dict]
    new_canonical_entities: int


# --- Endpoints ---


@router.post("/text", response_model=ParseTextResponse)
async def parse_text(request: ParseTextRequest):
    """
    Parse raw text and extract entities, dates, locations.

    This is a synchronous endpoint for small text snippets.
    For large documents, use POST /document/{id} instead.
    """
    if not _ner_extractor:
        raise HTTPException(status_code=503, detail="Parse service not initialized")

    from time import time
    start_time = time()

    entities = []
    dates = []
    locations = []
    relationships = []

    # Extract entities
    if request.extract_entities:
        entities = _ner_extractor.extract(
            request.text,
            doc_id=request.doc_id,
        )

    # Extract dates
    if request.extract_dates:
        dates = _date_extractor.extract(
            request.text,
            doc_id=request.doc_id,
        )

    # Extract locations (from GPE entities)
    if request.extract_locations:
        locations = []  # Would filter entities for GPE/LOC types

    # Extract relationships
    if request.extract_relationships:
        relationships = _relation_extractor.extract(
            request.text,
            entities,
            doc_id=request.doc_id,
        )

    processing_time = (time() - start_time) * 1000

    return ParseTextResponse(
        entities=[e.__dict__ for e in entities],
        dates=[d.__dict__ for d in dates],
        locations=[],
        relationships=[r.__dict__ for r in relationships],
        total_entities=len(entities),
        total_dates=len(dates),
        total_locations=0,
        processing_time_ms=processing_time,
    )


@router.post("/document/{doc_id}", response_model=ParseDocumentResponse)
async def parse_document(doc_id: str):
    """
    Parse a document and extract all entities, dates, and chunks.

    This dispatches a job to the cpu-ner worker pool for heavy processing.
    Returns immediately with job ID. Listen for parse.document.completed event.
    """
    if not _worker_service:
        raise HTTPException(status_code=503, detail="Worker service not available")

    # Dispatch to cpu-ner worker pool
    job_id = str(uuid.uuid4())
    job = await _worker_service.enqueue(
        pool="cpu-ner",
        job_id=job_id,
        payload={
            "document_id": doc_id,
            "job_type": "parse_document",
        },
        priority=2,
    )

    logger.info(f"Dispatched parse job {job_id} for document {doc_id}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "parse.document.started",
            {
                "document_id": doc_id,
                "job_id": job_id,
            },
            source="parse-shard",
        )

    return ParseDocumentResponse(
        document_id=doc_id,
        entities=[],
        dates=[],
        chunks=[],
        total_entities=0,
        total_chunks=0,
        status="processing",
        processing_time_ms=0.0,
    )


@router.post("/document/{doc_id}/sync")
async def parse_document_sync(doc_id: str, save_chunks: bool = True):
    """
    Parse a document synchronously and return results.

    This calls parse_document directly without going through the worker queue.
    Useful for testing, debugging, and re-parsing existing documents.

    Args:
        doc_id: Document ID to parse
        save_chunks: Whether to save chunks to database (default: True)

    Returns:
        Full parse result with entities, dates, chunks, and timing info
    """
    if not _parse_shard:
        raise HTTPException(status_code=503, detail="Parse shard not initialized")

    try:
        result = await _parse_shard.parse_document(doc_id, save_chunks=save_chunks)

        # Emit parse completion event so embed shard can auto-embed
        if save_chunks and _event_bus:
            await _event_bus.emit(
                "parse.document.completed",
                {
                    "document_id": doc_id,
                    "entities": result.get("total_entities", 0),
                    "chunks": result.get("total_chunks", 0),
                    "chunks_saved": result.get("chunks_saved", 0),
                },
                source="parse-shard",
            )

        return result
    except Exception as e:
        logger.error(f"Sync parse failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{doc_id}")
async def get_entities(doc_id: str):
    """
    Get extracted entities for a document.

    Returns entities that were previously extracted and stored.
    """
    # TODO: Entities are extracted but not stored to a dedicated table yet
    # For now, return empty. Future: store entities in arkham_frame.entities table
    return {
        "document_id": doc_id,
        "entities": [],
        "total": 0,
    }


@router.get("/chunks/{doc_id}")
async def get_chunks(doc_id: str):
    """
    Get text chunks for a document.

    Returns chunks that were previously created and stored.
    """
    if not _parse_shard or not _parse_shard._frame:
        raise HTTPException(status_code=503, detail="Parse shard not initialized")

    doc_service = _parse_shard._frame.get_service("documents")
    if not doc_service:
        raise HTTPException(status_code=503, detail="Document service not available")

    try:
        chunks = await doc_service.get_document_chunks(doc_id)
        return {
            "document_id": doc_id,
            "chunks": [
                {
                    "id": c.id,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "page_number": c.page_number,
                    "start_char": c.start_char,
                    "end_char": c.end_char,
                    "token_count": c.token_count,
                    "vector_id": c.vector_id,
                }
                for c in chunks
            ],
            "total": len(chunks),
        }
    except Exception as e:
        logger.error(f"Failed to get chunks for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", response_model=ChunkTextResponse)
async def chunk_text(request: ChunkTextRequest):
    """
    Chunk raw text into embedding-ready segments.

    This is synchronous and returns immediately.
    """
    if not _chunker:
        raise HTTPException(status_code=503, detail="Chunker not initialized")

    # Create temporary chunker with custom settings
    from .chunker import TextChunker

    chunker = TextChunker(
        chunk_size=request.chunk_size,
        overlap=request.overlap,
        method=request.method,
    )

    chunks = chunker.chunk_text(
        text=request.text,
        document_id="temp",
    )

    total_chars = sum(len(c.text) for c in chunks)

    return ChunkTextResponse(
        chunks=[c.__dict__ for c in chunks],
        total_chunks=len(chunks),
        total_chars=total_chars,
    )


@router.post("/link", response_model=EntityLinkResponse)
async def link_entities(request: EntityLinkRequest):
    """
    Link entity mentions to canonical entities.

    Takes a list of entity mentions and returns linked canonical entity IDs.
    Creates new canonical entities for unmatched mentions.
    """
    if not _entity_linker:
        raise HTTPException(status_code=503, detail="Entity linker not initialized")

    # Convert dicts to EntityMention objects
    from .models import EntityMention, EntityType

    mentions = []
    for entity_dict in request.entities:
        try:
            mention = EntityMention(
                text=entity_dict["text"],
                entity_type=EntityType[entity_dict["entity_type"]],
                start_char=entity_dict.get("start_char", 0),
                end_char=entity_dict.get("end_char", 0),
                confidence=entity_dict.get("confidence", 1.0),
            )
            mentions.append(mention)
        except Exception as e:
            logger.warning(f"Could not parse entity: {e}")

    # Link mentions
    results = await _entity_linker.link_mentions(mentions)

    # Count new entities
    new_entities = sum(1 for r in results if r.canonical_entity_id is None)

    return EntityLinkResponse(
        linked_entities=[
            {
                "mention": r.mention.__dict__,
                "canonical_entity_id": r.canonical_entity_id,
                "confidence": r.confidence,
                "reason": r.reason,
            }
            for r in results
        ],
        new_canonical_entities=new_entities,
    )


@router.get("/stats")
async def get_parse_stats():
    """
    Get parsing statistics.

    Returns counts of entities, chunks, and documents with chunks.
    """
    if not _parse_shard or not _parse_shard._frame:
        return {
            "total_entities": 0,
            "total_chunks": 0,
            "total_documents_parsed": 0,
            "entity_types": {},
        }

    db = _parse_shard._frame.get_service("database")
    if not db or not db._engine:
        return {
            "total_entities": 0,
            "total_chunks": 0,
            "total_documents_parsed": 0,
            "entity_types": {},
        }

    try:
        from sqlalchemy import text

        with db._engine.connect() as conn:
            # Get total chunks
            result = conn.execute(text("SELECT COUNT(*) FROM arkham_frame.chunks"))
            total_chunks = result.scalar() or 0

            # Get documents with chunks (parsed documents)
            result = conn.execute(text(
                "SELECT COUNT(DISTINCT document_id) FROM arkham_frame.chunks"
            ))
            total_documents_parsed = result.scalar() or 0

        return {
            "total_entities": 0,  # TODO: Implement entity storage
            "total_chunks": total_chunks,
            "total_documents_parsed": total_documents_parsed,
            "entity_types": {},
        }

    except Exception as e:
        logger.error(f"Failed to get parse stats: {e}")
        return {
            "total_entities": 0,
            "total_chunks": 0,
            "total_documents_parsed": 0,
            "entity_types": {},
        }


# --- List Endpoints for Dashboard ---


@router.get("/chunks")
async def list_all_chunks(
    limit: int = 50,
    offset: int = 0,
    document_id: str | None = None,
):
    """
    List all text chunks with pagination.

    Args:
        limit: Maximum number of chunks to return (default: 50)
        offset: Number of chunks to skip (default: 0)
        document_id: Optional filter by document ID
    """
    if not _parse_shard or not _parse_shard._frame:
        raise HTTPException(status_code=503, detail="Parse shard not initialized")

    db = _parse_shard._frame.get_service("database")
    doc_service = _parse_shard._frame.get_service("documents")
    if not db or not db._engine:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        from sqlalchemy import text

        with db._engine.connect() as conn:
            # Build query
            if document_id:
                query = text("""
                    SELECT c.id, c.document_id, c.chunk_index, c.text, c.page_number,
                           c.start_char, c.end_char, c.token_count, c.vector_id,
                           d.filename
                    FROM arkham_frame.chunks c
                    LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
                    WHERE c.document_id = :doc_id
                    ORDER BY c.chunk_index
                    LIMIT :limit OFFSET :offset
                """)
                result = conn.execute(query, {"doc_id": document_id, "limit": limit, "offset": offset})
                
                count_query = text("SELECT COUNT(*) FROM arkham_frame.chunks WHERE document_id = :doc_id")
                total = conn.execute(count_query, {"doc_id": document_id}).scalar() or 0
            else:
                query = text("""
                    SELECT c.id, c.document_id, c.chunk_index, c.text, c.page_number,
                           c.start_char, c.end_char, c.token_count, c.vector_id,
                           d.filename
                    FROM arkham_frame.chunks c
                    LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
                    ORDER BY c.document_id, c.chunk_index
                    LIMIT :limit OFFSET :offset
                """)
                result = conn.execute(query, {"limit": limit, "offset": offset})
                
                count_query = text("SELECT COUNT(*) FROM arkham_frame.chunks")
                total = conn.execute(count_query).scalar() or 0

            chunks = []
            for row in result:
                chunks.append({
                    "id": row.id,
                    "document_id": row.document_id,
                    "document_name": row.filename,
                    "chunk_index": row.chunk_index,
                    "text": row.text[:500] + "..." if len(row.text) > 500 else row.text,
                    "full_text": row.text,
                    "page_number": row.page_number,
                    "start_char": row.start_char,
                    "end_char": row.end_char,
                    "token_count": row.token_count,
                    "vector_id": row.vector_id,
                })

        return {
            "chunks": chunks,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(chunks) < total,
        }

    except Exception as e:
        logger.error(f"Failed to list chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Chunking Configuration Endpoints ---


@router.get("/config/chunking", response_model=ChunkingConfigResponse)
async def get_chunking_config():
    """
    Get current chunking configuration.

    Returns the current chunk size, overlap, method, and available methods.
    """
    if not _chunker:
        raise HTTPException(status_code=503, detail="Chunker not initialized")

    return ChunkingConfigResponse(
        chunk_size=_chunker.chunk_size,
        chunk_overlap=_chunker.overlap,
        chunk_method=_chunker.method,
        available_methods=["fixed", "sentence", "semantic"],
    )


@router.put("/config/chunking", response_model=ChunkingConfigResponse)
async def update_chunking_config(request: UpdateChunkingConfigRequest):
    """
    Update chunking configuration.

    Updates the chunker settings used for future document parsing.
    Changes take effect immediately for new parsing operations.

    Args:
        chunk_size: Target chunk size in characters (default: 500)
        chunk_overlap: Overlap between chunks in characters (default: 50)
        chunk_method: Chunking method - 'fixed', 'sentence', or 'semantic'
    """
    if not _chunker:
        raise HTTPException(status_code=503, detail="Chunker not initialized")

    # Validate method if provided
    if request.chunk_method and request.chunk_method not in ["fixed", "sentence", "semantic"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chunk_method. Must be one of: fixed, sentence, semantic"
        )

    # Update settings
    if request.chunk_size is not None:
        if request.chunk_size < 50:
            raise HTTPException(status_code=400, detail="chunk_size must be at least 50")
        _chunker.chunk_size = request.chunk_size

    if request.chunk_overlap is not None:
        if request.chunk_overlap < 0:
            raise HTTPException(status_code=400, detail="chunk_overlap cannot be negative")
        if request.chunk_overlap >= (_chunker.chunk_size if request.chunk_size is None else request.chunk_size):
            raise HTTPException(status_code=400, detail="chunk_overlap must be less than chunk_size")
        _chunker.overlap = request.chunk_overlap

    if request.chunk_method is not None:
        _chunker.method = request.chunk_method

    logger.info(f"Updated chunking config: size={_chunker.chunk_size}, overlap={_chunker.overlap}, method={_chunker.method}")

    # Emit event for other shards to know config changed
    if _event_bus:
        await _event_bus.emit(
            "parse.config.updated",
            {
                "chunk_size": _chunker.chunk_size,
                "chunk_overlap": _chunker.overlap,
                "chunk_method": _chunker.method,
            },
            source="parse-shard",
        )

    return ChunkingConfigResponse(
        chunk_size=_chunker.chunk_size,
        chunk_overlap=_chunker.overlap,
        chunk_method=_chunker.method,
        available_methods=["fixed", "sentence", "semantic"],
    )
