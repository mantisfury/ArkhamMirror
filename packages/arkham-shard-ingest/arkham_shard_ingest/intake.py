"""File intake and job management."""

import hashlib
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import aiofiles

from .classifiers import FileTypeClassifier, ImageQualityClassifier
from .classifiers.file_type import TYPICAL_ARCHIVE_MIMES
from .models import (
    FileCategory,
    FileInfo,
    ImageQuality,
    IngestBatch,
    IngestJob,
    JobPriority,
    JobStatus,
)

logger = logging.getLogger(__name__)

# Import wide event logging (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error, log_error_with_context
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    def log_operation(*args, **kwargs):
        from contextlib import nullcontext
        return nullcontext(None)
    def emit_wide_error(*args, **kwargs):
        pass
    def log_error_with_context(*args, **kwargs):
        pass

# Route steps (from file_type classifier) that are logical steps, not frame worker pool names.
# Map them to actual frame worker pools so enqueue() succeeds.
ROUTE_STEP_TO_POOL = {
    "IMAGES->ocr_route": "gpu-paddle",  # OCR for extracted document images; frame has gpu-paddle, gpu-qwen
}


def _resolve_pool_spec(pool_spec: str) -> tuple[str, str | None]:
    """Resolve a route step (e.g. IMAGES->ocr_route) or pool:operation to (pool, operation)."""
    if pool_spec in ROUTE_STEP_TO_POOL:
        return ROUTE_STEP_TO_POOL[pool_spec], None
    if ":" in pool_spec:
        pool, operation = pool_spec.split(":", 1)
        return pool, operation
    return pool_spec, None


class ValidationError(Exception):
    """Raised when file validation fails."""
    pass


class IntakeManager:
    """
    Manages file intake, classification, and job creation.

    Uses an in-memory cache for performance while persisting changes to
    the database through the shard's persistence methods. When a job/batch
    is requested, it's first checked in the cache. If not found, it can be
    loaded from the database.
    """

    # Validation defaults
    DEFAULT_MIN_SIZE_BYTES = 100  # Files smaller than this are likely corrupt
    DEFAULT_MAX_SIZE_MB = 100  # 100MB default limit

    def __init__(
        self,
        storage_path: Path,
        temp_path: Path | None = None,
        ocr_mode: str = "auto",
        min_file_size: int | None = None,
        max_file_size_mb: int | None = None,
        enable_validation: bool = True,
        enable_deduplication: bool = True,
        enable_downscale: bool = True,
        skip_blank_pages: bool = True,
        data_silo_path: Path | None = None,
        shard=None,
        use_magika: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.temp_path = Path(temp_path) if temp_path else self.storage_path / "temp"
        # Store base path for creating portable relative paths
        # This allows workers in different environments (Docker vs host) to resolve paths
        self.data_silo_path = Path(data_silo_path).resolve() if data_silo_path else self.storage_path.parent.resolve()
        self.ocr_mode = ocr_mode
        self.enable_validation = enable_validation
        self.enable_deduplication = enable_deduplication
        self.enable_downscale = enable_downscale
        self.skip_blank_pages = skip_blank_pages
        self.min_file_size = min_file_size if min_file_size is not None else self.DEFAULT_MIN_SIZE_BYTES
        self.max_file_size = (max_file_size_mb if max_file_size_mb is not None else self.DEFAULT_MAX_SIZE_MB) * 1024 * 1024

        # Shard reference for database persistence
        self._shard = shard

        # Ensure directories exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

        # Classifiers (use_magika: content-based MIME via Magika when available)
        self.file_classifier = FileTypeClassifier(use_magika=use_magika)
        self.image_classifier = ImageQualityClassifier()

        # Active jobs and batches (in-memory cache)
        self._jobs: dict[str, IngestJob] = {}
        self._batches: dict[str, IngestBatch] = {}

        # Deduplication: checksum -> job_id (loaded from DB on startup)
        self._checksums: dict[str, str] = {}

    def set_shard(self, shard) -> None:
        """Set the shard reference for database persistence."""
        self._shard = shard
        logger.debug("IntakeManager: shard reference set for persistence")

    async def initialize_from_db(self) -> None:
        """Load checksums from database for deduplication on startup."""
        if self._shard:
            self._checksums = await self._shard._load_checksums()
            logger.info(f"Loaded {len(self._checksums)} checksums from database")

    def get_relative_path(self, absolute_path: Path) -> str:
        """
        Convert an absolute path to a path relative to data_silo_path.

        This ensures portability across different environments (Docker, host, etc.)
        """
        try:
            return str(absolute_path.resolve().relative_to(self.data_silo_path))
        except ValueError:
            # Path is not under data_silo_path, return as-is
            logger.warning(f"Path {absolute_path} is not under {self.data_silo_path}")
            return str(absolute_path)

    async def receive_file(
        self,
        file: BinaryIO,
        filename: str,
        priority: JobPriority = JobPriority.USER,
        ocr_mode: str | None = None,
        project_id: str | None = None,
        original_file_path: str | None = None,
        provenance: dict | None = None,
        extract_archives: bool = False,
        from_archive: bool = False,
        source_archive_document_id: str | None = None,
        archive_member_path: str | None = None,
    ) -> IngestJob:
        """
        Receive an uploaded file and create an ingest job.

        Args:
            file: File-like object with the content
            filename: Original filename (unsanitized; stored in metadata as original_filename)
            priority: Job priority level
            ocr_mode: OCR routing mode override (auto, paddle_only, qwen_only).
                      If None, uses the instance default.
            project_id: Project ID to associate the document with
            original_file_path: Optional path (e.g. from path-based ingest); stored in metadata
            provenance: Optional dict (source_url, source_description, custodian, acquisition_date, etc.)

        Returns:
            Created IngestJob
        """
        # Use request-level ocr_mode if provided, otherwise fall back to instance default
        effective_ocr_mode = ocr_mode if ocr_mode else self.ocr_mode
        # Generate unique ID (must be <= 36 chars for document_metadata.ingest_job_id)
        job_id = str(uuid.uuid4())

        with log_operation("ingest.receive_file", job_id=job_id, filename=filename) as event:
            if event:
                event.input(filename=filename, project_id=project_id, priority=priority.value)

            # Save to temp location
            safe_filename = self._sanitize_filename(filename)
            temp_file = self.temp_path / f"{job_id}_{safe_filename}"

            # Calculate checksum while saving
            checksum = hashlib.sha256()
            async with aiofiles.open(temp_file, "wb") as f:
                while chunk := file.read(65536):
                    await f.write(chunk)
                    checksum.update(chunk)

            file_hash = checksum.hexdigest()

            # Deduplication check: if we've seen this file before, return existing job
            if self.enable_deduplication:
                # Check cache first
                existing_job_id = self._checksums.get(file_hash)

                # If not in cache, check database
                if not existing_job_id and self._shard:
                    existing_job_id = await self._shard._check_duplicate(file_hash)
                    if existing_job_id:
                        self._checksums[file_hash] = existing_job_id  # Cache it

                if existing_job_id:
                    existing_job = self._jobs.get(existing_job_id)
                    # If not in cache, load from database
                    if not existing_job and self._shard:
                        existing_job = await self._shard._load_job(existing_job_id)
                        if existing_job:
                            self._jobs[existing_job_id] = existing_job  # Cache it

                    if existing_job:
                        # Clean up temp file and return existing job
                        temp_file.unlink(missing_ok=True)
                        logger.info(
                            f"Duplicate detected: {filename} matches existing job {existing_job_id}"
                        )
                        if event:
                            event.output(
                                job_id=existing_job_id,
                                duplicate=True,
                                category=existing_job.file_info.category.value,
                                route=existing_job.worker_route,
                            )
                        return existing_job

            # Get extension for validation
            extension = Path(filename).suffix.lower()

            # Early validation: reject corrupt/invalid files before processing
            try:
                self._validate_file(temp_file, extension)
            except ValidationError as e:
                temp_file.unlink(missing_ok=True)
                logger.warning(f"Validation failed for {filename}: {e}")
                raise

            # Classify file
            file_info = self.file_classifier.classify(temp_file)
            file_info.original_name = filename
            file_info.checksum = file_hash

            # Create job with route
            route = self._determine_route(file_info)

            job = IngestJob(
                id=job_id,
                file_info=file_info,
                priority=priority,
                worker_route=route,
                project_id=project_id,
                original_file_path=original_file_path,
                provenance=provenance,
                extract_archives=extract_archives,
                from_archive=from_archive,
                source_archive_document_id=source_archive_document_id,
                archive_member_path=archive_member_path,
            )

            # Quality classification for images
            if file_info.category == FileCategory.IMAGE:
                job.quality_score = self.image_classifier.classify(temp_file)
                # Update route based on quality
                job.worker_route = self.image_classifier.get_ocr_route(
                    job.quality_score,
                    ocr_mode=effective_ocr_mode,
                    enable_downscale=self.enable_downscale,
                    skip_blank_pages=self.skip_blank_pages,
                )

            # Move to permanent storage
            permanent_path = self._get_storage_path(job_id, file_info)
            permanent_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(temp_file, permanent_path)
            job.file_info.path = permanent_path

            # Track job and checksum for deduplication (cache)
            self._jobs[job_id] = job
            self._checksums[file_hash] = job_id

            # Persist to database
            if self._shard:
                start_persist = time.time()
                try:
                    await self._shard._save_job(job)
                    await self._shard._record_checksum(file_hash, job_id, filename)
                    logger.debug("receive_file: job persisted job_id=%s", job_id)
                    if event:
                        event.dependency("persist", duration_ms=int((time.time() - start_persist) * 1000))
                except Exception as e:
                    if event:
                        event.dependency("persist", duration_ms=int((time.time() - start_persist) * 1000), error=str(e))
                    log_error_with_context(
                        logger,
                        "Failed to persist job to database",
                        exc=e,
                        job_id=job_id,
                        job_id_len=len(job_id),
                        filename=filename,
                    )
                    emit_wide_error(event, "PersistJobFailed", str(e), exc=e)

            logger.info(
                "Received file: filename=%s job_id=%s category=%s route=%s",
                filename,
                job_id,
                file_info.category.value,
                route,
            )

            if event:
                event.output(job_id=job.id, category=job.file_info.category.value, route=job.worker_route)

            return job

    async def receive_batch(
        self,
        files: list[tuple[BinaryIO, str]],
        priority: JobPriority = JobPriority.BATCH,
        ocr_mode: str | None = None,
        project_id: str | None = None,
        provenance: dict | None = None,
        extract_archives: bool = False,
    ) -> IngestBatch:
        """
        Receive multiple files as a batch.

        Args:
            files: List of (file, filename) tuples
            priority: Priority for all jobs in batch
            ocr_mode: OCR routing mode override for all files in batch
            project_id: Project ID to associate all documents with
            provenance: Optional provenance dict applied to all files in batch

        Returns:
            Created IngestBatch
        """
        batch_id = str(uuid.uuid4())
        batch = IngestBatch(
            id=batch_id,
            priority=priority,
            total_files=len(files),
        )

        for file, filename in files:
            try:
                job = await self.receive_file(
                    file, filename, priority,
                    ocr_mode=ocr_mode, project_id=project_id,
                    provenance=provenance,
                    extract_archives=extract_archives,
                )
                batch.jobs.append(job)
            except Exception as e:
                logger.error(f"Failed to receive {filename}: {e}")
                batch.failed += 1

        self._batches[batch_id] = batch

        # Persist to database
        if self._shard:
            try:
                await self._shard._save_batch(batch)
            except Exception as e:
                log_error_with_context(
                    logger,
                    "Failed to persist batch to database",
                    exc=e,
                    exc_info=True,
                    batch_id=batch_id,
                )

        return batch

    async def receive_path(
        self,
        path: Path,
        priority: JobPriority = JobPriority.BATCH,
        recursive: bool = True,
        ocr_mode: str | None = None,
        project_id: str | None = None,
    ) -> IngestBatch:
        """
        Ingest files from a local path.

        Args:
            path: File or directory path
            priority: Job priority
            recursive: If directory, recurse into subdirectories
            ocr_mode: OCR routing mode override
            project_id: Project ID to associate all documents with

        Returns:
            Created IngestBatch
        """
        path = Path(path)

        if path.is_file():
            # Single file; pass original path for metadata
            with open(path, "rb") as f:
                job = await self.receive_file(
                    f, path.name, priority,
                    ocr_mode=ocr_mode, project_id=project_id,
                    original_file_path=str(path.resolve()),
                )
            batch = IngestBatch(
                id=str(uuid.uuid4()),
                jobs=[job],
                priority=priority,
                total_files=1,
            )
            self._batches[batch.id] = batch
            return batch

        elif path.is_dir():
            # Directory
            files = []
            pattern = "**/*" if recursive else "*"
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    files.append((open(file_path, "rb"), file_path.name))

            batch = await self.receive_batch(files, priority, ocr_mode=ocr_mode, project_id=project_id)

            # Close file handles
            for f, _ in files:
                f.close()

            return batch

        else:
            raise FileNotFoundError(f"Path not found: {path}")

    async def create_job_from_path(
        self,
        path: Path,
        priority: JobPriority = JobPriority.BATCH,
        project_id: str | None = None,
        from_archive: bool = False,
        source_archive_document_id: str | None = None,
        archive_member_path: str | None = None,
    ) -> IngestJob:
        """
        Create an ingest job from an existing file path (e.g. extracted from an archive).
        Does not copy the file; the path is used as-is.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Not a file: {path}")

        file_info = self.file_classifier.classify(path)
        file_info.original_name = path.name
        file_info.path = path

        route = self._determine_route(file_info)
        job_id = str(uuid.uuid4())

        with log_operation("ingest.create_job_from_path", job_id=job_id, path=str(path)) as event:
            if event:
                event.input(path=str(path), project_id=project_id, from_archive=from_archive)

            job = IngestJob(
                id=job_id,
                file_info=file_info,
                priority=priority,
                worker_route=route,
                project_id=project_id,
                from_archive=from_archive,
                source_archive_document_id=source_archive_document_id,
                archive_member_path=archive_member_path,
            )

            self._jobs[job_id] = job
            if self._shard:
                try:
                    await self._shard._save_job(job)
                except Exception as e:
                    log_error_with_context(
                        logger,
                        "Failed to persist job from path",
                        exc=e,
                        exc_info=True,
                        job_id=job_id,
                        path=str(path),
                    )
                    emit_wide_error(event, "PersistJobFailed", str(e), exc=e)

            logger.info(
                f"Created job from path: {path.name} -> {job_id} "
                f"(from_archive={from_archive}, route={route})"
            )
            if event:
                event.output(job_id=job_id, route=route)
            return job

    def get_job(self, job_id: str) -> IngestJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_batch(self, batch_id: str) -> IngestBatch | None:
        """Get a batch by ID."""
        return self._batches.get(batch_id)

    def get_pending_jobs(self, limit: int = 100) -> list[IngestJob]:
        """Get pending jobs, sorted by priority."""
        pending = [j for j in self._jobs.values() if j.status == JobStatus.PENDING]
        # Sort by priority (lower = higher priority)
        pending.sort(key=lambda j: (j.priority.value, j.created_at))
        return pending[:limit]

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Update job status."""
        job = self._jobs.get(job_id)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return

        job.status = status

        if status == JobStatus.PROCESSING:
            job.started_at = datetime.utcnow()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD):
            job.completed_at = datetime.utcnow()

        if result:
            job.result = result
        if error:
            job.error = error
            job.retry_count += 1

        # Persist to database
        if self._shard:
            try:
                await self._shard._update_job_status(job_id, status, error, result)
            except Exception as e:
                log_error_with_context(
                    logger,
                    "Failed to persist job status",
                    exc=e,
                    exc_info=True,
                    job_id=job_id,
                )

        # Update batch if applicable
        batch_id = None
        for batch in self._batches.values():
            if job in batch.jobs:
                batch_id = batch.id
                if status == JobStatus.COMPLETED:
                    batch.completed += 1
                elif status in (JobStatus.FAILED, JobStatus.DEAD):
                    batch.failed += 1
                if batch.is_complete:
                    batch.completed_at = datetime.utcnow()

        # Update batch progress in database
        if batch_id and self._shard:
            try:
                await self._shard._update_batch_progress(batch_id)
            except Exception as e:
                log_error_with_context(
                    logger,
                    "Failed to persist batch progress",
                    exc=e,
                    exc_info=True,
                    batch_id=batch_id,
                )

    def _determine_route(self, file_info: FileInfo) -> list[str]:
        """Determine initial worker route for file."""
        return self.file_classifier.get_route(file_info)

    def _get_storage_path(self, job_id: str, file_info: FileInfo) -> Path:
        """Get permanent storage path for a file. Uses sanitized filename (max 64 chars) for on-disk name."""
        date_str = datetime.utcnow().strftime("%Y/%m/%d")
        category = file_info.category.value
        safe_filename = self._sanitize_filename(file_info.original_name)
        return self.storage_path / date_str / category / f"{job_id}_{safe_filename}"

    MAX_INTERNAL_FILENAME_CHARS = 64

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe on-disk storage.
        Internal filename is at most MAX_INTERNAL_FILENAME_CHARS (64).
        If longer, truncate name part and append 8-char hash of full name.
        Caller should store original in metadata as original_filename.
        """
        import re
        import unicodedata

        if not filename:
            return "unnamed"

        # Normalize unicode (NFC form)
        safe = unicodedata.normalize('NFC', filename)

        # Replace path separators
        safe = re.sub(r'[/\\]', '_', safe)

        # Block directory traversal patterns
        safe = re.sub(r'\.\.+', '_', safe)

        # Remove control characters (U+0000-U+001F and U+007F-U+009F)
        safe = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe)

        # Replace Windows-forbidden characters
        safe = re.sub(r'[<>:"|?*]', '_', safe)

        # Collapse multiple underscores
        safe = re.sub(r'_+', '_', safe)

        # Strip leading/trailing dots, spaces, and underscores
        safe = safe.strip('. \t_')

        # Block Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{i}' for i in range(1, 10)} | {f'LPT{i}' for i in range(1, 10)}
        name_part = safe.split('.')[0].upper() if '.' in safe else safe.upper()
        if name_part in reserved:
            safe = f"file_{safe}"

        # Internal filename length cap: max 64 chars (name + _ + 8-char hash + ext)
        max_len = self.MAX_INTERNAL_FILENAME_CHARS
        if '.' in safe:
            name_part, ext_part = safe.rsplit('.', 1)
            ext_part = ext_part[:10]  # limit extension
            # space for: name + "_" + 8-char hash + "." + ext
            name_max = max_len - 1 - 8 - 1 - len(ext_part)
            if name_max < 1:
                name_max = 1
            if len(name_part) > name_max:
                suffix = hashlib.sha256(safe.encode("utf-8", errors="replace")).hexdigest()[:8]
                name_part = name_part[:name_max] + "_" + suffix
            safe = name_part + "." + ext_part
        else:
            if len(safe) > max_len - 9:  # leave room for _ + 8-char hash
                suffix = hashlib.sha256(safe.encode("utf-8", errors="replace")).hexdigest()[:8]
                safe = safe[: max_len - 1 - 8] + "_" + suffix

        return safe[:max_len] if len(safe) > max_len else (safe or "unnamed")

    def _validate_file(self, path: Path, extension: str) -> None:
        """
        Validate file before processing.

        Raises:
            ValidationError: If file fails validation
        """
        if not self.enable_validation:
            return

        size = path.stat().st_size

        # Size checks
        if size < self.min_file_size:
            raise ValidationError(
                f"File too small ({size} bytes). Minimum is {self.min_file_size} bytes."
            )
        if size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            raise ValidationError(
                f"File too large ({size / (1024*1024):.1f}MB). Maximum is {max_mb:.0f}MB."
            )

        # Format-specific validation
        ext = extension.lower()

        # Validate images can be opened
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"):
            try:
                from PIL import Image
                with Image.open(path) as img:
                    img.verify()  # Verify it's a valid image
            except Exception as e:
                raise ValidationError(f"Invalid image file: {e}")

        # Validate PDFs can be read
        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                page_count = len(reader.pages)
                if page_count == 0:
                    raise ValidationError("PDF has no pages")
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f"Invalid PDF file: {e}")


class JobDispatcher:
    """
    Dispatches jobs to worker pools.
    """

    def __init__(
        self,
        worker_service,
        intake_manager: IntakeManager | None = None,
        on_completed_without_worker=None,
    ):
        """
        Args:
            worker_service: Frame's WorkerService instance
            intake_manager: IntakeManager for path resolution (optional for backwards compat)
            on_completed_without_worker: Optional async callback(job) when job completed without enqueueing (e.g. archive with extract_archives=False)
        """
        self.worker_service = worker_service
        self.intake_manager = intake_manager
        self._on_completed_without_worker = on_completed_without_worker
        self._active_jobs: dict[str, str] = {}  # job_id -> worker_pool

    async def dispatch(self, job: IngestJob) -> bool:
        """
        Dispatch a job to its first worker pool.

        Returns:
            True if dispatched successfully (or completed without worker)
        """
        if not job.worker_route:
            logger.info(f"Job {job.id} has empty route - completing without processing")
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = {
                "skipped": True,
                "reason": "blank_page" if (job.quality_score and job.quality_score.is_blank) else "empty_route",
            }
            return True

        mime = (job.file_info.mime_type or "").strip()
        is_typical_archive = mime in TYPICAL_ARCHIVE_MIMES
        extract_archives = getattr(job, "extract_archives", False)
        if (
            job.file_info.category == FileCategory.ARCHIVE
            and is_typical_archive
            and not extract_archives
        ):
            logger.info(f"Job {job.id} is typical archive but extract_archives=False - completing without extraction")
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = {"document_metadata": {"is_archive": True}}
            if self._on_completed_without_worker:
                await self._on_completed_without_worker(job)
            return True

        pool_spec = job.worker_route[0]
        job.current_worker = pool_spec
        job.status = JobStatus.QUEUED

        pool, operation = _resolve_pool_spec(pool_spec)

        try:
            if self.intake_manager:
                file_path = self.intake_manager.get_relative_path(job.file_info.path)
            else:
                file_path = str(job.file_info.path.resolve())

            payload = {
                "file_path": file_path,
                "file_info": {
                    "name": job.file_info.original_name,
                    "mime_type": job.file_info.mime_type,
                    "category": job.file_info.category.value,
                    "size": job.file_info.size_bytes,
                },
                "quality_score": (
                    {
                        "classification": job.quality_score.classification.value,
                        "issues": job.quality_score.issues,
                        "analysis_ms": job.quality_score.analysis_ms,
                    }
                    if job.quality_score
                    else None
                ),
                "route": job.worker_route,
                "route_index": 0,
            }

            if operation:
                payload["operation"] = operation

            if pool == "cpu-archive" and is_typical_archive and extract_archives:
                payload["operation"] = "extract"
                payload["archive_path"] = file_path
                if self.intake_manager:
                    output_dir = self.intake_manager.storage_path / job.id / "extracted"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    payload["output_dir"] = self.intake_manager.get_relative_path(output_dir)
                else:
                    payload["output_dir"] = str(Path(file_path).parent / job.id / "extracted")

            await self.worker_service.enqueue(
                pool=pool,
                job_id=job.id,
                payload=payload,
                priority=job.priority.value,
            )

            self._active_jobs[job.id] = pool
            logger.info(f"Dispatched job {job.id} to {pool}")
            return True

        except Exception as e:
            log_error_with_context(
                logger,
                "Failed to dispatch job",
                exc=e,
                exc_info=True,
                job_id=job.id,
            )
            job.status = JobStatus.FAILED
            job.error = str(e)
            return False

    async def advance(self, job: IngestJob, result: dict) -> bool:
        """
        Advance a job to the next worker in its route.

        Called when a worker completes its step.

        Returns:
            True if advanced to next step, False if complete
        """
        # Find current position in route
        try:
            current_idx = job.worker_route.index(job.current_worker)
        except ValueError:
            current_idx = 0

        next_idx = current_idx + 1

        if next_idx >= len(job.worker_route):
            # Route complete
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            del self._active_jobs[job.id]
            return False

        # Dispatch to next worker (may include operation suffix like "cpu-image:downscale")
        pool_spec = job.worker_route[next_idx]
        job.current_worker = pool_spec

        pool, operation = _resolve_pool_spec(pool_spec)

        # Build payload with accumulated results
        payload = {
            **result,  # Pass along accumulated results
            "route": job.worker_route,
            "route_index": next_idx,
        }

        # Add operation if specified in pool name
        if operation:
            payload["operation"] = operation

        await self.worker_service.enqueue(
            pool=pool,
            job_id=job.id,
            payload=payload,
            priority=job.priority.value,
        )

        self._active_jobs[job.id] = pool
        return True

    async def retry(self, job: IngestJob) -> bool:
        """
        Retry a failed job.

        Returns:
            True if retried, False if max retries exceeded
        """
        if not job.can_retry:
            job.status = JobStatus.DEAD
            return False

        job.status = JobStatus.PENDING
        job.error = None
        return await self.dispatch(job)
