import reflex as rx
from ..components.layout import layout
from ..components.file_upload import upload_component
from ..components.chat_interface import chat_interface
from ..components.worker_management import worker_management_component
from ..components.ingestion_status import (
    ingestion_status_component,
    recent_documents_component,
)
from ..components.upload_progress import upload_progress_panel


def ingest_page() -> rx.Component:
    """Ingestion and Chat page."""
    return layout(
        rx.vstack(
            rx.heading("Ingestion & Analysis", size="8"),
            # Ingestion Status Dashboard (mode settings and queue stats)
            ingestion_status_component(),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("File Upload", value="upload"),
                    rx.tabs.trigger("AI Chat", value="chat"),
                ),
                rx.tabs.content(
                    rx.vstack(
                        worker_management_component(),
                        rx.card(
                            upload_component(),
                            margin_top="4",
                        ),
                        # Upload Progress Panel
                        upload_progress_panel(),
                        spacing="4",
                        width="100%",
                    ),
                    value="upload",
                ),
                rx.tabs.content(
                    rx.card(
                        chat_interface(),
                        margin_top="4",
                    ),
                    value="chat",
                ),
                default_value="upload",
                width="100%",
            ),
            # Recent Documents - now at the bottom for better visibility of upload UI
            recent_documents_component(),
            width="100%",
            spacing="4",
        ),
    )
