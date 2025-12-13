"""
Document Comparison Page

Side-by-side comparison of documents.
"""

import reflex as rx
from app.arkham.state.comparison_state import ComparisonState
from app.arkham.components.sidebar import sidebar


def similarity_meter(label: str, value: float, color: str = "blue") -> rx.Component:
    """Meter showing similarity percentage."""
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="2", weight="medium"),
            rx.spacer(),
            rx.text(f"{value:.1f}%", size="2", weight="bold"),
            width="100%",
        ),
        rx.box(
            rx.box(
                width=f"{value}%",
                height="8px",
                bg=f"var(--{color}-9)",
                border_radius="full",
            ),
            width="100%",
            height="8px",
            bg="var(--gray-4)",
            border_radius="full",
        ),
        spacing="1",
        width="100%",
    )


def doc_selector(label: str, value: int, on_change, documents) -> rx.Component:
    """Document selector dropdown."""
    return rx.vstack(
        rx.text(label, size="2", weight="bold"),
        rx.cond(
            ComparisonState.documents.length() > 0,
            rx.select.root(
                rx.select.trigger(placeholder="Select document..."),
                rx.select.content(
                    rx.select.group(
                        rx.foreach(
                            ComparisonState.documents,
                            lambda d: rx.select.item(d.filename, value=d.id.to(str)),
                        ),
                    ),
                ),
                value=rx.cond(value > 0, value.to(str), None),
                on_change=on_change,
            ),
            rx.select(
                ["Loading..."],
                disabled=True,
                placeholder="Loading documents...",
            ),
        ),
        spacing="1",
        width="100%",
    )


def entity_list(title: str, entities, color: str = "blue") -> rx.Component:
    """List of entities."""
    return rx.vstack(
        rx.hstack(
            rx.text(title, size="2", weight="bold"),
            rx.badge(entities.length(), size="1", color_scheme=color),
            spacing="2",
        ),
        rx.cond(
            entities.length() > 0,
            rx.flex(
                rx.foreach(
                    entities,
                    lambda e: rx.badge(
                        f"{e.name} ({e.type})",
                        size="1",
                        variant="soft",
                    ),
                ),
                wrap="wrap",
                spacing="1",
            ),
            rx.text("None", size="1", color="gray"),
        ),
        spacing="2",
        align_items="start",
    )


def comparison_page() -> rx.Component:
    """Main Comparison page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Document Comparison", size="8"),
                    rx.text(
                        "Compare two documents side by side.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.cond(
                    ComparisonState.has_comparison,
                    rx.button(
                        rx.icon("x"),
                        "Clear",
                        variant="ghost",
                        on_click=ComparisonState.clear_comparison,
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align_items="end",
            ),
            # Document selection
            rx.card(
                rx.hstack(
                    rx.box(
                        doc_selector(
                            "Document 1",
                            ComparisonState.doc1_id,
                            ComparisonState.select_doc1,
                            ComparisonState.documents,
                        ),
                        width="40%",
                    ),
                    rx.center(
                        rx.icon("arrow-right-left", size=24, color="var(--gray-9)"),
                    ),
                    rx.box(
                        doc_selector(
                            "Document 2",
                            ComparisonState.doc2_id,
                            ComparisonState.select_doc2,
                            ComparisonState.documents,
                        ),
                        width="40%",
                    ),
                    rx.button(
                        rx.icon("git-compare", size=14),
                        "Compare",
                        on_click=ComparisonState.compare_documents,
                        loading=ComparisonState.is_loading,
                        disabled=(ComparisonState.doc1_id == 0)
                        | (ComparisonState.doc2_id == 0),
                    ),
                    width="100%",
                    spacing="4",
                    align_items="end",
                ),
                padding="4",
            ),
            # Comparison results
            rx.cond(
                ComparisonState.has_comparison,
                rx.vstack(
                    # Similarity scores
                    rx.grid(
                        rx.card(
                            rx.vstack(
                                rx.heading("Similarity", size="4"),
                                similarity_meter(
                                    "Text Similarity",
                                    ComparisonState.text_similarity,
                                    "blue",
                                ),
                                similarity_meter(
                                    "Entity Overlap",
                                    ComparisonState.entity_similarity,
                                    "green",
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            padding="4",
                        ),
                        rx.card(
                            rx.vstack(
                                rx.heading("Document Stats", size="4"),
                                rx.grid(
                                    rx.vstack(
                                        rx.text(
                                            ComparisonState.doc1_name,
                                            weight="medium",
                                            size="2",
                                        ),
                                        rx.hstack(
                                            rx.badge(
                                                f"{ComparisonState.doc1_chunks} chunks"
                                            ),
                                            rx.badge(
                                                f"{ComparisonState.doc1_entities} entities"
                                            ),
                                            spacing="2",
                                        ),
                                        spacing="1",
                                    ),
                                    rx.vstack(
                                        rx.text(
                                            ComparisonState.doc2_name,
                                            weight="medium",
                                            size="2",
                                        ),
                                        rx.hstack(
                                            rx.badge(
                                                f"{ComparisonState.doc2_chunks} chunks"
                                            ),
                                            rx.badge(
                                                f"{ComparisonState.doc2_entities} entities"
                                            ),
                                            spacing="2",
                                        ),
                                        spacing="1",
                                    ),
                                    columns="2",
                                    spacing="4",
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            padding="4",
                        ),
                        columns="2",
                        spacing="4",
                        width="100%",
                    ),
                    # Entity comparison
                    rx.card(
                        rx.vstack(
                            rx.heading("Entity Comparison", size="4"),
                            rx.divider(),
                            rx.grid(
                                entity_list(
                                    "Shared Entities",
                                    ComparisonState.shared_entities,
                                    "green",
                                ),
                                entity_list(
                                    f"Only in {ComparisonState.doc1_name}",
                                    ComparisonState.doc1_only_entities,
                                    "blue",
                                ),
                                entity_list(
                                    f"Only in {ComparisonState.doc2_name}",
                                    ComparisonState.doc2_only_entities,
                                    "purple",
                                ),
                                columns="3",
                                spacing="6",
                                width="100%",
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        padding="4",
                    ),
                    # Common phrases
                    rx.cond(
                        ComparisonState.common_phrases.length() > 0,
                        rx.card(
                            rx.vstack(
                                rx.heading("Common Text Segments", size="4"),
                                rx.divider(),
                                rx.foreach(
                                    ComparisonState.common_phrases,
                                    lambda p: rx.code(p, size="1"),
                                ),
                                spacing="3",
                                align_items="start",
                                width="100%",
                            ),
                            padding="4",
                        ),
                        rx.fragment(),
                    ),
                    # Diff view
                    rx.cond(
                        ComparisonState.diff_text != "",
                        rx.card(
                            rx.vstack(
                                rx.heading("Text Differences", size="4"),
                                rx.divider(),
                                rx.code_block(
                                    ComparisonState.diff_text,
                                    language="diff",
                                    show_line_numbers=True,
                                ),
                                spacing="3",
                                width="100%",
                            ),
                            padding="4",
                        ),
                        rx.fragment(),
                    ),
                    spacing="4",
                    width="100%",
                ),
                rx.cond(
                    ComparisonState.is_loading,
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="3"),
                            rx.text("Comparing documents...", color="gray"),
                            spacing="2",
                        ),
                        padding="8",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text(
                                "Select two documents to compare.",
                                weight="medium",
                            ),
                            rx.text(
                                "Comparison shows text similarity, shared entities, "
                                "common text segments, and differences between documents.",
                                size="2",
                            ),
                            align_items="start",
                            spacing="1",
                        ),
                        icon="git-compare",
                    ),
                ),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=ComparisonState.load_documents,
        ),
        width="100%",
        height="100vh",
    )
