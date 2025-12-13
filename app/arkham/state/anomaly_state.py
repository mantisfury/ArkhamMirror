import reflex as rx
from typing import List, Dict, Any, Optional, TypedDict


class AnomalyItem(TypedDict):
    """Structure for an anomaly item."""

    id: int
    score: float
    reason: str
    chunk_id: int
    chunk_text: str
    doc_id: int
    doc_title: str


class AnomalyState(rx.State):
    """State for the anomalies page."""

    # Anomaly data
    anomalies: List[AnomalyItem] = []
    is_loading: bool = False

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    # Document selection - now multi-select
    available_documents: List[Dict[str, Any]] = []
    selected_doc_ids: List[int] = []  # List of selected document IDs
    last_previewed_doc_id: int = 0  # Track which doc is currently previewed
    document_text: str = ""
    use_all_documents: bool = True  # True means search all docs

    # Pagination
    current_page: int = 1
    items_per_page: int = 20
    total_items: int = 0

    # Severity filtering (backlog feature)
    min_score: float = 0.0
    max_score: float = 1.0
    severity_filter: str = ""  # "critical", "high", "medium", "low", ""

    # Chat state
    chat_messages: List[Dict[str, str]] = [
        {
            "role": "assistant",
            "content": "I am your forensic assistant. Ask me about specific files, anomalies, or the entire dataset.",
        }
    ]
    current_question: str = ""
    is_generating: bool = False

    @rx.var
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.total_items == 0:
            return 1
        return (self.total_items + self.items_per_page - 1) // self.items_per_page

    @rx.var
    def has_data(self) -> bool:
        """Check if anomaly data has been loaded."""
        return len(self.anomalies) > 0

    @rx.var
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.current_page > 1

    @rx.var
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.current_page < self.total_pages

    @rx.var
    def filtered_anomalies(self) -> List[AnomalyItem]:
        """Get anomalies filtered by severity thresholds."""
        filtered = []
        for a in self.anomalies:
            score = a.get("score", 0)

            # Apply score range filter
            if score < self.min_score or score > self.max_score:
                continue

            # Apply severity level filter
            if self.severity_filter:
                if self.severity_filter == "critical" and score < 0.9:
                    continue
                elif self.severity_filter == "high" and (score < 0.7 or score >= 0.9):
                    continue
                elif self.severity_filter == "medium" and (score < 0.5 or score >= 0.7):
                    continue
                elif self.severity_filter == "low" and score >= 0.5:
                    continue

            filtered.append(a)

        return filtered

    @rx.var
    def severity_stats(self) -> Dict[str, int]:
        """Count anomalies by severity level."""
        stats = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in self.anomalies:
            score = a.get("score", 0)
            if score >= 0.9:
                stats["critical"] += 1
            elif score >= 0.7:
                stats["high"] += 1
            elif score >= 0.5:
                stats["medium"] += 1
            else:
                stats["low"] += 1
        return stats

    def set_min_score(self, value: str):
        """Set minimum score filter."""
        try:
            self.min_score = float(value)
        except ValueError:
            pass

    def set_max_score(self, value: str):
        """Set maximum score filter."""
        try:
            self.max_score = float(value)
        except ValueError:
            pass

    def set_severity_filter(self, value: str):
        """Set severity level filter."""
        self.severity_filter = value

    def next_page(self):
        """Go to next page."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            return AnomalyState.load_anomalies

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            return AnomalyState.load_anomalies

    def go_to_page(self, page: int):
        """Go to specific page."""
        if 1 <= page <= self.total_pages:
            self.current_page = page
            return AnomalyState.load_anomalies

    @rx.event(background=True)
    async def load_anomalies(self):
        """Load anomaly data from the database with pagination."""
        # Skip if already loaded (session cache)
        if self._has_loaded and self.anomalies:
            return

        async with self:
            self.is_loading = True

        try:
            from ..services.anomaly_service import (
                get_anomalies,
                get_all_documents,
                get_anomaly_count,
            )

            offset = (self.current_page - 1) * self.items_per_page
            anomalies = get_anomalies(limit=self.items_per_page, offset=offset)
            total = get_anomaly_count()
            documents = get_all_documents()

            async with self:
                self.anomalies = anomalies
                self.total_items = total
                self.available_documents = documents
                self._has_loaded = True  # Mark as loaded for session cache
        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="default",
                context={"action": "load_anomalies"},
            )

            toast_state = await self.get_state(ToastState)
            async with self:
                toast_state.show_error(format_error_for_ui(error_info))
                self.anomalies = []
                self.available_documents = []
        finally:
            async with self:
                self.is_loading = False

    def refresh_anomalies(self):
        """Force reload anomalies, clearing cache."""
        self._has_loaded = False
        return AnomalyState.load_anomalies

    @rx.var
    def document_select_options(self) -> List[Dict[str, str]]:
        """Format documents for checkbox list."""
        return [
            {"id": str(doc["id"]), "label": f"{doc['title']} ({doc['doc_type']})"}
            for doc in self.available_documents
        ]

    @rx.var
    def selected_doc_ids_str(self) -> List[str]:
        """Get selected document IDs as strings."""
        return [str(doc_id) for doc_id in self.selected_doc_ids]

    @rx.var
    def selection_summary(self) -> str:
        """Get summary of current selection."""
        if self.use_all_documents:
            return f"Searching all {len(self.available_documents)} documents"
        elif len(self.selected_doc_ids) == 0:
            return "No documents selected"
        elif len(self.selected_doc_ids) == 1:
            return "1 document selected"
        else:
            return f"{len(self.selected_doc_ids)} documents selected"

    def set_use_all_documents(self, value: bool):
        """Toggle between all docs and specific selection."""
        self.use_all_documents = value
        if value:
            self.selected_doc_ids = []
            self.document_text = ""

    def toggle_document(self, doc_id_str: str):
        """Toggle a single document in the selection."""
        try:
            doc_id = int(doc_id_str)
            if doc_id in self.selected_doc_ids:
                # Unselecting - remove from list
                self.selected_doc_ids = [
                    d for d in self.selected_doc_ids if d != doc_id
                ]
                # If we unselected the previewed doc, clear preview or pick another
                if self.last_previewed_doc_id == doc_id:
                    if self.selected_doc_ids:
                        # Preview the last remaining selected doc
                        self.last_previewed_doc_id = self.selected_doc_ids[-1]
                        self._load_document_text(self.last_previewed_doc_id)
                    else:
                        self.last_previewed_doc_id = 0
                        self.document_text = ""
            else:
                # Selecting - add to list and preview this one
                self.selected_doc_ids = self.selected_doc_ids + [doc_id]
                self.last_previewed_doc_id = doc_id
                self._load_document_text(doc_id)

            # If we have selections, we're not using 'all'
            if self.selected_doc_ids:
                self.use_all_documents = False
        except ValueError:
            pass

    def select_all_documents(self):
        """Select all available documents."""
        self.selected_doc_ids = [doc["id"] for doc in self.available_documents]
        self.use_all_documents = False
        self.document_text = ""

    def clear_selection(self):
        """Clear selection and use all documents."""
        self.selected_doc_ids = []
        self.last_previewed_doc_id = 0
        self.use_all_documents = True
        self.document_text = ""

    def _load_document_text(self, doc_id: int):
        """Load text for a single document."""
        try:
            from ..services.anomaly_service import get_document_text

            self.document_text = get_document_text(doc_id)
        except Exception as e:
            self.document_text = f"Error loading document: {e}"

    def set_current_question(self, question: str):
        """Update the current question input."""
        self.current_question = question

    async def ask_question(self):
        """Process a user question with RAG context."""
        if not self.current_question.strip():
            return

        # Add user message
        self.chat_messages.append({"role": "user", "content": self.current_question})

        self.is_generating = True
        try:
            from ..services.anomaly_service import get_rag_response

            # Pass document IDs to RAG (None means all)
            doc_ids = None if self.use_all_documents else self.selected_doc_ids
            response = get_rag_response(query=self.current_question, doc_ids=doc_ids)

            # Add assistant response
            self.chat_messages.append({"role": "assistant", "content": response})
        except Exception as e:
            from ..utils.error_handler import handle_processing_error

            error_info = handle_processing_error(
                e,
                error_type="default",
                context={
                    "action": "rag_query",
                    "question": self.current_question,
                    "doc_id": self.selected_doc_id,
                },
            )

            # Add error message to chat
            self.chat_messages.append(
                {
                    "role": "assistant",
                    "content": f"I encountered an error: {error_info['message']}",
                }
            )
        finally:
            self.current_question = ""
            self.is_generating = False

    def chat_about_anomaly(self, doc_title: str, score: float):
        """Start a chat about a specific anomaly."""
        question = f"Tell me about the anomaly in {doc_title} (Score: {score:.2f})"
        self.chat_messages.append({"role": "user", "content": question})
        self.current_question = question
        # Yield to trigger the async question handler
        yield type(self).ask_question

    async def export_anomalies(self):
        """Export anomalies to CSV."""
        if not self.anomalies:
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_warning("No anomalies to export")
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
            filename = f"{export_dir}/anomalies_{timestamp}.csv"

            # Write CSV
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Score", "Reason", "Document", "Chunk Text"])

                for anomaly in self.anomalies:
                    writer.writerow(
                        [
                            anomaly.get("id", ""),
                            f"{anomaly.get('score', 0):.4f}",
                            anomaly.get("reason", ""),
                            anomaly.get("doc_title", ""),
                            anomaly.get("chunk_text", "")[:500],  # Truncate long text
                        ]
                    )

            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_success(
                f"Exported {len(self.anomalies)} anomalies to {filename}"
            )

        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="permission"
                if "permission" in str(e).lower()
                else "default",
                context={"action": "export_anomalies", "count": len(self.anomalies)},
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
