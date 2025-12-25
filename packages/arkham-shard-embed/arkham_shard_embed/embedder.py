"""Core embedding logic for the Embed Shard."""

import logging
from typing import Any
from functools import lru_cache
import numpy as np

from .models import EmbedConfig, ModelInfo

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    Manages embedding model loading and inference.

    Features:
    - Lazy model loading (load on first use)
    - Automatic GPU/CPU detection
    - Model caching to avoid reloading
    - Batch processing optimization
    - Multiple model support
    """

    def __init__(self, config: EmbedConfig):
        """
        Initialize the embedding manager.

        Args:
            config: Embedding configuration
        """
        self.config = config
        self._model = None
        self._model_name = None
        self._dimensions = None
        self._device = None

        # Cache for embeddings (LRU cache)
        self._cache_enabled = config.cache_size > 0
        if self._cache_enabled:
            self._embed_cached = lru_cache(maxsize=config.cache_size)(self._embed_single)

    def _detect_device(self) -> str:
        """
        Detect the best available device for model inference.

        Returns:
            Device string ("cuda", "cpu", "mps")
        """
        if self.config.device != "auto":
            return self.config.device

        try:
            import torch
            if torch.cuda.is_available():
                logger.info("CUDA GPU detected")
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("Apple MPS detected")
                return "mps"
        except ImportError:
            pass

        logger.info("Using CPU for embeddings")
        return "cpu"

    def _load_model(self):
        """
        Load the embedding model.

        Lazy loads the model on first use. Tries the configured model first,
        with fallback options if loading fails.

        Raises:
            ImportError: If sentence-transformers is not installed
            RuntimeError: If model loading fails
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        # Detect device
        self._device = self._detect_device()

        # Try to load the configured model
        model_name = self.config.model

        try:
            logger.info(f"Loading embedding model: {model_name} on {self._device}")
            self._model = SentenceTransformer(model_name, device=self._device)
            self._model_name = model_name

            # Get dimensions from model
            self._dimensions = self._model.get_sentence_embedding_dimension()

            logger.info(
                f"Loaded model {self._model_name} "
                f"({self._dimensions} dimensions) on {self._device}"
            )
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise RuntimeError(f"Failed to load embedding model {model_name}: {e}")

    def get_model_info(self) -> ModelInfo:
        """
        Get information about the currently loaded model.

        Returns:
            ModelInfo object with model details
        """
        if self._model is None:
            return ModelInfo(
                name=self.config.model,
                dimensions=0,
                max_length=self.config.max_length,
                size_mb=0.0,
                loaded=False,
                description="Model not loaded yet"
            )

        return ModelInfo(
            name=self._model_name,
            dimensions=self._dimensions,
            max_length=self.config.max_length,
            size_mb=0.0,  # TODO: Calculate model size
            loaded=True,
            device=self._device,
            description=f"Loaded on {self._device}"
        )

    def _embed_single(self, text: str) -> list[float]:
        """
        Embed a single text (internal method for caching).

        Args:
            text: Text to embed

        Returns:
            Embedding as list of floats
        """
        # Ensure model is loaded
        self._load_model()

        # Generate embedding
        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize,
        )

        return embedding.tolist()

    def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Embed a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            Embedding as list of floats
        """
        if use_cache and self._cache_enabled:
            return self._embed_cached(text)
        else:
            return self._embed_single(text)

    def embed_batch(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing (uses config default if None)

        Returns:
            List of embeddings
        """
        # Ensure model is loaded
        self._load_model()

        if batch_size is None:
            batch_size = self.config.batch_size

        logger.info(f"Embedding batch of {len(texts)} texts (batch_size={batch_size})")

        # Generate embeddings for all texts
        # sentence-transformers handles batching internally
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize,
        )

        # Convert numpy arrays to lists for JSON serialization
        return [emb.tolist() for emb in embeddings]

    def calculate_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
        method: str = "cosine"
    ) -> float:
        """
        Calculate similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding
            method: Similarity method ("cosine", "euclidean", "dot")

        Returns:
            Similarity score

        Raises:
            ValueError: If method is not supported
        """
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)

        if method == "cosine":
            # Cosine similarity
            dot_product = np.dot(arr1, arr2)
            norm1 = np.linalg.norm(arr1)
            norm2 = np.linalg.norm(arr2)
            return float(dot_product / (norm1 * norm2))

        elif method == "dot":
            # Dot product
            return float(np.dot(arr1, arr2))

        elif method == "euclidean":
            # Euclidean distance (inverted to similarity)
            distance = np.linalg.norm(arr1 - arr2)
            return float(1.0 / (1.0 + distance))

        else:
            raise ValueError(f"Unsupported similarity method: {method}")

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> list[str]:
        """
        Split text into overlapping chunks for embedding.

        Args:
            text: Text to chunk
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Number of overlapping characters between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for last period, question mark, or exclamation point
                last_sentence = max(
                    chunk.rfind(". "),
                    chunk.rfind("? "),
                    chunk.rfind("! ")
                )
                if last_sentence > chunk_size // 2:
                    chunk = chunk[:last_sentence + 1]
                    end = start + last_sentence + 1

            chunks.append(chunk.strip())

            # Move start position with overlap
            start = end - chunk_overlap
            if start >= len(text):
                break

        return chunks

    def clear_cache(self):
        """Clear the embedding cache."""
        if self._cache_enabled:
            self._embed_cached.cache_clear()
            logger.info("Embedding cache cleared")

    def get_cache_info(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache info
        """
        if not self._cache_enabled:
            return {"enabled": False}

        cache_info = self._embed_cached.cache_info()
        return {
            "enabled": True,
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "size": cache_info.currsize,
            "max_size": cache_info.maxsize,
        }
