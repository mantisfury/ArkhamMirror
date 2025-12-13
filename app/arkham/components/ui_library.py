"""
ArkhamMirror UI Component Library

Reusable UI components following consistent design patterns.
All components use the design tokens from design_tokens.py for consistent styling.
"""

import reflex as rx
from typing import List, Callable, Union
from .design_tokens import SPACING, RADIUS, Z_INDEX


# =============================================================================
# CARDS & CONTAINERS
# =============================================================================


def stat_card(
    title: str,
    value: Union[str, int, rx.Var],
    icon: str = None,
    color: str = "blue",
    subtitle: str = None,
    on_click: Callable = None,
) -> rx.Component:
    """
    A statistics card showing a metric with optional icon.

    Args:
        title: Label for the metric
        value: The metric value to display
        icon: Optional Lucide icon name
        color: Accent color (blue, green, red, yellow, purple, gray)
        subtitle: Optional subtitle or description
        on_click: Optional click handler

    Example:
        stat_card("Documents", 42, icon="file-text", color="blue")
    """
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.cond(
                    icon is not None,
                    rx.icon(tag=icon, size=20, color=f"{color}.9"),
                    rx.fragment(),
                ),
                rx.text(title, size="2", color="gray"),
                align="center",
                spacing="2",
            ),
            rx.heading(value, size="7", weight="bold"),
            rx.cond(
                subtitle is not None,
                rx.text(subtitle, size="1", color="gray"),
                rx.fragment(),
            ),
            spacing="1",
            align="start",
        ),
        padding=SPACING["lg"],
        cursor="pointer" if on_click else "default",
        _hover={"border_color": f"{color}.6"} if on_click else {},
        on_click=on_click,
    )


def info_card(
    title: str,
    description: str = None,
    icon: str = None,
    variant: str = "info",  # info, success, warning, error
    children: rx.Component = None,
) -> rx.Component:
    """
    An informational card with icon and optional content.

    Args:
        title: Card title
        description: Optional description text
        icon: Lucide icon name
        variant: Visual style (info, success, warning, error)
        children: Optional child components
    """
    variant_colors = {
        "info": ("blue", "blue.2"),
        "success": ("green", "green.2"),
        "warning": ("yellow", "yellow.2"),
        "error": ("red", "red.2"),
    }
    color, bg = variant_colors.get(variant, ("blue", "blue.2"))

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.cond(
                    icon is not None,
                    rx.icon(tag=icon, size=20, color=f"{color}.9"),
                    rx.fragment(),
                ),
                rx.text(title, weight="bold", size="3"),
                align="center",
                spacing="2",
            ),
            rx.cond(
                description is not None,
                rx.text(description, size="2", color="gray"),
                rx.fragment(),
            ),
            rx.cond(
                children is not None,
                children,
                rx.fragment(),
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        padding=SPACING["md"],
        background=bg,
    )


def section_card(
    title: str,
    children: rx.Component,
    icon: str = None,
    actions: rx.Component = None,
    collapsible: bool = False,
) -> rx.Component:
    """
    A section card with header, optional icon, and content area.

    Args:
        title: Section title
        children: Section content
        icon: Optional header icon
        actions: Optional action buttons in header
        collapsible: Whether the section can be collapsed
    """
    header = rx.hstack(
        rx.hstack(
            rx.cond(
                icon is not None,
                rx.icon(tag=icon, size=18),
                rx.fragment(),
            ),
            rx.heading(title, size="4"),
            align="center",
            spacing="2",
        ),
        rx.cond(
            actions is not None,
            actions,
            rx.fragment(),
        ),
        justify="between",
        width="100%",
    )

    return rx.card(
        rx.vstack(
            header,
            rx.divider(margin_y=SPACING["sm"]),
            children,
            spacing="0",
            width="100%",
        ),
        padding=SPACING["md"],
    )


# =============================================================================
# BUTTONS & ACTIONS
# =============================================================================


def action_button(
    label: str,
    icon: str = None,
    variant: str = "primary",  # primary, secondary, ghost, danger
    size: str = "2",
    loading: bool = False,
    disabled: bool = False,
    on_click: Callable = None,
) -> rx.Component:
    """
    Styled action button with optional icon and loading state.

    Args:
        label: Button text
        icon: Optional Lucide icon name
        variant: Button style (primary, secondary, ghost, danger)
        size: Button size (1, 2, 3)
        loading: Show loading spinner
        disabled: Disable the button
        on_click: Click handler
    """
    variant_map = {
        "primary": {"variant": "solid", "color_scheme": "blue"},
        "secondary": {"variant": "outline", "color_scheme": "gray"},
        "ghost": {"variant": "ghost", "color_scheme": "gray"},
        "danger": {"variant": "solid", "color_scheme": "red"},
    }
    style = variant_map.get(variant, variant_map["primary"])

    return rx.button(
        rx.cond(
            loading,
            rx.spinner(size="1"),
            rx.cond(
                icon is not None,
                rx.icon(tag=icon, size=16),
                rx.fragment(),
            ),
        ),
        label,
        size=size,
        disabled=disabled or loading,
        on_click=on_click,
        **style,
    )


def icon_button(
    icon: str,
    tooltip: str = None,
    variant: str = "ghost",
    size: str = "1",
    color_scheme: str = "gray",
    on_click: Callable = None,
) -> rx.Component:
    """
    Icon-only button with optional tooltip.

    Args:
        icon: Lucide icon name
        tooltip: Optional tooltip text
        variant: Button variant (ghost, outline, solid)
        size: Button size
        color_scheme: Color scheme
        on_click: Click handler
    """
    button = rx.icon_button(
        rx.icon(tag=icon, size=16),
        variant=variant,
        size=size,
        color_scheme=color_scheme,
        on_click=on_click,
    )

    if tooltip:
        return rx.tooltip(button, content=tooltip)
    return button


def button_group(*buttons: rx.Component) -> rx.Component:
    """
    Group multiple buttons together with consistent spacing.
    """
    return rx.hstack(
        *buttons,
        spacing="2",
    )


# =============================================================================
# FORM INPUTS
# =============================================================================


def search_input(
    value: rx.Var,
    on_change: Callable,
    placeholder: str = "Search...",
    width: str = "300px",
    debounce_ms: int = 300,
) -> rx.Component:
    """
    Search input with icon and optional clear button.

    Args:
        value: State variable for input value
        on_change: Handler for value changes
        placeholder: Placeholder text
        width: Input width
        debounce_ms: Debounce delay (for reference, actual debouncing in state)
    """
    return rx.hstack(
        rx.icon(tag="search", size=16, color="gray"),
        rx.input(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            variant="soft",
            width="100%",
        ),
        padding_x=SPACING["sm"],
        padding_y=SPACING["xs"],
        background="gray.2",
        border_radius=RADIUS["md"],
        width=width,
        align="center",
    )


def labeled_input(
    label: str,
    value: rx.Var,
    on_change: Callable,
    placeholder: str = "",
    type: str = "text",
    required: bool = False,
    helper_text: str = None,
    error: str = None,
) -> rx.Component:
    """
    Input field with label, helper text, and error display.

    Args:
        label: Field label
        value: State variable for input value
        on_change: Handler for value changes
        placeholder: Placeholder text
        type: Input type (text, email, password, number)
        required: Show required indicator
        helper_text: Optional helper text below input
        error: Error message to display
    """
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="2", weight="medium"),
            rx.cond(
                required,
                rx.text("*", color="red", size="2"),
                rx.fragment(),
            ),
            spacing="1",
        ),
        rx.input(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            type=type,
            width="100%",
            color_scheme="red" if error else None,
        ),
        rx.cond(
            error is not None and error != "",
            rx.text(error, size="1", color="red"),
            rx.cond(
                helper_text is not None,
                rx.text(helper_text, size="1", color="gray"),
                rx.fragment(),
            ),
        ),
        spacing="1",
        align="start",
        width="100%",
    )


def select_field(
    label: str,
    options: List[str],
    value: rx.Var,
    on_change: Callable,
    placeholder: str = "Select...",
    required: bool = False,
) -> rx.Component:
    """
    Select dropdown with label.

    Args:
        label: Field label
        options: List of option strings
        value: State variable for selected value
        on_change: Handler for selection changes
        placeholder: Placeholder text
        required: Show required indicator
    """
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="2", weight="medium"),
            rx.cond(
                required,
                rx.text("*", color="red", size="2"),
                rx.fragment(),
            ),
            spacing="1",
        ),
        rx.select(
            options,
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            width="100%",
        ),
        spacing="1",
        align="start",
        width="100%",
    )


# =============================================================================
# DATA DISPLAY
# =============================================================================


def data_table_header(
    title: str,
    count: Union[int, rx.Var] = None,
    actions: rx.Component = None,
) -> rx.Component:
    """
    Header for data tables with title, count badge, and actions.

    Args:
        title: Table title
        count: Optional item count to display
        actions: Optional action buttons
    """
    return rx.hstack(
        rx.hstack(
            rx.heading(title, size="4"),
            rx.cond(
                count is not None,
                rx.badge(count, variant="soft"),
                rx.fragment(),
            ),
            align="center",
            spacing="2",
        ),
        rx.cond(
            actions is not None,
            actions,
            rx.fragment(),
        ),
        justify="between",
        width="100%",
        padding_bottom=SPACING["md"],
    )


def entity_badge(
    text: str,
    entity_type: str = None,
    on_click: Callable = None,
) -> rx.Component:
    """
    Badge for displaying entity names with type-based styling.

    Args:
        text: Entity name
        entity_type: Entity type (PERSON, ORG, GPE, DATE, MONEY, etc.)
        on_click: Optional click handler
    """
    type_colors = {
        "PERSON": "blue",
        "ORG": "purple",
        "GPE": "green",
        "LOC": "green",
        "DATE": "orange",
        "MONEY": "yellow",
        "PERCENT": "yellow",
        "default": "gray",
    }
    color = type_colors.get(entity_type, type_colors["default"])

    return rx.badge(
        text,
        color_scheme=color,
        variant="soft",
        cursor="pointer" if on_click else "default",
        on_click=on_click,
    )


def severity_badge(
    severity: str,
) -> rx.Component:
    """
    Badge showing severity level with appropriate color.

    Args:
        severity: Severity level (critical, high, medium, low)
    """
    severity_colors = {
        "critical": "red",
        "high": "orange",
        "medium": "yellow",
        "low": "green",
    }
    color = severity_colors.get(severity.lower(), "gray")

    return rx.badge(
        severity.capitalize(),
        color_scheme=color,
        variant="solid",
    )


def status_badge(
    status: str,
) -> rx.Component:
    """
    Badge showing status with appropriate color.

    Args:
        status: Status text (active, pending, completed, failed, etc.)
    """
    status_colors = {
        "active": "green",
        "pending": "yellow",
        "processing": "blue",
        "completed": "green",
        "complete": "green",
        "failed": "red",
        "error": "red",
        "queued": "gray",
    }
    color = status_colors.get(status.lower(), "gray")

    return rx.badge(
        status.capitalize(),
        color_scheme=color,
        variant="soft",
    )


def progress_indicator(
    value: Union[int, float, rx.Var],
    label: str = None,
    show_percentage: bool = True,
) -> rx.Component:
    """
    Progress bar with optional label and percentage.

    Args:
        value: Progress value (0-100)
        label: Optional label
        show_percentage: Whether to show percentage text
    """
    return rx.vstack(
        rx.cond(
            label is not None,
            rx.hstack(
                rx.text(label, size="2"),
                rx.cond(
                    show_percentage,
                    rx.text(f"{value}%", size="2", color="gray"),
                    rx.fragment(),
                ),
                justify="between",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.progress(value=value, width="100%"),
        spacing="1",
        width="100%",
    )


# =============================================================================
# LAYOUT HELPERS
# =============================================================================


def empty_state(
    title: str,
    description: str = None,
    icon: str = "inbox",
    action: rx.Component = None,
) -> rx.Component:
    """
    Empty state display for when there's no data.

    Args:
        title: Empty state title
        description: Optional description
        icon: Lucide icon name
        action: Optional action button
    """
    return rx.center(
        rx.vstack(
            rx.icon(tag=icon, size=48, color="gray.6"),
            rx.heading(title, size="4", color="gray"),
            rx.cond(
                description is not None,
                rx.text(description, size="2", color="gray", text_align="center"),
                rx.fragment(),
            ),
            rx.cond(
                action is not None,
                rx.box(action, padding_top=SPACING["md"]),
                rx.fragment(),
            ),
            spacing="2",
            align="center",
            padding=SPACING["xl"],
        ),
        width="100%",
        min_height="200px",
    )


def loading_overlay(
    is_loading: rx.Var,
    children: rx.Component,
    message: str = "Loading...",
) -> rx.Component:
    """
    Overlay that shows loading spinner while content loads.

    Args:
        is_loading: State variable indicating loading state
        children: Content to display when not loading
        message: Loading message
    """
    return rx.box(
        children,
        rx.cond(
            is_loading,
            rx.box(
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text(message, size="2", color="gray"),
                        spacing="2",
                        align="center",
                    ),
                    height="100%",
                    width="100%",
                ),
                position="absolute",
                top="0",
                left="0",
                right="0",
                bottom="0",
                background="rgba(255, 255, 255, 0.8)",
                z_index=Z_INDEX["modal"],
            ),
            rx.fragment(),
        ),
        position="relative",
    )


def grid_layout(
    *children: rx.Component,
    columns: int = 3,
    gap: str = SPACING["md"],
) -> rx.Component:
    """
    Responsive grid layout.

    Args:
        *children: Child components to arrange in grid
        columns: Number of columns
        gap: Gap between items
    """
    return rx.box(
        *children,
        display="grid",
        grid_template_columns=f"repeat({columns}, 1fr)",
        gap=gap,
        width="100%",
    )


def two_column_layout(
    left: rx.Component,
    right: rx.Component,
    left_width: str = "300px",
) -> rx.Component:
    """
    Two column layout with fixed left sidebar.

    Args:
        left: Left column content
        right: Right column content (main area)
        left_width: Width of left column
    """
    return rx.hstack(
        rx.box(left, width=left_width, flex_shrink="0"),
        rx.box(right, flex="1", min_width="0"),
        spacing="4",
        width="100%",
        align="start",
    )


# =============================================================================
# FEEDBACK & NOTIFICATIONS
# =============================================================================


def alert_banner(
    message: str,
    variant: str = "info",  # info, success, warning, error
    icon: str = None,
    dismissible: bool = False,
    on_dismiss: Callable = None,
) -> rx.Component:
    """
    Alert banner for important messages.

    Args:
        message: Alert message
        variant: Alert style
        icon: Optional icon override
        dismissible: Whether alert can be dismissed
        on_dismiss: Dismiss handler
    """
    variant_config = {
        "info": {"color": "blue", "icon": "info"},
        "success": {"color": "green", "icon": "circle-check"},
        "warning": {"color": "yellow", "icon": "triangle-alert"},
        "error": {"color": "red", "icon": "circle-x"},
    }
    config = variant_config.get(variant, variant_config["info"])
    display_icon = icon or config["icon"]

    return rx.callout.root(
        rx.callout.icon(rx.icon(tag=display_icon)),
        rx.callout.text(message),
        rx.cond(
            dismissible,
            rx.icon_button(
                rx.icon(tag="x", size=14),
                variant="ghost",
                size="1",
                on_click=on_dismiss,
            ),
            rx.fragment(),
        ),
        color=config["color"],
    )


def confirmation_dialog(
    title: str,
    message: str,
    is_open: rx.Var,
    on_confirm: Callable,
    on_cancel: Callable,
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    variant: str = "danger",  # danger, warning, info
) -> rx.Component:
    """
    Confirmation dialog for destructive actions.

    Args:
        title: Dialog title
        message: Confirmation message
        is_open: State variable controlling visibility
        on_confirm: Handler for confirmation
        on_cancel: Handler for cancellation
        confirm_text: Confirm button text
        cancel_text: Cancel button text
        variant: Button style for confirm action
    """
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title(title),
            rx.alert_dialog.description(message),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button(cancel_text, variant="soft", color_scheme="gray"),
                    on_click=on_cancel,
                ),
                rx.alert_dialog.action(
                    rx.button(
                        confirm_text,
                        variant="solid",
                        color_scheme="red" if variant == "danger" else "blue",
                    ),
                    on_click=on_confirm,
                ),
                spacing="3",
                justify="end",
                padding_top=SPACING["md"],
            ),
        ),
        open=is_open,
    )


# =============================================================================
# SPECIALIZED COMPONENTS
# =============================================================================


def document_card(
    title: str,
    doc_type: str = None,
    date: str = None,
    preview: str = None,
    status: str = None,
    on_click: Callable = None,
) -> rx.Component:
    """
    Card for displaying document information.

    Args:
        title: Document title
        doc_type: Document type (pdf, docx, etc.)
        date: Document date
        preview: Text preview
        status: Document status
        on_click: Click handler
    """
    type_icons = {
        "pdf": "file-text",
        "docx": "file-text",
        "doc": "file-text",
        "txt": "file",
        "eml": "mail",
        "msg": "mail",
        "image": "image",
        "default": "file",
    }
    icon = type_icons.get(doc_type, type_icons["default"])

    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon, size=20, color="blue.9"),
                rx.vstack(
                    rx.text(title, weight="medium", size="2"),
                    rx.cond(
                        date is not None,
                        rx.text(date, size="1", color="gray"),
                        rx.fragment(),
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                rx.cond(
                    status is not None,
                    status_badge(status),
                    rx.fragment(),
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                preview is not None,
                rx.text(preview, size="1", color="gray", no_of_lines=2),
                rx.fragment(),
            ),
            spacing="2",
            width="100%",
        ),
        padding=SPACING["md"],
        cursor="pointer" if on_click else "default",
        _hover={"border_color": "blue.6"} if on_click else {},
        on_click=on_click,
    )


def entity_relationship_badge(
    entity1: str,
    entity2: str,
    relationship: str = None,
) -> rx.Component:
    """
    Badge showing relationship between two entities.

    Args:
        entity1: First entity name
        entity2: Second entity name
        relationship: Optional relationship type
    """
    return rx.hstack(
        rx.badge(entity1, color_scheme="blue", variant="soft"),
        rx.cond(
            relationship is not None,
            rx.text(f"—{relationship}→", size="1", color="gray"),
            rx.icon(tag="arrow-right", size=12, color="gray"),
        ),
        rx.badge(entity2, color_scheme="purple", variant="soft"),
        spacing="1",
        align="center",
    )
