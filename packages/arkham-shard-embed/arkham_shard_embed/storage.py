"""Vector storage operations for the Embed Shard."""

import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Wrapper for pgvector storage operations.

    Handles:
    - Collection management
    - Vector upsert, query, delete operations
    - Index reindexing
    - Batch operations
    """

    def __init__(self, vectors_service):
        """
        Initialize the vector store.

        Args:
            vectors_service: The Frame's vectors service (Qdrant client wrapper)
        """
        self.vectors_service = vectors_service

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        recreate: bool = False
    ) -> bool:
        """
        Create a Qdrant collection for storing embeddings.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of the vectors
            distance: Distance metric ("Cosine", "Euclidean", "Dot")
            recreate: If True, delete existing collection first

        Returns:
            True if successful, False otherwise
        """
        try:
            if recreate:
                await self.delete_collection(collection_name)

            await self.vectors_service.create_collection(
                name=collection_name,
                vector_size=vector_size,
                distance=distance,
            )

            logger.info(
                f"Created collection '{collection_name}' "
                f"(size={vector_size}, distance={distance})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            return False

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a Qdrant collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.vectors_service.delete_collection(collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False

    async def upsert_vector(
        self,
        collection_name: str,
        vector: list[float],
        payload: dict[str, Any] | None = None,
        vector_id: str | None = None
    ) -> str | None:
        """
        Insert or update a single vector in the collection.

        Args:
            collection_name: Name of the collection
            vector: The embedding vector
            payload: Metadata associated with the vector
            vector_id: Optional ID for the vector (auto-generated if None)

        Returns:
            Vector ID if successful, None otherwise
        """
        if vector_id is None:
            vector_id = str(uuid4())

        try:
            await self.vectors_service.upsert(
                collection_name=collection_name,
                points=[{
                    "id": vector_id,
                    "vector": vector,
                    "payload": payload or {}
                }]
            )

            logger.debug(f"Upserted vector {vector_id} to '{collection_name}'")
            return vector_id

        except Exception as e:
            logger.error(f"Failed to upsert vector to '{collection_name}': {e}")
            return None

    async def upsert_batch(
        self,
        collection_name: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
        vector_ids: list[str] | None = None
    ) -> list[str] | None:
        """
        Insert or update multiple vectors in batch.

        Args:
            collection_name: Name of the collection
            vectors: List of embedding vectors
            payloads: List of metadata dictionaries (one per vector)
            vector_ids: List of vector IDs (auto-generated if None)

        Returns:
            List of vector IDs if successful, None otherwise
        """
        if not vectors:
            return []

        # Generate IDs if not provided
        if vector_ids is None:
            vector_ids = [str(uuid4()) for _ in vectors]

        # Use empty payloads if not provided
        if payloads is None:
            payloads = [{} for _ in vectors]

        # Ensure all lists have same length
        if not (len(vectors) == len(payloads) == len(vector_ids)):
            logger.error("Vectors, payloads, and IDs must have same length")
            return None

        try:
            points = [
                {
                    "id": vid,
                    "vector": vec,
                    "payload": pay
                }
                for vid, vec, pay in zip(vector_ids, vectors, payloads)
            ]

            await self.vectors_service.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info(f"Upserted {len(vectors)} vectors to '{collection_name}'")
            return vector_ids

        except Exception as e:
            logger.error(f"Failed to batch upsert to '{collection_name}': {e}")
            return None

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors in the collection.

        Args:
            collection_name: Name of the collection
            query_vector: The query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filters: Qdrant filter conditions

        Returns:
            List of search results with scores and payloads
        """
        try:
            results = await self.vectors_service.search(
                collection=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                filter=filters
            )

            logger.debug(
                f"Found {len(results)} results in '{collection_name}' "
                f"(limit={limit})"
            )

            return results

        except Exception as e:
            logger.error(f"Search failed in '{collection_name}': {e}")
            return []

    async def delete_vectors(
        self,
        collection_name: str,
        vector_ids: list[str]
    ) -> bool:
        """
        Delete vectors by their IDs.

        Args:
            collection_name: Name of the collection
            vector_ids: List of vector IDs to delete

        Returns:
            True if successful, False otherwise
        """
        if not vector_ids:
            return True

        try:
            await self.vectors_service.delete(
                collection_name=collection_name,
                ids=vector_ids
            )

            logger.info(f"Deleted {len(vector_ids)} vectors from '{collection_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to delete vectors from '{collection_name}': {e}")
            return False

    async def delete_by_filter(
        self,
        collection_name: str,
        filters: dict[str, Any]
    ) -> bool:
        """
        Delete vectors matching a filter condition.

        Args:
            collection_name: Name of the collection
            filters: Payload filter conditions (e.g., {"document_id": "doc-123"})

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.vectors_service.delete(
                collection_name=collection_name,
                filter=filters
            )

            logger.info(f"Deleted vectors from '{collection_name}' with filter")
            return True

        except Exception as e:
            logger.error(f"Failed to delete by filter from '{collection_name}': {e}")
            return False

    async def get_collection_info(self, collection_name: str) -> dict[str, Any] | None:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection info, or None if not found
        """
        try:
            info = await self.vectors_service.get_collection_info(collection_name)
            return info
        except Exception as e:
            logger.error(f"Failed to get info for '{collection_name}': {e}")
            return None

    async def list_collections(self) -> list[str]:
        """
        List all available collections.

        Returns:
            List of collection names
        """
        try:
            collections = await self.vectors_service.list_collections()
            return collections
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    async def reindex_collection(self, collection_name: str) -> bool:
        """
        Reindex a collection's IVFFlat index for better search performance.

        This rebuilds the IVFFlat index with optimal parameters based on
        current data distribution. Should be called periodically after
        significant data changes.

        Args:
            collection_name: Name of the collection

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.vectors_service.reindex_collection(collection_name)
            logger.info(
                f"Reindexed collection '{collection_name}': "
                f"lists {result.get('old_lists', 0)} -> {result.get('new_lists', 0)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to reindex '{collection_name}': {e}")
            return False
