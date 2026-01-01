"""Embed Shard API endpoints."""

import logging
import uuid
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import (
    EmbedRequest,
    BatchEmbedRequest,
    EmbedResult,
    BatchEmbedResult,
    SimilarityRequest,
    SimilarityResult,
    NearestRequest,
    NearestResult,
    DocumentEmbedRequest,
    ModelInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embed", tags=["embed"])

# These get set by the shard on initialization
_embedding_manager = None
_vector_store = None
_worker_service = None
_event_bus = None
_db_service = None


def init_api(embedding_manager, vector_store, worker_service, event_bus, db_service=None):
    """Initialize API with shard dependencies."""
    global _embedding_manager, _vector_store, _worker_service, _event_bus, _db_service
    _embedding_manager = embedding_manager
    _vector_store = vector_store
    _worker_service = worker_service
    _event_bus = event_bus
    _db_service = db_service


# --- Request/Response Models ---


class TextEmbedRequest(BaseModel):
    text: str
    doc_id: str | None = None
    chunk_id: str | None = None
    use_cache: bool = True


class BatchTextsRequest(BaseModel):
    texts: list[str]
    batch_size: int | None = None


class SimilarityRequestBody(BaseModel):
    text1: str
    text2: str
    method: str = "cosine"


class NearestRequestBody(BaseModel):
    query: str | list[float]
    limit: int = 10
    min_similarity: float = 0.5
    collection: str = "documents"
    filters: dict | None = None


class DocumentEmbedRequestBody(BaseModel):
    doc_id: str
    force: bool = False
    chunk_size: int = 512
    chunk_overlap: int = 50


class ConfigUpdateRequest(BaseModel):
    batch_size: int | None = None
    cache_size: int | None = None
    device: str | None = None


# --- Endpoints ---


@router.post("/text", response_model=EmbedResult)
async def embed_text(request: TextEmbedRequest):
    """
    Embed a single text and return the vector.

    This is a synchronous operation that returns the embedding immediately.
    For large batches, use the batch endpoint or async document embedding.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        start_time = time.time()

        embedding = _embedding_manager.embed_text(
            text=request.text,
            use_cache=request.use_cache
        )

        model_info = _embedding_manager.get_model_info()

        result = EmbedResult(
            embedding=embedding,
            dimensions=model_info.dimensions,
            model=model_info.name,
            doc_id=request.doc_id,
            chunk_id=request.chunk_id,
            text_length=len(request.text),
            success=True,
        )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"Embedded text ({len(request.text)} chars) in {duration_ms:.2f}ms")

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "embed.text.completed",
                {
                    "doc_id": request.doc_id,
                    "chunk_id": request.chunk_id,
                    "dimensions": model_info.dimensions,
                    "duration_ms": duration_ms,
                },
                source="embed-shard",
            )

        return result

    except Exception as e:
        logger.error(f"Text embedding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@router.post("/batch", response_model=BatchEmbedResult)
async def embed_batch(request: BatchTextsRequest):
    """
    Embed multiple texts in a single batch operation.

    More efficient than calling /text multiple times. Uses the embedding
    model's batch processing capabilities.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    if not request.texts:
        raise HTTPException(status_code=400, detail="No texts provided")

    try:
        start_time = time.time()

        embeddings = _embedding_manager.embed_batch(
            texts=request.texts,
            batch_size=request.batch_size
        )

        model_info = _embedding_manager.get_model_info()

        result = BatchEmbedResult(
            embeddings=embeddings,
            dimensions=model_info.dimensions,
            model=model_info.name,
            count=len(embeddings),
            success=True,
        )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Embedded batch of {len(request.texts)} texts in {duration_ms:.2f}ms "
            f"({duration_ms / len(request.texts):.2f}ms per text)"
        )

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "embed.batch.completed",
                {
                    "count": len(embeddings),
                    "dimensions": model_info.dimensions,
                    "duration_ms": duration_ms,
                },
                source="embed-shard",
            )

        return result

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch embedding failed: {str(e)}")


@router.post("/document/{doc_id}")
async def embed_document(doc_id: str, request: DocumentEmbedRequestBody | None = None):
    """
    Queue a job to embed all chunks of a document.

    This fetches document chunks from the database and dispatches them
    as a batch to the gpu-embed worker pool.
    Returns a job ID that can be used to track progress.
    """
    if not _worker_service:
        raise HTTPException(status_code=503, detail="Worker service not initialized")

    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not initialized")

    try:
        # Fetch chunks for this document from the database
        chunks = await _db_service.fetch_all(
            """SELECT id, text, chunk_index FROM arkham_frame.chunks
               WHERE document_id = :doc_id
               ORDER BY chunk_index""",
            {"doc_id": doc_id}
        )

        if not chunks:
            raise HTTPException(status_code=404, detail=f"No chunks found for document {doc_id}")

        # Extract texts and metadata
        texts = []
        chunk_ids = []
        for chunk in chunks:
            text = chunk.get("text", "")
            if text and text.strip():
                texts.append(text)
                chunk_ids.append(chunk.get("id", ""))

        if not texts:
            raise HTTPException(status_code=404, detail=f"No valid text in chunks for document {doc_id}")

        # Build payload for worker with batch mode
        job_id = str(uuid.uuid4())
        payload = {
            "batch": True,
            "texts": texts,
            "doc_id": doc_id,
            "chunk_ids": chunk_ids,
        }

        await _worker_service.enqueue(
            pool="gpu-embed",
            job_id=job_id,
            payload=payload,
        )

        logger.info(f"Queued document embedding job {job_id} for doc {doc_id} ({len(texts)} chunks)")

        return {
            "job_id": job_id,
            "doc_id": doc_id,
            "status": "queued",
            "chunk_count": len(texts),
            "message": "Document embedding job queued"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue document embedding: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue document embedding: {str(e)}"
        )


@router.get("/document/{doc_id}")
async def get_document_embeddings(doc_id: str):
    """
    Get existing embeddings for a document from the vector store.

    Returns all stored embeddings for the document's chunks.
    """
    if not _vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        # Search for embeddings with this doc_id in metadata
        # This assumes embeddings are stored with doc_id in the payload
        results = await _vector_store.search(
            collection_name="documents",
            query_vector=None,  # No query vector, just filter
            limit=1000,  # Large limit to get all chunks
            filters={"doc_id": doc_id}
        )

        return {
            "doc_id": doc_id,
            "embeddings": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Failed to get document embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get embeddings: {str(e)}"
        )


@router.post("/similarity", response_model=SimilarityResult)
async def calculate_similarity(request: SimilarityRequestBody):
    """
    Calculate similarity between two texts.

    Embeds both texts and computes their similarity using the specified method.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        # Embed both texts
        emb1 = _embedding_manager.embed_text(request.text1)
        emb2 = _embedding_manager.embed_text(request.text2)

        # Calculate similarity
        similarity = _embedding_manager.calculate_similarity(
            emb1, emb2, method=request.method
        )

        return SimilarityResult(
            similarity=similarity,
            method=request.method,
            success=True,
        )

    except Exception as e:
        logger.error(f"Similarity calculation failed: {e}", exc_info=True)
        return SimilarityResult(
            similarity=0.0,
            method=request.method,
            success=False,
            error=str(e),
        )


@router.post("/nearest", response_model=NearestResult)
async def find_nearest(request: NearestRequestBody):
    """
    Find nearest neighbors in vector space.

    If query is a string, it will be embedded first. If it's already a vector,
    it will be used directly for search.
    """
    if not _embedding_manager or not _vector_store:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        # Convert query to vector if needed
        if isinstance(request.query, str):
            query_vector = _embedding_manager.embed_text(request.query)
        else:
            query_vector = request.query

        # Search for nearest neighbors
        results = await _vector_store.search(
            collection_name=request.collection,
            query_vector=query_vector,
            limit=request.limit,
            score_threshold=request.min_similarity,
            filters=request.filters,
        )

        return NearestResult(
            neighbors=results,
            total=len(results),
            query_dimensions=len(query_vector),
            success=True,
        )

    except Exception as e:
        logger.error(f"Nearest neighbor search failed: {e}", exc_info=True)
        return NearestResult(
            neighbors=[],
            total=0,
            query_dimensions=0,
            success=False,
            error=str(e),
        )


@router.get("/models", response_model=list[ModelInfo])
async def list_models():
    """
    List available embedding models.

    Returns information about the currently loaded model and other
    supported models.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    # Get current model info
    current_model = _embedding_manager.get_model_info()

    # List of known models (could be expanded)
    models = [
        current_model,
        ModelInfo(
            name="BAAI/bge-m3",
            dimensions=1024,
            max_length=8192,
            size_mb=2200.0,
            loaded=(current_model.name == "BAAI/bge-m3"),
            description="Multilingual, high-quality embeddings"
        ),
        ModelInfo(
            name="all-MiniLM-L6-v2",
            dimensions=384,
            max_length=512,
            size_mb=80.0,
            loaded=(current_model.name == "all-MiniLM-L6-v2"),
            description="Lightweight, fast embeddings"
        ),
    ]

    # Remove duplicates
    seen = set()
    unique_models = []
    for model in models:
        if model.name not in seen:
            seen.add(model.name)
            unique_models.append(model)

    return unique_models


@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update embedding configuration.

    Note: Some changes (like device) may require reloading the model.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        updated = {}

        if request.batch_size is not None:
            _embedding_manager.config.batch_size = request.batch_size
            updated["batch_size"] = request.batch_size

        if request.cache_size is not None:
            # Note: Changing cache size requires reinitializing the cache
            logger.warning("Cache size changes require shard restart to take effect")
            updated["cache_size"] = request.cache_size

        if request.device is not None:
            # Note: Changing device requires reloading the model
            logger.warning("Device changes require model reload")
            updated["device"] = request.device

        logger.info(f"Updated embedding config: {updated}")

        return {
            "success": True,
            "updated": updated,
            "message": "Configuration updated"
        }

    except Exception as e:
        logger.error(f"Config update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Config update failed: {str(e)}")


@router.get("/cache/stats")
async def get_cache_stats():
    """Get embedding cache statistics."""
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        cache_info = _embedding_manager.get_cache_info()
        return cache_info
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/cache/clear")
async def clear_cache():
    """Clear the embedding cache."""
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        _embedding_manager.clear_cache()
        return {
            "success": True,
            "message": "Cache cleared"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
