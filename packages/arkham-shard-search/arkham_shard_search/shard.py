"""Search Shard - Semantic and keyword search for documents."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .engines import SemanticSearchEngine, KeywordSearchEngine, HybridSearchEngine
from .filters import FilterOptimizer

logger = logging.getLogger(__name__)


class SearchShard(ArkhamShard):
    """
    Search shard for ArkhamFrame.

    Handles:
    - Semantic search (vector similarity)
    - Keyword search (full-text)
    - Hybrid search (combined)
    - Document similarity
    - Autocomplete suggestions
    - Search filtering and ranking
    """

    name = "search"
    version = "0.1.0"
    description = "Semantic and keyword search for documents"

    def __init__(self):
        super().__init__()
        self.semantic_engine = None
        self.keyword_engine = None
        self.hybrid_engine = None
        self.filter_optimizer = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self.frame = frame

        logger.info("Initializing Search Shard...")

        # Get required services
        vectors_service = frame.get_service("vectors")
        if not vectors_service:
            logger.error("Vectors service not available - semantic search will be disabled")

        database_service = frame.get_service("database") or frame.get_service("db")
        if not database_service:
            logger.error("Database service not available - keyword search will be disabled")

        # Get optional services
        documents_service = frame.get_service("documents")
        entities_service = frame.get_service("entities")
        event_bus = frame.get_service("events")

        # Initialize search engines
        if vectors_service:
            self.semantic_engine = SemanticSearchEngine(
                vectors_service=vectors_service,
                documents_service=documents_service,
            )
            logger.info("Semantic search engine initialized")

        if database_service:
            self.keyword_engine = KeywordSearchEngine(
                database_service=database_service,
                documents_service=documents_service,
            )
            logger.info("Keyword search engine initialized")

        if self.semantic_engine and self.keyword_engine:
            self.hybrid_engine = HybridSearchEngine(
                semantic_engine=self.semantic_engine,
                keyword_engine=self.keyword_engine,
            )
            logger.info("Hybrid search engine initialized")

        # Initialize filter optimizer
        if database_service:
            self.filter_optimizer = FilterOptimizer(database_service)

        # Initialize API
        init_api(
            semantic_engine=self.semantic_engine,
            keyword_engine=self.keyword_engine,
            hybrid_engine=self.hybrid_engine,
            filter_optimizer=self.filter_optimizer,
            event_bus=event_bus,
        )

        # Subscribe to document events
        if event_bus:
            await event_bus.subscribe("documents.indexed", self._on_document_indexed)
            await event_bus.subscribe("documents.deleted", self._on_document_deleted)

        logger.info("Search Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Search Shard...")

        # Unsubscribe from events
        if self.frame:
            event_bus = self.frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("documents.indexed", self._on_document_indexed)
                await event_bus.unsubscribe("documents.deleted", self._on_document_deleted)

        self.semantic_engine = None
        self.keyword_engine = None
        self.hybrid_engine = None
        self.filter_optimizer = None

        logger.info("Search Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _on_document_indexed(self, event: dict) -> None:
        """
        Handle document indexed event.

        Could be used to:
        - Update search indexes
        - Invalidate caches
        - Trigger reindexing
        """
        doc_id = event.get("doc_id")
        logger.debug(f"Document indexed: {doc_id}")

        # TODO: Invalidate any caches for this document

    async def _on_document_deleted(self, event: dict) -> None:
        """
        Handle document deleted event.

        Could be used to:
        - Remove from search indexes
        - Clean up cache entries
        """
        doc_id = event.get("doc_id")
        logger.debug(f"Document deleted: {doc_id}")

        # TODO: Remove from any search caches

    # --- Public API for other shards ---

    async def search(self, query: str, mode: str = "hybrid", limit: int = 20, **kwargs):
        """
        Public method for other shards to perform searches.

        Args:
            query: Search query string
            mode: Search mode (hybrid, semantic, keyword)
            limit: Maximum results
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        from .models import SearchQuery, SearchMode

        try:
            search_mode = SearchMode(mode.lower())
        except ValueError:
            search_mode = SearchMode.HYBRID

        search_query = SearchQuery(
            query=query,
            mode=search_mode,
            limit=limit,
            **kwargs,
        )

        if search_mode == SearchMode.SEMANTIC and self.semantic_engine:
            return await self.semantic_engine.search(search_query)
        elif search_mode == SearchMode.KEYWORD and self.keyword_engine:
            return await self.keyword_engine.search(search_query)
        elif self.hybrid_engine:
            return await self.hybrid_engine.search(search_query)
        else:
            logger.error("No search engine available")
            return []

    async def find_similar(self, doc_id: str, limit: int = 10, min_similarity: float = 0.5):
        """
        Public method to find similar documents.

        Args:
            doc_id: Document ID to find similar documents for
            limit: Maximum results
            min_similarity: Minimum similarity score

        Returns:
            List of similar documents
        """
        if not self.semantic_engine:
            logger.error("Semantic engine not available")
            return []

        return await self.semantic_engine.find_similar(
            doc_id=doc_id,
            limit=limit,
            min_similarity=min_similarity,
        )
