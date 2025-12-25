"""Contradictions Shard - Multi-document contradiction detection."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .detector import ContradictionDetector, ChainDetector
from .storage import ContradictionStore

logger = logging.getLogger(__name__)


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

        # Initialize API with our instances
        init_api(
            detector=self.detector,
            storage=self.storage,
            event_bus=self._event_bus,
            chain_detector=self.chain_detector,
        )

        # Subscribe to events
        if self._event_bus:
            await self._subscribe_to_events()

        logger.info("Contradictions Shard initialized")

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
        await self._event_bus.subscribe(
            "document.ingested",
            self._on_document_ingested,
        )

        await self._event_bus.subscribe(
            "document.updated",
            self._on_document_updated,
        )

        # Subscribe to LLM analysis completion
        await self._event_bus.subscribe(
            "llm.analysis.completed",
            self._on_llm_analysis_completed,
        )

        logger.info("Subscribed to events: document.ingested, document.updated, llm.analysis.completed")

    async def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from events."""
        if not self._event_bus:
            return

        await self._event_bus.unsubscribe("document.ingested", self._on_document_ingested)
        await self._event_bus.unsubscribe("document.updated", self._on_document_updated)
        await self._event_bus.unsubscribe("llm.analysis.completed", self._on_llm_analysis_completed)

        logger.info("Unsubscribed from events")

    # --- Event Handlers ---

    async def _on_document_ingested(self, event_data: dict) -> None:
        """
        Handle document ingestion event.

        Triggers background analysis against existing documents.
        """
        doc_id = event_data.get("document_id")
        if not doc_id:
            return

        logger.info(f"Document ingested: {doc_id} - scheduling contradiction analysis")

        # TODO: Schedule background analysis job via worker service
        # For now, just log the event
        if self._worker_service:
            # Submit background job to analyze this document against all others
            # await self._worker_service.submit_job(
            #     "contradiction_analysis",
            #     document_id=doc_id,
            # )
            pass

    async def _on_document_updated(self, event_data: dict) -> None:
        """
        Handle document update event.

        May trigger re-analysis if content changed.
        """
        doc_id = event_data.get("document_id")
        if not doc_id:
            return

        logger.info(f"Document updated: {doc_id}")

        # TODO: Determine if re-analysis is needed based on what changed
        # If content changed significantly, trigger re-analysis

    async def _on_llm_analysis_completed(self, event_data: dict) -> None:
        """
        Handle LLM analysis completion event.

        Can be used for contradiction verification tasks.
        """
        job_id = event_data.get("job_id")
        result = event_data.get("result")

        logger.debug(f"LLM analysis completed: job={job_id}")

        # TODO: Process LLM results if they're for contradiction verification

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

        # TODO: Fetch actual document content from Frame
        doc_a_text = f"Document {doc_a_id} content"
        doc_b_text = f"Document {doc_b_id} content"

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
                self.storage.create(contradiction)
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

    def get_document_contradictions(self, document_id: str) -> list[dict]:
        """
        Public method to get contradictions for a document.

        Args:
            document_id: Document ID

        Returns:
            List of contradictions (as dicts)
        """
        if not self.storage:
            raise RuntimeError("Contradictions Shard not initialized")

        contradictions = self.storage.get_by_document(document_id)

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

    def get_statistics(self) -> dict:
        """
        Public method to get contradiction statistics.

        Returns:
            Statistics dictionary
        """
        if not self.storage:
            raise RuntimeError("Contradictions Shard not initialized")

        return self.storage.get_statistics()

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

        contradictions = self.storage.search(status=None)
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
            self.storage.create_chain(chain)
            created_chains.append(
                {
                    "id": chain.id,
                    "contradiction_count": len(chain.contradiction_ids),
                    "contradictions": chain.contradiction_ids,
                }
            )

        return created_chains
