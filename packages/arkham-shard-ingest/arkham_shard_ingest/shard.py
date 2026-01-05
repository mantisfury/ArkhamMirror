"""Ingest Shard - Document ingestion and file processing."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .intake import IntakeManager, JobDispatcher
from .models import (
    FileCategory,
    FileInfo,
    ImageQuality,
    ImageQualityScore,
    IngestBatch,
    IngestJob,
    JobPriority,
    JobStatus,
)

logger = logging.getLogger(__name__)


def _parse_json_field(value: Any, default: Any = None) -> Any:
    """Parse a JSON field that may already be parsed by the database driver."""
    if value is None:
        return default if default is not None else []
    if isinstance(value, (list, dict)):
        return value  # Already parsed by PostgreSQL JSONB
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []
    return default if default is not None else []


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
        self._db = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame
        self._config = frame.config
        self._db = frame.get_service("database")

        logger.info("Initializing Ingest Shard...")

        # Create database schema
        if self._db:
            await self._create_schema()
        else:
            logger.warning("Database service not available, persistence disabled")

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
            shard=self,  # For database persistence
        )

        # Load checksums from database for deduplication
        if self._db:
            await self.intake_manager.initialize_from_db()

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

        # Recover pending jobs from database and re-dispatch
        if self._db:
            await self._recover_and_dispatch_jobs()

        logger.info("Ingest Shard initialized")

    async def _recover_and_dispatch_jobs(self) -> None:
        """Recover pending jobs from database and re-dispatch them."""
        try:
            pending_jobs = await self._recover_pending_jobs()
            if not pending_jobs:
                return

            # Add to in-memory cache
            for job in pending_jobs:
                self.intake_manager._jobs[job.id] = job

            # Re-dispatch if job dispatcher is available
            if self.job_dispatcher:
                dispatched = 0
                for job in pending_jobs:
                    if await self.job_dispatcher.dispatch(job):
                        dispatched += 1
                logger.info(f"Re-dispatched {dispatched}/{len(pending_jobs)} recovered jobs")
        except Exception as e:
            logger.error(f"Failed to recover pending jobs: {e}")

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
            # Job complete - update status in database
            await self.intake_manager.update_job_status(
                job_id, JobStatus.COMPLETED, result=result
            )
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

            # Build metadata - start with ingest info
            metadata = {
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
            }

            # Add extracted document metadata (author, title, creator, etc.)
            # This comes from PDF/DOCX property extraction in ExtractWorker
            document_metadata = result.get("document_metadata", {})
            if document_metadata:
                # Merge extracted metadata into the main metadata dict
                for key, value in document_metadata.items():
                    if value:  # Only add non-empty values
                        metadata[key] = value
                logger.info(f"Including extracted metadata for job {job.id}: {list(document_metadata.keys())}")

            # Create document in Frame's document service
            doc = await doc_service.create_document(
                filename=job.file_info.original_name,
                content=content,
                project_id=None,  # Could be extracted from job metadata
                metadata=metadata,
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
        await self.intake_manager.update_job_status(
            job_id,
            status=JobStatus.FAILED,
            error=error,
        )

        # Attempt retry
        if job.can_retry:
            logger.info(f"Retrying job {job_id} (attempt {job.retry_count + 1}/{job.max_retries})")
            await self.job_dispatcher.retry(job)
        else:
            logger.error(f"Job {job_id} exhausted retries, marking as dead")
            await self.intake_manager.update_job_status(job_id, status=JobStatus.DEAD)

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

    # --- Database Persistence Methods ---

    async def _create_schema(self) -> None:
        """Create the arkham_ingest database schema."""
        if not self._db:
            return

        logger.info("Creating arkham_ingest schema...")

        await self._db.execute("CREATE SCHEMA IF NOT EXISTS arkham_ingest")

        # Jobs table - stores all ingest job information
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_ingest.jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_path TEXT,
                status TEXT DEFAULT 'pending',
                file_category TEXT,
                mime_type TEXT,
                file_size INTEGER,
                checksum TEXT,
                quality_score JSONB,
                worker_route JSONB DEFAULT '[]',
                current_worker TEXT,
                batch_id TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                error_message TEXT,
                document_id TEXT,
                result JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Batches table - stores batch information
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_ingest.batches (
                id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'batch',
                total_files INTEGER DEFAULT 0,
                completed_files INTEGER DEFAULT 0,
                failed_files INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Checksums table - for deduplication
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_ingest.checksums (
                checksum TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status ON arkham_ingest.jobs(status)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_jobs_batch ON arkham_ingest.jobs(batch_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_jobs_checksum ON arkham_ingest.jobs(checksum)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_batches_status ON arkham_ingest.batches(status)"
        )

        logger.info("arkham_ingest schema created successfully")

    async def _save_job(self, job: IngestJob) -> None:
        """Save a job to the database."""
        if not self._db:
            return

        # Build quality_score JSON
        quality_json = None
        if job.quality_score:
            quality_json = json.dumps({
                "dpi": job.quality_score.dpi,
                "skew_angle": job.quality_score.skew_angle,
                "contrast_ratio": job.quality_score.contrast_ratio,
                "is_grayscale": job.quality_score.is_grayscale,
                "compression_ratio": job.quality_score.compression_ratio,
                "has_noise": job.quality_score.has_noise,
                "layout_complexity": job.quality_score.layout_complexity,
                "is_blank": job.quality_score.is_blank,
                "analysis_ms": job.quality_score.analysis_ms,
            })

        await self._db.execute(
            """
            INSERT INTO arkham_ingest.jobs (
                id, filename, original_path, status, file_category, mime_type,
                file_size, checksum, quality_score, worker_route, current_worker,
                batch_id, retry_count, max_retries, error_message, result,
                created_at, started_at, completed_at
            ) VALUES (
                :id, :filename, :original_path, :status, :file_category, :mime_type,
                :file_size, :checksum, :quality_score, :worker_route, :current_worker,
                :batch_id, :retry_count, :max_retries, :error_message, :result,
                :created_at, :started_at, :completed_at
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                current_worker = EXCLUDED.current_worker,
                retry_count = EXCLUDED.retry_count,
                error_message = EXCLUDED.error_message,
                result = EXCLUDED.result,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at
            """,
            {
                "id": job.id,
                "filename": job.file_info.original_name,
                "original_path": str(job.file_info.path),
                "status": job.status.value,
                "file_category": job.file_info.category.value,
                "mime_type": job.file_info.mime_type,
                "file_size": job.file_info.size_bytes,
                "checksum": job.file_info.checksum,
                "quality_score": quality_json,
                "worker_route": json.dumps(job.worker_route),
                "current_worker": job.current_worker,
                "batch_id": None,
                "retry_count": job.retry_count,
                "max_retries": job.max_retries,
                "error_message": job.error,
                "result": json.dumps(job.result) if job.result else None,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            },
        )

    async def _load_job(self, job_id: str) -> IngestJob | None:
        """Load a job from the database."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_ingest.jobs WHERE id = :id",
            {"id": job_id},
        )

        if not row:
            return None

        return self._row_to_job(row)

    async def _list_jobs(
        self,
        status: str | None = None,
        batch_id: str | None = None,
        limit: int = 100,
    ) -> list[IngestJob]:
        """List jobs with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_ingest.jobs WHERE 1=1"
        params = {"limit": limit}

        if status:
            query += " AND status = :status"
            params["status"] = status

        if batch_id:
            query += " AND batch_id = :batch_id"
            params["batch_id"] = batch_id

        query += " ORDER BY created_at DESC LIMIT :limit"

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_job(row) for row in rows]

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        result: dict | None = None,
    ) -> None:
        """Update job status in the database."""
        if not self._db:
            return

        now = datetime.utcnow()
        started_at = now if status == JobStatus.PROCESSING else None
        completed_at = now if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD) else None

        await self._db.execute(
            """
            UPDATE arkham_ingest.jobs SET
                status = :status,
                error_message = COALESCE(:error_message, error_message),
                result = COALESCE(:result, result),
                started_at = COALESCE(:started_at, started_at),
                completed_at = COALESCE(:completed_at, completed_at)
            WHERE id = :id
            """,
            {
                "id": job_id,
                "status": status.value,
                "error_message": error,
                "result": json.dumps(result) if result else None,
                "started_at": started_at,
                "completed_at": completed_at,
            },
        )

    async def _save_batch(self, batch: IngestBatch) -> None:
        """Save a batch to the database."""
        if not self._db:
            return

        # Determine batch status
        if batch.is_complete:
            status = "completed"
        elif batch.failed > 0 and batch.pending == 0:
            status = "failed"
        elif batch.completed > 0 or batch.failed > 0:
            status = "processing"
        else:
            status = "pending"

        await self._db.execute(
            """
            INSERT INTO arkham_ingest.batches (
                id, name, status, priority, total_files, completed_files,
                failed_files, created_at, completed_at
            ) VALUES (:id, :name, :status, :priority, :total_files, :completed_files,
                :failed_files, :created_at, :completed_at)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                completed_files = EXCLUDED.completed_files,
                failed_files = EXCLUDED.failed_files,
                completed_at = EXCLUDED.completed_at
            """,
            {
                "id": batch.id,
                "name": None,
                "status": status,
                "priority": batch.priority.value if hasattr(batch.priority, 'value') else str(batch.priority),
                "total_files": batch.total_files,
                "completed_files": batch.completed,
                "failed_files": batch.failed,
                "created_at": batch.created_at,
                "completed_at": batch.completed_at,
            },
        )

        # Link jobs to batch
        for job in batch.jobs:
            await self._db.execute(
                "UPDATE arkham_ingest.jobs SET batch_id = :batch_id WHERE id = :id",
                {"id": job.id, "batch_id": batch.id},
            )

    async def _load_batch(self, batch_id: str) -> IngestBatch | None:
        """Load a batch from the database."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_ingest.batches WHERE id = :id",
            {"id": batch_id},
        )

        if not row:
            return None

        # Load jobs for this batch
        jobs = await self._list_jobs(batch_id=batch_id, limit=1000)

        # Parse priority
        try:
            priority = JobPriority[row["priority"].upper()]
        except (KeyError, AttributeError):
            priority = JobPriority.BATCH

        return IngestBatch(
            id=row["id"],
            jobs=jobs,
            priority=priority,
            total_files=row["total_files"],
            completed=row["completed_files"],
            failed=row["failed_files"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    async def _update_batch_progress(self, batch_id: str) -> None:
        """Update batch progress by counting job statuses."""
        if not self._db:
            return

        # Count jobs by status
        result = await self._db.fetch_one(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status IN ('failed', 'dead')) as failed
            FROM arkham_ingest.jobs
            WHERE batch_id = :batch_id
            """,
            {"batch_id": batch_id},
        )

        completed = result["completed"] if result else 0
        failed = result["failed"] if result else 0

        # Determine if batch is complete
        batch_row = await self._db.fetch_one(
            "SELECT total_files FROM arkham_ingest.batches WHERE id = :id",
            {"id": batch_id},
        )
        total = batch_row["total_files"] if batch_row else 0

        status = "processing"
        completed_at = None
        if completed + failed >= total:
            status = "completed" if failed == 0 else "failed"
            completed_at = datetime.utcnow()

        await self._db.execute(
            """
            UPDATE arkham_ingest.batches SET
                status = :status,
                completed_files = :completed_files,
                failed_files = :failed_files,
                completed_at = COALESCE(:completed_at, completed_at)
            WHERE id = :id
            """,
            {
                "id": batch_id,
                "status": status,
                "completed_files": completed,
                "failed_files": failed,
                "completed_at": completed_at,
            },
        )

    async def _check_duplicate(self, checksum: str) -> str | None:
        """Check if a file with this checksum has already been ingested."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT job_id FROM arkham_ingest.checksums WHERE checksum = :checksum",
            {"checksum": checksum},
        )

        return row["job_id"] if row else None

    async def _record_checksum(self, checksum: str, job_id: str, filename: str) -> None:
        """Record a file checksum for deduplication."""
        if not self._db:
            return

        await self._db.execute(
            """
            INSERT INTO arkham_ingest.checksums (checksum, job_id, filename)
            VALUES (:checksum, :job_id, :filename)
            ON CONFLICT (checksum) DO NOTHING
            """,
            {"checksum": checksum, "job_id": job_id, "filename": filename},
        )

    async def _recover_pending_jobs(self) -> list[IngestJob]:
        """
        Load pending/queued jobs from database on startup.

        Jobs that were processing when the server crashed are reset to pending
        for re-dispatch.
        """
        if not self._db:
            return []

        # Reset processing jobs to pending (they were interrupted)
        await self._db.execute(
            """
            UPDATE arkham_ingest.jobs
            SET status = 'pending', current_worker = NULL
            WHERE status IN ('queued', 'processing')
            """
        )

        # Load all pending jobs
        jobs = await self._list_jobs(status="pending", limit=1000)
        logger.info(f"Recovered {len(jobs)} pending jobs from database")

        return jobs

    async def _load_checksums(self) -> dict[str, str]:
        """Load all checksums from database for deduplication cache."""
        if not self._db:
            return {}

        rows = await self._db.fetch_all(
            "SELECT checksum, job_id FROM arkham_ingest.checksums"
        )

        return {row["checksum"]: row["job_id"] for row in rows}

    def _row_to_job(self, row) -> IngestJob:
        """Convert a database row to an IngestJob object."""
        # Parse quality score
        quality_score = None
        quality_data = _parse_json_field(row.get("quality_score"), {})
        if quality_data:
            quality_score = ImageQualityScore(
                dpi=quality_data.get("dpi", 150),
                skew_angle=quality_data.get("skew_angle", 0.0),
                contrast_ratio=quality_data.get("contrast_ratio", 1.0),
                is_grayscale=quality_data.get("is_grayscale", False),
                compression_ratio=quality_data.get("compression_ratio", 1.0),
                has_noise=quality_data.get("has_noise", False),
                layout_complexity=quality_data.get("layout_complexity", "simple"),
                is_blank=quality_data.get("is_blank", False),
                analysis_ms=quality_data.get("analysis_ms", 0.0),
            )

        # Parse file category
        try:
            category = FileCategory[row["file_category"].upper()]
        except (KeyError, AttributeError):
            category = FileCategory.UNKNOWN

        # Parse status
        try:
            status = JobStatus[row["status"].upper()]
        except (KeyError, AttributeError):
            status = JobStatus.PENDING

        # Parse priority (default to USER for recovered jobs)
        priority = JobPriority.USER

        # Build FileInfo
        file_info = FileInfo(
            path=Path(row["original_path"]) if row.get("original_path") else Path("."),
            original_name=row["filename"],
            size_bytes=row.get("file_size", 0),
            mime_type=row.get("mime_type", "application/octet-stream"),
            category=category,
            extension=Path(row["filename"]).suffix if row.get("filename") else "",
            checksum=row.get("checksum"),
        )

        # Build IngestJob
        return IngestJob(
            id=row["id"],
            file_info=file_info,
            priority=priority,
            status=status,
            worker_route=_parse_json_field(row.get("worker_route"), []),
            current_worker=row.get("current_worker"),
            quality_score=quality_score,
            created_at=row.get("created_at", datetime.utcnow()),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            result=_parse_json_field(row.get("result"), None),
            error=row.get("error_message"),
            retry_count=row.get("retry_count", 0),
            max_retries=row.get("max_retries", 3),
        )
