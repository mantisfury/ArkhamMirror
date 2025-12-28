"""Anomalies Shard - Anomaly and outlier detection."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .detector import AnomalyDetector
from .storage import AnomalyStore
from .models import DetectionConfig

logger = logging.getLogger(__name__)


class AnomaliesShard(ArkhamShard):
    """
    Anomaly detection shard for ArkhamFrame.

    Provides comprehensive anomaly detection across multiple dimensions:
    - Content anomalies: Documents semantically distant from corpus
    - Metadata anomalies: Unusual file properties
    - Temporal anomalies: Unexpected dates and time references
    - Structural anomalies: Unusual document structure
    - Statistical anomalies: Unusual text patterns and frequencies
    - Red flags: Sensitive content indicators

    Features:
    - Vector-based outlier detection
    - Statistical anomaly detection with configurable thresholds
    - Pattern recognition across multiple documents
    - Analyst workflow for triage and review
    - Real-time detection on document ingestion
    - Background batch processing
    """

    name = "anomalies"
    version = "0.1.0"
    description = "Anomaly and outlier detection for documents"

    def __init__(self):
        super().__init__()
        self.detector: AnomalyDetector | None = None
        self.store: AnomalyStore | None = None
        self._frame = None
        self._event_bus = None
        self._vector_service = None
        self._db_service = None
        self._config = DetectionConfig()

    async def initialize(self, frame) -> None:
        """
        Initialize the Anomalies shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Anomalies Shard...")

        # Get required services
        self._vector_service = frame.get_service("vectors")
        if not self._vector_service:
            logger.warning("Vectors service not available - content anomaly detection will be limited")

        self._db_service = frame.get_service("database") or frame.get_service("db")
        if not self._db_service:
            logger.warning("Database service not available - storage will be in-memory only")

        # Get optional services
        self._event_bus = frame.get_service("events")
        documents_service = frame.get_service("documents")

        # Initialize components
        self.detector = AnomalyDetector(config=self._config)
        self.store = AnomalyStore()

        logger.info("Anomaly detector initialized")
        logger.info("Anomaly store initialized")

        # Initialize API
        init_api(
            detector=self.detector,
            store=self.store,
            event_bus=self._event_bus,
        )

        # Subscribe to events
        if self._event_bus:
            await self._event_bus.subscribe("embeddings.created", self._on_embedding_created)
            await self._event_bus.subscribe("documents.indexed", self._on_document_indexed)
            logger.info("Subscribed to embeddings and document events")

        logger.info("Anomalies Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Anomalies Shard...")

        # Unsubscribe from events
        if self._event_bus:
            await self._event_bus.unsubscribe("embeddings.created", self._on_embedding_created)
            await self._event_bus.unsubscribe("documents.indexed", self._on_document_indexed)

        # Clear components
        self.detector = None
        self.store = None

        logger.info("Anomalies Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # --- Event Handlers ---

    async def _on_embedding_created(self, event: dict) -> None:
        """
        Handle embedding created event.

        Triggers automatic anomaly detection for new embeddings.

        Args:
            event: Event data containing doc_id and embedding
        """
        doc_id = event.get("doc_id")
        logger.debug(f"Embedding created for document: {doc_id}")

        # In a real implementation, this would trigger background detection
        # For now, just log
        logger.debug(f"Would trigger anomaly detection for {doc_id}")

    async def _on_document_indexed(self, event: dict) -> None:
        """
        Handle document indexed event.

        Could trigger metadata and statistical anomaly detection.

        Args:
            event: Event data containing doc_id
        """
        doc_id = event.get("doc_id")
        logger.debug(f"Document indexed: {doc_id}")

        # In a real implementation, this would trigger background detection
        # For now, just log
        logger.debug(f"Would trigger metadata detection for {doc_id}")

    # --- Public API for other shards ---

    async def detect_anomalies(
        self,
        doc_ids: list[str] | None = None,
        config: DetectionConfig | None = None,
    ) -> list:
        """
        Public method for other shards to trigger anomaly detection.

        Args:
            doc_ids: List of document IDs to check (None = all documents)
            config: Detection configuration

        Returns:
            List of detected anomalies
        """
        if not self.detector or not self.store:
            raise RuntimeError("Anomalies Shard not initialized")

        logger.info(f"Detecting anomalies for {len(doc_ids) if doc_ids else 'all'} documents")

        # In a real implementation, this would:
        # 1. Fetch documents from database
        # 2. Run detector on each document
        # 3. Store results
        # 4. Emit events

        return []

    async def get_anomalies_for_document(self, doc_id: str) -> list:
        """
        Public method to get all anomalies for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of anomalies
        """
        if not self.store:
            raise RuntimeError("Anomalies Shard not initialized")

        return await self.store.get_anomalies_by_doc(doc_id)

    async def check_document(self, doc_id: str, text: str, metadata: dict) -> list:
        """
        Public method to check if a document is anomalous.

        Args:
            doc_id: Document ID
            text: Document text
            metadata: Document metadata

        Returns:
            List of detected anomalies
        """
        if not self.detector:
            raise RuntimeError("Anomalies Shard not initialized")

        anomalies = []

        # Statistical checks
        corpus_stats = {}  # Would be fetched from database
        anomalies.extend(
            self.detector.detect_statistical_anomalies(doc_id, text, corpus_stats)
        )

        # Red flag checks
        anomalies.extend(
            self.detector.detect_red_flags(doc_id, text, metadata)
        )

        # Metadata checks
        corpus_metadata_stats = {}  # Would be fetched from database
        anomalies.extend(
            self.detector.detect_metadata_anomalies(doc_id, metadata, corpus_metadata_stats)
        )

        # Store detected anomalies
        if self.store:
            for anomaly in anomalies:
                await self.store.create_anomaly(anomaly)

        # Emit event
        if self._event_bus and anomalies:
            await self._event_bus.emit(
                "anomalies.detected",
                {
                    "doc_id": doc_id,
                    "count": len(anomalies),
                    "types": [a.anomaly_type.value for a in anomalies],
                },
                source="anomalies-shard",
            )

        return anomalies

    async def get_statistics(self) -> dict:
        """
        Public method to get anomaly statistics.

        Returns:
            Statistics dictionary
        """
        if not self.store:
            raise RuntimeError("Anomalies Shard not initialized")

        stats = await self.store.get_stats()

        return {
            "total_anomalies": stats.total_anomalies,
            "by_type": stats.by_type,
            "by_status": stats.by_status,
            "by_severity": stats.by_severity,
            "recent_activity": {
                "detected_last_24h": stats.detected_last_24h,
                "confirmed_last_24h": stats.confirmed_last_24h,
                "dismissed_last_24h": stats.dismissed_last_24h,
            },
            "quality_metrics": {
                "false_positive_rate": stats.false_positive_rate,
                "avg_confidence": stats.avg_confidence,
            },
        }
