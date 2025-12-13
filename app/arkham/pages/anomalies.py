import reflex as rx
from ..components.layout import layout
from ..state.anomaly_state import AnomalyState, AnomalyItem
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING, CARD_GAP


def anomaly_card(anomaly: AnomalyItem) -> rx.Component:
    """Display a single anomaly item."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    f"{anomaly.score:.2f}",
                    color_scheme="red",
                    variant="solid",
                    size="2",
                ),
                rx.heading(anomaly.doc_title, size="4"),
                spacing=SPACING["sm"],
                align="center",
                width="100%",
            ),
            rx.text(
                f"Reason: {anomaly.reason}",
                color="gray.11",
                font_size=FONT_SIZE["sm"],
            ),
            rx.text(
                anomaly.chunk_text,
                color="gray.11",
                font_size=FONT_SIZE["sm"],
                line_height="1.5",
            ),
            rx.button(
                "Chat about this",
                on_click=lambda: AnomalyState.chat_about_anomaly(
                    anomaly.doc_title, anomaly.score
                ),
                size="2",
                variant="soft",
            ),
            spacing=SPACING["sm"],
            align="start",
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
        variant="surface",
    )


def pagination_controls() -> rx.Component:
    """Pagination controls for anomalies list."""
    return rx.hstack(
        rx.button(
            rx.icon(tag="chevron_left", size=16),
            "Previous",
            on_click=AnomalyState.prev_page,
            disabled=~AnomalyState.has_previous,
            size="2",
            variant="soft",
        ),
        rx.text(
            f"Page {AnomalyState.current_page} of {AnomalyState.total_pages}",
            font_size=FONT_SIZE["sm"],
            color="gray.11",
        ),
        rx.button(
            "Next",
            rx.icon(tag="chevron_right", size=16),
            on_click=AnomalyState.next_page,
            disabled=~AnomalyState.has_next,
            size="2",
            variant="soft",
        ),
        rx.spacer(),
        rx.text(
            f"{AnomalyState.total_items} total anomalies",
            font_size=FONT_SIZE["sm"],
            color="gray.11",
        ),
        align="center",
        justify="center",
        spacing=SPACING["md"],
        width="100%",
        padding_top=SPACING["md"],
    )


def anomalies_tab() -> rx.Component:
    """Anomalies list tab."""
    return rx.vstack(
        rx.hstack(
            rx.text(
                "Statistical outliers detected by Isolation Forest.",
                color="gray.11",
                font_size=FONT_SIZE["sm"],
            ),
            rx.spacer(),
            rx.cond(
                AnomalyState.anomalies.length() > 0,
                rx.button(
                    rx.icon(tag="download", size=16),
                    "Export",
                    on_click=AnomalyState.export_anomalies,
                    size="2",
                    variant="soft",
                    color_scheme="green",
                ),
                rx.fragment(),
            ),
            align="center",
            width="100%",
        ),
        rx.cond(
            AnomalyState.is_loading,
            rx.spinner(),
            rx.cond(
                AnomalyState.anomalies.length() == 0,
                rx.callout(
                    "No anomalies detected.",
                    icon="info",
                    color_scheme="blue",
                ),
                rx.vstack(
                    rx.foreach(
                        AnomalyState.anomalies,
                        anomaly_card,
                    ),
                    pagination_controls(),
                    spacing=SPACING["sm"],
                    width="100%",
                ),
            ),
        ),
        spacing=SPACING["md"],
        width="100%",
    )


def document_checkbox(doc: dict) -> rx.Component:
    """Individual document checkbox."""
    doc_id = doc["id"]
    return rx.hstack(
        rx.checkbox(
            checked=AnomalyState.selected_doc_ids_str.contains(doc_id),
            on_change=lambda _: AnomalyState.toggle_document(doc_id),
        ),
        rx.text(doc["label"], size="2", flex="1"),
        width="100%",
        padding_y="1",
        _hover={"bg": "var(--gray-a3)"},
        cursor="pointer",
        on_click=lambda: AnomalyState.toggle_document(doc_id),
    )


def files_tab() -> rx.Component:
    """Files viewer tab with multi-select."""
    return rx.vstack(
        rx.text(
            "Select documents to focus the chat context. Multiple selections allowed.",
            color="gray.11",
            font_size=FONT_SIZE["sm"],
        ),
        # Selection controls
        rx.hstack(
            rx.button(
                rx.icon("square-check", size=14),
                "Select All",
                size="1",
                variant="soft",
                on_click=AnomalyState.select_all_documents,
            ),
            rx.button(
                rx.icon("square-x", size=14),
                "Clear / Use All",
                size="1",
                variant="soft",
                on_click=AnomalyState.clear_selection,
            ),
            rx.spacer(),
            rx.badge(
                AnomalyState.selection_summary,
                variant="soft",
                size="2",
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        # Document list with checkboxes
        rx.card(
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        AnomalyState.document_select_options,
                        document_checkbox,
                    ),
                    spacing="0",
                    width="100%",
                ),
                max_height="300px",
            ),
            width="100%",
            padding="2",
        ),
        # Document preview (shows last selected doc) - takes remaining space
        rx.cond(
            AnomalyState.document_text != "",
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Document Preview", weight="bold", size="2"),
                        rx.spacer(),
                        rx.badge(
                            f"Doc #{AnomalyState.last_previewed_doc_id}", size="1"
                        ),
                        width="100%",
                    ),
                    rx.scroll_area(
                        rx.markdown(AnomalyState.document_text),
                        height="100%",
                        flex="1",
                    ),
                    spacing="2",
                    width="100%",
                    height="100%",
                    flex="1",
                ),
                width="100%",
                padding=CARD_PADDING,
                flex="1",
            ),
            rx.callout(
                rx.cond(
                    AnomalyState.use_all_documents,
                    "Searching across ALL files. Select documents to focus the search.",
                    "No files selected. Select a document to preview its content.",
                ),
                icon="info",
                color_scheme="blue",
            ),
        ),
        spacing=SPACING["md"],
        width="100%",
        height="100%",
        flex="1",
    )


def chat_message(msg: dict) -> rx.Component:
    """Render a single chat message."""
    is_user = msg["role"] == "user"
    return rx.box(
        rx.card(
            rx.markdown(msg["content"]),
            background=rx.cond(is_user, "blue.3", "gray.3"),
            padding=SPACING["md"],
        ),
        display="flex",
        justify_content=rx.cond(is_user, "flex-end", "flex-start"),
        width="100%",
    )


def chat_interface() -> rx.Component:
    """Chat interface for asking questions - now roomier."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Investigation Chat", size="6"),
            rx.spacer(),
            rx.badge(
                AnomalyState.selection_summary,
                variant="outline",
                size="1",
            ),
            width="100%",
            align="center",
        ),
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    AnomalyState.chat_messages,
                    chat_message,
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            height="100%",
            flex="1",
        ),
        rx.form(
            rx.hstack(
                rx.input(
                    placeholder="Ask a question about your selected documents...",
                    value=AnomalyState.current_question,
                    on_change=AnomalyState.set_current_question,
                    width="100%",
                    size="3",
                    name="question",
                    required=True,
                    min_length=3,
                ),
                rx.button(
                    "Send",
                    type="submit",
                    loading=AnomalyState.is_generating,
                    size="3",
                ),
                spacing=SPACING["sm"],
                width="100%",
            ),
            on_submit=lambda _: AnomalyState.ask_question,
            width="100%",
        ),
        spacing=SPACING["md"],
        width="100%",
        height="100%",
        flex="1",
    )


def anomalies_page() -> rx.Component:
    """Anomalies investigation page with improved layout."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.heading("🕵️ Investigation & Anomalies", size="8"),
                rx.spacer(),
                # Load or Refresh button based on data state
                rx.cond(
                    AnomalyState.has_data,
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Refresh",
                        on_click=AnomalyState.refresh_anomalies,
                        loading=AnomalyState.is_loading,
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Load Anomalies",
                        on_click=AnomalyState.load_anomalies,
                        loading=AnomalyState.is_loading,
                        color_scheme="blue",
                    ),
                ),
                width="100%",
                align="center",
            ),
            # Use a better grid layout - left sidebar narrower, chat takes more space
            rx.hstack(
                # Left column: Tabs (narrower)
                rx.box(
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("⚠️ Anomalies", value="anomalies"),
                            rx.tabs.trigger("📂 Files", value="files"),
                        ),
                        rx.tabs.content(
                            anomalies_tab(),
                            value="anomalies",
                            padding_top=SPACING["md"],
                        ),
                        rx.tabs.content(
                            files_tab(),
                            value="files",
                            padding_top=SPACING["md"],
                        ),
                        default_value="files",
                    ),
                    width="550px",
                    flex_shrink="0",
                    height="calc(100vh - 200px)",
                    overflow_y="auto",
                ),
                # Right column: Chat interface (takes remaining space)
                rx.card(
                    chat_interface(),
                    flex="1",
                    height="calc(100vh - 200px)",
                    padding=SPACING["lg"],
                ),
                spacing=CARD_GAP,
                width="100%",
                align="stretch",
            ),
            spacing=SPACING["md"],
            width="100%",
            # Removed on_mount - user must click Load button
        )
    )
