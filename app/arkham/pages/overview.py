import reflex as rx
from ..components.layout import layout
from ..components.error_boundary import async_operation_wrapper, chart_error_boundary
from ..state.overview_state import OverviewState
from ..components.design_tokens import SPACING, CARD_PADDING, CARD_GAP


def stat_card_clickable(
    title: str, value: rx.Var, icon: str, color: str, on_click
) -> rx.Component:
    """A clickable statistic card that opens a drill-down modal."""
    return rx.card(
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=24, color="white"),
                bg=f"{color}.9",
                border_radius="full",
                padding=SPACING["sm"],
            ),
            rx.vstack(
                rx.text(title, size="1", color="gray.11", weight="bold"),
                rx.heading(value.to_string(), size="6"),
                spacing=SPACING["xs"],
            ),
            spacing=SPACING["md"],
            align="center",
        ),
        width="100%",
        padding=CARD_PADDING,
        cursor="pointer",
        _hover={"bg": "var(--gray-a3)", "transform": "scale(1.02)"},
        transition="all 0.2s",
        on_click=on_click,
    )


def stat_card(title: str, value: rx.Var, icon: str, color: str) -> rx.Component:
    """A simple statistic card (non-clickable)."""
    return rx.card(
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=24, color="white"),
                bg=f"{color}.9",
                border_radius="full",
                padding=SPACING["sm"],
            ),
            rx.vstack(
                rx.text(title, size="1", color="gray.11", weight="bold"),
                rx.heading(value.to_string(), size="6"),
                spacing=SPACING["xs"],
            ),
            spacing=SPACING["md"],
            align="center",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


def recent_doc_item(doc: dict) -> rx.Component:
    """A list item for recent documents."""
    return rx.hstack(
        rx.icon(tag="file-text", size=16, color="gray.11"),
        rx.vstack(
            rx.text(doc["title"], size="2", weight="medium"),
            rx.text(f"{doc['type']} • {doc['created_at']}", size="1", color="gray.11"),
            spacing=SPACING["xs"],
        ),
        width="100%",
        padding=SPACING["sm"],
        border_bottom="1px solid",
        border_color="gray.4",
    )


def drilldown_item(item) -> rx.Component:
    """A row in the drill-down modal list."""
    return rx.hstack(
        rx.badge(f"#{item.id}", variant="outline", size="1"),
        rx.text(item.name, size="2", weight="medium", flex="1"),
        rx.cond(
            item.type != "",
            rx.badge(item.type, size="1", variant="soft"),
            rx.fragment(),
        ),
        rx.cond(
            item.extra != "",
            rx.text(item.extra, size="1", color="gray"),
            rx.fragment(),
        ),
        width="100%",
        padding="3",
        border_bottom="1px solid var(--gray-4)",
        _hover={"bg": "var(--gray-a3)"},
    )


def drilldown_modal() -> rx.Component:
    """Modal for viewing drill-down lists with scrollable content."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(OverviewState.modal_title),
            rx.dialog.description(
                rx.text(
                    f"{OverviewState.modal_items.length()} items",
                    size="2",
                    color="gray",
                ),
            ),
            rx.cond(
                OverviewState.modal_loading,
                rx.center(
                    rx.spinner(size="3"),
                    padding="8",
                ),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(OverviewState.modal_items, drilldown_item),
                        width="100%",
                        spacing="0",
                    ),
                    max_height="60vh",
                    width="100%",
                ),
            ),
            rx.dialog.close(
                rx.button("Close", variant="soft", on_click=OverviewState.close_modal),
            ),
            max_width="600px",
        ),
        open=OverviewState.modal_open,
    )


def overview_page() -> rx.Component:
    """The project overview dashboard with error boundaries."""
    return layout(
        rx.vstack(
            rx.heading("📊 Project Overview", size="8"),
            rx.text(
                "Click on any stat card to view full list of items",
                size="2",
                color="gray",
            ),
            # Wrap main content with async_operation_wrapper for loading/error states
            async_operation_wrapper(
                content=rx.vstack(
                    # Stats Grid - Now Clickable
                    rx.grid(
                        stat_card_clickable(
                            "Total Documents",
                            OverviewState.total_docs,
                            "files",
                            "blue",
                            OverviewState.show_documents,
                        ),
                        stat_card_clickable(
                            "Total Entities",
                            OverviewState.total_entities,
                            "users",
                            "green",
                            OverviewState.show_entities,
                        ),
                        stat_card_clickable(
                            "Anomalies",
                            OverviewState.total_anomalies,
                            "triangle-alert",
                            "red",
                            OverviewState.show_anomalies,
                        ),
                        stat_card_clickable(
                            "Events",
                            OverviewState.total_events,
                            "calendar",
                            "purple",
                            OverviewState.show_events,
                        ),
                        columns="4",
                        spacing=CARD_GAP,
                        width="100%",
                    ),
                    # Charts Row with individual error boundaries
                    rx.grid(
                        # Document Type Chart with error boundary
                        chart_error_boundary(
                            chart_content=rx.card(
                                rx.plotly(data=OverviewState.doc_type_chart),
                                width="100%",
                                padding=CARD_PADDING,
                            ),
                            is_loading_var=OverviewState.is_loading,
                            has_error_var=OverviewState.has_chart_error,
                            error_message_var=OverviewState.chart_error_message,
                            retry_action=OverviewState.retry_load_stats,
                            height="400px",
                        ),
                        # Entity Type Chart with error boundary
                        chart_error_boundary(
                            chart_content=rx.card(
                                rx.plotly(data=OverviewState.entity_type_chart),
                                width="100%",
                                padding=CARD_PADDING,
                            ),
                            is_loading_var=OverviewState.is_loading,
                            has_error_var=OverviewState.has_chart_error,
                            error_message_var=OverviewState.chart_error_message,
                            retry_action=OverviewState.retry_load_stats,
                            height="400px",
                        ),
                        columns="2",
                        spacing=CARD_GAP,
                        width="100%",
                    ),
                    # Bottom Row: Recent Activity & Secondary Stats
                    rx.grid(
                        # Recent Documents
                        rx.card(
                            rx.vstack(
                                rx.heading("Recent Documents", size="4"),
                                rx.cond(
                                    OverviewState.recent_docs != [],
                                    rx.vstack(
                                        rx.foreach(
                                            OverviewState.recent_docs,
                                            recent_doc_item,
                                        ),
                                        width="100%",
                                    ),
                                    rx.center(
                                        rx.text("No recent documents", color="gray.11"),
                                        padding=SPACING["xl"],
                                    ),
                                ),
                                spacing=SPACING["md"],
                                width="100%",
                            ),
                            height="100%",
                            padding=CARD_PADDING,
                        ),
                        # Secondary Stats - Also Clickable
                        rx.vstack(
                            stat_card_clickable(
                                "Total Chunks",
                                OverviewState.total_chunks,
                                "layers",
                                "orange",
                                OverviewState.show_chunks,
                            ),
                            stat_card_clickable(
                                "Extracted Tables",
                                OverviewState.total_tables,
                                "table",
                                "cyan",
                                OverviewState.show_tables,
                            ),
                            spacing=CARD_GAP,
                            width="100%",
                        ),
                        columns="2",
                        spacing=CARD_GAP,
                        width="100%",
                    ),
                    spacing=SPACING["lg"],
                    width="100%",
                ),
                is_loading_var=OverviewState.is_loading,
                has_error_var=OverviewState.has_error,
                error_message_var=OverviewState.error_message,
                retry_action=OverviewState.retry_load_stats,
                loading_text="Loading overview statistics...",
            ),
            # Drill-down modal
            drilldown_modal(),
            spacing=SPACING["lg"],
            width="100%",
            on_mount=OverviewState.load_stats,
        ),
        page_name="Overview",
    )
