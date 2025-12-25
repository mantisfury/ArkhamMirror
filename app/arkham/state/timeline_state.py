import reflex as rx
from typing import List, Dict, Any
import plotly.graph_objects as go


class TimelineState(rx.State):
    """State for timeline analysis."""

    events: List[Dict[str, Any]] = []
    date_range_start: str = ""
    date_range_end: str = ""
    gaps: List[Dict[str, Any]] = []

    # Heatmap data
    heatmap_type: str = "day_hour"  # Options: "day_hour", "weekly", "monthly"
    heatmap_data: Dict[str, Any] = {}
    heatmap_stats: Dict[str, Any] = {}

    # Loading state
    is_loading: bool = False
    is_loading_heatmap: bool = False

    # Session cache flags - prevents auto-reload when navigating back
    _has_loaded_timeline: bool = False
    _has_loaded_heatmap: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if timeline data has been loaded."""
        return len(self.events) > 0 or bool(self.heatmap_data)

    async def _load_timeline_impl(self):
        """Helper to load timeline events."""
        from ..services.timeline_service import get_timeline_events
        from ..state.project_state import ProjectState

        # All state access must be inside context manager for background tasks
        async with self:
            # Skip if already loaded (session cache)
            if self._has_loaded_timeline and self.events:
                return
            self.is_loading = True
            # Get other state inside same context
            project_state = await self.get_state(ProjectState)

        # Read project_id inside project_state context
        async with project_state:
            project_id = project_state.selected_project_id_int

        try:
            # Run synchronous service call (outside context - no state access)
            events = get_timeline_events(project_id=project_id)

            async with self:
                self.events = events
                self._has_loaded_timeline = True  # Mark as loaded for session cache

        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="default",
                context={"action": "load_timeline"},
            )

            async with self:
                toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))
        finally:
            async with self:
                self.is_loading = False

    @rx.event(background=True)
    async def load_timeline(self):
        """Load timeline events from service."""
        await self._load_timeline_impl()

    def refresh_timeline(self):
        """Force reload timeline, clearing cache."""
        self._has_loaded_timeline = False
        self._has_loaded_heatmap = False
        return TimelineState.load_all

    def set_date_range_start(self, date: str):
        self.date_range_start = date

    def set_date_range_end(self, date: str):
        self.date_range_end = date

    async def export_timeline(self):
        """Export timeline events and gaps to CSV."""
        if not self.events:
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_warning("No timeline events to export")
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
            filename = f"{export_dir}/timeline_events_{timestamp}.csv"

            # Write CSV
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Date", "Event Type", "Document", "Description", "Reliability"]
                )

                for event in self.events:
                    writer.writerow(
                        [
                            event.get("date", ""),
                            event.get("event_type", ""),
                            event.get("document_title", ""),
                            event.get("description", ""),
                            event.get("confidence", ""),
                        ]
                    )

            # Also export gaps if available
            if self.gaps:
                gap_filename = f"{export_dir}/timeline_gaps_{timestamp}.csv"
                with open(gap_filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["Gap Start", "Gap End", "Duration (Days)", "Suspicion Level"]
                    )

                    for gap in self.gaps:
                        writer.writerow(
                            [
                                gap.get("start", ""),
                                gap.get("end", ""),
                                gap.get("duration_days", ""),
                                gap.get("suspicious", ""),
                            ]
                        )

            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            gap_msg = f" and {gap_filename}" if self.gaps else ""
            async with toast_state:
                toast_state.show_success(f"Timeline exported to {filename}{gap_msg}")

        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="permission"
                if "permission" in str(e).lower()
                else "default",
                context={"action": "export_timeline"},
            )

            toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))

    async def _load_heatmap_impl(self):
        """Helper to load heatmap data."""
        from ..services.heatmap_service import (
            get_day_of_week_hour_heatmap,
            get_weekly_activity_heatmap,
            get_monthly_activity_heatmap,
            get_heatmap_summary_stats,
        )
        from ..state.project_state import ProjectState

        # All state access must be inside context manager for background tasks
        async with self:
            # Skip if already loaded (session cache)
            if self._has_loaded_heatmap and self.heatmap_data:
                return
            self.is_loading_heatmap = True
            current_heatmap_type = self.heatmap_type
            # Get other state inside same context
            project_state = await self.get_state(ProjectState)

        # Read project_id inside project_state context
        async with project_state:
            project_id = project_state.selected_project_id_int

        try:
            # Load appropriate heatmap based on type (outside context - no state access)
            if current_heatmap_type == "day_hour":
                heatmap_data = get_day_of_week_hour_heatmap(project_id=project_id)
            elif current_heatmap_type == "weekly":
                heatmap_data = get_weekly_activity_heatmap(project_id=project_id)
            elif current_heatmap_type == "monthly":
                heatmap_data = get_monthly_activity_heatmap(project_id=project_id)
            else:
                heatmap_data = get_day_of_week_hour_heatmap(
                    project_id=project_id
                )  # Default fallback

            # Load summary stats
            heatmap_stats = get_heatmap_summary_stats(project_id=project_id)

            async with self:
                self.heatmap_data = heatmap_data
                self.heatmap_stats = heatmap_stats
                self._has_loaded_heatmap = True  # Mark as loaded for session cache

        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="default",
                context={"action": "load_heatmap", "heatmap_type": current_heatmap_type},
            )

            async with self:
                toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))
        finally:
            async with self:
                self.is_loading_heatmap = False

    @rx.event(background=True)
    async def load_heatmap(self):
        """Load heatmap data based on selected type."""
        await self._load_heatmap_impl()

    @rx.event(background=True)
    async def load_all(self):
        """Load both timeline and heatmap data."""
        await self._load_timeline_impl()
        await self._load_heatmap_impl()

    def set_heatmap_type(self, heatmap_type: str):
        """Change heatmap visualization type."""
        self.heatmap_type = heatmap_type
        # Yield to trigger the async heatmap loader
        yield type(self).load_heatmap

    @rx.var
    def heatmap_figure(self) -> go.Figure:
        """Generate Plotly heatmap figure from data."""
        if not self.heatmap_data or not self.heatmap_data.get("z"):
            return go.Figure()

        # Create heatmap
        fig = go.Figure(
            data=go.Heatmap(
                z=self.heatmap_data["z"],
                x=self.heatmap_data["x"],
                y=self.heatmap_data["y"],
                colorscale="Blues",
                hoverongaps=False,
                hovertemplate="<b>%{y}</b><br>%{x}<br>Events: %{z}<extra></extra>",
            )
        )

        # Update layout based on heatmap type
        if self.heatmap_type == "day_hour":
            title = "Activity by Day of Week and Hour"
            xaxis_title = "Hour of Day"
            yaxis_title = "Day of Week"
        elif self.heatmap_type == "weekly":
            title = "Activity by Week"
            xaxis_title = "Week"
            yaxis_title = "Day of Week"
        else:  # monthly
            title = "Activity by Month and Day"
            xaxis_title = "Day of Month"
            yaxis_title = "Month"

        fig.update_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            height=400,
            margin=dict(l=80, r=20, t=60, b=60),
        )

        return fig
