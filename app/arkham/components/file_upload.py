import reflex as rx
import sys
import logging
from typing import List
from pathlib import Path
from .design_tokens import SPACING, FONT_SIZE

# Initialize logger
logger = logging.getLogger(__name__)

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import REDIS_URL, TEMP_DIR

logger.info(f"Using TEMP_DIR: {TEMP_DIR}")


class UploadState(rx.State):
    """State for file uploads with progress tracking."""

    is_uploading: bool = False
    upload_progress: int = 0
    uploaded_files: List[str] = []
    ocr_mode: str = "paddle"  # Default OCR mode: "paddle" (fast) or "qwen" (smart)

    # Progress tracking for active uploads
    active_uploads: List[dict] = []  # List of documents currently being processed
    show_progress_panel: bool = True  # Show/hide progress panel

    # Batch upload throttling settings
    batch_size: int = 10  # Files per batch before delay
    batch_delay_ms: int = 1000  # Delay between batches in milliseconds
    current_batch: int = 0
    total_batches: int = 0

    def set_ocr_mode(self, mode: str):
        """Set the OCR mode for ingestion."""
        self.ocr_mode = mode

    def toggle_progress_panel(self):
        """Toggle progress panel visibility."""
        self.show_progress_panel = not self.show_progress_panel

    def refresh_active_uploads(self):
        """Refresh progress for all active uploads."""
        try:
            from ..services.upload_progress_service import get_progress_service

            service = get_progress_service()
            self.active_uploads = service.get_active_uploads(limit=20)
        except Exception as e:
            logger.error(f"Failed to refresh active uploads: {e}")
            import traceback

            traceback.print_exc()

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle file upload and enqueue ingestion jobs to RQ (non-blocking)."""
        logger.info(
            f"=== UPLOAD STARTED === Files: {len(files)}, OCR Mode: {self.ocr_mode}"
        )

        self.is_uploading = True
        self.upload_progress = 0

        # Determine upload directory - using DataSilo/temp
        upload_dir = TEMP_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory: {upload_dir}")

        # Save files to temp directory
        logger.info("Saving files to temp directory...")
        saved_files = []
        for file in files:
            upload_data = await file.read()
            outfile = upload_dir / file.filename

            # Save the file
            with open(outfile, "wb") as f:
                f.write(upload_data)

            file_size = len(upload_data)
            logger.info(
                f"Saved file: {file.filename} ({file_size:,} bytes) -> {outfile}"
            )
            saved_files.append((file.filename, str(outfile)))

        self.is_uploading = False
        self.upload_progress = 100
        logger.info(f"All files saved. Enqueuing {len(saved_files)} jobs to RQ...")

        # Enqueue ingestion jobs to RQ (async, non-blocking)
        enqueue_errors = []
        jobs_enqueued = 0
        redis_failed = False

        try:
            # Import Redis and RQ
            import asyncio
            from redis import Redis
            from rq import Queue
            from dotenv import load_dotenv

            # Import the worker function directly
            from app.arkham.services.workers.ingest_worker import process_file

            # Environment already loaded via central config

            # Connect to Redis
            redis_conn = Redis.from_url(REDIS_URL)
            q = Queue(connection=redis_conn)

            # Calculate batches for throttling
            total_files = len(saved_files)
            self.total_batches = (total_files + self.batch_size - 1) // self.batch_size
            self.current_batch = 0

            logger.info(
                f"Processing {total_files} files in {self.total_batches} batches of {self.batch_size}"
            )

            # Enqueue files in batches with delays
            for i in range(0, total_files, self.batch_size):
                batch = saved_files[i : i + self.batch_size]
                self.current_batch += 1

                logger.info(
                    f"Enqueuing batch {self.current_batch}/{self.total_batches} ({len(batch)} files)"
                )

                for filename, file_path in batch:
                    try:
                        job = q.enqueue(
                            process_file,
                            file_path=file_path,
                            project_id=None,
                            ocr_mode=self.ocr_mode,
                            job_timeout="10m",
                        )
                        logger.info(f"Enqueued job {job.id} for {filename}")
                        jobs_enqueued += 1
                    except Exception as e:
                        error_msg = f"Error enqueuing {filename}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        enqueue_errors.append(error_msg)

                # Delay between batches (except after last batch)
                if self.current_batch < self.total_batches:
                    delay_seconds = self.batch_delay_ms / 1000
                    logger.info(f"Waiting {delay_seconds}s before next batch...")
                    await asyncio.sleep(delay_seconds)

        except Exception as e:
            error_msg = f"Failed to connect to Redis/RQ: {str(e)}"
            logger.error(error_msg, exc_info=True)
            redis_failed = True
            msg = f"Upload failed: {error_msg}"

        # Handle early Redis failure - no state communication needed
        if redis_failed:
            yield rx.window_alert(msg)
            return

        logger.info(
            f"=== UPLOAD COMPLETE === Jobs enqueued: {jobs_enqueued}, Errors: {len(enqueue_errors)}"
        )

        # Prepare success/error message
        if enqueue_errors:
            msg = f"Uploaded {len(files)} files. {jobs_enqueued} jobs enqueued, {len(enqueue_errors)} errors. Check logs."
            logger.warning(msg)
        else:
            msg = f"Uploaded {len(files)} files. {jobs_enqueued} jobs enqueued with {self.ocr_mode.upper()} OCR. Workers will process them."
            logger.info(msg)

        # Note: Ingestion status will auto-refresh via background task
        # No need to manually trigger refresh here

        # Refresh active uploads to show progress (Phase 2.1)
        self.refresh_active_uploads()

        # Show alert to user (must yield instead of return in async generator)
        yield rx.window_alert(msg)


def upload_component() -> rx.Component:
    """File upload component - OCR mode is now set via Ingestion Mode panel above."""
    return rx.vstack(
        # Note: OCR mode is controlled by the Ingestion Mode selector in the status panel
        # This keeps the UI simpler and avoids duplicate controls
        # File Upload Area
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select Files",
                    color="white",
                    bg="blue.9",
                    border="1px solid",
                    border_color="blue.9",
                ),
                rx.text(
                    "Drag and drop files here or click to select",
                    font_size=FONT_SIZE["sm"],
                    color="gray.11",
                ),
                spacing=SPACING["sm"],
            ),
            id="upload1",
            border="1px dotted",
            border_color="blue.9",
            padding=SPACING["xl"],
        ),
        # Selected Files Display
        rx.hstack(
            rx.foreach(
                rx.selected_files("upload1"),
                lambda file: rx.text(file, font_size=FONT_SIZE["sm"], color="gray.11"),
            ),
            width="100%",
            wrap="wrap",
            spacing=SPACING["sm"],
        ),
        # Upload Button
        rx.button(
            "Upload",
            on_click=UploadState.handle_upload(rx.upload_files("upload1")),
            color="white",
            bg="blue.9",
            size="3",
        ),
        # Progress Indicator
        rx.cond(
            UploadState.is_uploading,
            rx.progress(value=UploadState.upload_progress),
        ),
        width="100%",
        spacing=SPACING["md"],
    )
