"""Contradictions Shard - Multi-document contradiction detection."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router, set_db_service
from .detector import ContradictionDetector, ChainDetector
from .storage import ContradictionStore

logger = logging.getLogger(__name__)

# SQL for schema creation
SCHEMA_SQL = """
-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS arkham_contradictions;

-- Main contradictions table
CREATE TABLE IF NOT EXISTS arkham_contradictions.contradictions (
    id TEXT PRIMARY KEY,
    doc_a_id TEXT NOT NULL,
    doc_b_id TEXT NOT NULL,
    claim_a TEXT NOT NULL,
    claim_b TEXT NOT NULL,
    claim_a_location TEXT DEFAULT '',
    claim_b_location TEXT DEFAULT '',
    contradiction_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT DEFAULT 'detected',
    explanation TEXT DEFAULT '',
    confidence_score REAL DEFAULT 1.0,
    detected_by TEXT DEFAULT 'system',
    analyst_notes TEXT DEFAULT '[]',
    chain_id TEXT,
    related_contradictions TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    confirmed_by TEXT,
    confirmed_at TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Contradiction chains table
CREATE TABLE IF NOT EXISTS arkham_contradictions.chains (
    id TEXT PRIMARY KEY,
    contradiction_ids TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    severity TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_contradictions_doc_a ON arkham_contradictions.contradictions(doc_a_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_doc_b ON arkham_contradictions.contradictions(doc_b_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON arkham_contradictions.contradictions(status);
CREATE INDEX IF NOT EXISTS idx_contradictions_chain ON arkham_contradictions.contradictions(chain_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_severity ON arkham_contradictions.contradictions(severity);
CREATE INDEX IF NOT EXISTS idx_contradictions_type ON arkham_contradictions.contradictions(contradiction_type);
"""


class ContradictionsShard(ArkhamShard):
    """
    Contradictions shard for ArkhamFrame.

    Provides multi-document contradiction detection and analysis
    for investigative journalists.

    Features:
    - Multi-stage detection: claim extraction -> semantic matching -> LLM verification
    - Configurable severity thresholds
    - Background processing via worker pools
    - Chain detection (A contradicts B, B contradicts C)
    - Analyst workflow: confirm, dismiss, add notes
    - Multiple detection strategies:
      * Direct contradiction: "X happened" vs "X did not happen"
      * Temporal contradiction: Different dates for same event
      * Numeric contradiction: Different figures/amounts
      * Entity contradiction: Different people/places attributed
    """

    name = "contradictions"
    version = "0.1.0"
    description = "Contradiction detection engine for multi-document analysis"

    def __init__(self):
        super().__init__()
        self.detector: ContradictionDetector | None = None
        self.chain_detector: ChainDetector | None = None
        self.storage: ContradictionStore | None = None
        self._frame = None
        self._event_bus = None
        self._llm_service = None
        self._embedding_service = None
        self._db_service = None
        self._worker_service = None

    async def initialize(self, frame) -> None:
        """
        Initialize the Contradictions shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Contradictions Shard...")

        # Get Frame services
        self._event_bus = frame.get_service("events")
        self._llm_service = frame.get_service("llm")
        self._embedding_service = frame.get_service("embeddings")
        self._db_service = frame.get_service("database")
        self._worker_service = frame.get_service("workers")

        if not self._db_service:
            logger.warning("Database service not available - using in-memory storage")
        else:
            # Create database schema
            await self._create_schema()

        if not self._llm_service:
            logger.warning("LLM service not available - using heuristic detection only")

        if not self._embedding_service:
            logger.warning("Embedding service not available - using keyword matching")

        # Create components
        self.detector = ContradictionDetector(
            embedding_service=self._embedding_service,
            llm_service=self._llm_service,
        )

        self.chain_detector = ChainDetector()

        self.storage = ContradictionStore(
            db_service=self._db_service,
        )

        # Initialize API with our instances and database service
        init_api(
            detector=self.detector,
            storage=self.storage,
            event_bus=self._event_bus,
            chain_detector=self.chain_detector,
        )

        # Set database service for document fetching in API
        set_db_service(self._db_service)

        # Subscribe to events
        if self._event_bus:
            await self._subscribe_to_events()

        logger.info("Contradictions Shard initialized")

    async def _create_schema(self) -> None:
        """Create the database schema for contradictions."""
        if not self._db_service:
            return

        try:
            # Execute schema creation SQL
            for statement in SCHEMA_SQL.split(';'):
                statement = statement.strip()
                if statement:
                    await self._db_service.execute(statement)
            logger.info("Contradictions schema created/verified")
        except Exception as e:
            logger.error(f"Failed to create contradictions schema: {e}")
            raise

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Contradictions Shard...")

        # Unsubscribe from events
        if self._event_bus:
            await self._unsubscribe_from_events()

        # Clear components
        self.detector = None
        self.chain_detector = None
        self.storage = None

        logger.info("Contradictions Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # --- Event Subscriptions ---

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events."""
        if not self._event_bus:
            return

        # Subscribe to document events for background analysis
        # Use correct Frame event names
        await self._event_bus.subscribe(
            "documents.document.created",
            self._on_document_created,
        )

        await self._event_bus.subscribe(
            "documents.document.updated",
            self._on_document_updated,
        )

        # Subscribe to embedding completion (documents are ready for analysis)
        await self._event_bus.subscribe(
            "embed.document.completed",
            self._on_document_embedded,
        )

        logger.info("Subscribed to events: documents.document.created, documents.document.updated, embed.document.completed")

    async def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from events."""
        if not self._event_bus:
            return

        try:
            await self._event_bus.unsubscribe("documents.document.created", self._on_document_created)
            await self._event_bus.unsubscribe("documents.document.updated", self._on_document_updated)
            await self._event_bus.unsubscribe("embed.document.completed", self._on_document_embedded)
        except Exception as e:
            logger.warning(f"Error unsubscribing from events: {e}")

        logger.info("Unsubscribed from events")

    # --- Event Handlers ---

    async def _on_document_created(self, event_data: dict) -> None:
        """
        Handle document creation event.

        Logs the event - actual analysis happens after embedding is complete.
        """
        doc_id = event_data.get("document_id") or event_data.get("id")
        if not doc_id:
            return

        logger.info(f"Document created: {doc_id} - will analyze after embedding completes")

    async def _on_document_updated(self, event_data: dict) -> None:
        """
        Handle document update event.

        Triggers re-analysis if content changed.
        """
        doc_id = event_data.get("document_id") or event_data.get("id")
        if not doc_id:
            return

        logger.info(f"Document updated: {doc_id} - checking for re-analysis")

        # Check if we have existing contradictions for this document
        if self.storage:
            existing = await self.storage.get_by_document(doc_id)
            if existing:
                logger.info(f"Document {doc_id} has {len(existing)} existing contradictions - may need re-analysis")
                # Mark existing contradictions for review
                for c in existing:
                    if c.status.value == "confirmed":
                        # Add note about document update
                        await self.storage.add_note(
                            c.id,
                            f"Source document {doc_id} was updated - may require review",
                            analyst_id="system"
                        )

    async def _on_document_embedded(self, event_data: dict) -> None:
        """
        Handle document embedding completion event.

        This is the best time to analyze for contradictions since
        the document text is available and embeddings are ready.
        """
        doc_id = event_data.get("document_id") or event_data.get("id")
        if not doc_id:
            return

        logger.info(f"Document embedded: {doc_id} - running contradiction analysis")

        if not self.detector or not self.storage or not self._db_service:
            logger.warning("Cannot analyze - detector, storage, or db not available")
            return

        try:
            # Get all other document IDs
            other_docs = await self._db_service.fetch_all(
                """SELECT id FROM arkham_frame.documents
                   WHERE id != :id
                   ORDER BY created_at DESC
                   LIMIT 50""",
                {"id": doc_id}
            )

            if not other_docs:
                logger.info(f"No other documents to compare against {doc_id}")
                return

            # Analyze against each document
            total_contradictions = 0
            for other in other_docs:
                other_id = other.get("id")
                if not other_id:
                    continue

                try:
                    # Use the public analyze_pair method
                    results = await self.analyze_pair(
                        doc_a_id=doc_id,
                        doc_b_id=other_id,
                        threshold=0.7,
                        use_llm=self._llm_service is not None
                    )
                    total_contradictions += len(results)
                except Exception as e:
                    logger.debug(f"Failed to analyze {doc_id} vs {other_id}: {e}")

            if total_contradictions > 0:
                logger.info(f"Found {total_contradictions} contradictions for document {doc_id}")

                # Emit event
                if self._event_bus:
                    await self._event_bus.emit(
                        "contradictions.detected",
                        {
                            "document_id": doc_id,
                            "count": total_contradictions,
                        },
                        source="contradictions-shard",
                    )

        except Exception as e:
            logger.error(f"Error analyzing document {doc_id} for contradictions: {e}")

    # --- Public API for other shards ---

    async def analyze_pair(
        self, doc_a_id: str, doc_b_id: str, threshold: float = 0.7, use_llm: bool = True
    ) -> list[dict]:
        """
        Public method for other shards to analyze document pair.

        Args:
            doc_a_id: First document ID
            doc_b_id: Second document ID
            threshold: Similarity threshold (0.0 to 1.0)
            use_llm: Use LLM for verification

        Returns:
            List of detected contradictions (as dicts)
        """
        if not self.detector or not self.storage:
            raise RuntimeError("Contradictions Shard not initialized")

        # Fetch document content from Frame
        doc_a_content = await self._get_document_content(doc_a_id)
        doc_b_content = await self._get_document_content(doc_b_id)

        if not doc_a_content or not doc_b_content:
            raise RuntimeError(f"Could not fetch document content for analysis")

        doc_a_text = doc_a_content["content"]
        doc_b_text = doc_b_content["content"]

        # Extract claims
        if use_llm and self._llm_service:
            claims_a = await self.detector.extract_claims_llm(doc_a_text, doc_a_id)
            claims_b = await self.detector.extract_claims_llm(doc_b_text, doc_b_id)
        else:
            claims_a = self.detector.extract_claims_simple(doc_a_text, doc_a_id)
            claims_b = self.detector.extract_claims_simple(doc_b_text, doc_b_id)

        # Find similar claim pairs
        similar_pairs = await self.detector.find_similar_claims(
            claims_a, claims_b, threshold=threshold
        )

        # Verify contradictions
        contradictions = []
        for claim_a, claim_b, similarity in similar_pairs:
            contradiction = await self.detector.verify_contradiction(claim_a, claim_b, similarity)
            if contradiction:
                await self.storage.create(contradiction)
                contradictions.append(
                    {
                        "id": contradiction.id,
                        "claim_a": contradiction.claim_a,
                        "claim_b": contradiction.claim_b,
                        "type": contradiction.contradiction_type.value,
                        "severity": contradiction.severity.value,
                        "confidence": contradiction.confidence_score,
                    }
                )

        return contradictions

    async def _get_document_content(self, doc_id: str) -> dict | None:
        """
        Fetch document content from Frame database.

        Gets document metadata and combines chunk text for content.
        Matches the implementation in api.py for consistency.
        """
        if not self._db_service:
            return None

        try:
            # Get document metadata
            doc_result = await self._db_service.fetch_one(
                "SELECT id, filename FROM arkham_frame.documents WHERE id = :id",
                {"id": doc_id}
            )

            if not doc_result:
                logger.warning(f"Document not found: {doc_id}")
                return None

            # Get all chunks for the document, ordered by chunk_index
            chunks = await self._db_service.fetch_all(
                """SELECT text FROM arkham_frame.chunks
                   WHERE document_id = :id
                   ORDER BY chunk_index""",
                {"id": doc_id}
            )

            # Combine chunk text
            content = "\n\n".join(c["text"] for c in chunks if c.get("text"))

            if not content:
                logger.warning(f"Document {doc_id} has no chunk content")
                return None

            return {
                "id": doc_id,
                "content": content,
                "title": doc_result.get("filename", f"Document {doc_id}")
            }

        except Exception as e:
            logger.error(f"Failed to fetch document {doc_id}: {e}")
            return None

    async def get_document_contradictions(self, document_id: str) -> list[dict]:
        """
        Public method to get contradictions for a document.

        Args:
            document_id: Document ID

        Returns:
            List of contradictions (as dicts)
        """
        if not self.storage:
            raise RuntimeError("Contradictions Shard not initialized")

        contradictions = await self.storage.get_by_document(document_id)

        return [
            {
                "id": c.id,
                "doc_a_id": c.doc_a_id,
                "doc_b_id": c.doc_b_id,
                "claim_a": c.claim_a,
                "claim_b": c.claim_b,
                "type": c.contradiction_type.value,
                "severity": c.severity.value,
                "status": c.status.value,
                "confidence": c.confidence_score,
            }
            for c in contradictions
        ]

    async def get_statistics(self) -> dict:
        """
        Public method to get contradiction statistics.

        Returns:
            Statistics dictionary
        """
        if not self.storage:
            raise RuntimeError("Contradictions Shard not initialized")

        return await self.storage.get_statistics()

    async def detect_chains(self) -> list[dict]:
        """
        Public method to detect contradiction chains.

        Returns:
            List of detected chains (as dicts)
        """
        if not self.storage or not self.chain_detector:
            raise RuntimeError("Contradictions Shard not initialized")

        # Get all contradictions except dismissed
        from .models import ContradictionStatus

        contradictions = await self.storage.search(status=None)
        contradictions = [
            c for c in contradictions if c.status != ContradictionStatus.DISMISSED
        ]

        # Detect chains
        chains = self.chain_detector.detect_chains(contradictions)

        # Create chain objects
        from .models import ContradictionChain
        import uuid

        created_chains = []
        for chain_ids in chains:
            chain = ContradictionChain(
                id=str(uuid.uuid4()),
                contradiction_ids=chain_ids,
                description=f"Chain of {len(chain_ids)} contradictions",
            )
            await self.storage.create_chain(chain)
            created_chains.append(
                {
                    "id": chain.id,
                    "contradiction_count": len(chain.contradiction_ids),
                    "contradictions": chain.contradiction_ids,
                }
            )

        return created_chains
