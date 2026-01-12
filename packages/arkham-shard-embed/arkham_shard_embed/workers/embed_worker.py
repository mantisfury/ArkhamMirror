"""
EmbedWorker - Generates embeddings for text using sentence-transformers.

Pool: gpu-embed
Purpose: Generate vector embeddings for semantic search and similarity matching.
"""

from typing import Dict, Any, List
import logging
import os
import json
import uuid as uuid_mod

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class EmbedWorker(BaseWorker):
    """
    Worker for generating text embeddings using sentence-transformers.

    Supports both single text and batch embedding generation.
    Uses GPU acceleration if available, falls back to CPU.

    Payload formats:
    - Single: {"text": "...", "doc_id": "...", "chunk_id": "..."}
    - Batch: {"texts": ["...", "..."], "batch": True}

    Returns:
    - Single: {"embedding": [0.1, 0.2, ...], "dimensions": 1024, "model": "...", "success": True}
    - Batch: {"embeddings": [[...], [...]], "dimensions": 1024, "model": "...", "success": True}
    """

    pool = "gpu-embed"
    name = "EmbedWorker"
    job_timeout = 60.0  # Embedding can be slow for long texts

    # Model configuration - default to smaller model for fast testing
    # Set EMBED_MODEL=BAAI/bge-m3 for production quality (1024 dims, ~2.2GB)
    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384 dims, fast, ~80MB
    FALLBACK_MODEL = "paraphrase-MiniLM-L6-v2"  # 384 dims, alternative small model

    # Class-level lazy-loaded model
    _model = None
    _model_name = None
    _dimensions = None

    @classmethod
    def _get_model(cls):
        """
        Get or initialize the embedding model.

        Lazy loads the model on first use. Tries DEFAULT_MODEL first,
        falls back to FALLBACK_MODEL if not available.

        Returns:
            Tuple of (model, model_name, dimensions)
        """
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

            try:
                logger.info(f"Loading embedding model: {cls.DEFAULT_MODEL}")
                cls._model = SentenceTransformer(cls.DEFAULT_MODEL)
                cls._model_name = cls.DEFAULT_MODEL
                # Get actual dimensions from model
                cls._dimensions = cls._model.get_sentence_embedding_dimension()
                logger.info(f"Loaded model {cls._model_name} ({cls._dimensions} dimensions)")
            except Exception as e:
                logger.warning(
                    f"Failed to load {cls.DEFAULT_MODEL}: {e}. "
                    f"Falling back to {cls.FALLBACK_MODEL}"
                )
                try:
                    cls._model = SentenceTransformer(cls.FALLBACK_MODEL)
                    cls._model_name = cls.FALLBACK_MODEL
                    cls._dimensions = cls._model.get_sentence_embedding_dimension()
                    logger.info(f"Loaded fallback model {cls._model_name} ({cls._dimensions} dimensions)")
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Failed to load both models: {e}, {fallback_error}"
                    )

        return cls._model, cls._model_name, cls._dimensions

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an embedding job.

        Args:
            job_id: Unique job identifier
            payload: Job data containing either:
                - Single: {"text": str, "doc_id": str, "chunk_id": str}
                - Batch: {"texts": List[str], "batch": True}

        Returns:
            Dict with embedding(s), dimensions, model name, and success flag.

        Raises:
            ValueError: If payload is missing required fields
            Exception: If model loading or encoding fails
        """
        # Get the model (lazy load on first call)
        model, model_name, dimensions = self._get_model()

        # Check if this is a batch job
        is_batch = payload.get("batch", False)

        if is_batch:
            # Batch mode: multiple texts
            texts = payload.get("texts")
            if not texts:
                raise ValueError("Batch mode requires 'texts' field with list of strings")

            if not isinstance(texts, list):
                raise ValueError("'texts' must be a list of strings")

            doc_id = payload.get("doc_id", "")
            chunk_ids = payload.get("chunk_ids", [])

            logger.info(f"Job {job_id}: Embedding batch of {len(texts)} texts for doc {doc_id}")

            # Generate embeddings for all texts
            # sentence-transformers handles batching internally
            embeddings = model.encode(texts, convert_to_numpy=True)

            # Convert numpy arrays to lists for JSON serialization
            embeddings_list = [emb.tolist() for emb in embeddings]

            # Store embeddings in database
            vector_ids = await self._store_embeddings(
                embeddings_list,
                doc_id,
                chunk_ids,
                dimensions,
                model_name,
            )

            return {
                "embeddings": embeddings_list,
                "dimensions": dimensions,
                "model": model_name,
                "count": len(embeddings_list),
                "vector_ids": vector_ids,
                "success": True,
            }

        else:
            # Single text mode
            text = payload.get("text")
            if not text:
                raise ValueError("Single mode requires 'text' field with string content")

            if not isinstance(text, str):
                raise ValueError("'text' must be a string")

            doc_id = payload.get("doc_id", "unknown")
            chunk_id = payload.get("chunk_id", "unknown")

            logger.info(
                f"Job {job_id}: Embedding text for doc={doc_id}, chunk={chunk_id} "
                f"({len(text)} chars)"
            )

            # Generate embedding
            embedding = model.encode(text, convert_to_numpy=True)

            # Convert numpy array to list for JSON serialization
            embedding_list = embedding.tolist()

            # Store single embedding in database
            vector_ids = await self._store_embeddings(
                [embedding_list],
                doc_id,
                [chunk_id],
                dimensions,
                model_name,
            )

            return {
                "embedding": embedding_list,
                "dimensions": dimensions,
                "model": model_name,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text_length": len(text),
                "vector_id": vector_ids[0] if vector_ids else None,
                "success": True,
            }

    async def _store_embeddings(
        self,
        embeddings: List[List[float]],
        doc_id: str,
        chunk_ids: List[str],
        dimensions: int,
        model_name: str,
    ) -> List[str]:
        """
        Store embeddings in the arkham_vectors.embeddings table.

        Args:
            embeddings: List of embedding vectors
            doc_id: Document ID
            chunk_ids: List of chunk IDs (parallel to embeddings)
            dimensions: Embedding dimensions
            model_name: Name of the embedding model

        Returns:
            List of vector IDs that were stored
        """
        if not self._db_pool:
            logger.warning("No database pool - embeddings not stored persistently")
            return []

        vector_ids = []
        # Use "arkham_documents" to match VectorService standard collection naming
        # SemanticSearchEngine._get_collection_name("documents") returns "arkham_documents"
        collection_name = "arkham_documents"

        try:
            async with self._db_pool.acquire() as conn:
                # Ensure collection exists in collections table
                exists = await conn.fetchval(
                    "SELECT 1 FROM arkham_vectors.collections WHERE name = $1",
                    collection_name
                )
                if not exists:
                    # Create collection with proper dimensions
                    # Calculate optimal lists for IVFFlat (sqrt of expected rows)
                    lists = max(100, min(1000, int((100000 ** 0.5))))
                    probes = max(1, lists // 10)

                    await conn.execute("""
                        INSERT INTO arkham_vectors.collections
                            (name, vector_size, distance_metric, index_type, lists, probes)
                        VALUES ($1, $2, 'cosine', 'ivfflat', $3, $4)
                        ON CONFLICT (name) DO NOTHING
                    """, collection_name, dimensions, lists, probes)

                    logger.info(f"Created collection {collection_name} with {dimensions} dimensions")

                # Insert embeddings using batch
                values = []
                for i, embedding in enumerate(embeddings):
                    vector_id = str(uuid_mod.uuid4())
                    chunk_id = chunk_ids[i] if i < len(chunk_ids) else ""

                    # Store metadata in payload JSONB
                    payload = {
                        "document_id": doc_id,
                        "chunk_id": chunk_id,
                        "chunk_index": i,
                        "model": model_name,
                    }

                    # Pass payload as JSON string - asyncpg will handle ::jsonb cast
                    values.append((vector_id, collection_name, str(embedding), payload))
                    vector_ids.append(vector_id)

                # Batch insert all embeddings
                await conn.executemany("""
                    INSERT INTO arkham_vectors.embeddings
                    (id, collection, embedding, payload)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        payload = EXCLUDED.payload,
                        updated_at = CURRENT_TIMESTAMP
                """, values)

                # Update chunk vector_id references in batch
                chunk_updates = [(vid, cid) for vid, cid in zip(vector_ids, chunk_ids) if cid]
                if chunk_updates:
                    await conn.executemany("""
                        UPDATE arkham_frame.chunks
                        SET vector_id = $1
                        WHERE id = $2
                    """, chunk_updates)

                logger.info(f"Stored {len(vector_ids)} embeddings for doc {doc_id} in {collection_name}")

        except Exception as e:
            logger.error(f"Failed to store embeddings: {e}", exc_info=True)

        return vector_ids


def run_embed_worker(database_url: str = None, worker_id: str = None):
    """
    Convenience function to run an EmbedWorker.

    Args:
        database_url: PostgreSQL connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        python -m arkham_shard_embed.workers.embed_worker
    """
    import asyncio
    worker = EmbedWorker(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    # Allow running directly: python -m arkham_shard_embed.workers.embed_worker
    run_embed_worker()
