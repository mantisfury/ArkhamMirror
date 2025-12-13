import reflex as rx
from .sidebar import sidebar
from .toast import toast
from .design_tokens import PAGE_PADDING
from .keyboard_shortcuts import (
    keyboard_shortcuts_listener,
    global_search_modal,
    shortcuts_help_dialog,
)
from .welcome_modal import welcome_modal, WelcomeState


def layout(
    page_content: rx.Component,
    page_name: str = "Page",
    on_mount: rx.EventHandler = None,
) -> rx.Component:
    """
    Main layout wrapper for all pages.

    Args:
        page_content: The page content to display
        page_name: Name of the page for error context
        on_mount: Optional event handler to call when page loads

    Returns:
        Layout component with error boundaries
    """
    # Build the main layout
    main_layout = rx.hstack(
        sidebar(),
        rx.box(
            # Page content is already wrapped with error boundaries at page level
            page_content,
            flex="1",
            padding=PAGE_PADDING["x"],
            overflow_y="auto",
            height="100vh",
            bg="gray.1",  # Adapts to theme (light/dark) automatically
        ),
        width="100%",
        height="100vh",
        spacing="0",
    )

    # Collect on_mount handlers
    mount_handlers = [WelcomeState.check_first_run]
    if on_mount:
        mount_handlers.append(on_mount)

    return rx.fragment(
        # Global utilities
        toast(),  # Global toast notifications
        keyboard_shortcuts_listener(),  # Global keyboard shortcuts handler
        global_search_modal(),  # Cmd+K global search
        shortcuts_help_dialog(),  # Cmd+/ shortcuts help
        welcome_modal(),  # First-run welcome screen
        # Main layout
        rx.box(
            main_layout,
            on_mount=mount_handlers,
        ),
    )


def safe_layout(page_content: rx.Component, page_name: str = "Page") -> rx.Component:
    """
    Layout wrapper with error boundary protection.

    Use this for maximum safety on critical pages.

    Args:
        page_content: The page content to display
        page_name: Name of the page

    Returns:
        Error-protected layout
    """
    from .error_boundary import page_error_boundary

    # Wrap page content with error boundary before passing to layout
    safe_content = page_error_boundary(
        page_content,
        page_name=page_name,
    )

    return layout(safe_content, page_name)
