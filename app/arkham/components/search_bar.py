import reflex as rx
from ..state.search_state import SearchState
from .design_tokens import SPACING
from .search_history import search_history_panel
from .saved_searches import saved_searches_panel, save_search_dialog


def search_bar() -> rx.Component:
    """Main search input with filters."""
    return rx.box(
        rx.form(
            rx.hstack(
                # History toggle button
                rx.tooltip(
                    rx.button(
                        rx.icon(
                            tag="clock",
                            size=20,
                        ),
                        on_click=SearchState.toggle_history,
                        size="3",
                        variant="soft",
                        color_scheme="gray",
                        type="button",
                    ),
                    content="Search History",
                ),
                rx.input(
                    placeholder="Search documents, entities, and events...",
                    value=SearchState.query,
                    on_change=SearchState.set_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="full",
                    padding_left=SPACING["lg"],
                    name="query",
                ),
                # Saved searches toggle button
                rx.tooltip(
                    rx.button(
                        rx.icon(
                            tag="bookmark",
                            size=20,
                        ),
                        on_click=SearchState.toggle_saved_searches,
                        size="3",
                        variant="soft",
                        color_scheme="gray",
                        type="button",
                    ),
                    content="Saved Searches",
                ),
                # Save search dialog button
                rx.cond(
                    SearchState.query != "",
                    save_search_dialog(),
                ),
                rx.button(
                    rx.icon(tag="search"),
                    "Search",
                    type="submit",
                    loading=SearchState.is_loading,
                    size="3",
                    radius="full",
                    variant="solid",
                    color_scheme="blue",
                    cursor="pointer",
                ),
                width="100%",
                spacing=SPACING["md"],
                align="center",
            ),
            on_submit=SearchState.handle_submit,
            width="100%",
        ),
        # Search history panel (positioned absolutely left)
        search_history_panel(),
        # Saved searches panel (positioned absolutely right)
        saved_searches_panel(),
        position="relative",
        width="100%",
    )
