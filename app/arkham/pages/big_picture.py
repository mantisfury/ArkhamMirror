"""
Cross-Document Big Picture Engine Page

High-level synthesis of entire corpus with executive summaries
and investigation briefings.
"""

import reflex as rx
from app.arkham.state.big_picture_state import BigPictureState
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


def key_actor_card(actor) -> rx.Component:
    """Card showing a key actor."""
    return rx.hstack(
        rx.avatar(fallback=actor.name[:2].upper(), size="2"),
        rx.vstack(
            rx.text(actor.name, weight="medium", size="2"),
            rx.hstack(
                rx.badge(actor.type, size="1", variant="soft"),
                rx.text(f"{actor.mentions} mentions", size="1", color="gray"),
                spacing="2",
            ),
            align_items="start",
            spacing="0",
        ),
        spacing="3",
        padding="2",
        _hover={"bg": "var(--gray-a3)"},
        border_radius="md",
    )


def relationship_row(rel) -> rx.Component:
    """Row showing a relationship."""
    return rx.hstack(
        rx.text(rel.entity1, weight="medium", size="2"),
        rx.icon("arrow-left-right", size=12, color="var(--gray-9)"),
        rx.text(rel.entity2, weight="medium", size="2"),
        rx.badge(rel.type, size="1", variant="outline"),
        rx.text(f"({rel.strength})", size="1", color="gray"),
        spacing="2",
        padding="2",
    )


def overview_tab() -> rx.Component:
    """Overview tab with corpus statistics."""
    return rx.vstack(
        # Stats grid
        rx.grid(
            stat_card("Documents", BigPictureState.doc_count, "file-text", "blue"),
            stat_card("Entities", BigPictureState.entity_count, "users", "green"),
            stat_card(
                "Relationships",
                BigPictureState.relationship_count,
                "git-branch",
                "purple",
            ),
            stat_card(
                "Text Chunks", BigPictureState.chunk_count, "layout-grid", "orange"
            ),
            columns="4",
            spacing="4",
            width="100%",
        ),
        rx.grid(
            # Key actors
            rx.card(
                rx.vstack(
                    rx.heading("Key Actors", size="4"),
                    rx.text(
                        "Most frequently mentioned entities", size="2", color="gray"
                    ),
                    rx.divider(),
                    rx.cond(
                        BigPictureState.key_actors.length() > 0,
                        rx.vstack(
                            rx.foreach(BigPictureState.key_actors, key_actor_card),
                            spacing="1",
                            width="100%",
                        ),
                        rx.text("No entities found", color="gray"),
                    ),
                    spacing="3",
                    width="100%",
                ),
                padding="4",
            ),
            # Key relationships
            rx.card(
                rx.vstack(
                    rx.heading("Key Relationships", size="4"),
                    rx.text("Strongest entity connections", size="2", color="gray"),
                    rx.divider(),
                    rx.cond(
                        BigPictureState.key_relationships.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                BigPictureState.key_relationships, relationship_row
                            ),
                            spacing="0",
                            width="100%",
                            max_height="400px",
                            overflow_y="auto",
                        ),
                        rx.text("No relationships found", color="gray"),
                    ),
                    spacing="3",
                    width="100%",
                ),
                padding="4",
            ),
            columns="2",
            spacing="4",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def summary_tab() -> rx.Component:
    """Executive summary tab."""
    return rx.vstack(
        rx.cond(
            BigPictureState.has_summary,
            rx.vstack(
                # Executive Summary
                rx.card(
                    rx.vstack(
                        rx.heading("Executive Summary", size="5"),
                        rx.text(BigPictureState.executive_summary, size="2"),
                        align_items="start",
                        spacing="3",
                    ),
                    padding="4",
                    width="100%",
                ),
                rx.grid(
                    # Key Themes
                    rx.card(
                        rx.vstack(
                            rx.heading("Key Themes", size="4"),
                            rx.foreach(
                                BigPictureState.key_themes,
                                lambda t: rx.hstack(
                                    rx.icon("tag", size=12),
                                    rx.text(t, size="2"),
                                    spacing="2",
                                ),
                            ),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                    ),
                    # Red Flags
                    rx.card(
                        rx.vstack(
                            rx.heading("Red Flags", size="4", color="red"),
                            rx.foreach(
                                BigPictureState.red_flags,
                                lambda f: rx.hstack(
                                    rx.icon(
                                        "triangle-alert", size=12, color="var(--red-9)"
                                    ),
                                    rx.text(f, size="2"),
                                    spacing="2",
                                ),
                            ),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                    ),
                    columns="2",
                    spacing="4",
                    width="100%",
                ),
                # Central Figures
                rx.cond(
                    BigPictureState.central_figures.length() > 0,
                    rx.card(
                        rx.vstack(
                            rx.heading("Central Figures", size="4"),
                            rx.foreach(
                                BigPictureState.central_figures,
                                lambda f: rx.hstack(
                                    rx.avatar(fallback=f.name[:2].upper(), size="2"),
                                    rx.vstack(
                                        rx.text(f.name, weight="bold", size="2"),
                                        rx.text(f.role, size="1", color="gray"),
                                        rx.text(f.significance, size="2"),
                                        align_items="start",
                                        spacing="0",
                                    ),
                                    spacing="3",
                                    padding="2",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        padding="4",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Network Insights
                rx.cond(
                    BigPictureState.network_insights != "",
                    rx.card(
                        rx.vstack(
                            rx.heading("Network Insights", size="4"),
                            rx.text(BigPictureState.network_insights, size="2"),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Focus Areas
                rx.cond(
                    BigPictureState.focus_areas.length() > 0,
                    rx.card(
                        rx.vstack(
                            rx.heading("Recommended Focus Areas", size="4"),
                            rx.foreach(
                                BigPictureState.focus_areas,
                                lambda a: rx.hstack(
                                    rx.icon(
                                        "crosshair", size=12, color="var(--blue-9)"
                                    ),
                                    rx.text(a, size="2"),
                                    spacing="2",
                                ),
                            ),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="4",
                width="100%",
            ),
            rx.cond(
                BigPictureState.is_generating,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Generating executive summary...", color="gray"),
                        rx.text(
                            "Analyzing corpus patterns and themes",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="8",
                ),
                rx.callout(
                    "Click 'Generate Executive Summary' to create an AI-powered analysis of your corpus.",
                    icon="info",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


def brief_tab() -> rx.Component:
    """Investigation brief tab."""
    return rx.vstack(
        rx.cond(
            BigPictureState.has_brief,
            rx.vstack(
                # Title and classification
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading(BigPictureState.brief_title, size="5"),
                            rx.spacer(),
                            rx.badge("CONFIDENTIAL", color_scheme="red"),
                            rx.badge(
                                f"Evidence: {BigPictureState.brief_evidence_strength}",
                                variant="outline",
                            ),
                            width="100%",
                        ),
                        spacing="2",
                    ),
                    padding="4",
                    width="100%",
                ),
                # Subjects
                rx.cond(
                    BigPictureState.brief_subjects.length() > 0,
                    rx.card(
                        rx.vstack(
                            rx.heading("Subjects Under Investigation", size="4"),
                            rx.foreach(
                                BigPictureState.brief_subjects,
                                lambda s: rx.hstack(
                                    rx.avatar(fallback=s.name[:2].upper(), size="2"),
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text(s.name, weight="bold", size="2"),
                                            rx.badge(
                                                s.risk_level,
                                                color_scheme=rx.match(
                                                    s.risk_level,
                                                    ("High", "red"),
                                                    ("Medium", "orange"),
                                                    "green",
                                                ),
                                                size="1",
                                            ),
                                            spacing="2",
                                        ),
                                        rx.text(s.profile, size="2"),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    spacing="3",
                                    padding="3",
                                    width="100%",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        padding="4",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.grid(
                    # Hypotheses
                    rx.card(
                        rx.vstack(
                            rx.heading("Working Hypotheses", size="4"),
                            rx.foreach(
                                BigPictureState.brief_hypotheses,
                                lambda h: rx.vstack(
                                    rx.hstack(
                                        rx.icon(
                                            "lightbulb",
                                            size=14,
                                            color="var(--yellow-9)",
                                        ),
                                        rx.text(
                                            h.hypothesis, weight="medium", size="2"
                                        ),
                                        rx.badge(
                                            h.confidence, size="1", variant="outline"
                                        ),
                                        spacing="2",
                                    ),
                                    rx.cond(
                                        h.supporting_evidence != "",
                                        rx.text(
                                            f"Evidence: {h.supporting_evidence}",
                                            size="1",
                                            color="gray",
                                        ),
                                        rx.fragment(),
                                    ),
                                    align_items="start",
                                    spacing="1",
                                    padding="2",
                                ),
                            ),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                    ),
                    # Risks
                    rx.card(
                        rx.vstack(
                            rx.heading(
                                "Risks & Complications", size="4", color="orange"
                            ),
                            rx.foreach(
                                BigPictureState.brief_risks,
                                lambda r: rx.hstack(
                                    rx.icon(
                                        "circle-alert", size=12, color="var(--orange-9)"
                                    ),
                                    rx.text(r, size="2"),
                                    spacing="2",
                                ),
                            ),
                            spacing="2",
                            align_items="start",
                        ),
                        padding="4",
                    ),
                    columns="2",
                    spacing="4",
                    width="100%",
                ),
                # Priority Actions
                rx.card(
                    rx.vstack(
                        rx.heading("Priority Actions", size="4"),
                        rx.foreach(
                            BigPictureState.brief_priority_actions,
                            lambda a: rx.hstack(
                                rx.icon("arrow-right", size=12, color="var(--blue-9)"),
                                rx.text(a, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        align_items="start",
                    ),
                    padding="4",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            rx.cond(
                BigPictureState.is_generating,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Generating investigation brief...", color="gray"),
                        rx.text(
                            "Analyzing key subjects and connections",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="8",
                ),
                rx.callout(
                    "Click 'Generate Investigation Brief' to create a focused analysis of key entities.",
                    icon="info",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


def big_picture_page() -> rx.Component:
    """Main Big Picture Engine page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Big Picture Engine", size="8"),
                    rx.text(
                        "High-level synthesis and analysis of your entire corpus.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.button(
                        rx.icon("file-text", size=14),
                        "Generate Executive Summary",
                        on_click=BigPictureState.generate_executive_summary,
                        loading=BigPictureState.is_generating,
                    ),
                    rx.button(
                        rx.icon("briefcase", size=14),
                        "Generate Investigation Brief",
                        variant="soft",
                        color_scheme="orange",
                        on_click=BigPictureState.generate_investigation_brief,
                        loading=BigPictureState.is_generating,
                    ),
                    spacing="2",
                ),
                width="100%",
                align_items="end",
            ),
            # Tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Overview", value="overview"),
                    rx.tabs.trigger("Executive Summary", value="summary"),
                    rx.tabs.trigger("Investigation Brief", value="brief"),
                ),
                rx.tabs.content(
                    overview_tab(),
                    value="overview",
                    padding_top="4",
                ),
                rx.tabs.content(
                    summary_tab(),
                    value="summary",
                    padding_top="4",
                ),
                rx.tabs.content(
                    brief_tab(),
                    value="brief",
                    padding_top="4",
                ),
                default_value="overview",
                width="100%",
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=BigPictureState.load_overview,
        ),
        width="100%",
        height="100vh",
    )
