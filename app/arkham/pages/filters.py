"""
Advanced Filtering Page

Cross-page filtering for documents and entities.
"""

import reflex as rx
from app.arkham.state.filter_state import FilterState
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


def filter_chip(label: str, selected: bool, on_click) -> rx.Component:
    """Toggleable filter chip."""
    return rx.box(
        rx.hstack(
            rx.cond(
                selected,
                rx.icon("check", size=12),
                rx.fragment(),
            ),
            rx.text(label, size="1"),
            spacing="1",
        ),
        padding="2",
        border_radius="full",
        bg=rx.cond(selected, "var(--blue-9)", "var(--gray-3)"),
        color=rx.cond(selected, "white", "inherit"),
        cursor="pointer",
        on_click=on_click,
        _hover={"opacity": 0.8},
    )


def document_filters() -> rx.Component:
    """Document filter panel."""
    return rx.card(
        rx.vstack(
            rx.heading("Document Filters", size="4"),
            rx.divider(),
            # File types
            rx.vstack(
                rx.text("File Types", size="2", weight="bold"),
                rx.cond(
                    FilterState.available_file_types.length() > 0,
                    rx.flex(
                        rx.foreach(
                            FilterState.available_file_types,
                            lambda ft: filter_chip(
                                ft,
                                FilterState.selected_file_types.contains(ft),
                                lambda: FilterState.toggle_file_type(ft),
                            ),
                        ),
                        wrap="wrap",
                        spacing="2",
                    ),
                    rx.text("No file types available", size="1", color="gray"),
                ),
                spacing="1",
                align_items="start",
            ),
            # Date range
            rx.vstack(
                rx.text("Date Range", size="2", weight="bold"),
                rx.hstack(
                    rx.input(
                        type="date",
                        value=FilterState.date_from,
                        on_change=FilterState.set_date_from,
                        placeholder="From",
                    ),
                    rx.text("to", size="1", color="gray"),
                    rx.input(
                        type="date",
                        value=FilterState.date_to,
                        on_change=FilterState.set_date_to,
                        placeholder="To",
                    ),
                    spacing="2",
                ),
                spacing="1",
                align_items="start",
            ),
            # Text search
            rx.vstack(
                rx.text("Filename Search", size="2", weight="bold"),
                rx.input(
                    placeholder="Search filenames...",
                    value=FilterState.doc_search,
                    on_change=FilterState.set_doc_search,
                    width="100%",
                ),
                spacing="1",
                align_items="start",
                width="100%",
            ),
            # Has entities
            rx.vstack(
                rx.text("Has Entities", size="2", weight="bold"),
                rx.select(
                    ["any", "yes", "no"],
                    placeholder="Any",
                    value=FilterState.has_entities_filter,
                    on_change=FilterState.set_has_entities_filter,
                ),
                spacing="1",
                align_items="start",
            ),
            # Min chunks
            rx.vstack(
                rx.text("Minimum Chunks", size="2", weight="bold"),
                rx.input(
                    type="number",
                    placeholder="0",
                    value=FilterState.min_chunks,
                    on_change=FilterState.set_min_chunks,
                    width="100px",
                ),
                spacing="1",
                align_items="start",
            ),
            # Apply button
            rx.button(
                rx.icon("filter", size=14),
                "Apply Filters",
                width="100%",
                on_click=FilterState.apply_document_filters,
                loading=FilterState.is_loading,
            ),
            spacing="4",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def entity_filters() -> rx.Component:
    """Entity filter panel."""
    return rx.card(
        rx.vstack(
            rx.heading("Entity Filters", size="4"),
            rx.divider(),
            # Entity types
            rx.vstack(
                rx.text("Entity Types", size="2", weight="bold"),
                rx.cond(
                    FilterState.available_entity_types.length() > 0,
                    rx.flex(
                        rx.foreach(
                            FilterState.available_entity_types,
                            lambda et: filter_chip(
                                et,
                                FilterState.selected_entity_types.contains(et),
                                lambda: FilterState.toggle_entity_type(et),
                            ),
                        ),
                        wrap="wrap",
                        spacing="2",
                    ),
                    rx.text("No entity types available", size="1", color="gray"),
                ),
                spacing="1",
                align_items="start",
            ),
            # Mention range
            rx.vstack(
                rx.text("Mention Count", size="2", weight="bold"),
                rx.hstack(
                    rx.input(
                        type="number",
                        placeholder="Min",
                        value=FilterState.min_mentions,
                        on_change=FilterState.set_min_mentions,
                        width="80px",
                    ),
                    rx.text("to", size="1", color="gray"),
                    rx.input(
                        type="number",
                        placeholder="Max",
                        value=FilterState.max_mentions,
                        on_change=FilterState.set_max_mentions,
                        width="80px",
                    ),
                    spacing="2",
                ),
                rx.text(f"Range: {FilterState.mentions_range}", size="1", color="gray"),
                spacing="1",
                align_items="start",
            ),
            # Has relationships
            rx.vstack(
                rx.text("Has Relationships", size="2", weight="bold"),
                rx.select(
                    ["any", "yes", "no"],
                    placeholder="Any",
                    value=FilterState.has_relationships_filter,
                    on_change=FilterState.set_has_relationships_filter,
                ),
                spacing="1",
                align_items="start",
            ),
            # Text search
            rx.vstack(
                rx.text("Name Search", size="2", weight="bold"),
                rx.input(
                    placeholder="Search entities...",
                    value=FilterState.entity_search,
                    on_change=FilterState.set_entity_search,
                    width="100%",
                ),
                spacing="1",
                align_items="start",
                width="100%",
            ),
            # Apply button
            rx.button(
                rx.icon("filter", size=14),
                "Apply Filters",
                width="100%",
                on_click=FilterState.apply_entity_filters,
                loading=FilterState.is_loading,
            ),
            spacing="4",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def document_result(doc) -> rx.Component:
    """Document result row."""
    return rx.hstack(
        rx.icon("file-text", size=16),
        rx.text(doc.filename, weight="medium", size="2"),
        rx.badge(doc.file_type, size="1", variant="outline"),
        rx.badge(f"{doc.chunk_count} chunks", size="1", variant="soft"),
        rx.badge(
            f"{doc.entity_count} entities",
            size="1",
            variant="soft",
            color_scheme="green",
        ),
        rx.spacer(),
        rx.text(doc.created_at, size="1", color="gray"),
        width="100%",
        padding="3",
        border_bottom="1px solid var(--gray-4)",
    )


def entity_result(entity) -> rx.Component:
    """Entity result row."""
    return rx.hstack(
        rx.icon("user", size=16),
        rx.text(entity.name, weight="medium", size="2"),
        rx.badge(entity.type, size="1", variant="outline"),
        rx.badge(f"{entity.mentions} mentions", size="1", variant="soft"),
        rx.badge(
            f"{entity.relationship_count} rels",
            size="1",
            variant="soft",
            color_scheme="purple",
        ),
        rx.spacer(),
        rx.cond(
            entity.aliases.length() > 0,
            rx.text(f"Aliases: {entity.aliases.length()}", size="1", color="gray"),
            rx.fragment(),
        ),
        width="100%",
        padding="3",
        border_bottom="1px solid var(--gray-4)",
    )


def filter_page() -> rx.Component:
    """Main Advanced Filtering page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Advanced Filters", size="8"),
                    rx.text(
                        "Filter and explore documents and entities.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.cond(
                    FilterState.filter_count > 0,
                    rx.hstack(
                        rx.badge(
                            f"{FilterState.filter_count} active filters",
                            color_scheme="blue",
                        ),
                        rx.button(
                            rx.icon("x", size=14),
                            "Clear All",
                            variant="ghost",
                            size="1",
                            on_click=FilterState.clear_all_filters,
                        ),
                        spacing="2",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card("Documents", FilterState.doc_total, "file-text", "blue"),
                stat_card(
                    "Active Filters", FilterState.filter_count, "filter", "purple"
                ),
                stat_card(
                    "Results",
                    rx.cond(
                        FilterState.active_tab == "documents",
                        FilterState.filtered_documents.length(),
                        FilterState.filtered_entities.length(),
                    ),
                    "list",
                    "green",
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            # Main content
            rx.grid(
                # Filter panels
                rx.vstack(
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Documents", value="documents"),
                            rx.tabs.trigger("Entities", value="entities"),
                        ),
                        rx.tabs.content(
                            document_filters(), value="documents", padding_top="4"
                        ),
                        rx.tabs.content(
                            entity_filters(), value="entities", padding_top="4"
                        ),
                        value=FilterState.active_tab,
                        on_change=FilterState.set_active_tab,
                        width="100%",
                    ),
                    width="100%",
                ),
                # Results panel
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading("Results", size="4"),
                            rx.spacer(),
                            rx.badge(
                                rx.cond(
                                    FilterState.active_tab == "documents",
                                    f"{FilterState.filtered_documents.length()} documents",
                                    f"{FilterState.filtered_entities.length()} entities",
                                ),
                                size="1",
                            ),
                            width="100%",
                        ),
                        rx.divider(),
                        rx.cond(
                            FilterState.is_loading,
                            rx.center(
                                rx.spinner(size="3"),
                                padding="8",
                            ),
                            rx.cond(
                                FilterState.active_tab == "documents",
                                rx.cond(
                                    FilterState.filtered_documents.length() > 0,
                                    rx.vstack(
                                        rx.foreach(
                                            FilterState.filtered_documents,
                                            document_result,
                                        ),
                                        spacing="0",
                                        width="100%",
                                        max_height="400px",
                                        overflow_y="auto",
                                    ),
                                    rx.text(
                                        "Apply filters to see document results",
                                        size="2",
                                        color="gray",
                                    ),
                                ),
                                rx.cond(
                                    FilterState.filtered_entities.length() > 0,
                                    rx.vstack(
                                        rx.foreach(
                                            FilterState.filtered_entities,
                                            entity_result,
                                        ),
                                        spacing="0",
                                        width="100%",
                                        max_height="400px",
                                        overflow_y="auto",
                                    ),
                                    rx.text(
                                        "Apply filters to see entity results",
                                        size="2",
                                        color="gray",
                                    ),
                                ),
                            ),
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
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=FilterState.load_options,
        ),
        width="100%",
        height="100vh",
    )
