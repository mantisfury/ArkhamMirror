"""Reusable pagination component for lists."""

import reflex as rx
from .design_tokens import SPACING, FONT_SIZE


def create_pagination_controls(
    current_page: rx.Var,
    total_pages: rx.Var,
    total_items: rx.Var,
    has_previous: rx.Var,
    has_next: rx.Var,
    on_prev: callable,
    on_next: callable,
    items_label: str = "items",
) -> rx.Component:
    """
    Create a reusable pagination control bar.

    Args:
        current_page: State variable for current page number
        total_pages: State variable for total pages
        total_items: State variable for total item count
        has_previous: State variable (bool) if previous page exists
        has_next: State variable (bool) if next page exists
        on_prev: Event handler for previous button
        on_next: Event handler for next button
        items_label: Label for the items (e.g., "anomalies", "documents")

    Returns:
        Pagination controls component
    """
    return rx.hstack(
        rx.button(
            rx.icon(tag="chevron_left", size=16),
            "Previous",
            on_click=on_prev,
            disabled=~has_previous,
            size="2",
            variant="soft",
        ),
        rx.text(
            f"Page {current_page} of {total_pages}",
            font_size=FONT_SIZE["sm"],
            color="gray.11",
        ),
        rx.button(
            "Next",
            rx.icon(tag="chevron_right", size=16),
            on_click=on_next,
            disabled=~has_next,
            size="2",
            variant="soft",
        ),
        rx.spacer(),
        rx.text(
            f"{total_items} total {items_label}",
            font_size=FONT_SIZE["sm"],
            color="gray.11",
        ),
        align="center",
        justify="center",
        spacing=SPACING["md"],
        width="100%",
        padding_top=SPACING["md"],
    )


def simple_pagination(
    current_page: rx.Var,
    total_pages: rx.Var,
    on_prev: callable,
    on_next: callable,
    has_previous: rx.Var,
    has_next: rx.Var,
) -> rx.Component:
    """
    Minimal pagination with just prev/next buttons.
    """
    return rx.hstack(
        rx.button(
            rx.icon(tag="chevron_left", size=16),
            on_click=on_prev,
            disabled=~has_previous,
            size="1",
            variant="ghost",
        ),
        rx.text(
            f"{current_page} / {total_pages}",
            font_size=FONT_SIZE["xs"],
            color="gray.10",
        ),
        rx.button(
            rx.icon(tag="chevron_right", size=16),
            on_click=on_next,
            disabled=~has_next,
            size="1",
            variant="ghost",
        ),
        align="center",
        spacing=SPACING["xs"],
    )
