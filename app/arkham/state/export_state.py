import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class EntityOption(BaseModel):
    id: int
    name: str
    type: str
    mentions: int


class ExportState(rx.State):
    """State for Export Investigation Packages."""

    # Export options
    include_entities: bool = True
    include_timeline: bool = True
    include_relationships: bool = True

    # Entity selection
    available_entities: List[EntityOption] = []
    selected_entity_ids: List[int] = []

    # Summary stats
    doc_count: int = 0
    entity_count: int = 0
    rel_count: int = 0

    # CSV exports
    csv_data: str = ""
    csv_type: str = ""

    # UI state
    is_loading: bool = False
    is_exporting: bool = False
    export_ready: bool = False
    export_filename: str = ""

    def load_options(self):
        """Load export options and entity list."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.export_service import get_export_service

            service = get_export_service()
            summary = service.get_findings_summary()

            self.doc_count = summary["summary"]["total_documents"]
            self.entity_count = summary["summary"]["total_entities"]
            self.rel_count = summary["summary"]["total_relationships"]

            self.available_entities = [
                EntityOption(
                    id=e["mentions"],  # Using index as temp ID
                    name=e["name"],
                    type=e["type"],
                    mentions=e["mentions"],
                )
                for e in summary["key_entities"][:30]
            ]

        except Exception as e:
            logger.error(f"Error loading options: {e}")
        finally:
            self.is_loading = False

    def toggle_entity(self, entity_id: int):
        """Toggle entity selection."""
        if entity_id in self.selected_entity_ids:
            self.selected_entity_ids = [
                e for e in self.selected_entity_ids if e != entity_id
            ]
        else:
            self.selected_entity_ids = self.selected_entity_ids + [entity_id]

    def select_all_entities(self):
        """Select all available entities."""
        self.selected_entity_ids = [e.id for e in self.available_entities]

    def clear_selection(self):
        """Clear entity selection."""
        self.selected_entity_ids = []

    def set_include_entities(self, value: bool):
        self.include_entities = value

    def set_include_timeline(self, value: bool):
        self.include_timeline = value

    def set_include_relationships(self, value: bool):
        self.include_relationships = value

    def export_csv(self, data_type: str):
        """Export data as CSV."""
        self.is_exporting = True
        yield

        try:
            from app.arkham.services.export_service import get_export_service

            service = get_export_service()
            self.csv_data = service.export_to_csv(data_type)
            self.csv_type = data_type

        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
        finally:
            self.is_exporting = False

    def create_package(self):
        """Create investigation package ZIP."""
        self.is_exporting = True
        yield

        try:
            from app.arkham.services.export_service import get_export_service
            from datetime import datetime

            service = get_export_service()

            # Create the package (returns bytes)
            package_bytes = service.create_investigation_package(
                include_entities=self.include_entities,
                include_timeline=self.include_timeline,
                include_relationships=self.include_relationships,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
            )

            # Set filename
            self.export_filename = (
                f"investigation_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
            self.export_ready = True

            # Trigger download
            return rx.download(
                data=package_bytes,
                filename=self.export_filename,
            )

        except Exception as e:
            logger.error(f"Error creating package: {e}")
        finally:
            self.is_exporting = False

    def clear_export(self):
        self.export_ready = False
        self.csv_data = ""

    def download_csv(self):
        """Download the currently generated CSV."""
        if not self.csv_data:
            return

        filename = f"{self.csv_type}_export.csv"
        return rx.download(
            data=self.csv_data,
            filename=filename,
        )
