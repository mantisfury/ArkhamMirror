"""Embed Shard - Document embeddings and vector operations."""

import logging
import os

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .embedder import EmbeddingManager
from .storage import VectorStore
from .models import EmbedConfig

logger = logging.getLogger(__name__)


class EmbedShard(ArkhamShard):
    """
    Embed shard for ArkhamFrame.

    Handles:
    - Text embedding (single and batch)
    - Document chunk embedding
    - Vector similarity search
    - Nearest neighbor search
    - Embedding model management
    - Vector storage operations
    """

    name = "embed"
    version = "0.1.0"
    description = "Document embeddings and vector operations"

    def __init__(self):
        super().__init__()
        self.embedding_manager = None
        self.vector_store = None
        self.config = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self.frame = frame

        logger.info("Initializing Embed Shard...")

        # Get required services
        vectors_service = frame.get_service("vectors")
        if not vectors_service:
            logger.error("Vectors service not available - embedding storage will be disabled")

        # Get optional services
        worker_service = frame.get_service("workers")
        event_bus = frame.get_service("events")

        # Register workers with Frame
        if worker_service:
            from .workers import EmbedWorker
            worker_service.register_worker(EmbedWorker)
            logger.info("Registered EmbedWorker to gpu-embed pool")

        # Load configuration from environment or use defaults
        model = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
        device = os.getenv("EMBED_DEVICE", "auto")
        batch_size = int(os.getenv("EMBED_BATCH_SIZE", "32"))
        cache_size = int(os.getenv("EMBED_CACHE_SIZE", "1000"))

        # Create embedding configuration
        self.config = EmbedConfig(
            model=model,
            device=device,
            batch_size=batch_size,
            cache_size=cache_size,
        )

        logger.info(
            f"Embedding config: model={model}, device={device}, "
            f"batch_size={batch_size}, cache_size={cache_size}"
        )

        # Initialize embedding manager (lazy loads model on first use)
        self.embedding_manager = EmbeddingManager(self.config)
        logger.info("Embedding manager initialized (model will load on first use)")

        # Initialize vector store
        if vectors_service:
            self.vector_store = VectorStore(vectors_service)
            logger.info("Vector store initialized")
        else:
            logger.warning("Vector store not available - storage operations disabled")

        # Initialize API
        init_api(
            embedding_manager=self.embedding_manager,
            vector_store=self.vector_store,
            worker_service=worker_service,
            event_bus=event_bus,
        )

        # Subscribe to document events for auto-embedding
        if event_bus:
            event_bus.subscribe("documents.ingested", self._on_document_ingested)
            event_bus.subscribe("documents.chunks.created", self._on_chunks_created)
            event_bus.subscribe("parse.chunks.created", self._on_chunks_created)
            logger.info("Subscribed to document events")

        logger.info("Embed Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Embed Shard...")

        # Unregister workers
        if self.frame:
            worker_service = self.frame.get_service("workers")
            if worker_service:
                from .workers import EmbedWorker
                worker_service.unregister_worker(EmbedWorker)
                logger.info("Unregistered EmbedWorker from gpu-embed pool")

        # Unsubscribe from events
        if self.frame:
            event_bus = self.frame.get_service("events")
            if event_bus:
                event_bus.unsubscribe("documents.ingested", self._on_document_ingested)
                event_bus.unsubscribe("documents.chunks.created", self._on_chunks_created)
                event_bus.unsubscribe("parse.chunks.created", self._on_chunks_created)

        # Clear cache
        if self.embedding_manager:
            self.embedding_manager.clear_cache()

        self.embedding_manager = None
        self.vector_store = None
        self.config = None

        logger.info("Embed Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _on_document_ingested(self, event: dict) -> None:
        """
        Handle document ingested event.

        Automatically queues embedding jobs for new documents.
        """
        doc_id = event.get("doc_id")
        logger.debug(f"Document ingested: {doc_id}")

        # Get worker service to queue embedding job
        worker_service = self.frame.get_service("workers")
        if not worker_service:
            logger.warning("Worker service not available - cannot queue auto-embedding")
            return

        # Queue embedding job
        try:
            job_id = await worker_service.enqueue(
                pool="gpu-embed",
                job_type="embed_document",
                payload={
                    "doc_id": doc_id,
                    "force": False,
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                },
            )
            logger.info(f"Queued auto-embedding job {job_id} for document {doc_id}")
        except Exception as e:
            logger.error(f"Failed to queue auto-embedding for {doc_id}: {e}")

    async def _on_chunks_created(self, event: dict) -> None:
        """
        Handle document chunks created event.

        Could be used to trigger immediate embedding of new chunks.
        """
        doc_id = event.get("doc_id")
        chunk_count = event.get("chunk_count", 0)
        logger.debug(f"Chunks created for document {doc_id}: {chunk_count} chunks")

        # TODO: Optionally trigger embedding of specific chunks

    # --- Public API for other shards ---

    async def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Public method for other shards to embed text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            Embedding vector as list of floats
        """
        if not self.embedding_manager:
            logger.error("Embedding manager not available")
            return []

        try:
            return self.embedding_manager.embed_text(text, use_cache=use_cache)
        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            return []

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int | None = None
    ) -> list[list[float]]:
        """
        Public method for other shards to embed multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            List of embedding vectors
        """
        if not self.embedding_manager:
            logger.error("Embedding manager not available")
            return []

        try:
            return self.embedding_manager.embed_batch(texts, batch_size=batch_size)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return []

    async def find_similar(
        self,
        query: str | list[float],
        collection: str = "documents",
        limit: int = 10,
        min_similarity: float = 0.5,
        filters: dict | None = None
    ) -> list[dict]:
        """
        Public method to find similar vectors in the vector store.

        Args:
            query: Query text or embedding vector
            collection: Qdrant collection name
            limit: Maximum results
            min_similarity: Minimum similarity score
            filters: Optional filter conditions

        Returns:
            List of similar items with scores
        """
        if not self.vector_store:
            logger.error("Vector store not available")
            return []

        try:
            # Convert query to vector if needed
            if isinstance(query, str):
                if not self.embedding_manager:
                    logger.error("Embedding manager not available")
                    return []
                query_vector = self.embedding_manager.embed_text(query)
            else:
                query_vector = query

            # Search for similar vectors
            results = await self.vector_store.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=min_similarity,
                filters=filters,
            )

            return results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []

    async def store_embedding(
        self,
        embedding: list[float],
        payload: dict,
        collection: str = "documents",
        vector_id: str | None = None
    ) -> str | None:
        """
        Public method to store an embedding in the vector store.

        Args:
            embedding: The embedding vector
            payload: Metadata to store with the vector
            collection: Qdrant collection name
            vector_id: Optional ID for the vector

        Returns:
            Vector ID if successful, None otherwise
        """
        if not self.vector_store:
            logger.error("Vector store not available")
            return None

        try:
            return await self.vector_store.upsert_vector(
                collection_name=collection,
                vector=embedding,
                payload=payload,
                vector_id=vector_id,
            )
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return None

    async def store_batch(
        self,
        embeddings: list[list[float]],
        payloads: list[dict],
        collection: str = "documents",
        vector_ids: list[str] | None = None
    ) -> list[str] | None:
        """
        Public method to store multiple embeddings in batch.

        Args:
            embeddings: List of embedding vectors
            payloads: List of metadata dictionaries
            collection: Qdrant collection name
            vector_ids: Optional list of vector IDs

        Returns:
            List of vector IDs if successful, None otherwise
        """
        if not self.vector_store:
            logger.error("Vector store not available")
            return None

        try:
            return await self.vector_store.upsert_batch(
                collection_name=collection,
                vectors=embeddings,
                payloads=payloads,
                vector_ids=vector_ids,
            )
        except Exception as e:
            logger.error(f"Failed to store batch: {e}")
            return None

    def get_model_info(self) -> dict:
        """
        Get information about the current embedding model.

        Returns:
            Dictionary with model information
        """
        if not self.embedding_manager:
            return {"error": "Embedding manager not available"}

        model_info = self.embedding_manager.get_model_info()
        return {
            "name": model_info.name,
            "dimensions": model_info.dimensions,
            "max_length": model_info.max_length,
            "loaded": model_info.loaded,
            "device": model_info.device,
        }
