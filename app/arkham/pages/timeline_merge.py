"""
Multi-Document Timeline Merging Page

Combined chronological view across documents with
conflict detection and gap analysis.
"""

import reflex as rx
from app.arkham.state.timeline_merge_state import TimelineMergeState
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


def reliability_badge(reliability: str) -> rx.Component:
    """Badge showing reliability level."""
    return rx.badge(
        reliability,
        color_scheme=rx.match(
            reliability,
            ("High", "green"),
            ("Low", "red"),
            "yellow",
        ),
        size="1",
    )


def entity_card(entity) -> rx.Component:
    """Card for entity selection."""
    return rx.hstack(
        rx.avatar(fallback=entity.name[:2].upper(), size="2"),
        rx.vstack(
            rx.text(entity.name, weight="medium", size="2"),
            rx.hstack(
                rx.badge(entity.type, size="1", variant="soft"),
                rx.text(f"{entity.mentions} mentions", size="1", color="gray"),
                spacing="2",
            ),
            align_items="start",
            spacing="0",
            flex="1",
        ),
        rx.button(
            "Analyze",
            size="1",
            variant="solid",
            color_scheme="blue",
            on_click=lambda: TimelineMergeState.analyze_entity_timeline(entity.id),
        ),
        spacing="3",
        padding="3",
        width="100%",
        _hover={"bg": "var(--gray-a3)"},
        border_radius="md",
        align="center",
    )


def event_row(event) -> rx.Component:
    """Row showing a timeline event."""
    return rx.hstack(
        # Date column
        rx.vstack(
            rx.text(event.date, weight="bold", size="2"),
            rx.badge(event.date_precision, size="1", variant="outline"),
            align_items="start",
            min_width="120px",
        ),
        # Event details
        rx.vstack(
            rx.text(event.event, size="2"),
            rx.hstack(
                rx.text("Source:", size="1", color="gray"),
                rx.text(event.source, size="1"),
                reliability_badge(event.confidence),
                spacing="2",
            ),
            rx.cond(
                event.entities_involved.length() > 0,
                rx.hstack(
                    rx.text("Entities:", size="1", color="gray"),
                    rx.foreach(
                        event.entities_involved,
                        lambda e: rx.badge(e, size="1", variant="soft"),
                    ),
                    spacing="1",
                ),
                rx.fragment(),
            ),
            align_items="start",
            spacing="1",
        ),
        spacing="4",
        padding="3",
        width="100%",
        border_left="3px solid var(--blue-7)",
        _hover={"bg": "var(--gray-a3)"},
    )


def conflict_card(conflict) -> rx.Component:
    """Card showing a timeline conflict."""
    return rx.card(
        rx.hstack(
            rx.icon("triangle-alert", size=16, color="var(--orange-9)"),
            rx.vstack(
                rx.hstack(
                    rx.text(conflict.date, weight="bold", size="2"),
                    rx.badge(
                        conflict.type.replace("_", " ").title(),
                        size="1",
                        color_scheme="orange",
                    ),
                    spacing="2",
                ),
                rx.text(conflict.description, size="2"),
                align_items="start",
                spacing="1",
            ),
            spacing="3",
            width="100%",
        ),
        padding="3",
    )


def gap_card(gap) -> rx.Component:
    """Card showing a timeline gap."""
    return rx.card(
        rx.hstack(
            rx.icon("clock", size=16, color="var(--yellow-9)"),
            rx.vstack(
                rx.hstack(
                    rx.text(
                        f"{gap.from_date} → {gap.to_date}", weight="medium", size="2"
                    ),
                    rx.badge(f"{gap.gap_days} days", size="1", variant="outline"),
                    spacing="2",
                ),
                rx.text(gap.description, size="2", color="gray"),
                align_items="start",
                spacing="1",
            ),
            spacing="3",
            width="100%",
        ),
        padding="3",
    )


def entity_panel() -> rx.Component:
    """Panel for entity selection."""
    return rx.card(
        rx.vstack(
            rx.heading("Focus Entity", size="4"),
            rx.text(
                "Optionally focus timeline on a specific entity", size="2", color="gray"
            ),
            rx.divider(),
            rx.button(
                rx.icon("globe", size=14),
                "Analyze Full Corpus",
                width="100%",
                on_click=TimelineMergeState.analyze_corpus_timeline,
            ),
            rx.divider(),
            rx.cond(
                TimelineMergeState.available_entities.length() > 0,
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(TimelineMergeState.available_entities, entity_card),
                        spacing="1",
                        width="100%",
                        padding_right="3",  # Space for scrollbar
                    ),
                    type="always",
                    scrollbars="vertical",
                    style={"max-height": "calc(100vh - 300px)"},
                ),
                rx.text("No entities available", color="gray", size="2"),
            ),
            spacing="3",
            width="100%",
        ),
        padding="4",
        width="400px",
        min_width="350px",
    )


def timeline_view() -> rx.Component:
    """Main timeline view."""
    return rx.vstack(
        rx.cond(
            TimelineMergeState.has_results,
            rx.vstack(
                # Stats
                rx.grid(
                    stat_card(
                        "Events", TimelineMergeState.total_events, "calendar", "blue"
                    ),
                    stat_card(
                        "Sources",
                        TimelineMergeState.sources_count,
                        "file-text",
                        "green",
                    ),
                    stat_card(
                        "Conflicts",
                        TimelineMergeState.conflicts.length(),
                        "triangle-alert",
                        "orange",
                    ),
                    stat_card(
                        "Gaps", TimelineMergeState.gaps.length(), "clock", "yellow"
                    ),
                    columns="4",
                    spacing="4",
                    width="100%",
                ),
                # Focus entity indicator
                rx.cond(
                    TimelineMergeState.entity_focus != "",
                    rx.hstack(
                        rx.icon("user", size=16, color="var(--blue-9)"),
                        rx.text("Focused on: ", size="2", color="gray"),
                        rx.text(
                            TimelineMergeState.entity_focus, size="2", weight="bold"
                        ),
                        spacing="2",
                        align="center",
                        padding="3",
                        background="var(--blue-a3)",
                        border_radius="md",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Tabs for different views
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Timeline", value="timeline"),
                        rx.tabs.trigger("Conflicts", value="conflicts"),
                        rx.tabs.trigger("Gaps", value="gaps"),
                        rx.tabs.trigger("Narrative", value="narrative"),
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.cond(
                                TimelineMergeState.events.length() > 0,
                                rx.vstack(
                                    rx.foreach(TimelineMergeState.events, event_row),
                                    spacing="2",
                                    width="100%",
                                ),
                                rx.text("No events found", color="gray"),
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        value="timeline",
                        padding_top="4",
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.cond(
                                TimelineMergeState.conflicts.length() > 0,
                                rx.vstack(
                                    rx.text(
                                        "These dates have conflicting information from different sources:",
                                        size="2",
                                        color="gray",
                                    ),
                                    rx.foreach(
                                        TimelineMergeState.conflicts, conflict_card
                                    ),
                                    spacing="3",
                                    width="100%",
                                ),
                                rx.callout(
                                    "No conflicts detected - timeline is consistent across sources.",
                                    icon="circle-check",
                                    color="green",
                                ),
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        value="conflicts",
                        padding_top="4",
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.cond(
                                TimelineMergeState.gaps.length() > 0,
                                rx.vstack(
                                    rx.text(
                                        "Significant time periods with no documented events:",
                                        size="2",
                                        color="gray",
                                    ),
                                    rx.foreach(TimelineMergeState.gaps, gap_card),
                                    spacing="3",
                                    width="100%",
                                ),
                                rx.callout(
                                    "No significant gaps detected in the timeline.",
                                    icon="circle-check",
                                    color="green",
                                ),
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        value="gaps",
                        padding_top="4",
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.cond(
                                TimelineMergeState.narrative != "",
                                # Has narrative - show styled content
                                rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.heading("Timeline Narrative", size="4"),
                                            rx.spacer(),
                                            rx.badge(
                                                f"{TimelineMergeState.sources_count} Sources",
                                                color_scheme="blue",
                                                variant="soft",
                                            ),
                                            rx.button(
                                                "Regenerate",
                                                size="1",
                                                variant="outline",
                                                on_click=TimelineMergeState.generate_narrative,
                                                loading=TimelineMergeState.is_analyzing,
                                            ),
                                            width="100%",
                                            align="center",
                                        ),
                                        rx.divider(),
                                        rx.scroll_area(
                                            rx.markdown(
                                                TimelineMergeState.narrative,
                                            ),
                                            type="auto",
                                            scrollbars="vertical",
                                            style={"max-height": "60vh"},
                                        ),
                                        rx.divider(),
                                        rx.hstack(
                                            rx.spacer(),
                                            rx.text(
                                                f"{TimelineMergeState.events.length()} events analyzed",
                                                size="1",
                                                color="gray",
                                            ),
                                            spacing="2",
                                            width="100%",
                                            align="center",
                                        ),
                                        spacing="4",
                                        width="100%",
                                    ),
                                    padding="5",
                                    width="100%",
                                ),
                                # No narrative - show generate prompt
                                rx.center(
                                    rx.vstack(
                                        rx.icon(
                                            "book-open", size=40, color="var(--gray-8)"
                                        ),
                                        rx.text(
                                            "No Narrative Generated",
                                            size="4",
                                            color="gray",
                                        ),
                                        rx.text(
                                            "Generate an AI summary of the timeline.",
                                            size="2",
                                            color="gray",
                                        ),
                                        rx.button(
                                            "Generate Narrative",
                                            size="3",
                                            color_scheme="blue",
                                            on_click=TimelineMergeState.generate_narrative,
                                            loading=TimelineMergeState.is_analyzing,
                                        ),
                                        spacing="3",
                                        align="center",
                                        padding="8",
                                    ),
                                ),
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        value="narrative",
                        padding_top="4",
                    ),
                    default_value="timeline",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            rx.cond(
                TimelineMergeState.is_analyzing,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Analyzing timeline...", color="gray"),
                        rx.text(
                            "Extracting temporal events and detecting conflicts",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="8",
                ),
                rx.callout(
                    "Select an entity or analyze the full corpus to build a merged timeline. "
                    "Timeline analysis extracts dates from documents, merges events chronologically, "
                    "detects conflicts between sources, and identifies gaps in coverage.",
                    icon="calendar",
                    color_scheme="gray",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


def timeline_merge_page() -> rx.Component:
    """Main Timeline Merging page."""
    return rx.hstack(
        sidebar(),
        rx.hstack(
            # Entity panel
            entity_panel(),
            # Main content
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.heading("Timeline Merge", size="8"),
                        rx.text(
                            "Merge and analyze timelines across multiple documents.",
                            color="gray",
                        ),
                        align_items="start",
                    ),
                    rx.spacer(),
                    rx.cond(
                        TimelineMergeState.has_results,
                        rx.button(
                            rx.icon("x"),
                            "Clear",
                            variant="ghost",
                            on_click=TimelineMergeState.clear_results,
                        ),
                        rx.fragment(),
                    ),
                    width="100%",
                    align_items="end",
                ),
                timeline_view(),
                padding="2em",
                width="100%",
                align_items="start",
                spacing="6",
            ),
            spacing="0",
            width="100%",
        ),
        width="100%",
        height="100vh",
        on_mount=TimelineMergeState.load_entities,
    )
