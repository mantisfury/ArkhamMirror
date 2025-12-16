import reflex as rx
import logging
from typing import Dict, Any, List
from pydantic import BaseModel
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


class DrilldownItem(BaseModel):
    """Generic item for drill-down lists."""

    id: int
    name: str
    type: str = ""
    extra: str = ""


class OverviewState(rx.State):
    """State for the overview dashboard."""

    stats: Dict[str, Any] = {}

    # Loading and error states
    is_loading: bool = False
    has_error: bool = False
    error_message: str = ""

    # Chart-specific error tracking
    has_chart_error: bool = False
    chart_error_message: str = ""

    # Modal state for drill-downs
    modal_open: bool = False
    modal_title: str = ""
    modal_items: List[DrilldownItem] = []
    modal_loading: bool = False

    def reset_stats(self):
        """Clear all cached statistics. Called after nuclear wipe."""
        self.stats = {}
        self.modal_items = []
        self.has_error = False
        self.error_message = ""

    @rx.var
    def recent_docs(self) -> List[Dict[str, Any]]:
        """Get recent documents list safely."""
        return self.stats.get("recent_docs", [])

    # Computed vars for stats (fix JavaScript rendering issues)
    @rx.var
    def total_docs(self) -> int:
        """Total document count."""
        return self.stats.get("total_docs", 0)

    @rx.var
    def total_entities(self) -> int:
        """Total entity count."""
        return self.stats.get("total_entities", 0)

    @rx.var
    def total_anomalies(self) -> int:
        """Total anomaly count."""
        return self.stats.get("total_anomalies", 0)

    @rx.var
    def total_events(self) -> int:
        """Total timeline events count."""
        return self.stats.get("total_events", 0)

    @rx.var
    def total_chunks(self) -> int:
        """Total chunk count."""
        return self.stats.get("total_chunks", 0)

    @rx.var
    def total_tables(self) -> int:
        """Total extracted tables count."""
        return self.stats.get("total_tables", 0)

    @rx.var
    def docs_by_type(self) -> List[Dict[str, Any]]:
        """Documents grouped by type for chart."""
        return self.stats.get("docs_by_type", [])

    @rx.var
    def top_entity_types(self) -> List[Dict[str, Any]]:
        """Top entity types for chart."""
        return self.stats.get("top_entity_types", [])

    @rx.var
    def doc_type_chart(self) -> go.Figure:
        """Pie chart of document types."""
        data = self.docs_by_type
        if not data:
            return go.Figure()

        fig = px.pie(
            names=[d["type"] for d in data],
            values=[d["count"] for d in data],
            title="Documents by Type",
            hole=0.4,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            showlegend=True,
            margin=dict(t=40, b=0, l=0, r=0),
        )
        return fig

    @rx.var
    def entity_type_chart(self) -> go.Figure:
        """Bar chart of top entity types."""
        data = self.top_entity_types
        if not data:
            return go.Figure()

        fig = px.bar(
            x=[d["type"] for d in data],
            y=[d["count"] for d in data],
            title="Top Entity Types",
            labels={"x": "Type", "y": "Count"},
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            margin=dict(t=40, b=0, l=0, r=0),
        )
        fig.update_traces(marker_color="#3b82f6")
        return fig

    @rx.event(background=True)
    async def load_stats(self):
        """Load overview statistics with error handling."""
        async with self:
            self.is_loading = True
            self.has_error = False
            self.error_message = ""

        try:
            from ..services.overview_service import get_overview_stats

            stats = get_overview_stats()

            async with self:
                if not stats:
                    self.stats = {}
                else:
                    self.stats = stats
        except Exception as e:
            async with self:
                self.has_error = True
                self.error_message = str(e)
            logger.error(f"Error loading overview stats: {e}")

            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            async with self:
                toast_state.show_error(f"Failed to load statistics: {str(e)}")
        finally:
            async with self:
                self.is_loading = False

    def retry_load_stats(self):
        """Retry loading statistics."""
        return self.load_stats()

    def close_modal(self):
        """Close the drill-down modal."""
        self.modal_open = False
        self.modal_items = []

    def show_documents(self):
        """Show all documents in modal."""
        self.modal_title = "All Documents"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_all_documents

            docs = get_all_documents()
            self.modal_items = [
                DrilldownItem(
                    id=d["id"],
                    name=d["title"] or d["filename"],
                    type=d.get("media_type", ""),
                    extra=d.get("status", ""),
                )
                for d in docs
            ]
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False

    def show_entities(self):
        """Show all entities in modal."""
        self.modal_title = "All Entities"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_all_entities

            entities = get_all_entities()
            self.modal_items = [
                DrilldownItem(
                    id=e["id"],
                    name=e["name"],
                    type=e.get("type", ""),
                    extra=f"{e.get('mentions', 0)} mentions",
                )
                for e in entities
            ]
        except Exception as e:
            logger.error(f"Error loading entities: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False

    def show_anomalies(self):
        """Show all anomalies in modal."""
        self.modal_title = "All Anomalies"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_all_anomalies

            anomalies = get_all_anomalies()
            self.modal_items = [
                DrilldownItem(
                    id=a["id"],
                    name=a.get("description", f"Anomaly #{a['id']}")[:80],
                    type=a.get("type", ""),
                    extra=a.get("severity", ""),
                )
                for a in anomalies
            ]
        except Exception as e:
            logger.error(f"Error loading anomalies: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False

    def show_events(self):
        """Show all timeline events in modal."""
        self.modal_title = "All Timeline Events"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_all_events

            events = get_all_events()
            self.modal_items = [
                DrilldownItem(
                    id=e["id"],
                    name=e.get("description", f"Event #{e['id']}")[:80],
                    type=e.get("event_type", ""),
                    extra=e.get("date", ""),
                )
                for e in events
            ]
        except Exception as e:
            logger.error(f"Error loading events: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False

    def show_chunks(self):
        """Show chunks (sample) in modal."""
        self.modal_title = "Chunks (Sample - First 100)"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_sample_chunks

            chunks = get_sample_chunks(limit=100)
            self.modal_items = [
                DrilldownItem(
                    id=c["id"],
                    name=c.get("text", "")[:80] + "...",
                    type=f"Doc #{c.get('doc_id', '')}",
                    extra=f"Chunk {c.get('sequence', '')}",
                )
                for c in chunks
            ]
        except Exception as e:
            logger.error(f"Error loading chunks: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False

    def show_tables(self):
        """Show all extracted tables in modal."""
        self.modal_title = "Extracted Tables"
        self.modal_loading = True
        self.modal_open = True
        yield

        try:
            from ..services.overview_service import get_all_tables

            tables = get_all_tables()
            self.modal_items = [
                DrilldownItem(
                    id=t["id"],
                    name=t.get("title", f"Table #{t['id']}"),
                    type=f"Doc #{t.get('doc_id', '')}",
                    extra=f"{t.get('row_count', 0)} rows",
                )
                for t in tables
            ]
        except Exception as e:
            logger.error(f"Error loading tables: {e}")
            self.modal_items = []
        finally:
            self.modal_loading = False
