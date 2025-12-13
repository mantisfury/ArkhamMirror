import reflex as rx
from ..components.layout import layout
from ..components.design_tokens import SPACING, FONT_SIZE


class DocumentViewState(rx.State):
    """State for the document view page."""

    doc_title: str = ""
    doc_content: str = ""
    is_loading: bool = True
    error_message: str = ""
    current_doc_id: int = 0  # Store the parsed doc_id

    def on_load(self):
        """Load document on page mount."""
        from ..services.search_service import get_document_content, get_document_title

        # Get doc_id from route parameter
        doc_id_str = self.router.page.params.get("doc_id", "0")
        try:
            self.current_doc_id = int(doc_id_str)
        except (ValueError, TypeError):
            self.current_doc_id = 0

        self.is_loading = True
        self.error_message = ""
        yield

        try:
            if self.current_doc_id <= 0:
                self.error_message = "Invalid document ID"
                self.is_loading = False
                return

            title = get_document_title(self.current_doc_id)
            self.doc_title = title or f"Document #{self.current_doc_id}"

            content = get_document_content(self.current_doc_id)
            self.doc_content = content
        except Exception as e:
            self.error_message = f"Error loading document: {e}"
        finally:
            self.is_loading = False


def document_page() -> rx.Component:
    """Page for viewing a full reconstructed document."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.icon("arrow-left", size=14),
                        "Back to Search",
                        variant="ghost",
                        size="2",
                    ),
                    href="/",
                ),
                rx.spacer(),
                rx.badge(f"Document #{DocumentViewState.current_doc_id}", size="2"),
                width="100%",
                align="center",
                margin_bottom=SPACING["md"],
            ),
            rx.heading(DocumentViewState.doc_title, size="7"),
            rx.separator(margin_y=SPACING["md"]),
            rx.cond(
                DocumentViewState.is_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Loading document...", color="gray"),
                        spacing="3",
                    ),
                    padding=SPACING["2xl"],
                    width="100%",
                ),
                rx.cond(
                    DocumentViewState.error_message != "",
                    rx.callout(
                        DocumentViewState.error_message,
                        icon="triangle-alert",
                        color="red",
                    ),
                    rx.card(
                        rx.scroll_area(
                            rx.text(
                                DocumentViewState.doc_content,
                                white_space="pre-wrap",
                                font_size=FONT_SIZE["sm"],
                                line_height="1.7",
                                font_family="monospace",
                            ),
                            max_height="70vh",
                        ),
                        width="100%",
                        padding=SPACING["lg"],
                    ),
                ),
            ),
            spacing=SPACING["md"],
            width="100%",
        ),
        page_name="Document View",
    )
