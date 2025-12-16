import reflex as rx
from ..components.layout import layout
from ..state.map_state import MapState
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING


def map_page() -> rx.Component:
    """Geospatial analysis page."""
    return layout(
        rx.vstack(
            rx.heading("🌍 Geospatial Analysis", size="8"),
            rx.text(
                "Visualize entity locations and geographic distribution.",
                color="gray.11",
                font_size=FONT_SIZE["sm"],
            ),
            # Controls
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            "Entity Types", size="2", weight="bold", color="gray.11"
                        ),
                        rx.spacer(),
                        rx.button(
                            "All",
                            on_click=MapState.select_all_types,
                            size="1",
                            variant="ghost",
                        ),
                        rx.button(
                            "None",
                            on_click=MapState.select_no_types,
                            size="1",
                            variant="ghost",
                        ),
                        rx.spacer(),
                        rx.button(
                            rx.icon(tag="globe", size=14),
                            "Run Geocoder",
                            on_click=MapState.run_geocoding,
                            loading=MapState.is_geocoding,
                            variant="soft",
                            color_scheme="blue",
                            size="2",
                        ),
                        width="100%",
                        align="center",
                    ),
                    rx.hstack(
                        rx.foreach(
                            MapState.available_types,
                            lambda t: rx.checkbox(
                                t,
                                checked=MapState.selected_types.contains(t),
                                on_change=lambda _: MapState.toggle_type(t),
                                size="2",
                            ),
                        ),
                        wrap="wrap",
                        spacing="4",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
                padding=CARD_PADDING,
            ),
            # Messages
            rx.cond(
                MapState.error_message != "",
                rx.callout(
                    MapState.error_message,
                    icon="triangle-alert",
                    color_scheme="red",
                    width="100%",
                ),
            ),
            rx.cond(
                MapState.success_message != "",
                rx.callout(
                    MapState.success_message,
                    icon="circle-check",
                    color_scheme="green",
                    width="100%",
                ),
            ),
            # Map Visualization
            rx.cond(
                MapState.is_loading,
                rx.center(
                    rx.spinner(size="3"),
                    height=f"{MapState.map_height}px",
                    width="100%",
                ),
                rx.center(
                    rx.box(
                        rx.plotly(data=MapState.map_figure),
                        width="100%",
                        max_width="1400px",
                        height=f"{MapState.map_height}px",
                        border_radius="md",
                        overflow="hidden",
                        border="1px solid",
                        border_color="gray.6",
                    ),
                    width="100%",
                ),
            ),
            # Stats / Controls
            rx.hstack(
                rx.text(
                    f"Showing {MapState.map_entities.length()} locations",
                    color="gray.11",
                    size="2",
                ),
                rx.spacer(),
                rx.text("Size:", color="gray.11", size="2"),
                rx.button(
                    "S",
                    on_click=lambda: MapState.set_map_height(400),
                    size="1",
                    variant="ghost",
                ),
                rx.button(
                    "M",
                    on_click=lambda: MapState.set_map_height(600),
                    size="1",
                    variant="ghost",
                ),
                rx.button(
                    "L",
                    on_click=lambda: MapState.set_map_height(800),
                    size="1",
                    variant="ghost",
                ),
                rx.button(
                    "XL",
                    on_click=lambda: MapState.set_map_height(1000),
                    size="1",
                    variant="ghost",
                ),
                width="100%",
                align="center",
            ),
            spacing=SPACING["md"],
            width="100%",
            on_mount=MapState.load_map_data,
        )
    )
