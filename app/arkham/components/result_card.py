import reflex as rx
from ..state.search_state import SearchResult, SearchState
from .design_tokens import SPACING, FONT_SIZE


def result_card_compact(result: SearchResult) -> rx.Component:
    """Display a compact search result for modals."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(
                    rx.cond(
                        result.metadata.title != "",
                        result.metadata.title,
                        "Untitled Document",
                    ),
                    size="2",
                    weight="medium",
                    trim="both",
                ),
                rx.spacer(),
                rx.badge(
                    f"{result.score:.2f}",
                    color_scheme="green",
                    variant="soft",
                    size="1",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                result.snippet,
                color="gray.11",
                size="1",
                trim="both",
            ),
            spacing="1",
            width="100%",
        ),
        width="100%",
        padding="2",
        variant="surface",
        size="1",
    )


def result_card(result: SearchResult) -> rx.Component:
    """
    Display a full search result.
    - Click title to view chunk in dialog
    - Click "View Document" link to see full document page
    """
    return rx.card(
        rx.vstack(
            rx.hstack(
                # Title - opens chunk dialog
                rx.dialog.root(
                    rx.dialog.trigger(
                        rx.heading(
                            rx.cond(
                                result.metadata.title != "",
                                result.metadata.title,
                                f"Document #{result.doc_id}",
                            ),
                            size="4",
                            color="blue.11",
                            cursor="pointer",
                            _hover={"color": "blue.9", "text_decoration": "underline"},
                        ),
                    ),
                    rx.dialog.content(
                        rx.dialog.title("Matched Chunk"),
                        rx.dialog.description(
                            rx.hstack(
                                rx.badge(f"Doc ID: {result.doc_id}", size="1"),
                                rx.cond(
                                    result.metadata.doc_type != "",
                                    rx.badge(
                                        result.metadata.doc_type,
                                        variant="outline",
                                        size="1",
                                    ),
                                    rx.fragment(),
                                ),
                                rx.badge(
                                    f"Score: {result.score}",
                                    color_scheme="green",
                                    size="1",
                                ),
                                spacing="2",
                            ),
                        ),
                        rx.separator(margin_y="3"),
                        rx.scroll_area(
                            rx.text(
                                result.text,
                                white_space="pre-wrap",
                                font_size=FONT_SIZE["sm"],
                                line_height="1.6",
                            ),
                            max_height="50vh",
                        ),
                        rx.separator(margin_y="3"),
                        rx.hstack(
                            rx.link(
                                rx.button(
                                    rx.icon("file-text", size=14),
                                    "View Full Document",
                                    variant="solid",
                                ),
                                href=f"/document/{result.doc_id}",
                            ),
                            rx.spacer(),
                            rx.dialog.close(
                                rx.button("Close", variant="soft"),
                            ),
                            width="100%",
                        ),
                        max_width="700px",
                    ),
                ),
                rx.spacer(),
                rx.badge(
                    result.score,
                    color_scheme="green",
                    variant="soft",
                    radius="full",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                result.snippet,
                color="gray.11",
                font_size=FONT_SIZE["sm"],
                line_height="1.5",
            ),
            rx.hstack(
                rx.badge(f"Doc #{result.doc_id}", variant="outline", size="1"),
                rx.cond(
                    result.metadata.doc_type != "",
                    rx.badge(result.metadata.doc_type, variant="outline", size="1"),
                    rx.fragment(),
                ),
                rx.spacer(),
                rx.link(
                    rx.text(
                        "View Full Document →",
                        size="1",
                        color="blue",
                        _hover={"text_decoration": "underline"},
                    ),
                    href=f"/document/{result.doc_id}",
                ),
                width="100%",
                align="center",
                margin_top=SPACING["sm"],
            ),
            align="start",
            spacing=SPACING["xs"],
            width="100%",
        ),
        width="100%",
        padding=SPACING["md"],
        variant="surface",
        _hover={"box_shadow": "md", "border_color": "var(--gray-6)"},
    )


def document_viewer_modal() -> rx.Component:
    """Modal for viewing full reconstructed document (legacy, kept for compatibility)."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(SearchState.doc_viewer_title),
            rx.dialog.description(
                rx.hstack(
                    rx.badge(f"Doc ID: {SearchState.doc_viewer_doc_id}", size="1"),
                    rx.text(
                        "Full document reconstructed from chunks",
                        size="1",
                        color="gray",
                    ),
                    spacing="2",
                ),
            ),
            rx.separator(margin_y="3"),
            rx.cond(
                SearchState.doc_viewer_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Loading document...", size="2", color="gray"),
                        spacing="2",
                    ),
                    padding="8",
                ),
                rx.scroll_area(
                    rx.text(
                        SearchState.doc_viewer_content,
                        white_space="pre-wrap",
                        font_size=FONT_SIZE["sm"],
                        line_height="1.6",
                        font_family="monospace",
                    ),
                    max_height="60vh",
                ),
            ),
            rx.separator(margin_y="3"),
            rx.hstack(
                rx.button(
                    "Close", variant="soft", on_click=SearchState.close_document_viewer
                ),
                justify="end",
                width="100%",
            ),
            max_width="900px",
        ),
        open=SearchState.doc_viewer_open,
    )
