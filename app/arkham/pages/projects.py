"""
Project/Case Management Page

Organize investigations into projects and cases.
"""

import reflex as rx
from app.arkham.state.project_state import ProjectState
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
    return rx.badge(
        status.title(),
        color_scheme=rx.match(
            status,
            ("active", "green"),
            ("completed", "blue"),
            ("archived", "gray"),
            "gray",
        ),
        variant="soft",
        size="1",
    )


def color_dot(color: str) -> rx.Component:
    return rx.box(
        width="12px",
        height="12px",
        border_radius="full",
        bg=f"var(--{color}-9)",
    )


def project_card(project) -> rx.Component:
    """Card showing a project."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                color_dot(project.color),
                rx.text(project.name, weight="bold", size="3"),
                rx.spacer(),
                priority_badge(project.priority),
                status_badge(project.status),
                width="100%",
            ),
            rx.cond(
                project.description != "",
                rx.text(
                    project.description,
                    size="2",
                    color="gray",
                    no_of_lines=2,
                ),
                rx.fragment(),
            ),
            rx.hstack(
                rx.badge(f"{project.document_count} docs", size="1", variant="outline"),
                rx.cond(
                    project.tags.length() > 0,
                    rx.hstack(
                        rx.foreach(
                            project.tags,
                            lambda t: rx.badge(
                                t, size="1", variant="soft", color_scheme="purple"
                            ),
                        ),
                        spacing="1",
                    ),
                    rx.fragment(),
                ),
                rx.spacer(),
                rx.text(project.updated_at, size="1", color="gray"),
                width="100%",
            ),
            spacing="2",
            align_items="start",
            width="100%",
        ),
        padding="4",
        cursor="pointer",
        on_click=lambda: ProjectState.select_project(project.id),
        _hover={"bg": "var(--gray-a3)"},
    )


def new_project_form() -> rx.Component:
    """Form for creating a new project."""
    return rx.card(
        rx.vstack(
            rx.heading("New Project", size="4"),
            rx.divider(),
            rx.vstack(
                rx.text("Name", size="1", weight="bold"),
                rx.input(
                    placeholder="Project name",
                    value=ProjectState.new_name,
                    on_change=ProjectState.set_new_name,
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
            rx.vstack(
                rx.text("Description", size="1", weight="bold"),
                rx.text_area(
                    placeholder="Project description",
                    value=ProjectState.new_description,
                    on_change=ProjectState.set_new_description,
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Priority", size="1", weight="bold"),
                    rx.select(
                        ["high", "medium", "low"],
                        value=ProjectState.new_priority,
                        on_change=ProjectState.set_new_priority,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Color", size="1", weight="bold"),
                    rx.select(
                        ["blue", "green", "red", "yellow", "purple", "orange", "gray"],
                        value=ProjectState.new_color,
                        on_change=ProjectState.set_new_color,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Tags (comma-separated)", size="1", weight="bold"),
                    rx.input(
                        placeholder="tag1, tag2",
                        value=ProjectState.new_tags,
                        on_change=ProjectState.set_new_tags,
                    ),
                    spacing="1",
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("plus", size=14),
                    "Create Project",
                    on_click=ProjectState.create_project,
                ),
                rx.button(
                    "Cancel",
                    variant="ghost",
                    on_click=ProjectState.toggle_form,
                ),
                spacing="2",
            ),
            spacing="4",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def project_details() -> rx.Component:
    """Details panel for selected project."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.button(
                    rx.icon("arrow-left", size=14),
                    "Back",
                    variant="ghost",
                    on_click=ProjectState.close_details,
                ),
                rx.spacer(),
                rx.cond(
                    ProjectState.editing,
                    rx.hstack(
                        rx.button(
                            "Save",
                            size="1",
                            on_click=ProjectState.save_edit,
                        ),
                        rx.button(
                            "Cancel",
                            size="1",
                            variant="ghost",
                            on_click=ProjectState.cancel_edit,
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.icon("pencil", size=14),
                            "Edit",
                            size="1",
                            variant="soft",
                            on_click=ProjectState.start_edit,
                        ),
                        rx.button(
                            rx.icon("trash-2", size=14),
                            size="1",
                            variant="ghost",
                            color_scheme="red",
                            on_click=ProjectState.delete_project,
                        ),
                        spacing="2",
                    ),
                ),
                width="100%",
            ),
            rx.divider(),
            rx.cond(
                ProjectState.current_project is not None,
                rx.cond(
                    ProjectState.editing,
                    # Edit mode
                    rx.vstack(
                        rx.input(
                            value=ProjectState.edit_name,
                            on_change=ProjectState.set_edit_name,
                            width="100%",
                        ),
                        rx.text_area(
                            value=ProjectState.edit_description,
                            on_change=ProjectState.set_edit_description,
                            width="100%",
                        ),
                        rx.hstack(
                            rx.select(
                                ["high", "medium", "low"],
                                value=ProjectState.edit_priority,
                                on_change=ProjectState.set_edit_priority,
                            ),
                            rx.select(
                                ["active", "completed", "archived"],
                                value=ProjectState.edit_status,
                                on_change=ProjectState.set_edit_status,
                            ),
                            spacing="2",
                        ),
                        rx.text_area(
                            placeholder="Project notes...",
                            value=ProjectState.edit_notes,
                            on_change=ProjectState.set_edit_notes,
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    # View mode
                    rx.vstack(
                        rx.hstack(
                            color_dot(ProjectState.current_project.color),
                            rx.heading(ProjectState.current_project.name, size="5"),
                            rx.spacer(),
                            priority_badge(ProjectState.current_project.priority),
                            status_badge(ProjectState.current_project.status),
                            width="100%",
                        ),
                        rx.cond(
                            ProjectState.current_project.description != "",
                            rx.text(
                                ProjectState.current_project.description,
                                size="2",
                                color="gray",
                            ),
                            rx.fragment(),
                        ),
                        rx.divider(),
                        rx.heading("Documents", size="4"),
                        rx.cond(
                            ProjectState.project_documents.length() > 0,
                            rx.vstack(
                                rx.foreach(
                                    ProjectState.project_documents,
                                    lambda d: rx.hstack(
                                        rx.icon("file-text", size=14),
                                        rx.text(d.filename, size="2"),
                                        rx.badge(
                                            d.file_type, size="1", variant="outline"
                                        ),
                                        spacing="2",
                                    ),
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            rx.text(
                                "No documents in this project", size="2", color="gray"
                            ),
                        ),
                        spacing="4",
                        align_items="start",
                        width="100%",
                    ),
                ),
                rx.text("Loading..."),
            ),
            spacing="4",
            width="100%",
        ),
        padding="4",
        width="100%",
    )


def projects_page() -> rx.Component:
    """Main Projects page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Projects", size="8"),
                    rx.text(
                        "Organize your investigations into projects and cases.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("folder-plus", size=14),
                    "New Project",
                    on_click=ProjectState.toggle_form,
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card(
                    "Total Projects", ProjectState.total_projects, "folder", "blue"
                ),
                stat_card("Active", ProjectState.active_count, "folder-open", "green"),
                stat_card(
                    "High Priority",
                    ProjectState.high_priority_count,
                    "circle-alert",
                    "red",
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            # New project form
            rx.cond(
                ProjectState.show_form,
                new_project_form(),
                rx.fragment(),
            ),
            # Content
            rx.cond(
                ProjectState.show_details,
                project_details(),
                rx.vstack(
                    # Filters
                    rx.hstack(
                        rx.select(
                            ["all", "active", "completed", "archived"],
                            placeholder="Status",
                            value=ProjectState.filter_status,
                            on_change=ProjectState.set_filter_status,
                            size="1",
                        ),
                        rx.select(
                            ["all", "high", "medium", "low"],
                            placeholder="Priority",
                            value=ProjectState.filter_priority,
                            on_change=ProjectState.set_filter_priority,
                            size="1",
                        ),
                        spacing="2",
                    ),
                    # Project list
                    rx.cond(
                        ProjectState.is_loading,
                        rx.center(
                            rx.spinner(size="3"),
                            padding="8",
                        ),
                        rx.cond(
                            ProjectState.projects.length() > 0,
                            rx.grid(
                                rx.foreach(ProjectState.projects, project_card),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            rx.callout(
                                rx.vstack(
                                    rx.text("No projects yet.", weight="medium"),
                                    rx.text(
                                        "Create a project to organize your investigation documents.",
                                        size="2",
                                    ),
                                    align_items="start",
                                    spacing="1",
                                ),
                                icon="folder",
                            ),
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=ProjectState.load_projects,
        ),
        width="100%",
        height="100vh",
    )
