"""
Cross-Document Fact Comparison Page

Identifies corroborating and conflicting facts across documents.
"""

import reflex as rx
from app.arkham.state.fact_comparison_state import FactComparisonState
from app.arkham.components.sidebar import sidebar

# Color-coding for visual consistency
CATEGORY_COLORS = {
    "Date": "blue",
    "Location": "green",
    "Relationship": "purple",
    "Amount": "yellow",
    "Event": "orange",
    "Role": "cyan",
    "Other": "gray",
}

RELIABILITY_COLORS = {
    "High": "green",
    "Medium": "yellow",
    "Low": "gray",
}

SEVERITY_COLORS = {
    "High": "red",
    "Medium": "orange",
    "Low": "yellow",
}


def stat_card(
    label: str, value, icon: str, color: str = "blue", on_click=None
) -> rx.Component:
    """Stat card that's optionally clickable."""
    card_style = {}
    if on_click:
        card_style = {
            "cursor": "pointer",
            "_hover": {"border_color": f"var(--{color}-8)", "transform": "scale(1.02)"},
            "transition": "transform 0.15s ease",
        }

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
        on_click=on_click,
        **card_style,
    )


def entity_analysis_row(analysis) -> rx.Component:
    """Row showing entity fact analysis summary."""
    return rx.table.row(
        rx.table.cell(rx.text(analysis.entity_name, weight="medium")),
        rx.table.cell(rx.text(analysis.total_facts)),
        rx.table.cell(
            rx.cond(
                analysis.confirmations > 0,
                rx.badge(
                    f"+{analysis.confirmations}",
                    color_scheme="green",
                    variant="soft",
                ),
                rx.text("-", color="gray"),
            )
        ),
        rx.table.cell(
            rx.cond(
                analysis.conflicts > 0,
                rx.badge(
                    analysis.conflicts,
                    color_scheme="red",
                    variant="soft",
                ),
                rx.text("-", color="gray"),
            )
        ),
        rx.table.cell(
            rx.button(
                rx.icon("search", size=14),
                "Analyze",
                size="1",
                variant="soft",
                on_click=lambda: FactComparisonState.analyze_entity(
                    analysis.entity_id, analysis.entity_name
                ),
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def fact_card(fact, index: int) -> rx.Component:
    """Card displaying a single fact with color-coded badges. Clickable for details."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(f"#{index}", variant="outline", size="1"),
                # Category badge with color-coding
                rx.badge(
                    fact.category,
                    color_scheme=rx.match(
                        fact.category,
                        ("Date", "blue"),
                        ("Location", "green"),
                        ("Relationship", "purple"),
                        ("Amount", "yellow"),
                        ("Event", "orange"),
                        ("Role", "cyan"),
                        "gray",  # Default for "Other"
                    ),
                    size="1",
                ),
                # Reliability badge with color-coding
                rx.badge(
                    fact.reliability,
                    color_scheme=rx.match(
                        fact.reliability,
                        ("High", "green"),
                        ("Medium", "yellow"),
                        "gray",  # Default for "Low"
                    ),
                    size="1",
                ),
                rx.spacer(),
                # Show doc title instead of just doc_id
                rx.text(
                    rx.cond(
                        fact.doc_title != "",
                        fact.doc_title,
                        f"Doc {fact.doc_id}",
                    ),
                    size="1",
                    color="gray",
                    style={
                        "max_width": "150px",
                        "overflow": "hidden",
                        "text_overflow": "ellipsis",
                    },
                ),
                width="100%",
            ),
            rx.text(fact.claim, size="2"),
            # Show chunk text excerpt if available
            rx.cond(
                fact.chunk_text != "",
                rx.text(
                    fact.chunk_text,
                    size="1",
                    color="gray",
                    style={"font_style": "italic", "opacity": "0.8"},
                ),
                rx.fragment(),
            ),
            align_items="start",
            spacing="2",
        ),
        padding="3",
        cursor="pointer",
        _hover={
            "border_color": "var(--accent-8)",
            "box_shadow": "0 2px 8px rgba(0,0,0,0.1)",
        },
        on_click=lambda: FactComparisonState.open_fact_modal(index),
    )


def corroboration_card(relation, index: int) -> rx.Component:
    """Card showing corroborating facts with reliability badge."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("circle-check", size=18, color="var(--green-9)"),
                rx.text("Corroborated", weight="bold", color="green"),
                rx.spacer(),
                rx.badge(
                    relation.reliability,
                    color_scheme=rx.match(
                        relation.reliability,
                        ("High", "green"),
                        ("Medium", "yellow"),
                        "gray",
                    ),
                    variant="soft",
                    size="1",
                ),
                width="100%",
            ),
            rx.text(relation.explanation, size="2"),
            rx.hstack(
                rx.text("Related facts:", size="1", color="gray"),
                rx.foreach(
                    relation.fact_indices,
                    lambda idx: rx.badge(f"#{idx}", size="1", variant="outline"),
                ),
                rx.icon("chevron-right", size=14, color="gray"),
                spacing="1",
            ),
            align_items="start",
            spacing="2",
        ),
        padding="3",
        style={"border-left": "3px solid var(--green-9)"},
        cursor="pointer",
        _hover={
            "border_color": "var(--green-8)",
            "box_shadow": "0 2px 8px rgba(0,0,0,0.1)",
        },
        on_click=lambda: FactComparisonState.open_relation_modal(
            index, "corroboration"
        ),
    )


def conflict_card(relation, index: int) -> rx.Component:
    """Card showing conflicting facts."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("triangle-alert", size=18, color="var(--red-9)"),
                rx.text("Conflict", weight="bold", color="red"),
                rx.spacer(),
                rx.badge(
                    relation.severity,
                    color_scheme=rx.match(
                        relation.severity,
                        ("High", "red"),
                        ("Medium", "orange"),
                        "yellow",
                    ),
                    size="1",
                ),
                width="100%",
            ),
            rx.text(relation.explanation, size="2"),
            rx.hstack(
                rx.text("Conflicting facts:", size="1", color="gray"),
                rx.foreach(
                    relation.fact_indices,
                    lambda idx: rx.badge(f"#{idx}", size="1", variant="outline"),
                ),
                rx.icon("chevron-right", size=14, color="gray"),
                spacing="1",
            ),
            align_items="start",
            spacing="2",
        ),
        padding="3",
        style={"border-left": "3px solid var(--red-9)"},
        cursor="pointer",
        _hover={
            "border_color": "var(--red-8)",
            "box_shadow": "0 2px 8px rgba(0,0,0,0.1)",
        },
        on_click=lambda: FactComparisonState.open_relation_modal(index, "conflict"),
    )


def doc_checkbox(doc: dict) -> rx.Component:
    """Individual document checkbox."""
    doc_id = doc["id"]
    return rx.hstack(
        rx.checkbox(
            checked=FactComparisonState.selected_doc_ids_str.contains(doc_id),
            on_change=lambda _: FactComparisonState.toggle_document(doc_id),
        ),
        rx.text(doc["label"], size="2", flex="1"),
        width="100%",
        padding_y="1",
        _hover={"bg": "var(--gray-a3)"},
        cursor="pointer",
        on_click=lambda: FactComparisonState.toggle_document(doc_id),
    )


def entity_checkbox(entity: dict) -> rx.Component:
    """Individual entity checkbox."""
    entity_id = entity["id"]
    return rx.hstack(
        rx.checkbox(
            checked=FactComparisonState.selected_entity_ids_str.contains(entity_id),
            on_change=lambda _: FactComparisonState.toggle_entity(entity_id),
        ),
        rx.vstack(
            rx.text(entity["name"], size="2", weight="medium"),
            rx.hstack(
                rx.cond(
                    entity["type"] != "",
                    rx.badge(entity["type"], size="1", variant="outline"),
                    rx.fragment(),
                ),
                rx.text(f"{entity['mentions']} mentions", size="1", color="gray"),
                spacing="1",
            ),
            spacing="0",
            align_items="start",
        ),
        width="100%",
        padding_y="1",
        _hover={"bg": "var(--gray-a3)"},
        cursor="pointer",
        on_click=lambda: FactComparisonState.toggle_entity(entity_id),
    )


def document_selector() -> rx.Component:
    """Document selector panel with toggle."""
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon(
                    rx.cond(
                        FactComparisonState.show_doc_selector,
                        "chevron-down",
                        "chevron-right",
                    ),
                    size=14,
                ),
                rx.icon("folder-open", size=16),
                "Document Selection",
                size="2",
                variant="ghost",
                on_click=FactComparisonState.toggle_doc_selector,
            ),
            rx.spacer(),
            rx.badge(
                FactComparisonState.selection_summary,
                variant="soft",
                size="1",
            ),
            width="100%",
        ),
        rx.cond(
            FactComparisonState.show_doc_selector,
            rx.vstack(
                rx.text(
                    "Select specific documents to compare, or leave empty to analyze all.",
                    size="1",
                    color="gray",
                ),
                rx.hstack(
                    rx.button(
                        rx.icon("square-check", size=14),
                        "Select All",
                        size="1",
                        variant="soft",
                        on_click=FactComparisonState.select_all_documents,
                    ),
                    rx.button(
                        rx.icon("square-x", size=14),
                        "Clear / Use All",
                        size="1",
                        variant="soft",
                        on_click=FactComparisonState.clear_doc_selection,
                    ),
                    spacing="2",
                ),
                rx.card(
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.document_options,
                                doc_checkbox,
                            ),
                            spacing="0",
                            width="100%",
                        ),
                        max_height="200px",
                    ),
                    width="100%",
                    padding="2",
                ),
                spacing="2",
                width="100%",
            ),
            rx.fragment(),
        ),
        width="100%",
        border="1px solid var(--gray-a5)",
        border_radius="md",
        padding="3",
    )


def entity_selector() -> rx.Component:
    """Entity selector panel with search."""
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon(
                    rx.cond(
                        FactComparisonState.show_entity_selector,
                        "chevron-down",
                        "chevron-right",
                    ),
                    size=14,
                ),
                rx.icon("users", size=16),
                "Entity Selection",
                size="2",
                variant="ghost",
                on_click=FactComparisonState.toggle_entity_selector,
            ),
            rx.spacer(),
            rx.badge(
                FactComparisonState.entity_selection_summary,
                variant="soft",
                size="1",
            ),
            width="100%",
        ),
        rx.cond(
            FactComparisonState.show_entity_selector,
            rx.vstack(
                rx.text(
                    "Select specific entities to analyze, or leave empty to analyze top 10 by mentions.",
                    size="1",
                    color="gray",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="Search entities...",
                        value=FactComparisonState.entity_search_query,
                        on_change=FactComparisonState.set_entity_search,
                        width="200px",
                        size="1",
                    ),
                    rx.button(
                        rx.icon("square-x", size=14),
                        "Clear / Use Top 10",
                        size="1",
                        variant="soft",
                        on_click=FactComparisonState.clear_entity_selection,
                    ),
                    spacing="2",
                ),
                rx.card(
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.filtered_entity_options,
                                entity_checkbox,
                            ),
                            spacing="0",
                            width="100%",
                        ),
                        max_height="250px",
                    ),
                    width="100%",
                    padding="2",
                ),
                rx.cond(
                    FactComparisonState.selected_entity_ids.length() > 0,
                    rx.text(
                        f"Selected: {FactComparisonState.selected_entity_ids.length()} entities",
                        size="1",
                        color="blue",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
                width="100%",
            ),
            rx.fragment(),
        ),
        width="100%",
        border="1px solid var(--gray-a5)",
        border_radius="md",
        padding="3",
    )


def overview_tab() -> rx.Component:
    """Tab showing corpus-wide analysis overview."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Entity Fact Analysis", size="5"),
            # Cache indicator
            rx.cond(
                FactComparisonState.results_from_cache,
                rx.tooltip(
                    rx.badge(
                        rx.icon("database", size=12),
                        "From Cache",
                        color_scheme="blue",
                        variant="soft",
                        size="1",
                    ),
                    content=rx.cond(
                        FactComparisonState.cache_expires_at != "",
                        f"Cached results (expires: {FactComparisonState.cache_expires_at})",
                        "Using cached results",
                    ),
                ),
                rx.fragment(),
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.icon("play"),
                    "Run Analysis",
                    on_click=lambda: FactComparisonState.run_corpus_analysis(False),
                    loading=FactComparisonState.is_loading,
                    variant="solid",
                ),
                rx.button(
                    rx.icon("refresh-cw", size=16),
                    "Force Re-Analysis",
                    on_click=lambda: FactComparisonState.run_corpus_analysis(True),
                    loading=FactComparisonState.is_loading,
                    variant="outline",
                    color_scheme="orange",
                ),
                spacing="2",
            ),
            width="100%",
        ),
        rx.text(
            "Analyzes factual claims about selected entities to find agreements and conflicts.",
            color="gray",
            size="2",
        ),
        # Document selector
        document_selector(),
        # Entity selector
        entity_selector(),
        rx.grid(
            stat_card(
                "Entities Analyzed",
                FactComparisonState.total_entities_analyzed,
                "users",
                "blue",
                on_click=lambda: FactComparisonState.open_stats_modal("entities"),
            ),
            stat_card(
                "Facts Found",
                FactComparisonState.total_facts_found,
                "file-text",
                "purple",
                on_click=lambda: FactComparisonState.open_stats_modal("facts"),
            ),
            stat_card(
                "Confirmations",
                FactComparisonState.total_confirmations,
                "circle-check",
                "green",
                on_click=lambda: FactComparisonState.open_stats_modal("confirmations"),
            ),
            stat_card(
                "Conflicts",
                FactComparisonState.total_conflicts,
                "triangle-alert",
                "red",
                on_click=lambda: FactComparisonState.open_stats_modal("conflicts"),
            ),
            columns="4",
            spacing="4",
            width="100%",
        ),
        rx.cond(
            FactComparisonState.entity_analyses.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell(
                            rx.hstack(
                                rx.text("Entity"),
                                rx.cond(
                                    FactComparisonState.sort_column == "entity_name",
                                    rx.icon(
                                        rx.cond(
                                            FactComparisonState.sort_ascending,
                                            "arrow-up",
                                            "arrow-down",
                                        ),
                                        size=12,
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                cursor="pointer",
                            ),
                            on_click=lambda: FactComparisonState.set_sort(
                                "entity_name"
                            ),
                        ),
                        rx.table.column_header_cell(
                            rx.hstack(
                                rx.text("Facts"),
                                rx.cond(
                                    FactComparisonState.sort_column == "total_facts",
                                    rx.icon(
                                        rx.cond(
                                            FactComparisonState.sort_ascending,
                                            "arrow-up",
                                            "arrow-down",
                                        ),
                                        size=12,
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                cursor="pointer",
                            ),
                            on_click=lambda: FactComparisonState.set_sort(
                                "total_facts"
                            ),
                        ),
                        rx.table.column_header_cell(
                            rx.hstack(
                                rx.text("Confirmed"),
                                rx.cond(
                                    FactComparisonState.sort_column == "confirmations",
                                    rx.icon(
                                        rx.cond(
                                            FactComparisonState.sort_ascending,
                                            "arrow-up",
                                            "arrow-down",
                                        ),
                                        size=12,
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                cursor="pointer",
                            ),
                            on_click=lambda: FactComparisonState.set_sort(
                                "confirmations"
                            ),
                        ),
                        rx.table.column_header_cell(
                            rx.hstack(
                                rx.text("Conflicts"),
                                rx.cond(
                                    FactComparisonState.sort_column == "conflicts",
                                    rx.icon(
                                        rx.cond(
                                            FactComparisonState.sort_ascending,
                                            "arrow-up",
                                            "arrow-down",
                                        ),
                                        size=12,
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1",
                                cursor="pointer",
                            ),
                            on_click=lambda: FactComparisonState.set_sort("conflicts"),
                        ),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        FactComparisonState.sorted_entity_analyses, entity_analysis_row
                    )
                ),
                width="100%",
            ),
            rx.cond(
                FactComparisonState.is_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Analyzing corpus...", color="gray"),
                        spacing="2",
                    ),
                    padding="8",
                ),
                rx.callout(
                    "Click 'Run Analysis' to analyze facts across top entities.",
                    icon="info",
                ),
            ),
        ),
        spacing="4",
        width="100%",
        on_mount=FactComparisonState.load_documents,
    )


def detail_tab() -> rx.Component:
    """Tab showing detailed fact analysis for selected entity."""
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon("arrow-left", size=14),
                "Back",
                variant="ghost",
                on_click=FactComparisonState.clear_selection,
            ),
            rx.heading(
                f"Fact Analysis: {FactComparisonState.selected_entity_name}",
                size="5",
            ),
            width="100%",
        ),
        rx.cond(
            FactComparisonState.is_analyzing_entity,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Extracting and comparing facts...", color="gray"),
                    spacing="2",
                ),
                padding="8",
            ),
            rx.vstack(
                # Summary stats
                rx.grid(
                    stat_card(
                        "Facts Extracted",
                        FactComparisonState.facts_count,
                        "file-text",
                        "blue",
                    ),
                    stat_card(
                        "Confirmations",
                        FactComparisonState.confirmations_count,
                        "circle-check",
                        "green",
                    ),
                    stat_card(
                        "Conflicts",
                        FactComparisonState.conflicts_count,
                        "triangle-alert",
                        "red",
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                # Conflicts section
                rx.cond(
                    FactComparisonState.conflicting.length() > 0,
                    rx.vstack(
                        rx.heading("Conflicts Detected", size="4", color="red"),
                        rx.foreach(
                            FactComparisonState.conflicting,
                            lambda rel, idx: conflict_card(rel, idx),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Corroborations section
                rx.cond(
                    FactComparisonState.corroborating.length() > 0,
                    rx.vstack(
                        rx.heading("Corroborated Facts", size="4", color="green"),
                        rx.foreach(
                            FactComparisonState.corroborating,
                            lambda rel, idx: corroboration_card(rel, idx),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # All facts
                rx.vstack(
                    rx.heading("All Extracted Facts", size="4"),
                    rx.grid(
                        rx.foreach(
                            FactComparisonState.facts,
                            lambda fact, index: fact_card(fact, index),
                        ),
                        columns="2",
                        spacing="3",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="6",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


def stats_detail_modal() -> rx.Component:
    """Modal showing detailed stats lists."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("list", size=20),
                    rx.match(
                        FactComparisonState.stats_modal_type,
                        ("entities", rx.text("Entities Analyzed")),
                        ("facts", rx.text("All Facts")),
                        ("confirmations", rx.text("Corroborated Facts")),
                        ("conflicts", rx.text("Conflicting Facts")),
                        rx.text("Details"),
                    ),
                    spacing="2",
                ),
            ),
            rx.scroll_area(
                rx.match(
                    FactComparisonState.stats_modal_type,
                    # Entities list
                    (
                        "entities",
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.entity_analyses,
                                lambda a: rx.hstack(
                                    rx.text(a.entity_name, weight="medium"),
                                    rx.spacer(),
                                    rx.badge(f"{a.total_facts} facts", variant="soft"),
                                    rx.badge(
                                        f"{a.confirmations}",
                                        color_scheme="green",
                                        size="1",
                                    ),
                                    rx.badge(
                                        f"{a.conflicts}",
                                        color_scheme="red",
                                        size="1",
                                    ),
                                    width="100%",
                                    padding="2",
                                    _hover={"bg": "var(--gray-3)"},
                                ),
                            ),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    # All facts list - using aggregated data
                    (
                        "facts",
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.all_facts_aggregated,
                                lambda fact: rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(
                                                fact["category"],
                                                color_scheme=rx.match(
                                                    fact["category"],
                                                    ("financial", "blue"),
                                                    ("temporal", "green"),
                                                    ("location", "purple"),
                                                    ("relationship", "orange"),
                                                    ("quantitative", "cyan"),
                                                    "gray",
                                                ),
                                                size="1",
                                            ),
                                            rx.badge(
                                                fact["entity_name"],
                                                variant="outline",
                                                size="1",
                                            ),
                                            rx.text(
                                                fact["doc_title"],
                                                size="1",
                                                color="gray",
                                            ),
                                            spacing="2",
                                        ),
                                        rx.text(fact["claim"], size="2"),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="2",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),
                    # Confirmations list - using aggregated data
                    (
                        "confirmations",
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.all_corroborations_aggregated,
                                lambda rel: rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(
                                                rel["entity_name"],
                                                variant="outline",
                                                size="1",
                                            ),
                                            rx.badge(
                                                rel["reliability"],
                                                color_scheme=rx.match(
                                                    rel["reliability"],
                                                    ("High", "green"),
                                                    ("Medium", "yellow"),
                                                    "orange",
                                                ),
                                                size="1",
                                            ),
                                            spacing="2",
                                        ),
                                        rx.text(rel["explanation"], size="2"),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="2",
                                    style={"border-left": "3px solid var(--green-8)"},
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),
                    # Conflicts list - using aggregated data
                    (
                        "conflicts",
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.all_conflicts_aggregated,
                                lambda rel: rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(
                                                rel["entity_name"],
                                                variant="outline",
                                                size="1",
                                            ),
                                            rx.badge(
                                                rel["severity"],
                                                color_scheme=rx.match(
                                                    rel["severity"],
                                                    ("High", "red"),
                                                    ("Medium", "orange"),
                                                    "yellow",
                                                ),
                                                size="1",
                                            ),
                                            spacing="2",
                                        ),
                                        rx.text(rel["explanation"], size="2"),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="2",
                                    style={"border-left": "3px solid var(--red-8)"},
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),
                    rx.text("No data available", color="gray"),
                ),
                max_height="400px",
                padding="4",
            ),
            rx.dialog.close(
                rx.button("Close", variant="soft"),
            ),
            max_width="600px",
        ),
        open=FactComparisonState.stats_modal_open,
        on_open_change=FactComparisonState.close_stats_modal,
    )


def fact_detail_modal() -> rx.Component:
    """Modal showing detailed fact information."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("file-text", size=20),
                    rx.text("Fact Details"),
                    spacing="2",
                ),
            ),
            rx.cond(
                FactComparisonState.selected_fact,
                rx.vstack(
                    # Claim
                    rx.box(
                        rx.text("Claim", weight="bold", size="2", color="gray"),
                        rx.text(
                            FactComparisonState.selected_fact.claim,
                            size="3",
                        ),
                        width="100%",
                    ),
                    # Source document - clickable link to document viewer
                    rx.box(
                        rx.text(
                            "Source Document", weight="bold", size="2", color="gray"
                        ),
                        rx.link(
                            rx.hstack(
                                rx.icon("file", size=14),
                                rx.text(
                                    rx.cond(
                                        FactComparisonState.selected_fact.doc_title
                                        != "",
                                        FactComparisonState.selected_fact.doc_title,
                                        f"Document {FactComparisonState.selected_fact.doc_id}",
                                    ),
                                ),
                                rx.icon("external-link", size=12, color="gray"),
                                spacing="1",
                                _hover={"color": "var(--accent-9)"},
                            ),
                            href=f"/document/{FactComparisonState.selected_fact.doc_id}",
                        ),
                        width="100%",
                    ),
                    # Evidence excerpt
                    rx.cond(
                        FactComparisonState.selected_fact.chunk_text != "",
                        rx.box(
                            rx.text(
                                "Evidence Excerpt",
                                weight="bold",
                                size="2",
                                color="gray",
                            ),
                            rx.card(
                                rx.text(
                                    FactComparisonState.selected_fact.chunk_text,
                                    size="2",
                                    style={"font_style": "italic"},
                                ),
                                padding="3",
                                style={"background": "var(--gray-3)"},
                            ),
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Metadata badges
                    rx.hstack(
                        rx.badge(
                            FactComparisonState.selected_fact.category,
                            color_scheme=rx.match(
                                FactComparisonState.selected_fact.category,
                                ("Date", "blue"),
                                ("Location", "green"),
                                ("Relationship", "purple"),
                                ("Amount", "yellow"),
                                ("Event", "orange"),
                                ("Role", "cyan"),
                                "gray",
                            ),
                        ),
                        rx.badge(
                            FactComparisonState.selected_fact.reliability,
                            color_scheme=rx.match(
                                FactComparisonState.selected_fact.reliability,
                                ("High", "green"),
                                ("Medium", "yellow"),
                                "gray",
                            ),
                        ),
                        rx.text(
                            f"Chunk #{FactComparisonState.selected_fact.chunk_id}",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                    ),
                    spacing="4",
                    width="100%",
                    padding="4",
                ),
                rx.text("No fact selected", color="gray"),
            ),
            rx.dialog.close(
                rx.button("Close", variant="soft"),
            ),
            max_width="600px",
        ),
        open=FactComparisonState.fact_modal_open,
        on_open_change=FactComparisonState.close_fact_modal,
    )


def relation_detail_modal() -> rx.Component:
    """Modal showing corroboration/conflict details with related facts."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.cond(
                        FactComparisonState.selected_relation_type == "corroboration",
                        rx.icon("circle-check", size=20, color="green"),
                        rx.icon("triangle-alert", size=20, color="red"),
                    ),
                    rx.match(
                        FactComparisonState.selected_relation_type,
                        ("corroboration", rx.text("Corroborating Facts")),
                        ("conflict", rx.text("Conflicting Facts")),
                        rx.text("Relation Details"),
                    ),
                    spacing="2",
                ),
            ),
            rx.cond(
                FactComparisonState.selected_relation,
                rx.vstack(
                    # Explanation
                    rx.box(
                        rx.text("Explanation", weight="bold", size="2", color="gray"),
                        rx.text(
                            FactComparisonState.selected_relation.explanation,
                            size="3",
                        ),
                        width="100%",
                    ),
                    # Severity/Reliability badge
                    rx.hstack(
                        rx.cond(
                            FactComparisonState.selected_relation_type == "conflict",
                            rx.badge(
                                FactComparisonState.selected_relation.severity,
                                color_scheme=rx.match(
                                    FactComparisonState.selected_relation.severity,
                                    ("High", "red"),
                                    ("Medium", "orange"),
                                    "yellow",
                                ),
                            ),
                            rx.badge(
                                FactComparisonState.selected_relation.reliability,
                                color_scheme=rx.match(
                                    FactComparisonState.selected_relation.reliability,
                                    ("High", "green"),
                                    ("Medium", "yellow"),
                                    "orange",
                                ),
                            ),
                        ),
                        spacing="2",
                    ),
                    # Related facts header
                    rx.separator(margin_y="3"),
                    rx.text("Related Facts", weight="bold", size="2", color="gray"),
                    rx.text(
                        "Click a fact to view details",
                        size="1",
                        color="gray",
                        style={"font_style": "italic"},
                    ),
                    # Related facts - clickable cards
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                FactComparisonState.related_facts_for_modal,
                                lambda fact_data: rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(
                                                f"#{fact_data['index']}", size="1"
                                            ),
                                            rx.badge(
                                                fact_data["category"],
                                                color_scheme=rx.match(
                                                    fact_data["category"],
                                                    ("financial", "blue"),
                                                    ("temporal", "green"),
                                                    ("location", "purple"),
                                                    ("relationship", "orange"),
                                                    ("quantitative", "cyan"),
                                                    "gray",
                                                ),
                                                size="1",
                                            ),
                                            rx.spacer(),
                                            rx.link(
                                                rx.hstack(
                                                    rx.text(
                                                        fact_data["doc_title"],
                                                        size="1",
                                                        color="gray",
                                                    ),
                                                    rx.icon("external-link", size=10),
                                                    spacing="1",
                                                ),
                                                href=f"/document/{fact_data['doc_id']}",
                                                size="1",
                                            ),
                                            spacing="2",
                                            width="100%",
                                        ),
                                        rx.text(fact_data["claim"], size="2"),
                                        rx.cond(
                                            fact_data["chunk_text"] != "",
                                            rx.text(
                                                fact_data["chunk_text"],
                                                size="1",
                                                color="gray",
                                                style={"font_style": "italic"},
                                            ),
                                            rx.fragment(),
                                        ),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="2",
                                    cursor="pointer",
                                    _hover={
                                        "background": "var(--gray-3)",
                                        "border-color": "var(--accent-8)",
                                    },
                                    on_click=lambda: FactComparisonState.open_fact_modal(
                                        fact_data["index"]
                                    ),
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        max_height="300px",
                    ),
                    spacing="3",
                    width="100%",
                    padding="4",
                ),
                rx.text("No relation selected", color="gray"),
            ),
            rx.dialog.close(
                rx.button("Close", variant="soft"),
            ),
            max_width="700px",
        ),
        open=FactComparisonState.relation_modal_open,
        on_open_change=FactComparisonState.close_relation_modal,
    )


def fact_comparison_page() -> rx.Component:
    """Main Fact Comparison page."""
    return rx.fragment(
        rx.hstack(
            sidebar(),
            rx.vstack(
                rx.heading("Cross-Document Fact Comparison", size="8"),
                rx.text(
                    "Identify corroborating and conflicting facts across your document corpus.",
                    color="gray",
                ),
                rx.cond(
                    FactComparisonState.has_selection,
                    detail_tab(),
                    overview_tab(),
                ),
                padding="2em",
                width="100%",
                align_items="start",
            ),
            width="100%",
            height="100vh",
            # Don't auto-start analysis on mount - user must click "Run Analysis"
        ),
        # Modals
        fact_detail_modal(),
        relation_detail_modal(),
        stats_detail_modal(),
    )
