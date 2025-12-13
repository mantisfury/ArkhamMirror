"""
Contradiction Chain Page - Conspiracy board style visualization.
"""

import reflex as rx
from app.arkham.state.chain_state import ChainState
from app.arkham.components.sidebar import sidebar


def entity_filter_chip(entity) -> rx.Component:
    """Render an entity filter checkbox."""
    return rx.box(
        rx.checkbox(
            rx.hstack(
                rx.text(entity.name, size="2"),
                rx.badge(entity.label, size="1", variant="soft"),
                spacing="1",
            ),
            checked=ChainState.selected_entity_ids.contains(entity.id),
            on_change=lambda: ChainState.toggle_entity(entity.id),
            size="1",
        ),
        padding="1",
    )


def controls_panel() -> rx.Component:
    """Control panel for filters and view options."""
    return rx.card(
        rx.vstack(
            # Row 1: Confidence and quick actions
            rx.hstack(
                rx.vstack(
                    rx.text("Min Strength", size="1", weight="bold"),
                    rx.select(
                        [
                            "0%",
                            "10%",
                            "20%",
                            "30%",
                            "40%",
                            "50%",
                            "60%",
                            "70%",
                            "80%",
                            "90%",
                        ],
                        value=(ChainState.pending_min_confidence * 100).to(int).to(str)
                        + "%",
                        on_change=ChainState.set_min_confidence_dropdown,
                        size="1",
                        width="80px",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.checkbox(
                    "High Only",
                    checked=ChainState.pending_high_only,
                    on_change=ChainState.toggle_high_only,
                ),
                rx.checkbox(
                    "Group by Severity",
                    checked=ChainState.pending_group_by_severity,
                    on_change=ChainState.toggle_group_by_severity,
                ),
                rx.button(
                    rx.icon("zap", size=14),
                    "Zoom High",
                    variant="soft",
                    size="1",
                    on_click=ChainState.zoom_to_high_confidence,
                ),
                rx.button(
                    rx.icon("refresh-cw", size=14),
                    "Reset",
                    variant="ghost",
                    size="1",
                    on_click=ChainState.reset_filters,
                ),
                spacing="4",
                align_items="end",
            ),
            # Row 2: Sort and display options
            rx.hstack(
                rx.vstack(
                    rx.text("Sort", size="1", weight="bold"),
                    rx.select(
                        ["mentions", "alpha", "contradictions"],
                        value=ChainState.pending_sort_by,
                        on_change=ChainState.set_sort_by,
                        size="1",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.vstack(
                    rx.text("X-Axis", size="1", weight="bold"),
                    rx.radio_group(
                        ["sequence", "time"],
                        value=ChainState.pending_x_axis_mode,
                        on_change=ChainState.set_x_axis_mode,
                        direction="row",
                        size="1",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.vstack(
                    rx.text("Show", size="1", weight="bold"),
                    rx.select(
                        ["25", "50", "100", "All"],
                        value=ChainState.limit_display,
                        on_change=ChainState.set_limit,
                        size="1",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.button(
                    rx.icon("check", size=14),
                    "Apply Settings",
                    on_click=ChainState.load_chain_data,
                    loading=ChainState.is_loading,
                    color_scheme="green",
                ),
                spacing="4",
                align_items="end",
            ),
            # Row 3: Entity filters (collapsible)
            rx.cond(
                ChainState.available_entities.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.text("Filter Entities", size="1", weight="bold"),
                        rx.badge(
                            ChainState.available_entities.length().to(str)
                            + " available",
                            color_scheme="gray",
                            size="1",
                        ),
                        rx.text(
                            "(Select up to 10 for chart)",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                    ),
                    rx.scroll_area(
                        rx.hstack(
                            rx.foreach(
                                ChainState.available_entities, entity_filter_chip
                            ),
                            spacing="2",
                            wrap="wrap",
                        ),
                        height="100px",
                        width="100%",
                    ),
                    spacing="1",
                    align_items="start",
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing="4",
            width="100%",
        ),
        padding="4",
    )


def legend_component() -> rx.Component:
    """Legend showing shape and color meanings."""
    return rx.hstack(
        rx.text("Legend:", size="1", weight="bold", color="gray"),
        rx.hstack(
            rx.box(width="10px", height="10px", bg="#ef4444", border_radius="50%"),
            rx.text("High", size="1"),
            spacing="1",
        ),
        rx.hstack(
            rx.box(width="10px", height="10px", bg="#f97316", border_radius="50%"),
            rx.text("Medium", size="1"),
            spacing="1",
        ),
        rx.hstack(
            rx.box(width="10px", height="10px", bg="#9ca3af", border_radius="50%"),
            rx.text("Low", size="1"),
            spacing="1",
        ),
        rx.text("|", color="gray"),
        rx.text(
            "Open=Circle  Resolved=Diamond  FP=X  Escalated=Square",
            size="1",
            color="gray",
        ),
        spacing="3",
    )


def visualization_mode_selector() -> rx.Component:
    """Segmented control for switching between visualization modes."""
    return rx.hstack(
        rx.text("View:", size="2", weight="bold"),
        rx.segmented_control.root(
            rx.segmented_control.item(
                rx.hstack(
                    rx.icon("target", size=14),
                    rx.text("Conspiracy"),
                    spacing="1",
                ),
                value="conspiracy",
            ),
            rx.segmented_control.item(
                rx.hstack(
                    rx.icon("git-branch", size=14),
                    rx.text("Lie Web"),
                    spacing="1",
                ),
                value="web",
            ),
            rx.segmented_control.item(
                rx.hstack(
                    rx.icon("gantt-chart", size=14),
                    rx.text("Timeline"),
                    spacing="1",
                ),
                value="timeline",
            ),
            value=ChainState.visualization_mode,
            on_change=ChainState.set_visualization_mode,
            size="1",
        ),
        spacing="3",
        align_items="center",
    )


def web_entity_item(entity) -> rx.Component:
    """Single entity item in the web legend."""
    return rx.hstack(
        rx.box(
            width="12px",
            height="12px",
            bg=entity.color,
            border_radius="50%",
        ),
        rx.text(entity.name, size="1"),
        rx.button(
            rx.icon("focus", size=10),
            on_click=lambda: ChainState.focus_entity(entity.id),
            variant="ghost",
            size="1",
        ),
        cursor="pointer",
        spacing="1",
    )


def web_legend() -> rx.Component:
    """Interactive legend for the Lie Web view with entity focus buttons."""
    return rx.cond(
        ChainState.visualization_mode == "web",
        rx.card(
            rx.vstack(
                rx.text("Entities", weight="bold", size="2"),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            ChainState.web_entities,
                            web_entity_item,
                        ),
                        spacing="1",
                    ),
                    height="120px",
                ),
                spacing="2",
            ),
            padding="2",
            style={"min_width": "150px"},
        ),
        rx.fragment(),
    )


def entity_focus_badge() -> rx.Component:
    """Badge showing focused entity with clear button."""
    return rx.cond(
        ~ChainState.focused_entity_id.is_none(),
        rx.hstack(
            rx.badge(
                rx.hstack(
                    rx.icon("focus", size=12),
                    rx.text("Focused: "),
                    rx.text(ChainState.focused_entity_name, weight="bold"),
                    spacing="1",
                ),
                color_scheme="blue",
            ),
            rx.button(
                rx.icon("x", size=12),
                "Show All",
                on_click=ChainState.clear_focus,
                variant="ghost",
                size="1",
            ),
            spacing="2",
        ),
        rx.fragment(),
    )


def empty_state() -> rx.Component:
    """Empty state when no contradictions exist."""
    return rx.center(
        rx.vstack(
            rx.icon("git-branch", size=48, color="gray"),
            rx.heading("No Contradictions Found", size="5", color="gray"),
            rx.text(
                "Run contradiction detection first to populate this visualization.",
                color="gray",
            ),
            rx.link(
                rx.button(
                    rx.icon("arrow-left", size=14),
                    "Go to Contradictions",
                ),
                href="/contradictions",
            ),
            spacing="3",
            align_items="center",
        ),
        padding="8",
        width="100%",
    )


def evidence_item(evidence) -> rx.Component:
    """Render a single evidence item in the modal."""
    return rx.box(
        rx.text(evidence["text"], style={"font_style": "italic"}),
        rx.link(
            rx.hstack(
                rx.icon("file-text", size=12),
                rx.text(f"Document {evidence['document_id']}", size="1"),
                rx.icon("external-link", size=10),
                spacing="1",
                align="center",
            ),
            href=f"/document/{evidence['document_id']}",
            color="var(--accent-11)",
            size="1",
        ),
        padding="3",
        border="1px solid var(--gray-a6)",
        border_radius="6px",
        bg="var(--gray-a2)",
        width="100%",
    )


def contradiction_modal() -> rx.Component:
    """Modal for displaying contradiction details."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.heading("Contradiction Detail", size="5"),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x", size=16),
                            variant="ghost",
                            size="1",
                        )
                    ),
                    width="100%",
                ),
                # Entity and severity
                rx.hstack(
                    rx.heading(ChainState.modal_entity_name, size="6"),
                    rx.badge(
                        ChainState.modal_severity,
                        color_scheme=rx.match(
                            ChainState.modal_severity,
                            ("High", "red"),
                            ("Medium", "orange"),
                            "gray",
                        ),
                    ),
                    rx.badge(ChainState.modal_status, variant="outline"),
                    spacing="2",
                ),
                # Description
                rx.text(ChainState.modal_description),
                rx.divider(),
                # Evidence
                rx.heading("Evidence", size="4"),
                rx.vstack(
                    rx.foreach(ChainState.modal_evidence, evidence_item),
                    spacing="2",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            max_width="700px",
            padding="4",
        ),
        open=ChainState.has_modal_open,
        on_open_change=ChainState.on_modal_close,
    )


def chain_page() -> rx.Component:
    """Main Contradiction Chain visualization page."""
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.link(
                        rx.hstack(
                            rx.icon("arrow-left", size=14),
                            rx.text("Back to Contradictions"),
                            spacing="1",
                        ),
                        href="/contradictions",
                        color="var(--accent-11)",
                    ),
                    rx.spacer(),
                    rx.heading("Contradiction Chain", size="7"),
                    rx.spacer(),
                    # Mode badge - shows current mode
                    rx.match(
                        ChainState.visualization_mode,
                        (
                            "conspiracy",
                            rx.badge(
                                "Conspiracy Board View",
                                color_scheme="red",
                                variant="soft",
                            ),
                        ),
                        (
                            "web",
                            rx.badge(
                                "Lie Web View", color_scheme="purple", variant="soft"
                            ),
                        ),
                        (
                            "timeline",
                            rx.badge(
                                "Timeline View", color_scheme="blue", variant="soft"
                            ),
                        ),
                        rx.badge("View", variant="soft"),
                    ),
                    width="100%",
                    align_items="center",
                ),
                rx.text(
                    "Visual chain of contradictions across entities. "
                    "Red lines connect conflicting claims. Click a point for details.",
                    color="gray",
                    size="2",
                ),
                # Mode selector
                visualization_mode_selector(),
                # Collapsible controls section
                rx.vstack(
                    # Toggle button
                    rx.button(
                        rx.hstack(
                            rx.cond(
                                ChainState.controls_collapsed,
                                rx.icon("chevron-down", size=14),
                                rx.icon("chevron-up", size=14),
                            ),
                            rx.cond(
                                ChainState.controls_collapsed,
                                rx.text("Show Settings"),
                                rx.text("Hide Settings"),
                            ),
                            spacing="1",
                        ),
                        on_click=ChainState.toggle_controls,
                        variant="ghost",
                        size="1",
                    ),
                    # Controls panel (collapsible)
                    rx.cond(
                        ~ChainState.controls_collapsed,
                        controls_panel(),
                        rx.fragment(),
                    ),
                    width="100%",
                    align_items="start",
                ),
                # Status bar with focus badge
                rx.hstack(
                    rx.text(ChainState.showing_count, size="2", color="gray"),
                    entity_focus_badge(),
                    rx.spacer(),
                    legend_component(),
                    width="100%",
                    align_items="center",
                ),
                # Main visualization area with optional legend
                rx.hstack(
                    # Main chart
                    rx.cond(
                        ChainState.is_loading,
                        rx.center(
                            rx.vstack(
                                rx.spinner(size="3"),
                                rx.text("Loading chain data...", color="gray"),
                                spacing="2",
                            ),
                            padding="8",
                            width="100%",
                            min_height="600px",
                        ),
                        rx.cond(
                            ChainState.has_data,
                            # Conditional chart based on mode
                            rx.match(
                                ChainState.visualization_mode,
                                (
                                    "web",
                                    rx.scroll_area(
                                        rx.box(
                                            rx.plotly(
                                                data=ChainState.web_figure,
                                                on_click=ChainState.on_plotly_click,
                                                config={
                                                    "displayModeBar": True,
                                                    "modeBarButtonsToAdd": ["toImage"],
                                                    "displaylogo": False,
                                                    "scrollZoom": True,
                                                },
                                            ),
                                            width="100%",
                                        ),
                                        width="100%",
                                        height="calc(100vh - 400px)",
                                        border="1px solid var(--gray-a6)",
                                        border_radius="8px",
                                        bg="var(--gray-a1)",
                                        scrollbars="both",
                                    ),
                                ),
                                (
                                    "timeline",
                                    # Timeline swimlane visualization
                                    rx.scroll_area(
                                        rx.box(
                                            rx.plotly(
                                                data=ChainState.timeline_figure,
                                                on_click=ChainState.on_plotly_click,
                                                config={
                                                    "displayModeBar": True,
                                                    "modeBarButtonsToAdd": ["toImage"],
                                                    "displaylogo": False,
                                                    "scrollZoom": True,
                                                },
                                            ),
                                            min_width=ChainState.chart_min_width,
                                        ),
                                        width="100%",
                                        height="calc(100vh - 400px)",
                                        border="1px solid var(--gray-a6)",
                                        border_radius="8px",
                                        bg="var(--gray-a1)",
                                        scrollbars="both",
                                    ),
                                ),
                                # Default: conspiracy
                                rx.scroll_area(
                                    rx.box(
                                        rx.plotly(
                                            data=ChainState.chain_figure,
                                            on_click=ChainState.on_plotly_click,
                                            config={
                                                "displayModeBar": True,
                                                "modeBarButtonsToAdd": ["toImage"],
                                                "displaylogo": False,
                                                "scrollZoom": True,
                                            },
                                        ),
                                        min_width=ChainState.chart_min_width,
                                    ),
                                    width="100%",
                                    height="calc(100vh - 400px)",
                                    border="1px solid var(--gray-a6)",
                                    border_radius="8px",
                                    bg="var(--gray-a1)",
                                    scrollbars="both",
                                ),
                            ),
                            empty_state(),
                        ),
                    ),
                    # Web legend (only shown in web mode)
                    web_legend(),
                    width="100%",
                    spacing="4",
                    align_items="start",
                ),
                # Modal
                contradiction_modal(),
                padding="2em",
                width="100%",
                spacing="4",
                align_items="start",
                on_mount=ChainState.load_filter_options,
            ),
            width="100%",
            min_height="100vh",
            overflow_y="auto",
        ),
        width="100%",
        min_height="100vh",
    )
