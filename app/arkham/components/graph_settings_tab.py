"""Graph settings tab component for configuring graph filters and display options."""

import reflex as rx
from ..state.graph_state import GraphState
from .design_tokens import SPACING, CARD_PADDING


def setting_section(title: str, *children) -> rx.Component:
    """A styled section for grouping related settings."""
    return rx.box(
        rx.heading(title, size="4", margin_bottom=SPACING["sm"]),
        rx.vstack(
            *children,
            spacing=SPACING["sm"],
            width="100%",
            align="start",
        ),
        width="100%",
        padding=CARD_PADDING,
        border="1px solid",
        border_color="gray.6",
        border_radius="md",
        margin_bottom=SPACING["md"],
    )


def dropdown_setting(
    label: str,
    value: rx.Var,
    on_change,
    options: list,
    tooltip: str = "",
) -> rx.Component:
    """A labeled dropdown with value display."""
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="2", color="gray.11"),
            rx.spacer(),
            rx.text(
                value,
                size="2",
                color="gray.12",
                weight="medium",
            ),
            width="100%",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="Select value"),
            rx.select.content(
                *[rx.select.item(str(opt), value=str(opt)) for opt in options],
            ),
            value=value.to_string(),
            on_change=on_change,
            size="2",
            width="100%",
        ),
        rx.cond(
            tooltip != "",
            rx.text(tooltip, size="1", color="gray.9"),
            rx.fragment(),
        ),
        spacing=SPACING["xs"],
        width="100%",
    )


def toggle_setting(
    label: str,
    checked: rx.Var,
    on_change,
    tooltip: str = "",
) -> rx.Component:
    """A labeled toggle switch."""
    return rx.hstack(
        rx.vstack(
            rx.text(label, size="2", color="gray.12"),
            rx.cond(
                tooltip != "",
                rx.text(tooltip, size="1", color="gray.9"),
                rx.fragment(),
            ),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.switch(
            checked=checked,
            on_change=on_change,
        ),
        width="100%",
        align="center",
    )


def entity_type_filter_chip(entity_type: str) -> rx.Component:
    """Chip button for filtering entity types."""
    is_excluded = GraphState.exclude_entity_types.contains(entity_type)
    return rx.button(
        entity_type,
        variant=rx.cond(is_excluded, "solid", "outline"),
        color_scheme=rx.cond(is_excluded, "red", "gray"),
        size="1",
        on_click=lambda: GraphState.toggle_entity_type_exclusion(entity_type),
    )


def graph_settings_tab() -> rx.Component:
    """Settings tab for configuring graph display and filtering options."""
    return rx.vstack(
        # === FILTERING SECTION ===
        setting_section(
            "🔍 Filtering",
            # Min Edge Strength
            dropdown_setting(
                "Min Edge Strength",
                GraphState.min_edge_strength,
                GraphState.set_min_edge_strength_from_dropdown,
                [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                "Only show relationships stronger than this threshold",
            ),
            # Min Connections
            dropdown_setting(
                "Min Connections",
                GraphState.min_degree,
                GraphState.set_min_degree_from_dropdown,
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20],
                "Hide nodes with fewer connections than this",
            ),
            # Max Document Ratio
            dropdown_setting(
                "Max Document Ratio",
                GraphState.max_doc_ratio,
                GraphState.set_max_doc_ratio_from_dropdown,
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                "Hide super-nodes appearing in more than this % of documents",
            ),
            # Hide Singletons
            toggle_setting(
                "Hide Singletons",
                GraphState.hide_singletons,
                GraphState.set_hide_singletons,
                "Remove nodes with no connections",
            ),
        ),
        # === ENTITY TYPE FILTERS ===
        setting_section(
            "🏷️ Entity Type Filters",
            rx.text(
                "Click to toggle exclusion. Red = excluded from graph.",
                size="1",
                color="gray.9",
                margin_bottom=SPACING["xs"],
            ),
            rx.flex(
                rx.foreach(
                    GraphState.available_entity_types,
                    entity_type_filter_chip,
                ),
                wrap="wrap",
                gap=SPACING["xs"],
                width="100%",
            ),
            rx.cond(
                GraphState.available_entity_types.length() == 0,
                rx.text(
                    "No entity types loaded. Click 'Refresh Types' below.",
                    size="1",
                    color="gray.9",
                    style={"fontStyle": "italic"},
                ),
                rx.fragment(),
            ),
            rx.button(
                rx.icon("refresh-cw", size=14),
                "Refresh Types",
                size="1",
                variant="soft",
                on_click=GraphState.load_available_entity_types,
            ),
        ),
        # === LABEL SETTINGS ===
        setting_section(
            "🔤 Labels",
            # Master Label Toggle
            toggle_setting(
                "Show Labels",
                GraphState.show_labels,
                GraphState.toggle_labels,
                "Master toggle for node labels",
            ),
            # Label Mode
            rx.vstack(
                rx.text("Label Visibility", size="2", color="gray.11"),
                rx.select.root(
                    rx.select.trigger(placeholder="Select mode"),
                    rx.select.content(
                        rx.select.item("All Labels", value="all"),
                        rx.select.item("Top by Degree", value="top_percent"),
                        rx.select.item("No Labels", value="none"),
                    ),
                    value=GraphState.label_visibility_mode,
                    on_change=GraphState.set_label_visibility_mode,
                    size="2",
                ),
                rx.text(
                    "Control which nodes show labels",
                    size="1",
                    color="gray.9",
                ),
                spacing=SPACING["xs"],
                width="100%",
                align="start",
            ),
            # Label Percent (only show when mode is top_percent)
            rx.cond(
                GraphState.label_visibility_mode == "top_percent",
                dropdown_setting(
                    "Top % by Connections",
                    GraphState.label_percent,
                    GraphState.set_label_percent_from_dropdown,
                    [5, 10, 15, 20, 25, 30, 40, 50, 75, 100],
                    "Only show labels for the most connected nodes",
                ),
                rx.fragment(),
            ),
        ),
        # === RENDERING SETTINGS ===
        setting_section(
            "🎨 Rendering",
            # Edge Opacity
            dropdown_setting(
                "Edge Opacity",
                GraphState.edge_opacity,
                GraphState.set_edge_opacity_from_dropdown,
                [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0],
                "Lower values reduce visual clutter from many edges",
            ),
            # Spring Force (layout spread)
            dropdown_setting(
                "Spring Force",
                GraphState.spring_k,
                GraphState.set_spring_k_from_dropdown,
                [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
                "Higher values spread nodes further apart",
            ),
            # Node Size Min
            dropdown_setting(
                "Min Node Size",
                GraphState.node_size_min,
                GraphState.set_node_size_min_from_dropdown,
                [2, 4, 6, 8, 10, 12, 15, 20, 25, 30],
                "Minimum size for node markers",
            ),
            # Node Size Max
            dropdown_setting(
                "Max Node Size",
                GraphState.node_size_max,
                GraphState.set_node_size_max_from_dropdown,
                [20, 30, 40, 50, 60, 75, 100],
                "Maximum size for node markers",
            ),
        ),
        # === LAYOUT SETTINGS ===
        setting_section(
            "📐 Layout",
            rx.vstack(
                rx.text("Layout Algorithm", size="2", color="gray.11"),
                rx.select.root(
                    rx.select.trigger(placeholder="Select layout"),
                    rx.select.content(
                        rx.select.item("Spring (Force-Directed)", value="spring"),
                        rx.select.item("Circular", value="circular"),
                        rx.select.item("Kamada-Kawai", value="kamada"),
                    ),
                    value=GraphState.layout_algorithm,
                    on_change=GraphState.set_layout_algorithm,
                    size="2",
                ),
                rx.text(
                    "Choose how nodes are positioned in the graph",
                    size="1",
                    color="gray.9",
                ),
                spacing=SPACING["xs"],
                width="100%",
                align="start",
            ),
        ),
        # === ACTIONS ===
        rx.hstack(
            rx.button(
                rx.icon("rotate-ccw", size=14),
                "Reset to Defaults",
                variant="soft",
                color_scheme="gray",
                on_click=GraphState.reset_to_defaults,
            ),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=14),
                "Reload Graph",
                variant="solid",
                color_scheme="blue",
                on_click=GraphState.refresh_graph,
            ),
            width="100%",
            align="center",
        ),
        rx.callout(
            "After changing settings, click 'Reload Graph' to apply them.",
            icon="info",
            size="1",
            color_scheme="blue",
            width="100%",
        ),
        spacing=SPACING["md"],
        width="100%",
        padding=SPACING["md"],
        on_mount=GraphState.load_available_entity_types,
    )
