"""Search history component for displaying recent searches."""

import reflex as rx
from ..state.search_state import SearchState, SearchHistoryEntry
from .design_tokens import SPACING, CARD_PADDING


def search_history_item(entry: SearchHistoryEntry) -> rx.Component:
    """Render a single search history item."""
    return rx.box(
        rx.hstack(
            rx.icon(tag="clock", size=16, color="gray.9"),
            rx.vstack(
                rx.text(
                    entry["query"],
                    size="2",
                    weight="medium",
                    color="gray.12",
                    _hover={"color": "blue.11"},
                ),
                rx.text(
                    f"{entry['result_count']} results",
                    size="1",
                    color="gray.10",
                ),
                spacing="0",
                align="start",
                flex="1",
            ),
            width="100%",
            align="center",
            spacing=SPACING["sm"],
        ),
        padding=SPACING["sm"],
        border_radius="6px",
        _hover={
            "background": "var(--gray-3)",
            "cursor": "pointer",
        },
        on_click=lambda: SearchState.use_history_item(entry["query"]),
        width="100%",
    )


def search_history_panel() -> rx.Component:
    """Search history dropdown panel."""
    return rx.cond(
        SearchState.show_history,
        rx.card(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.text(
                        "Recent Searches",
                        size="2",
                        weight="bold",
                        color="gray.12",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="x", size=14),
                        on_click=SearchState.toggle_history,
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.divider(margin_y=SPACING["xs"]),
                # History items or empty state
                rx.cond(
                    SearchState.search_history.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            SearchState.search_history,
                            search_history_item,
                        ),
                        # Clear history button
                        rx.divider(margin_y=SPACING["xs"]),
                        rx.button(
                            rx.icon(tag="trash-2", size=14),
                            "Clear History",
                            on_click=SearchState.clear_history,
                            size="1",
                            variant="ghost",
                            color_scheme="red",
                            width="100%",
                        ),
                        spacing=SPACING["xs"],
                        width="100%",
                    ),
                    # Empty state
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="search", size=24, color="gray.8"),
                            rx.text(
                                "No recent searches",
                                size="1",
                                color="gray.10",
                            ),
                            spacing=SPACING["xs"],
                            align="center",
                        ),
                        padding=SPACING["lg"],
                        width="100%",
                    ),
                ),
                spacing=SPACING["sm"],
                width="100%",
            ),
            padding=CARD_PADDING,
            width="100%",
            max_width="400px",
            position="absolute",
            top="calc(100% + 8px)",
            left="0",
            z_index="1000",
            box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        ),
    )
