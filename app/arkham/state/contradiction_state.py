import reflex as rx
import logging
from typing import List, Optional
from pydantic import BaseModel
from app.arkham.models.contradiction_models import Contradiction

logger = logging.getLogger(__name__)

# NOTE: Service import moved inside methods to prevent slow startup (lazy loading)


# Selection models
class SelectableEntity(BaseModel):
    id: int
    name: str
    label: str
    mentions: int


class SelectableDocument(BaseModel):
    id: int
    filename: str
    doc_type: str


class ContradictionState(rx.State):
    contradictions: List[Contradiction] = []
    is_loading: bool = False
    selected_contradiction: Optional[Contradiction] = None

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    # Filter selection state
    available_entities: List[SelectableEntity] = []
    available_documents: List[SelectableDocument] = []
    selected_entity_ids: List[int] = []
    selected_doc_ids: List[int] = []
    show_filters: bool = False
    entity_search: str = ""
    doc_search: str = ""

    # Background job state - use LocalStorage for job_id to survive refresh
    job_id: str = rx.LocalStorage(name="contradiction_job_id")
    job_status: str = ""  # queued, running, paused, cooldown, complete, failed, stopped
    job_progress: int = 0
    job_total: int = 0
    job_current_entity: str = ""
    job_found: int = 0
    job_error: str = ""

    # Phase 2: Caching state
    has_new_docs: bool = False  # True if new docs since last analysis
    force_refresh: bool = False  # Checkbox to bypass cache

    # Phase 4: Browsing state
    view_mode: str = "list"  # "list" or "cards"
    search_query: str = ""  # Text search
    severity_filter: str = ""  # "", "High", "Medium", "Low"
    status_filter: str = ""  # "", "Open", "Resolved", "False Positive"
    category_filter: str = ""  # "", "timeline", "financial", etc.
    sort_by: str = "newest"  # Legacy - kept for compatibility
    sort_column: str = "date"  # "severity", "entity", "status", "confidence", "date"
    sort_ascending: bool = False  # True = ascending, False = descending

    # Phase 5: Pagination
    current_page: int = 0
    page_size: int = 25

    # Batch Management
    batches: List[dict] = []
    total_batches: int = 0
    completed_batches: int = 0
    auto_continue: bool = False
    total_entities: int = 0
    all_batches_complete: bool = False

    # Phase 4: Semantic Search
    semantic_query: str = ""
    semantic_results: List[Contradiction] = []
    is_semantic_search: bool = False
    is_searching: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if contradictions have been loaded."""
        return len(self.contradictions) > 0

    @rx.var
    def filtered_entities(self) -> List[SelectableEntity]:
        """Filter available entities by search term."""
        if not self.entity_search:
            return self.available_entities
        search = self.entity_search.lower()
        return [e for e in self.available_entities if search in e.name.lower()]

    @rx.var
    def filtered_documents(self) -> List[SelectableDocument]:
        """Filter available documents by search term."""
        if not self.doc_search:
            return self.available_documents
        search = self.doc_search.lower()
        return [d for d in self.available_documents if search in d.filename.lower()]

    @rx.var
    def filter_description(self) -> str:
        """Human-readable description of current filters."""
        parts = []
        if self.selected_entity_ids:
            count = len(self.selected_entity_ids)
            parts.append(f"{count} entit{'ies' if count != 1 else 'y'}")
        if self.selected_doc_ids:
            count = len(self.selected_doc_ids)
            parts.append(f"{count} document{'s' if count != 1 else ''}")
        if parts:
            return "Focusing on: " + " in ".join(parts)
        return "Analyzing all entities in full corpus"

    # Phase 4: Filtered and sorted contradictions (all)
    @rx.var
    def filtered_contradictions(self) -> List[Contradiction]:
        """Apply filters, search, and sorting (no pagination)."""
        result = self.contradictions

        # Text search
        if self.search_query:
            q = self.search_query.lower()
            result = [
                c
                for c in result
                if q in c.description.lower() or q in c.entity_name.lower()
            ]

        # Severity filter
        if self.severity_filter:
            result = [c for c in result if c.severity == self.severity_filter]

        # Status filter
        if self.status_filter:
            result = [c for c in result if c.status == self.status_filter]

        # Category filter
        if self.category_filter:
            result = [c for c in result if c.category == self.category_filter]

        # Sorting by column with direction
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        status_order = {"Open": 0, "Resolved": 1, "False Positive": 2}

        if self.sort_column == "severity":
            result = sorted(
                result,
                key=lambda c: severity_order.get(c.severity, 9),
                reverse=not self.sort_ascending,  # High first by default
            )
        elif self.sort_column == "entity":
            result = sorted(
                result,
                key=lambda c: c.entity_name.lower(),
                reverse=not self.sort_ascending,
            )
        elif self.sort_column == "status":
            result = sorted(
                result,
                key=lambda c: status_order.get(c.status, 9),
                reverse=not self.sort_ascending,
            )
        elif self.sort_column == "confidence":
            result = sorted(
                result,
                key=lambda c: c.confidence,
                reverse=not self.sort_ascending,  # High first by default
            )
        else:  # date (default)
            result = sorted(
                result,
                key=lambda c: c.created_at or "",
                reverse=not self.sort_ascending,  # Newest first by default
            )

        return result

    # Phase 5: Paginated results
    @rx.var
    def displayed_contradictions(self) -> List[Contradiction]:
        """Return current page of filtered or semantic results."""
        # If in semantic search mode, show those results
        if self.is_semantic_search and self.semantic_results:
            start = self.current_page * self.page_size
            end = start + self.page_size
            return self.semantic_results[start:end]
        # Otherwise show filtered results
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.filtered_contradictions[start:end]

    @rx.var
    def result_count(self) -> int:
        """Number of contradictions after filtering (total)."""
        if self.is_semantic_search and self.semantic_results:
            return len(self.semantic_results)
        return len(self.filtered_contradictions)

    @rx.var
    def page_count(self) -> int:
        """Total number of pages."""
        count = len(self.filtered_contradictions)
        return max(1, (count + self.page_size - 1) // self.page_size)

    @rx.var
    def can_prev(self) -> bool:
        """Can navigate to previous page."""
        return self.current_page > 0

    @rx.var
    def can_next(self) -> bool:
        """Can navigate to next page."""
        return self.current_page < self.page_count - 1

    @rx.var
    def page_info(self) -> str:
        """Page X of Y display."""
        return f"Page {self.current_page + 1} of {self.page_count}"

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1

    def next_page(self):
        """Go to next page."""
        if self.current_page < self.page_count - 1:
            self.current_page += 1

    def set_page_size(self, value: str):
        """Set page size."""
        self.page_size = int(value)
        self.current_page = 0  # Reset to first page

    def set_search_query(self, value: str):
        """Set search query."""
        self.search_query = value
        self.current_page = 0  # Reset pagination on search

    def set_severity_filter(self, value: str):
        """Set severity filter."""
        self.severity_filter = "" if value == "all" else value
        self.current_page = 0

    def set_status_filter(self, value: str):
        """Set status filter."""
        self.status_filter = "" if value == "all" else value
        self.current_page = 0

    def set_category_filter(self, value: str):
        """Set category filter."""
        self.category_filter = "" if value == "all" else value
        self.current_page = 0

    def set_sort_by(self, value: str):
        """Set sort order."""
        self.sort_by = value

    def toggle_sort(self, column: str):
        """Toggle sort by column - click again to reverse direction."""
        if self.sort_column == column:
            # Same column - toggle direction
            self.sort_ascending = not self.sort_ascending
        else:
            # New column - default to descending (newest/highest first)
            self.sort_column = column
            self.sort_ascending = False
        self.current_page = 0

    def toggle_view_mode(self):
        """Toggle between list and card views."""
        self.view_mode = "cards" if self.view_mode == "list" else "list"

    def clear_all_filters(self):
        """Clear all browsing filters."""
        self.search_query = ""
        self.severity_filter = ""
        self.status_filter = ""
        self.category_filter = ""
        self.current_page = 0

    # Phase 5: CSV Export
    def export_csv(self):
        """Export filtered contradictions to CSV and download."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "ID",
                "Entity",
                "Description",
                "Severity",
                "Status",
                "Strength",
                "Category",
                "Created At",
            ]
        )

        # Data
        for c in self.filtered_contradictions:
            writer.writerow(
                [
                    c.id,
                    c.entity_name,
                    c.description,
                    c.severity,
                    c.status,
                    f"{c.confidence:.2f}",
                    c.category or "",
                    c.created_at or "",
                ]
            )

        csv_content = output.getvalue()
        # Trigger download (Reflex handles this via rx.download)
        return rx.download(data=csv_content, filename="contradictions_export.csv")

    def load_filter_options(self):
        """Load entities and documents for filter selection."""
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            entities = service.get_selectable_entities()
            documents = service.get_selectable_documents()

            self.available_entities = [SelectableEntity(**e) for e in entities]
            self.available_documents = [SelectableDocument(**d) for d in documents]
        except Exception as e:
            logger.error(f"Error loading filter options: {e}")

    def toggle_filters(self):
        """Toggle filter panel visibility."""
        self.show_filters = not self.show_filters
        if self.show_filters and not self.available_entities:
            self.load_filter_options()

    def toggle_entity(self, entity_id: int):
        """Toggle an entity in the selection."""
        if entity_id in self.selected_entity_ids:
            self.selected_entity_ids = [
                e for e in self.selected_entity_ids if e != entity_id
            ]
        else:
            self.selected_entity_ids = self.selected_entity_ids + [entity_id]

    def toggle_document(self, doc_id: int):
        """Toggle a document in the selection."""
        if doc_id in self.selected_doc_ids:
            self.selected_doc_ids = [d for d in self.selected_doc_ids if d != doc_id]
        else:
            self.selected_doc_ids = self.selected_doc_ids + [doc_id]

    def clear_filters(self):
        """Clear all filters."""
        self.selected_entity_ids = []
        self.selected_doc_ids = []
        self.entity_search = ""
        self.doc_search = ""

    def set_entity_search(self, value: str):
        """Set entity search filter."""
        self.entity_search = value

    def set_doc_search(self, value: str):
        """Set document search filter."""
        self.doc_search = value

    # ========== Batch Management ==========

    def load_batch_overview(self):
        """Load batch status from service."""
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            overview = service.get_batch_overview(
                entity_ids=self.selected_entity_ids or None,
                doc_ids=self.selected_doc_ids or None,
            )
            self.batches = overview["batches"]
            self.total_batches = overview["total_batches"]
            self.completed_batches = overview["completed_batches"]
            self.total_entities = overview["total_entities"]
            self.all_batches_complete = overview["all_complete"]
            logger.info(
                f"Loaded batch overview: {self.total_batches} batches, {self.total_entities} entities"
            )
        except Exception as e:
            logger.error(f"Error loading batch overview: {e}", exc_info=True)

    def start_next_batch(self):
        """Start the next pending batch."""
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            job_id = service.start_next_batch(
                entity_ids=self.selected_entity_ids or None,
                doc_ids=self.selected_doc_ids or None,
                force_refresh=self.force_refresh,
                auto_continue=self.auto_continue,
            )
            if job_id:
                self.job_id = job_id
                self.job_status = "queued"
            else:
                self.all_batches_complete = True
            # Refresh batch overview
            self.load_batch_overview()
        except Exception as e:
            logger.error(f"Error starting next batch: {e}")

    def toggle_auto_continue(self, value: bool):
        """Toggle auto-continue mode."""
        self.auto_continue = value

    def reset_batches(self):
        """Reset all batches to pending state."""
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            service.reset_batches()
            self.load_batch_overview()
        except Exception as e:
            logger.error(f"Error resetting batches: {e}")

    def load_contradictions(self):
        # Skip if already loaded (session cache)
        if self._has_loaded and self.contradictions:
            return

        self.is_loading = True
        yield
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            data = service.get_contradictions()
            # Convert dicts to Pydantic models
            self.contradictions = [Contradiction(**item) for item in data]
            self._has_loaded = True  # Mark as loaded for session cache
        except Exception as e:
            logger.error(f"Error loading contradictions: {e}")
        finally:
            self.is_loading = False

    def refresh_contradictions(self):
        """Force reload contradictions, clearing cache."""
        self._has_loaded = False
        return ContradictionState.load_contradictions

    def set_semantic_query(self, value: str):
        """Set the semantic search query."""
        self.semantic_query = value

    def semantic_search(self):
        """Run semantic search on contradictions using Qdrant embeddings."""
        if not self.semantic_query.strip():
            self.is_semantic_search = False
            self.semantic_results = []
            return

        self.is_searching = True
        yield

        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            results = service.semantic_search_contradictions(
                query=self.semantic_query,
                limit=50,
            )
            self.semantic_results = [Contradiction(**r) for r in results]
            self.is_semantic_search = True
            logger.info(
                f"Semantic search found {len(results)} results for '{self.semantic_query}'"
            )
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            self.semantic_results = []
        finally:
            self.is_searching = False

    def clear_semantic_search(self):
        """Clear semantic search and return to normal view."""
        self.semantic_query = ""
        self.semantic_results = []
        self.is_semantic_search = False

    @rx.event(background=True)
    async def run_detection(self):
        async with self:
            self.is_loading = True
            # Capture filter values before async work
            entity_ids = self.selected_entity_ids if self.selected_entity_ids else None
            doc_ids = self.selected_doc_ids if self.selected_doc_ids else None

        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            # Pass filters to detection
            service.detect_contradictions(entity_ids=entity_ids, doc_ids=doc_ids)

            # Load results after detection completes
            data = service.get_contradictions()

            # Update all state in single block to prevent UI flicker
            async with self:
                self.contradictions = [Contradiction(**item) for item in data]
                self._has_loaded = True
                self.is_loading = False  # Set loading to False AFTER data is set

        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
            async with self:
                self.is_loading = False

    def select_contradiction(self, contradiction: Contradiction):
        self.selected_contradiction = contradiction

    def clear_selection(self):
        self.selected_contradiction = None

    def on_open_change(self, is_open: bool):
        if not is_open:
            self.selected_contradiction = None

    def mark_resolved(self):
        if self.selected_contradiction:
            self.resolve_contradiction(self.selected_contradiction.id, "Resolved")

    def mark_false_positive(self):
        if self.selected_contradiction:
            self.resolve_contradiction(self.selected_contradiction.id, "False Positive")

    def resolve_contradiction(self, contradiction_id: int, status: str):
        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        service = get_contradiction_service()
        service.resolve_contradiction(contradiction_id, status)
        # Refresh list
        data = service.get_contradictions()
        self.contradictions = [Contradiction(**item) for item in data]
        self.selected_contradiction = None

    def clear_all(self):
        """Clear all contradictions from the database."""
        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        service = get_contradiction_service()
        deleted = service.clear_all_contradictions()
        logger.info(f"Cleared {deleted} contradictions")
        self.contradictions = []
        self._has_loaded = False

    # ==================== Background Job Methods ====================

    @rx.var
    def is_job_running(self) -> bool:
        """Check if a background job is currently running."""
        return self.job_status in ["queued", "running", "cooldown", "initializing"]

    @rx.var
    def is_job_paused(self) -> bool:
        """Check if job is paused."""
        return self.job_status == "paused"

    @rx.var
    def progress_pct(self) -> int:
        """Progress as percentage."""
        if self.job_total <= 0:
            return 0
        return int((self.job_progress / self.job_total) * 100)

    @rx.var
    def eta_display(self) -> str:
        """Simple ETA display based on progress."""
        if self.job_total <= 0 or self.job_progress <= 0:
            return "Calculating..."
        remaining = self.job_total - self.job_progress
        # Rough estimate: ~30 seconds per entity
        seconds = remaining * 30
        if seconds < 60:
            return f"~{seconds}s remaining"
        elif seconds < 3600:
            return f"~{seconds // 60}m remaining"
        else:
            return f"~{seconds // 3600}h {(seconds % 3600) // 60}m remaining"

    def start_background_detection(self):
        """Start a background detection job using the batch system."""
        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        # Reset job state
        self.job_status = "queued"
        self.job_progress = 0
        self.job_total = 0
        self.job_current_entity = ""
        self.job_found = 0
        self.job_error = ""

        service = get_contradiction_service()

        # First reset batches to start fresh, then start first batch
        service.reset_batches()

        # Start first batch using the new system
        job_id = service.start_next_batch(
            entity_ids=self.selected_entity_ids if self.selected_entity_ids else None,
            doc_ids=self.selected_doc_ids if self.selected_doc_ids else None,
            force_refresh=self.force_refresh,
            auto_continue=self.auto_continue,
        )

        if job_id:
            self.job_id = job_id
            logger.info(
                f"Started background job: {self.job_id} (force_refresh={self.force_refresh}, auto_continue={self.auto_continue})"
            )
        else:
            self.job_status = ""
            logger.warning("No entities to process")

        # Refresh batch overview
        self.load_batch_overview()

        # Clear banner after starting detection
        self.has_new_docs = False

    def toggle_force_refresh(self):
        """Toggle force refresh checkbox."""
        self.force_refresh = not self.force_refresh

    @rx.event(background=True)
    async def poll_job_status(self):
        """Poll job status from Redis. Called repeatedly by UI."""

        # Get current job_id synchronously
        async with self:
            current_job_id = self.job_id
            current_status = self.job_status

        if not current_job_id:
            return

        # Don't poll if job is complete/failed/stopped
        if current_status in ["complete", "failed", "stopped", "timeout", ""]:
            return

        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            status = service.get_job_status(current_job_id)

            async with self:
                self.job_status = status.get("status", "unknown")
                self.job_progress = int(status.get("processed", 0))
                self.job_total = int(status.get("total", 0))
                self.job_current_entity = status.get("current_entity", "")
                self.job_found = int(status.get("found", 0))
                self.job_error = status.get("error", "")

        except Exception as e:
            logger.error(f"Error polling job status: {e}")

    def pause_job(self):
        """Pause the running job."""
        if not self.job_id:
            return

        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        service = get_contradiction_service()
        service.pause_job(self.job_id)
        self.job_status = "pausing"  # Will update on next poll

    def resume_job(self):
        """Resume a paused job."""
        if not self.job_id:
            return

        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        service = get_contradiction_service()
        service.resume_job(self.job_id)
        self.job_status = "resuming"  # Will update on next poll

    def stop_job(self):
        """Stop the running job."""
        if not self.job_id:
            return

        from app.arkham.services.contradiction_service import (
            get_contradiction_service,
        )

        service = get_contradiction_service()
        service.stop_job(self.job_id)
        self.job_status = "stopping"  # Will update on next poll

    def load_results(self):
        """Load results after job completion."""
        self._has_loaded = False  # Force reload
        self.job_id = ""  # Clear job
        self.job_status = ""
        return ContradictionState.load_contradictions
