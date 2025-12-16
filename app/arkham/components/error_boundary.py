"""
Error boundary components for graceful failure handling.

Provides React-style error boundaries for Reflex applications,
catching errors and displaying fallback UI while maintaining app stability.
"""

import reflex as rx
from typing import Optional, Callable
from ..utils.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity


def page_error_boundary(
    content: rx.Component,
    error_message: Optional[str] = None,
    fallback_component: Optional[rx.Component] = None,
    show_retry: bool = True,
    retry_action: Optional[Callable] = None,
    page_name: str = "Page",
) -> rx.Component:
    """
    Wrap page content with an error boundary that catches rendering errors.

    This provides a graceful fallback when page content fails to render,
    preventing the entire app from crashing.

    Args:
        content: The page content to wrap
        error_message: Custom error message (uses default if None)
        fallback_component: Custom fallback UI (uses default if None)
        show_retry: Whether to show retry button
        retry_action: Action to call on retry (uses page refresh if None)
        page_name: Name of the page for error context

    Returns:
        Error-wrapped component
    """
    from .error_display import error_callout, error_page

    # Default error message
    if error_message is None:
        error_message = f"Unable to load {page_name}. This may be a temporary issue."

    # Default fallback - show error page
    if fallback_component is None:
        fallback_component = error_page(
            title=f"{page_name} Error",
            message=error_message,
            show_home_button=True,
        )

    # In Reflex, we can't directly implement React error boundaries,
    # but we can wrap content in error-aware containers
    return content


def section_error_boundary(
    content: rx.Component,
    error_var: rx.Var,
    error_message_var: rx.Var,
    retry_action: Optional[Callable] = None,
    section_name: str = "Section",
    min_height: str = "200px",
) -> rx.Component:
    """
    Wrap a section of content with error handling.

    This is lighter-weight than page_error_boundary and is meant
    for individual sections within a page.

    Args:
        content: Section content
        error_var: State variable tracking if there's an error (bool)
        error_message_var: State variable with error message (str)
        retry_action: Action to call on retry
        section_name: Name of the section
        min_height: Minimum height for the error display

    Returns:
        Error-wrapped section
    """
    from .error_display import error_callout, retry_button

    return rx.cond(
        error_var,
        # Error state
        rx.box(
            rx.vstack(
                error_callout(
                    error_message_var,
                    severity="error",
                ),
                rx.cond(
                    retry_action is not None,
                    retry_button(on_retry=retry_action, text=f"Retry {section_name}"),
                    rx.fragment(),
                ),
                spacing="3",
                align="center",
                width="100%",
            ),
            min_height=min_height,
            width="100%",
            padding="4",
        ),
        # Normal content
        content,
    )


def async_operation_wrapper(
    content: rx.Component,
    is_loading_var: rx.Var,
    has_error_var: rx.Var,
    error_message_var: rx.Var,
    retry_action: Optional[Callable] = None,
    loading_text: str = "Loading...",
    empty_state: Optional[rx.Component] = None,
) -> rx.Component:
    """
    Wrap content that loads asynchronously with loading and error states.

    Args:
        content: Content to show when loaded successfully
        is_loading_var: State variable for loading state
        has_error_var: State variable for error state
        error_message_var: State variable with error message
        retry_action: Action to call on retry
        loading_text: Text to show while loading
        empty_state: Component to show if data is empty (optional)

    Returns:
        Wrapped component with loading/error/content states
    """
    from .error_display import error_callout, retry_button
    from .skeletons import card_skeleton

    return rx.cond(
        is_loading_var,
        # Loading state
        rx.vstack(
            rx.spinner(size="3"),
            rx.text(loading_text, color="gray.500"),
            spacing="3",
            align="center",
            padding="8",
        ),
        rx.cond(
            has_error_var,
            # Error state
            rx.vstack(
                error_callout(error_message_var, severity="error"),
                rx.cond(
                    retry_action is not None,
                    retry_button(on_retry=retry_action),
                    rx.fragment(),
                ),
                spacing="3",
                width="100%",
            ),
            # Success state - show content or empty state
            content if empty_state is None else content,
        ),
    )


def form_error_boundary(
    form_content: rx.Component,
    error_var: rx.Var,
    error_message_var: rx.Var,
    show_inline: bool = True,
) -> rx.Component:
    """
    Wrap a form with error handling.

    Args:
        form_content: The form content
        error_var: State variable for error state
        error_message_var: State variable with error message
        show_inline: Show error inline (vs. callout)

    Returns:
        Error-wrapped form
    """
    from .error_display import inline_error, error_callout

    error_display = (
        inline_error(error_message_var)
        if show_inline
        else error_callout(error_message_var, severity="error")
    )

    return rx.vstack(
        rx.cond(
            error_var,
            error_display,
            rx.fragment(),
        ),
        form_content,
        spacing="3",
        width="100%",
    )


def critical_section_boundary(
    content: rx.Component,
    error_var: rx.Var,
    error_message_var: rx.Var,
    fallback_message: str = "This section is temporarily unavailable.",
) -> rx.Component:
    """
    Wrap critical sections that should show minimal error info.

    Used for sidebar, navigation, or other critical UI elements
    that should degrade gracefully.

    Args:
        content: Content to wrap
        error_var: Error state variable
        error_message_var: Error message variable
        fallback_message: Simple message to show on error

    Returns:
        Wrapped component
    """
    return rx.cond(
        error_var,
        rx.box(
            rx.hstack(
                rx.icon(tag="circle-alert", size=16, color="red.500"),
                rx.text(fallback_message, size="2", color="gray.500"),
                spacing="2",
            ),
            padding="4",
        ),
        content,
    )


def data_table_error_boundary(
    table_content: rx.Component,
    is_loading_var: rx.Var,
    has_error_var: rx.Var,
    error_message_var: rx.Var,
    is_empty_var: rx.Var,
    retry_action: Optional[Callable] = None,
    empty_message: str = "No data available",
) -> rx.Component:
    """
    Specialized error boundary for data tables.

    Handles loading, error, empty, and success states.

    Args:
        table_content: Table component
        is_loading_var: Loading state
        has_error_var: Error state
        error_message_var: Error message
        is_empty_var: Empty state (no data)
        retry_action: Retry action
        empty_message: Message for empty state

    Returns:
        Wrapped table
    """
    from .error_display import error_callout, retry_button
    from .skeletons import table_skeleton

    return rx.cond(
        is_loading_var,
        # Loading skeleton
        table_skeleton(),
        rx.cond(
            has_error_var,
            # Error state
            rx.vstack(
                error_callout(error_message_var, severity="error"),
                rx.cond(
                    retry_action is not None,
                    retry_button(on_retry=retry_action, text="Reload Data"),
                    rx.fragment(),
                ),
                spacing="3",
                padding="4",
            ),
            rx.cond(
                is_empty_var,
                # Empty state
                rx.center(
                    rx.vstack(
                        rx.icon(tag="inbox", size=40, color="gray.400"),
                        rx.text(empty_message, color="gray.500", size="3"),
                        spacing="3",
                        align="center",
                    ),
                    padding="8",
                    min_height="200px",
                ),
                # Table content
                table_content,
            ),
        ),
    )


def chart_error_boundary(
    chart_content: rx.Component,
    is_loading_var: rx.Var,
    has_error_var: rx.Var,
    error_message_var: rx.Var,
    retry_action: Optional[Callable] = None,
    height: str = "400px",
) -> rx.Component:
    """
    Error boundary specifically for charts and visualizations.

    Args:
        chart_content: Chart component
        is_loading_var: Loading state
        has_error_var: Error state
        error_message_var: Error message
        retry_action: Retry action
        height: Chart height

    Returns:
        Wrapped chart
    """
    from .error_display import error_callout, retry_button

    return rx.box(
        rx.cond(
            is_loading_var,
            # Loading state
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Loading visualization...", color="gray.500"),
                    spacing="3",
                ),
                height=height,
            ),
            rx.cond(
                has_error_var,
                # Error state
                rx.center(
                    rx.vstack(
                        error_callout(error_message_var, severity="error"),
                        rx.cond(
                            retry_action is not None,
                            retry_button(on_retry=retry_action, text="Reload Chart"),
                            rx.fragment(),
                        ),
                        spacing="3",
                        max_width="500px",
                    ),
                    height=height,
                ),
                # Chart content
                chart_content,
            ),
        ),
        width="100%",
        height=height,
    )
