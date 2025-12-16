"""Saved searches component for bookmarking and managing search queries."""

import reflex as rx
from ..state.search_state import SearchState, SavedSearch
from .design_tokens import SPACING, CARD_PADDING


def saved_search_item(search: SavedSearch) -> rx.Component:
    """Render a single saved search item."""
    return rx.box(
        rx.hstack(
            # Icon and name
            rx.hstack(
                rx.icon(tag="bookmark", size=16, color="blue.9"),
                rx.vstack(
                    rx.text(
                        search["name"],
                        size="2",
                        weight="medium",
                        color="gray.12",
                        _hover={"color": "blue.11"},
                    ),
                    rx.text(
                        search["query"],
                        size="1",
                        color="gray.10",
                        max_width="200px",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                    ),
                    spacing="0",
                    align="start",
                    flex="1",
                ),
                spacing=SPACING["sm"],
                flex="1",
                on_click=lambda: SearchState.load_saved_search(search["id"]),
                cursor="pointer",
            ),
            # Delete button
            rx.icon_button(
                rx.icon(tag="trash-2", size=14),
                on_click=lambda: SearchState.delete_saved_search(search["id"]),
                size="1",
                variant="ghost",
                color_scheme="red",
            ),
            width="100%",
            align="center",
            justify="between",
        ),
        padding=SPACING["sm"],
        border_radius="6px",
        _hover={"background": "var(--gray-3)"},
        width="100%",
    )


def save_search_dialog() -> rx.Component:
    """Dialog for saving current search with custom name."""
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon(tag="bookmark-plus", size=16),
                "Save Search",
                size="2",
                variant="soft",
                color_scheme="blue",
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("Save Search"),
            rx.dialog.description(
                "Give this search a memorable name so you can quickly access it later."
            ),
            rx.vstack(
                rx.input(
                    placeholder="e.g., 'Recent financial documents' or 'Q4 emails'",
                    value=SearchState.current_save_name,
                    on_change=SearchState.set_current_save_name,
                    size="3",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            size="2",
                            variant="soft",
                            color_scheme="gray",
                        ),
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Save",
                            on_click=lambda: SearchState.save_current_search(
                                SearchState.current_save_name
                            ),
                            size="2",
                            variant="solid",
                            color_scheme="blue",
                        ),
                    ),
                    spacing=SPACING["sm"],
                    justify="end",
                    width="100%",
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            max_width="450px",
        ),
    )


def saved_searches_panel() -> rx.Component:
    """Saved searches dropdown panel."""
    return rx.cond(
        SearchState.show_saved_searches,
        rx.card(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.text(
                        "Saved Searches",
                        size="2",
                        weight="bold",
                        color="gray.12",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="x", size=14),
                        on_click=SearchState.toggle_saved_searches,
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.divider(margin_y=SPACING["xs"]),
                # Saved searches list or empty state
                rx.cond(
                    SearchState.saved_searches.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            SearchState.saved_searches,
                            saved_search_item,
                        ),
                        spacing=SPACING["xs"],
                        width="100%",
                    ),
                    # Empty state
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="bookmark", size=24, color="gray.8"),
                            rx.text(
                                "No saved searches yet",
                                size="1",
                                color="gray.10",
                            ),
                            rx.text(
                                "Save your frequent searches for quick access",
                                size="1",
                                color="gray.9",
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
            max_width="450px",
            position="absolute",
            top="calc(100% + 8px)",
            right="0",
            z_index="1000",
            box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        ),
    )
