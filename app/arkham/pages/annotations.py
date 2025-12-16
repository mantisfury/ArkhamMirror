"""
Annotation System Page

Manage notes, tags, and annotations across the investigation.
"""

import reflex as rx
from app.arkham.state.annotation_state import AnnotationState
from app.arkham.components.sidebar import sidebar


def stat_card(label: str, value, icon: str, color: str = "blue") -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=20, color=f"var(--{color}-9)"),
                rx.text(label, size="2", color="gray"),
                spacing="2",
            ),
            rx.heading(value, size="6"),
            align_items="start",
            spacing="1",
        ),
        padding="4",
    )


def priority_badge(priority: str) -> rx.Component:
    """Badge showing priority level."""
    return rx.badge(
        priority.title(),
        color_scheme=rx.match(
            priority,
            ("high", "red"),
            ("low", "gray"),
            "yellow",
        ),
        size="1",
    )


def status_badge(status: str) -> rx.Component:
    """Badge showing status."""
    return rx.badge(
        status.replace("_", " ").title(),
        color_scheme=rx.match(
            status,
            ("open", "blue"),
            ("in_progress", "yellow"),
            ("resolved", "green"),
            ("archived", "gray"),
            "gray",
        ),
        size="1",
        variant="soft",
    )


def type_badge(target_type: str) -> rx.Component:
    """Badge showing target type."""
    return rx.badge(
        target_type.title(),
        variant="outline",
        size="1",
    )


def annotation_card(annotation) -> rx.Component:
    """Card displaying an annotation."""
    return rx.card(
        rx.cond(
            AnnotationState.editing_id == annotation.id,
            # Edit mode
            rx.vstack(
                rx.text_area(
                    value=AnnotationState.edit_note,
                    on_change=AnnotationState.set_edit_note,
                    width="100%",
                    min_height="80px",
                ),
                rx.hstack(
                    rx.select(
                        ["high", "medium", "low"],
                        value=AnnotationState.edit_priority,
                        on_change=AnnotationState.set_edit_priority,
                        size="1",
                    ),
                    rx.select(
                        ["open", "in_progress", "resolved", "archived"],
                        value=AnnotationState.edit_status,
                        on_change=AnnotationState.set_edit_status,
                        size="1",
                    ),
                    rx.spacer(),
                    rx.button("Save", size="1", on_click=AnnotationState.save_edit),
                    rx.button(
                        "Cancel",
                        size="1",
                        variant="ghost",
                        on_click=AnnotationState.cancel_edit,
                    ),
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            # View mode
            rx.vstack(
                rx.hstack(
                    type_badge(annotation.target_type),
                    rx.text(f"#{annotation.target_id}", size="1", color="gray"),
                    rx.spacer(),
                    priority_badge(annotation.priority),
                    status_badge(annotation.status),
                    width="100%",
                ),
                rx.text(annotation.note, size="2"),
                rx.cond(
                    annotation.tags.length() > 0,
                    rx.hstack(
                        rx.foreach(
                            annotation.tags,
                            lambda t: rx.badge(
                                t, size="1", variant="soft", color_scheme="purple"
                            ),
                        ),
                        spacing="1",
                        wrap="wrap",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.text(annotation.created_at, size="1", color="gray"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("pencil", size=12),
                        size="1",
                        variant="ghost",
                        on_click=lambda: AnnotationState.start_edit(annotation.id),
                    ),
                    rx.button(
                        rx.icon("trash-2", size=12),
                        size="1",
                        variant="ghost",
                        color_scheme="red",
                        on_click=lambda: AnnotationState.delete_annotation(
                            annotation.id
                        ),
                    ),
                    width="100%",
                ),
                spacing="2",
                align_items="start",
                width="100%",
            ),
        ),
        padding="4",
    )


def new_annotation_form() -> rx.Component:
    """Form for adding new annotation."""
    return rx.card(
        rx.vstack(
            rx.heading("New Annotation", size="4"),
            rx.divider(),
            rx.hstack(
                rx.vstack(
                    rx.text("Target Type", size="1", weight="bold"),
                    rx.select(
                        ["document", "entity", "relationship", "chunk"],
                        value=AnnotationState.new_target_type,
                        on_change=AnnotationState.set_new_target_type,
                    ),
                    spacing="1",
                    width="50%",
                ),
                rx.vstack(
                    rx.text("Target ID", size="1", weight="bold"),
                    rx.input(
                        placeholder="ID (optional)",
                        value=AnnotationState.new_target_id,
                        on_change=AnnotationState.set_new_target_id,
                    ),
                    spacing="1",
                    width="50%",
                ),
                width="100%",
            ),
            rx.vstack(
                rx.text("Note", size="1", weight="bold"),
                rx.text_area(
                    placeholder="Enter your note...",
                    value=AnnotationState.new_note,
                    on_change=AnnotationState.set_new_note,
                    width="100%",
                    min_height="100px",
                ),
                spacing="1",
                width="100%",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Priority", size="1", weight="bold"),
                    rx.select(
                        ["high", "medium", "low"],
                        value=AnnotationState.new_priority,
                        on_change=AnnotationState.set_new_priority,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Tags (comma-separated)", size="1", weight="bold"),
                    rx.input(
                        placeholder="tag1, tag2, tag3",
                        value=AnnotationState.new_tags,
                        on_change=AnnotationState.set_new_tags,
                        width="200px",
                    ),
                    spacing="1",
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("plus", size=14),
                    "Add Annotation",
                    on_click=AnnotationState.add_annotation,
                ),
                rx.button(
                    "Cancel",
                    variant="ghost",
                    on_click=AnnotationState.toggle_form,
                ),
                spacing="2",
            ),
            spacing="4",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def annotations_page() -> rx.Component:
    """Main Annotations page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Annotations", size="8"),
                    rx.text(
                        "Notes, tags, and observations for your investigation.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("plus", size=14),
                    "New Annotation",
                    on_click=AnnotationState.toggle_form,
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card("Total", AnnotationState.total_count, "sticky-note", "blue"),
                stat_card("Open", AnnotationState.open_count, "circle-dot", "yellow"),
                stat_card(
                    "High Priority",
                    AnnotationState.high_priority_count,
                    "circle-alert",
                    "red",
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            # New annotation form
            rx.cond(
                AnnotationState.show_form,
                new_annotation_form(),
                rx.fragment(),
            ),
            # Filters
            rx.hstack(
                rx.select(
                    ["all", "open", "in_progress", "resolved", "archived"],
                    placeholder="Status",
                    value=AnnotationState.filter_status,
                    on_change=AnnotationState.set_filter_status,
                    size="1",
                ),
                rx.select(
                    ["all", "high", "medium", "low"],
                    placeholder="Priority",
                    value=AnnotationState.filter_priority,
                    on_change=AnnotationState.set_filter_priority,
                    size="1",
                ),
                rx.select(
                    ["all", "document", "entity", "relationship", "chunk"],
                    placeholder="Type",
                    value=AnnotationState.filter_type,
                    on_change=AnnotationState.set_filter_type,
                    size="1",
                ),
                rx.cond(
                    AnnotationState.all_tags.length() > 0,
                    rx.hstack(
                        rx.text("Tags:", size="1", color="gray"),
                        rx.foreach(
                            AnnotationState.all_tags,
                            lambda t: rx.badge(t, size="1", variant="outline"),
                        ),
                        spacing="1",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
                wrap="wrap",
            ),
            # Annotations list
            rx.cond(
                AnnotationState.is_loading,
                rx.center(
                    rx.spinner(size="3"),
                    padding="8",
                ),
                rx.cond(
                    AnnotationState.annotations.length() > 0,
                    rx.vstack(
                        rx.foreach(AnnotationState.annotations, annotation_card),
                        spacing="3",
                        width="100%",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text(
                                "No annotations yet.",
                                weight="medium",
                            ),
                            rx.text(
                                "Add notes, tags, and observations to track your investigation progress.",
                                size="2",
                            ),
                            align_items="start",
                            spacing="1",
                        ),
                        icon="sticky-note",
                    ),
                ),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=AnnotationState.load_annotations,
        ),
        width="100%",
        height="100vh",
    )
