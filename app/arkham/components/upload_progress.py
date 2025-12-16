"""
Upload Progress Component

Displays real-time progress for documents being processed through the pipeline.
Shows stage indicators and progress bars for each active upload.
"""

import reflex as rx
from .design_tokens import SPACING, FONT_SIZE


def stage_badge(stage) -> rx.Component:
    """Stage indicator badge with color coding."""
    return rx.match(
        stage,
        ("uploaded", rx.badge("Queued", color_scheme="gray", variant="soft")),
        ("splitting", rx.badge("Splitting", color_scheme="blue", variant="soft")),
        ("ocr", rx.badge("OCR", color_scheme="cyan", variant="soft")),
        ("parsing", rx.badge("Parsing", color_scheme="violet", variant="soft")),
        ("embedding", rx.badge("Embedding", color_scheme="purple", variant="soft")),
        ("complete", rx.badge("Complete", color_scheme="green", variant="soft")),
        ("failed", rx.badge("Failed", color_scheme="red", variant="soft")),
        rx.badge(stage, color_scheme="gray", variant="soft"),  # default
    )


def progress_item(upload: dict) -> rx.Component:
    """Individual upload progress item with progress bar and details."""
    return rx.card(
        rx.vstack(
            # Header row: title + stage badge
            rx.hstack(
                rx.vstack(
                    rx.text(
                        upload["title"],
                        font_weight="600",
                        font_size=FONT_SIZE["sm"],
                    ),
                    rx.text(
                        f"ID: {upload['doc_id']} | {upload['num_pages']} pages",
                        font_size=FONT_SIZE["xs"],
                        color="gray.11",
                    ),
                    spacing=SPACING["xs"],
                    align_items="start",
                    flex="1",
                ),
                stage_badge(upload["stage"]),
                justify="between",
                width="100%",
            ),

            # Progress bar
            rx.vstack(
                rx.progress(
                    value=upload["progress_pct"],
                    width="100%",
                    color_scheme=rx.cond(
                        upload["stage"] == "failed",
                        "red",
                        rx.cond(
                            upload["stage"] == "complete",
                            "green",
                            "blue"
                        )
                    ),
                ),
                rx.text(
                    f"{upload['progress_pct']}% - {upload['details']}",
                    font_size=FONT_SIZE["xs"],
                    color="gray.10",
                ),
                spacing=SPACING["xs"],
                width="100%",
            ),

            spacing=SPACING["sm"],
            width="100%",
        ),
        padding=SPACING["sm"],
        margin_bottom=SPACING["xs"],
    )


def upload_progress_panel() -> rx.Component:
    """
    Collapsible panel showing progress for all active uploads.

    Displays:
    - Progress bars for each document
    - Stage indicators (Splitting, OCR, Parsing, Embedding)
    - Detailed progress text (e.g., "OCR progress: 5/10 pages")
    - Empty state when no active uploads
    """
    from .file_upload import UploadState

    return rx.cond(
        UploadState.show_progress_panel,
        rx.card(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.heading(
                        "Upload Progress",
                        size="5",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.icon("refresh-cw", size=16),
                            on_click=UploadState.refresh_active_uploads,
                            size="1",
                            variant="soft",
                        ),
                        rx.button(
                            rx.icon("chevron-up", size=16),
                            on_click=UploadState.toggle_progress_panel,
                            size="1",
                            variant="ghost",
                        ),
                        spacing=SPACING["xs"],
                    ),
                    justify="between",
                    width="100%",
                ),

                # Progress list or empty state
                rx.cond(
                    UploadState.active_uploads.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            UploadState.active_uploads,
                            progress_item,
                        ),
                        width="100%",
                        spacing=SPACING["xs"],
                    ),
                    rx.box(
                        rx.text(
                            "No active uploads. Files will appear here after upload.",
                            font_size=FONT_SIZE["sm"],
                            color="gray.11",
                            text_align="center",
                        ),
                        padding=SPACING["lg"],
                    ),
                ),

                spacing=SPACING["md"],
                width="100%",
            ),
            padding=SPACING["md"],
            margin_top=SPACING["md"],
        ),
        # Collapsed state - just a button to expand
        rx.button(
            rx.hstack(
                rx.icon("chevron-down", size=16),
                rx.text("Show Upload Progress", font_size=FONT_SIZE["sm"]),
                rx.badge(
                    UploadState.active_uploads.length(),
                    color_scheme="blue",
                    variant="solid",
                ),
                spacing=SPACING["xs"],
            ),
            on_click=UploadState.toggle_progress_panel,
            variant="soft",
            size="2",
            margin_top=SPACING["md"],
        ),
    )
