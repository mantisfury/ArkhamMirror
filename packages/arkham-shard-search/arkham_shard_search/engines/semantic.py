"""Semantic search engine using vector similarity."""

import logging
import uuid
from typing import Any

from ..models import SearchQuery, SearchResultItem

logger = logging.getLogger(__name__)


class SemanticSearchEngine:
    """
    Semantic search using Qdrant vector store.

    Performs similarity search based on embedding vectors.
    """

    def __init__(
        self,
        vectors_service,
        documents_service=None,
        embedding_service=None,
        worker_service=None,
    ):
        """
        Initialize semantic search engine.

        Args:
            vectors_service: Qdrant vector store service
            documents_service: Optional documents service for metadata
            embedding_service: Direct embedding service (for sync calls)
            worker_service: Worker service (for async dispatching)
        """
        self.vectors = vectors_service
        self.documents = documents_service
        self.embedding_service = embedding_service
        self.worker_service = worker_service

    async def search(self, query: SearchQuery) -> list[SearchResultItem]:
        """
        Perform semantic search.

        Args:
            query: SearchQuery object

        Returns:
            List of SearchResultItem
        """
        logger.info(f"Semantic search: '{query.query}' (limit={query.limit})")

        # Generate query embedding
        query_vector = await self._embed_query(query.query)

        if not query_vector:
            logger.warning("Failed to generate query embedding, returning empty results")
            return []

        # Search Qdrant for similar vectors
        try:
            results = await self.vectors.search(
                collection="chunks",
                vector=query_vector,
                limit=query.limit,
                offset=query.offset if hasattr(query, 'offset') else 0,
                filters=self._build_filters(query.filters) if query.filters else None,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            results = []

        # Convert Qdrant results to SearchResultItem
        search_items = []
        for result in results:
            item = SearchResultItem(
                doc_id=result.get("doc_id", ""),
                chunk_id=result.get("chunk_id"),
                title=result.get("title", ""),
                excerpt=result.get("text", "")[:300],
                score=result.get("score", 0.0),
                file_type=result.get("file_type"),
                created_at=result.get("created_at"),
                page_number=result.get("page_number"),
                highlights=[],
                entities=result.get("entities", []),
                project_ids=result.get("project_ids", []),
                metadata=result.get("metadata", {}),
            )
            search_items.append(item)

        return search_items

    async def find_similar(self, doc_id: str, limit: int = 10, min_similarity: float = 0.5) -> list[SearchResultItem]:
        """
        Find documents similar to a given document.

        Args:
            doc_id: Document ID to find similar documents for
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0.0-1.0)

        Returns:
            List of SearchResultItem
        """
        logger.info(f"Finding similar documents to {doc_id}")

        # Get document vector from Qdrant
        try:
            doc_vector = await self.vectors.get_vector(collection="documents", id=doc_id)
        except Exception as e:
            logger.error(f"Failed to get document vector: {e}")
            return []

        if not doc_vector:
            logger.warning(f"No vector found for document {doc_id}")
            return []

        # Search for similar vectors
        try:
            results = await self.vectors.search(
                collection="documents",
                vector=doc_vector,
                limit=limit + 1,  # +1 to exclude self
                score_threshold=min_similarity,
            )
        except Exception as e:
            logger.error(f"Similar document search failed: {e}")
            results = []

        # Filter out the source document
        results = [r for r in results if r.get("doc_id") != doc_id][:limit]

        search_items = []
        for result in results:
            item = SearchResultItem(
                doc_id=result.get("doc_id", ""),
                chunk_id=None,
                title=result.get("title", ""),
                excerpt=result.get("excerpt", ""),
                score=result.get("score", 0.0),
                file_type=result.get("file_type"),
                created_at=result.get("created_at"),
                highlights=[],
                metadata=result.get("metadata", {}),
            )
            search_items.append(item)

        return search_items

    async def _embed_query(self, query: str) -> list[float] | None:
        """
        Generate embedding for query text.

        Args:
            query: Query text

        Returns:
            Embedding vector or None if failed
        """
        # Try direct embedding service first (faster for search)
        if self.embedding_service:
            try:
                result = await self.embedding_service.embed(query)
                if result and "embedding" in result:
                    return result["embedding"]
            except Exception as e:
                logger.warning(f"Direct embedding failed: {e}")

        # Fallback to worker pool
        if self.worker_service:
            try:
                import asyncio
                import json

                job_id = str(uuid.uuid4())
                await self.worker_service.enqueue(
                    pool="gpu-embed",
                    job_id=job_id,
                    payload={"text": query},
                    priority=1,  # High priority for search
                )

                # Wait for result (blocking)
                job_key = f"arkham:job:{job_id}"
                redis = self.worker_service.redis

                for _ in range(100):  # 10 second timeout
                    status = await redis.hget(job_key, "status")
                    if status:
                        if isinstance(status, bytes):
                            status = status.decode()
                        if status == "completed":
                            result = await redis.hget(job_key, "result")
                            if result:
                                if isinstance(result, bytes):
                                    result = result.decode()
                                data = json.loads(result)
                                return data.get("embedding")
                        elif status == "failed":
                            logger.error("Embedding job failed")
                            break
                    await asyncio.sleep(0.1)

                logger.warning("Embedding job timed out")
            except Exception as e:
                logger.error(f"Worker embedding failed: {e}")

        logger.error("No embedding service available")
        return None

    def _build_filters(self, filters) -> dict[str, Any]:
        """
        Build Qdrant filters from SearchFilters.

        Args:
            filters: SearchFilters object

        Returns:
            Qdrant filter dict
        """
        if not filters:
            return {}

        qdrant_filters = {}

        # Date range
        if filters.date_range:
            if filters.date_range.start:
                qdrant_filters["created_at_gte"] = filters.date_range.start.isoformat()
            if filters.date_range.end:
                qdrant_filters["created_at_lte"] = filters.date_range.end.isoformat()

        # Entity filter
        if filters.entity_ids:
            qdrant_filters["entity_ids"] = {"any": filters.entity_ids}

        # Project filter
        if filters.project_ids:
            qdrant_filters["project_ids"] = {"any": filters.project_ids}

        # File type filter
        if filters.file_types:
            qdrant_filters["file_type"] = {"any": filters.file_types}

        # Tags filter
        if filters.tags:
            qdrant_filters["tags"] = {"any": filters.tags}

        return qdrant_filters
