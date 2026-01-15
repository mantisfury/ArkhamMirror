"""Search Shard - Semantic and keyword search for documents."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .engines import SemanticSearchEngine, KeywordSearchEngine, HybridSearchEngine, RegexSearchEngine
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
        self.regex_engine = None
        self.filter_optimizer = None
        self._db = None

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
                frame=frame,
            )
            logger.info("Semantic search engine initialized")

        if database_service:
            self.keyword_engine = KeywordSearchEngine(
                database_service=database_service,
                documents_service=documents_service,
            )
            logger.info("Keyword search engine initialized")

        if self.semantic_engine and self.keyword_engine:
            # Get embedding dimensions from vectors service for model-aware weight tuning
            embedding_dimensions = None
            if vectors_service:
                embedding_dimensions = getattr(vectors_service, '_default_dimension', None)
                logger.info(f"Detected embedding dimensions: {embedding_dimensions}")

            self.hybrid_engine = HybridSearchEngine(
                semantic_engine=self.semantic_engine,
                keyword_engine=self.keyword_engine,
                embedding_dimensions=embedding_dimensions,
            )
            logger.info("Hybrid search engine initialized with model-aware weights")

        # Initialize filter optimizer
        if database_service:
            self.filter_optimizer = FilterOptimizer(database_service)

        # Initialize regex search engine
        if database_service:
            self.regex_engine = RegexSearchEngine(
                database_service=database_service,
                documents_service=documents_service,
            )
            logger.info("Regex search engine initialized")

        # Create search schema and tables
        if database_service:
            await self._create_schema(database_service)

        # Initialize API
        init_api(
            semantic_engine=self.semantic_engine,
            keyword_engine=self.keyword_engine,
            hybrid_engine=self.hybrid_engine,
            regex_engine=self.regex_engine,
            filter_optimizer=self.filter_optimizer,
            event_bus=event_bus,
        )

        # Subscribe to document events
        if event_bus:
            await event_bus.subscribe("documents.indexed", self._on_document_indexed)
            await event_bus.subscribe("documents.deleted", self._on_document_deleted)
            # Subscribe to parse completion for auto-extraction of regex patterns
            await event_bus.subscribe("parse.document.completed", self._on_parse_completed)

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.search_shard = self

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
                await event_bus.unsubscribe("parse.document.completed", self._on_parse_completed)

        self.semantic_engine = None
        self.keyword_engine = None
        self.hybrid_engine = None
        self.regex_engine = None
        self.filter_optimizer = None

        logger.info("Search Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _create_schema(self, db) -> None:
        """Create search-related database tables."""
        self._db = db

        try:
            # Create schema for search shard
            await db.execute("CREATE SCHEMA IF NOT EXISTS arkham_search")

            # AI feedback table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_search.ai_feedback (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message_id TEXT,
                    rating TEXT NOT NULL,
                    feedback_text TEXT,
                    context JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id UUID
                )
            """)

            # Create indexes for AI feedback
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_feedback_session
                ON arkham_search.ai_feedback(session_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_feedback_rating
                ON arkham_search.ai_feedback(rating)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_feedback_created
                ON arkham_search.ai_feedback(created_at DESC)
            """)

            # Regex presets table for custom patterns
            await db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_search.regex_presets (
                    id TEXT PRIMARY KEY,
                    tenant_id UUID,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'custom',
                    flags JSONB DEFAULT '[]',
                    is_system BOOLEAN DEFAULT FALSE,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            """)

            # Regex search history for analytics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_search.regex_history (
                    id TEXT PRIMARY KEY,
                    tenant_id UUID,
                    pattern TEXT NOT NULL,
                    flags JSONB DEFAULT '[]',
                    matches_found INTEGER DEFAULT 0,
                    documents_searched INTEGER DEFAULT 0,
                    search_time_ms REAL,
                    searched_by TEXT,
                    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for regex tables
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_regex_presets_tenant
                ON arkham_search.regex_presets(tenant_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_regex_presets_category
                ON arkham_search.regex_presets(category)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_regex_history_tenant
                ON arkham_search.regex_history(tenant_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_regex_history_searched_at
                ON arkham_search.regex_history(searched_at DESC)
            """)

            # Auto-extracted pattern matches table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_search.pattern_extractions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    preset_id TEXT NOT NULL,
                    preset_name TEXT,
                    category TEXT,
                    match_text TEXT NOT NULL,
                    context TEXT,
                    page_number INTEGER,
                    chunk_id TEXT,
                    start_offset INTEGER,
                    end_offset INTEGER,
                    line_number INTEGER,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id UUID
                )
            """)

            # Indexes for pattern extractions
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_pattern_extractions_doc
                ON arkham_search.pattern_extractions(document_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_pattern_extractions_preset
                ON arkham_search.pattern_extractions(preset_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_pattern_extractions_category
                ON arkham_search.pattern_extractions(category)
            """)

            logger.info("Search schema and tables created")
        except Exception as e:
            logger.warning(f"Failed to create search schema: {e}")

    async def store_feedback(
        self,
        feedback_id: str,
        session_id: str,
        rating: str,
        message_id: str | None = None,
        feedback_text: str | None = None,
        context: dict | None = None,
    ) -> bool:
        """
        Store AI feedback in the database.

        Args:
            feedback_id: Unique feedback ID
            session_id: Session ID
            rating: Rating (up/down)
            message_id: Optional message ID
            feedback_text: Optional feedback text
            context: Optional context dict

        Returns:
            True if stored successfully
        """
        if not self._db:
            return False

        import json

        try:
            await self._db.execute(
                """
                INSERT INTO arkham_search.ai_feedback
                (id, session_id, message_id, rating, feedback_text, context)
                VALUES (:id, :session_id, :message_id, :rating, :feedback_text, :context)
                """,
                {
                    "id": feedback_id,
                    "session_id": session_id,
                    "message_id": message_id,
                    "rating": rating,
                    "feedback_text": feedback_text,
                    "context": json.dumps(context or {}),
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            return False

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
        doc_id = event.get("doc_id") or event.get("document_id")
        logger.debug(f"Document deleted: {doc_id}")

        # Clean up pattern extractions for deleted document
        if self._db and doc_id:
            try:
                await self._db.execute(
                    "DELETE FROM arkham_search.pattern_extractions WHERE document_id = :doc_id",
                    {"doc_id": doc_id}
                )
            except Exception as e:
                logger.warning(f"Failed to delete pattern extractions for {doc_id}: {e}")

    async def _on_parse_completed(self, event: dict) -> None:
        """
        Handle parse completion event - auto-extract regex patterns from document.

        Runs all system presets against the newly parsed document and stores
        the matches for quick retrieval.
        """
        import re
        import uuid

        # Handle both wrapped and unwrapped event payloads
        payload = event.get("payload", event)
        doc_id = payload.get("document_id")

        if not doc_id:
            logger.debug("No document_id in parse.document.completed event")
            return

        if not self._db or not self.regex_engine:
            logger.debug("Database or regex engine not available for pattern extraction")
            return

        logger.info(f"Auto-extracting regex patterns for document {doc_id}")

        try:
            # Fetch all chunks for this document
            chunks = await self._db.fetch_all(
                """
                SELECT id, text, chunk_index, page_number
                FROM arkham_frame.chunks
                WHERE document_id = :doc_id
                ORDER BY chunk_index
                """,
                {"doc_id": doc_id}
            )

            if not chunks:
                logger.debug(f"No chunks found for document {doc_id}")
                return

            # Get all system presets
            from .engines.regex import REGEX_PRESETS

            extractions = []
            for preset in REGEX_PRESETS:
                preset_id = preset["id"]
                preset_name = preset["name"]
                category = preset["category"]
                pattern = preset["pattern"]

                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                except re.error:
                    continue

                for chunk in chunks:
                    text = chunk["text"] or ""
                    chunk_id = chunk["id"]
                    page_number = chunk["page_number"]

                    for match in compiled.finditer(text):
                        match_text = match.group(0)
                        match_start = match.start()
                        match_end = match.end()

                        # Extract context
                        ctx_start = max(0, match_start - 50)
                        ctx_end = min(len(text), match_end + 50)
                        context = text[ctx_start:ctx_end]
                        if ctx_start > 0:
                            context = "..." + context
                        if ctx_end < len(text):
                            context = context + "..."

                        line_number = text[:match_start].count('\n') + 1

                        extractions.append({
                            "id": str(uuid.uuid4())[:12],
                            "document_id": doc_id,
                            "preset_id": preset_id,
                            "preset_name": preset_name,
                            "category": category,
                            "match_text": match_text,
                            "context": context,
                            "page_number": page_number,
                            "chunk_id": chunk_id,
                            "start_offset": match_start,
                            "end_offset": match_end,
                            "line_number": line_number,
                        })

            # Store extractions in batch
            if extractions:
                for ext in extractions:
                    await self._db.execute(
                        """
                        INSERT INTO arkham_search.pattern_extractions
                        (id, document_id, preset_id, preset_name, category, match_text,
                         context, page_number, chunk_id, start_offset, end_offset, line_number)
                        VALUES (:id, :document_id, :preset_id, :preset_name, :category, :match_text,
                                :context, :page_number, :chunk_id, :start_offset, :end_offset, :line_number)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        ext
                    )

                logger.info(f"Auto-extracted {len(extractions)} pattern matches from document {doc_id}")

                # Emit event for pattern extraction completion
                event_bus = self.frame.get_service("events") if self.frame else None
                if event_bus:
                    await event_bus.emit(
                        "search.patterns.extracted",
                        {
                            "document_id": doc_id,
                            "total_matches": len(extractions),
                            "categories": list(set(e["category"] for e in extractions)),
                        },
                        source="search-shard",
                    )

        except Exception as e:
            logger.error(f"Failed to extract patterns for document {doc_id}: {e}", exc_info=True)

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
