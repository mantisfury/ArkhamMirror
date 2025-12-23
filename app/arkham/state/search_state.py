import reflex as rx
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
from ..state.project_state import ProjectState


class SearchResultMetadata(TypedDict, total=False):
    """Metadata structure for search results."""

    title: str
    doc_type: str
    page_number: int
    doc_id: int
    text: str
    project_id: str


class SearchResult(TypedDict):
    """Structure of a single search result from hybrid_search."""

    id: str
    score: float
    doc_id: int
    text: str
    snippet: str
    metadata: SearchResultMetadata


class SearchHistoryEntry(TypedDict):
    """Structure for a search history entry."""

    query: str
    timestamp: str
    result_count: int


class SavedSearch(TypedDict):
    """Structure for a saved search bookmark."""

    id: str  # Unique identifier
    name: str  # User-defined name
    query: str
    date_from: str
    date_to: str
    entity_type_filter: str
    doc_type_filter: str
    created_at: str


class SearchState(rx.State):
    """State for the search page."""

    query: str = ""
    results: List[SearchResult] = []
    selected_result_id: Optional[str] = None

    # Filters
    date_from: str = ""
    date_to: str = ""
    entity_type_filter: str = "all"
    doc_type_filter: str = "all"

    # Pagination
    current_page: int = 1
    results_per_page: int = 20
    total_results: int = 0  # Note: Qdrant RRF doesn't give total count easily

    # Loading state
    is_loading: bool = False

    # Search history (stored in LocalStorage)
    search_history: List[SearchHistoryEntry] = []
    show_history: bool = False
    max_history_items: int = 10

    # Saved searches (stored in LocalStorage)
    saved_searches: List[SavedSearch] = []
    show_saved_searches: bool = False
    current_save_name: str = ""  # For naming/renaming saved searches
    is_current_search_saved: bool = False  # Track if current query is already saved

    # Document viewer
    doc_viewer_open: bool = False
    doc_viewer_title: str = ""
    doc_viewer_content: str = ""
    doc_viewer_loading: bool = False
    doc_viewer_doc_id: int = 0

    def open_document_viewer(self, doc_id_str: str):
        """Open document viewer and load full document."""
        try:
            doc_id = int(doc_id_str)
        except (ValueError, TypeError):
            self.doc_viewer_content = f"Invalid document ID: {doc_id_str}"
            self.doc_viewer_open = True
            return

        self.doc_viewer_doc_id = doc_id
        self.doc_viewer_title = f"Document #{doc_id}"
        self.doc_viewer_loading = True
        self.doc_viewer_open = True
        self.doc_viewer_content = ""
        yield

        try:
            from ..services.search_service import (
                get_document_content,
                get_document_title,
            )

            # Get title
            title = get_document_title(doc_id)
            self.doc_viewer_title = title or f"Document #{doc_id}"

            content = get_document_content(doc_id)
            self.doc_viewer_content = content
        except Exception as e:
            self.doc_viewer_content = f"Error loading document: {e}"
        finally:
            self.doc_viewer_loading = False

    def close_document_viewer(self):
        """Close document viewer."""
        self.doc_viewer_open = False
        self.doc_viewer_content = ""
        self.doc_viewer_title = ""

    # Search execution
    async def execute_search(self):
        """Run search against Qdrant."""
        if not self.query:
            return

        self.is_loading = True
        yield
        try:
            # Import service here to avoid circular imports
            from ..services.search_service import hybrid_search

            # Get project ID from global project state for filtering
            project_state = await self.get_state(ProjectState)
            project_id = project_state.selected_project_id_int

            # Run search in executor to avoid blocking event loop
            import asyncio
            from functools import partial

            loop = asyncio.get_event_loop()
            self.results = await loop.run_in_executor(
                None,
                partial(
                    hybrid_search,
                    query=self.query,
                    project_id=project_id if project_id else None,
                    limit=self.results_per_page,
                    offset=(self.current_page - 1) * self.results_per_page,
                    date_from=self.date_from if self.date_from else None,
                    date_to=self.date_to if self.date_to else None,
                    entity_type=self.entity_type_filter
                    if self.entity_type_filter != "all"
                    else None,
                    doc_type=self.doc_type_filter
                    if self.doc_type_filter != "all"
                    else None,
                    allowed_doc_ids=[self.filter_doc_id] if self.filter_doc_id else None,
                ),
            )

            # Add to search history after successful search
            self._add_to_history(self.query, len(self.results))

        except Exception as e:
            # Use centralized error handling
            from ..utils.error_handler import handle_database_error, format_error_for_ui

            error_info = handle_database_error(
                e,
                error_type="timeout" if "timeout" in str(e).lower() else "default",
                context={
                    "action": "search",
                    "query": self.query,
                    "page": self.current_page,
                },
            )

            # Show error to user via toast
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))

        finally:
            self.is_loading = False

    def handle_submit(self, form_data: Dict[str, Any]):
        """Handle search form submission."""
        # Update query from form data if present, though on_change should have handled it
        if "query" in form_data:
            self.query = form_data["query"]
        return SearchState.execute_search

    def set_query(self, query: str):
        self.query = query

    def set_current_page(self, page: int):
        self.current_page = page
        return self.execute_search()

    def set_date_from(self, date: str):
        """Set the start date filter."""
        self.date_from = date

    def set_date_to(self, date: str):
        """Set the end date filter."""
        self.date_to = date

    def set_entity_type_filter(self, entity_type: str):
        """Set the entity type filter."""
        self.entity_type_filter = entity_type

    def set_doc_type_filter(self, doc_type: str):
        """Set the document type filter."""
        self.doc_type_filter = doc_type

    def clear_filters(self):
        """Clear all filters."""
        self.date_from = ""
        self.date_to = ""
        self.entity_type_filter = "all"
        self.doc_type_filter = "all"
        return self.execute_search()

    async def export_results(self):
        """Export search results to CSV."""
        if not self.results:
            return

        try:
            import csv
            from datetime import datetime
            import os

            # Create exports directory if it doesn't exist
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{export_dir}/search_results_{timestamp}.csv"

            # Write CSV
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Document Title", "Document Type", "Page", "Score", "Snippet"]
                )

                for result in self.results:
                    metadata = result.get("metadata", {})
                    writer.writerow(
                        [
                            metadata.get("title", "Unknown"),
                            metadata.get("doc_type", "Unknown"),
                            metadata.get("page_number", "N/A"),
                            f"{result.get('score', 0):.4f}",
                            result.get("snippet", "")[:200],  # Truncate long snippets
                        ]
                    )

            # Show success toast
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_success(
                f"Exported {len(self.results)} results to {filename}"
            )

        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="permission"
                if "permission" in str(e).lower()
                else "default",
                context={
                    "action": "export_search_results",
                    "result_count": len(self.results),
                },
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info, show_error_id=False))

    def _add_to_history(self, query: str, result_count: int):
        """Add a search query to history (internal method)."""
        if not query or not query.strip():
            return

        # Remove duplicate if query already exists
        self.search_history = [
            entry
            for entry in self.search_history
            if entry["query"].lower() != query.lower()
        ]

        # Add new entry at the beginning
        new_entry: SearchHistoryEntry = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "result_count": result_count,
        }
        self.search_history.insert(0, new_entry)

        # Limit history size
        if len(self.search_history) > self.max_history_items:
            self.search_history = self.search_history[: self.max_history_items]

    def toggle_history(self):
        """Toggle search history visibility."""
        self.show_history = not self.show_history

    def clear_history(self):
        """Clear all search history."""
        self.search_history = []
        self.show_history = False

    async def use_history_item(self, query: str):
        """Load a query from history and execute search."""
        self.query = query
        self.current_page = 1  # Reset to first page
        self.show_history = False  # Hide history after selection
        await self.execute_search()

    # Saved Searches Methods
    def toggle_saved_searches(self):
        """Toggle saved searches visibility."""
        self.show_saved_searches = not self.show_saved_searches

    def _check_if_current_search_is_saved(self):
        """Check if current search parameters match any saved search."""
        for saved in self.saved_searches:
            if (
                saved["query"].lower() == self.query.lower()
                and saved["date_from"] == self.date_from
                and saved["date_to"] == self.date_to
                and saved["entity_type_filter"] == self.entity_type_filter
                and saved["doc_type_filter"] == self.doc_type_filter
            ):
                self.is_current_search_saved = True
                return
        self.is_current_search_saved = False

    def save_current_search(self, name: str = ""):
        """Save current search parameters as a bookmark."""
        if not self.query or not self.query.strip():
            return

        # Generate default name if not provided
        if not name or not name.strip():
            name = f"{self.query[:30]}..." if len(self.query) > 30 else self.query

        # Generate unique ID
        import uuid

        search_id = str(uuid.uuid4())

        # Create saved search entry
        saved_search: SavedSearch = {
            "id": search_id,
            "name": name,
            "query": self.query,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "entity_type_filter": self.entity_type_filter,
            "doc_type_filter": self.doc_type_filter,
            "created_at": datetime.now().isoformat(),
        }

        # Add to saved searches
        self.saved_searches.insert(0, saved_search)
        self.is_current_search_saved = True
        self.current_save_name = ""

    def delete_saved_search(self, search_id: str):
        """Delete a saved search by ID."""
        self.saved_searches = [s for s in self.saved_searches if s["id"] != search_id]
        self._check_if_current_search_is_saved()

    async def load_saved_search(self, search_id: str):
        """Load a saved search and execute it."""
        # Find the saved search
        saved_search = None
        for s in self.saved_searches:
            if s["id"] == search_id:
                saved_search = s
                break

        if not saved_search:
            return

        # Load all parameters
        self.query = saved_search["query"]
        self.date_from = saved_search["date_from"]
        self.date_to = saved_search["date_to"]
        self.entity_type_filter = saved_search["entity_type_filter"]
        self.doc_type_filter = saved_search["doc_type_filter"]
        self.current_page = 1

        # Hide saved searches panel
        self.show_saved_searches = False

        # Update saved status
        self.is_current_search_saved = True

        # Execute search
        await self.execute_search()

    def set_current_save_name(self, name: str):
        """Set the name for the current save operation."""
        self.current_save_name = name

    # Document filter from URL query parameter
    filter_doc_id: Optional[int] = None
    filter_doc_title: str = ""

    def clear_doc_filter(self):
        """Clear the document filter."""
        self.filter_doc_id = None
        self.filter_doc_title = ""
        return SearchState.execute_search
