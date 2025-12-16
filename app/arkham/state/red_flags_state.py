"""
Red Flags State Management

Manages state for the Red Flags Discovery page including filtering,
sorting, and red flag review actions.
"""

import reflex as rx
from typing import List, Dict
import logging

# NOTE: Service import moved inside methods to prevent slow startup (lazy loading)
from app.arkham.models import RedFlag

logger = logging.getLogger(__name__)


class RedFlagsState(rx.State):
    """State for Red Flags Discovery page."""

    # Data
    red_flags: List[RedFlag] = []
    selected_flag: Dict = {}

    # Filters
    severity_filter: str = "all"
    category_filter: str = "all"
    status_filter: str = "active"
    sort_by: str = "severity"  # severity, category, title, detected_at, status
    sort_direction: str = "desc"  # asc or desc

    # Summary stats
    summary_critical: int = 0
    summary_high: int = 0
    summary_medium: int = 0
    summary_low: int = 0
    summary_total: int = 0

    # Pagination
    current_page: int = 1
    items_per_page: int = 20
    total_items: int = 0

    # UI state
    show_detail_modal: bool = False
    is_loading: bool = False
    error_message: str = ""
    success_message: str = ""

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if red flags have been loaded."""
        return len(self.red_flags) > 0

    # Available filter options
    severity_options: List[str] = ["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
    category_options: List[str] = [
        "all",
        "round_numbers",
        "structuring",
        "backdated_document",
        "timeline_gap",
        "impossible_date",
        "high_anomaly_clustering",
        "name_changes",
        "sudden_disappearance",
        "creation_date_anomaly",
        "author_inconsistency",
        "invisible_characters",
        "whitespace_anomalies",
        "zero_width_steganography",
        "homoglyph_substitution",
        "hidden_layers",
        "ocr_anomalies",
    ]
    status_options: List[str] = ["active", "reviewed", "dismissed", "escalated", "all"]

    # Category display names for dropdown (pre-computed to avoid Var iteration)
    category_display_names: List[str] = [
        "All",
        "Round Numbers",
        "Structuring Pattern",
        "Backdated Document",
        "Timeline Gap",
        "Impossible Date",
        "High Anomaly Clustering",
        "Name Changes",
        "Sudden Disappearance",
        "Creation Date Anomaly",
        "Author Inconsistency",
        "Invisible Characters",
        "Whitespace Anomalies",
        "Zero-Width Steganography",
        "Homoglyph Substitution",
        "Hidden Layers",
        "OCR Anomalies",
    ]

    @rx.var
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.total_items == 0:
            return 1
        return (self.total_items + self.items_per_page - 1) // self.items_per_page

    @rx.var
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.current_page > 1

    @rx.var
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.current_page < self.total_pages

    def next_page(self):
        """Go to next page."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._has_loaded = False
            return RedFlagsState.load_red_flags

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._has_loaded = False
            return RedFlagsState.load_red_flags

    async def _load_red_flags_impl(self):
        """Implementation of red flags loading logic."""
        async with self:
            self.is_loading = True
            self.error_message = ""

        try:
            from app.arkham.services.red_flag_service import get_red_flag_service

            service = get_red_flag_service()

            # Apply filters
            severity = None if self.severity_filter == "all" else self.severity_filter
            category = None if self.category_filter == "all" else self.category_filter
            status = None if self.status_filter == "all" else self.status_filter

            # Calculate pagination - use large limit to get all, we'll scroll client-side
            offset = 0
            limit = 1000  # Get all flags, scrollable on client

            # Get flags as dicts with sorting
            flags_dicts = service.get_red_flags(
                severity_filter=severity,
                category_filter=category,
                status_filter=status,
                sort_by=self.sort_by,
                sort_direction=self.sort_direction,
                limit=limit,
                offset=offset,
            )

            # Load summary stats (includes total count)
            stats = service.get_summary_stats()

            # Convert to RedFlag objects and update state
            async with self:
                self.red_flags = [
                    RedFlag(
                        id=f.get("id", 0),
                        severity=f.get("severity", "LOW"),
                        flag_category=f.get("flag_category", ""),
                        title=f.get("title", ""),
                        description=f.get("description", ""),
                        detected_at=f.get("detected_at", ""),
                        status=f.get("status", "active"),
                        confidence=float(f.get("confidence", 0)),
                        evidence=f.get("evidence", {}),
                        document_id=f.get("document_id"),
                    )
                    for f in flags_dicts
                ]

                self.summary_critical = stats["critical"]
                self.summary_high = stats["high"]
                self.summary_medium = stats["medium"]
                self.summary_low = stats["low"]
                self.summary_total = stats["total"]
                self.total_items = stats["total"]

            logger.info(
                f"Loaded {len(self.red_flags)} red flags (page {self.current_page})"
            )

        except Exception as e:
            logger.error(f"Failed to load red flags: {e}")
            async with self:
                self.error_message = f"Failed to load red flags: {str(e)}"
                self.red_flags = []

        finally:
            async with self:
                self.is_loading = False
                self._has_loaded = True  # Mark as loaded for session cache

    @rx.event(background=True)
    async def load_red_flags(self):
        """Load red flags from database with current filters and pagination."""
        # Skip if already loaded (session cache)
        if self._has_loaded and self.red_flags:
            return

        await self._load_red_flags_impl()

    def set_severity_filter(self, value: str):
        """Set severity filter and reload."""
        self.severity_filter = value
        self._has_loaded = False
        return RedFlagsState.load_red_flags

    def set_category_filter(self, value: str):
        """Set category filter and reload."""
        self.category_filter = value
        self._has_loaded = False
        return RedFlagsState.load_red_flags

    def set_status_filter(self, value: str):
        """Set status filter and reload."""
        self.status_filter = value
        self._has_loaded = False
        return RedFlagsState.load_red_flags

    def refresh_flags(self):
        """Refresh red flags from database, clearing cache."""
        self._has_loaded = False
        return RedFlagsState.load_red_flags

    def set_sort_column(self, column: str):
        """Set sort column - clicking same column toggles direction."""
        if self.sort_by == column:
            # Toggle direction
            self.sort_direction = "asc" if self.sort_direction == "desc" else "desc"
        else:
            self.sort_by = column
            self.sort_direction = "desc"  # Default to descending for new column
        self._has_loaded = False
        return RedFlagsState.load_red_flags

    @rx.event(background=True)
    async def run_detection(self):
        """Run red flag detection on all documents."""
        async with self:
            self.is_loading = True
            self.error_message = ""
            self.success_message = ""

        try:
            from app.arkham.services.red_flag_service import get_red_flag_service

            service = get_red_flag_service()

            # Run all detectors
            logger.info("Running red flag detection...")
            flags = service.detect_all_red_flags()

            # Save to database
            saved_count = service.save_red_flags(flags)

            async with self:
                self.success_message = (
                    f"Detection complete! Found and saved {saved_count} new red flags."
                )
                self._has_loaded = False  # Force refresh on next load
            logger.info(f"Saved {saved_count} red flags")

            # Reload data after detection completes
            await self._load_red_flags_impl()

        except Exception as e:
            logger.error(f"Detection failed: {e}")
            async with self:
                self.error_message = f"Detection failed: {str(e)}"

        finally:
            async with self:
                self.is_loading = False

    def show_flag_details(self, flag: Dict):
        """Show detail modal for a specific flag."""
        self.selected_flag = flag
        self.show_detail_modal = True

    def close_detail_modal(self):
        """Close the detail modal."""
        self.show_detail_modal = False
        self.selected_flag = {}

    @rx.var
    def selected_flag_category_display(self) -> str:
        """Get formatted display name for selected flag category."""
        cat = self.selected_flag.get("flag_category", "")
        if isinstance(cat, str):
            return cat.replace("_", " ").title()
        return ""

    def handle_mark_reviewed(self):
        """Handle mark as reviewed click."""
        flag_id = self.selected_flag.get("id")
        if flag_id:
            self.mark_as_reviewed(flag_id)

    def handle_mark_dismissed(self):
        """Handle mark as dismissed click."""
        flag_id = self.selected_flag.get("id")
        if flag_id:
            self.mark_as_dismissed(flag_id)

    def handle_mark_escalated(self):
        """Handle mark as escalated click."""
        flag_id = self.selected_flag.get("id")
        if flag_id:
            self.mark_as_escalated(flag_id)

    def mark_as_reviewed(self, flag_id: int):
        """Mark a flag as reviewed."""
        return self._update_flag_status(flag_id, "reviewed", "Reviewed by analyst")

    def mark_as_dismissed(self, flag_id: int):
        """Mark a flag as dismissed (false positive)."""
        return self._update_flag_status(
            flag_id, "dismissed", "Dismissed as false positive"
        )

    def mark_as_escalated(self, flag_id: int):
        """Mark a flag as escalated for further investigation."""
        return self._update_flag_status(
            flag_id, "escalated", "Escalated for further investigation"
        )

    def _update_flag_status(self, flag_id: int, status: str, notes: str):
        """Internal method to update flag status."""
        try:
            from app.arkham.services.red_flag_service import get_red_flag_service

            service = get_red_flag_service()
            success = service.update_flag_status(flag_id, status, notes)

            if success:
                self.success_message = f"Flag marked as {status}"
                self.close_detail_modal()
                self._has_loaded = False
                return RedFlagsState.load_red_flags
            else:
                self.error_message = "Failed to update flag status"

        except Exception as e:
            logger.error(f"Failed to update flag: {e}")
            self.error_message = f"Failed to update flag: {str(e)}"

    def get_severity_color(self, severity: str) -> str:
        """Get color for severity badge."""
        colors = {
            "CRITICAL": "red",
            "HIGH": "orange",
            "MEDIUM": "yellow",
            "LOW": "blue",
        }
        return colors.get(severity, "gray")

    def get_category_display_name(self, category: str) -> str:
        """Convert category ID to display name."""
        names = {
            "round_numbers": "Round Numbers",
            "structuring": "Structuring Pattern",
            "backdated_document": "Backdated Document",
            "timeline_gap": "Timeline Gap",
            "impossible_date": "Impossible Date",
            "high_anomaly_clustering": "High Anomaly Clustering",
            "name_changes": "Name Changes",
            "sudden_disappearance": "Sudden Disappearance",
            "creation_date_anomaly": "Creation Date Anomaly",
            "author_inconsistency": "Author Inconsistency",
            "invisible_characters": "Invisible Characters",
            "whitespace_anomalies": "Whitespace Anomalies",
            "zero_width_steganography": "Zero-Width Steganography",
            "homoglyph_substitution": "Homoglyph Substitution",
            "hidden_layers": "Hidden Layers",
            "ocr_anomalies": "OCR Anomalies",
        }
        return names.get(category, category.replace("_", " ").title())

    def export_to_json(self):
        """Export current red flags to JSON file."""
        import json
        from datetime import datetime

        try:
            filename = (
                f"red_flags_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            # Export data
            export_data = {
                "export_date": datetime.now().isoformat(),
                "filters": {
                    "severity": self.severity_filter,
                    "category": self.category_filter,
                    "status": self.status_filter,
                },
                "total_flags": len(self.red_flags),
                "flags": self.red_flags,
            }

            with open(filename, "w") as f:
                json.dump(export_data, f, indent=2)

            self.success_message = f"Exported {len(self.red_flags)} flags to {filename}"
            logger.info(f"Exported red flags to {filename}")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.error_message = f"Export failed: {str(e)}"

    def clear_messages(self):
        """Clear success/error messages."""
        self.success_message = ""
        self.error_message = ""
