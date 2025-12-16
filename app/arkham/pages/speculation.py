"""
Speculation Mode Page

LLM-powered investigative hypotheses and leads generation.
"""

import reflex as rx
from app.arkham.state.speculation_state import SpeculationState
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


def significance_badge(level: str) -> rx.Component:
    """Badge showing significance/priority level."""
    return rx.badge(
        level,
        color_scheme=rx.match(
            level,
            ("High", "red"),
            ("Low", "gray"),
            "yellow",
        ),
        size="1",
    )


def gap_type_badge(gap_type: str) -> rx.Component:
    """Badge showing gap type."""
    type_display = gap_type.replace("_", " ").title()
    return rx.badge(
        type_display,
        color_scheme=rx.match(
            gap_type,
            ("missing_document", "red"),
            ("unexplored_connection", "blue"),
            ("time_gap", "orange"),
            ("underrepresented_entity", "purple"),
            "gray",
        ),
        size="1",
    )


def scenario_card(scenario) -> rx.Component:
    """Card showing a what-if scenario."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("lightbulb", size=16, color="var(--yellow-9)"),
                rx.heading(f"Scenario {scenario.id}", size="4"),
                rx.spacer(),
                significance_badge(scenario.significance),
                width="100%",
            ),
            rx.text(scenario.hypothesis, weight="medium", size="3"),
            rx.divider(),
            rx.vstack(
                rx.text("Basis:", weight="bold", size="2"),
                rx.text(scenario.basis, size="2", color="gray"),
                align_items="start",
                spacing="1",
            ),
            rx.cond(
                scenario.evidence_needed.length() > 0,
                rx.vstack(
                    rx.text("Evidence Needed:", weight="bold", size="2"),
                    rx.foreach(
                        scenario.evidence_needed,
                        lambda e: rx.hstack(
                            rx.icon("search", size=12),
                            rx.text(e, size="2"),
                            spacing="2",
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                scenario.investigation_steps.length() > 0,
                rx.vstack(
                    rx.text("Investigation Steps:", weight="bold", size="2"),
                    rx.foreach(
                        scenario.investigation_steps,
                        lambda s: rx.hstack(
                            rx.icon("arrow-right", size=12, color="var(--blue-9)"),
                            rx.text(s, size="2"),
                            spacing="2",
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                scenario.significance_explanation != "",
                rx.callout(
                    scenario.significance_explanation,
                    icon="info",
                    size="1",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def gap_card(gap) -> rx.Component:
    """Card showing an information gap."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("circle-alert", size=16, color="var(--orange-9)"),
                gap_type_badge(gap.type),
                rx.spacer(),
                significance_badge(gap.importance),
                width="100%",
            ),
            rx.text(gap.description, size="2"),
            rx.cond(
                gap.indicators.length() > 0,
                rx.vstack(
                    rx.text("Indicators:", weight="bold", size="2"),
                    rx.foreach(
                        gap.indicators,
                        lambda i: rx.hstack(
                            rx.icon("circle", size=8),
                            rx.text(i, size="2", color="gray"),
                            spacing="2",
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            rx.cond(
                gap.suggested_sources.length() > 0,
                rx.vstack(
                    rx.text("Suggested Sources:", weight="bold", size="2"),
                    rx.foreach(
                        gap.suggested_sources,
                        lambda s: rx.hstack(
                            rx.icon("folder-search", size=12, color="var(--blue-9)"),
                            rx.text(s, size="2"),
                            spacing="2",
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def question_card(question) -> rx.Component:
    """Card showing an investigative question."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("circle-help", size=16, color="var(--blue-9)"),
                significance_badge(question.priority),
                width="100%",
            ),
            rx.text(question.question, weight="medium", size="3"),
            rx.cond(
                question.rationale != "",
                rx.text(question.rationale, size="2", color="gray"),
                rx.fragment(),
            ),
            rx.hstack(
                rx.cond(
                    question.related_entities.length() > 0,
                    rx.hstack(
                        rx.text("Entities:", size="1", color="gray"),
                        rx.foreach(
                            question.related_entities,
                            lambda e: rx.badge(e, size="1", variant="soft"),
                        ),
                        spacing="1",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
            ),
            rx.cond(
                question.potential_sources.length() > 0,
                rx.vstack(
                    rx.text("Potential Sources:", weight="bold", size="2"),
                    rx.foreach(
                        question.potential_sources,
                        lambda s: rx.hstack(
                            rx.icon("file-search", size=12),
                            rx.text(s, size="2", color="gray"),
                            spacing="2",
                        ),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        padding="4",
    )


def scenarios_tab() -> rx.Component:
    """Tab showing what-if scenarios."""
    return rx.vstack(
        rx.cond(
            SpeculationState.scenarios.length() > 0,
            rx.vstack(
                rx.foreach(SpeculationState.scenarios, scenario_card),
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Generate Scenarios' to create what-if hypotheses.",
                icon="lightbulb",
            ),
        ),
        spacing="4",
        width="100%",
    )


def gaps_tab() -> rx.Component:
    """Tab showing information gaps."""
    return rx.vstack(
        rx.cond(
            SpeculationState.gaps.length() > 0,
            rx.vstack(
                rx.foreach(SpeculationState.gaps, gap_card),
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Find Gaps' to identify missing information.",
                icon="circle-alert",
            ),
        ),
        spacing="4",
        width="100%",
    )


def questions_tab() -> rx.Component:
    """Tab showing investigative questions."""
    return rx.vstack(
        rx.cond(
            SpeculationState.questions.length() > 0,
            rx.grid(
                rx.foreach(SpeculationState.questions, question_card),
                columns="2",
                spacing="4",
                width="100%",
            ),
            rx.callout(
                "Click 'Generate Questions' to create investigative questions.",
                icon="circle-help",
            ),
        ),
        spacing="4",
        width="100%",
    )


def speculation_page() -> rx.Component:
    """Main Speculation Mode page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Speculation Mode", size="8"),
                    rx.text(
                        "AI-generated hypotheses, gaps, and investigative leads.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.input(
                        placeholder="Focus topic (optional)...",
                        value=SpeculationState.focus_topic,
                        on_change=SpeculationState.set_focus_topic,
                        width="200px",
                    ),
                    spacing="2",
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card("Documents", SpeculationState.doc_count, "file-text", "blue"),
                stat_card("Entities", SpeculationState.entity_count, "users", "green"),
                stat_card(
                    "Relationships", SpeculationState.rel_count, "git-branch", "purple"
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            # Data Selection Filter Panel
            rx.box(
                rx.hstack(
                    rx.button(
                        rx.icon("filter", size=14),
                        rx.cond(
                            SpeculationState.show_filters,
                            "Hide Data Selection",
                            "Data Selection (optional)",
                        ),
                        on_click=SpeculationState.toggle_filters,
                        variant="ghost",
                        size="2",
                    ),
                    rx.spacer(),
                    rx.cond(
                        (SpeculationState.selected_doc_ids.length() > 0)
                        | (SpeculationState.selected_entity_ids.length() > 0),
                        rx.hstack(
                            rx.badge(
                                f"{SpeculationState.selected_doc_ids.length()} docs",
                                color_scheme="blue",
                                variant="soft",
                                size="1",
                            ),
                            rx.badge(
                                f"{SpeculationState.selected_entity_ids.length()} entities",
                                color_scheme="green",
                                variant="soft",
                                size="1",
                            ),
                            rx.button(
                                rx.icon("x", size=12),
                                "Clear",
                                on_click=SpeculationState.clear_selections,
                                variant="ghost",
                                size="1",
                                color_scheme="gray",
                            ),
                            spacing="2",
                        ),
                        rx.text("Using all data", size="1", color="gray"),
                    ),
                    width="100%",
                ),
                rx.cond(
                    SpeculationState.show_filters,
                    rx.vstack(
                        rx.divider(),
                        # Documents section
                        rx.vstack(
                            rx.text("Documents", weight="bold", size="2"),
                            rx.cond(
                                SpeculationState.available_documents.length() > 0,
                                rx.hstack(
                                    rx.foreach(
                                        SpeculationState.available_documents,
                                        lambda doc: rx.badge(
                                            doc.title[:30],
                                            color_scheme=rx.cond(
                                                SpeculationState.selected_doc_ids.contains(
                                                    doc.id
                                                ),
                                                "blue",
                                                "gray",
                                            ),
                                            variant=rx.cond(
                                                SpeculationState.selected_doc_ids.contains(
                                                    doc.id
                                                ),
                                                "solid",
                                                "outline",
                                            ),
                                            cursor="pointer",
                                            on_click=lambda: SpeculationState.toggle_document(
                                                doc.id
                                            ),
                                        ),
                                    ),
                                    wrap="wrap",
                                    spacing="2",
                                ),
                                rx.text(
                                    "No documents available", size="1", color="gray"
                                ),
                            ),
                            align_items="start",
                            spacing="2",
                            width="100%",
                        ),
                        # Entities section
                        rx.vstack(
                            rx.text("Entities", weight="bold", size="2"),
                            rx.cond(
                                SpeculationState.available_entities.length() > 0,
                                rx.hstack(
                                    rx.foreach(
                                        SpeculationState.available_entities[
                                            :30
                                        ],  # Limit display
                                        lambda entity: rx.badge(
                                            f"{entity.name[:20]} ({entity.type})",
                                            color_scheme=rx.cond(
                                                SpeculationState.selected_entity_ids.contains(
                                                    entity.id
                                                ),
                                                "green",
                                                "gray",
                                            ),
                                            variant=rx.cond(
                                                SpeculationState.selected_entity_ids.contains(
                                                    entity.id
                                                ),
                                                "solid",
                                                "outline",
                                            ),
                                            cursor="pointer",
                                            on_click=lambda: SpeculationState.toggle_entity(
                                                entity.id
                                            ),
                                        ),
                                    ),
                                    wrap="wrap",
                                    spacing="2",
                                ),
                                rx.text(
                                    "No entities available", size="1", color="gray"
                                ),
                            ),
                            align_items="start",
                            spacing="2",
                            width="100%",
                        ),
                        spacing="3",
                        padding_top="3",
                        width="100%",
                    ),
                ),
                padding="3",
                border="1px solid var(--gray-6)",
                border_radius="md",
                width="100%",
            ),
            # Action buttons
            rx.hstack(
                rx.button(
                    rx.icon("lightbulb", size=14),
                    "Generate Scenarios",
                    on_click=SpeculationState.generate_scenarios,
                    loading=SpeculationState.is_generating,
                    color_scheme="yellow",
                ),
                rx.button(
                    rx.icon("circle-alert", size=14),
                    "Find Gaps",
                    on_click=SpeculationState.identify_gaps,
                    loading=SpeculationState.is_generating,
                    variant="soft",
                    color_scheme="orange",
                ),
                rx.button(
                    rx.icon("circle-help", size=14),
                    "Generate Questions",
                    on_click=SpeculationState.generate_questions,
                    loading=SpeculationState.is_generating,
                    variant="soft",
                    color_scheme="blue",
                ),
                rx.spacer(),
                rx.cond(
                    SpeculationState.has_results,
                    rx.button(
                        rx.icon("download", size=14),
                        "Export Results",
                        on_click=SpeculationState.export_results,
                        variant="soft",
                        color_scheme="gray",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                width="100%",
            ),
            # Content
            rx.cond(
                SpeculationState.is_generating,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Generating investigative leads...", color="gray"),
                        rx.text(
                            "AI is analyzing patterns and formulating hypotheses",
                            size="1",
                            color="gray",
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="8",
                ),
                rx.cond(
                    SpeculationState.has_results,
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger(
                                f"Scenarios ({SpeculationState.scenarios.length()})",
                                value="scenarios",
                            ),
                            rx.tabs.trigger(
                                f"Gaps ({SpeculationState.gaps.length()})",
                                value="gaps",
                            ),
                            rx.tabs.trigger(
                                f"Questions ({SpeculationState.questions.length()})",
                                value="questions",
                            ),
                        ),
                        rx.tabs.content(
                            scenarios_tab(), value="scenarios", padding_top="4"
                        ),
                        rx.tabs.content(gaps_tab(), value="gaps", padding_top="4"),
                        rx.tabs.content(
                            questions_tab(), value="questions", padding_top="4"
                        ),
                        value=SpeculationState.active_tab,
                        on_change=SpeculationState.set_active_tab,
                        width="100%",
                    ),
                    rx.callout(
                        "Speculation Mode uses AI to generate investigative leads. Generate what-if scenarios to explore hypothetical connections, identify gaps in your corpus, or create prioritized investigative questions.",
                        icon="brain",
                    ),
                ),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=SpeculationState.load_summary,
        ),
        width="100%",
        height="100vh",
    )
