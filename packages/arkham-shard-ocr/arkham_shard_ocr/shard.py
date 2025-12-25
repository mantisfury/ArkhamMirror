"""OCR Shard implementation."""

import logging
from arkham_frame.shard_interface import ArkhamShard
from .api import router, init_api

logger = logging.getLogger(__name__)


class OCRShard(ArkhamShard):
    """
    OCR shard for ArkhamFrame.

    Handles:
    - PaddleOCR for standard document OCR
    - Qwen-VL for complex/handwritten OCR
    - Page-level and document-level processing
    - Bounding box extraction
    """

    name = "ocr"
    version = "0.1.0"
    description = "Optical character recognition for document images"

    def __init__(self):
        self._frame = None
        self._config = None
        self._default_engine = "paddle"

    async def initialize(self, frame) -> None:
        """Initialize the shard with Frame services."""
        self._frame = frame
        self._config = frame.config

        logger.info("Initializing OCR Shard...")

        # Get default OCR engine from config
        self._default_engine = self._config.get("ocr.default_engine", "paddle")

        # Register workers with Frame
        worker_service = frame.get_service("workers")
        if worker_service:
            from .workers import PaddleWorker, QwenWorker
            worker_service.register_worker(PaddleWorker)
            worker_service.register_worker(QwenWorker)
            logger.info("Registered OCR workers (paddle, qwen)")

        # Subscribe to events
        event_bus = frame.get_service("events")
        if event_bus:
            await event_bus.subscribe("ingest.job.completed", self._on_document_ingested)

        # Initialize API with shard reference
        init_api(self)

        logger.info("OCR Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down OCR Shard...")

        # Unregister workers
        if self._frame:
            worker_service = self._frame.get_service("workers")
            if worker_service:
                from .workers import PaddleWorker, QwenWorker
                worker_service.unregister_worker(PaddleWorker)
                worker_service.unregister_worker(QwenWorker)

            # Unsubscribe from events
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("ingest.job.completed", self._on_document_ingested)

        logger.info("OCR Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _on_document_ingested(self, event: dict) -> None:
        """Handle document ingestion - trigger OCR if needed."""
        doc_id = event.get("document_id")
        doc_type = event.get("document_type", "")

        # Only OCR image-based documents
        if doc_type not in ("image", "scanned_pdf"):
            return

        logger.info(f"Auto-triggering OCR for document {doc_id}")
        await self.ocr_document(doc_id)

    # --- Public API ---

    async def ocr_page(
        self,
        image_path: str,
        engine: str | None = None,
        language: str = "en",
    ) -> dict:
        """
        OCR a single page image.

        Args:
            image_path: Path to the image file
            engine: OCR engine ("paddle" or "qwen"), defaults to config
            language: Language code

        Returns:
            OCR result with text and bounding boxes
        """
        engine = engine or self._default_engine
        pool = f"gpu-{engine}" if engine == "qwen" else "gpu-paddle"

        worker_service = self._frame.get_service("workers")
        if not worker_service:
            raise RuntimeError("Worker service not available")

        job_id = await worker_service.enqueue(
            pool=pool,
            payload={
                "image_path": image_path,
                "lang": language,
                "job_type": "ocr_page",
            },
        )

        result = await worker_service.wait_for_result(job_id)
        return result

    async def ocr_document(
        self,
        document_id: str,
        engine: str | None = None,
        language: str = "en",
    ) -> dict:
        """
        OCR all pages of a document.

        Args:
            document_id: Document ID to process
            engine: OCR engine to use
            language: Language code

        Returns:
            Combined OCR results for all pages
        """
        # Emit start event
        event_bus = self._frame.get_service("events")
        if event_bus:
            await event_bus.emit(
                "ocr.document.started",
                {"document_id": document_id, "engine": engine or self._default_engine},
                source="ocr-shard",
            )

        # Get document pages from storage
        doc_service = self._frame.get_service("documents")
        if not doc_service:
            raise RuntimeError("Document service not available")

        # In production: get page paths from document service
        # pages = await doc_service.get_pages(document_id)
        # For now, return placeholder

        result = {
            "document_id": document_id,
            "engine": engine or self._default_engine,
            "pages_processed": 0,
            "total_text": "",
            "status": "completed",
        }

        # Emit completion event
        if event_bus:
            await event_bus.emit(
                "ocr.document.completed",
                result,
                source="ocr-shard",
            )

        return result
