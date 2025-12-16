"""
Narrative Reconstruction & Motive Inference Page

LLM-powered hypothesis generation for investigative analysis.
"""

import reflex as rx
from app.arkham.state.narrative_state import NarrativeState
from app.arkham.components.sidebar import sidebar


def entity_selector() -> rx.Component:
    """Entity selection panel."""
    return rx.card(
        rx.vstack(
            rx.heading("Select Entity to Analyze", size="4"),
            rx.text(
                "Choose an entity to reconstruct their narrative or infer motives.",
                size="2",
                color="gray",
            ),
            rx.cond(
                NarrativeState.available_entities.length() > 0,
                rx.vstack(
                    rx.foreach(
                        NarrativeState.available_entities,
                        lambda entity: rx.box(
                            rx.hstack(
                                rx.vstack(
                                    rx.text(entity.name, weight="medium"),
                                    rx.hstack(
                                        rx.badge(entity.type, size="1", variant="soft"),
                                        rx.text(
                                            f"{entity.mentions} mentions",
                                            size="1",
                                            color="gray",
                                        ),
                                        spacing="2",
                                    ),
                                    align_items="start",
                                    spacing="1",
                                ),
                                rx.spacer(),
                                rx.button(
                                    "Select",
                                    size="1",
                                    variant="soft",
                                    on_click=lambda: NarrativeState.select_entity(
                                        entity.id, entity.name
                                    ),
                                ),
                                width="100%",
                            ),
                            padding="3",
                            border_radius="md",
                            _hover={"bg": "var(--gray-a3)"},
                        ),
                    ),
                    spacing="2",
                    width="100%",
                    max_height="400px",
                    overflow_y="auto",
                ),
                rx.center(
                    rx.spinner(size="3"),
                    padding="8",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        padding="4",
    )


def narrative_tab() -> rx.Component:
    """Tab showing reconstructed narrative."""
    return rx.vstack(
        rx.cond(
            NarrativeState.has_narrative,
            rx.vstack(
                # Reliability badge
                rx.hstack(
                    rx.text("Reliability:", weight="medium"),
                    rx.badge(
                        NarrativeState.narrative_confidence,
                        color_scheme=rx.match(
                            NarrativeState.narrative_confidence,
                            ("High", "green"),
                            ("Medium", "yellow"),
                            "gray",
                        ),
                    ),
                    spacing="2",
                ),
                # Narrative text
                rx.card(
                    rx.text(NarrativeState.narrative_text, size="2"),
                    padding="4",
                    width="100%",
                ),
                # Events timeline
                rx.cond(
                    NarrativeState.narrative_events.length() > 0,
                    rx.vstack(
                        rx.heading("Reconstructed Events", size="4"),
                        rx.foreach(
                            NarrativeState.narrative_events,
                            lambda event: rx.card(
                                rx.hstack(
                                    rx.vstack(
                                        rx.text(event.date, size="1", color="gray"),
                                        rx.text(event.event, size="2"),
                                        align_items="start",
                                    ),
                                    rx.spacer(),
                                    rx.badge(
                                        event.confidence, size="1", variant="outline"
                                    ),
                                    width="100%",
                                ),
                                padding="3",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Relationships
                rx.cond(
                    NarrativeState.narrative_relationships.length() > 0,
                    rx.vstack(
                        rx.heading("Identified Relationships", size="4"),
                        rx.foreach(
                            NarrativeState.narrative_relationships,
                            lambda rel: rx.hstack(
                                rx.icon(
                                    rx.match(
                                        rel.nature,
                                        ("positive", "heart"),
                                        ("negative", "x"),
                                        "minus",
                                    ),
                                    size=14,
                                    color=rx.match(
                                        rel.nature,
                                        ("positive", "var(--green-9)"),
                                        ("negative", "var(--red-9)"),
                                        "var(--gray-9)",
                                    ),
                                ),
                                rx.text(rel.entity, weight="medium"),
                                rx.text("-", color="gray"),
                                rx.text(rel.relationship, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Gaps
                rx.cond(
                    NarrativeState.narrative_gaps.length() > 0,
                    rx.vstack(
                        rx.heading("Information Gaps", size="4"),
                        rx.foreach(
                            NarrativeState.narrative_gaps,
                            lambda gap: rx.hstack(
                                rx.icon(
                                    "circle-help", size=14, color="var(--orange-9)"
                                ),
                                rx.text(gap, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Reconstruct Narrative' to analyze the selected entity.",
                icon="info",
            ),
        ),
        spacing="4",
        width="100%",
    )


def hypothesis_card(hyp) -> rx.Component:
    """Card displaying a motive hypothesis."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("lightbulb", size=18, color="var(--yellow-9)"),
                rx.text(hyp.hypothesis, weight="medium"),
                rx.spacer(),
                rx.badge(
                    hyp.confidence,
                    color_scheme=rx.match(
                        hyp.confidence,
                        ("High", "green"),
                        ("Medium", "yellow"),
                        ("Speculative", "red"),
                        "gray",
                    ),
                ),
                width="100%",
            ),
            rx.cond(
                hyp.supporting_evidence.length() > 0,
                rx.vstack(
                    rx.text(
                        "Supporting Evidence:", size="1", weight="bold", color="green"
                    ),
                    rx.foreach(
                        hyp.supporting_evidence,
                        lambda e: rx.text(f"• {e}", size="1"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                hyp.contradicting_evidence.length() > 0,
                rx.vstack(
                    rx.text(
                        "Contradicting Evidence:", size="1", weight="bold", color="red"
                    ),
                    rx.foreach(
                        hyp.contradicting_evidence,
                        lambda e: rx.text(f"• {e}", size="1"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                hyp.verification_needed.length() > 0,
                rx.vstack(
                    rx.text("To Verify:", size="1", weight="bold", color="blue"),
                    rx.foreach(
                        hyp.verification_needed,
                        lambda v: rx.text(f"→ {v}", size="1"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            align_items="start",
            spacing="3",
        ),
        padding="4",
    )


def motives_tab() -> rx.Component:
    """Tab showing motive hypotheses."""
    return rx.vstack(
        rx.cond(
            NarrativeState.has_hypotheses,
            rx.vstack(
                # Warning banner
                rx.callout(
                    NarrativeState.speculation_warning,
                    icon="triangle-alert",
                    color="orange",
                ),
                # Risk flags
                rx.cond(
                    NarrativeState.risk_flags.length() > 0,
                    rx.vstack(
                        rx.heading("Risk Flags", size="4", color="red"),
                        rx.foreach(
                            NarrativeState.risk_flags,
                            lambda flag: rx.hstack(
                                rx.icon("flag", size=14, color="var(--red-9)"),
                                rx.text(flag, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Behavioral patterns
                rx.cond(
                    NarrativeState.behavioral_patterns.length() > 0,
                    rx.vstack(
                        rx.heading("Behavioral Patterns", size="4"),
                        rx.foreach(
                            NarrativeState.behavioral_patterns,
                            lambda pattern: rx.hstack(
                                rx.icon("activity", size=14),
                                rx.text(pattern, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Hypotheses
                rx.heading("Motive Hypotheses", size="4"),
                rx.foreach(NarrativeState.hypotheses, hypothesis_card),
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Infer Motives' to generate hypotheses about the selected entity.",
                icon="info",
            ),
        ),
        spacing="4",
        width="100%",
    )


def brief_tab() -> rx.Component:
    """Tab showing the investigation brief."""
    return rx.vstack(
        rx.cond(
            NarrativeState.brief_summary != "",
            rx.vstack(
                # Executive summary
                rx.card(
                    rx.vstack(
                        rx.heading("Executive Summary", size="4"),
                        rx.text(NarrativeState.brief_summary, size="2"),
                        align_items="start",
                        spacing="2",
                    ),
                    padding="4",
                    width="100%",
                ),
                # Key players
                rx.cond(
                    NarrativeState.brief_key_players.length() > 0,
                    rx.vstack(
                        rx.heading("Key Players", size="4"),
                        rx.foreach(
                            NarrativeState.brief_key_players,
                            lambda p: rx.hstack(
                                rx.text(p.name, weight="bold"),
                                rx.text(f"({p.role})", color="gray"),
                                rx.text(p.significance, size="1"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Red flags
                rx.cond(
                    NarrativeState.brief_red_flags.length() > 0,
                    rx.vstack(
                        rx.heading("Red Flags", size="4", color="red"),
                        rx.foreach(
                            NarrativeState.brief_red_flags,
                            lambda f: rx.hstack(
                                rx.icon(
                                    "triangle-alert",
                                    size=14,
                                    color="var(--red-9)",
                                ),
                                rx.text(f, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Hypotheses
                rx.cond(
                    NarrativeState.brief_hypotheses.length() > 0,
                    rx.vstack(
                        rx.heading("Working Hypotheses", size="4"),
                        rx.foreach(
                            NarrativeState.brief_hypotheses,
                            lambda h: rx.hstack(
                                rx.icon("lightbulb", size=14),
                                rx.text(h.hypothesis, size="2"),
                                rx.badge(h.confidence, size="1"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Gaps
                rx.cond(
                    NarrativeState.brief_gaps.length() > 0,
                    rx.vstack(
                        rx.heading("Information Gaps", size="4", color="orange"),
                        rx.foreach(
                            NarrativeState.brief_gaps,
                            lambda g: rx.hstack(
                                rx.icon(
                                    "circle-help", size=14, color="var(--orange-9)"
                                ),
                                rx.text(g, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Next steps
                rx.cond(
                    NarrativeState.brief_next_steps.length() > 0,
                    rx.vstack(
                        rx.heading("Recommended Next Steps", size="4"),
                        rx.foreach(
                            NarrativeState.brief_next_steps,
                            lambda s: rx.hstack(
                                rx.icon(
                                    "arrow-right",
                                    size=14,
                                    color="var(--blue-9)",
                                ),
                                rx.text(s, size="2"),
                                spacing="2",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Generate Brief' to create an investigation summary.",
                icon="info",
            ),
        ),
        spacing="4",
        width="100%",
    )


def narrative_page() -> rx.Component:
    """Main Narrative Reconstruction page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Narrative Reconstruction", size="8"),
                    rx.text(
                        "LLM-powered hypothesis generation and motive inference.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("file-text"),
                    "Generate Brief",
                    on_click=NarrativeState.generate_brief,
                    loading=NarrativeState.is_loading,
                    variant="soft",
                ),
                width="100%",
                align_items="end",
            ),
            rx.grid(
                # Left: Entity selector
                rx.box(
                    entity_selector(),
                    width="100%",
                ),
                # Right: Unified analysis panel with all tabs
                rx.vstack(
                    # Action buttons card
                    rx.card(
                        rx.hstack(
                            rx.cond(
                                NarrativeState.has_entity_selected,
                                rx.text(
                                    f"Entity: {NarrativeState.selected_entity_name}",
                                    weight="bold",
                                ),
                                rx.text("No entity selected", color="gray"),
                            ),
                            rx.spacer(),
                            rx.button(
                                rx.icon("book-open", size=14),
                                "Narrative",
                                size="2",
                                variant="outline",
                                on_click=NarrativeState.analyze_narrative,
                                loading=NarrativeState.is_loading,
                                disabled=~NarrativeState.has_entity_selected,
                            ),
                            rx.button(
                                rx.icon("brain", size=14),
                                "Motives",
                                size="2",
                                variant="outline",
                                color_scheme="orange",
                                on_click=NarrativeState.analyze_motives,
                                loading=NarrativeState.is_loading,
                                disabled=~NarrativeState.has_entity_selected,
                            ),
                            width="100%",
                        ),
                        padding="4",
                        width="100%",
                    ),
                    # Unified tabs for all content
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("📖 Narrative", value="narrative"),
                            rx.tabs.trigger("🧠 Motives", value="motives"),
                            rx.tabs.trigger("📋 Brief", value="brief"),
                        ),
                        rx.tabs.content(
                            rx.cond(
                                NarrativeState.has_entity_selected,
                                narrative_tab(),
                                rx.callout(
                                    "Select an entity to reconstruct their narrative.",
                                    icon="info",
                                ),
                            ),
                            value="narrative",
                            padding_top="4",
                        ),
                        rx.tabs.content(
                            rx.cond(
                                NarrativeState.has_entity_selected,
                                motives_tab(),
                                rx.callout(
                                    "Select an entity to infer their motives.",
                                    icon="info",
                                ),
                            ),
                            value="motives",
                            padding_top="4",
                        ),
                        rx.tabs.content(
                            brief_tab(),
                            value="brief",
                            padding_top="4",
                        ),
                        value=NarrativeState.active_tab,
                        on_change=NarrativeState.set_active_tab,
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            padding="2em",
            width="100%",
            align_items="start",
            on_mount=NarrativeState.load_entities,
        ),
        width="100%",
        height="100vh",
    )
