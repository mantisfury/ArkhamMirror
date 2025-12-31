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
            # Subscribe to parse completion - this is when chunks are ready for embedding
            await event_bus.subscribe("parse.document.completed", self._on_parse_completed)
            logger.info("Subscribed to parse.document.completed for auto-embedding")

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
                await event_bus.unsubscribe("parse.document.completed", self._on_parse_completed)

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

    async def _on_parse_completed(self, event: dict) -> None:
        """
        Handle parse completion event.

        Automatically embeds document chunks when parsing is complete.
        The parse shard emits this event with document_id and chunk counts.
        """
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        doc_id = payload.get("document_id")
        chunks_count = payload.get("chunks_saved", payload.get("chunks", 0))

        if not doc_id:
            logger.warning("parse.document.completed event missing document_id")
            return

        logger.info(f"Parse completed for document {doc_id} with {chunks_count} chunks - starting embedding")

        # Check required services
        if not self.embedding_manager:
            logger.warning("Embedding manager not available - cannot embed")
            return

        vectors_service = self.frame.get_service("vectors")
        if not vectors_service:
            logger.warning("Vectors service not available - cannot store embeddings")
            return

        documents_service = self.frame.documents
        if not documents_service:
            logger.warning("Documents service not available - cannot fetch chunks")
            return

        try:
            # Fetch chunks from database
            chunks = await documents_service.get_document_chunks(doc_id)
            if not chunks:
                logger.warning(f"No chunks found for document {doc_id}")
                return

            logger.info(f"Found {len(chunks)} chunks to embed for document {doc_id}")

            # Extract text from chunks
            texts = []
            chunk_data = []
            for chunk in chunks:
                # Handle both Chunk objects and dicts
                if hasattr(chunk, 'content'):
                    text = chunk.content
                    chunk_id = chunk.id
                    chunk_index = getattr(chunk, 'chunk_index', 0)
                elif hasattr(chunk, 'text'):
                    text = chunk.text
                    chunk_id = chunk.id
                    chunk_index = getattr(chunk, 'index', 0)
                elif isinstance(chunk, dict):
                    text = chunk.get('content') or chunk.get('text', '')
                    chunk_id = chunk.get('id', chunk.get('chunk_id', ''))
                    chunk_index = chunk.get('chunk_index', chunk.get('index', 0))
                else:
                    logger.warning(f"Unknown chunk format: {type(chunk)}")
                    continue

                if text and text.strip():
                    texts.append(text)
                    chunk_data.append({
                        'chunk_id': str(chunk_id),
                        'doc_id': doc_id,
                        'chunk_index': chunk_index,
                        'text_length': len(text),
                    })

            if not texts:
                logger.warning(f"No valid text found in chunks for document {doc_id}")
                return

            # Embed all texts in batches
            logger.info(f"Embedding {len(texts)} chunks for document {doc_id}")
            embeddings = self.embedding_manager.embed_batch(texts, batch_size=32)

            if len(embeddings) != len(texts):
                logger.error(f"Embedding count mismatch: {len(embeddings)} vs {len(texts)}")
                return

            # Store embeddings in vector store
            import uuid as uuid_mod
            from arkham_frame.services.vectors import VectorPoint

            points = []
            for emb, data in zip(embeddings, chunk_data):
                vector_id = str(uuid_mod.uuid4())
                point = VectorPoint(
                    id=vector_id,
                    vector=emb,
                    payload={
                        'doc_id': data['doc_id'],
                        'chunk_id': data['chunk_id'],
                        'chunk_index': data['chunk_index'],
                        'text_length': data['text_length'],
                    }
                )
                points.append(point)

            # Ensure collection exists before upserting
            model_info = self.embedding_manager.get_model_info()
            if not await vectors_service.collection_exists("documents"):
                logger.info(f"Creating documents collection with {model_info.dimensions} dimensions")
                await vectors_service.create_collection(
                    name="documents",
                    vector_size=model_info.dimensions,
                )

            # Upsert to Qdrant
            await vectors_service.upsert(
                collection="documents",
                points=points,
            )

            logger.info(f"Stored {len(embeddings)} embeddings for document {doc_id}")

            # Emit completion event
            event_bus = self.frame.get_service("events")
            if event_bus:
                await event_bus.emit(
                    "embed.document.completed",
                    {
                        "document_id": doc_id,
                        "chunks_embedded": len(embeddings),
                        "dimensions": self.embedding_manager.get_model_info().dimensions,
                    },
                    source="embed-shard",
                )

        except Exception as e:
            logger.error(f"Failed to embed document {doc_id}: {e}", exc_info=True)

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
