"""
Red Flags Discovery Page

Displays automatically detected suspicious patterns in documents with filtering,
sorting, and review capabilities.
"""

import reflex as rx

from app.arkham.state.red_flags_state import RedFlagsState
from app.arkham.models import RedFlag
from ..components.layout import layout


def severity_badge(severity: str) -> rx.Component:
    """Display severity badge with color coding."""
    color_map = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "blue"}

    return rx.badge(severity, color_scheme=color_map.get(severity, "gray"), size="2")


def summary_card(title: str, count, color: str) -> rx.Component:
    """Summary stat card."""
    return rx.card(
        rx.vstack(
            rx.heading(count, size="8", color=color),
            rx.text(title, size="2", color="gray"),
            align="center",
            spacing="1",
        ),
        width="200px",
    )


def red_flag_row(flag: RedFlag) -> rx.Component:
    """Single red flag table row."""
    return rx.table.row(
        rx.table.cell(severity_badge(flag.severity)),
        rx.table.cell(rx.text(flag.flag_category, size="2")),
        rx.table.cell(rx.text(flag.title, size="2", weight="bold")),
        rx.table.cell(
            rx.text(
                flag.detected_at.to_string()[:10],  # Show date only
                size="2",
                color="gray",
            )
        ),
        rx.table.cell(
            rx.badge(
                flag.status,
                color_scheme=rx.cond(flag.status == "active", "green", "gray"),
                size="1",
            )
        ),
        rx.table.cell(
            rx.button(
                "View Details",
                size="1",
                variant="soft",
                on_click=lambda: RedFlagsState.show_flag_details(flag),
            )
        ),
        style={"_hover": {"background_color": "var(--gray-3)"}},
    )


def detail_modal() -> rx.Component:
    """Modal showing detailed red flag information."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.text("Red Flag Details"),
                    severity_badge(
                        RedFlagsState.selected_flag.get("severity", "MEDIUM")
                    ),
                    justify="between",
                    width="100%",
                )
            ),
            rx.dialog.description(
                rx.vstack(
                    # Title and category
                    rx.heading(RedFlagsState.selected_flag.get("title", ""), size="6"),
                    rx.text(
                        RedFlagsState.selected_flag_category_display,
                        size="2",
                        color="gray",
                    ),
                    # Description
                    rx.divider(),
                    rx.text("Description:", weight="bold", size="2"),
                    rx.text(
                        RedFlagsState.selected_flag.get("description", ""), size="2"
                    ),
                    # Evidence
                    rx.divider(),
                    rx.text("Evidence:", weight="bold", size="2"),
                    rx.cond(
                        RedFlagsState.selected_flag.get("evidence", {}),
                        rx.code_block(
                            str(RedFlagsState.selected_flag.get("evidence", {})),
                            language="json",
                            width="100%",
                        ),
                        rx.text("No evidence data", color="gray"),
                    ),
                    # Metadata
                    rx.divider(),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Strength:", weight="bold", size="1"),
                            rx.text(
                                f"{RedFlagsState.selected_flag.get('confidence', 0):.2%}",
                                size="2",
                            ),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Status:", weight="bold", size="1"),
                            rx.badge(
                                RedFlagsState.selected_flag.get("status", "active"),
                                size="1",
                            ),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Detected:", weight="bold", size="1"),
                            rx.text(
                                RedFlagsState.selected_flag.get(
                                    "detected_at", "N/A"
                                ).to_string()[:10],
                                size="2",
                            ),
                            spacing="1",
                        ),
                        spacing="4",
                    ),
                    # Action buttons
                    rx.divider(),
                    rx.hstack(
                        rx.button(
                            "Mark as Reviewed",
                            size="2",
                            variant="soft",
                            color_scheme="green",
                            on_click=RedFlagsState.handle_mark_reviewed,
                        ),
                        rx.button(
                            "Dismiss (False Positive)",
                            size="2",
                            variant="soft",
                            color_scheme="gray",
                            on_click=RedFlagsState.handle_mark_dismissed,
                        ),
                        rx.button(
                            "Escalate",
                            size="2",
                            variant="soft",
                            color_scheme="orange",
                            on_click=RedFlagsState.handle_mark_escalated,
                        ),
                        spacing="2",
                        wrap="wrap",
                    ),
                    spacing="3",
                    width="100%",
                    align="start",
                ),
                size="2",
            ),
            rx.dialog.close(rx.button("Close", size="2", variant="soft")),
            max_width="800px",
        ),
        open=RedFlagsState.show_detail_modal,
        on_open_change=RedFlagsState.close_detail_modal,
    )


def filters_section() -> rx.Component:
    """Filter controls."""
    return rx.hstack(
        # Severity filter
        rx.select(
            RedFlagsState.severity_options,
            value=RedFlagsState.severity_filter,
            on_change=RedFlagsState.set_severity_filter,
            placeholder="Severity",
            size="2",
        ),
        # Category filter
        rx.select(
            RedFlagsState.category_options,
            value=RedFlagsState.category_filter,
            on_change=RedFlagsState.set_category_filter,
            placeholder="Category",
            size="2",
        ),
        # Status filter
        rx.select(
            RedFlagsState.status_options,
            value=RedFlagsState.status_filter,
            on_change=RedFlagsState.set_status_filter,
            placeholder="Status",
            size="2",
        ),
        # Refresh button
        rx.button(
            rx.icon("refresh-cw", size=16),
            "Refresh",
            size="2",
            variant="soft",
            on_click=RedFlagsState.refresh_flags,
        ),
        # Run detection button
        rx.button(
            rx.icon("shield-alert", size=16),
            "Run Detection",
            size="2",
            variant="solid",
            color_scheme="blue",
            on_click=RedFlagsState.run_detection,
        ),
        # Export button
        rx.button(
            rx.icon("download", size=16),
            "Export JSON",
            size="2",
            variant="soft",
            on_click=RedFlagsState.export_to_json,
        ),
        spacing="3",
        wrap="wrap",
    )


def sortable_header(label: str, column: str) -> rx.Component:
    """Clickable column header with sort indicator."""
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(label, weight="bold"),
            rx.cond(
                RedFlagsState.sort_by == column,
                rx.cond(
                    RedFlagsState.sort_direction == "desc",
                    rx.icon("chevron-down", size=14),
                    rx.icon("chevron-up", size=14),
                ),
                rx.icon("chevrons-up-down", size=12, color="gray"),
            ),
            spacing="1",
            align="center",
        ),
        cursor="pointer",
        _hover={"background": "var(--gray-a3)"},
        on_click=lambda: RedFlagsState.set_sort_column(column),
    )


def red_flags_table() -> rx.Component:
    """Main red flags table with sortable headers and scrollable body."""
    return rx.scroll_area(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    sortable_header("Severity", "severity"),
                    sortable_header("Category", "category"),
                    sortable_header("Title", "title"),
                    sortable_header("Detected", "detected_at"),
                    sortable_header("Status", "status"),
                    rx.table.column_header_cell("Actions"),
                )
            ),
            rx.table.body(rx.foreach(RedFlagsState.red_flags, red_flag_row)),
            width="100%",
            variant="surface",
        ),
        max_height="calc(100vh - 400px)",
        width="100%",
    )


def red_flags_page() -> rx.Component:
    """Red Flags Discovery page."""
    return layout(
        rx.vstack(
            # Header
            rx.heading("Red Flag Discovery", size="8"),
            rx.text(
                "Automatically detected suspicious patterns requiring investigative attention",
                size="3",
                color="gray",
            ),
            # Messages
            rx.cond(
                RedFlagsState.success_message != "",
                rx.callout(
                    RedFlagsState.success_message,
                    icon="circle-check",
                    color_scheme="green",
                    role="alert",
                    on_click=RedFlagsState.clear_messages,
                ),
            ),
            rx.cond(
                RedFlagsState.error_message != "",
                rx.callout(
                    RedFlagsState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                    role="alert",
                    on_click=RedFlagsState.clear_messages,
                ),
            ),
            # Summary cards
            rx.hstack(
                summary_card("Critical", RedFlagsState.summary_critical, "red"),
                summary_card("High", RedFlagsState.summary_high, "orange"),
                summary_card("Medium", RedFlagsState.summary_medium, "yellow"),
                summary_card("Low", RedFlagsState.summary_low, "blue"),
                summary_card("Total Active", RedFlagsState.summary_total, "gray"),
                spacing="3",
                wrap="wrap",
            ),
            # Filters
            filters_section(),
            # Loading state
            rx.cond(
                RedFlagsState.is_loading,
                rx.hstack(
                    rx.spinner(size="3"),
                    rx.text("Loading red flags...", size="3"),
                    spacing="3",
                ),
            ),
            # Table
            rx.cond(
                RedFlagsState.red_flags.length() > 0,
                red_flags_table(),
                rx.cond(
                    ~RedFlagsState.is_loading,
                    rx.card(
                        rx.vstack(
                            rx.icon("shield-check", size=48, color="gray"),
                            rx.heading("No Red Flags Found", size="6", color="gray"),
                            rx.text(
                                "No red flags match the current filters. Try adjusting your filters or run detection.",
                                size="2",
                                color="gray",
                            ),
                            align="center",
                            spacing="3",
                        ),
                        width="100%",
                    ),
                ),
            ),
            # Detail modal
            detail_modal(),
            spacing="4",
            width="100%",
            align="start",
            # Removed on_mount - user must click Refresh or Run Detection
        )
    )
