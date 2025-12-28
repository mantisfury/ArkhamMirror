"""Parse Shard - Entity extraction and NER."""

import logging
import uuid
from pathlib import Path

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .extractors import NERExtractor, DateExtractor, LocationExtractor, RelationExtractor
from .linkers import EntityLinker, CoreferenceResolver
from .chunker import TextChunker

logger = logging.getLogger(__name__)


class ParseShard(ArkhamShard):
    """
    Parse shard for ArkhamFrame.

    Handles:
    - Named entity recognition (NER)
    - Date/time extraction
    - Location extraction and geocoding
    - Entity relationship extraction
    - Entity linking to canonical entities
    - Coreference resolution
    - Text chunking for embeddings
    """

    name = "parse"
    version = "0.1.0"
    description = "Entity extraction, NER, and text chunking"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.ner_extractor: NERExtractor | None = None
        self.date_extractor: DateExtractor | None = None
        self.location_extractor: LocationExtractor | None = None
        self.relation_extractor: RelationExtractor | None = None
        self.entity_linker: EntityLinker | None = None
        self.coref_resolver: CoreferenceResolver | None = None
        self.chunker: TextChunker | None = None

        self._frame = None
        self._config = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame
        self._config = frame.config

        logger.info("Initializing Parse Shard...")

        # Get services
        db_service = frame.get_service("database")
        worker_service = frame.get_service("workers")
        event_bus = frame.get_service("events")

        # Initialize extractors
        self.ner_extractor = NERExtractor(
            model_name=self._config.get("parse.spacy_model", "en_core_web_sm")
        )

        # Initialize NER in background (loading spaCy model is slow)
        # In production, this should be done in worker process
        try:
            self.ner_extractor.initialize()
        except Exception as e:
            logger.warning(f"Could not initialize NER extractor: {e}")

        self.date_extractor = DateExtractor()
        self.location_extractor = LocationExtractor()
        self.relation_extractor = RelationExtractor()

        # Initialize linkers
        self.entity_linker = EntityLinker(database_service=db_service)
        self.coref_resolver = CoreferenceResolver()

        # Initialize chunker
        chunk_size = self._config.get("parse.chunk_size", 500)
        chunk_overlap = self._config.get("parse.chunk_overlap", 50)
        chunk_method = self._config.get("parse.chunk_method", "sentence")

        self.chunker = TextChunker(
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            method=chunk_method,
        )

        # Initialize API
        init_api(
            ner_extractor=self.ner_extractor,
            date_extractor=self.date_extractor,
            location_extractor=self.location_extractor,
            relation_extractor=self.relation_extractor,
            entity_linker=self.entity_linker,
            coref_resolver=self.coref_resolver,
            chunker=self.chunker,
            worker_service=worker_service,
            event_bus=event_bus,
        )

        # Register workers with Frame
        if worker_service:
            from .workers import NERWorker
            worker_service.register_worker(NERWorker)
            logger.info("Registered NERWorker to cpu-ner pool")

        # Subscribe to events
        if event_bus:
            await event_bus.subscribe("ingest.job.completed", self._on_document_ingested)
            await event_bus.subscribe("worker.job.completed", self._on_worker_completed)

        logger.info("Parse Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Parse Shard...")

        # Unregister workers
        if self._frame:
            worker_service = self._frame.get_service("workers")
            if worker_service:
                from .workers import NERWorker
                worker_service.unregister_worker(NERWorker)
                logger.info("Unregistered NERWorker from cpu-ner pool")

        # Unsubscribe from events
        if self._frame:
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("ingest.job.completed", self._on_document_ingested)
                await event_bus.unsubscribe("worker.job.completed", self._on_worker_completed)

        self.ner_extractor = None
        self.date_extractor = None
        self.location_extractor = None
        self.relation_extractor = None
        self.entity_linker = None
        self.coref_resolver = None
        self.chunker = None

        logger.info("Parse Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _on_document_ingested(self, event: dict) -> None:
        """
        Handle document ingestion completion.

        Automatically trigger parsing for newly ingested documents.
        """
        job_id = event.get("job_id")
        result = event.get("result", {})
        doc_id = result.get("document_id")

        if not doc_id:
            return

        logger.info(f"Auto-parsing document {doc_id} after ingestion")

        # Dispatch parsing job to cpu-ner worker
        worker_service = self._frame.get_service("workers")
        if worker_service:
            parse_job_id = str(uuid.uuid4())
            await worker_service.enqueue(
                pool="cpu-ner",
                job_id=parse_job_id,
                payload={
                    "document_id": doc_id,
                    "source_job_id": job_id,
                    "job_type": "parse_document",
                },
                priority=2,
            )

    async def _on_worker_completed(self, event: dict) -> None:
        """Handle worker job completion."""
        job_type = event.get("job_type")

        if job_type == "parse_document":
            result = event.get("result", {})
            doc_id = result.get("document_id")

            if doc_id:
                logger.info(f"Document {doc_id} parsing completed")

                # Emit parse completion event
                event_bus = self._frame.get_service("events")
                if event_bus:
                    await event_bus.emit(
                        "parse.document.completed",
                        {
                            "document_id": doc_id,
                            "entities": result.get("total_entities", 0),
                            "chunks": result.get("total_chunks", 0),
                        },
                        source="parse-shard",
                    )

    # --- Public API for other shards ---

    async def parse_text(
        self,
        text: str,
        doc_id: str | None = None,
    ) -> dict:
        """
        Parse text and extract entities.

        Args:
            text: Text to parse
            doc_id: Optional document ID

        Returns:
            Parse result dict with entities, dates, locations
        """
        from time import time

        start_time = time()

        # Extract entities
        entities = self.ner_extractor.extract(text, doc_id)

        # Extract dates
        dates = self.date_extractor.extract(text, doc_id)

        # Extract locations (from NER GPE entities)
        locations = []

        # Extract relationships
        relationships = self.relation_extractor.extract(text, entities, doc_id)

        # Chunk text
        chunks = self.chunker.chunk_text(text, doc_id or "temp") if doc_id else []

        processing_time = (time() - start_time) * 1000

        return {
            "entities": [e.__dict__ for e in entities],
            "dates": [d.__dict__ for d in dates],
            "locations": locations,
            "relationships": [r.__dict__ for r in relationships],
            "chunks": [c.__dict__ for c in chunks],
            "total_entities": len(entities),
            "total_chunks": len(chunks),
            "processing_time_ms": processing_time,
        }

    async def parse_document(self, document_id: str) -> dict:
        """
        Parse a full document.

        Args:
            document_id: Document to parse

        Returns:
            Parse result dict
        """
        # Get document text from document service
        doc_service = self._frame.get_service("documents")
        if not doc_service:
            raise RuntimeError("Document service not available")

        # In production: fetch document text
        # doc_text = await doc_service.get_text(document_id)

        # For now, return mock
        return await self.parse_text("Mock document text", document_id)
