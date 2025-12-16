import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class UploadItem(BaseModel):
    id: int
    filename: str
    file_type: str = ""
    file_size: int = 0
    status: str = "pending"
    document_id: int = 0
    error_message: str = ""
    uploaded_at: str = ""
    completed_at: str = ""


class UploadHistoryState(rx.State):
    """State for Upload History."""

    # History list
    uploads: List[UploadItem] = []

    # Stats
    total_uploads: int = 0
    completed_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    total_size: int = 0

    # Filters
    filter_status: str = "all"

    # UI state
    is_loading: bool = False

    def load_history(self):
        """Load upload history."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.upload_history_service import (
                get_upload_history_service,
            )

            service = get_upload_history_service()

            # "all" means no filter
            status_filter = None if self.filter_status == "all" else self.filter_status
            uploads = service.get_history(status=status_filter)

            self.uploads = [
                UploadItem(
                    id=u["id"],
                    filename=u["filename"],
                    file_type=u["file_type"] or "",
                    file_size=u["file_size"] or 0,
                    status=u["status"],
                    document_id=u["document_id"] or 0,
                    error_message=u["error_message"] or "",
                    uploaded_at=u["uploaded_at"] or "",
                    completed_at=u["completed_at"] or "",
                )
                for u in uploads
            ]

            # Get stats
            stats = service.get_stats()
            self.total_uploads = stats["total"]
            self.completed_count = stats["by_status"].get("completed", 0)
            self.failed_count = stats["by_status"].get("failed", 0)
            self.pending_count = stats["by_status"].get("pending", 0)
            self.total_size = stats["total_size_bytes"]

        except Exception as e:
            logger.error(f"Error loading history: {e}")
        finally:
            self.is_loading = False

    def delete_record(self, record_id: int):
        """Delete an upload record."""
        try:
            from app.arkham.services.upload_history_service import (
                get_upload_history_service,
            )

            service = get_upload_history_service()
            service.delete_record(record_id)

            yield from self.load_history()

        except Exception as e:
            logger.error(f"Error deleting: {e}")

    def clear_old(self):
        """Clear records older than 30 days."""
        try:
            from app.arkham.services.upload_history_service import (
                get_upload_history_service,
            )

            service = get_upload_history_service()
            service.clear_old_records(30)

            yield from self.load_history()

        except Exception as e:
            logger.error(f"Error clearing: {e}")

    def set_filter_status(self, value: str):
        self.filter_status = value
        yield from self.load_history()

    @rx.var
    def formatted_size(self) -> str:
        """Format total size for display."""
        size = self.total_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
