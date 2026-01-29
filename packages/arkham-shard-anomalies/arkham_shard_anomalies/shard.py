"""Anomalies Shard - Anomaly and outlier detection."""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .detector import AnomalyDetector
from .hidden_content import HiddenContentDetector
from .storage import AnomalyStore
from .models import DetectionConfig, Anomaly, HiddenContentConfig, HiddenContentScan

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
        self.hidden_detector: HiddenContentDetector | None = None
        self.store: AnomalyStore | None = None
        self._frame = None
        self._event_bus = None
        self._vector_service = None
        self._db_service = None
        self._workers = None
        self._storage = None
        self._config = DetectionConfig()
        self._hidden_config = HiddenContentConfig()

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
            # Try direct database attribute
            self._db_service = getattr(frame, "database", None)

        if not self._db_service:
            logger.warning("Database service not available - storage will be in-memory only")

        # Get optional services
        self._event_bus = frame.get_service("events")
        self._workers = frame.get_service("workers")
        self._storage = frame.get_service("storage")

        # Create database schema
        await self._create_schema()

        # Initialize components
        self.detector = AnomalyDetector(config=self._config)
        self.hidden_detector = HiddenContentDetector(config=self._hidden_config)
        self.store = AnomalyStore(db=self._db_service)

        logger.info("Anomaly detector initialized")
        logger.info("Hidden content detector initialized")
        logger.info("Anomaly store initialized")

        # Initialize API
        init_api(
            detector=self.detector,
            store=self.store,
            event_bus=self._event_bus,
            db=self._db_service,
            vectors=self._vector_service,
            hidden_detector=self.hidden_detector,
            storage=self._storage,
        )

        # Subscribe to events (correct event names from system)
        if self._event_bus:
            await self._event_bus.subscribe("embed.document.completed", self._on_embedding_created)
            await self._event_bus.subscribe("documents.metadata.updated", self._on_document_indexed)
            logger.info("Subscribed to embed.document.completed and documents.metadata.updated events")

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.anomalies_shard = self

        logger.info("Anomalies Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Anomalies Shard...")

        # Unsubscribe from events
        if self._event_bus:
            await self._event_bus.unsubscribe("embed.document.completed", self._on_embedding_created)
            await self._event_bus.unsubscribe("documents.metadata.updated", self._on_document_indexed)

        # Clear components
        self.detector = None
        self.store = None

        logger.info("Anomalies Shard shutdown complete")

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for anomalies shard."""
        if not self._db_service:
            logger.warning("Database not available, skipping schema creation")
            return

        # Main anomalies table
        await self._db_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_anomalies (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                project_id TEXT,
                anomaly_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'detected',
                score REAL DEFAULT 0.0,
                confidence REAL DEFAULT 1.0,
                title TEXT,
                description TEXT,
                explanation TEXT,
                field_name TEXT,
                expected_range TEXT,
                actual_value TEXT,
                evidence TEXT DEFAULT '{}',
                details TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                detected_at TEXT,
                reviewed_at TEXT,
                reviewed_by TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Analyst notes table
        await self._db_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_anomaly_notes (
                id TEXT PRIMARY KEY,
                anomaly_id TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (anomaly_id) REFERENCES arkham_anomalies(id)
            )
        """)

        # Patterns table for detected patterns across anomalies
        await self._db_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_anomaly_patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                description TEXT,
                anomaly_ids TEXT DEFAULT '[]',
                doc_ids TEXT DEFAULT '[]',
                frequency INTEGER DEFAULT 0,
                confidence REAL DEFAULT 1.0,
                detected_at TEXT,
                notes TEXT
            )
        """)

        # Create indexes for common queries
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_doc_id ON arkham_anomalies(doc_id)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_type ON arkham_anomalies(anomaly_type)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_status ON arkham_anomalies(status)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON arkham_anomalies(severity)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_project ON arkham_anomalies(project_id)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_notes_anomaly ON arkham_anomaly_notes(anomaly_id)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db_service.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_anomalies', 'arkham_anomaly_notes', 'arkham_anomaly_patterns'];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_anomalies_tenant
            ON arkham_anomalies(tenant_id)
        """)

        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_anomaly_notes_tenant
            ON arkham_anomaly_notes(tenant_id)
        """)

        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_anomaly_patterns_tenant
            ON arkham_anomaly_patterns(tenant_id)
        """)

        # ===========================================
        # Hidden Content Detection Tables
        # ===========================================

        # Create schema for new tables (following project conventions)
        await self._db_service.execute("""
            CREATE SCHEMA IF NOT EXISTS arkham_anomalies
        """)

        # Hidden content scans table
        await self._db_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_anomalies.hidden_content_scans (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                scan_type TEXT NOT NULL,
                scan_status TEXT DEFAULT 'pending',
                findings TEXT DEFAULT '[]',
                entropy_score REAL,
                entropy_regions TEXT DEFAULT '[]',
                magic_expected TEXT,
                magic_actual TEXT,
                file_signature BYTEA,
                lsb_analysis TEXT DEFAULT '{}',
                stego_indicators TEXT DEFAULT '[]',
                stego_confidence REAL DEFAULT 0.0,
                created_at TEXT,
                completed_at TEXT,
                metadata TEXT DEFAULT '{}',
                tenant_id UUID
            )
        """)

        # File signatures table for corpus comparison
        await self._db_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_anomalies.file_signatures (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL UNIQUE,
                file_hash_md5 TEXT,
                file_hash_sha256 TEXT,
                file_hash_sha512 TEXT,
                magic_type TEXT,
                mime_type TEXT,
                file_size BIGINT,
                entropy_global REAL,
                entropy_chunks TEXT DEFAULT '[]',
                header_bytes BYTEA,
                trailer_bytes BYTEA,
                created_at TEXT,
                tenant_id UUID
            )
        """)

        # Indexes for hidden content tables
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_hidden_scans_doc
            ON arkham_anomalies.hidden_content_scans(doc_id)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_hidden_scans_type
            ON arkham_anomalies.hidden_content_scans(scan_type)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_hidden_scans_status
            ON arkham_anomalies.hidden_content_scans(scan_status)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_hidden_scans_tenant
            ON arkham_anomalies.hidden_content_scans(tenant_id)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_sigs_doc
            ON arkham_anomalies.file_signatures(doc_id)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_sigs_hash
            ON arkham_anomalies.file_signatures(file_hash_sha256)
        """)
        await self._db_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_sigs_tenant
            ON arkham_anomalies.file_signatures(tenant_id)
        """)

        logger.debug("Anomalies schema created/verified")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def delete_data_for_project(self, project_id: str) -> None:
        """
        Delete all anomaly data for a project. Called when a project is deleted.

        Removes anomalies, notes, and patterns for the project.
        """
        if not self._db_service:
            return
        try:
            # Delete notes and patterns that reference project anomalies, then anomalies
            await self._db_service.execute(
                "DELETE FROM arkham_anomaly_notes WHERE anomaly_id IN (SELECT id FROM arkham_anomalies WHERE project_id = :project_id)",
                {"project_id": project_id},
            )
            await self._db_service.execute(
                "DELETE FROM arkham_anomaly_patterns WHERE anomaly_id IN (SELECT id FROM arkham_anomalies WHERE project_id = :project_id)",
                {"project_id": project_id},
            )
            await self._db_service.execute(
                "DELETE FROM arkham_anomalies WHERE project_id = :project_id",
                {"project_id": project_id},
            )
            logger.info(f"Deleted anomaly data for project {project_id}")
        except Exception as e:
            logger.warning("Failed to delete anomaly data for project %s: %s", project_id, e)

    # --- Event Handlers ---

    async def _on_embedding_created(self, event: dict) -> None:
        """
        Handle embedding created event.

        Triggers automatic anomaly detection for new embeddings using
        a hybrid approach:
        - Quick sync checks (red flags, basic stats) happen immediately
        - Deep analysis (content anomalies, vector-based) queued as background job

        Args:
            event: Event data containing doc_id and embedding
        """
        doc_id = event.get("doc_id")
        if not doc_id:
            return

        logger.debug(f"Embedding created for document: {doc_id}")

        try:
            # Fetch document content
            text, metadata = await self._fetch_document_content(doc_id)
            if not text:
                logger.debug(f"No text content found for document {doc_id}")
                return

            # Run quick red flag detection (sync) - fast, no corpus comparison needed
            if self.detector and self.store:
                quick_anomalies = self.detector.detect_red_flags(doc_id, text, metadata)
                for anomaly in quick_anomalies:
                    await self.store.create_anomaly(anomaly)

                if quick_anomalies:
                    logger.info(f"Detected {len(quick_anomalies)} red flag anomalies for {doc_id}")

                    # Emit event for quick detections
                    if self._event_bus:
                        await self._event_bus.emit(
                            "anomalies.detected",
                            {
                                "doc_id": doc_id,
                                "count": len(quick_anomalies),
                                "types": [a.anomaly_type.value for a in quick_anomalies],
                                "detection_phase": "quick",
                            },
                            source="anomalies-shard",
                        )

            # Queue deep analysis if workers available
            if self._workers:
                try:
                    await self._workers.enqueue("anomaly-detection", {
                        "doc_id": doc_id,
                        "detection_types": ["content", "statistical", "metadata"],
                    })
                    logger.debug(f"Queued deep analysis for {doc_id}")
                except Exception as worker_err:
                    logger.warning(f"Failed to queue deep analysis: {worker_err}")
                    # Fall back to sync deep analysis
                    await self._run_deep_analysis(doc_id, text, metadata)
            else:
                # No workers available - run deep analysis synchronously
                await self._run_deep_analysis(doc_id, text, metadata)

        except Exception as e:
            logger.error(f"Event handler error for {doc_id}: {e}", exc_info=True)

    async def _on_document_indexed(self, event: dict) -> None:
        """
        Handle document indexed event.

        Triggers metadata and statistical anomaly detection using
        a hybrid approach similar to embedding events.

        Args:
            event: Event data containing doc_id
        """
        doc_id = event.get("doc_id")
        if not doc_id:
            return

        logger.debug(f"Document indexed: {doc_id}")

        try:
            # Fetch document content
            text, metadata = await self._fetch_document_content(doc_id)
            if not text:
                logger.debug(f"No text content found for document {doc_id}")
                return

            # Run quick red flag detection (sync)
            if self.detector and self.store:
                quick_anomalies = self.detector.detect_red_flags(doc_id, text, metadata)
                for anomaly in quick_anomalies:
                    await self.store.create_anomaly(anomaly)

                if quick_anomalies:
                    logger.info(f"Detected {len(quick_anomalies)} red flag anomalies for {doc_id}")

                    if self._event_bus:
                        await self._event_bus.emit(
                            "anomalies.detected",
                            {
                                "doc_id": doc_id,
                                "count": len(quick_anomalies),
                                "types": [a.anomaly_type.value for a in quick_anomalies],
                                "detection_phase": "quick",
                            },
                            source="anomalies-shard",
                        )

            # Queue deep analysis for metadata-focused detection
            if self._workers:
                try:
                    await self._workers.enqueue("anomaly-detection", {
                        "doc_id": doc_id,
                        "detection_types": ["metadata", "statistical"],
                    })
                    logger.debug(f"Queued metadata analysis for {doc_id}")
                except Exception as worker_err:
                    logger.warning(f"Failed to queue metadata analysis: {worker_err}")
                    await self._run_deep_analysis(doc_id, text, metadata)
            else:
                await self._run_deep_analysis(doc_id, text, metadata)

        except Exception as e:
            logger.error(f"Event handler error for {doc_id}: {e}", exc_info=True)

    async def _fetch_document_content(self, doc_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Fetch document text and metadata from the database.

        Content is stored in chunks, not in the documents table.

        Args:
            doc_id: Document ID

        Returns:
            Tuple of (text, metadata) or (None, {}) if not found
        """
        if not self._db_service:
            return None, {}

        try:
            # Get document metadata
            doc_row = await self._db_service.fetch_one(
                """SELECT id, filename, file_size, mime_type, created_at, metadata
                   FROM arkham_frame.documents WHERE id = :doc_id""",
                {"doc_id": doc_id}
            )

            if not doc_row:
                return None, {}

            metadata = {}

            # Parse stored metadata JSON
            if doc_row.get("metadata"):
                try:
                    if isinstance(doc_row["metadata"], str):
                        metadata = json.loads(doc_row["metadata"])
                    else:
                        metadata = dict(doc_row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            # Add file info to metadata
            metadata["file_name"] = doc_row.get("filename")
            metadata["file_size"] = doc_row.get("file_size")
            metadata["file_type"] = doc_row.get("mime_type")
            metadata["created_at"] = doc_row.get("created_at")

            # Get content from chunks
            chunk_rows = await self._db_service.fetch_all(
                """SELECT text FROM arkham_frame.chunks
                   WHERE document_id = :doc_id
                   ORDER BY chunk_index""",
                {"doc_id": doc_id}
            )

            if not chunk_rows:
                return None, metadata

            # Concatenate all chunk texts
            text = "\n".join(row.get("text", "") for row in chunk_rows if row.get("text"))

            return text, metadata

        except Exception as e:
            logger.error(f"Failed to fetch document {doc_id}: {e}")
            return None, {}

    async def _run_deep_analysis(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> list[Anomaly]:
        """
        Run deep analysis detection strategies that require corpus comparison.

        This includes:
        - Content anomalies (vector distance)
        - Statistical anomalies (corpus-relative)
        - Metadata anomalies (corpus-relative)

        Args:
            doc_id: Document ID
            text: Document text content
            metadata: Document metadata

        Returns:
            List of detected anomalies
        """
        if not self.detector or not self.store:
            return []

        all_anomalies: list[Anomaly] = []

        try:
            # Statistical anomalies - needs corpus stats
            corpus_stats = await self._get_corpus_stats()
            if corpus_stats:
                stat_anomalies = self.detector.detect_statistical_anomalies(
                    doc_id, text, corpus_stats
                )
                all_anomalies.extend(stat_anomalies)

            # Metadata anomalies - needs corpus metadata stats
            corpus_metadata_stats = await self._get_corpus_metadata_stats()
            if corpus_metadata_stats:
                meta_anomalies = self.detector.detect_metadata_anomalies(
                    doc_id, metadata, corpus_metadata_stats
                )
                all_anomalies.extend(meta_anomalies)

            # Content anomalies - needs vector service
            if self._vector_service:
                content_anomalies = await self._detect_content_anomalies(doc_id, text)
                all_anomalies.extend(content_anomalies)

            # Store all detected anomalies
            for anomaly in all_anomalies:
                await self.store.create_anomaly(anomaly)

            if all_anomalies:
                logger.info(f"Deep analysis found {len(all_anomalies)} anomalies for {doc_id}")

                # Emit event for deep detections
                if self._event_bus:
                    await self._event_bus.emit(
                        "anomalies.detected",
                        {
                            "doc_id": doc_id,
                            "count": len(all_anomalies),
                            "types": list(set(a.anomaly_type.value for a in all_anomalies)),
                            "detection_phase": "deep",
                        },
                        source="anomalies-shard",
                    )

        except Exception as e:
            logger.error(f"Deep analysis failed for {doc_id}: {e}", exc_info=True)

        return all_anomalies

    async def _get_corpus_stats(self) -> Dict[str, Any]:
        """
        Calculate corpus-wide text statistics for comparison.

        Returns:
            Dictionary of corpus statistics by metric
        """
        if not self._db_service:
            return {}

        try:
            rows = await self._db_service.fetch_all(
                """SELECT
                    AVG(LENGTH(text)) as avg_char_count,
                    AVG(LENGTH(text) - LENGTH(REPLACE(text, ' ', '')) + 1) as avg_word_count
                   FROM arkham_frame.chunks
                   WHERE text IS NOT NULL AND LENGTH(text) > 0
                   LIMIT 1000"""
            )

            if not rows or not rows[0]:
                return {}

            row = rows[0]

            # Build corpus stats structure
            corpus_stats = {
                'char_count': {
                    'mean': float(row.get('avg_char_count') or 0),
                    'std': float(row.get('avg_char_count', 0) or 0) * 0.5,
                },
                'word_count': {
                    'mean': float(row.get('avg_word_count') or 0),
                    'std': float(row.get('avg_word_count', 0) or 0) * 0.5,
                },
            }

            return corpus_stats

        except Exception as e:
            logger.debug(f"Failed to get corpus stats: {e}")
            return {}

    async def _get_corpus_metadata_stats(self) -> Dict[str, Any]:
        """
        Calculate corpus-wide metadata statistics for comparison.

        Returns:
            Dictionary of metadata statistics
        """
        if not self._db_service:
            return {}

        try:
            row = await self._db_service.fetch_one(
                """SELECT
                    AVG(file_size) as avg_size,
                    MIN(file_size) as min_size,
                    MAX(file_size) as max_size
                   FROM arkham_frame.documents
                   WHERE file_size IS NOT NULL"""
            )

            if not row:
                return {}

            avg_size = float(row.get('avg_size') or 0)
            min_size = float(row.get('min_size') or 0)
            max_size = float(row.get('max_size') or 0)

            estimated_std = (max_size - min_size) / 4 if max_size > min_size else avg_size * 0.5

            return {
                'file_size': {
                    'mean': avg_size,
                    'std': estimated_std,
                }
            }

        except Exception as e:
            logger.debug(f"Failed to get corpus metadata stats: {e}")
            return {}

    async def _detect_content_anomalies(self, doc_id: str, text: str) -> list[Anomaly]:
        """
        Detect content anomalies using vector embeddings.

        Args:
            doc_id: Document ID
            text: Document text

        Returns:
            List of content anomalies
        """
        import uuid
        from datetime import datetime
        from .models import AnomalyType, SeverityLevel

        if not self._vector_service or not self.detector:
            return []

        try:
            # Check if vector text search is available (embeds text then searches)
            if hasattr(self._vector_service, 'search_text'):
                # Search for similar documents using text query
                # search_text handles embedding internally
                results = await self._vector_service.search_text(
                    collection="arkham_documents",  # Use correct collection name
                    text=text[:1000],  # Use first 1000 chars as query
                    limit=10,
                )

                # If this document is very different from results, it might be anomalous
                if results and len(results) > 0:
                    # SearchResult is a dataclass with .score attribute
                    avg_score = sum(r.score if hasattr(r, 'score') else r.get('score', 0) for r in results) / len(results)
                    if avg_score < 0.3:  # Low similarity to corpus
                        return [Anomaly(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            anomaly_type=AnomalyType.CONTENT,
                            score=1.0 - avg_score,
                            severity=SeverityLevel.MEDIUM,
                            confidence=0.7,
                            explanation=f"Document is semantically distant from corpus (avg similarity: {avg_score:.2f})",
                            details={'avg_similarity': avg_score, 'compared_to': len(results)},
                        )]

            return []

        except Exception as e:
            logger.debug(f"Content anomaly detection failed: {e}")
            return []

    # --- Public API for other shards ---

    async def detect_anomalies(
        self,
        doc_ids: list[str] | None = None,
        config: DetectionConfig | None = None,
    ) -> list[Anomaly]:
        """
        Public method for other shards to trigger anomaly detection.

        Uses hybrid detection approach:
        - Quick red flag detection runs synchronously for all documents
        - Deep analysis (statistical, metadata, content) runs after

        Args:
            doc_ids: List of document IDs to check (None = all documents)
            config: Detection configuration

        Returns:
            List of detected anomalies
        """
        if not self.detector or not self.store:
            raise RuntimeError("Anomalies Shard not initialized")

        # Use provided config or default
        detection_config = config or self._config

        # Get doc_ids if not provided
        if not doc_ids and self._db_service:
            query = "SELECT id FROM arkham_frame.documents WHERE 1=1"
            params: Dict[str, Any] = {}

            # Add tenant filtering if tenant context is available
            tenant_id = self.get_tenant_id_or_none()
            if tenant_id:
                query += " AND tenant_id = :tenant_id"
                params["tenant_id"] = str(tenant_id)

            query += " LIMIT 1000"
            rows = await self._db_service.fetch_all(query, params)
            doc_ids = [row["id"] for row in rows] if rows else []

        if not doc_ids:
            logger.warning("No documents to analyze")
            return []

        logger.info(f"Detecting anomalies for {len(doc_ids)} documents")

        all_anomalies: list[Anomaly] = []

        for doc_id in doc_ids:
            try:
                # Fetch document content
                text, metadata = await self._fetch_document_content(doc_id)
                if not text:
                    continue

                # Quick red flag detection
                if detection_config.detect_red_flags:
                    red_flags = self.detector.detect_red_flags(doc_id, text, metadata)
                    for anomaly in red_flags:
                        await self.store.create_anomaly(anomaly)
                    all_anomalies.extend(red_flags)

                # Deep analysis
                if any([
                    detection_config.detect_statistical,
                    detection_config.detect_metadata,
                    detection_config.detect_content
                ]):
                    deep_anomalies = await self._run_deep_analysis(doc_id, text, metadata)
                    # Deep analysis already stores anomalies, just collect them
                    all_anomalies.extend(deep_anomalies)

            except Exception as e:
                logger.warning(f"Failed to analyze document {doc_id}: {e}")

        # Emit summary event
        if self._event_bus and all_anomalies:
            await self._event_bus.emit(
                "anomalies.batch_detection_completed",
                {
                    "doc_count": len(doc_ids),
                    "anomaly_count": len(all_anomalies),
                    "types": list(set(a.anomaly_type.value for a in all_anomalies)),
                },
                source="anomalies-shard",
            )

        logger.info(f"Detection completed: {len(all_anomalies)} anomalies found")
        return all_anomalies

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

    # === Hidden Content Detection Methods ===

    async def _store_hidden_content_scan(self, scan: HiddenContentScan) -> None:
        """
        Store a hidden content scan result in the database.

        Args:
            scan: HiddenContentScan result to store
        """
        if not self._db_service:
            return

        from datetime import datetime

        tenant_id = self.get_tenant_id_or_none()

        # Convert complex objects to JSON strings
        entropy_regions = json.dumps([
            {
                "start_offset": r.start_offset,
                "end_offset": r.end_offset,
                "entropy_value": r.entropy_value,
                "is_anomalous": r.is_anomalous,
                "description": r.description,
            }
            for r in scan.entropy_regions
        ])

        lsb_analysis = json.dumps(
            {
                "bit_ratio": scan.lsb_result.bit_ratio,
                "chi_square_value": scan.lsb_result.chi_square_value,
                "chi_square_p_value": scan.lsb_result.chi_square_p_value,
                "is_suspicious": scan.lsb_result.is_suspicious,
                "confidence": scan.lsb_result.confidence,
                "sample_size": scan.lsb_result.sample_size,
            } if scan.lsb_result else {}
        )

        stego_indicators = json.dumps([
            {
                "indicator_type": i.indicator_type,
                "confidence": i.confidence,
                "location": i.location,
                "details": i.details,
            }
            for i in scan.stego_indicators
        ])

        await self._db_service.execute(
            """
            INSERT INTO arkham_anomalies.hidden_content_scans (
                id, doc_id, scan_type, scan_status, findings,
                entropy_score, entropy_regions, magic_expected, magic_actual,
                lsb_analysis, stego_indicators, stego_confidence,
                created_at, completed_at, metadata, tenant_id
            ) VALUES (
                :id, :doc_id, :scan_type, :scan_status, :findings,
                :entropy_score, :entropy_regions, :magic_expected, :magic_actual,
                :lsb_analysis, :stego_indicators, :stego_confidence,
                :created_at, :completed_at, :metadata, :tenant_id
            )
            """,
            {
                "id": scan.id,
                "doc_id": scan.doc_id,
                "scan_type": scan.scan_type.value,
                "scan_status": scan.scan_status.value,
                "findings": json.dumps(scan.findings),
                "entropy_score": scan.entropy_global,
                "entropy_regions": entropy_regions,
                "magic_expected": scan.magic_expected,
                "magic_actual": scan.magic_actual,
                "lsb_analysis": lsb_analysis,
                "stego_indicators": stego_indicators,
                "stego_confidence": scan.stego_confidence,
                "created_at": scan.created_at.isoformat() if scan.created_at else datetime.utcnow().isoformat(),
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "metadata": json.dumps(scan.metadata),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

    async def get_hidden_content_scan(self, scan_id: str, project_id: str | None = None) -> Optional[Dict[str, Any]]:
        """
        Get a hidden content scan by ID.

        Args:
            scan_id: Scan ID

        Returns:
            Scan data dict or None
        """
        if not self._db_service:
            return None

        tenant_id = self.get_tenant_id_or_none()
        params: Dict[str, Any] = {"id": scan_id}

        if project_id:
            query = """
                SELECT s.*
                FROM arkham_anomalies.hidden_content_scans s
                INNER JOIN arkham_frame.documents d ON d.id = s.doc_id
                WHERE s.id = :id AND d.project_id = :project_id
            """
            params["project_id"] = str(project_id)
        else:
            query = "SELECT * FROM arkham_anomalies.hidden_content_scans WHERE id = :id"

        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db_service.fetch_one(query, params)
        return dict(row) if row else None

    async def get_document_hidden_scans(self, doc_id: str, project_id: str | None = None) -> list[Dict[str, Any]]:
        """
        Get all hidden content scans for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of scan data dicts
        """
        if not self._db_service:
            return []

        tenant_id = self.get_tenant_id_or_none()
        params: Dict[str, Any] = {"doc_id": doc_id}

        if project_id:
            query = """
                SELECT s.*
                FROM arkham_anomalies.hidden_content_scans s
                INNER JOIN arkham_frame.documents d ON d.id = s.doc_id
                WHERE s.doc_id = :doc_id AND d.project_id = :project_id
            """
            params["project_id"] = str(project_id)
        else:
            query = """
                SELECT * FROM arkham_anomalies.hidden_content_scans
                WHERE doc_id = :doc_id
            """

        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        query += " ORDER BY created_at DESC"
        rows = await self._db_service.fetch_all(query, params)
        return [dict(row) for row in rows] if rows else []

    async def get_hidden_content_stats(self, project_id: str | None = None) -> Dict[str, Any]:
        """
        Get hidden content detection statistics.

        Returns:
            Statistics dictionary
        """
        if not self._db_service:
            return {}

        tenant_id = self.get_tenant_id_or_none()
        params: Dict[str, Any] = {}

        joins = ""
        where_clauses = []

        if project_id:
            joins = " INNER JOIN arkham_frame.documents d ON d.id = s.doc_id"
            where_clauses.append("d.project_id = :project_id")
            params["project_id"] = str(project_id)

        if tenant_id:
            where_clauses.append("s.tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total scans
        total_row = await self._db_service.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_anomalies.hidden_content_scans s{joins}{where}",
            params,
        )
        total_scans = total_row.get("count", 0) if total_row else 0

        # Scans by type
        type_rows = await self._db_service.fetch_all(
            f"""SELECT s.scan_type, COUNT(*) as count
                FROM arkham_anomalies.hidden_content_scans s{joins}{where}
                GROUP BY s.scan_type""",
            params,
        )
        scans_by_type = {row["scan_type"]: row["count"] for row in type_rows} if type_rows else {}

        # Documents with findings
        findings_row = await self._db_service.fetch_one(
            f"""SELECT COUNT(DISTINCT s.doc_id) as count
                FROM arkham_anomalies.hidden_content_scans s{joins}
                WHERE s.findings != '[]'{(' AND ' + ' AND '.join(where_clauses)) if where_clauses else ''}""",
            params,
        )
        docs_with_findings = findings_row.get("count", 0) if findings_row else 0

        # High entropy files
        entropy_row = await self._db_service.fetch_one(
            f"""SELECT COUNT(*) as count
                FROM arkham_anomalies.hidden_content_scans s{joins}
                WHERE s.entropy_score >= 7.5{(' AND ' + ' AND '.join(where_clauses)) if where_clauses else ''}""",
            params,
        )
        high_entropy = entropy_row.get("count", 0) if entropy_row else 0

        # Stego candidates
        stego_row = await self._db_service.fetch_one(
            f"""SELECT COUNT(*) as count
                FROM arkham_anomalies.hidden_content_scans s{joins}
                WHERE s.stego_confidence >= 0.5{(' AND ' + ' AND '.join(where_clauses)) if where_clauses else ''}""",
            params,
        )
        stego_candidates = stego_row.get("count", 0) if stego_row else 0

        return {
            "total_scans": total_scans,
            "scans_by_type": scans_by_type,
            "documents_with_findings": docs_with_findings,
            "high_entropy_files": high_entropy,
            "stego_candidates": stego_candidates,
        }
