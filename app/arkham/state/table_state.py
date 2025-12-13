import reflex as rx
from typing import List, Dict, Any, Optional


class TableState(rx.State):
    """State for the tables page."""

    tables: List[Dict[str, Any]] = []
    selected_table_id: Optional[int] = None
    selected_table_content: Dict[str, Any] = {}

    is_loading: bool = False
    error_message: str = ""

    # Pagination
    current_page: int = 1
    items_per_page: int = 20
    total_items: int = 0

    @rx.var
    def table_headers(self) -> List[str]:
        """Get headers from selected table content."""
        return self.selected_table_content.get("headers", [])

    @rx.var
    def table_rows(self) -> List[List[str]]:
        """Get rows from selected table content."""
        return self.selected_table_content.get("rows", [])

    async def load_tables(self):
        """Load the list of extracted tables."""
        self.is_loading = True
        self.error_message = ""
        yield
        try:
            from ..services.table_service import get_extracted_tables

            offset = (self.current_page - 1) * self.items_per_page
            result = get_extracted_tables(limit=self.items_per_page, offset=offset)

            self.tables = result["items"]
            self.total_items = result["total"]

            if not self.tables and self.current_page == 1:
                self.error_message = "No extracted tables found."
        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="not_found" if "not found" in str(e).lower() else "default",
                context={"action": "load_tables", "page": self.current_page},
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
            self.error_message = error_info["user_message"]
        finally:
            self.is_loading = False

    def set_current_page(self, page: int):
        """Set the current page and reload."""
        self.current_page = page
        return TableState.load_tables

    async def select_table(self, table_id: int):
        """Select a table and load its content."""
        self.selected_table_id = table_id
        self.is_loading = True
        self.error_message = ""
        yield
        try:
            from ..services.table_service import get_table_content

            self.selected_table_content = get_table_content(table_id)

            if "error" in self.selected_table_content:
                self.error_message = self.selected_table_content["error"]
        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="read_error" if "read" in str(e).lower() else "default",
                context={"action": "load_table_content", "table_id": table_id},
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
            self.error_message = error_info["user_message"]
        finally:
            self.is_loading = False

    async def export_csv(self):
        """Export the currently selected table to CSV."""
        if (
            not self.selected_table_content
            or "csv_path" not in self.selected_table_content
        ):
            self.error_message = "No CSV available for export."
            return

        csv_path = self.selected_table_content["csv_path"]

        # If no path but we have content, we could generate it, but that's a fallback.
        if not csv_path:
            self.error_message = "CSV file path is missing."
            return

        # Security check - ensure path is within allowed directories if needed
        # For now, we trust the database path but verify existence
        import os

        if not os.path.exists(csv_path):
            self.error_message = "CSV file not found on server."
            return

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()

            filename = os.path.basename(csv_path)
            return rx.download(data=content, filename=filename)

        except Exception as e:
            self.error_message = f"Failed to export CSV: {e}"

    def clear_selection(self):
        """Clear the selected table."""
        self.selected_table_id = None
        self.selected_table_content = {}
        self.error_message = ""
