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
):
    """Initialize API with shard dependencies."""
    global _ner_extractor, _date_extractor, _location_extractor, _relation_extractor
    global _entity_linker, _coref_resolver, _chunker, _worker_service, _event_bus

    _ner_extractor = ner_extractor
    _date_extractor = date_extractor
    _location_extractor = location_extractor
    _relation_extractor = relation_extractor
    _entity_linker = entity_linker
    _coref_resolver = coref_resolver
    _chunker = chunker
    _worker_service = worker_service
    _event_bus = event_bus


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


@router.get("/entities/{doc_id}")
async def get_entities(doc_id: str):
    """
    Get extracted entities for a document.

    Returns entities that were previously extracted and stored.
    """
    # In production: query database for entities
    # SELECT * FROM entities WHERE document_id = doc_id

    return {
        "document_id": doc_id,
        "entities": [],
        "total": 0,
    }


@router.get("/chunks/{doc_id}")
async def get_chunks(doc_id: str):
    """
    Get text chunks for a document.

    Returns chunks that were previously created.
    """
    # In production: query database for chunks
    # SELECT * FROM chunks WHERE document_id = doc_id

    return {
        "document_id": doc_id,
        "chunks": [],
        "total": 0,
    }


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

    Returns counts of entities, chunks, etc.
    """
    # In production: query database for stats

    return {
        "total_entities": 0,
        "total_chunks": 0,
        "total_documents_parsed": 0,
        "entity_types": {},
    }
