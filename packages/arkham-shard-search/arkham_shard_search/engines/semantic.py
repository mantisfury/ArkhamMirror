"""Semantic search engine using vector similarity."""

import logging
import uuid
from typing import Any

from ..models import SearchQuery, SearchResultItem

logger = logging.getLogger(__name__)


async def _fetch_chunk_text(db, chunk_id: str) -> dict | None:
    """Fetch chunk text and metadata from database."""
    if not db or not chunk_id:
        return None
    try:
        row = await db.fetchrow(
            """SELECT c.id, c.text, c.chunk_index, c.page_number,
                      d.id as doc_id, d.filename, d.mime_type
               FROM arkham_frame.chunks c
               LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
               WHERE c.id = $1""",
            chunk_id
        )
        if row:
            return dict(row)
    except Exception as e:
        logger.debug(f"Could not fetch chunk {chunk_id}: {e}")
    return None


async def _fetch_document_info(db, doc_id: str) -> dict | None:
    """Fetch document metadata from database."""
    if not db or not doc_id:
        return None
    try:
        row = await db.fetchrow(
            """SELECT id, filename, mime_type, file_size, created_at
               FROM arkham_frame.documents WHERE id = $1""",
            doc_id
        )
        if row:
            return dict(row)
    except Exception as e:
        logger.debug(f"Could not fetch document {doc_id}: {e}")
    return None


class SemanticSearchEngine:
    """
    Semantic search using pgvector.

    Performs similarity search based on embedding vectors stored in PostgreSQL.
    """

    def __init__(
        self,
        vectors_service,
        documents_service=None,
        embedding_service=None,
        worker_service=None,
        frame=None,
    ):
        """
        Initialize semantic search engine.

        Args:
            vectors_service: pgvector storage service
            documents_service: Optional documents service for metadata
            embedding_service: Direct embedding service (for sync calls)
            worker_service: Worker service (for async dispatching)
            frame: ArkhamFrame instance for active project context
        """
        self.vectors = vectors_service
        self.documents = documents_service
        self.embedding_service = embedding_service
        self.worker_service = worker_service
        self.frame = frame

    def _get_db_pool(self):
        """Get database pool dynamically from vectors service."""
        if self.vectors and hasattr(self.vectors, '_pool'):
            return self.vectors._pool
        return None

    async def _get_collection_name(self, base_name: str) -> str:
        """Get collection name with project scope if active."""
        if self.frame:
            return await self.frame.get_collection_name(base_name)
        # Fallback to global collection
        return f"arkham_{base_name}"

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

        # Get project-scoped collection name
        # Note: embeddings are stored in "documents" collection by embed shard
        collection_name = await self._get_collection_name("documents")
        logger.debug(f"Searching collection: {collection_name}")

        # Search pgvector for similar vectors
        try:
            results = await self.vectors.search(
                collection=collection_name,
                query_vector=query_vector,
                limit=query.limit,
                filter=self._build_filter(query.filters) if query.filters else None,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            results = []

        # Convert SearchResult objects to SearchResultItem with enrichment
        search_items = []
        db_conn = None
        db_pool = self._get_db_pool()
        if db_pool:
            try:
                db_conn = await db_pool.acquire()
            except Exception as e:
                logger.debug(f"Could not acquire db connection for enrichment: {e}")

        try:
            for result in results:
                payload = result.payload if hasattr(result, 'payload') else {}
                doc_id = payload.get("document_id", payload.get("doc_id", ""))
                chunk_id = payload.get("chunk_id") or (result.id if hasattr(result, 'id') else None)

                # Default values from payload
                title = payload.get("title", payload.get("filename", ""))
                excerpt = payload.get("text", payload.get("content", ""))
                file_type = payload.get("file_type", payload.get("mime_type"))
                page_number = payload.get("page_number")
                created_at = payload.get("created_at")

                # Enrich from database if we have minimal payload (just IDs)
                if db_conn and chunk_id and not excerpt:
                    chunk_info = await _fetch_chunk_text(db_conn, chunk_id)
                    if chunk_info:
                        excerpt = chunk_info.get("text", "")
                        page_number = chunk_info.get("page_number") or page_number
                        if not title:
                            title = chunk_info.get("filename", "")
                        if not file_type:
                            file_type = chunk_info.get("mime_type")
                        if not doc_id:
                            doc_id = chunk_info.get("doc_id", "")

                # If still no title, try fetching document info
                if db_conn and doc_id and not title:
                    doc_info = await _fetch_document_info(db_conn, doc_id)
                    if doc_info:
                        title = doc_info.get("filename", "")
                        if not file_type:
                            file_type = doc_info.get("mime_type")
                        if not created_at:
                            created_at = str(doc_info.get("created_at", "")) if doc_info.get("created_at") else None

                item = SearchResultItem(
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    title=title,
                    excerpt=excerpt[:500] if excerpt else "",
                    score=result.score if hasattr(result, 'score') else 0.0,
                    file_type=file_type,
                    created_at=created_at,
                    page_number=page_number,
                    highlights=[],
                    entities=payload.get("entities", []),
                    project_ids=payload.get("project_ids", []),
                    metadata=payload.get("metadata", {}),
                )
                search_items.append(item)
        finally:
            if db_conn and db_pool:
                await db_pool.release(db_conn)

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

        # Get project-scoped collection name
        collection_name = await self._get_collection_name("documents")
        logger.debug(f"Searching collection: {collection_name}")

        # Get document vector from vector store
        try:
            doc_vector = await self.vectors.get_vector(collection=collection_name, id=doc_id)
        except Exception as e:
            logger.error(f"Failed to get document vector: {e}")
            return []

        if not doc_vector:
            logger.warning(f"No vector found for document {doc_id}")
            return []

        # Search for similar vectors
        try:
            results = await self.vectors.search(
                collection=collection_name,
                query_vector=doc_vector,
                limit=limit + 1,  # +1 to exclude self
                score_threshold=min_similarity,
            )
        except Exception as e:
            logger.error(f"Similar document search failed: {e}")
            results = []

        # Filter out the source document
        results = [r for r in results if (r.payload.get("document_id") if hasattr(r, 'payload') else r.get("doc_id")) != doc_id][:limit]

        search_items = []
        for result in results:
            payload = result.payload if hasattr(result, 'payload') else {}
            item = SearchResultItem(
                doc_id=payload.get("document_id", payload.get("doc_id", "")),
                chunk_id=None,
                title=payload.get("title", payload.get("filename", "")),
                excerpt=payload.get("excerpt", payload.get("text", "")[:300] if payload.get("text") else ""),
                score=result.score if hasattr(result, 'score') else 0.0,
                file_type=payload.get("file_type"),
                created_at=payload.get("created_at"),
                highlights=[],
                metadata=payload.get("metadata", {}),
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
        # Try vectors service embed_text method first (primary method)
        if self.vectors and hasattr(self.vectors, 'embed_text'):
            try:
                result = await self.vectors.embed_text(query)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Vectors embed_text failed: {e}")

        # Try direct embedding service
        if self.embedding_service:
            try:
                result = await self.embedding_service.embed(query)
                if result and "embedding" in result:
                    return result["embedding"]
            except Exception as e:
                logger.warning(f"Direct embedding failed: {e}")

        # Fallback to worker pool (async dispatch with wait)
        if self.worker_service:
            try:
                job_id = str(uuid.uuid4())
                await self.worker_service.enqueue(
                    pool="gpu-embed",
                    job_id=job_id,
                    payload={"text": query},
                    priority=1,  # High priority for search
                )

                # Wait for result using PostgreSQL polling
                result = await self.worker_service.wait_for_result(
                    job_id=job_id,
                    timeout=10.0,
                    poll_interval=0.1,
                )

                if result and "embedding" in result:
                    return result["embedding"]

            except Exception as e:
                logger.error(f"Worker embedding failed: {e}")

        logger.error("No embedding service available")
        return None

    def _build_filter(self, filters) -> dict[str, Any]:
        """
        Build pgvector JSONB filters from SearchFilters.

        Args:
            filters: SearchFilters object

        Returns:
            Filter dict for pgvector search
        """
        if not filters:
            return {}

        filter_dict = {}

        # Date range
        if filters.date_range:
            if filters.date_range.start:
                filter_dict["created_at_gte"] = filters.date_range.start.isoformat()
            if filters.date_range.end:
                filter_dict["created_at_lte"] = filters.date_range.end.isoformat()

        # Entity filter
        if filters.entity_ids:
            filter_dict["entity_ids"] = {"any": filters.entity_ids}

        # Project filter
        if filters.project_ids:
            filter_dict["project_ids"] = {"any": filters.project_ids}

        # File type filter
        if filters.file_types:
            filter_dict["file_type"] = {"any": filters.file_types}

        # Tags filter
        if filters.tags:
            filter_dict["tags"] = {"any": filters.tags}

        return filter_dict
