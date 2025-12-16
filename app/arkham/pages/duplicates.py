"""
Fingerprint Duplicate Detector Page

Detect near-duplicate documents using fingerprinting algorithms.
"""

import reflex as rx
from app.arkham.state.duplicates_state import DuplicatesState
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


def match_type_badge(match_type) -> rx.Component:
    """Badge showing match type."""
    return rx.badge(
        match_type,
        color_scheme=rx.match(
            match_type,
            ("exact_duplicate", "red"),
            ("near_duplicate", "orange"),
            ("similar_content", "yellow"),
            "gray",
        ),
        size="1",
    )


def similarity_bar(similarity) -> rx.Component:
    """Visual bar showing similarity percentage."""
    return rx.hstack(
        rx.box(
            width=similarity.to(str) + "%",
            height="8px",
            bg=rx.cond(
                similarity >= 90,
                "var(--red-9)",
                rx.cond(
                    similarity >= 70,
                    "var(--orange-9)",
                    "var(--yellow-9)",
                ),
            ),
            border_radius="full",
        ),
        rx.text(similarity.to(str) + "%", size="1", weight="bold"),
        width="120px",
        spacing="2",
        align_items="center",
    )


def pair_row(pair) -> rx.Component:
    """Row showing a similar document pair with clickable links and compare action."""
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.link(
                    rx.hstack(
                        rx.icon("file-text", size=14),
                        rx.text(pair.doc1_filename, weight="medium", size="2"),
                        spacing="1",
                        align="center",
                    ),
                    href="/document/" + pair.doc1_id.to(str),
                    color="var(--accent-11)",
                    _hover={"text_decoration": "underline"},
                ),
                rx.text("ID: " + pair.doc1_id.to(str), size="1", color="gray"),
                align_items="start",
                spacing="0",
            )
        ),
        rx.table.cell(rx.icon("arrow-left-right", size=16, color="var(--gray-9)")),
        rx.table.cell(
            rx.vstack(
                rx.link(
                    rx.hstack(
                        rx.icon("file-text", size=14),
                        rx.text(pair.doc2_filename, weight="medium", size="2"),
                        spacing="1",
                        align="center",
                    ),
                    href="/document/" + pair.doc2_id.to(str),
                    color="var(--accent-11)",
                    _hover={"text_decoration": "underline"},
                ),
                rx.text("ID: " + pair.doc2_id.to(str), size="1", color="gray"),
                align_items="start",
                spacing="0",
            )
        ),
        rx.table.cell(similarity_bar(pair.similarity)),
        rx.table.cell(match_type_badge(pair.match_type)),
        rx.table.cell(
            rx.button(
                rx.icon("git-compare", size=14),
                "Compare",
                size="1",
                variant="soft",
                on_click=lambda: DuplicatesState.compare_pair(
                    pair.doc1_id,
                    pair.doc1_filename,
                    pair.doc2_id,
                    pair.doc2_filename,
                ),
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def cluster_card(cluster) -> rx.Component:
    """Card showing a document cluster."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge("Cluster " + cluster.cluster_id.to(str), color_scheme="blue"),
                rx.text(cluster.size.to(str) + " documents", size="2", color="gray"),
                spacing="2",
            ),
            rx.divider(),
            rx.vstack(
                rx.foreach(
                    cluster.documents,
                    lambda d: rx.link(
                        rx.hstack(
                            rx.icon("file-text", size=14),
                            rx.text(d.filename, size="2"),
                            spacing="2",
                        ),
                        href="/document/" + d.id.to(str),
                        color="var(--accent-11)",
                        _hover={"text_decoration": "underline"},
                    ),
                ),
                spacing="1",
                align_items="start",
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def pattern_card(pattern) -> rx.Component:
    """Card showing a shared text pattern."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge("#" + pattern.pattern_hash, variant="outline"),
                rx.badge(
                    "Found in " + pattern.occurrences.to(str) + " documents",
                    color_scheme="orange",
                ),
                spacing="2",
            ),
            rx.code(pattern.sample_text, size="1"),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="3",
    )


def duplicates_tab() -> rx.Component:
    """Tab showing similar document pairs."""
    return rx.vstack(
        rx.cond(
            DuplicatesState.similar_pairs.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Document 1"),
                        rx.table.column_header_cell(""),
                        rx.table.column_header_cell("Document 2"),
                        rx.table.column_header_cell("Similarity"),
                        rx.table.column_header_cell("Match Type"),
                        rx.table.column_header_cell("Actions"),
                    )
                ),
                rx.table.body(rx.foreach(DuplicatesState.similar_pairs, pair_row)),
                width="100%",
            ),
            rx.callout(
                "No similar document pairs found at current threshold.",
                icon="circle-check",
                color="green",
            ),
        ),
        spacing="4",
        width="100%",
    )


def clusters_tab() -> rx.Component:
    """Tab showing document clusters."""
    return rx.vstack(
        rx.cond(
            DuplicatesState.clusters.length() > 0,
            rx.grid(
                rx.foreach(DuplicatesState.clusters, cluster_card),
                columns="2",
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "No document clusters found.",
                icon="circle-check",
                color="green",
            ),
        ),
        spacing="4",
        width="100%",
    )


def patterns_tab() -> rx.Component:
    """Tab showing shared text patterns."""
    return rx.vstack(
        rx.text(
            "Text segments that appear identically in multiple documents (copy-paste detection).",
            color="gray",
            size="2",
        ),
        rx.cond(
            DuplicatesState.shared_patterns.length() > 0,
            rx.vstack(
                rx.foreach(DuplicatesState.shared_patterns, pattern_card),
                spacing="3",
                width="100%",
            ),
            rx.callout(
                "No shared text patterns found across documents.",
                icon="circle-check",
                color="green",
            ),
        ),
        spacing="4",
        width="100%",
    )


# ========== AUTHORSHIP / STYLOMETRY COMPONENTS ==========


def style_match_row(match) -> rx.Component:
    """Row showing a style match between documents."""
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.hstack(
                    rx.icon("user-pen", size=14),
                    rx.text(match.doc1_filename, weight="medium", size="2"),
                    spacing="1",
                ),
                href="/document/" + match.doc1_id.to(str),
                color="var(--accent-11)",
            )
        ),
        rx.table.cell(rx.icon("arrow-left-right", size=16, color="var(--gray-9)")),
        rx.table.cell(
            rx.link(
                rx.hstack(
                    rx.icon("user-pen", size=14),
                    rx.text(match.doc2_filename, weight="medium", size="2"),
                    spacing="1",
                ),
                href="/document/" + match.doc2_id.to(str),
                color="var(--accent-11)",
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.badge(
                    match.style_similarity.to(str) + "%",
                    color_scheme=rx.cond(
                        match.style_similarity >= 80,
                        "green",
                        rx.cond(match.style_similarity >= 60, "yellow", "gray"),
                    ),
                ),
                spacing="2",
            )
        ),
        rx.table.cell(
            rx.vstack(
                rx.foreach(
                    match.key_similarities,
                    lambda s: rx.badge(s, size="1", variant="soft"),
                ),
                spacing="1",
                align_items="start",
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def author_cluster_card(cluster) -> rx.Component:
    """Card showing an author cluster (documents likely by same author)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("user-check", size=18, color="var(--purple-9)"),
                rx.badge(cluster.label, color_scheme="purple"),
                rx.text(cluster.size.to(str) + " documents", size="2", color="gray"),
                spacing="2",
            ),
            rx.divider(),
            rx.vstack(
                rx.foreach(
                    cluster.documents,
                    lambda d: rx.link(
                        rx.hstack(
                            rx.icon("file-text", size=14),
                            rx.text(d.filename, size="2"),
                            spacing="2",
                        ),
                        href="/document/" + d.id.to(str),
                        color="var(--accent-11)",
                        _hover={"text_decoration": "underline"},
                    ),
                ),
                spacing="1",
                align_items="start",
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def style_profile_row(profile) -> rx.Component:
    """Row showing a document's style profile."""
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(profile.filename, weight="medium", size="2"),
                href="/document/" + profile.document_id.to(str),
                color="var(--accent-11)",
            )
        ),
        rx.table.cell(rx.text(profile.word_count.to(str), size="2")),
        rx.table.cell(rx.text(profile.avg_word_length.to(str), size="2")),
        rx.table.cell(
            rx.badge(
                (profile.vocabulary_richness * 100).to(int).to(str) + "%",
                color_scheme=rx.cond(
                    profile.vocabulary_richness > 0.4,
                    "green",
                    rx.cond(profile.vocabulary_richness > 0.25, "yellow", "orange"),
                ),
                size="1",
            )
        ),
        rx.table.cell(rx.text(profile.avg_sentence_length.to(str), size="2")),
        rx.table.cell(rx.text(profile.punctuation_per_sentence.to(str), size="2")),
        _hover={"bg": "var(--gray-a3)"},
    )


def authorship_tab() -> rx.Component:
    """Tab showing authorship/stylometry analysis."""
    return rx.vstack(
        # Description
        rx.text(
            "Stylometry analyzes writing patterns (vocabulary, sentence structure, punctuation) "
            "to identify documents that may be written by the same author.",
            color="gray",
            size="2",
        ),
        # Controls
        rx.hstack(
            rx.vstack(
                rx.text("Style Threshold", size="1", color="gray"),
                rx.select(
                    ["40", "50", "60", "70", "80"],
                    value=DuplicatesState.style_threshold_str,
                    default_value="60",
                    on_change=DuplicatesState.set_style_threshold,
                    size="1",
                ),
                spacing="1",
            ),
            rx.button(
                rx.icon("user-search", size=14),
                "Analyze Authorship",
                on_click=DuplicatesState.run_authorship_scan,
                loading=DuplicatesState.is_analyzing_style,
                variant="soft",
            ),
            spacing="3",
            align_items="end",
        ),
        # Results
        rx.cond(
            DuplicatesState.is_analyzing_style,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Analyzing writing styles...", color="gray"),
                    spacing="2",
                ),
                padding="4",
            ),
            rx.cond(
                DuplicatesState.has_style_results,
                rx.vstack(
                    # Author clusters
                    rx.cond(
                        DuplicatesState.author_clusters.length() > 0,
                        rx.vstack(
                            rx.heading("Potential Author Groups", size="4"),
                            rx.text(
                                "Documents grouped by similar writing style - may indicate same author.",
                                size="2",
                                color="gray",
                            ),
                            rx.grid(
                                rx.foreach(
                                    DuplicatesState.author_clusters, author_cluster_card
                                ),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                            align_items="start",
                        ),
                        rx.fragment(),
                    ),
                    # Style matches table
                    rx.cond(
                        DuplicatesState.style_matches.length() > 0,
                        rx.vstack(
                            rx.heading("Style Matches", size="4"),
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Document 1"),
                                        rx.table.column_header_cell(""),
                                        rx.table.column_header_cell("Document 2"),
                                        rx.table.column_header_cell("Style Match"),
                                        rx.table.column_header_cell("Key Similarities"),
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(
                                        DuplicatesState.style_matches, style_match_row
                                    )
                                ),
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                            align_items="start",
                        ),
                        rx.fragment(),
                    ),
                    # Style profiles table
                    rx.cond(
                        DuplicatesState.style_profiles.length() > 0,
                        rx.vstack(
                            rx.heading("Document Style Profiles", size="4"),
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Document"),
                                        rx.table.column_header_cell("Words"),
                                        rx.table.column_header_cell("Avg Word Len"),
                                        rx.table.column_header_cell("Vocab Richness"),
                                        rx.table.column_header_cell("Avg Sent Len"),
                                        rx.table.column_header_cell("Punct/Sent"),
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(
                                        DuplicatesState.style_profiles,
                                        style_profile_row,
                                    )
                                ),
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                            align_items="start",
                        ),
                        rx.fragment(),
                    ),
                    # No results message
                    rx.cond(
                        (DuplicatesState.style_matches.length() == 0)
                        & (DuplicatesState.author_clusters.length() == 0),
                        rx.callout(
                            "No similar writing styles found at current threshold. "
                            "Try lowering the threshold or adding more documents.",
                            icon="circle-check",
                            color="green",
                        ),
                        rx.fragment(),
                    ),
                    spacing="6",
                    width="100%",
                ),
                rx.callout(
                    "Click 'Analyze Authorship' to detect writing style patterns. "
                    "This analyzes vocabulary, sentence structure, and punctuation habits "
                    "to identify documents that may share the same author.",
                    icon="user-search",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


# ========== UNMASK AUTHOR TAB ==========


def document_chip(doc, is_known: bool) -> rx.Component:
    """Render a document selection chip."""
    return rx.badge(
        rx.hstack(
            rx.icon("file-text", size=12),
            rx.text(doc.filename, size="1"),
            spacing="1",
        ),
        color_scheme="green" if is_known else "blue",
        variant="soft",
        cursor="pointer",
        on_click=lambda: (
            DuplicatesState.toggle_known_doc(doc.id)
            if is_known
            else DuplicatesState.toggle_unknown_doc(doc.id)
        ),
    )


def unmask_result_row(result) -> rx.Component:
    """Render a row in the authorship probability table."""
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(result.filename, size="2"),
                href="/document/" + result.document_id.to(str),
                color="var(--accent-11)",
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.progress(
                    value=result.probability.to(int),
                    max=100,
                    color_scheme=rx.cond(
                        result.probability >= 75,
                        "green",
                        rx.cond(result.probability >= 55, "yellow", "gray"),
                    ),
                    width="80px",
                ),
                rx.text(
                    result.probability.to(int).to(str) + "%", size="2", weight="bold"
                ),
                spacing="2",
            )
        ),
        rx.table.cell(
            rx.badge(
                rx.cond(
                    result.verdict == "likely_match",
                    "Likely Match",
                    rx.cond(
                        result.verdict == "possible_match",
                        "Possible Match",
                        "Unlikely",
                    ),
                ),
                color_scheme=rx.cond(
                    result.verdict == "likely_match",
                    "green",
                    rx.cond(result.verdict == "possible_match", "yellow", "gray"),
                ),
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.foreach(
                    result.key_matches,
                    lambda m: rx.badge(
                        m, size="1", variant="soft", color_scheme="green"
                    ),
                ),
                spacing="1",
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.foreach(
                    result.key_differences,
                    lambda d: rx.badge(d, size="1", variant="soft", color_scheme="red"),
                ),
                spacing="1",
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def pseudonym_group_card(group) -> rx.Component:
    """Card showing a group of documents likely by the same (anonymous) author."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("users", size=18, color="var(--cyan-9)"),
                rx.badge(
                    "Pseudonym Group " + group.group_id.to(str),
                    color_scheme="cyan",
                ),
                rx.badge(
                    group.match_to_reference.to(int).to(str) + "% match to reference",
                    color_scheme=rx.cond(
                        group.match_to_reference >= 70,
                        "green",
                        rx.cond(group.match_to_reference >= 50, "yellow", "gray"),
                    ),
                    variant="soft",
                ),
                spacing="2",
            ),
            rx.text(
                "These "
                + group.size.to(str)
                + " documents share similar writing style",
                size="2",
                color="gray",
            ),
            rx.divider(),
            rx.vstack(
                rx.foreach(
                    group.documents,
                    lambda d: rx.link(
                        rx.hstack(
                            rx.icon("file-text", size=14),
                            rx.text(d.filename, size="2"),
                            spacing="2",
                        ),
                        href="/document/" + d.id.to(str),
                        color="var(--accent-11)",
                    ),
                ),
                spacing="1",
                align_items="start",
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def unmask_author_tab() -> rx.Component:
    """Tab for Unmask Author - authorship attribution."""
    return rx.vstack(
        # Description
        rx.callout(
            rx.text(
                "Select documents known to be by a suspected author as your reference corpus, "
                "then select unknown documents to test. The system analyzes writing patterns "
                "(vocabulary, sentence structure, punctuation habits) to calculate authorship probability.",
                size="2",
            ),
            icon="user-search",
            color="cyan",
        ),
        # Document Selection
        rx.cond(
            DuplicatesState.available_documents.length() == 0,
            rx.button(
                rx.icon("folder-open", size=14),
                "Load Documents",
                on_click=DuplicatesState.load_documents_for_unmask,
            ),
            rx.vstack(
                rx.hstack(
                    # Known Documents Column
                    rx.vstack(
                        rx.hstack(
                            rx.icon("user-check", size=16, color="var(--green-9)"),
                            rx.text("Known Author Documents", weight="bold", size="3"),
                            rx.badge(
                                DuplicatesState.known_doc_ids.length().to(str)
                                + " selected",
                                color_scheme="green",
                            ),
                            spacing="2",
                        ),
                        rx.text(
                            "Click documents you know are by the suspected author",
                            size="1",
                            color="gray",
                        ),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    DuplicatesState.available_documents,
                                    lambda doc: rx.box(
                                        rx.checkbox(
                                            doc.filename,
                                            checked=DuplicatesState.known_doc_ids.contains(
                                                doc.id
                                            ),
                                            on_change=lambda: DuplicatesState.toggle_known_doc(
                                                doc.id
                                            ),
                                            size="1",
                                        ),
                                        padding="1",
                                    ),
                                ),
                                spacing="1",
                                align_items="start",
                                width="100%",
                            ),
                            height="200px",
                            width="100%",
                        ),
                        border="1px solid var(--green-a6)",
                        border_radius="8px",
                        padding="3",
                        width="100%",
                        spacing="2",
                    ),
                    # Unknown Documents Column
                    rx.vstack(
                        rx.hstack(
                            rx.icon("circle-help", size=16, color="var(--blue-9)"),
                            rx.text("Unknown Documents", weight="bold", size="3"),
                            rx.badge(
                                DuplicatesState.unknown_doc_ids.length().to(str)
                                + " selected",
                                color_scheme="blue",
                            ),
                            rx.button(
                                "Select All",
                                size="1",
                                variant="ghost",
                                on_click=DuplicatesState.select_all_as_unknown,
                            ),
                            spacing="2",
                        ),
                        rx.text(
                            "Click documents to test for authorship match",
                            size="1",
                            color="gray",
                        ),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    DuplicatesState.available_documents,
                                    lambda doc: rx.box(
                                        rx.checkbox(
                                            doc.filename,
                                            checked=DuplicatesState.unknown_doc_ids.contains(
                                                doc.id
                                            ),
                                            on_change=lambda: DuplicatesState.toggle_unknown_doc(
                                                doc.id
                                            ),
                                            size="1",
                                        ),
                                        padding="1",
                                    ),
                                ),
                                spacing="1",
                                align_items="start",
                                width="100%",
                            ),
                            height="200px",
                            width="100%",
                        ),
                        border="1px solid var(--blue-a6)",
                        border_radius="8px",
                        padding="3",
                        width="100%",
                        spacing="2",
                    ),
                    spacing="4",
                    width="100%",
                ),
                # Action buttons
                rx.hstack(
                    rx.button(
                        rx.icon("wand-sparkles", size=14),
                        "Unmask Author",
                        on_click=DuplicatesState.run_unmask_author,
                        loading=DuplicatesState.is_unmasking,
                        disabled=(DuplicatesState.known_doc_ids.length() == 0)
                        | (DuplicatesState.unknown_doc_ids.length() == 0),
                        color_scheme="cyan",
                    ),
                    rx.button(
                        rx.icon("x", size=14),
                        "Clear",
                        on_click=DuplicatesState.clear_selections,
                        variant="soft",
                        color_scheme="gray",
                    ),
                    spacing="2",
                ),
                spacing="4",
                width="100%",
            ),
        ),
        # Results
        rx.cond(
            DuplicatesState.is_unmasking,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Analyzing authorship patterns...", color="gray"),
                    rx.text(
                        "Comparing writing styles across documents",
                        size="1",
                        color="gray",
                    ),
                    spacing="2",
                ),
                padding="6",
            ),
            rx.cond(
                DuplicatesState.has_unmask_results,
                rx.vstack(
                    # Summary stats
                    rx.grid(
                        rx.card(
                            rx.vstack(
                                rx.text("Reference Corpus", size="1", color="gray"),
                                rx.text(
                                    DuplicatesState.reference_doc_count.to(str)
                                    + " documents",
                                    size="4",
                                    weight="bold",
                                ),
                                spacing="1",
                            ),
                            padding="3",
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Likely Matches", size="1", color="gray"),
                                rx.hstack(
                                    rx.icon(
                                        "circle-check", size=20, color="var(--green-9)"
                                    ),
                                    rx.text(
                                        DuplicatesState.unmask_summary.likely_matches.to(
                                            str
                                        ),
                                        size="5",
                                        weight="bold",
                                        color="var(--green-11)",
                                    ),
                                    spacing="1",
                                ),
                                spacing="1",
                            ),
                            padding="3",
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Possible Matches", size="1", color="gray"),
                                rx.hstack(
                                    rx.icon(
                                        "circle-help", size=20, color="var(--yellow-9)"
                                    ),
                                    rx.text(
                                        DuplicatesState.unmask_summary.possible_matches.to(
                                            str
                                        ),
                                        size="5",
                                        weight="bold",
                                        color="var(--yellow-11)",
                                    ),
                                    spacing="1",
                                ),
                                spacing="1",
                            ),
                            padding="3",
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Unlikely Matches", size="1", color="gray"),
                                rx.hstack(
                                    rx.icon("circle-x", size=20, color="var(--gray-9)"),
                                    rx.text(
                                        DuplicatesState.unmask_summary.unlikely_matches.to(
                                            str
                                        ),
                                        size="5",
                                        weight="bold",
                                    ),
                                    spacing="1",
                                ),
                                spacing="1",
                            ),
                            padding="3",
                        ),
                        columns="4",
                        spacing="3",
                        width="100%",
                    ),
                    # Pseudonym Groups (if any)
                    rx.cond(
                        DuplicatesState.pseudonym_groups.length() > 0,
                        rx.vstack(
                            rx.heading("Pseudonym Groups Detected", size="4"),
                            rx.text(
                                "These unknown documents cluster together - potentially by the same anonymous author",
                                size="2",
                                color="gray",
                            ),
                            rx.grid(
                                rx.foreach(
                                    DuplicatesState.pseudonym_groups,
                                    pseudonym_group_card,
                                ),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                            align_items="start",
                        ),
                        rx.fragment(),
                    ),
                    # Results Table (Probability Heatmap)
                    rx.vstack(
                        rx.heading("Authorship Probability", size="4"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Document"),
                                    rx.table.column_header_cell("Match %"),
                                    rx.table.column_header_cell("Verdict"),
                                    rx.table.column_header_cell("Matching Features"),
                                    rx.table.column_header_cell("Differing Features"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    DuplicatesState.unmask_results, unmask_result_row
                                )
                            ),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                        align_items="start",
                    ),
                    spacing="6",
                    width="100%",
                ),
                rx.fragment(),
            ),
        ),
        spacing="4",
        width="100%",
    )


def duplicates_page() -> rx.Component:
    """Main Fingerprint Duplicate Detection page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Duplicate Detector", size="8"),
                    rx.text(
                        "Find near-duplicate documents and copy-paste patterns.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.vstack(
                        rx.text("Similarity Threshold", size="1", color="gray"),
                        rx.select(
                            ["0.5", "0.6", "0.7", "0.8", "0.9"],
                            value=DuplicatesState.similarity_threshold_str,
                            default_value="0.7",
                            on_change=DuplicatesState.set_threshold,
                            size="1",
                        ),
                        spacing="1",
                    ),
                    rx.button(
                        rx.icon("scan", size=14),
                        "Scan for Duplicates",
                        on_click=DuplicatesState.run_scan,
                        loading=DuplicatesState.is_scanning,
                    ),
                    spacing="3",
                    align_items="end",
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.cond(
                DuplicatesState.has_results,
                rx.grid(
                    stat_card(
                        "Similar Pairs",
                        DuplicatesState.total_similar_pairs,
                        "copy",
                        "blue",
                    ),
                    stat_card(
                        "Exact Duplicates",
                        DuplicatesState.exact_duplicates,
                        "copy-check",
                        "red",
                    ),
                    stat_card(
                        "Near Duplicates",
                        DuplicatesState.near_duplicates,
                        "copy-minus",
                        "orange",
                    ),
                    stat_card(
                        "Clusters",
                        DuplicatesState.total_clusters,
                        "layers",
                        "purple",
                    ),
                    columns="4",
                    spacing="4",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Tabs - always visible
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("copy", size=14),
                            rx.text("Duplicates"),
                            rx.cond(
                                DuplicatesState.has_results,
                                rx.badge(
                                    DuplicatesState.similar_pairs.length().to(str),
                                    color_scheme="blue",
                                    size="1",
                                ),
                                rx.fragment(),
                            ),
                            spacing="1",
                        ),
                        value="duplicates",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("layers", size=14),
                            rx.text("Clusters"),
                            spacing="1",
                        ),
                        value="clusters",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("copy-check", size=14),
                            rx.text("Patterns"),
                            spacing="1",
                        ),
                        value="patterns",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("user-pen", size=14),
                            rx.text("Authorship"),
                            spacing="1",
                        ),
                        value="authorship",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("wand-sparkles", size=14),
                            rx.text("Unmask Author"),
                            spacing="1",
                        ),
                        value="unmask",
                    ),
                ),
                rx.tabs.content(
                    rx.cond(
                        DuplicatesState.has_results,
                        duplicates_tab(),
                        rx.cond(
                            DuplicatesState.is_scanning,
                            rx.center(
                                rx.vstack(
                                    rx.spinner(size="3"),
                                    rx.text(
                                        "Scanning corpus for duplicates...",
                                        color="gray",
                                    ),
                                    spacing="2",
                                ),
                                padding="8",
                            ),
                            rx.callout(
                                "Click 'Scan for Duplicates' above to find near-duplicate documents.",
                                icon="copy",
                            ),
                        ),
                    ),
                    value="duplicates",
                    padding_top="4",
                ),
                rx.tabs.content(
                    rx.cond(
                        DuplicatesState.has_results,
                        clusters_tab(),
                        rx.callout(
                            "Run a duplicate scan first to see document clusters.",
                            icon="layers",
                        ),
                    ),
                    value="clusters",
                    padding_top="4",
                ),
                rx.tabs.content(
                    rx.cond(
                        DuplicatesState.has_results,
                        patterns_tab(),
                        rx.callout(
                            "Run a duplicate scan first to detect copy-paste patterns.",
                            icon="copy-check",
                        ),
                    ),
                    value="patterns",
                    padding_top="4",
                ),
                rx.tabs.content(authorship_tab(), value="authorship", padding_top="4"),
                rx.tabs.content(unmask_author_tab(), value="unmask", padding_top="4"),
                default_value="duplicates",
                width="100%",
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
        ),
        width="100%",
        height="100vh",
    )
