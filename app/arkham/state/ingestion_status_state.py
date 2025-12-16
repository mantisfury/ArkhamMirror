import reflex as rx
import sys
import asyncio
import logging
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL, REDIS_URL


class IngestionStatusState(rx.State):
    """State for tracking ingestion progress and document management."""

    # Queue stats
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0

    # Recent documents
    recent_documents: List[Dict[str, str]] = []

    # Refresh control
    refresh_interval: int = 10  # seconds when active
    is_active: bool = False  # Are there jobs in progress?
    auto_refresh_enabled: bool = True  # Control auto-refresh (enabled by default)
    bg_task_running: bool = False  # Track if background task is running

    # Phase 5.1: Ingestion Mode Controls
    ingestion_mode: str = "enhanced"  # "economy", "enhanced", "vision"
    auto_fallback_enabled: bool = True  # Auto-retry with Vision OCR on low confidence
    fallback_threshold: int = 60  # OCR confidence threshold (40-80%)

    # Modal control
    show_completed_modal: bool = False
    show_failed_modal: bool = False
    show_processing_modal: bool = False
    show_queued_modal: bool = False
    show_document_detail_modal: bool = False  # Phase 2.3: Document detail viewer

    # Document lists for modals
    completed_documents: List[Dict[str, str]] = []
    failed_documents: List[Dict[str, str]] = []
    processing_documents: List[Dict[str, str]] = []
    queued_documents: List[Dict[str, str]] = []

    # Phase 2.3: Document detail state
    selected_document: Dict[str, str] = {}
    document_chunks_preview: List[Dict[str, str]] = []

    # Action feedback
    action_message: str = ""
    action_type: str = "info"  # info, success, error
    show_action_toast: bool = False

    # Loading states
    is_loading_action: bool = False

    # Confirmation dialog state
    show_confirm_dialog: bool = False
    confirm_title: str = ""
    confirm_message: str = ""
    confirm_action: str = ""  # "delete_doc", "clear_completed", "wipe_db"
    confirm_target_id: str = ""  # Store doc_id for delete operations

    def refresh_status(self):
        """
        Refresh ingestion status from database and queue.

        Uses hybrid tracking (Phase 1.4):
        - Queued: DB docs with status="uploaded"/"pending" + RQ queue length
        - Processing: RQ started jobs
        - Complete: DB docs with status="complete"
        - Failed: DB docs with status="failed" + RQ failed jobs
        """
        try:
            # Import here to avoid circular dependencies
            from rq import Queue
            from redis import Redis
            from sqlalchemy import create_engine, func
            from sqlalchemy.orm import sessionmaker
            from app.arkham.services.db.models import Document
            from dotenv import load_dotenv

            load_dotenv()

            # Connect to PostgreSQL for document status counts
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                # Query document counts by status (Phase 1.4 - Hybrid Counters)
                db_uploaded_count = (
                    session.query(func.count(Document.id))
                    .filter(Document.status == "uploaded")
                    .scalar()
                    or 0
                )

                db_pending_count = (
                    session.query(func.count(Document.id))
                    .filter(Document.status == "pending")
                    .scalar()
                    or 0
                )

                db_complete_count = (
                    session.query(func.count(Document.id))
                    .filter(Document.status == "complete")
                    .scalar()
                    or 0
                )

                db_failed_count = (
                    session.query(func.count(Document.id))
                    .filter(Document.status == "failed")
                    .scalar()
                    or 0
                )

                # Connect to Redis for RQ job stats
                redis_conn = Redis.from_url(REDIS_URL)
                q = Queue(connection=redis_conn)

                rq_queued = len(q)
                rq_processing = len(q.started_job_registry)
                rq_failed = len(q.failed_job_registry)

                # Hybrid counter calculation (Phase 1.4)
                self.queued_count = db_uploaded_count + db_pending_count + rq_queued
                self.processing_count = (
                    rq_processing  # Only RQ knows what's actively processing
                )
                self.completed_count = (
                    db_complete_count  # DB is source of truth for completion
                )
                self.failed_count = db_failed_count + rq_failed  # Combine both sources

                # Determine if there's active processing
                self.is_active = self.queued_count > 0 or self.processing_count > 0

                # Get recent documents from database with enhanced details (Phase 2.3)
                docs = (
                    session.query(Document)
                    .order_by(Document.created_at.desc())
                    .limit(10)
                    .all()
                )

                self.recent_documents = [
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "status": doc.status,
                        "num_pages": str(doc.num_pages) if doc.num_pages else "0",
                        "path": doc.path or "",  # Phase 2.3: File path
                        "source_path": doc.source_path
                        or "",  # Phase 2.3: Original path
                        "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if doc.created_at
                        else "",  # Phase 2.3: Upload time
                        "doc_type": doc.doc_type
                        or "unknown",  # Phase 2.3: Document type
                    }
                    for doc in docs
                ]

        except Exception as e:
            logger.error(f"Failed to refresh status: {e}", exc_info=True)

    @rx.event(background=True)
    async def auto_refresh_loop(self):
        """
        Background task: Auto-refresh status periodically.

        This runs concurrently without blocking the UI.
        - Updates state via: async with self: self.state_var = value
        - Runs while page is active and websocket connected
        - Automatically stops when user navigates away
        """
        try:
            while True:
                # Check if auto-refresh is enabled
                if not self.auto_refresh_enabled:
                    await asyncio.sleep(
                        30
                    )  # Check every 30s if refresh should re-enable
                    continue

                # Update state: MUST use async with self context block
                async with self:
                    self.refresh_status()

                    # Also refresh active upload progress (Phase 2.1)
                    try:
                        from ..components.file_upload import UploadState

                        upload_state = await self.get_state(UploadState)
                        if upload_state and hasattr(
                            upload_state, "refresh_active_uploads"
                        ):
                            upload_state.refresh_active_uploads()
                    except Exception as e:
                        logger.warning(f"Failed to refresh upload progress: {e}")

                    # Determine next sleep interval based on activity
                    current_is_active = self.is_active
                    refresh_delay = self.refresh_interval if current_is_active else 30

                # Sleep outside context block to avoid blocking other handlers
                await asyncio.sleep(refresh_delay)

        except asyncio.CancelledError:
            # Task was cancelled (user navigated away, websocket closed, etc.)
            logger.info("Auto-refresh background task cancelled")
            async with self:
                self.bg_task_running = False
        except Exception as e:
            logger.error(f"Auto-refresh loop failed: {e}", exc_info=True)
            async with self:
                self.bg_task_running = False

    def toggle_auto_refresh(self):
        """Toggle auto-refresh on/off without stopping the task."""
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        if self.auto_refresh_enabled:
            self.refresh_status()

    # Phase 5.1: Ingestion Mode Handlers
    def set_ingestion_mode(self, mode: str):
        """Set the ingestion mode (economy, enhanced, vision)."""
        if mode in ["economy", "enhanced", "vision"]:
            self.ingestion_mode = mode
            # Sync to Redis so workers can read it
            self._sync_mode_to_redis()
            self.show_toast(f"Ingestion mode set to: {mode.title()}", "info")

    def toggle_auto_fallback(self):
        """Toggle auto-fallback to Vision OCR."""
        self.auto_fallback_enabled = not self.auto_fallback_enabled
        self._sync_mode_to_redis()
        status = "enabled" if self.auto_fallback_enabled else "disabled"
        self.show_toast(f"Auto-fallback {status}", "info")

    def set_fallback_threshold(self, value: list):
        """Set the OCR confidence threshold for auto-fallback."""
        if value and len(value) > 0:
            self.fallback_threshold = int(value[0])
            self._sync_mode_to_redis()

    def _sync_mode_to_redis(self):
        """Sync ingestion settings to Redis for workers to read."""
        try:
            from redis import Redis
            from dotenv import load_dotenv

            load_dotenv()
            redis_url = REDIS_URL
            if redis_url:
                redis_conn = Redis.from_url(redis_url)
                redis_conn.set("arkham:ingestion_mode", self.ingestion_mode)
                redis_conn.set(
                    "arkham:auto_fallback", "1" if self.auto_fallback_enabled else "0"
                )
                redis_conn.set(
                    "arkham:fallback_threshold", str(self.fallback_threshold)
                )
        except Exception as e:
            logger.error(f"Failed to sync mode to Redis: {e}")

    def on_load(self):
        """
        Called when the Ingest page loads.
        - Performs initial status refresh
        - Yields background task to start it (if not already running)
        """
        self.refresh_status()

        # Start background task only if not already running
        if not self.bg_task_running:
            self.bg_task_running = True
            # Yield the background task to start it
            # Reflex will automatically manage its lifecycle
            return IngestionStatusState.auto_refresh_loop

    # Document Management Methods

    def open_completed_modal(self):
        """Open modal showing completed documents."""
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            docs = service.get_documents_by_status("complete", limit=100)
            self.completed_documents = docs
            self.show_completed_modal = True
        except Exception as e:
            logger.error(f"Failed to load completed documents: {e}")
            self.show_toast(f"Error loading documents: {str(e)}", "error")

    def open_failed_modal(self):
        """Open modal showing failed documents."""
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            docs = service.get_documents_by_status("failed", limit=100)
            self.failed_documents = docs
            self.show_failed_modal = True
        except Exception as e:
            logger.error(f"Failed to load failed documents: {e}")
            self.show_toast(f"Error loading documents: {str(e)}", "error")

    def open_processing_modal(self):
        """Open modal showing processing documents."""
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            docs = service.get_documents_by_status("processing", limit=100)
            self.processing_documents = docs
            self.show_processing_modal = True
        except Exception as e:
            logger.error(f"Failed to load processing documents: {e}")
            self.show_toast(f"Error loading documents: {str(e)}", "error")

    def open_queued_modal(self):
        """Open modal showing queued documents."""
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            # Get both uploaded and pending status
            docs_uploaded = service.get_documents_by_status("uploaded", limit=50)
            docs_pending = service.get_documents_by_status("pending", limit=50)
            self.queued_documents = docs_uploaded + docs_pending
            self.show_queued_modal = True
        except Exception as e:
            logger.error(f"Failed to load queued documents: {e}")
            self.show_toast(f"Error loading documents: {str(e)}", "error")

    def close_modals(self):
        """Close all modals."""
        self.show_completed_modal = False
        self.show_failed_modal = False
        self.show_processing_modal = False
        self.show_queued_modal = False
        self.show_document_detail_modal = False
        self.show_confirm_dialog = False

    # Confirmation Dialog Methods

    def show_delete_confirmation(self, doc_id: str):
        """Show confirmation dialog for document deletion."""
        self.confirm_title = "Delete Document"
        self.confirm_message = f"Are you sure you want to delete document #{doc_id}? This action cannot be undone."
        self.confirm_action = "delete_doc"
        self.confirm_target_id = doc_id
        self.show_confirm_dialog = True

    def show_clear_completed_confirmation(self):
        """Show confirmation dialog for clearing all completed documents."""
        self.confirm_title = "Clear All Completed"
        self.confirm_message = f"Are you sure you want to delete all {self.completed_count} completed documents? This action cannot be undone."
        self.confirm_action = "clear_completed"
        self.confirm_target_id = ""
        self.show_confirm_dialog = True

    def show_wipe_database_confirmation(self):
        """Show confirmation dialog for wiping the entire database."""
        self.confirm_title = "⚠️ DANGER: Wipe Database"
        self.confirm_message = "This will DELETE ALL documents, chunks, entities, and annotations. This action is IRREVERSIBLE. Are you absolutely sure?"
        self.confirm_action = "wipe_db"
        self.confirm_target_id = ""
        self.show_confirm_dialog = True

    def cancel_confirmation(self):
        """Cancel the confirmation dialog."""
        self.show_confirm_dialog = False
        self.confirm_action = ""
        self.confirm_target_id = ""

    def execute_confirmed_action(self):
        """Execute the action that was confirmed."""
        action = self.confirm_action
        target_id = self.confirm_target_id

        # Close the dialog first
        self.show_confirm_dialog = False
        self.confirm_action = ""
        self.confirm_target_id = ""

        # Execute the appropriate action
        if action == "delete_doc":
            self._do_delete_document(target_id)
        elif action == "clear_completed":
            self._do_clear_completed()
        elif action == "wipe_db":
            self._do_wipe_database()

    def delete_document(self, doc_id):
        """Show confirmation dialog before deleting a document."""
        # Convert to string for the confirmation state
        doc_id_str = str(doc_id) if not isinstance(doc_id, str) else doc_id
        self.show_delete_confirmation(doc_id_str)

    def _do_delete_document(self, doc_id):
        """Actually delete a document with full cleanup (called after confirmation)."""
        if self.is_loading_action:
            return

        self.is_loading_action = True
        try:
            # Convert to int if string
            if isinstance(doc_id, str):
                doc_id = int(doc_id)

            from ..services.document_management_service import get_document_service

            service = get_document_service()
            result = service.delete_document(doc_id)

            if result["success"]:
                self.show_toast(f"Document {doc_id} deleted successfully", "success")
                # Refresh status and close modals
                self.refresh_status()
                self.close_modals()
            else:
                errors = "; ".join(result["errors"])
                self.show_toast(f"Delete failed: {errors}", "error")

        except Exception as e:
            logger.error(f"Delete document failed: {e}")
            self.show_toast(f"Delete failed: {str(e)}", "error")
        finally:
            self.is_loading_action = False

    def requeue_document(self, doc_id):
        """Requeue a document for reprocessing."""
        if self.is_loading_action:
            return

        self.is_loading_action = True
        try:
            # Convert to int if string
            if isinstance(doc_id, str):
                doc_id = int(doc_id)

            from ..services.document_management_service import get_document_service

            service = get_document_service()
            result = service.requeue_document(doc_id)

            if result["success"]:
                self.show_toast(f"Document {doc_id} requeued successfully", "success")
                # Refresh status and close modals
                self.refresh_status()
                self.close_modals()
            else:
                errors = "; ".join(result["errors"])
                self.show_toast(f"Requeue failed: {errors}", "error")

        except Exception as e:
            logger.error(f"Requeue document failed: {e}")
            self.show_toast(f"Requeue failed: {str(e)}", "error")
        finally:
            self.is_loading_action = False

    def requeue_document_by_id(self):
        """Requeue the currently selected document."""
        if self.selected_document and "id" in self.selected_document:
            doc_id = self.selected_document["id"]
            self.requeue_document(doc_id)

    def delete_document_by_id(self):
        """Delete the currently selected document."""
        if self.selected_document and "id" in self.selected_document:
            doc_id = self.selected_document["id"]
            self.delete_document(doc_id)

    def clear_completed(self):
        """Show confirmation dialog before clearing completed documents."""
        self.show_clear_completed_confirmation()

    def _do_clear_completed(self):
        """Actually clear all completed documents (called after confirmation)."""
        if self.is_loading_action:
            return

        self.is_loading_action = True
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            result = service.clear_completed_documents()

            if result["success"]:
                self.show_toast(
                    f"Cleared {result['deleted_count']} completed documents", "success"
                )
                self.refresh_status()
                self.close_modals()
            else:
                errors = "; ".join(result["errors"])
                self.show_toast(f"Clear failed: {errors}", "error")

        except Exception as e:
            logger.error(f"Clear completed failed: {e}")
            self.show_toast(f"Clear failed: {str(e)}", "error")
        finally:
            self.is_loading_action = False

    def wipe_database(self):
        """Show confirmation dialog before wiping database."""
        self.show_wipe_database_confirmation()

    def _do_wipe_database(self):
        """DANGER: Actually wipe entire database (called after confirmation)."""
        if self.is_loading_action:
            return

        self.is_loading_action = True
        try:
            from ..services.document_management_service import get_document_service

            service = get_document_service()
            result = service.wipe_all_data()

            if result["success"]:
                self.show_toast(
                    f"Database wiped: {result['documents_deleted']} docs, {result['files_deleted']} files",
                    "success",
                )
                self.refresh_status()
                self.close_modals()
            else:
                errors = "; ".join(result["errors"])
                self.show_toast(f"Wipe failed: {errors}", "error")

        except Exception as e:
            logger.error(f"Wipe database failed: {e}")
            self.show_toast(f"Wipe failed: {str(e)}", "error")
        finally:
            self.is_loading_action = False

    def show_toast(self, message: str, toast_type: str = "info"):
        """Show toast notification."""
        self.action_message = message
        self.action_type = toast_type
        self.show_action_toast = True

    def hide_toast(self):
        """Hide toast notification."""
        self.show_action_toast = False

    # Phase 2.3: Document Detail Methods

    def open_document_detail(self, doc_id):
        """Open document detail modal with full information."""
        try:
            # Convert to int if string
            if isinstance(doc_id, str):
                doc_id = int(doc_id)

            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from app.arkham.services.db.models import Document, Chunk
            from dotenv import load_dotenv

            load_dotenv()
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                # Get document details
                doc = session.query(Document).filter(Document.id == doc_id).first()
                if not doc:
                    self.show_toast(f"Document {doc_id} not found", "error")
                    return

                # Get processing breakdown
                chunk_count = (
                    session.query(Chunk).filter(Chunk.doc_id == doc_id).count()
                )

                # Get first 3 chunks as preview
                chunks = (
                    session.query(Chunk).filter(Chunk.doc_id == doc_id).limit(3).all()
                )

                self.selected_document = {
                    "id": str(doc.id),
                    "title": doc.title,
                    "status": doc.status,
                    "num_pages": str(doc.num_pages) if doc.num_pages else "0",
                    "path": doc.path or "",
                    "source_path": doc.source_path or "",
                    "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if doc.created_at
                    else "",
                    "doc_type": doc.doc_type or "unknown",
                    "chunk_count": str(chunk_count),
                    "file_size": f"{doc.file_size_bytes / 1024 / 1024:.2f} MB"
                    if doc.file_size_bytes
                    else "Unknown",
                }

                self.document_chunks_preview = [
                    {
                        "id": str(chunk.id),
                        "text": chunk.text[:200] + "..."
                        if len(chunk.text) > 200
                        else chunk.text,
                        "chunk_index": str(chunk.chunk_index),
                    }
                    for chunk in chunks
                ]

                self.show_document_detail_modal = True

        except Exception as e:
            logger.error(f"Failed to load document detail: {e}", exc_info=True)
            self.show_toast(f"Error loading document: {str(e)}", "error")
