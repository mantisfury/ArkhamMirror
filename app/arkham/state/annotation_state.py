import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class AnnotationItem(BaseModel):
    id: int
    target_type: str
    target_id: int
    note: str
    tags: List[str] = []
    priority: str = "medium"
    status: str = "open"
    created_at: str = ""


class AnnotationState(rx.State):
    """State for Annotation System."""

    # Annotations list
    annotations: List[AnnotationItem] = []
    all_tags: List[str] = []

    # Stats
    total_count: int = 0
    open_count: int = 0
    high_priority_count: int = 0

    # New annotation form
    new_note: str = ""
    new_target_type: str = "document"
    new_target_id: str = ""
    new_priority: str = "medium"
    new_tags: str = ""

    # Filters
    filter_status: str = "all"
    filter_priority: str = "all"
    filter_type: str = "all"
    search_query: str = ""

    # Edit mode
    editing_id: int = 0
    edit_note: str = ""
    edit_priority: str = ""
    edit_status: str = ""

    # UI state
    is_loading: bool = False
    show_form: bool = False

    def load_annotations(self):
        """Load annotations from database."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.annotation_service import get_annotation_service

            service = get_annotation_service()

            # Get annotations with filters (treat "all" as no filter)
            annotations = service.get_annotations(
                target_type=self.filter_type if self.filter_type != "all" else None,
                status=self.filter_status if self.filter_status != "all" else None,
                priority=self.filter_priority
                if self.filter_priority != "all"
                else None,
            )

            self.annotations = [
                AnnotationItem(
                    id=a["id"],
                    target_type=a["target_type"],
                    target_id=a["target_id"],
                    note=a["note"],
                    tags=a["tags"],
                    priority=a["priority"],
                    status=a["status"],
                    created_at=a["created_at"] or "",
                )
                for a in annotations
            ]

            # Get stats
            stats = service.get_annotation_stats()
            self.total_count = stats["total"]
            self.open_count = stats["by_status"].get("open", 0)
            self.high_priority_count = stats["by_priority"].get("high", 0)

            # Get tags
            self.all_tags = service.get_all_tags()

        except Exception as e:
            logger.error(f"Error loading annotations: {e}")
        finally:
            self.is_loading = False

    def add_annotation(self):
        """Add a new annotation."""
        if not self.new_note.strip():
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.annotation_service import get_annotation_service

            service = get_annotation_service()

            tags = [t.strip() for t in self.new_tags.split(",") if t.strip()]
            target_id = int(self.new_target_id) if self.new_target_id else 0

            service.add_annotation(
                target_type=self.new_target_type,
                target_id=target_id,
                note=self.new_note,
                tags=tags,
                priority=self.new_priority,
            )

            # Reset form
            self.new_note = ""
            self.new_target_id = ""
            self.new_tags = ""
            self.show_form = False

            # Reload
            yield from self.load_annotations()

        except Exception as e:
            logger.error(f"Error adding annotation: {e}")
        finally:
            self.is_loading = False

    def start_edit(self, annotation_id: int):
        """Start editing an annotation."""
        self.editing_id = annotation_id
        for a in self.annotations:
            if a.id == annotation_id:
                self.edit_note = a.note
                self.edit_priority = a.priority
                self.edit_status = a.status
                break

    def save_edit(self):
        """Save annotation edit."""
        if self.editing_id == 0:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.annotation_service import get_annotation_service

            service = get_annotation_service()
            service.update_annotation(
                self.editing_id,
                note=self.edit_note,
                priority=self.edit_priority,
                status=self.edit_status,
            )

            self.editing_id = 0
            yield from self.load_annotations()

        except Exception as e:
            logger.error(f"Error saving edit: {e}")
        finally:
            self.is_loading = False

    def cancel_edit(self):
        self.editing_id = 0

    def delete_annotation(self, annotation_id: int):
        """Delete an annotation."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.annotation_service import get_annotation_service

            service = get_annotation_service()
            service.delete_annotation(annotation_id)

            yield from self.load_annotations()

        except Exception as e:
            logger.error(f"Error deleting: {e}")
        finally:
            self.is_loading = False

    def set_filter_status(self, value: str):
        self.filter_status = value
        yield from self.load_annotations()

    def set_filter_priority(self, value: str):
        self.filter_priority = value
        yield from self.load_annotations()

    def set_filter_type(self, value: str):
        self.filter_type = value
        yield from self.load_annotations()

    def set_new_note(self, value: str):
        self.new_note = value

    def set_new_target_type(self, value: str):
        self.new_target_type = value

    def set_new_target_id(self, value: str):
        self.new_target_id = value

    def set_new_priority(self, value: str):
        self.new_priority = value

    def set_new_tags(self, value: str):
        self.new_tags = value

    def set_edit_note(self, value: str):
        self.edit_note = value

    def set_edit_priority(self, value: str):
        self.edit_priority = value

    def set_edit_status(self, value: str):
        self.edit_status = value

    def toggle_form(self):
        self.show_form = not self.show_form
