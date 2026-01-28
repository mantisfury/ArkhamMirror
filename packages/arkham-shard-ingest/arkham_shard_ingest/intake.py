"""File intake and job management."""

import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import aiofiles

from .classifiers import FileTypeClassifier, ImageQualityClassifier
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

        # Classifiers
        self.file_classifier = FileTypeClassifier()
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
    ) -> IngestJob:
        """
        Receive an uploaded file and create an ingest job.

        Args:
            file: File-like object with the content
            filename: Original filename
            priority: Job priority level
            ocr_mode: OCR routing mode override (auto, paddle_only, qwen_only).
                      If None, uses the instance default.
            project_id: Project ID to associate the document with

        Returns:
            Created IngestJob
        """
        # Use request-level ocr_mode if provided, otherwise fall back to instance default
        effective_ocr_mode = ocr_mode if ocr_mode else self.ocr_mode
        # Generate unique ID
        job_id = str(uuid.uuid4())

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
            try:
                await self._shard._save_job(job)
                await self._shard._record_checksum(file_hash, job_id, filename)
            except Exception as e:
                logger.error(f"Failed to persist job {job_id} to database: {e}")

        logger.info(
            f"Received file: {filename} -> job {job_id} "
            f"(category={file_info.category.value}, route={route})"
        )

        return job

    async def receive_batch(
        self,
        files: list[tuple[BinaryIO, str]],
        priority: JobPriority = JobPriority.BATCH,
        ocr_mode: str | None = None,
        project_id: str | None = None,
    ) -> IngestBatch:
        """
        Receive multiple files as a batch.

        Args:
            files: List of (file, filename) tuples
            priority: Priority for all jobs in batch
            ocr_mode: OCR routing mode override for all files in batch
            project_id: Project ID to associate all documents with

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
                job = await self.receive_file(file, filename, priority, ocr_mode=ocr_mode, project_id=project_id)
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
                logger.error(f"Failed to persist batch {batch_id} to database: {e}")

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
            # Single file
            with open(path, "rb") as f:
                job = await self.receive_file(f, path.name, priority, ocr_mode=ocr_mode, project_id=project_id)
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
                logger.error(f"Failed to persist job status {job_id}: {e}")

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
                logger.error(f"Failed to persist batch progress {batch_id}: {e}")

    def _determine_route(self, file_info: FileInfo) -> list[str]:
        """Determine initial worker route for file."""
        return self.file_classifier.get_route(file_info)

    def _get_storage_path(self, job_id: str, file_info: FileInfo) -> Path:
        """Get permanent storage path for a file."""
        # Organize by date and category
        date_str = datetime.utcnow().strftime("%Y/%m/%d")
        category = file_info.category.value
        ext = file_info.extension

        return self.storage_path / date_str / category / f"{job_id}{ext}"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
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

        # Limit length while preserving extension
        if len(safe) > 200:
            if '.' in safe:
                name, ext = safe.rsplit('.', 1)
                # Limit extension to 10 chars
                ext = ext[:10]
                safe = f"{name[:200-len(ext)-1]}.{ext}"
            else:
                safe = safe[:200]

        return safe or "unnamed"

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

    def __init__(self, worker_service, intake_manager: IntakeManager | None = None):
        """
        Args:
            worker_service: Frame's WorkerService instance
            intake_manager: IntakeManager for path resolution (optional for backwards compat)
        """
        self.worker_service = worker_service
        self.intake_manager = intake_manager
        self._active_jobs: dict[str, str] = {}  # job_id -> worker_pool

    async def dispatch(self, job: IngestJob) -> bool:
        """
        Dispatch a job to its first worker pool.

        Returns:
            True if dispatched successfully
        """
        if not job.worker_route:
            # Empty route means no processing needed (e.g., blank page detected)
            # Mark as completed immediately - no workers to dispatch to
            logger.info(f"Job {job.id} has empty route - completing without processing")
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = {
                "skipped": True,
                "reason": "blank_page" if (job.quality_score and job.quality_score.is_blank) else "empty_route",
            }
            return True

        # Get first worker pool (may include operation suffix like "cpu-image:downscale")
        pool_spec = job.worker_route[0]
        job.current_worker = pool_spec
        job.status = JobStatus.QUEUED

        # Parse pool:operation format (e.g., "cpu-image:downscale" -> pool="cpu-image", operation="downscale")
        if ":" in pool_spec:
            pool, operation = pool_spec.split(":", 1)
        else:
            pool = pool_spec
            operation = None

        try:
            # Build payload with portable relative path
            # Workers use DATA_SILO_PATH env var to resolve the full path
            if self.intake_manager:
                file_path = self.intake_manager.get_relative_path(job.file_info.path)
            else:
                # Fallback to absolute path (less portable but backwards compatible)
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

            # Add operation if specified in pool name
            if operation:
                payload["operation"] = operation

            # Enqueue to worker service
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
            logger.error(f"Failed to dispatch job {job.id}: {e}")
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

        # Parse pool:operation format
        if ":" in pool_spec:
            pool, operation = pool_spec.split(":", 1)
        else:
            pool = pool_spec
            operation = None

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
