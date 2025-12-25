"""File intake and job management."""

import hashlib
import logging
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


class IntakeManager:
    """
    Manages file intake, classification, and job creation.
    """

    def __init__(
        self,
        storage_path: Path,
        temp_path: Path | None = None,
    ):
        self.storage_path = Path(storage_path)
        self.temp_path = Path(temp_path) if temp_path else self.storage_path / "temp"

        # Ensure directories exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)

        # Classifiers
        self.file_classifier = FileTypeClassifier()
        self.image_classifier = ImageQualityClassifier()

        # Active jobs and batches
        self._jobs: dict[str, IngestJob] = {}
        self._batches: dict[str, IngestBatch] = {}

    async def receive_file(
        self,
        file: BinaryIO,
        filename: str,
        priority: JobPriority = JobPriority.USER,
    ) -> IngestJob:
        """
        Receive an uploaded file and create an ingest job.

        Args:
            file: File-like object with the content
            filename: Original filename
            priority: Job priority level

        Returns:
            Created IngestJob
        """
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
        )

        # Quality classification for images
        if file_info.category == FileCategory.IMAGE:
            job.quality_score = self.image_classifier.classify(temp_file)
            # Update route based on quality
            job.worker_route = self.image_classifier.get_ocr_route(
                job.quality_score,
                ocr_mode="auto",  # TODO: Get from config
            )

        # Move to permanent storage
        permanent_path = self._get_storage_path(job_id, file_info)
        permanent_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(temp_file, permanent_path)
        job.file_info.path = permanent_path

        # Track job
        self._jobs[job_id] = job

        logger.info(
            f"Received file: {filename} -> job {job_id} "
            f"(category={file_info.category.value}, route={route})"
        )

        return job

    async def receive_batch(
        self,
        files: list[tuple[BinaryIO, str]],
        priority: JobPriority = JobPriority.BATCH,
    ) -> IngestBatch:
        """
        Receive multiple files as a batch.

        Args:
            files: List of (file, filename) tuples
            priority: Priority for all jobs in batch

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
                job = await self.receive_file(file, filename, priority)
                batch.jobs.append(job)
            except Exception as e:
                logger.error(f"Failed to receive {filename}: {e}")
                batch.failed += 1

        self._batches[batch_id] = batch
        return batch

    async def receive_path(
        self,
        path: Path,
        priority: JobPriority = JobPriority.BATCH,
        recursive: bool = True,
    ) -> IngestBatch:
        """
        Ingest files from a local path.

        Args:
            path: File or directory path
            priority: Job priority
            recursive: If directory, recurse into subdirectories

        Returns:
            Created IngestBatch
        """
        path = Path(path)

        if path.is_file():
            # Single file
            with open(path, "rb") as f:
                job = await self.receive_file(f, path.name, priority)
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

            batch = await self.receive_batch(files, priority)

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

    def update_job_status(
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

        # Update batch if applicable
        for batch in self._batches.values():
            if job in batch.jobs:
                if status == JobStatus.COMPLETED:
                    batch.completed += 1
                elif status in (JobStatus.FAILED, JobStatus.DEAD):
                    batch.failed += 1
                if batch.is_complete:
                    batch.completed_at = datetime.utcnow()

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
        # Remove path separators and null bytes
        safe = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
        # Limit length
        if len(safe) > 200:
            name, ext = safe.rsplit(".", 1) if "." in safe else (safe, "")
            safe = name[:200-len(ext)-1] + "." + ext if ext else name[:200]
        return safe or "unnamed"


class JobDispatcher:
    """
    Dispatches jobs to worker pools.
    """

    def __init__(self, worker_service):
        """
        Args:
            worker_service: Frame's WorkerService instance
        """
        self.worker_service = worker_service
        self._active_jobs: dict[str, str] = {}  # job_id -> worker_pool

    async def dispatch(self, job: IngestJob) -> bool:
        """
        Dispatch a job to its first worker pool.

        Returns:
            True if dispatched successfully
        """
        if not job.worker_route:
            logger.error(f"Job {job.id} has no worker route")
            return False

        # Get first worker pool
        pool = job.worker_route[0]
        job.current_worker = pool
        job.status = JobStatus.QUEUED

        try:
            # Enqueue to worker service
            await self.worker_service.enqueue(
                pool=pool,
                job_id=job.id,
                payload={
                    "file_path": str(job.file_info.path),
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
                },
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

        # Dispatch to next worker
        next_pool = job.worker_route[next_idx]
        job.current_worker = next_pool

        await self.worker_service.enqueue(
            pool=next_pool,
            job_id=job.id,
            payload={
                **result,  # Pass along accumulated results
                "route": job.worker_route,
                "route_index": next_idx,
            },
            priority=job.priority.value,
        )

        self._active_jobs[job.id] = next_pool
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
