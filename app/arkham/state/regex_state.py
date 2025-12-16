import reflex as rx
import logging
from typing import List, Dict, Any, TypedDict

logger = logging.getLogger(__name__)


class PatternMatchResult(TypedDict):
    """Structure for pattern match results."""

    doc_id: int
    chunk_id: int
    pattern_type: str
    match_text: str
    confidence: float
    context: str
    document: str


class SensitiveDataStat(TypedDict):
    """Statistics for sensitive data detection."""

    pattern_type: str
    count: int


class RegexState(rx.State):
    """State for the Regex Search page."""

    # Pattern selection
    available_patterns: Dict[str, str] = {}
    pattern_options: List[str] = []  # List of pattern keys for select component
    selected_patterns: List[str] = ["email", "phone", "ssn"]
    custom_regex: str = ""
    custom_pattern_name: str = ""

    # Filters
    confidence_threshold: float = 0.5
    detected_pattern_filter: str = ""  # Single pattern filter for detected tab
    detected_min_confidence: float = 0.0

    # Search results
    search_results: List[Dict[str, Any]] = []
    is_searching: bool = False

    # Detected tab data
    detected_results: List[Dict[str, Any]] = []
    detected_stats: Dict[str, int] = {}
    is_loading_detected: bool = False

    # Active tab
    active_tab: str = "search"

    async def on_load(self):
        """Load available pattern types from backend on page load."""
        try:
            from ..services.regex_service import get_pattern_descriptions

            self.available_patterns = get_pattern_descriptions()
            self.pattern_options = list(self.available_patterns.keys())

            # Load detected data immediately
            await self.load_detected_data()
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")

    async def run_search(self):
        """Execute pattern search across all documents."""
        if not self.selected_patterns:
            return

        self.is_searching = True
        yield

        try:
            from ..services.regex_service import search_patterns_in_chunks
            import asyncio
            from functools import partial

            loop = asyncio.get_event_loop()
            self.search_results = await loop.run_in_executor(
                None,
                partial(
                    search_patterns_in_chunks,
                    pattern_types=self.selected_patterns,
                    confidence_threshold=self.confidence_threshold,
                ),
            )
        except Exception as e:
            from ..utils.error_handler import (
                handle_processing_error,
                format_error_for_ui,
            )
            from ..state.toast_state import ToastState

            error_info = handle_processing_error(
                e,
                error_type="default",
                context={
                    "action": "regex_search",
                    "pattern_types": self.selected_patterns,
                    "confidence_threshold": self.confidence_threshold,
                },
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
        finally:
            self.is_searching = False

    async def load_detected_data(self):
        """Load previously detected sensitive data from database."""
        self.is_loading_detected = True

        try:
            from ..services.regex_service import get_detected_sensitive_data
            import asyncio
            from functools import partial

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, partial(get_detected_sensitive_data)
            )

            self.detected_results = result["matches"]
            self.detected_stats = result["stats"]

        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="default",
                context={"action": "load_detected_sensitive_data"},
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
        finally:
            self.is_loading_detected = False

    def toggle_pattern(self, pattern: str):
        """Toggle a pattern in the selected patterns list (multi-select)."""
        if pattern == "all":
            self.select_all_patterns()
            return

        if pattern in self.selected_patterns:
            self.selected_patterns = [p for p in self.selected_patterns if p != pattern]
        else:
            self.selected_patterns = self.selected_patterns + [pattern]

    def select_all_patterns(self):
        """Select all available patterns."""
        self.selected_patterns = list(self.available_patterns.keys())

    def clear_patterns(self):
        """Clear all selected patterns."""
        self.selected_patterns = []

    def set_confidence_threshold(self, value: str):
        """Set minimum confidence threshold."""
        self.confidence_threshold = float(value)

    def set_custom_regex(self, value: str):
        """Set custom regex pattern."""
        self.custom_regex = value

    def set_detected_pattern_filter(self, pattern: str):
        """Set pattern type filter for detected tab."""
        if pattern == "all":
            self.detected_pattern_filter = ""
        else:
            self.detected_pattern_filter = pattern

    def set_detected_min_confidence(self, value: str):
        """Set confidence filter for detected tab."""
        self.detected_min_confidence = float(value)

    @rx.var
    def detected_matches(self) -> List[Dict[str, Any]]:
        """Filter detected results based on criteria."""
        results = self.detected_results
        if self.detected_pattern_filter:
            results = [
                r for r in results if r["pattern_type"] == self.detected_pattern_filter
            ]
        if self.detected_min_confidence > 0:
            results = [
                r for r in results if r["confidence"] >= self.detected_min_confidence
            ]
        return results

    @rx.var
    def unique_doc_count(self) -> int:
        """Count unique documents in detected matches."""
        if not self.detected_matches:
            return 0
        return len({match["document"] for match in self.detected_matches})

    @rx.var
    def selected_patterns_count(self) -> int:
        """Count of selected patterns."""
        return len(self.selected_patterns)

    @rx.var
    def selected_patterns_display(self) -> str:
        """Display string for selected patterns."""
        count = len(self.selected_patterns)
        if count == 0:
            return "No patterns selected"
        elif count == 1:
            return "1 pattern selected"
        else:
            return f"{count} patterns selected"
