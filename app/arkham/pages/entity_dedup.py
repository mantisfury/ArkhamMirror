"""
Entity Deduplication Page

Provides UI for:
- Viewing duplicate entity candidates
- Manual entity merging
- Adding custom aliases
- Reviewing automatic deduplication results
"""

import reflex as rx
from typing import Dict, Any
from ..components.layout import layout
from ..state.entity_dedup_state import EntityDedupState
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING


def stats_card() -> rx.Component:
    """Statistics card showing deduplication progress."""
    return rx.card(
        rx.vstack(
            rx.heading("Deduplication Statistics", size="5"),
            rx.divider(),
            rx.hstack(
                rx.vstack(
                    rx.text("Total Entities", size="2", color="gray.11"),
                    rx.heading(
                        EntityDedupState.stats.get("total_entities", 0),
                        size="6",
                    ),
                    spacing=SPACING["xs"],
                    align="center",
                ),
                rx.vstack(
                    rx.text("Linked", size="2", color="gray.11"),
                    rx.heading(
                        EntityDedupState.stats.get("linked_entities", 0),
                        size="6",
                        color="green",
                    ),
                    spacing=SPACING["xs"],
                    align="center",
                ),
                rx.vstack(
                    rx.text("Unlinked", size="2", color="gray.11"),
                    rx.heading(
                        EntityDedupState.stats.get("unlinked_entities", 0),
                        size="6",
                        color="orange",
                    ),
                    spacing=SPACING["xs"],
                    align="center",
                ),
                rx.vstack(
                    rx.text("Canonical", size="2", color="gray.11"),
                    rx.heading(
                        EntityDedupState.stats.get("total_canonicals", 0),
                        size="6",
                        color="blue",
                    ),
                    spacing=SPACING["xs"],
                    align="center",
                ),
                rx.vstack(
                    rx.text("Link Rate", size="2", color="gray.11"),
                    rx.heading(
                        f"{EntityDedupState.stats.get('link_rate', 0)}%",
                        size="6",
                    ),
                    spacing=SPACING["xs"],
                    align="center",
                ),
                spacing=SPACING["lg"],
                width="100%",
                justify="between",
            ),
            # By label breakdown - simplified, no dict iteration for now
            # (Reflex state dicts don't support .items() in component context)
            spacing=SPACING["md"],
            width="100%",
        ),
        padding=CARD_PADDING,
        width="100%",
    )


def filters_bar() -> rx.Component:
    """Filter controls for candidates."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text("Entity Type", size="2", weight="bold"),
                rx.select(
                    EntityDedupState.available_labels,
                    value=EntityDedupState.label_filter,
                    on_change=EntityDedupState.set_label_filter,
                    size="2",
                ),
                spacing=SPACING["xs"],
            ),
            rx.vstack(
                rx.text("Min Similarity", size="2", weight="bold"),
                rx.text(
                    f"{EntityDedupState.min_similarity:.2f}",
                    size="2",
                    color="gray.10",
                ),
                spacing=SPACING["xs"],
            ),
            rx.vstack(
                rx.text("Filters", size="2", weight="bold"),
                rx.checkbox(
                    "Auto-matches only",
                    checked=EntityDedupState.show_auto_matches_only,
                    on_change=EntityDedupState.toggle_auto_matches_only,
                ),
                spacing=SPACING["xs"],
            ),
            rx.spacer(),
            rx.button(
                rx.icon(tag="refresh-cw", size=16),
                "Reload",
                on_click=EntityDedupState.load_candidates,
                size="2",
                variant="soft",
            ),
            spacing=SPACING["md"],
            align="end",
            width="100%",
        ),
        padding=CARD_PADDING,
        width="100%",
    )


def candidate_row(candidate: Dict) -> rx.Component:
    """A row showing a duplicate candidate pair."""
    return rx.card(
        rx.hstack(
            # Entity 1
            rx.vstack(
                rx.text(candidate["name1"], size="3", weight="bold"),
                rx.hstack(
                    rx.badge(candidate["label"], size="1", variant="soft"),
                    rx.text(
                        f"{candidate['mentions1']} mentions",
                        size="1",
                        color="gray.11",
                    ),
                    spacing=SPACING["xs"],
                ),
                rx.cond(
                    candidate.get("aliases1", []) != [],
                    rx.badge(
                        "Has aliases",
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                    ),
                    rx.fragment(),
                ),
                spacing=SPACING["xs"],
                flex="1",
            ),
            # Arrow and similarity
            rx.vstack(
                rx.icon(tag="arrow-left-right", size=24, color="gray.10"),
                rx.cond(
                    candidate.get("is_auto_match", False),
                    rx.badge(
                        f"{candidate['similarity']:.0%}",
                        size="2",
                        color_scheme="blue",
                        variant="solid",
                    ),
                    rx.badge(
                        f"{candidate['similarity']:.0%}",
                        size="2",
                        color_scheme="gray",
                        variant="soft",
                    ),
                ),
                rx.cond(
                    candidate.get("is_auto_match", False),
                    rx.text("Auto", size="1", color="blue.11"),
                    rx.fragment(),
                ),
                spacing=SPACING["xs"],
                align="center",
            ),
            # Entity 2
            rx.vstack(
                rx.text(candidate["name2"], size="3", weight="bold"),
                rx.hstack(
                    rx.badge(candidate["label"], size="1", variant="soft"),
                    rx.text(
                        f"{candidate['mentions2']} mentions",
                        size="1",
                        color="gray.11",
                    ),
                    spacing=SPACING["xs"],
                ),
                rx.cond(
                    candidate.get("aliases2", []) != [],
                    rx.badge(
                        "Has aliases",
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                    ),
                    rx.fragment(),
                ),
                spacing=SPACING["xs"],
                flex="1",
            ),
            # Actions
            rx.vstack(
                rx.button(
                    "Review",
                    on_click=lambda: EntityDedupState.select_pair(
                        candidate["id1"], candidate["id2"]
                    ),
                    size="2",
                    variant="soft",
                ),
                rx.button(
                    rx.icon(tag="x", size=16),
                    "Dismiss",
                    on_click=lambda: EntityDedupState.dismiss_pair(
                        candidate["id1"], candidate["id2"]
                    ),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                ),
                spacing=SPACING["xs"],
            ),
            spacing=SPACING["md"],
            align="center",
            width="100%",
        ),
        padding=CARD_PADDING,
        width="100%",
    )


def candidates_list() -> rx.Component:
    """List of duplicate candidates."""
    return rx.vstack(
        rx.heading("Duplicate Candidates", size="5"),
        rx.text(
            "Review potential duplicate entity pairs below",
            size="2",
            color="gray.11",
        ),
        # Candidates
        rx.cond(
            EntityDedupState.filtered_candidates != [],
            rx.vstack(
                rx.foreach(
                    EntityDedupState.current_page_candidates,
                    candidate_row,
                ),
                # Pagination
                rx.cond(
                    EntityDedupState.total_pages != 1,
                    rx.hstack(
                        rx.button(
                            rx.icon(tag="chevron-left", size=16),
                            "Previous",
                            on_click=EntityDedupState.prev_page,
                            disabled=EntityDedupState.page == 0,
                            size="2",
                            variant="soft",
                        ),
                        rx.text(
                            f"Page {EntityDedupState.page + 1} of {EntityDedupState.total_pages}",
                            size="2",
                            color="gray.11",
                        ),
                        rx.button(
                            "Next",
                            rx.icon(tag="chevron-right", size=16),
                            on_click=EntityDedupState.next_page,
                            disabled=EntityDedupState.page
                            >= EntityDedupState.total_pages - 1,
                            size="2",
                            variant="soft",
                        ),
                        spacing=SPACING["md"],
                        justify="center",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            rx.callout(
                "No duplicate candidates found. Try adjusting the filters.",
                icon="info",
                color_scheme="blue",
                width="100%",
            ),
        ),
        spacing=SPACING["md"],
        width="100%",
    )


def entity_details_card_1() -> rx.Component:
    """Detailed view of entity 1."""
    return rx.card(
        rx.vstack(
            rx.heading("Entity 1", size="4"),
            rx.divider(),
            # Basic info
            rx.vstack(
                rx.text("Canonical Name", size="2", weight="bold"),
                rx.text(EntityDedupState.entity1_canonical_name, size="3"),
                spacing=SPACING["xs"],
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Type", size="2", weight="bold"),
                    rx.badge(EntityDedupState.entity1_label, size="2"),
                    spacing=SPACING["xs"],
                ),
                rx.vstack(
                    rx.text("Total Mentions", size="2", weight="bold"),
                    rx.text(EntityDedupState.entity1_total_mentions, size="2"),
                    spacing=SPACING["xs"],
                ),
                rx.vstack(
                    rx.text("Documents", size="2", weight="bold"),
                    rx.text(EntityDedupState.entity1_document_count, size="2"),
                    spacing=SPACING["xs"],
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            # Aliases - just show if they exist
            rx.cond(
                EntityDedupState.entity1_has_aliases,
                rx.text("Has custom aliases", size="1", color="gray.10"),
                rx.fragment(),
            ),
            # Mention variations
            rx.cond(
                EntityDedupState.entity1_has_mentions,
                rx.text("Has mention variations", size="1", color="gray.10"),
                rx.fragment(),
            ),
            # Geospatial if available
            rx.cond(
                EntityDedupState.entity1_has_location,
                rx.vstack(
                    rx.text("Location", size="2", weight="bold"),
                    rx.text(
                        EntityDedupState.entity1_location_text,
                        size="2",
                        color="gray.11",
                    ),
                    rx.cond(
                        EntityDedupState.entity1_has_address,
                        rx.text(
                            EntityDedupState.entity1_resolved_address,
                            size="1",
                            color="gray.10",
                        ),
                        rx.fragment(),
                    ),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing=SPACING["md"],
            width="100%",
        ),
        padding=CARD_PADDING,
        width="100%",
    )


def entity_details_card_2() -> rx.Component:
    """Detailed view of entity 2."""
    return rx.card(
        rx.vstack(
            rx.heading("Entity 2", size="4"),
            rx.divider(),
            # Basic info
            rx.vstack(
                rx.text("Canonical Name", size="2", weight="bold"),
                rx.text(EntityDedupState.entity2_canonical_name, size="3"),
                spacing=SPACING["xs"],
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Type", size="2", weight="bold"),
                    rx.badge(EntityDedupState.entity2_label, size="2"),
                    spacing=SPACING["xs"],
                ),
                rx.vstack(
                    rx.text("Total Mentions", size="2", weight="bold"),
                    rx.text(EntityDedupState.entity2_total_mentions, size="2"),
                    spacing=SPACING["xs"],
                ),
                rx.vstack(
                    rx.text("Documents", size="2", weight="bold"),
                    rx.text(EntityDedupState.entity2_document_count, size="2"),
                    spacing=SPACING["xs"],
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            # Aliases - just show if they exist
            rx.cond(
                EntityDedupState.entity2_has_aliases,
                rx.text("Has custom aliases", size="1", color="gray.10"),
                rx.fragment(),
            ),
            # Mention variations
            rx.cond(
                EntityDedupState.entity2_has_mentions,
                rx.text("Has mention variations", size="1", color="gray.10"),
                rx.fragment(),
            ),
            # Geospatial if available
            rx.cond(
                EntityDedupState.entity2_has_location,
                rx.vstack(
                    rx.text("Location", size="2", weight="bold"),
                    rx.text(
                        EntityDedupState.entity2_location_text,
                        size="2",
                        color="gray.11",
                    ),
                    rx.cond(
                        EntityDedupState.entity2_has_address,
                        rx.text(
                            EntityDedupState.entity2_resolved_address,
                            size="1",
                            color="gray.10",
                        ),
                        rx.fragment(),
                    ),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing=SPACING["md"],
            width="100%",
        ),
        padding=CARD_PADDING,
        width="100%",
    )


def review_modal() -> rx.Component:
    """Modal for reviewing and merging a selected pair."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Review Entity Pair"),
                rx.dialog.description(
                    "Review the details below and choose which entity to keep.",
                ),
                # Loading state
                rx.cond(
                    EntityDedupState.is_loading
                    & (EntityDedupState.entity1_details == None),
                    rx.center(rx.spinner(size="3"), padding="40px", width="100%"),
                    rx.fragment(),
                ),
                # Content (only if not loading or if we have details)
                rx.cond(
                    ~EntityDedupState.is_loading
                    | (EntityDedupState.entity1_details != None),
                    rx.vstack(
                        # Show both entities side by side
                        rx.hstack(
                            rx.cond(
                                EntityDedupState.entity1_details != None,
                                entity_details_card_1(),
                                rx.callout(
                                    "Entity 1 details not found",
                                    icon="triangle-alert",
                                    color_scheme="red",
                                ),
                            ),
                            rx.cond(
                                EntityDedupState.entity2_details != None,
                                entity_details_card_2(),
                                rx.callout(
                                    "Entity 2 details not found",
                                    icon="triangle-alert",
                                    color_scheme="red",
                                ),
                            ),
                            spacing=SPACING["md"],
                            width="100%",
                        ),
                        # Merge actions
                        rx.divider(),
                        rx.hstack(
                            rx.button(
                                "Keep Entity 1, Merge Entity 2",
                                on_click=lambda: EntityDedupState.merge_entities(
                                    EntityDedupState.selected_pair["id1"],
                                    EntityDedupState.selected_pair["id2"],
                                ),
                                size="2",
                                color_scheme="green",
                                disabled=EntityDedupState.is_loading
                                | (EntityDedupState.entity1_details == None)
                                | (EntityDedupState.entity2_details == None),
                            ),
                            rx.button(
                                "Keep Entity 2, Merge Entity 1",
                                on_click=lambda: EntityDedupState.merge_entities(
                                    EntityDedupState.selected_pair["id2"],
                                    EntityDedupState.selected_pair["id1"],
                                ),
                                size="2",
                                color_scheme="blue",
                                disabled=EntityDedupState.is_loading
                                | (EntityDedupState.entity1_details == None)
                                | (EntityDedupState.entity2_details == None),
                            ),
                            rx.spacer(),
                            rx.button(
                                "Close",
                                on_click=EntityDedupState.clear_selection,
                                size="2",
                                variant="soft",
                                color_scheme="gray",
                            ),
                            spacing=SPACING["md"],
                            width="100%",
                        ),
                        spacing=SPACING["md"],
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing=SPACING["md"],
                width="100%",
            ),
            max_width="900px",
        ),
        open=EntityDedupState.selected_pair != None,
        on_open_change=EntityDedupState.clear_selection,
    )


def manual_merge_section() -> rx.Component:
    """Section for manually selecting and merging any two entities."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Manual Merge", size="5"),
            rx.spacer(),
            rx.button(
                rx.icon("undo-2"),
                "Undo Last Merge",
                variant="outline",
                color_scheme="orange",
                on_click=EntityDedupState.unmerge_last,
                loading=EntityDedupState.is_loading,
            ),
            width="100%",
            align="center",
        ),
        rx.text(
            "Search and select any two entities to merge, or delete garbage entities.",
            color="gray",
            size="2",
        ),
        # Search input
        rx.hstack(
            rx.input(
                placeholder="Search entities by name...",
                value=EntityDedupState.manual_search_query,
                on_change=EntityDedupState.search_entities,
                width="100%",
            ),
            rx.button(
                rx.icon("x"),
                variant="ghost",
                on_click=EntityDedupState.clear_manual_selection,
            ),
            width="100%",
        ),
        # Search results
        rx.cond(
            EntityDedupState.manual_search_results.length() > 0,
            rx.card(
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            EntityDedupState.manual_search_results,
                            lambda entity: rx.hstack(
                                rx.vstack(
                                    rx.hstack(
                                        rx.badge(
                                            entity["label"], variant="soft", size="1"
                                        ),
                                        rx.text(entity["name"], weight="medium"),
                                        spacing="2",
                                    ),
                                    rx.text(
                                        f"{entity['mentions']} mentions",
                                        size="1",
                                        color="gray",
                                    ),
                                    align_items="start",
                                    spacing="1",
                                ),
                                rx.spacer(),
                                rx.hstack(
                                    rx.button(
                                        "Select as #1",
                                        size="1",
                                        variant="soft",
                                        color_scheme="blue",
                                        on_click=lambda: EntityDedupState.select_manual_entity1(
                                            entity
                                        ),
                                    ),
                                    rx.button(
                                        "Select as #2",
                                        size="1",
                                        variant="soft",
                                        color_scheme="green",
                                        on_click=lambda: EntityDedupState.select_manual_entity2(
                                            entity
                                        ),
                                    ),
                                    rx.tooltip(
                                        rx.button(
                                            rx.icon("trash-2", size=14),
                                            "Delete Entity",
                                            size="1",
                                            variant="soft",
                                            color_scheme="red",
                                            on_click=lambda: EntityDedupState.delete_entity(
                                                entity["id"], entity["name"]
                                            ),
                                        ),
                                        content="Delete this entity permanently",
                                    ),
                                    spacing="1",
                                ),
                                width="100%",
                                padding="2",
                                padding_right="9",  # Increased padding to clear scrollbar
                                _hover={"bg": "var(--gray-a3)"},
                            ),
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    max_height="300px",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
        # Selected entities
        rx.grid(
            rx.card(
                rx.vstack(
                    rx.text("Entity #1 (to keep)", size="1", color="gray"),
                    rx.cond(
                        EntityDedupState.manual_entity1 != None,
                        rx.vstack(
                            rx.text(
                                EntityDedupState.manual_entity1_name, weight="bold"
                            ),
                            rx.button(
                                "Clear",
                                size="1",
                                variant="ghost",
                                on_click=lambda: EntityDedupState.select_manual_entity1(
                                    None
                                ),
                            ),
                            align_items="start",
                        ),
                        rx.text("Not selected", color="gray", size="2"),
                    ),
                    align_items="start",
                    spacing="2",
                ),
                padding="3",
            ),
            rx.card(
                rx.vstack(
                    rx.text("Entity #2 (to merge/delete)", size="1", color="gray"),
                    rx.cond(
                        EntityDedupState.manual_entity2 != None,
                        rx.vstack(
                            rx.text(
                                EntityDedupState.manual_entity2_name, weight="bold"
                            ),
                            rx.button(
                                "Clear",
                                size="1",
                                variant="ghost",
                                on_click=lambda: EntityDedupState.select_manual_entity2(
                                    None
                                ),
                            ),
                            align_items="start",
                        ),
                        rx.text("Not selected", color="gray", size="2"),
                    ),
                    align_items="start",
                    spacing="2",
                ),
                padding="3",
            ),
            columns="2",
            spacing="3",
            width="100%",
        ),
        # Merge button
        rx.cond(
            EntityDedupState.can_manual_merge,
            rx.hstack(
                rx.button(
                    rx.icon("git-merge"),
                    f"Merge → Keep: {EntityDedupState.manual_entity1_name}",
                    color_scheme="green",
                    on_click=lambda: EntityDedupState.manual_merge(True),
                    loading=EntityDedupState.is_loading,
                ),
                rx.button(
                    rx.icon("git-merge"),
                    f"Merge → Keep: {EntityDedupState.manual_entity2_name}",
                    color_scheme="blue",
                    on_click=lambda: EntityDedupState.manual_merge(False),
                    loading=EntityDedupState.is_loading,
                ),
                spacing="2",
            ),
            rx.fragment(),
        ),
        spacing="4",
        width="100%",
        padding="4",
        background="var(--gray-a2)",
        border_radius="8px",
    )


def entity_dedup_page() -> rx.Component:
    """Entity deduplication page."""
    return layout(
        rx.vstack(
            rx.heading("🔗 Entity Deduplication", size="8"),
            rx.text(
                "Review and merge duplicate entities to improve data quality and relationship accuracy.",
                color="gray.11",
                font_size=FONT_SIZE["sm"],
            ),
            # Messages
            rx.cond(
                EntityDedupState.error_message != "",
                rx.callout(
                    EntityDedupState.error_message,
                    icon="triangle-alert",
                    color_scheme="red",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.cond(
                EntityDedupState.success_message != "",
                rx.callout(
                    EntityDedupState.success_message,
                    icon="check-check",
                    color_scheme="green",
                    width="100%",
                    on_click=EntityDedupState.clear_messages,
                ),
                rx.fragment(),
            ),
            # Statistics
            stats_card(),
            # Tabs for suggested vs manual merge
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Suggested Pairs", value="suggested"),
                    rx.tabs.trigger("Manual Merge", value="manual"),
                ),
                rx.tabs.content(
                    rx.vstack(
                        filters_bar(),
                        rx.cond(
                            EntityDedupState.is_loading,
                            rx.center(
                                rx.spinner(size="3"),
                                padding="40px",
                            ),
                            candidates_list(),
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    value="suggested",
                    padding_top="4",
                ),
                rx.tabs.content(
                    manual_merge_section(),
                    value="manual",
                    padding_top="4",
                ),
                default_value="suggested",
                width="100%",
            ),
            # Review modal
            review_modal(),
            spacing=SPACING["lg"],
            width="100%",
            on_mount=[
                EntityDedupState.clear_selection,
                EntityDedupState.load_candidates,
                EntityDedupState.load_labels,
                EntityDedupState.load_statistics,
                lambda: EntityDedupState.search_entities(""),
            ],
        ),
    )
