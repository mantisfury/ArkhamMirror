"""
Upload History Page

View and manage document upload history.
"""

import reflex as rx
from app.arkham.state.upload_history_state import UploadHistoryState
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


def status_badge(status: str) -> rx.Component:
    """Status badge with color coding."""
    return rx.badge(
        status.title(),
        color_scheme=rx.match(
            status,
            ("completed", "green"),
            ("failed", "red"),
            ("processing", "blue"),
            ("pending", "yellow"),
            "gray",
        ),
        size="1",
    )


def format_size(size: int) -> str:
    """Format file size for display."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size // 1024} KB"
    else:
        return f"{size // (1024 * 1024)} MB"


def upload_row(upload) -> rx.Component:
    """Row showing an upload record."""
    return rx.hstack(
        rx.icon(
            rx.match(
                upload.status,
                ("completed", "circle-check"),
                ("failed", "circle-x"),
                ("processing", "loader"),
                "clock",
            ),
            size=16,
            color=rx.match(
                upload.status,
                ("completed", "var(--green-9)"),
                ("failed", "var(--red-9)"),
                ("processing", "var(--blue-9)"),
                "var(--yellow-9)",
            ),
        ),
        rx.vstack(
            rx.text(upload.filename, weight="medium", size="2"),
            rx.hstack(
                rx.badge(upload.file_type, size="1", variant="outline"),
                rx.text(
                    rx.cond(
                        upload.file_size > 1024 * 1024,
                        f"{upload.file_size // (1024 * 1024)} MB",
                        rx.cond(
                            upload.file_size > 1024,
                            f"{upload.file_size // 1024} KB",
                            f"{upload.file_size} B",
                        ),
                    ),
                    size="1",
                    color="gray",
                ),
                spacing="2",
            ),
            align_items="start",
            spacing="1",
        ),
        rx.spacer(),
        status_badge(upload.status),
        rx.text(upload.uploaded_at, size="1", color="gray"),
        rx.button(
            rx.icon("trash-2", size=12),
            variant="ghost",
            size="1",
            color_scheme="red",
            on_click=lambda: UploadHistoryState.delete_record(upload.id),
        ),
        width="100%",
        padding="3",
        border_bottom="1px solid var(--gray-4)",
        align_items="center",
    )


def upload_history_page() -> rx.Component:
    """Main Upload History page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Upload History", size="8"),
                    rx.text(
                        "Track and manage document uploads.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("trash", size=14),
                    "Clear Old",
                    variant="ghost",
                    size="1",
                    on_click=UploadHistoryState.clear_old,
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card(
                    "Total Uploads", UploadHistoryState.total_uploads, "upload", "blue"
                ),
                stat_card(
                    "Completed",
                    UploadHistoryState.completed_count,
                    "circle-check",
                    "green",
                ),
                stat_card("Failed", UploadHistoryState.failed_count, "circle-x", "red"),
                stat_card(
                    "Total Size",
                    UploadHistoryState.formatted_size,
                    "hard-drive",
                    "purple",
                ),
                columns="4",
                spacing="4",
                width="100%",
            ),
            # Filter and list
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Uploads", size="4"),
                        rx.spacer(),
                        rx.select(
                            ["all", "pending", "processing", "completed", "failed"],
                            placeholder="Filter by status",
                            value=UploadHistoryState.filter_status,
                            on_change=UploadHistoryState.set_filter_status,
                            size="1",
                        ),
                        rx.button(
                            rx.icon("refresh-cw", size=14),
                            "Refresh",
                            variant="ghost",
                            size="1",
                            on_click=UploadHistoryState.load_history,
                        ),
                        width="100%",
                    ),
                    rx.divider(),
                    rx.cond(
                        UploadHistoryState.is_loading,
                        rx.center(
                            rx.spinner(size="3"),
                            padding="8",
                        ),
                        rx.cond(
                            UploadHistoryState.uploads.length() > 0,
                            rx.vstack(
                                rx.foreach(
                                    UploadHistoryState.uploads,
                                    upload_row,
                                ),
                                spacing="0",
                                width="100%",
                                max_height="500px",
                                overflow_y="auto",
                            ),
                            rx.center(
                                rx.vstack(
                                    rx.icon("inbox", size=32, color="var(--gray-7)"),
                                    rx.text(
                                        "No upload history",
                                        size="2",
                                        color="gray",
                                    ),
                                    spacing="2",
                                ),
                                padding="8",
                            ),
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                padding="4",
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=UploadHistoryState.load_history,
        ),
        width="100%",
        height="100vh",
    )
