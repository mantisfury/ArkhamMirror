"""Ingest Shard - Document ingestion and file processing."""

import logging
from pathlib import Path

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .intake import IntakeManager, JobDispatcher

logger = logging.getLogger(__name__)


class IngestShard(ArkhamShard):
    """
    Document ingestion shard for ArkhamFrame.

    Handles:
    - File upload and intake
    - File type classification
    - Image quality assessment (CLEAN/FIXABLE/MESSY)
    - Job creation and worker dispatch
    - Progress tracking
    """

    name = "ingest"
    version = "0.1.0"
    description = "Document ingestion and file processing"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.intake_manager: IntakeManager | None = None
        self.job_dispatcher: JobDispatcher | None = None
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

        logger.info("Initializing Ingest Shard...")

        # Get storage paths from config
        data_silo = Path(self._config.get("data_silo_path", "./DataSilo"))
        storage_path = data_silo / "documents"
        temp_path = data_silo / "temp" / "ingest"

        # Get OCR mode from config (auto, fast, quality)
        ocr_mode = self._config.get("ingest_ocr_mode", "auto")

        # Get validation settings from config
        max_file_size_mb = self._config.get("ingest_max_file_size_mb", 100)
        min_file_size = self._config.get("ingest_min_file_size_bytes", 100)
        enable_validation = self._config.get("ingest_enable_validation", True)

        # Get optimization toggles from config
        enable_deduplication = self._config.get("ingest_enable_deduplication", True)
        enable_downscale = self._config.get("ingest_enable_downscale", True)
        skip_blank_pages = self._config.get("ingest_skip_blank_pages", True)

        # Create intake manager with data_silo_path for portable relative paths
        self.intake_manager = IntakeManager(
            storage_path=storage_path,
            temp_path=temp_path,
            ocr_mode=ocr_mode,
            min_file_size=min_file_size,
            max_file_size_mb=max_file_size_mb,
            enable_validation=enable_validation,
            enable_deduplication=enable_deduplication,
            enable_downscale=enable_downscale,
            skip_blank_pages=skip_blank_pages,
            data_silo_path=data_silo,  # For Docker/portable path resolution
        )

        # Create job dispatcher with intake_manager for path resolution
        worker_service = frame.get_service("workers")
        if worker_service:
            self.job_dispatcher = JobDispatcher(worker_service, self.intake_manager)
        else:
            logger.warning("Worker service not available, dispatching disabled")

        # Initialize API with our instances
        event_bus = frame.get_service("events")
        init_api(
            intake_manager=self.intake_manager,
            job_dispatcher=self.job_dispatcher,
            event_bus=event_bus,
            config=self._config,
        )

        # Subscribe to worker events
        if event_bus:
            await event_bus.subscribe("worker.job.completed", self._on_job_completed)
            await event_bus.subscribe("worker.job.failed", self._on_job_failed)

        # Register workers with Frame
        if worker_service:
            from .workers import ExtractWorker, FileWorker, ArchiveWorker, ImageWorker
            worker_service.register_worker(ExtractWorker)
            worker_service.register_worker(FileWorker)
            worker_service.register_worker(ArchiveWorker)
            worker_service.register_worker(ImageWorker)
            logger.info("Registered ingest workers")

        logger.info("Ingest Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Ingest Shard...")

        # Unregister workers
        if self._frame:
            worker_service = self._frame.get_service("workers")
            if worker_service:
                from .workers import ExtractWorker, FileWorker, ArchiveWorker, ImageWorker
                worker_service.unregister_worker(ExtractWorker)
                worker_service.unregister_worker(FileWorker)
                worker_service.unregister_worker(ArchiveWorker)
                worker_service.unregister_worker(ImageWorker)

        # Unsubscribe from events
        if self._frame:
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("worker.job.completed", self._on_job_completed)
                await event_bus.unsubscribe("worker.job.failed", self._on_job_failed)

        self.intake_manager = None
        self.job_dispatcher = None
        logger.info("Ingest Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _on_job_completed(self, event: dict) -> None:
        """Handle worker job completion."""
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        job_id = payload.get("job_id")
        if not job_id:
            return

        job = self.intake_manager.get_job(job_id)
        if not job:
            return  # Not our job

        result = payload.get("result", {})

        # Advance to next worker or complete
        advanced = await self.job_dispatcher.advance(job, result)

        if not advanced:
            # Job complete - register document in Frame's document service
            logger.info(f"Job {job_id} completed successfully")

            # Register the document with the Frame's document service
            # Returns the document ID for the event
            document_id = await self._register_document(job, result)

            event_bus = self._frame.get_service("events")
            if event_bus:
                # Include document_id in result for downstream shards (parse, embed)
                result_with_doc = {**result, "document_id": document_id}
                await event_bus.emit(
                    "ingest.job.completed",
                    {
                        "job_id": job_id,
                        "filename": job.file_info.original_name,
                        "result": result_with_doc,
                    },
                    source="ingest-shard",
                )

    async def _register_document(self, job, result: dict) -> str | None:
        """
        Register completed document with Frame's document service.

        Creates a document record in arkham_frame.documents so it can be
        browsed and searched by the documents shard.

        Returns:
            Document ID if successfully registered, None otherwise.
        """
        doc_service = self._frame.get_service("documents")
        if not doc_service:
            logger.warning("Document service not available, skipping registration")
            return None

        try:
            # Read file content for storage
            file_path = job.file_info.path
            with open(file_path, "rb") as f:
                content = f.read()

            # Create document in Frame's document service
            doc = await doc_service.create_document(
                filename=job.file_info.original_name,
                content=content,
                project_id=None,  # Could be extracted from job metadata
                metadata={
                    "ingest_job_id": job.id,
                    "category": job.file_info.category.value,
                    "mime_type": job.file_info.mime_type,
                    "checksum": job.file_info.checksum,
                    "storage_path": str(file_path),
                    "quality_score": (
                        {
                            "classification": job.quality_score.classification.value,
                            "issues": job.quality_score.issues,
                        }
                        if job.quality_score
                        else None
                    ),
                },
            )

            # Update status to processed
            await doc_service.update_document(doc.id, status="processed")

            # If we have extracted text from the result, add it as a page
            text = result.get("text", "")
            if text:
                page_count = result.get("pages", 1)
                await doc_service.add_page(
                    doc_id=doc.id,
                    page_number=1,
                    text=text,
                )

            logger.info(f"Registered document {doc.id} from job {job.id}")
            return doc.id

        except Exception as e:
            logger.error(f"Failed to register document for job {job.id}: {e}", exc_info=True)
            return None

    async def _on_job_failed(self, event: dict) -> None:
        """Handle worker job failure."""
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        job_id = payload.get("job_id")
        if not job_id:
            return

        job = self.intake_manager.get_job(job_id)
        if not job:
            return  # Not our job

        error = payload.get("error", "Unknown error")
        logger.warning(f"Job {job_id} failed: {error}")

        # Update job status
        self.intake_manager.update_job_status(
            job_id,
            status=job.status,  # Will be updated to FAILED
            error=error,
        )

        # Attempt retry
        if job.can_retry:
            logger.info(f"Retrying job {job_id} (attempt {job.retry_count + 1}/{job.max_retries})")
            await self.job_dispatcher.retry(job)
        else:
            logger.error(f"Job {job_id} exhausted retries, marking as dead")
            job.status = job.status.DEAD

            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.emit(
                    "ingest.job.failed",
                    {
                        "job_id": job_id,
                        "filename": job.file_info.original_name,
                        "error": error,
                        "retries": job.retry_count,
                    },
                    source="ingest-shard",
                )

    # --- Public API for other shards ---

    async def ingest_file(self, file, filename: str, priority: str = "user"):
        """
        Public method for other shards to trigger ingestion.

        Args:
            file: File-like object
            filename: Original filename
            priority: "user", "batch", or "reprocess"

        Returns:
            IngestJob
        """
        from .models import JobPriority

        try:
            job_priority = JobPriority[priority.upper()]
        except KeyError:
            job_priority = JobPriority.USER

        job = await self.intake_manager.receive_file(file, filename, job_priority)
        await self.job_dispatcher.dispatch(job)
        return job

    async def ingest_path(self, path: str, recursive: bool = True, priority: str = "batch"):
        """
        Public method to ingest from a filesystem path.

        Args:
            path: File or directory path
            recursive: Recurse into directories
            priority: Job priority

        Returns:
            IngestBatch
        """
        from .models import JobPriority

        try:
            job_priority = JobPriority[priority.upper()]
        except KeyError:
            job_priority = JobPriority.BATCH

        batch = await self.intake_manager.receive_path(
            Path(path),
            priority=job_priority,
            recursive=recursive,
        )

        for job in batch.jobs:
            await self.job_dispatcher.dispatch(job)

        return batch

    def get_job_status(self, job_id: str):
        """Get status of a job."""
        return self.intake_manager.get_job(job_id)

    def get_batch_status(self, batch_id: str):
        """Get status of a batch."""
        return self.intake_manager.get_batch(batch_id)
