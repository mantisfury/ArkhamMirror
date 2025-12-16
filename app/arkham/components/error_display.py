"""
Error display components for ArkhamMirror.

Provides consistent error UI across the application with
different severity levels and recovery options.
"""

import reflex as rx
from typing import Optional


def error_callout(
    message: str,
    error_id: Optional[str] = None,
    severity: str = "error",
    show_retry: bool = False,
    retry_action=None,
) -> rx.Component:
    """
    Display an error message in a callout component.

    Args:
        message: Error message to display
        error_id: Optional error ID for tracking
        severity: Severity level (error, warning, info)
        show_retry: Whether to show retry button
        retry_action: Action to call on retry

    Returns:
        Reflex callout component
    """
    # Map severity to color scheme
    color_schemes = {
        "error": "red",
        "warning": "yellow",
        "info": "blue",
        "success": "green",
    }

    icons = {
        "error": "circle-alert",
        "warning": "triangle-alert",
        "info": "info",
        "success": "circle-check",
    }

    color = color_schemes.get(severity, "red")
    icon = icons.get(severity, "circle-alert")

    content = [rx.text(message, size="2")]

    if error_id:
        content.append(
            rx.text(
                f"Error ID: {error_id}",
                size="1",
                color="gray",
                margin_top="2",
            )
        )

    if show_retry and retry_action:
        content.append(
            rx.button(
                "Retry",
                on_click=retry_action,
                size="1",
                variant="soft",
                margin_top="2",
            )
        )

    return rx.callout(
        rx.vstack(*content, spacing="1", align="start"),
        icon=icon,
        color_scheme=color,
        width="100%",
    )


def error_banner(
    message: str,
    error_id: Optional[str] = None,
    severity: str = "error",
) -> rx.Component:
    """
    Display an error as a prominent banner at the top of the page.

    Args:
        message: Error message
        error_id: Optional error ID
        severity: Severity level

    Returns:
        Banner component
    """
    color_schemes = {
        "error": "red",
        "warning": "yellow",
        "info": "blue",
    }

    return rx.box(
        rx.hstack(
            rx.icon(tag="circle-alert", size=20),
            rx.vstack(
                rx.text(message, weight="bold", size="2"),
                rx.cond(
                    error_id is not None,
                    rx.text(f"Error ID: {error_id}", size="1", color="gray"),
                    rx.fragment(),
                ),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        bg=f"{color_schemes.get(severity, 'red')}.100",
        border=f"1px solid {color_schemes.get(severity, 'red')}.300",
        border_radius="md",
        padding="4",
        width="100%",
    )


def error_page(
    title: str = "An Error Occurred",
    message: str = "Something went wrong. Please try again.",
    error_id: Optional[str] = None,
    show_home_button: bool = True,
) -> rx.Component:
    """
    Full-page error display for critical failures.

    Args:
        title: Error title
        message: Error message
        error_id: Optional error ID
        show_home_button: Whether to show "Go Home" button

    Returns:
        Full-page error component
    """
    return rx.center(
        rx.vstack(
            rx.icon(tag="circle-alert", size=60, color="red.500"),
            rx.heading(title, size="8", margin_top="4"),
            rx.text(message, size="3", color="gray.500", text_align="center"),
            rx.cond(
                error_id is not None,
                rx.code(f"Error ID: {error_id}", size="1"),
                rx.fragment(),
            ),
            rx.cond(
                show_home_button,
                rx.button(
                    rx.icon(tag="home", size=16),
                    "Go Home",
                    on_click=rx.redirect("/"),
                    size="3",
                    margin_top="4",
                ),
                rx.fragment(),
            ),
            spacing="4",
            align="center",
            max_width="500px",
        ),
        height="100vh",
        width="100%",
    )


def inline_error(
    message: str,
    size: str = "2",
) -> rx.Component:
    """
    Small inline error message for form fields.

    Args:
        message: Error message
        size: Text size

    Returns:
        Inline error component
    """
    return rx.hstack(
        rx.icon(tag="circle-alert", size=14, color="red.500"),
        rx.text(message, size=size, color="red.500"),
        spacing="1",
        align="center",
    )


def error_toast_trigger(
    error_message: str,
    error_id: Optional[str] = None,
) -> rx.Component:
    """
    Trigger a toast notification for an error.

    Note: This returns the toast content. You need to trigger it via ToastState.

    Args:
        error_message: Error message
        error_id: Optional error ID

    Returns:
        Toast content
    """
    content = error_message
    if error_id:
        content += f" (Error ID: {error_id})"

    return rx.text(content)


def loading_with_error_fallback(
    is_loading: bool,
    has_error: bool,
    error_message: str = "",
    content: rx.Component = None,
    loading_component: rx.Component = None,
) -> rx.Component:
    """
    Component that shows loading state, error state, or content.

    Args:
        is_loading: Whether currently loading
        has_error: Whether an error occurred
        error_message: Error message to display
        content: Content to show when loaded successfully
        loading_component: Custom loading component (default: spinner)

    Returns:
        Component with loading/error/content states
    """
    if loading_component is None:
        loading_component = rx.center(rx.spinner(size="3"), height="200px")

    return rx.cond(
        is_loading,
        loading_component,
        rx.cond(
            has_error,
            error_callout(error_message if error_message else "An error occurred"),
            content if content else rx.fragment(),
        ),
    )


def retry_button(
    on_retry=None,
    is_retrying: bool = False,
    text: str = "Retry",
) -> rx.Component:
    """
    Retry button for failed operations.

    Args:
        on_retry: Action to call on retry
        is_retrying: Whether currently retrying
        text: Button text

    Returns:
        Retry button component
    """
    return rx.button(
        rx.icon(tag="refresh-cw", size=16),
        text,
        on_click=on_retry,
        loading=is_retrying,
        variant="soft",
        color_scheme="blue",
    )
