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
            parse_shard=self,
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
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        job_id = payload.get("job_id")
        result = payload.get("result", {})
        doc_id = result.get("document_id")

        if not doc_id:
            logger.debug(f"No document_id in ingest.job.completed event, skipping parse")
            return

        logger.info(f"Auto-parsing document {doc_id} after ingestion")

        try:
            # Parse document directly (extracts entities, creates and saves chunks)
            parse_result = await self.parse_document(doc_id, save_chunks=True)

            logger.info(
                f"Document {doc_id} parsed: {parse_result.get('total_entities', 0)} entities, "
                f"{parse_result.get('chunks_saved', 0)} chunks saved"
            )

            # Emit completion event
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.emit(
                    "parse.document.completed",
                    {
                        "document_id": doc_id,
                        "entities": parse_result.get("total_entities", 0),
                        "chunks": parse_result.get("total_chunks", 0),
                        "chunks_saved": parse_result.get("chunks_saved", 0),
                    },
                    source="parse-shard",
                )

        except Exception as e:
            logger.error(f"Failed to parse document {doc_id}: {e}")

    async def _on_worker_completed(self, event: dict) -> None:
        """Handle worker job completion."""
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        job_type = payload.get("job_type")

        if job_type == "parse_document":
            result = payload.get("result", {})
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

    async def parse_document(self, document_id: str, save_chunks: bool = True) -> dict:
        """
        Parse a full document.

        Args:
            document_id: Document to parse
            save_chunks: Whether to persist chunks to database

        Returns:
            Parse result dict
        """
        from time import time

        start_time = time()

        # Get document text from document service
        doc_service = self._frame.get_service("documents")
        if not doc_service:
            raise RuntimeError("Document service not available")

        # Get all pages for the document
        pages = await doc_service.get_document_pages(document_id)

        if not pages:
            logger.warning(f"No pages found for document {document_id}")
            return {
                "document_id": document_id,
                "entities": [],
                "chunks": [],
                "total_entities": 0,
                "total_chunks": 0,
                "processing_time_ms": 0,
            }

        # Combine all page text
        all_entities = []
        all_chunks = []
        all_dates = []
        all_relationships = []

        for page in pages:
            if not page.text:
                continue

            # Extract entities from this page
            entities = self.ner_extractor.extract(page.text, document_id)
            all_entities.extend(entities)

            # Extract dates
            dates = self.date_extractor.extract(page.text, document_id)
            all_dates.extend(dates)

            # Extract relationships
            relationships = self.relation_extractor.extract(page.text, entities, document_id)
            all_relationships.extend(relationships)

            # Chunk this page's text
            chunks = self.chunker.chunk_text(page.text, document_id, page.page_number)
            all_chunks.extend(chunks)

        # Save chunks to database if requested
        chunks_saved = 0
        if save_chunks and all_chunks:
            chunks_saved = await self._save_chunks(document_id, all_chunks, doc_service)

        # Save entities to database via EntityService
        entities_saved = 0
        entity_service = self._frame.get_service("entities")
        if entity_service and all_entities:
            entities_saved = await self._save_entities(document_id, all_entities, entity_service)

        # Emit entity extraction event for Entities shard to process
        event_bus = self._frame.get_service("events")
        if event_bus and all_entities:
            entity_data = []
            for entity in all_entities:
                entity_type_val = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
                entity_data.append({
                    "text": entity.text,
                    "entity_type": entity_type_val,
                    "start_offset": getattr(entity, 'start_char', 0),
                    "end_offset": getattr(entity, 'end_char', 0),
                    "confidence": getattr(entity, 'confidence', 0.85),
                    "sentence": getattr(entity, 'sentence', None),
                })
            await event_bus.emit(
                "parse.entity.extracted",
                {
                    "document_id": document_id,
                    "entities": entity_data,
                },
                source="parse-shard",
            )
            logger.debug(f"Emitted parse.entity.extracted event with {len(entity_data)} entities")

        # Emit relationship extraction event for Entities shard to process
        if event_bus and all_relationships:
            relationship_data = []
            for rel in all_relationships:
                relationship_data.append({
                    "source_entity": rel.source_entity_id,
                    "target_entity": rel.target_entity_id,
                    "relation_type": rel.relation_type,
                    "confidence": rel.confidence,
                    "evidence_text": rel.evidence_text,
                })
            await event_bus.emit(
                "parse.relationships.extracted",
                {
                    "document_id": document_id,
                    "relationships": relationship_data,
                },
                source="parse-shard",
            )
            logger.debug(f"Emitted parse.relationships.extracted event with {len(relationship_data)} relationships")

        processing_time = (time() - start_time) * 1000

        logger.info(
            f"Parsed document {document_id}: {len(all_entities)} entities ({entities_saved} saved), "
            f"{len(all_chunks)} chunks ({chunks_saved} saved)"
        )

        return {
            "document_id": document_id,
            "entities": [e.__dict__ for e in all_entities],
            "dates": [d.__dict__ for d in all_dates],
            "relationships": [r.__dict__ for r in all_relationships],
            "chunks": [c.__dict__ for c in all_chunks],
            "total_entities": len(all_entities),
            "total_chunks": len(all_chunks),
            "chunks_saved": chunks_saved,
            "entities_saved": entities_saved,
            "pages_processed": len(pages),
            "processing_time_ms": processing_time,
        }

    async def _save_chunks(self, document_id: str, chunks: list, doc_service) -> int:
        """
        Save chunks to the database.

        Args:
            document_id: Document ID
            chunks: List of TextChunk objects
            doc_service: Document service instance

        Returns:
            Number of chunks saved
        """
        saved_count = 0

        for chunk in chunks:
            try:
                await doc_service.add_chunk(
                    doc_id=document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    start_char=chunk.char_start,
                    end_char=chunk.char_end,
                    page_number=chunk.page_number,
                    token_count=chunk.token_count,
                    metadata={
                        "chunk_method": chunk.chunk_method,
                        "original_id": chunk.id,
                    },
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save chunk {chunk.chunk_index}: {e}")

        # Update document's chunk_count
        if saved_count > 0:
            await doc_service.update_chunk_count(document_id)

        logger.debug(f"Saved {saved_count}/{len(chunks)} chunks for document {document_id}")
        return saved_count

    async def _save_entities(self, document_id: str, entities: list, entity_service) -> int:
        """
        Save extracted entities to the database via EntityService.

        Args:
            document_id: Document ID
            entities: List of EntityMention objects from NER extractor
            entity_service: Entity service instance from Frame

        Returns:
            Number of entities saved
        """
        saved_count = 0

        # Map parse shard EntityType to Frame EntityType
        from arkham_frame.services.entities import EntityType as FrameEntityType

        type_mapping = {
            "PERSON": FrameEntityType.PERSON,
            "ORG": FrameEntityType.ORGANIZATION,
            "GPE": FrameEntityType.LOCATION,
            "FAC": FrameEntityType.LOCATION,
            "DATE": FrameEntityType.DATE,
            "TIME": FrameEntityType.DATE,
            "MONEY": FrameEntityType.MONEY,
            "PERCENT": FrameEntityType.OTHER,
            "PRODUCT": FrameEntityType.PRODUCT,
            "EVENT": FrameEntityType.EVENT,
            "LAW": FrameEntityType.DOCUMENT,
            "LANGUAGE": FrameEntityType.CONCEPT,
            "NORP": FrameEntityType.ORGANIZATION,
            "CARDINAL": FrameEntityType.OTHER,
            "ORDINAL": FrameEntityType.OTHER,
            "QUANTITY": FrameEntityType.OTHER,
            "WORK_OF_ART": FrameEntityType.DOCUMENT,
            "OTHER": FrameEntityType.OTHER,
        }

        for entity in entities:
            try:
                # Get entity type value (may be enum or string)
                entity_type_val = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)

                # Map to Frame's EntityType
                frame_entity_type = type_mapping.get(entity_type_val, FrameEntityType.OTHER)

                await entity_service.create_entity(
                    text=entity.text,
                    entity_type=frame_entity_type,
                    document_id=document_id,
                    chunk_id=getattr(entity, 'source_chunk_id', None),
                    start_offset=getattr(entity, 'start_char', 0),
                    end_offset=getattr(entity, 'end_char', 0),
                    confidence=getattr(entity, 'confidence', 0.85),
                    metadata={
                        "sentence": getattr(entity, 'sentence', None),
                        "source": "parse-shard",
                    },
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save entity '{entity.text}': {e}")

        logger.debug(f"Saved {saved_count}/{len(entities)} entities for document {document_id}")
        return saved_count
