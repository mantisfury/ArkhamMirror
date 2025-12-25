"""
EmbedWorker - Generates embeddings for text using sentence-transformers.

Pool: gpu-embed
Purpose: Generate vector embeddings for semantic search and similarity matching.
"""

from typing import Dict, Any, List
import logging

from .base import BaseWorker

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

    # Model configuration
    DEFAULT_MODEL = "BAAI/bge-m3"  # Multilingual, 1024 dims, ~2.2GB
    FALLBACK_MODEL = "all-MiniLM-L6-v2"  # 384 dims, faster, smaller

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
                # BGE-M3 produces 1024-dimensional embeddings
                cls._dimensions = 1024
                logger.info(f"Loaded model {cls._model_name} ({cls._dimensions} dimensions)")
            except Exception as e:
                logger.warning(
                    f"Failed to load {cls.DEFAULT_MODEL}: {e}. "
                    f"Falling back to {cls.FALLBACK_MODEL}"
                )
                try:
                    cls._model = SentenceTransformer(cls.FALLBACK_MODEL)
                    cls._model_name = cls.FALLBACK_MODEL
                    # MiniLM produces 384-dimensional embeddings
                    cls._dimensions = 384
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

            logger.info(f"Job {job_id}: Embedding batch of {len(texts)} texts")

            # Generate embeddings for all texts
            # sentence-transformers handles batching internally
            embeddings = model.encode(texts, convert_to_numpy=True)

            # Convert numpy arrays to lists for JSON serialization
            embeddings_list = [emb.tolist() for emb in embeddings]

            return {
                "embeddings": embeddings_list,
                "dimensions": dimensions,
                "model": model_name,
                "count": len(embeddings_list),
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

            return {
                "embedding": embedding_list,
                "dimensions": dimensions,
                "model": model_name,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text_length": len(text),
                "success": True,
            }


def run_embed_worker(redis_url: str = None, worker_id: str = None):
    """
    Convenience function to run an EmbedWorker.

    Args:
        redis_url: Redis connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        python -m arkham_frame.workers.embed_worker
    """
    import asyncio
    worker = EmbedWorker(redis_url=redis_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    # Allow running directly: python -m arkham_frame.workers.embed_worker
    run_embed_worker()
