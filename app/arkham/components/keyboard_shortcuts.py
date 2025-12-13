"""
Global keyboard shortcuts handler and help dialog.
"""

import reflex as rx
from ..state.keyboard_state import KeyboardState


def keyboard_shortcuts_listener() -> rx.Component:
    """
    Global keyboard event listener using JavaScript.

    This component should be included once in the root layout.
    It listens for keyboard events and communicates with Reflex state.
    """

    # JavaScript code for global keyboard shortcuts
    keyboard_script = """
    (function() {
        // Prevent duplicate listeners
        if (window.__arkhamKeyboardListenerInstalled) {
            return;
        }
        window.__arkhamKeyboardListenerInstalled = true;

        document.addEventListener('keydown', function(event) {
            // Cmd+K or Ctrl+K: Toggle global search
            if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
                event.preventDefault();
                // Trigger search modal via data attribute toggle
                const searchTrigger = document.querySelector('[data-shortcut-trigger="search"]');
                if (searchTrigger) {
                    searchTrigger.click();
                }
            }

            // Escape: Close modals
            if (event.key === 'Escape') {
                const escapeHandler = document.querySelector('[data-shortcut-trigger="escape"]');
                if (escapeHandler) {
                    escapeHandler.click();
                }
            }

            // Cmd+/ or Ctrl+/: Show shortcuts help
            if ((event.metaKey || event.ctrlKey) && event.key === '/') {
                event.preventDefault();
                const helpTrigger = document.querySelector('[data-shortcut-trigger="help"]');
                if (helpTrigger) {
                    helpTrigger.click();
                }
            }

            // Cmd+J or Ctrl+J: Focus main search input
            if ((event.metaKey || event.ctrlKey) && event.key === 'j') {
                event.preventDefault();
                const searchInput = document.querySelector('[data-main-search="true"]');
                if (searchInput) {
                    searchInput.focus();
                }
            }
        });
    })();
    """

    return rx.fragment(
        # Hidden trigger buttons that JavaScript can click
        rx.button(
            display="none",
            on_click=KeyboardState.toggle_search_modal,
            data_shortcut_trigger="search",
        ),
        rx.button(
            display="none",
            on_click=KeyboardState.close_all_modals,
            data_shortcut_trigger="escape",
        ),
        rx.button(
            display="none",
            on_click=KeyboardState.toggle_shortcuts_help,
            data_shortcut_trigger="help",
        ),
        # Inject the keyboard event listener
        rx.script(keyboard_script),
    )


def shortcuts_help_dialog() -> rx.Component:
    """
    Keyboard shortcuts help dialog.
    """

    shortcuts_list = [
        ("Cmd+K / Ctrl+K", "Open global search"),
        ("Cmd+J / Ctrl+J", "Focus search bar"),
        ("Cmd+/ / Ctrl+/", "Show this help"),
        ("Escape", "Close modals"),
        ("Enter", "Submit forms/Execute search"),
    ]

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    rx.hstack(
                        rx.icon(tag="keyboard", size=20),
                        rx.text("Keyboard Shortcuts"),
                        spacing="2",
                        align="center",
                    )
                ),
                rx.dialog.description(
                    "Use these keyboard shortcuts to navigate ArkhamMirror efficiently.",
                    size="2",
                    margin_bottom="4",
                ),
                rx.vstack(
                    *[
                        rx.hstack(
                            rx.box(
                                rx.code(
                                    shortcut,
                                    size="2",
                                    variant="soft",
                                    color_scheme="gray",
                                ),
                                width="200px",
                            ),
                            rx.text(description, size="2", color="gray"),
                            width="100%",
                            justify="between",
                            align="center",
                        )
                        for shortcut, description in shortcuts_list
                    ],
                    spacing="3",
                    width="100%",
                ),
                rx.flex(
                    rx.dialog.close(
                        rx.button(
                            "Close",
                            variant="soft",
                            color_scheme="gray",
                        )
                    ),
                    spacing="3",
                    margin_top="4",
                    justify="end",
                ),
                spacing="4",
                width="100%",
            ),
            style={"max_width": "500px"},
        ),
        open=KeyboardState.shortcuts_help_open,
        on_open_change=KeyboardState.toggle_shortcuts_help,
    )


def global_search_modal() -> rx.Component:
    """
    Global search modal triggered by Cmd+K / Ctrl+K.
    """
    from ..state.search_state import SearchState
    from ..components.result_card import result_card_compact

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Search"),
                rx.form(
                    rx.vstack(
                        rx.input(
                            placeholder="Search documents, entities, events...",
                            value=SearchState.query,
                            on_change=SearchState.set_query,
                            size="3",
                            width="100%",
                            auto_focus=True,
                            name="query",
                        ),
                        rx.hstack(
                            rx.cond(
                                SearchState.total_results > 0,
                                rx.text(
                                    f"{SearchState.total_results} results",
                                    size="2",
                                    color="gray",
                                ),
                                rx.text(
                                    "No results",
                                    size="2",
                                    color="gray",
                                ),
                            ),
                            rx.button(
                                rx.icon(tag="search", size=16),
                                "Search",
                                type="submit",
                                loading=SearchState.is_loading,
                                size="2",
                            ),
                            width="100%",
                            justify="between",
                            align="center",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=SearchState.handle_submit,
                    width="100%",
                ),
                # Results preview (first 5)
                rx.cond(
                    SearchState.total_results > 0,
                    rx.vstack(
                        rx.divider(),
                        rx.foreach(
                            SearchState.results[:5],
                            lambda result: result_card_compact(result),
                        ),
                        rx.cond(
                            SearchState.total_results > 5,
                            rx.link(
                                rx.button(
                                    f"View all {SearchState.total_results} results",
                                    variant="soft",
                                    size="2",
                                    width="100%",
                                ),
                                href="/search",
                                on_click=KeyboardState.close_all_modals,
                            ),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            style={"max_width": "700px", "max_height": "80vh", "overflow": "auto"},
        ),
        open=KeyboardState.search_modal_open,
        on_open_change=KeyboardState.toggle_search_modal,
    )
