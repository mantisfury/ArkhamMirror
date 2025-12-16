import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class FilteredDocument(BaseModel):
    id: int
    filename: str
    file_type: str = ""
    chunk_count: int = 0
    entity_count: int = 0
    created_at: str = ""


class FilteredEntity(BaseModel):
    id: int
    name: str
    type: str = ""
    mentions: int = 0
    relationship_count: int = 0
    aliases: List[str] = []


class FilterState(rx.State):
    """State for Advanced Filtering."""

    # Filter options
    available_entity_types: List[str] = []
    available_file_types: List[str] = []

    # Selected filters - Documents
    selected_file_types: List[str] = []
    date_from: str = ""
    date_to: str = ""
    doc_search: str = ""
    has_entities_filter: str = "any"  # "any", "yes", "no"
    min_chunks: str = ""

    # Selected filters - Entities
    selected_entity_types: List[str] = []
    min_mentions: str = ""
    max_mentions: str = ""
    has_relationships_filter: str = "any"
    entity_search: str = ""

    # Results
    filtered_documents: List[FilteredDocument] = []
    filtered_entities: List[FilteredEntity] = []

    # Stats
    doc_total: int = 0
    entity_by_type: str = ""  # JSON display
    mentions_range: str = ""

    # UI state
    is_loading: bool = False
    active_tab: str = "documents"
    filter_count: int = 0

    def load_options(self):
        """Load filter options."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.filter_service import get_filter_service

            service = get_filter_service()
            options = service.get_filter_options()

            self.available_entity_types = options["entity_types"]
            self.available_file_types = options["file_types"]

            # Get stats
            doc_stats = service.get_document_stats()
            entity_stats = service.get_entity_stats()

            self.doc_total = doc_stats["total"]
            self.entity_by_type = str(entity_stats["by_type"])
            self.mentions_range = f"{entity_stats['mention_range']['min']} - {entity_stats['mention_range']['max']}"

        except Exception as e:
            logger.error(f"Error loading options: {e}")
        finally:
            self.is_loading = False

    def apply_document_filters(self):
        """Apply document filters."""
        self.is_loading = True
        self.active_tab = "documents"
        yield

        try:
            from app.arkham.services.filter_service import get_filter_service

            service = get_filter_service()

            # Parse has_entities (any = no filter)
            has_entities = None
            if self.has_entities_filter == "yes":
                has_entities = True
            elif self.has_entities_filter == "no":
                has_entities = False

            # Parse min_chunks
            min_chunks = None
            if self.min_chunks:
                try:
                    min_chunks = int(self.min_chunks)
                except ValueError:
                    pass

            results = service.filter_documents(
                file_types=self.selected_file_types
                if self.selected_file_types
                else None,
                date_from=self.date_from if self.date_from else None,
                date_to=self.date_to if self.date_to else None,
                search_text=self.doc_search if self.doc_search else None,
                has_entities=has_entities,
                min_chunks=min_chunks,
            )

            self.filtered_documents = [
                FilteredDocument(
                    id=d["id"],
                    filename=d["filename"],
                    file_type=d["file_type"] or "",
                    chunk_count=d["chunk_count"],
                    entity_count=d["entity_count"],
                    created_at=d["created_at"] or "",
                )
                for d in results
            ]

            self._update_filter_count()

        except Exception as e:
            logger.error(f"Error filtering documents: {e}")
        finally:
            self.is_loading = False

    def apply_entity_filters(self):
        """Apply entity filters."""
        self.is_loading = True
        self.active_tab = "entities"
        yield

        try:
            from app.arkham.services.filter_service import get_filter_service

            service = get_filter_service()

            # Parse has_relationships (any = no filter)
            has_relationships = None
            if self.has_relationships_filter == "yes":
                has_relationships = True
            elif self.has_relationships_filter == "no":
                has_relationships = False

            # Parse mention limits
            min_mentions = None
            max_mentions = None
            if self.min_mentions:
                try:
                    min_mentions = int(self.min_mentions)
                except ValueError:
                    pass
            if self.max_mentions:
                try:
                    max_mentions = int(self.max_mentions)
                except ValueError:
                    pass

            results = service.filter_entities(
                entity_types=self.selected_entity_types
                if self.selected_entity_types
                else None,
                min_mentions=min_mentions,
                max_mentions=max_mentions,
                has_relationships=has_relationships,
                search_text=self.entity_search if self.entity_search else None,
            )

            self.filtered_entities = [
                FilteredEntity(
                    id=e["id"],
                    name=e["name"],
                    type=e["type"] or "",
                    mentions=e["mentions"],
                    relationship_count=e["relationship_count"],
                    aliases=e["aliases"],
                )
                for e in results
            ]

            self._update_filter_count()

        except Exception as e:
            logger.error(f"Error filtering entities: {e}")
        finally:
            self.is_loading = False

    def _update_filter_count(self):
        """Update active filter count."""
        count = 0
        if self.selected_file_types:
            count += 1
        if self.date_from or self.date_to:
            count += 1
        if self.doc_search:
            count += 1
        if self.has_entities_filter and self.has_entities_filter != "any":
            count += 1
        if self.min_chunks:
            count += 1
        if self.selected_entity_types:
            count += 1
        if self.min_mentions or self.max_mentions:
            count += 1
        if self.has_relationships_filter and self.has_relationships_filter != "any":
            count += 1
        if self.entity_search:
            count += 1
        self.filter_count = count

    def clear_all_filters(self):
        """Clear all filters."""
        self.selected_file_types = []
        self.date_from = ""
        self.date_to = ""
        self.doc_search = ""
        self.has_entities_filter = "any"
        self.min_chunks = ""
        self.selected_entity_types = []
        self.min_mentions = ""
        self.max_mentions = ""
        self.has_relationships_filter = "any"
        self.entity_search = ""
        self.filtered_documents = []
        self.filtered_entities = []
        self.filter_count = 0

    def toggle_file_type(self, file_type: str):
        if file_type in self.selected_file_types:
            self.selected_file_types = [
                t for t in self.selected_file_types if t != file_type
            ]
        else:
            self.selected_file_types = self.selected_file_types + [file_type]

    def toggle_entity_type(self, entity_type: str):
        if entity_type in self.selected_entity_types:
            self.selected_entity_types = [
                t for t in self.selected_entity_types if t != entity_type
            ]
        else:
            self.selected_entity_types = self.selected_entity_types + [entity_type]

    def set_date_from(self, value: str):
        self.date_from = value

    def set_date_to(self, value: str):
        self.date_to = value

    def set_doc_search(self, value: str):
        self.doc_search = value

    def set_has_entities_filter(self, value: str):
        self.has_entities_filter = value

    def set_min_chunks(self, value: str):
        self.min_chunks = value

    def set_min_mentions(self, value: str):
        self.min_mentions = value

    def set_max_mentions(self, value: str):
        self.max_mentions = value

    def set_has_relationships_filter(self, value: str):
        self.has_relationships_filter = value

    def set_entity_search(self, value: str):
        self.entity_search = value

    def set_active_tab(self, tab: str):
        self.active_tab = tab
