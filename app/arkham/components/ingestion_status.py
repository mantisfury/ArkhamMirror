import reflex as rx
from ..state.ingestion_status_state import IngestionStatusState
from .design_tokens import SPACING, FONT_SIZE, Z_INDEX
from .confirmation_dialog import confirmation_dialog


def document_modal(
    show_var,
    title: str,
    documents_var,
    bulk_action_button=None,
    action_buttons_fn=None,
) -> rx.Component:
    """Reusable modal for displaying document lists with actions."""

    # Build the card content based on whether we have action buttons
    def card_content(doc):
        base_content = [
            rx.hstack(
                rx.vstack(
                    rx.text(
                        doc["title"],
                        font_weight="600",
                        font_size=FONT_SIZE["sm"],
                    ),
                    rx.text(
                        f"ID: {doc['id']} | Pages: {doc['num_pages']}",
                        font_size=FONT_SIZE["xs"],
                        color="gray.11",
                    ),
                    spacing=SPACING["xs"],
                    align_items="start",
                    flex="1",
                ),
                rx.badge(
                    doc["status"],
                    color_scheme=rx.cond(
                        doc["status"] == "complete",
                        "green",
                        rx.cond(
                            doc["status"] == "processing",
                            "blue",
                            rx.cond(doc["status"] == "failed", "red", "gray"),
                        ),
                    ),
                ),
                justify="between",
                width="100%",
            ),
        ]

        # Add action buttons if provided
        if action_buttons_fn is not None:
            base_content.append(action_buttons_fn(doc))

        return rx.vstack(
            *base_content,
            spacing=SPACING["sm"],
            width="100%",
        )

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.dialog.title(title),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x", size=18),
                            on_click=IngestionStatusState.close_modals,
                            variant="soft",
                            color_scheme="gray",
                            size="1",
                        )
                    ),
                    justify="between",
                    width="100%",
                ),
                # Bulk action button (if provided)
                rx.cond(
                    bulk_action_button is not None,
                    bulk_action_button,
                    rx.box(),
                ),
                # Document list
                rx.cond(
                    documents_var.length() > 0,
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                documents_var,
                                lambda doc: rx.card(
                                    card_content(doc),
                                    padding=SPACING["sm"],
                                    margin_bottom=SPACING["xs"],
                                ),
                            ),
                            width="100%",
                            spacing=SPACING["xs"],
                        ),
                        height="500px",
                        scrollbars="vertical",
                    ),
                    rx.text(
                        "No documents found.",
                        color="gray.11",
                        font_size=FONT_SIZE["sm"],
                        padding=SPACING["lg"],
                    ),
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            max_width="600px",
            padding=SPACING["lg"],
        ),
        open=show_var,
    )


def document_detail_modal() -> rx.Component:
    """Phase 2.3: Modal for viewing document details."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.dialog.title("Document Details"),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x", size=18),
                            on_click=IngestionStatusState.close_modals,
                            variant="soft",
                            color_scheme="gray",
                            size="1",
                        )
                    ),
                    justify="between",
                    width="100%",
                ),
                # Document information
                rx.scroll_area(
                    rx.vstack(
                        # Title and status
                        rx.card(
                            rx.vstack(
                                rx.text(
                                    "Title",
                                    font_size=FONT_SIZE["xs"],
                                    color="gray.10",
                                    font_weight="600",
                                ),
                                rx.text(
                                    IngestionStatusState.selected_document["title"],
                                    font_size=FONT_SIZE["sm"],
                                ),
                                rx.hstack(
                                    rx.badge(
                                        IngestionStatusState.selected_document[
                                            "status"
                                        ],
                                        color_scheme="blue",
                                    ),
                                    rx.badge(
                                        IngestionStatusState.selected_document[
                                            "doc_type"
                                        ],
                                        color_scheme="purple",
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                spacing=SPACING["xs"],
                                width="100%",
                            ),
                            padding=SPACING["sm"],
                        ),
                        # File information
                        rx.card(
                            rx.vstack(
                                rx.text(
                                    "File Information",
                                    font_size=FONT_SIZE["sm"],
                                    font_weight="600",
                                    margin_bottom=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "ID:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document["id"],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Path:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document["path"],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Uploaded:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document[
                                            "created_at"
                                        ],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Size:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document[
                                            "file_size"
                                        ],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                spacing=SPACING["xs"],
                                width="100%",
                            ),
                            padding=SPACING["sm"],
                        ),
                        # Processing breakdown
                        rx.card(
                            rx.vstack(
                                rx.text(
                                    "Processing Breakdown",
                                    font_size=FONT_SIZE["sm"],
                                    font_weight="600",
                                    margin_bottom=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Pages:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document[
                                            "num_pages"
                                        ],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Chunks:",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    rx.text(
                                        IngestionStatusState.selected_document[
                                            "chunk_count"
                                        ],
                                        font_size=FONT_SIZE["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                ),
                                spacing=SPACING["xs"],
                                width="100%",
                            ),
                            padding=SPACING["sm"],
                        ),
                        # Chunk preview
                        rx.cond(
                            IngestionStatusState.document_chunks_preview.length() > 0,
                            rx.card(
                                rx.vstack(
                                    rx.text(
                                        "Content Preview",
                                        font_size=FONT_SIZE["sm"],
                                        font_weight="600",
                                        margin_bottom=SPACING["xs"],
                                    ),
                                    rx.foreach(
                                        IngestionStatusState.document_chunks_preview,
                                        lambda chunk: rx.box(
                                            rx.vstack(
                                                rx.text(
                                                    f"Chunk {chunk['chunk_index']}:",
                                                    font_size=FONT_SIZE["xs"],
                                                    color="gray.10",
                                                    font_weight="600",
                                                ),
                                                rx.text(
                                                    chunk["text"],
                                                    font_size=FONT_SIZE["xs"],
                                                    color="gray.11",
                                                ),
                                                spacing=SPACING["xs"],
                                            ),
                                            padding=SPACING["xs"],
                                            border="1px solid var(--gray-6)",
                                            border_radius="4px",
                                            margin_bottom=SPACING["xs"],
                                        ),
                                    ),
                                    width="100%",
                                    spacing=SPACING["xs"],
                                ),
                                padding=SPACING["sm"],
                            ),
                        ),
                        # Quick actions
                        rx.card(
                            rx.vstack(
                                rx.text(
                                    "Quick Actions",
                                    font_size=FONT_SIZE["sm"],
                                    font_weight="600",
                                    margin_bottom=SPACING["xs"],
                                ),
                                rx.hstack(
                                    rx.button(
                                        rx.icon("search", size=16),
                                        "Search in Document",
                                        on_click=rx.redirect(
                                            f"/search?doc_id={IngestionStatusState.selected_document['id']}"
                                        ),
                                        size="2",
                                        variant="soft",
                                        color_scheme="violet",
                                    ),
                                    rx.button(
                                        rx.icon("refresh-cw", size=16),
                                        "Requeue",
                                        on_click=IngestionStatusState.requeue_document_by_id,
                                        size="2",
                                        variant="soft",
                                        color_scheme="orange",
                                    ),
                                    rx.button(
                                        rx.icon("trash-2", size=16),
                                        "Delete",
                                        on_click=IngestionStatusState.delete_document_by_id,
                                        size="2",
                                        variant="soft",
                                        color_scheme="red",
                                    ),
                                    spacing=SPACING["sm"],
                                    wrap="wrap",
                                ),
                                width="100%",
                                spacing=SPACING["xs"],
                            ),
                            padding=SPACING["sm"],
                        ),
                        width="100%",
                        spacing=SPACING["sm"],
                    ),
                    height="500px",
                ),
                width="100%",
                spacing=SPACING["md"],
            ),
            max_width="600px",
            padding=SPACING["lg"],
        ),
        open=IngestionStatusState.show_document_detail_modal,
    )


def status_card(label: str, count_var, color: str, on_click_handler) -> rx.Component:
    """Clickable status card."""
    return rx.card(
        rx.vstack(
            rx.text(label, font_size=FONT_SIZE["sm"], color="gray.11"),
            rx.heading(count_var, size="7", color=f"{color}.11"),
            spacing=SPACING["xs"],
            align="center",
        ),
        padding=SPACING["md"],
        on_click=on_click_handler,
        style={
            "cursor": "pointer",
            ":hover": {
                "background_color": f"var(--{color}-3)",
                "transform": "translateY(-2px)",
                "box_shadow": "0 4px 12px rgba(0, 0, 0, 0.15)",
            },
            "transition": "all 0.2s ease",
        },
    )


def recent_documents_component() -> rx.Component:
    """Recent documents list component - can be placed independently on the page."""
    return rx.card(
        rx.vstack(
            rx.heading("Recent Documents", size="4", margin_bottom=SPACING["sm"]),
            rx.cond(
                IngestionStatusState.recent_documents.length() > 0,
                rx.vstack(
                    rx.foreach(
                        IngestionStatusState.recent_documents,
                        lambda doc: rx.card(
                            rx.vstack(
                                # Header row: Title and status
                                rx.hstack(
                                    rx.vstack(
                                        # Clickable title
                                        rx.text(
                                            doc["title"],
                                            font_weight="600",
                                            font_size=FONT_SIZE["sm"],
                                            color="blue.11",
                                            cursor="pointer",
                                            on_click=IngestionStatusState.open_document_detail(
                                                doc["id"]
                                            ),
                                            _hover={"text_decoration": "underline"},
                                        ),
                                        # File path and upload time
                                        rx.text(
                                            f"Uploaded: {doc['created_at']}",
                                            font_size=FONT_SIZE["xs"],
                                            color="gray.10",
                                        ),
                                        spacing=SPACING["xs"],
                                        align_items="start",
                                    ),
                                    rx.badge(
                                        doc["status"],
                                        color_scheme=rx.cond(
                                            doc["status"] == "complete",
                                            "green",
                                            rx.cond(
                                                doc["status"] == "processing",
                                                "blue",
                                                rx.cond(
                                                    doc["status"] == "failed",
                                                    "red",
                                                    "gray",
                                                ),
                                            ),
                                        ),
                                    ),
                                    justify="between",
                                    width="100%",
                                    align="start",
                                ),
                                # Processing breakdown
                                rx.hstack(
                                    rx.badge(
                                        doc["doc_type"],
                                        color_scheme="purple",
                                        variant="soft",
                                        size="1",
                                    ),
                                    rx.text(
                                        f"Pages: {doc['num_pages']}",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.11",
                                    ),
                                    rx.text(
                                        f"ID: {doc['id']}",
                                        font_size=FONT_SIZE["xs"],
                                        color="gray.10",
                                    ),
                                    spacing=SPACING["xs"],
                                    wrap="wrap",
                                ),
                                # Quick action buttons
                                rx.hstack(
                                    rx.button(
                                        rx.icon("eye", size=14),
                                        "View",
                                        on_click=IngestionStatusState.open_document_detail(
                                            doc["id"]
                                        ),
                                        size="1",
                                        variant="soft",
                                        color_scheme="blue",
                                    ),
                                    rx.button(
                                        rx.icon("search", size=14),
                                        "Search",
                                        on_click=rx.redirect(
                                            f"/search?doc_id={doc['id']}"
                                        ),
                                        size="1",
                                        variant="soft",
                                        color_scheme="violet",
                                    ),
                                    rx.cond(
                                        doc["status"] == "failed",
                                        rx.button(
                                            rx.icon("refresh-cw", size=14),
                                            "Requeue",
                                            on_click=IngestionStatusState.requeue_document(
                                                doc["id"]
                                            ),
                                            size="1",
                                            variant="soft",
                                            color_scheme="orange",
                                        ),
                                    ),
                                    rx.button(
                                        rx.icon("trash-2", size=14),
                                        "Delete",
                                        on_click=IngestionStatusState.delete_document(
                                            doc["id"]
                                        ),
                                        size="1",
                                        variant="soft",
                                        color_scheme="red",
                                    ),
                                    spacing=SPACING["xs"],
                                    wrap="wrap",
                                ),
                                spacing=SPACING["xs"],
                                width="100%",
                            ),
                            padding=SPACING["sm"],
                            margin_bottom=SPACING["xs"],
                        ),
                    ),
                    width="100%",
                    spacing=SPACING["xs"],
                ),
                rx.text(
                    "No documents yet. Upload files to get started!",
                    color="gray.11",
                    font_size=FONT_SIZE["sm"],
                ),
            ),
            width="100%",
            spacing=SPACING["sm"],
        ),
        padding=SPACING["lg"],
        margin_top=SPACING["md"],
    )


def ingestion_status_component() -> rx.Component:
    """Real-time ingestion status dashboard with clickable cards and document management."""
    return rx.fragment(
        rx.card(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.heading("Ingestion Status", size="5"),
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Refresh",
                        on_click=IngestionStatusState.refresh_status,
                        size="2",
                        variant="soft",
                    ),
                    justify="between",
                    width="100%",
                ),
                # Phase 5.1: Ingestion Mode Settings
                rx.card(
                    rx.hstack(
                        # Mode selector
                        rx.vstack(
                            rx.text(
                                "Ingestion Mode",
                                font_size=FONT_SIZE["xs"],
                                color="gray.10",
                            ),
                            rx.select(
                                ["economy", "enhanced", "vision"],
                                value=IngestionStatusState.ingestion_mode,
                                on_change=IngestionStatusState.set_ingestion_mode,
                            ),
                            spacing="1",
                            align_items="start",
                        ),
                        # Auto-fallback toggle
                        rx.vstack(
                            rx.text(
                                "Auto Vision Fallback",
                                font_size=FONT_SIZE["xs"],
                                color="gray.10",
                            ),
                            rx.switch(
                                checked=IngestionStatusState.auto_fallback_enabled,
                                on_change=IngestionStatusState.toggle_auto_fallback,
                            ),
                            spacing="1",
                            align_items="start",
                        ),
                        # Threshold slider
                        rx.vstack(
                            rx.text(
                                f"Threshold: {IngestionStatusState.fallback_threshold}%",
                                font_size=FONT_SIZE["xs"],
                                color="gray.10",
                            ),
                            rx.slider(
                                default_value=[60],
                                min=40,
                                max=80,
                                step=5,
                                on_value_commit=IngestionStatusState.set_fallback_threshold,
                                width="120px",
                            ),
                            spacing="1",
                            align_items="start",
                        ),
                        # Mode description
                        rx.box(
                            rx.cond(
                                IngestionStatusState.ingestion_mode == "economy",
                                rx.text(
                                    "PaddleOCR only - no LLM",
                                    font_size=FONT_SIZE["xs"],
                                    color="gray.11",
                                ),
                                rx.cond(
                                    IngestionStatusState.ingestion_mode == "enhanced",
                                    rx.text(
                                        "PaddleOCR + LLM enrichment",
                                        font_size=FONT_SIZE["xs"],
                                        color="blue.11",
                                    ),
                                    rx.text(
                                        "Qwen-VL Vision OCR",
                                        font_size=FONT_SIZE["xs"],
                                        color="violet.11",
                                    ),
                                ),
                            ),
                            flex="1",
                        ),
                        spacing="4",
                        align="center",
                        width="100%",
                    ),
                    padding=SPACING["sm"],
                    bg="var(--gray-2)",
                ),
                # Queue Stats - Now clickable
                rx.grid(
                    status_card(
                        "Queued",
                        IngestionStatusState.queued_count,
                        "blue",
                        IngestionStatusState.open_queued_modal,
                    ),
                    status_card(
                        "Processing",
                        IngestionStatusState.processing_count,
                        "orange",
                        IngestionStatusState.open_processing_modal,
                    ),
                    status_card(
                        "Complete",
                        IngestionStatusState.completed_count,
                        "green",
                        IngestionStatusState.open_completed_modal,
                    ),
                    status_card(
                        "Failed",
                        IngestionStatusState.failed_count,
                        "red",
                        IngestionStatusState.open_failed_modal,
                    ),
                    columns="4",
                    spacing=SPACING["md"],
                    width="100%",
                ),
                # Status indicator
                rx.text(
                    "Click status cards to view and manage documents",
                    font_size=FONT_SIZE["xs"],
                    color="gray.10",
                    text_align="center",
                ),
                spacing="4",
                width="100%",
            ),
            padding=SPACING["lg"],
            margin_top=SPACING["md"],
        ),
        # Completed Documents Modal
        document_modal(
            IngestionStatusState.show_completed_modal,
            "Completed Documents",
            IngestionStatusState.completed_documents,
            bulk_action_button=rx.button(
                rx.icon("trash-2", size=16),
                "Clear All Completed",
                on_click=IngestionStatusState.clear_completed,
                color_scheme="red",
                variant="soft",
                size="2",
                loading=IngestionStatusState.is_loading_action,
            ),
            action_buttons_fn=lambda doc: rx.hstack(
                rx.button(
                    rx.icon("trash-2", size=14),
                    "Delete",
                    on_click=IngestionStatusState.delete_document(doc["id"]),
                    color_scheme="red",
                    variant="soft",
                    size="1",
                ),
                spacing=SPACING["xs"],
            ),
        ),
        # Failed Documents Modal
        document_modal(
            IngestionStatusState.show_failed_modal,
            "Failed Documents",
            IngestionStatusState.failed_documents,
            action_buttons_fn=lambda doc: rx.hstack(
                rx.button(
                    rx.icon("rotate-cw", size=14),
                    "Requeue",
                    on_click=IngestionStatusState.requeue_document(doc["id"]),
                    color_scheme="blue",
                    variant="soft",
                    size="1",
                ),
                rx.button(
                    rx.icon("trash-2", size=14),
                    "Delete",
                    on_click=IngestionStatusState.delete_document(doc["id"]),
                    color_scheme="red",
                    variant="soft",
                    size="1",
                ),
                spacing=SPACING["xs"],
            ),
        ),
        # Processing Documents Modal
        document_modal(
            IngestionStatusState.show_processing_modal,
            "Processing Documents",
            IngestionStatusState.processing_documents,
        ),
        # Queued Documents Modal
        document_modal(
            IngestionStatusState.show_queued_modal,
            "Queued Documents",
            IngestionStatusState.queued_documents,
        ),
        # Phase 2.3: Document Detail Modal
        document_detail_modal(),
        # Toast Notification
        rx.cond(
            IngestionStatusState.show_action_toast,
            rx.box(
                rx.hstack(
                    rx.icon(
                        tag=rx.cond(
                            IngestionStatusState.action_type == "success",
                            "circle-check",
                            rx.cond(
                                IngestionStatusState.action_type == "error",
                                "circle-alert",
                                "info",
                            ),
                        ),
                        size=20,
                        color="white",
                    ),
                    rx.text(
                        IngestionStatusState.action_message,
                        color="white",
                        size="2",
                        weight="medium",
                    ),
                    rx.spacer(),
                    rx.icon_button(
                        rx.icon(tag="x", size=16),
                        on_click=IngestionStatusState.hide_toast,
                        variant="ghost",
                        size="1",
                    ),
                    align="center",
                    spacing="3",
                    padding="3",
                ),
                position="fixed",
                top="20px",
                right="20px",
                z_index=Z_INDEX["toast"],
                bg=rx.cond(
                    IngestionStatusState.action_type == "success",
                    "green.600",
                    rx.cond(
                        IngestionStatusState.action_type == "error",
                        "red.600",
                        "blue.600",
                    ),
                ),
                border_radius="md",
                box_shadow="lg",
                min_width="300px",
                max_width="500px",
            ),
        ),
        # Confirmation Dialog for destructive actions
        confirmation_dialog(
            is_open=IngestionStatusState.show_confirm_dialog,
            title=IngestionStatusState.confirm_title,
            message=IngestionStatusState.confirm_message,
            on_confirm=IngestionStatusState.execute_confirmed_action,
            on_cancel=IngestionStatusState.cancel_confirmation,
            confirm_text="Delete",
            cancel_text="Cancel",
            confirm_color="red",
        ),
    )
