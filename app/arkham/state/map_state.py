import reflex as rx
from typing import List, Dict, Any, Optional
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import textwrap


class MapState(rx.State):
    """State for the map page."""

    # Map data
    map_entities: List[Dict[str, Any]] = []
    selected_entity: Optional[Dict[str, Any]] = None

    # Filters - multi-select with checkboxes
    selected_types: List[str] = [
        "GPE",
        "LOC",
        "FAC",
        "ORG",
        "PERSON",
    ]  # Default selection
    available_types: List[str] = [
        "GPE",
        "LOC",
        "FAC",
        "ORG",
        "PERSON",
        "DATE",
        "WORK_OF_ART",
        "LAW",
        "PRODUCT",
        "NORP",
    ]

    # UI State
    is_loading: bool = False
    is_geocoding: bool = False
    error_message: str = ""
    success_message: str = ""
    map_height: int = 600  # Default map height in pixels

    @rx.var
    def map_figure(self) -> go.Figure:
        """Computed Plotly figure for the map."""
        if not self.map_entities:
            # Return empty map centered on world
            fig = go.Figure(go.Scattermapbox())
            fig.update_layout(
                mapbox_style="carto-darkmatter",
                mapbox_zoom=1,
                mapbox_center={"lat": 20, "lon": 0},
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                paper_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        df = pd.DataFrame(self.map_entities)

        # Size markers by mention count (log scale or capped)
        df["size"] = df["mentions"].apply(lambda x: min(20, max(5, x / 2)))

        # Wrap long addresses for hover display
        df["short_address"] = df["address"].apply(
            lambda x: textwrap.fill(x, width=40).replace('\n', '<br>') if x else ""
        )

        fig = px.scatter_mapbox(
            df,
            lat="lat",
            lon="lon",
            hover_name="name",
            hover_data=["type", "short_address", "mentions"],
            color="type",
            size="size",
            zoom=1,
            height=700,
        )

        fig.update_layout(
            mapbox_style="carto-darkmatter",
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(0,0,0,0.5)",
                font=dict(color="white"),
            ),
            hoverlabel=dict(
                bgcolor="rgba(30,30,30,0.9)",
                font_size=12,
                font_family="sans-serif",
            ),
            hovermode="closest",
            height=self.map_height,
            autosize=True,  # Allow responsive width
        )

        return fig

    @rx.event(background=True)
    async def load_map_data(self):
        """Load entities for the map."""
        async with self:
            self.is_loading = True
            self.error_message = ""

        try:
            from ..services.map_service import get_map_entities

            # Pass selected types list (or None if empty to get all)
            filter_types = self.selected_types if self.selected_types else None
            entities = get_map_entities(entity_types=filter_types, limit=1000)

            async with self:
                self.map_entities = entities
                if not self.map_entities:
                    self.error_message = (
                        "No geocoded entities found. Try running the geocoder."
                    )
        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="default",
                context={"action": "load_map_data"},
            )

            async with self:
                self.error_message = error_info["message"]

            toast_state = await self.get_state(ToastState)
            async with self:
                toast_state.show_error(format_error_for_ui(error_info))
        finally:
            async with self:
                self.is_loading = False

    async def run_geocoding(self):
        """Trigger batch geocoding."""
        self.is_geocoding = True
        self.success_message = ""
        self.error_message = ""
        yield
        try:
            from ..services.map_service import trigger_geocoding_batch

            count = trigger_geocoding_batch(limit=20)

            if count > 0:
                self.success_message = f"Successfully geocoded {count} new entities!"
                # Yield to trigger the background map data loader
                yield type(self).load_map_data
            else:
                self.success_message = (
                    "Geocoding complete. No new entities found or processed."
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
                context={"action": "run_geocoding"},
            )

            self.error_message = error_info["message"]

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
        finally:
            self.is_geocoding = False

    def toggle_type(self, entity_type: str):
        """Toggle an entity type in the selected list."""
        if entity_type in self.selected_types:
            self.selected_types = [t for t in self.selected_types if t != entity_type]
        else:
            self.selected_types = self.selected_types + [entity_type]
        return MapState.load_map_data

    def select_all_types(self):
        """Select all entity types."""
        self.selected_types = list(self.available_types)
        return MapState.load_map_data

    def select_no_types(self):
        """Clear all entity type selections."""
        self.selected_types = []
        return MapState.load_map_data

    def set_map_height(self, height: int):
        """Set map display height."""
        self.map_height = height
