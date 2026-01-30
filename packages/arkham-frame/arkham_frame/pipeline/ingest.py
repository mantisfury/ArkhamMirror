"""
Ingest stage - Document ingestion dispatcher.

This stage dispatches ingestion jobs to the appropriate worker pools.
Workers are registered by the arkham-shard-ingest package.
"""

from typing import Dict, Any
from datetime import datetime
import logging
import uuid
import time

from .base import PipelineStage, StageResult, StageStatus

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class IngestStage(PipelineStage):
    """
    Dispatches ingestion jobs to worker pools.

    Routes to:
        - io-file: File reading and storage
        - cpu-extract: Content extraction (PDF, DOCX, etc.)
        - cpu-archive: Archive extraction (ZIP, TAR, etc.)
        - cpu-image: Image preprocessing
    """

    def __init__(self, frame=None):
        super().__init__("ingest", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have a file to ingest."""
        return "file_path" in context or "file_bytes" in context

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Dispatch ingestion to worker pools.

        Expected context:
            - file_path: Path to the file
            - file_bytes: Raw file bytes (alternative to file_path)
            - filename: Original filename
            - project_id: Optional project ID
            - file_type: Detected file type (optional)
        """
        started_at = datetime.utcnow()
        document_id = context.get("document_id") or str(uuid.uuid4())
        
        with log_operation("pipeline.stage.ingest", document_id=document_id) as event:
            if event:
                event.context("component", "pipeline_stage")
                event.context("stage", "ingest")
                event.input(
                    document_id=document_id,
                    filename=context.get("filename", "unknown"),
                    file_type=context.get("file_type"),
                    has_file_path="file_path" in context,
                    has_file_bytes="file_bytes" in context,
                    project_id=context.get("project_id"),
                )
                if context.get("project_id"):
                    event.context("project_id", context.get("project_id"))

            try:
                file_path = context.get("file_path")
                filename = context.get("filename", "unknown")
                file_type = context.get("file_type")

                logger.info(f"Dispatching ingest for: {filename}")

                # Get worker service
                workers = self.frame.get_service("workers") if self.frame else None
                if not workers:
                    logger.warning("Worker service not available, skipping ingest dispatch")
                    if event:
                        event.error("WorkerServiceUnavailable", "Worker service not available")
                    return StageResult(
                        stage_name=self.name,
                        status=StageStatus.SKIPPED,
                        output={"reason": "Worker service not available"},
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )

                # Determine appropriate pool based on file type
                pool = self._select_pool(file_type, filename)

                # Check if pool has registered workers
                if not workers.get_worker_class(pool):
                    # Fallback to io-file for basic file handling
                    if workers.get_worker_class("io-file"):
                        pool = "io-file"
                    else:
                        logger.warning(f"No workers registered for pool {pool}")
                        if event:
                            event.error("NoWorkersAvailable", f"No workers for pool {pool}")
                        return StageResult(
                            stage_name=self.name,
                            status=StageStatus.SKIPPED,
                            output={"reason": f"No workers for pool {pool}"},
                            started_at=started_at,
                            completed_at=datetime.utcnow(),
                        )

                # Dispatch ingest job
                payload = {
                    "document_id": document_id,
                    "file_path": file_path,
                    "filename": filename,
                    "file_type": file_type,
                    "project_id": context.get("project_id"),
                    "job_type": "ingest_file",
                }

                start_time = time.time()
                try:
                    result = await workers.enqueue_and_wait(
                        pool=pool,
                        payload=payload,
                        timeout=120.0,  # 2 minutes for file processing
                    )
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Extract page paths for OCR stage
                    page_paths = result.get("page_paths", [])
                    page_count = result.get("page_count", len(page_paths))

                    output = {
                        "document_id": document_id,
                        "filename": filename,
                        "file_type": result.get("file_type", file_type),
                        "pool_used": pool,
                        "page_count": page_count,
                        "page_paths": page_paths,
                        "has_text": result.get("has_text", False),
                        "status": "ingested",
                    }

                    if event:
                        event.dependency(f"worker_pool_{pool}", duration_ms=duration_ms)
                        event.output(
                            page_count=page_count,
                            has_text=output.get("has_text", False),
                            pool_used=pool,
                        )

                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"Ingest dispatch failed: {e}")
                    if event:
                        event.dependency(f"worker_pool_{pool}", duration_ms=duration_ms, error=str(e))
                        emit_wide_error(event, "IngestDispatchFailed", str(e), exc=e)
                    output = {
                        "document_id": document_id,
                        "filename": filename,
                        "page_count": 0,
                        "error": str(e),
                        "status": "ingest_failed",
                    }

                # Emit event
                events = self.frame.get_service("events") if self.frame else None
                if events:
                    await events.publish(
                        "ingest.document.completed",
                        {
                            "document_id": document_id,
                            "filename": filename,
                            "page_count": output.get("page_count", 0),
                        },
                        source="pipeline-ingest",
                    )

                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.COMPLETED,
                    output=output,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            except Exception as e:
                logger.error(f"Ingest dispatch failed: {e}")
                if event:
                    emit_wide_error(event, "IngestStageFailed", str(e), exc=e)
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

    def _select_pool(self, file_type: str | None, filename: str) -> str:
        """Select appropriate worker pool based on file type."""
        if not file_type:
            # Guess from filename extension
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            file_type = {
                "pdf": "document",
                "docx": "document",
                "doc": "document",
                "xlsx": "spreadsheet",
                "xls": "spreadsheet",
                "pptx": "presentation",
                "png": "image",
                "jpg": "image",
                "jpeg": "image",
                "tiff": "image",
                "tif": "image",
                "zip": "archive",
                "tar": "archive",
                "gz": "archive",
                "7z": "archive",
                "rar": "archive",
            }.get(ext, "unknown")

        # Map file type to pool
        pool_map = {
            "document": "cpu-extract",
            "spreadsheet": "cpu-extract",
            "presentation": "cpu-extract",
            "image": "cpu-image",
            "archive": "cpu-archive",
        }

        return pool_map.get(file_type, "io-file")
