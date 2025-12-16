"""Confirmation dialog component for destructive actions."""

import reflex as rx
from .design_tokens import SPACING


def confirmation_dialog(
    is_open: rx.Var,
    title: rx.Var,
    message: rx.Var,
    on_confirm: callable,
    on_cancel: callable,
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    confirm_color: str = "red",
) -> rx.Component:
    """
    Create a confirmation dialog for destructive actions.

    Args:
        is_open: State variable controlling dialog visibility
        title: Dialog title text (state var)
        message: Dialog message text (state var)
        on_confirm: Event handler called when user confirms
        on_cancel: Event handler called when user cancels
        confirm_text: Text for confirm button
        cancel_text: Text for cancel button
        confirm_color: Color scheme for confirm button

    Returns:
        Confirmation dialog component
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(title),
            rx.dialog.description(
                message,
                size="2",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        cancel_text,
                        variant="soft",
                        color_scheme="gray",
                        on_click=on_cancel,
                    ),
                ),
                rx.dialog.close(
                    rx.button(
                        confirm_text,
                        color_scheme=confirm_color,
                        on_click=on_confirm,
                    ),
                ),
                spacing=SPACING["sm"],
                justify="end",
                width="100%",
                padding_top=SPACING["md"],
            ),
            max_width="450px",
        ),
        open=is_open,
    )


def danger_confirmation_dialog(
    is_open: rx.Var,
    title: rx.Var,
    message: rx.Var,
    on_confirm: callable,
    on_cancel: callable,
) -> rx.Component:
    """
    Create a danger/destructive confirmation dialog with red styling.
    """
    return confirmation_dialog(
        is_open=is_open,
        title=title,
        message=message,
        on_confirm=on_confirm,
        on_cancel=on_cancel,
        confirm_text="Delete",
        cancel_text="Cancel",
        confirm_color="red",
    )
