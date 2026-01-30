"""Embed Shard API endpoints."""

import logging
import uuid
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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

try:
    from arkham_frame.auth import current_optional_user
except ImportError:
    async def current_optional_user():
        return None

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embed", tags=["embed"])

# These get set by the shard on initialization
_embedding_manager = None
_vector_store = None
_worker_service = None
_event_bus = None
_db_service = None
_frame = None


def init_api(embedding_manager, vector_store, worker_service, event_bus, db_service=None, frame=None):
    """Initialize API with shard dependencies."""
    global _embedding_manager, _vector_store, _worker_service, _event_bus, _db_service, _frame
    _embedding_manager = embedding_manager
    _vector_store = vector_store
    _worker_service = worker_service
    _event_bus = event_bus
    _db_service = db_service
    _frame = frame


async def get_collection_name(base_name: str, user=None) -> str:
    """Get collection name with active-project scope when available."""
    if _frame:
        user_id = None
        if user is not None:
            user_id = getattr(user, "id", None)
            if user_id is None and isinstance(user, dict):
                user_id = user.get("id")
        return await _frame.get_collection_name(base_name, user_id=user_id)
    # Fallback to global collection
    return f"arkham_{base_name}"


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


class BatchDocumentEmbedRequestBody(BaseModel):
    """Request to embed multiple documents at once."""
    doc_ids: list[str]
    force: bool = False


class ConfigUpdateRequest(BaseModel):
    batch_size: int | None = None
    cache_size: int | None = None
    device: str | None = None


# --- Endpoints ---


@router.post("/text", response_model=EmbedResult)
async def embed_text(
    request: TextEmbedRequest,
    user = Depends(current_optional_user),
):
    """
    Embed a single text and return the vector.

    This is a synchronous operation that returns the embedding immediately.
    For large batches, use the batch endpoint or async document embedding.
    Authentication required for embedding operations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required for embedding operations")
    
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
async def embed_batch(
    request: BatchTextsRequest,
    user = Depends(current_optional_user),
):
    """
    Embed multiple texts in a single batch operation.

    More efficient than calling /text multiple times. Uses the embedding
    model's batch processing capabilities.
    Authentication required for embedding operations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required for embedding operations")
    
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
    with log_operation("embed.document", document_id=doc_id) as event:
        if event:
            event.context("shard", "embed")
            event.context("operation", "embed_document")
            event.input(document_id=doc_id)
        
        if not _worker_service:
            if event:
                event.error("ServiceUnavailable", "Worker service not initialized")
            raise HTTPException(status_code=503, detail="Worker service not initialized")

        if not _db_service:
            if event:
                event.error("ServiceUnavailable", "Database service not initialized")
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
                if event:
                    event.error("NoChunksFound", f"No chunks found for document {doc_id}")
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
                if event:
                    event.error("NoValidText", f"No valid text in chunks for document {doc_id}")
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

            if event:
                event.output(
                    job_id=job_id,
                    chunk_count=len(texts),
                    status="queued",
                    pool="gpu-embed",
                )

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
            if event:
                emit_wide_error(event, "EmbedQueueFailed", str(e), exc=e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to queue document embedding: {str(e)}"
            )


@router.get("/document/{doc_id}")
async def get_document_embeddings(doc_id: str):
    """
    Get existing embeddings for a document from the vector store.

    Returns all stored embeddings for the document's chunks.
    Uses project-scoped collection if active project is set.
    """
    if not _vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        # Get collection name with project scope
        collection_name = await get_collection_name("documents")

        # Search for embeddings with this doc_id in metadata
        # This assumes embeddings are stored with doc_id in the payload
        results = await _vector_store.search(
            collection_name=collection_name,
            query_vector=None,  # No query vector, just filter
            limit=1000,  # Large limit to get all chunks
            filters={"doc_id": doc_id}
        )

        return {
            "doc_id": doc_id,
            "collection": collection_name,
            "embeddings": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Failed to get document embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get embeddings: {str(e)}"
        )


@router.get("/documents/available")
async def get_documents_for_embedding(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    only_unembedded: bool = Query(default=False, description="Only show documents without embeddings"),
    project_id: Optional[str] = Query(default=None, description="Filter by project"),
):
    """
    Get list of documents available for embedding.

    Returns documents with their embedding status (whether they have vectors or not).
    When project_id is set, only documents in that project are returned.
    """
    if not _frame:
        raise HTTPException(status_code=503, detail="Frame not initialized")

    if not _frame.documents:
        raise HTTPException(status_code=503, detail="Document service unavailable")

    try:
        # Get documents from documents service (optionally scoped by project)
        docs, total = await _frame.documents.list_documents(
            limit=limit,
            offset=offset,
            project_id=project_id,
        )

        # Get collection name for embeddings
        collection_name = await get_collection_name("documents")

        # Build a dict of doc_id -> embedding count using SQL
        embedding_counts = {}
        chunk_counts = {}

        if _db_service:
            try:
                # Get embedding counts per document from pgvector
                # Embeddings store document_id in the payload JSONB
                embed_results = await _db_service.fetch_all(
                    """SELECT payload->>'document_id' as doc_id, COUNT(*) as count
                       FROM arkham_vectors.embeddings
                       WHERE collection = :collection
                         AND payload->>'document_id' IS NOT NULL
                       GROUP BY payload->>'document_id'""",
                    {"collection": collection_name}
                )
                for row in embed_results:
                    if row.get("doc_id"):
                        embedding_counts[row["doc_id"]] = row.get("count", 0)
            except Exception as e:
                logger.debug(f"Could not get embedding counts: {e}")

            try:
                # Get chunk counts per document
                chunk_results = await _db_service.fetch_all(
                    """SELECT document_id, COUNT(*) as count
                       FROM arkham_frame.chunks
                       GROUP BY document_id"""
                )
                for row in chunk_results:
                    if row.get("document_id"):
                        chunk_counts[row["document_id"]] = row.get("count", 0)
            except Exception as e:
                logger.debug(f"Could not get chunk counts: {e}")

        result_docs = []
        for doc in docs:
            doc_dict = doc if isinstance(doc, dict) else doc.__dict__ if hasattr(doc, '__dict__') else {}

            # Try to get the document ID
            doc_id = doc_dict.get('id') or doc_dict.get('document_id') or (doc.id if hasattr(doc, 'id') else None)

            if not doc_id:
                continue

            # Look up counts from pre-fetched data
            embedding_count = embedding_counts.get(doc_id, 0)
            chunk_count = chunk_counts.get(doc_id, 0)

            # Filter if only_unembedded is requested
            if only_unembedded and embedding_count > 0:
                continue

            result_docs.append({
                "id": doc_id,
                "title": doc_dict.get('title') or doc_dict.get('original_name') or doc_dict.get('filename') or 'Untitled',
                "filename": doc_dict.get('filename') or doc_dict.get('original_name'),
                "mime_type": doc_dict.get('mime_type'),
                "file_size": doc_dict.get('file_size'),
                "created_at": str(doc_dict.get('created_at', '')),
                "status": doc_dict.get('status', 'unknown'),
                "chunk_count": chunk_count,
                "embedding_count": embedding_count,
                "has_embeddings": embedding_count > 0,
            })

        return {
            "documents": result_docs,
            "total": total if not only_unembedded else len(result_docs),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to get documents for embedding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")


@router.post("/documents/batch")
async def embed_documents_batch(request: BatchDocumentEmbedRequestBody):
    """
    Queue multiple documents for embedding.

    This queues embedding jobs for all specified documents.
    Returns a summary of queued jobs.
    """
    if not _worker_service:
        raise HTTPException(status_code=503, detail="Worker service not initialized")

    if not _db_service:
        raise HTTPException(status_code=503, detail="Database service not initialized")

    if not request.doc_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    results = {
        "queued": [],
        "skipped": [],
        "failed": [],
    }

    for doc_id in request.doc_ids:
        try:
            # Fetch chunks for this document
            chunks = await _db_service.fetch_all(
                """SELECT id, text, chunk_index FROM arkham_frame.chunks
                   WHERE document_id = :doc_id
                   ORDER BY chunk_index""",
                {"doc_id": doc_id}
            )

            if not chunks:
                results["skipped"].append({
                    "doc_id": doc_id,
                    "reason": "No chunks found"
                })
                continue

            # Extract texts and metadata
            texts = []
            chunk_ids = []
            for chunk in chunks:
                text = chunk.get("text", "")
                if text and text.strip():
                    texts.append(text)
                    chunk_ids.append(chunk.get("id", ""))

            if not texts:
                results["skipped"].append({
                    "doc_id": doc_id,
                    "reason": "No valid text in chunks"
                })
                continue

            # Build payload for worker
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

            results["queued"].append({
                "job_id": job_id,
                "doc_id": doc_id,
                "chunk_count": len(texts),
            })

            logger.info(f"Queued embedding job {job_id} for doc {doc_id} ({len(texts)} chunks)")

        except Exception as e:
            logger.error(f"Failed to queue embedding for {doc_id}: {e}")
            results["failed"].append({
                "doc_id": doc_id,
                "error": str(e)
            })

    return {
        "success": True,
        "message": f"Queued {len(results['queued'])} documents for embedding",
        "queued": results["queued"],
        "skipped": results["skipped"],
        "failed": results["failed"],
        "summary": {
            "queued_count": len(results["queued"]),
            "skipped_count": len(results["skipped"]),
            "failed_count": len(results["failed"]),
            "total_chunks": sum(r["chunk_count"] for r in results["queued"]),
        }
    }


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
async def find_nearest(
    request: NearestRequestBody,
    user = Depends(current_optional_user),
):
    """
    Find nearest neighbors in vector space.

    If query is a string, it will be embedded first. If it's already a vector,
    it will be used directly for search.

    The collection name is resolved based on active project context.
    For example, "documents" becomes "project_{id}_documents" if a project is active.
    Authentication required for vector search operations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required for vector search")
    
    if not _embedding_manager or not _vector_store:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    try:
        # Convert query to vector if needed
        if isinstance(request.query, str):
            query_vector = _embedding_manager.embed_text(request.query)
        else:
            query_vector = request.query

        # Get collection name with project scope
        collection_name = await get_collection_name(request.collection, user=user)

        # Search for nearest neighbors
        results = await _vector_store.search(
            collection_name=collection_name,
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
    current_model_name = _embedding_manager._model_name if _embedding_manager._model_name else _embedding_manager.config.model
    is_loaded = current_model.loaded

    # Build list of known models with correct loaded state
    models = []

    # Add current model first (from actual model info)
    models.append(ModelInfo(
        name=current_model_name,
        dimensions=current_model.dimensions if is_loaded else KNOWN_MODELS.get(current_model_name, {}).get("dimensions", 0),
        max_length=current_model.max_length if is_loaded else KNOWN_MODELS.get(current_model_name, {}).get("max_length", 512),
        size_mb=KNOWN_MODELS.get(current_model_name, {}).get("size_mb", 0.0),
        loaded=is_loaded,
        device=current_model.device,
        description=KNOWN_MODELS.get(current_model_name, {}).get("description", current_model.description),
    ))

    # Add other known models
    for name, info in KNOWN_MODELS.items():
        if name == current_model_name:
            continue  # Already added above
        models.append(ModelInfo(
            name=name,
            dimensions=info["dimensions"],
            max_length=info["max_length"],
            size_mb=info["size_mb"],
            loaded=False,
            description=info["description"]
        ))

    return models


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
    """
    Get embedding statistics.

    Returns actual embedding counts from the vector store database,
    which is more meaningful than in-memory cache stats since most
    embeddings are processed through the worker pool.
    """
    try:
        # Get in-memory cache info if available
        cache_info = {}
        if _embedding_manager:
            cache_info = _embedding_manager.get_cache_info()

        # Get actual embedding stats from database
        total_embeddings = 0
        total_documents = 0
        total_chunks = 0

        if _db_service:
            try:
                # Count total embeddings in vector store
                embed_count = await _db_service.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_vectors.embeddings"
                )
                total_embeddings = embed_count.get("count", 0) if embed_count else 0

                # Count unique documents with embeddings
                doc_count = await _db_service.fetch_one(
                    """SELECT COUNT(DISTINCT payload->>'document_id') as count
                       FROM arkham_vectors.embeddings
                       WHERE payload->>'document_id' IS NOT NULL"""
                )
                total_documents = doc_count.get("count", 0) if doc_count else 0

                # Count total chunks in system
                chunk_count = await _db_service.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_frame.chunks"
                )
                total_chunks = chunk_count.get("count", 0) if chunk_count else 0
            except Exception as db_err:
                logger.debug(f"Could not get embedding counts from DB: {db_err}")

        # Calculate coverage rate (embeddings vs chunks)
        coverage_rate = total_embeddings / total_chunks if total_chunks > 0 else 0.0

        return {
            "enabled": cache_info.get("enabled", False),
            "hits": total_embeddings,  # Total embeddings stored
            "misses": max(0, total_chunks - total_embeddings),  # Chunks not yet embedded
            "size": total_documents,  # Documents with embeddings
            "max_size": total_chunks,  # Total chunks available
            "hit_rate": coverage_rate,  # Embedding coverage percentage
            # Additional context
            "total_embeddings": total_embeddings,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
        }
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


# --- Model Management ---

class ModelSwitchRequest(BaseModel):
    """Request to switch embedding model."""
    model: str
    confirm_wipe: bool = False  # Must be True if dimensions differ


class VectorCollectionInfo(BaseModel):
    """Information about a vector collection."""
    name: str
    vector_size: int
    points_count: int
    status: str


class ModelSwitchResponse(BaseModel):
    """Response from model switch operation."""
    success: bool
    message: str
    previous_model: str | None = None
    new_model: str | None = None
    previous_dimensions: int | None = None
    new_dimensions: int | None = None
    collections_wiped: bool = False
    requires_wipe: bool = False
    affected_collections: list[str] = []


# Known embedding models with their dimensions
KNOWN_MODELS = {
    "BAAI/bge-m3": {
        "dimensions": 1024,
        "max_length": 8192,
        "size_mb": 2200.0,
        "description": "Multilingual, high-quality embeddings (large)"
    },
    "all-MiniLM-L6-v2": {
        "dimensions": 384,
        "max_length": 512,
        "size_mb": 80.0,
        "description": "Lightweight, fast embeddings (small)"
    },
    "all-mpnet-base-v2": {
        "dimensions": 768,
        "max_length": 512,
        "size_mb": 420.0,
        "description": "High quality, balanced size (medium)"
    },
    "paraphrase-MiniLM-L6-v2": {
        "dimensions": 384,
        "max_length": 512,
        "size_mb": 80.0,
        "description": "Optimized for paraphrase detection (small)"
    },
}


@router.get("/model/current")
async def get_current_model():
    """
    Get information about the currently active embedding model.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    model_info = _embedding_manager.get_model_info()

    return {
        "model": model_info.name,
        "dimensions": model_info.dimensions,
        "max_length": model_info.max_length,
        "loaded": model_info.loaded,
        "device": model_info.device,
        "description": model_info.description,
    }


@router.get("/model/available")
async def get_available_models():
    """
    Get list of available embedding models with their specifications.
    """
    current_model = None
    current_loaded = False

    if _embedding_manager:
        current_info = _embedding_manager.get_model_info()
        current_loaded = current_info.loaded
        # Use _model_name if loaded, otherwise fall back to config model
        if current_loaded and _embedding_manager._model_name:
            current_model = _embedding_manager._model_name
        else:
            # Model not loaded yet, use config model name to show which will be loaded
            current_model = _embedding_manager.config.model

    models = []
    for name, info in KNOWN_MODELS.items():
        is_current = name == current_model
        models.append({
            "name": name,
            "dimensions": info["dimensions"],
            "max_length": info["max_length"],
            "size_mb": info["size_mb"],
            "description": info["description"],
            "loaded": is_current and current_loaded,
            "is_current": is_current,
        })

    return models


@router.get("/model/collections")
async def get_vector_collections():
    """
    Get information about current vector collections and their dimensions.
    """
    if not _vector_store or not _vector_store.vectors_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")

    try:
        vectors_service = _vector_store.vectors_service
        collections = await vectors_service.list_collections()

        result = []
        for coll in collections:
            result.append({
                "name": coll.name,
                "vector_size": coll.vector_size,
                "points_count": coll.points_count,
                "status": coll.status,
            })

        return result
    except Exception as e:
        logger.error(f"Failed to get collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get collections: {str(e)}")


@router.post("/model/check-switch")
async def check_model_switch(request: ModelSwitchRequest):
    """
    Check what would happen if switching to a new model.
    Returns whether a wipe is required and which collections would be affected.
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    if not _vector_store or not _vector_store.vectors_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")

    # Get current model info
    current_info = _embedding_manager.get_model_info()
    current_model = current_info.name
    current_dimensions = current_info.dimensions

    # Get new model dimensions
    new_model = request.model
    if new_model in KNOWN_MODELS:
        new_dimensions = KNOWN_MODELS[new_model]["dimensions"]
    else:
        # Unknown model - we'll need to load it to get dimensions
        # For now, return that we can't determine without loading
        return {
            "success": True,
            "requires_wipe": None,  # Unknown until model is loaded
            "message": f"Model '{new_model}' is not in known list. Dimensions will be determined on load.",
            "current_model": current_model,
            "current_dimensions": current_dimensions,
            "new_model": new_model,
            "new_dimensions": None,
            "affected_collections": [],
        }

    # Check if dimensions differ (handle None case)
    requires_wipe = current_dimensions != new_dimensions and (current_dimensions or 0) > 0

    # Get affected collections (non-empty ones)
    affected_collections = []
    if requires_wipe:
        try:
            vectors_service = _vector_store.vectors_service
            collections = await vectors_service.list_collections()
            for coll in collections:
                if coll.points_count > 0:
                    affected_collections.append(coll.name)
        except Exception as e:
            logger.warning(f"Could not check collections: {e}")

    return {
        "success": True,
        "requires_wipe": requires_wipe,
        "message": "Dimensions differ - vector database wipe required" if requires_wipe else "Model can be switched without data loss",
        "current_model": current_model,
        "current_dimensions": current_dimensions,
        "new_model": new_model,
        "new_dimensions": new_dimensions,
        "affected_collections": affected_collections,
        "total_vectors_affected": sum(
            c.points_count for c in (await _vector_store.vectors_service.list_collections())
            if c.name in affected_collections
        ) if affected_collections else 0,
    }


@router.post("/model/switch", response_model=ModelSwitchResponse)
async def switch_model(request: ModelSwitchRequest):
    """
    Switch to a different embedding model.

    If the new model has different dimensions than the current one,
    all vector collections must be wiped and recreated. This requires
    setting confirm_wipe=True in the request.

    This is a destructive operation when dimensions differ!
    """
    if not _embedding_manager:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    if not _vector_store or not _vector_store.vectors_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")

    vectors_service = _vector_store.vectors_service

    # Get current model info
    current_info = _embedding_manager.get_model_info()
    current_model = current_info.name
    current_dimensions = current_info.dimensions

    new_model = request.model

    # Same model - no change needed
    if new_model == current_model:
        return ModelSwitchResponse(
            success=True,
            message="Model is already active",
            previous_model=current_model,
            new_model=new_model,
            previous_dimensions=current_dimensions,
            new_dimensions=current_dimensions,
            collections_wiped=False,
            requires_wipe=False,
        )

    # Get new model dimensions
    if new_model in KNOWN_MODELS:
        new_dimensions = KNOWN_MODELS[new_model]["dimensions"]
    else:
        # For unknown models, we need to try loading to get dimensions
        # This is a temporary load just to check dimensions
        try:
            from sentence_transformers import SentenceTransformer
            temp_model = SentenceTransformer(new_model)
            new_dimensions = temp_model.get_sentence_embedding_dimension()
            del temp_model
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load model '{new_model}': {str(e)}"
            )

    # Check if wipe is required (handle None case)
    requires_wipe = current_dimensions != new_dimensions and (current_dimensions or 0) > 0

    if requires_wipe and not request.confirm_wipe:
        # Get affected collections
        affected = []
        try:
            collections = await vectors_service.list_collections()
            affected = [c.name for c in collections if c.points_count > 0]
        except Exception:
            pass

        return ModelSwitchResponse(
            success=False,
            message=f"Model switch requires wiping vector database (dimensions: {current_dimensions} -> {new_dimensions}). Set confirm_wipe=True to proceed.",
            previous_model=current_model,
            new_model=new_model,
            previous_dimensions=current_dimensions,
            new_dimensions=new_dimensions,
            collections_wiped=False,
            requires_wipe=True,
            affected_collections=affected,
        )

    try:
        wiped_collections = []

        # If dimensions differ and wipe confirmed, wipe collections
        if requires_wipe:
            logger.warning(f"Wiping vector collections for model switch: {current_model} -> {new_model}")

            # Get all collections
            collections = await vectors_service.list_collections()

            # Delete and recreate each collection with new dimensions
            for coll in collections:
                try:
                    await vectors_service.delete_collection(coll.name)
                    await vectors_service.create_collection(
                        name=coll.name,
                        vector_size=new_dimensions,
                    )
                    wiped_collections.append(coll.name)
                    logger.info(f"Recreated collection '{coll.name}' with {new_dimensions} dimensions")
                except Exception as e:
                    logger.error(f"Failed to recreate collection '{coll.name}': {e}")

        # Update the embedding manager config
        _embedding_manager.config.model = new_model
        _embedding_manager._model = None  # Force reload
        _embedding_manager._model_name = None
        _embedding_manager._dimensions = None

        # Clear cache since embeddings from old model are invalid
        _embedding_manager.clear_cache()

        # Trigger model load
        _ = _embedding_manager.embed_text("test")

        # Get updated model info
        new_info = _embedding_manager.get_model_info()

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "embed.model.switched",
                {
                    "previous_model": current_model,
                    "new_model": new_model,
                    "previous_dimensions": current_dimensions,
                    "new_dimensions": new_info.dimensions,
                    "collections_wiped": len(wiped_collections),
                },
                source="embed-shard",
            )

        logger.info(f"Switched embedding model: {current_model} -> {new_model}")

        return ModelSwitchResponse(
            success=True,
            message=f"Successfully switched to {new_model}" + (f" (wiped {len(wiped_collections)} collections)" if wiped_collections else ""),
            previous_model=current_model,
            new_model=new_model,
            previous_dimensions=current_dimensions,
            new_dimensions=new_info.dimensions,
            collections_wiped=bool(wiped_collections),
            requires_wipe=False,
            affected_collections=wiped_collections,
        )

    except Exception as e:
        logger.error(f"Failed to switch model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")
