"""Timeline Shard - Temporal event extraction and visualization."""

import logging
from datetime import datetime
from typing import Optional

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .extraction import DateExtractor
from .merging import TimelineMerger
from .conflicts import ConflictDetector
from .models import (
    TimelineEvent,
    ExtractionContext,
    MergeStrategy,
    ConflictType,
    TimelineQuery,
    EntityTimeline,
    DateRange,
)

logger = logging.getLogger(__name__)


class TimelineShard(ArkhamShard):
    """
    Timeline shard for ArkhamFrame.

    Handles:
    - Date extraction from text
    - Timeline visualization
    - Timeline merging across documents
    - Temporal conflict detection
    - Entity timelines
    - Date normalization
    """

    name = "timeline"
    version = "0.1.0"
    description = "Temporal event extraction and timeline visualization"

    def __init__(self):
        super().__init__()
        self.extractor = None
        self.merger = None
        self.conflict_detector = None
        self.database_service = None
        self.documents_service = None
        self.entities_service = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self.frame = frame

        logger.info("Initializing Timeline Shard...")

        # Get required services
        self.database_service = frame.get_service("database") or frame.get_service("db")
        if not self.database_service:
            logger.warning("Database service not available - timeline storage will be disabled")

        # Get optional services
        self.documents_service = frame.get_service("documents")
        self.entities_service = frame.get_service("entities")
        event_bus = frame.get_service("events")

        # Initialize extraction engine
        self.extractor = DateExtractor()
        logger.info("Date extractor initialized")

        # Initialize merger
        self.merger = TimelineMerger(strategy=MergeStrategy.CHRONOLOGICAL)
        logger.info("Timeline merger initialized")

        # Initialize conflict detector
        self.conflict_detector = ConflictDetector(tolerance_days=0)
        logger.info("Conflict detector initialized")

        # Initialize API
        init_api(
            extractor=self.extractor,
            merger=self.merger,
            conflict_detector=self.conflict_detector,
            database_service=self.database_service,
            documents_service=self.documents_service,
            entities_service=self.entities_service,
            event_bus=event_bus,
        )

        # Subscribe to document events
        if event_bus:
            await event_bus.subscribe("documents.indexed", self._on_document_indexed)
            await event_bus.subscribe("documents.deleted", self._on_document_deleted)
            await event_bus.subscribe("entities.created", self._on_entity_created)

        # Create database schema if needed
        if self.database_service:
            await self._create_schema()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.timeline_shard = self

        logger.info("Timeline Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Timeline Shard...")

        # Unsubscribe from events
        if self.frame:
            event_bus = self.frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("documents.indexed", self._on_document_indexed)
                await event_bus.unsubscribe("documents.deleted", self._on_document_deleted)
                await event_bus.unsubscribe("entities.created", self._on_entity_created)

        self.extractor = None
        self.merger = None
        self.conflict_detector = None
        self.database_service = None
        self.documents_service = None
        self.entities_service = None

        logger.info("Timeline Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _create_schema(self) -> None:
        """Create database schema for timeline storage."""
        if not self.database_service:
            return

        logger.info("Creating timeline schema...")

        # Create timeline events table
        await self.database_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_timeline_events (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                text TEXT NOT NULL,
                date_start TIMESTAMP NOT NULL,
                date_end TIMESTAMP,
                precision TEXT NOT NULL,
                confidence REAL NOT NULL,
                entities JSONB DEFAULT '[]',
                event_type TEXT NOT NULL,
                span_start INTEGER,
                span_end INTEGER,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for timeline events
        await self.database_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_timeline_events_document_id
            ON arkham_timeline_events(document_id)
        """)

        await self.database_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_timeline_events_date_start
            ON arkham_timeline_events(date_start)
        """)

        await self.database_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_timeline_events_event_type
            ON arkham_timeline_events(event_type)
        """)

        # Create timeline conflicts table
        await self.database_service.execute("""
            CREATE TABLE IF NOT EXISTS arkham_timeline_conflicts (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                event_ids JSONB DEFAULT '[]',
                description TEXT NOT NULL,
                document_ids JSONB DEFAULT '[]',
                suggested_resolution TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for conflicts
        await self.database_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_timeline_conflicts_type
            ON arkham_timeline_conflicts(type)
        """)

        await self.database_service.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_timeline_conflicts_severity
            ON arkham_timeline_conflicts(severity)
        """)

        logger.info("Timeline schema created successfully")

    async def _on_document_indexed(self, event: dict) -> None:
        """
        Handle document indexed event.

        Automatically extract timeline when documents are indexed.
        """
        doc_id = event.get("doc_id") or event.get("document_id") or event.get("id")
        if not doc_id:
            logger.warning("Document indexed event missing document ID")
            return

        logger.info(f"Document indexed, extracting timeline: {doc_id}")

        # Extract timeline in background
        try:
            events = await self.extract_timeline(doc_id)
            if events:
                logger.info(f"Extracted {len(events)} timeline events from {doc_id}")
                # Emit event
                event_bus = self.frame.get_service("events")
                if event_bus:
                    await event_bus.emit(
                        "timeline.timeline.extracted",
                        {"document_id": doc_id, "event_count": len(events)},
                        source="timeline-shard"
                    )
        except Exception as e:
            logger.error(f"Failed to extract timeline for {doc_id}: {e}")

    async def _on_document_deleted(self, event: dict) -> None:
        """
        Handle document deleted event.

        Clean up timeline events when documents are deleted.
        """
        doc_id = event.get("doc_id") or event.get("document_id") or event.get("id")
        if not doc_id:
            logger.warning("Document deleted event missing document ID")
            return

        logger.info(f"Document deleted, cleaning up timeline: {doc_id}")

        if self.database_service:
            try:
                # Delete timeline events for this document
                await self.database_service.execute(
                    "DELETE FROM arkham_timeline_events WHERE document_id = :doc_id",
                    {"doc_id": doc_id}
                )
                logger.info(f"Cleaned up timeline events for {doc_id}")
            except Exception as e:
                logger.error(f"Failed to clean up timeline for {doc_id}: {e}")

    async def _on_entity_created(self, event: dict) -> None:
        """
        Handle entity created event.

        Could be used to update timeline event entities.
        """
        entity_id = event.get("entity_id")
        logger.debug(f"Entity created: {entity_id}")

        # Could update timeline events to link with this entity
        # if the entity was mentioned in event text

    # --- Public API for other shards ---

    async def extract_timeline(
        self,
        document_id: str,
        context: Optional[ExtractionContext] = None
    ) -> list[TimelineEvent]:
        """
        Public method to extract timeline from a document.

        Args:
            document_id: Document to extract timeline from
            context: Optional extraction context

        Returns:
            List of extracted timeline events
        """
        if not self.database_service:
            logger.error("Database service not available")
            return []

        if context is None:
            context = ExtractionContext(reference_date=datetime.now())

        # Get document text from chunks (preferred) or documents table
        doc_text = ""
        try:
            # First try to get text from chunks table
            rows = await self.database_service.fetch_all(
                """
                SELECT text FROM arkham_frame.chunks
                WHERE document_id = :document_id
                ORDER BY chunk_index
                """,
                {"document_id": document_id}
            )
            if rows:
                doc_text = " ".join(row["text"] for row in rows if row.get("text"))
                logger.debug(f"Got {len(rows)} chunks for document {document_id}")
            else:
                logger.warning(f"No chunks found for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to get text for document {document_id}: {e}")
            return []

        if not doc_text:
            logger.warning(f"No text found for document {document_id}")
            return []

        logger.info(f"Extracting timeline from {len(doc_text)} chars for document {document_id}")

        # Extract events
        events = self.extractor.extract_events(doc_text, document_id, context)

        # Store events if database available
        if self.database_service and events:
            try:
                await self._store_events(events)
            except Exception as e:
                logger.error(f"Failed to store timeline events: {e}")

        return events

    async def merge_timelines(
        self,
        document_ids: list[str],
        strategy: MergeStrategy = MergeStrategy.CHRONOLOGICAL,
        date_range: Optional[DateRange] = None,
    ):
        """
        Public method to merge timelines from multiple documents.

        Args:
            document_ids: Documents to merge timelines from
            strategy: Merge strategy to use
            date_range: Optional date range filter

        Returns:
            MergeResult with merged timeline
        """
        if not self.database_service:
            logger.error("Database service not available")
            return None

        # Get events for all documents
        all_events = []
        for doc_id in document_ids:
            try:
                events = await self._get_events_for_document(doc_id)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Failed to get events for {doc_id}: {e}")

        # Apply date range filter
        if date_range:
            filtered = []
            for event in all_events:
                if date_range.start and event.date_start < date_range.start:
                    continue
                if date_range.end and event.date_start > date_range.end:
                    continue
                filtered.append(event)
            all_events = filtered

        # Merge
        return self.merger.merge(all_events, strategy=strategy)

    async def detect_conflicts(
        self,
        document_ids: list[str],
        conflict_types: Optional[list[ConflictType]] = None,
        tolerance_days: int = 0,
    ):
        """
        Public method to detect temporal conflicts.

        Args:
            document_ids: Documents to check for conflicts
            conflict_types: Types of conflicts to detect
            tolerance_days: Days of tolerance for date matching

        Returns:
            List of detected conflicts
        """
        if not self.database_service:
            logger.error("Database service not available")
            return []

        # Get events for all documents
        all_events = []
        for doc_id in document_ids:
            try:
                events = await self._get_events_for_document(doc_id)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Failed to get events for {doc_id}: {e}")

        # Detect conflicts
        if tolerance_days != self.conflict_detector.tolerance_days:
            detector = ConflictDetector(tolerance_days=tolerance_days)
        else:
            detector = self.conflict_detector

        conflicts = detector.detect_conflicts(all_events, conflict_types)

        # Store conflicts if database available
        if self.database_service and conflicts:
            try:
                await self._store_conflicts(conflicts)
            except Exception as e:
                logger.error(f"Failed to store conflicts: {e}")

        return conflicts

    async def get_entity_timeline(
        self,
        entity_id: str,
        date_range: Optional[DateRange] = None,
        include_related: bool = False,
    ) -> EntityTimeline:
        """
        Public method to get timeline for an entity.

        Args:
            entity_id: Entity to get timeline for
            date_range: Optional date range filter
            include_related: Include related entities

        Returns:
            EntityTimeline object
        """
        if not self.database_service:
            logger.error("Database service not available")
            return EntityTimeline(
                entity_id=entity_id,
                events=[],
                count=0,
                date_range=DateRange(),
            )

        # Query events mentioning this entity
        try:
            events = await self._get_events_for_entity(entity_id)
        except Exception as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            events = []

        # Apply date range filter
        if date_range:
            filtered = []
            for event in events:
                if date_range.start and event.date_start < date_range.start:
                    continue
                if date_range.end and event.date_start > date_range.end:
                    continue
                filtered.append(event)
            events = filtered

        # Calculate date range
        event_date_range = DateRange()
        if events:
            dates = [e.date_start for e in events]
            event_date_range = DateRange(
                start=min(dates),
                end=max(dates),
            )

        # Get related entities if requested
        related_entities = []
        if include_related and self.entities_service:
            try:
                # Get entities that appear in same events
                all_entity_ids = set()
                for event in events:
                    all_entity_ids.update(event.entities)
                all_entity_ids.discard(entity_id)
                related_entities = list(all_entity_ids)
            except Exception as e:
                logger.error(f"Failed to get related entities: {e}")

        return EntityTimeline(
            entity_id=entity_id,
            events=events,
            count=len(events),
            date_range=event_date_range,
            related_entities=related_entities,
        )

    async def _store_events(self, events: list[TimelineEvent]) -> None:
        """Store timeline events in database."""
        if not self.database_service:
            return

        import json
        for event in events:
            await self.database_service.execute(
                """
                INSERT INTO arkham_timeline_events
                (id, document_id, text, date_start, date_end, precision, confidence,
                 entities, event_type, span_start, span_end, metadata)
                VALUES (:id, :document_id, :text, :date_start, :date_end, :precision,
                        :confidence, :entities, :event_type, :span_start, :span_end, :metadata)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    date_start = EXCLUDED.date_start,
                    date_end = EXCLUDED.date_end,
                    precision = EXCLUDED.precision,
                    confidence = EXCLUDED.confidence,
                    entities = EXCLUDED.entities,
                    event_type = EXCLUDED.event_type,
                    span_start = EXCLUDED.span_start,
                    span_end = EXCLUDED.span_end,
                    metadata = EXCLUDED.metadata
                """,
                {
                    "id": event.id,
                    "document_id": event.document_id,
                    "text": event.text,
                    "date_start": event.date_start,
                    "date_end": event.date_end,
                    "precision": event.precision.value,
                    "confidence": event.confidence,
                    "entities": json.dumps(event.entities),
                    "event_type": event.event_type.value,
                    "span_start": event.span[0] if event.span else None,
                    "span_end": event.span[1] if event.span else None,
                    "metadata": json.dumps(event.metadata),
                }
            )

        logger.debug(f"Stored {len(events)} timeline events")

    async def _store_conflicts(self, conflicts) -> None:
        """Store temporal conflicts in database."""
        if not self.database_service:
            return

        import json
        for conflict in conflicts:
            await self.database_service.execute(
                """
                INSERT INTO arkham_timeline_conflicts
                (id, type, severity, event_ids, description, document_ids,
                 suggested_resolution, metadata)
                VALUES (:id, :type, :severity, :event_ids, :description, :document_ids,
                        :suggested_resolution, :metadata)
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    severity = EXCLUDED.severity,
                    event_ids = EXCLUDED.event_ids,
                    description = EXCLUDED.description,
                    document_ids = EXCLUDED.document_ids,
                    suggested_resolution = EXCLUDED.suggested_resolution,
                    metadata = EXCLUDED.metadata
                """,
                {
                    "id": conflict.id,
                    "type": conflict.type.value,
                    "severity": conflict.severity.value,
                    "event_ids": json.dumps(conflict.events),
                    "description": conflict.description,
                    "document_ids": json.dumps(conflict.documents),
                    "suggested_resolution": conflict.suggested_resolution,
                    "metadata": json.dumps(conflict.metadata),
                }
            )

        logger.debug(f"Stored {len(conflicts)} conflicts")

    async def _get_events_for_document(self, document_id: str) -> list[TimelineEvent]:
        """Get all timeline events for a document."""
        if not self.database_service:
            return []

        rows = await self.database_service.fetch_all(
            "SELECT * FROM arkham_timeline_events WHERE document_id = :document_id ORDER BY date_start",
            {"document_id": document_id}
        )

        return [self._row_to_event(row) for row in rows]

    async def _get_events_for_entity(self, entity_id: str) -> list[TimelineEvent]:
        """Get all timeline events mentioning an entity."""
        if not self.database_service:
            return []

        # Query events where entity_id is in the entities JSONB array
        rows = await self.database_service.fetch_all(
            """
            SELECT * FROM arkham_timeline_events
            WHERE entities::jsonb @> :entity_array::jsonb
            ORDER BY date_start
            """,
            {"entity_array": f'["{entity_id}"]'}
        )

        return [self._row_to_event(row) for row in rows]

    def _parse_jsonb(self, value, default=None):
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        import json
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default

    def _row_to_event(self, row) -> TimelineEvent:
        """Convert database row to TimelineEvent."""
        from .models import EventType, DatePrecision

        entities = self._parse_jsonb(row.get("entities"), [])
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return TimelineEvent(
            id=row["id"],
            document_id=row["document_id"],
            text=row["text"],
            date_start=row["date_start"],
            date_end=row.get("date_end"),
            precision=DatePrecision(row["precision"]),
            confidence=row["confidence"],
            entities=entities,
            event_type=EventType(row["event_type"]),
            span=(row["span_start"], row["span_end"]) if row.get("span_start") is not None else None,
            metadata=metadata,
        )
