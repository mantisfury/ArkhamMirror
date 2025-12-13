"""Graph explorer page with tabbed interface for visualization and settings."""

import reflex as rx
from ..components.layout import layout
from ..state.graph_state import GraphState
from ..state.graph_settings_state import GraphSettingsState
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING
from ..components.graph_settings_tab import graph_settings_tab


def graph_stats_bar() -> rx.Component:
    """Stats and controls bar above the graph."""
    return rx.hstack(
        rx.card(
            rx.vstack(
                rx.text("Nodes", size="2", color="gray.11"),
                rx.heading(GraphState.nodes.length(), size="6"),
                spacing=SPACING["xs"],
            ),
            padding=CARD_PADDING,
        ),
        rx.card(
            rx.vstack(
                rx.text("Edges", size="2", color="gray.11"),
                rx.heading(GraphState.edges.length(), size="6"),
                spacing=SPACING["xs"],
            ),
            padding=CARD_PADDING,
        ),
        rx.spacer(),
        # Export menu
        rx.cond(
            GraphState.nodes.length() > 0,
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        rx.icon(tag="download", size=16),
                        "Export",
                        size="2",
                        variant="soft",
                        color_scheme="green",
                    ),
                ),
                rx.menu.content(
                    rx.menu.item(
                        "Export as CSV",
                        on_click=GraphState.export_graph_csv,
                    ),
                    rx.menu.item(
                        "Export as JSON",
                        on_click=GraphState.export_graph_json,
                    ),
                ),
            ),
            rx.fragment(),
        ),
        spacing=SPACING["md"],
        width="100%",
        align="center",
    )


def graph_visualization() -> rx.Component:
    """The graph visualization area with loading and empty states."""
    return rx.box(
        rx.cond(
            GraphState.is_loading,
            rx.center(
                rx.spinner(size="3"),
                height="700px",
            ),
            rx.cond(
                GraphState.graph_figure,
                rx.plotly(data=GraphState.graph_figure),
                rx.box(
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="network", size=40, color="gray.8"),
                            rx.text("No graph data loaded", color="gray.11"),
                            rx.text(
                                "Click 'Generate Graph' above to build the entity relationship graph.",
                                color="gray.9",
                                size="1",
                            ),
                            rx.button(
                                rx.icon("play", size=16),
                                "Generate Graph",
                                on_click=GraphState.load_graph,
                                loading=GraphState.is_loading,
                                color_scheme="blue",
                                size="3",
                                margin_top=SPACING["md"],
                            ),
                            spacing=SPACING["sm"],
                            align="center",
                        ),
                        height="100%",
                    ),
                    width="100%",
                    height="700px",
                    bg="gray.3",
                    border_radius="md",
                    border="1px dashed",
                    border_color="gray.6",
                ),
            ),
        ),
        width="100%",
    )


def selected_node_panel() -> rx.Component:
    """Details panel for the selected node."""
    return rx.cond(
        GraphState.selected_node_id,
        rx.card(
            rx.vstack(
                rx.heading("Selected Entity", size="4"),
                rx.text(f"ID: {GraphState.selected_node_id}"),
                spacing=SPACING["sm"],
            ),
            width="100%",
            padding=CARD_PADDING,
        ),
        rx.fragment(),
    )


def graph_tab_content() -> rx.Component:
    """Content for the main Graph tab."""
    return rx.vstack(
        # Error message
        rx.cond(
            GraphState.error_message != "",
            rx.callout(
                GraphState.error_message,
                icon="triangle-alert",
                color_scheme="red",
                width="100%",
            ),
            rx.fragment(),
        ),
        # Stats bar
        graph_stats_bar(),
        # Main visualization
        graph_visualization(),
        # Selected node details
        selected_node_panel(),
        spacing=SPACING["md"],
        width="100%",
    )


def graph_page() -> rx.Component:
    """Graph explorer page with tabbed interface."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("🕸️ Entity Relationship Graph", size="8"),
                    rx.text(
                        "Explore connections between entities extracted from your documents.",
                        color="gray.11",
                        font_size=FONT_SIZE["sm"],
                    ),
                    align_items="start",
                    spacing=SPACING["xs"],
                ),
                rx.spacer(),
                # Generate or Refresh button based on data state
                rx.cond(
                    GraphState.has_data,
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Refresh Graph",
                        on_click=GraphState.refresh_graph,
                        loading=GraphState.is_loading,
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Generate Graph",
                        on_click=GraphState.load_graph,
                        loading=GraphState.is_loading,
                        color_scheme="blue",
                    ),
                ),
                width="100%",
                align_items="end",
            ),
            # Tabbed interface
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("network", size=16),
                            "Graph",
                            spacing=SPACING["xs"],
                            align="center",
                        ),
                        value="graph",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("settings", size=16),
                            "Settings",
                            spacing=SPACING["xs"],
                            align="center",
                        ),
                        value="settings",
                    ),
                ),
                rx.tabs.content(
                    graph_tab_content(),
                    value="graph",
                    padding_top=SPACING["md"],
                ),
                rx.tabs.content(
                    graph_settings_tab(),
                    value="settings",
                    padding_top=SPACING["md"],
                ),
                default_value="graph",
                width="100%",
            ),
            spacing=SPACING["md"],
            width="100%",
            # Only load entity types for settings (cheap), not the graph itself
            on_mount=GraphSettingsState.load_available_entity_types,
        )
    )
