"""
ACH (Analysis of Competing Hypotheses) Page.

Main page for ACH analysis following Heuer's 8-step methodology.
"""

import reflex as rx
from ..components.sidebar import sidebar
from ..components.ach_step_indicator import ach_step_indicator
from ..components.ach_guidance_panel import ach_guidance_for_current_step
from ..components.design_tokens import SPACING, CARD_PADDING
from ..state.ach_state import ACHState


# =============================================================================
# RATING CONSTANTS
# =============================================================================

RATING_OPTIONS = ["-", "CC", "C", "N", "I", "II"]  # "-" = unrated
RATING_COLORS = {
    "CC": "green",
    "C": "lime",
    "N": "gray",
    "I": "orange",
    "II": "red",
    "-": "gray",  # Unrated
    "": "gray",  # Legacy fallback
}
RATING_LABELS = {
    "CC": "Very Consistent",
    "C": "Consistent",
    "N": "Neutral",
    "I": "Inconsistent",
    "II": "Very Inconsistent",
    "-": "Unrated",
    "": "Unrated",  # Legacy fallback
}

EVIDENCE_TYPES = ["fact", "testimony", "document", "assumption", "argument"]
RELIABILITY_OPTIONS = ["high", "medium", "low"]


# =============================================================================
# ANALYSIS LIST VIEW
# =============================================================================


def analysis_list_card(analysis) -> rx.Component:
    """Render a card for an analysis in the list view."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.heading(analysis.title, size="4"),
                    rx.badge(
                        analysis.status,
                        color_scheme=rx.match(
                            analysis.status,
                            ("complete", "green"),
                            ("in_progress", "blue"),
                            ("archived", "gray"),
                            "blue",
                        ),
                        variant="soft",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    analysis.focus_question,
                    size="2",
                    color="gray.11",
                    no_of_lines=2,
                ),
                rx.hstack(
                    rx.badge(
                        f"{analysis.hypothesis_count} hypotheses",
                        variant="outline",
                        size="1",
                    ),
                    rx.badge(
                        f"{analysis.evidence_count} evidence",
                        variant="outline",
                        size="1",
                    ),
                    rx.text(
                        f"Step {analysis.current_step}/8",
                        size="1",
                        color="gray.9",
                    ),
                    spacing="2",
                ),
                align="start",
                spacing="1",
                flex="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.button(
                    rx.icon("arrow-right", size=14),
                    "Open",
                    on_click=lambda: ACHState.load_analysis(analysis.id),
                    size="2",
                ),
                rx.button(
                    rx.icon("trash-2", size=12),
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                    on_click=lambda: ACHState.delete_analysis_confirm(
                        analysis.id, analysis.title
                    ),
                ),
                spacing="2",
            ),
            width="100%",
            align="center",
        ),
        width="100%",
        cursor="pointer",
        _hover={"border_color": "var(--accent-7)"},
    )


def analysis_list_view() -> rx.Component:
    """View for listing all ACH analyses."""
    return rx.vstack(
        # Header
        rx.hstack(
            rx.vstack(
                rx.heading("Analysis of Competing Hypotheses", size="7"),
                rx.text(
                    "Structured methodology for evaluating competing explanations",
                    color="gray.11",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "New Analysis",
                on_click=ACHState.open_new_analysis_dialog,
                color_scheme="blue",
            ),
            width="100%",
            align="center",
        ),
        rx.divider(margin_y=SPACING["md"]),
        # Analysis list
        rx.cond(
            ACHState.is_loading,
            rx.center(rx.spinner(size="3"), padding="4"),
            rx.cond(
                ACHState.analyses.length() > 0,
                rx.vstack(
                    rx.foreach(ACHState.analyses, analysis_list_card),
                    spacing=SPACING["sm"],
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("file-question", size=48, color="gray.7"),
                        rx.text("No analyses yet", size="4", color="gray.9"),
                        rx.text(
                            "Create your first ACH analysis to get started",
                            size="2",
                            color="gray.11",
                        ),
                        rx.button(
                            rx.icon("plus", size=14),
                            "Create Analysis",
                            on_click=ACHState.open_new_analysis_dialog,
                            margin_top=SPACING["md"],
                        ),
                        align="center",
                        spacing="2",
                    ),
                    padding="8",
                    width="100%",
                ),
            ),
        ),
        spacing=SPACING["md"],
        width="100%",
        align="start",
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - HYPOTHESIS MANAGEMENT
# =============================================================================


def hypothesis_card(h) -> rx.Component:
    """Render a hypothesis card."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.badge(
                        h.label,
                        color_scheme="blue",
                        variant="solid",
                    ),
                    rx.text(h.description, weight="medium"),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    h.future_indicators,
                    rx.text(
                        f"Future indicators: {h.future_indicators}",
                        size="1",
                        color="gray.11",
                    ),
                    rx.fragment(),
                ),
                align="start",
                spacing="1",
                flex="1",
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=12),
                    variant="ghost",
                    size="1",
                    on_click=lambda: ACHState.edit_hypothesis(h.id),
                ),
                rx.button(
                    rx.icon("trash-2", size=12),
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                    on_click=lambda: ACHState.delete_hypothesis_confirm(h.id, h.label),
                ),
                spacing="1",
            ),
            width="100%",
            align="center",
        ),
        width="100%",
        border_left=f"4px solid {h.color}",
    )


def hypotheses_section() -> rx.Component:
    """Section for managing hypotheses (Step 1)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("lightbulb", size=18, color="var(--blue-9)"),
                rx.heading("Hypotheses", size="5"),
                rx.badge(
                    ACHState.hypothesis_count,
                    variant="soft",
                ),
                rx.spacer(),
                # AI Buttons
                rx.cond(
                    ACHState.is_ai_loading,
                    rx.spinner(size="2"),
                    rx.hstack(
                        rx.button(
                            rx.icon("sparkles", size=12),
                            "AI Suggest",
                            on_click=ACHState.request_hypothesis_suggestions,
                            size="1",
                            variant="soft",
                            color_scheme="violet",
                        ),
                        rx.cond(
                            ACHState.has_hypotheses,
                            rx.hstack(
                                rx.select.root(
                                    rx.select.trigger(
                                        placeholder="All",
                                        width="90px",
                                    ),
                                    rx.select.content(
                                        rx.select.group(
                                            rx.select.item("All", value="all"),
                                            rx.foreach(
                                                ACHState.hypotheses,
                                                lambda h: rx.select.item(
                                                    h.label,
                                                    value=h.label,
                                                ),
                                            ),
                                        ),
                                    ),
                                    value=ACHState.challenge_hypothesis_id,
                                    on_change=ACHState.set_challenge_hypothesis_id,
                                    size="1",
                                ),
                                rx.button(
                                    rx.icon("swords", size=12),
                                    "Challenge",
                                    on_click=ACHState.request_challenge_hypotheses,
                                    size="1",
                                    variant="soft",
                                    color_scheme="orange",
                                ),
                                spacing="1",
                            ),
                            rx.fragment(),
                        ),
                        spacing="1",
                    ),
                ),
                rx.button(
                    rx.icon("plus", size=14),
                    "Add Hypothesis",
                    on_click=ACHState.open_add_hypothesis_dialog,
                    size="1",
                    variant="soft",
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                ACHState.has_hypotheses,
                rx.vstack(
                    rx.foreach(ACHState.hypotheses, hypothesis_card),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.center(
                    rx.text(
                        "Add at least 2 hypotheses to begin",
                        size="2",
                        color="gray.11",
                    ),
                    padding="3",
                ),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - EVIDENCE MANAGEMENT
# =============================================================================


def evidence_card(e) -> rx.Component:
    """Render an evidence card."""
    diag_color = rx.cond(
        e.is_high_diagnostic,
        "amber",
        rx.cond(e.is_low_diagnostic, "gray", "blue"),
    )

    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.badge(e.label, color_scheme=diag_color, variant="solid"),
                    rx.badge(e.evidence_type, variant="outline", size="1"),
                    rx.badge(
                        e.reliability.upper(),
                        color_scheme=rx.match(
                            e.reliability,
                            ("high", "green"),
                            ("medium", "yellow"),
                            ("low", "red"),
                            "gray",
                        ),
                        variant="soft",
                        size="1",
                    ),
                    rx.cond(
                        e.is_high_diagnostic,
                        rx.tooltip(
                            rx.icon("star", size=12, color="var(--amber-9)"),
                            content="High diagnostic value",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(e.description, size="2"),
                rx.cond(
                    e.source,
                    rx.text(f'Source: "{e.source}"', size="1", color="gray.11"),
                    rx.fragment(),
                ),
                # Phase 4: Corpus link indicator
                rx.cond(
                    e.source_document_id.is_not_none(),
                    rx.hstack(
                        rx.icon("file-search", size=10, color="var(--cyan-9)"),
                        rx.text("From corpus", size="1", color="var(--cyan-11)"),
                        spacing="1",
                        align="center",
                    ),
                    rx.fragment(),
                ),
                align="start",
                spacing="1",
                flex="1",
            ),
            rx.spacer(),
            rx.hstack(
                # Phase 4: Show Context button for corpus-linked evidence
                rx.cond(
                    e.source_document_id.is_not_none(),
                    rx.tooltip(
                        rx.button(
                            rx.icon("file-search", size=12),
                            variant="ghost",
                            size="1",
                            color_scheme="cyan",
                            on_click=lambda: ACHState.show_evidence_context(e.id),
                        ),
                        content="Show document context",
                    ),
                    rx.fragment(),
                ),
                rx.button(
                    rx.icon("pencil", size=12),
                    variant="ghost",
                    size="1",
                    on_click=lambda: ACHState.edit_evidence(e.id),
                ),
                rx.button(
                    rx.icon("trash-2", size=12),
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                    on_click=lambda: ACHState.delete_evidence_confirm(e.id, e.label),
                ),
                spacing="1",
            ),
            width="100%",
            align="start",
        ),
        width="100%",
    )


def evidence_section() -> rx.Component:
    """Section for managing evidence (Step 2)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("file-text", size=18, color="var(--green-9)"),
                rx.heading("Evidence", size="5"),
                rx.badge(ACHState.evidence_count, variant="soft"),
                rx.spacer(),
                # Phase 4: Filter dropdown
                rx.select(
                    ["all", "unrated", "has_ai", "high_diagnostic"],
                    value=ACHState.evidence_filter,
                    on_change=ACHState.set_evidence_filter,
                    size="1",
                    variant="soft",
                    placeholder="Filter...",
                ),
                # Sort dropdown
                rx.select(
                    ["order", "diagnosticity"],
                    value=ACHState.sort_evidence_by,
                    on_change=ACHState.set_sort_evidence_by,
                    size="1",
                    variant="soft",
                ),
                # AI Suggest button
                rx.cond(
                    ACHState.is_ai_loading,
                    rx.spinner(size="2"),
                    rx.button(
                        rx.icon("sparkles", size=12),
                        "AI Suggest",
                        on_click=ACHState.request_evidence_suggestions,
                        size="1",
                        variant="soft",
                        color_scheme="violet",
                    ),
                ),
                # Import from Corpus button (Phase 3)
                rx.button(
                    rx.icon("download", size=12),
                    "Import",
                    on_click=ACHState.open_import_dialog,
                    size="1",
                    variant="soft",
                    color_scheme="cyan",
                ),
                rx.button(
                    rx.icon("plus", size=14),
                    "Add Evidence",
                    on_click=ACHState.open_add_evidence_dialog,
                    size="1",
                    variant="soft",
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                ACHState.has_evidence,
                rx.vstack(
                    rx.foreach(ACHState.displayed_evidence, evidence_card),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.center(
                    rx.text(
                        "Add evidence to rate against hypotheses",
                        size="2",
                        color="gray.11",
                    ),
                    padding="3",
                ),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - MATRIX
# =============================================================================


def rating_cell(
    evidence_id: int, hypothesis_id: int, current_rating: str
) -> rx.Component:
    """Render a single rating cell in the matrix."""
    # Check if this cell is focused (for keyboard navigation)
    is_focused = (ACHState.focused_evidence_id == evidence_id) & (
        ACHState.focused_hypothesis_id == hypothesis_id
    )

    return rx.box(
        rx.select(
            RATING_OPTIONS,
            value=current_rating,
            on_change=lambda v: ACHState.set_rating(evidence_id, hypothesis_id, v),
            on_focus=lambda: ACHState.focus_cell(evidence_id, hypothesis_id),
            size="1",
            variant="soft",
            color=RATING_COLORS.get(current_rating, "gray"),
        ),
        border=rx.cond(
            is_focused,
            "2px solid var(--accent-9)",
            "2px solid transparent",
        ),
        border_radius="4px",
    )


def matrix_row(e) -> rx.Component:
    """Render a matrix row for one evidence item."""
    row_bg = rx.cond(
        e.is_high_diagnostic,
        "var(--amber-3)",
        rx.cond(e.is_low_diagnostic, "var(--gray-3)", "transparent"),
    )

    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.badge(e.label, variant="outline", size="1"),
                rx.text(
                    e.description,
                    size="1",
                    truncate=True,
                ),
                spacing="1",
            ),
        ),
        # Rating cells for each hypothesis - use rx.foreach with a helper
        rx.foreach(
            ACHState.hypotheses,
            lambda h: rx.table.cell(
                rx.select(
                    RATING_OPTIONS,
                    value=e.ratings.get(h.id, "-"),
                    on_change=lambda v: ACHState.set_rating(e.id, h.id, v),
                    size="1",
                    variant="soft",
                ),
            ),
        ),
        # AI Suggest button for this row
        rx.table.cell(
            rx.tooltip(
                rx.button(
                    rx.icon("sparkles", size=10),
                    on_click=lambda: ACHState.request_rating_suggestions(e.id),
                    size="1",
                    variant="ghost",
                    color_scheme="violet",
                    padding="1",
                ),
                content="AI suggest ratings",
            ),
        ),
        bg=row_bg,
    )


def matrix_section() -> rx.Component:
    """ACH Matrix section (Step 3)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("grid-3x3", size=18, color="var(--purple-9)"),
                rx.heading("Analysis Matrix", size="5"),
                rx.spacer(),
                rx.hstack(
                    rx.text("Completion:", size="1", color="gray.11"),
                    rx.progress(
                        value=ACHState.matrix_completion_pct.to(int),
                        max=100,
                        width="100px",
                    ),
                    rx.text(
                        f"{ACHState.matrix_completion_pct}%",
                        size="1",
                        weight="medium",
                    ),
                    spacing="2",
                    align="center",
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                ACHState.has_hypotheses & ACHState.has_evidence,
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Evidence"),
                                rx.foreach(
                                    ACHState.hypotheses,
                                    lambda h: rx.table.column_header_cell(
                                        rx.tooltip(
                                            rx.text(h.label, weight="bold"),
                                            content=h.description,
                                        ),
                                    ),
                                ),
                                rx.table.column_header_cell(
                                    rx.tooltip(
                                        rx.icon(
                                            "sparkles", size=12, color="var(--violet-9)"
                                        ),
                                        content="AI-assisted ratings",
                                    ),
                                ),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(ACHState.displayed_evidence, matrix_row),
                        ),
                        width="100%",
                        variant="surface",
                    ),
                    width="100%",
                    max_height="400px",
                ),
                rx.center(
                    rx.text(
                        "Add hypotheses and evidence to create the matrix",
                        size="2",
                        color="gray.11",
                    ),
                    padding="4",
                ),
            ),
            # Rating legend
            rx.hstack(
                rx.text("Legend:", size="1", color="gray.11"),
                rx.badge("CC", color_scheme="green", size="1"),
                rx.text("Very Consistent", size="1"),
                rx.badge("C", color_scheme="lime", size="1"),
                rx.text("Consistent", size="1"),
                rx.badge("N", color_scheme="gray", size="1"),
                rx.text("Neutral", size="1"),
                rx.badge("I", color_scheme="orange", size="1"),
                rx.text("Inconsistent", size="1"),
                rx.badge("II", color_scheme="red", size="1"),
                rx.text("Very Inconsistent", size="1"),
                rx.spacer(),
                # Phase 4: Keyboard shortcut hint
                rx.cond(
                    ACHState.focused_evidence_id.is_not_none(),
                    rx.text(
                        "⌨ Keys: 1-5 to rate, ←→↑↓ to navigate",
                        size="1",
                        color="gray.11",
                    ),
                    rx.fragment(),
                ),
                spacing="1",
                wrap="wrap",
            ),
            # Phase 4: Hidden trigger buttons for keyboard shortcuts
            rx.cond(
                ACHState.focused_evidence_id.is_not_none(),
                rx.fragment(
                    # Indicator that ACH matrix has focus
                    rx.box(
                        display="none",
                        data_ach_matrix_active="true",
                    ),
                    # Rating buttons
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.quick_rate("1"),
                        data_ach_rating="1",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.quick_rate("2"),
                        data_ach_rating="2",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.quick_rate("3"),
                        data_ach_rating="3",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.quick_rate("4"),
                        data_ach_rating="4",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.quick_rate("5"),
                        data_ach_rating="5",
                    ),
                    # Navigation buttons
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.navigate_matrix("up"),
                        data_ach_nav="up",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.navigate_matrix("down"),
                        data_ach_nav="down",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.navigate_matrix("left"),
                        data_ach_nav="left",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.navigate_matrix("right"),
                        data_ach_nav="right",
                    ),
                    rx.button(
                        display="none",
                        on_click=lambda: ACHState.navigate_matrix("tab"),
                        data_ach_nav="tab",
                    ),
                ),
                rx.fragment(),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - SCORES
# =============================================================================


def score_bar(s) -> rx.Component:
    """Render a score bar for a hypothesis."""
    # Use the score directly as percentage (capped at 100)
    # Score is typically 0-10+ range, multiply by 10 for percentage
    pct = (s.inconsistency_score * 10).to(int)

    return rx.hstack(
        rx.badge(
            f"#{s.rank}",
            color_scheme=rx.match(
                s.rank,
                (1, "green"),
                (2, "yellow"),
                (3, "orange"),
                "gray",
            ),
            variant="solid",
        ),
        rx.text(s.label, weight="bold", width="50px"),
        rx.progress(
            value=pct,
            max=100,
            width="200px",
            color_scheme=rx.cond(pct < 30, "green", rx.cond(pct < 60, "yellow", "red")),
        ),
        rx.text(
            f"{s.inconsistency_score:.1f}",
            size="2",
            weight="medium",
            width="40px",
        ),
        rx.text(
            s.description,
            size="1",
            color="gray.11",
            flex="1",
            truncate=True,
        ),
        spacing="2",
        width="100%",
        align="center",
    )


def scores_section() -> rx.Component:
    """Scores section (Step 6)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("target", size=18, color="var(--red-9)"),
                rx.heading("Hypothesis Scores", size="5"),
                rx.spacer(),
                rx.text("Lower = better fit", size="1", color="gray.11"),
                width="100%",
                align="center",
            ),
            rx.cond(
                ACHState.scores.length() > 0,
                # Progress bar list view
                rx.vstack(
                    rx.foreach(ACHState.scores, score_bar),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.center(
                    rx.text("Rate the matrix to see scores", size="2", color="gray.11"),
                    padding="3",
                ),
            ),
            # Close race warning
            rx.cond(
                ACHState.close_race_warning,
                rx.callout(
                    ACHState.close_race_warning,
                    icon="triangle-alert",
                    color="yellow",
                    size="1",
                ),
                rx.fragment(),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - CONSISTENCY CHECKS
# =============================================================================


def consistency_check_item(c) -> rx.Component:
    """Render a consistency check result."""
    return rx.hstack(
        rx.icon(
            rx.cond(c.passed, "check-circle", "alert-circle"),
            size=14,
            color=rx.cond(c.passed, "var(--green-9)", "var(--yellow-9)"),
        ),
        rx.text(c.message, size="2"),
        spacing="2",
        width="100%",
    )


def consistency_section() -> rx.Component:
    """Consistency checks section."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("shield-check", size=18, color="var(--cyan-9)"),
                rx.heading("Consistency Checks", size="5"),
                width="100%",
            ),
            rx.vstack(
                rx.foreach(ACHState.consistency_checks, consistency_check_item),
                spacing=SPACING["xs"],
                width="100%",
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - SENSITIVITY (Step 7)
# =============================================================================


def sensitivity_section() -> rx.Component:
    """Sensitivity analysis section (Step 7)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("shield-question", size=18, color="var(--orange-9)"),
                rx.heading("Sensitivity Analysis", size="5"),
                rx.spacer(),
                rx.button(
                    rx.cond(
                        ACHState.is_sensitivity_loading,
                        rx.spinner(size="1"),
                        rx.icon("zap", size=14),
                    ),
                    "Run Analysis",
                    on_click=ACHState.run_sensitivity_analysis,
                    size="2",
                    variant="soft",
                    color_scheme="orange",
                    loading=ACHState.is_sensitivity_loading,
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Identify which evidence is most critical to your conclusion.",
                size="2",
                color="gray.11",
            ),
            # Critical evidence warning (if any)
            rx.cond(
                ACHState.sensitivity_results.length() > 0,
                rx.vstack(
                    rx.foreach(
                        ACHState.sensitivity_results[:3],  # Show top 3
                        lambda s: rx.cond(
                            s["impact"] == "critical",
                            rx.callout(
                                rx.text(
                                    rx.text(s["evidence_label"], weight="bold"),
                                    ": If wrong, the winner would change!",
                                ),
                                icon="triangle-alert",
                                color="red",
                                size="1",
                            ),
                            rx.cond(
                                s["impact"] == "moderate",
                                rx.callout(
                                    rx.text(
                                        rx.text(s["evidence_label"], weight="bold"),
                                        ": If wrong, rankings would shift.",
                                    ),
                                    icon="info",
                                    color="yellow",
                                    size="1",
                                ),
                                rx.fragment(),
                            ),
                        ),
                    ),
                    spacing="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.divider(),
            rx.hstack(
                rx.text("Key Assumptions & Notes", weight="bold", size="2"),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.cond(
                            ACHState.notes_expanded,
                            rx.icon("minimize-2", size=14),
                            rx.icon("maximize-2", size=14),
                        ),
                        on_click=ACHState.toggle_notes_expanded,
                        variant="ghost",
                        size="1",
                    ),
                    content=rx.cond(
                        ACHState.notes_expanded,
                        "Collapse notes",
                        "Expand notes",
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.text_area(
                value=ACHState.sensitivity_notes,
                on_change=ACHState.set_sensitivity_notes,
                on_blur=ACHState.save_sensitivity_notes,
                placeholder="What are your key assumptions? What evidence, if wrong, would change your conclusion?",
                width="100%",
                min_height=rx.cond(
                    ACHState.notes_expanded,
                    "600px",
                    "120px",
                ),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - MILESTONES (Step 8)
# =============================================================================


def milestone_card(m, index: int) -> rx.Component:
    """Render a milestone card."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.badge(
                        rx.cond(
                            m.observed == 1,
                            "OBSERVED",
                            rx.cond(m.observed == -1, "CONTRADICTED", "PENDING"),
                        ),
                        color_scheme=rx.match(
                            m.observed,
                            (1, "green"),
                            (-1, "red"),
                            (0, "gray"),
                            "gray",
                        ),
                        variant="soft",
                        size="1",
                    ),
                    rx.text(m.description, weight="medium", size="2"),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    m.expected_by,
                    rx.hstack(
                        rx.icon("calendar", size=12, color="gray.9"),
                        rx.text(
                            m.expected_by.split("T")[0],
                            size="1",
                            color="gray.11",
                        ),
                        spacing="1",
                        align="center",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    m.observation_notes,
                    rx.text(
                        f"Notes: {m.observation_notes}",
                        size="1",
                        color="gray.11",
                        margin_top="1",
                    ),
                    rx.fragment(),
                ),
                align="start",
                spacing="1",
                flex="1",
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=12),
                    variant="ghost",
                    size="1",
                    on_click=lambda: ACHState.edit_milestone(m.id),
                ),
                rx.button(
                    rx.icon("trash-2", size=12),
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                    on_click=lambda: ACHState.delete_milestone_confirm(m.id),
                ),
                spacing="1",
            ),
            width="100%",
            align="center",
        ),
        width="100%",
        border_left=rx.match(
            m.observed,
            (1, "4px solid var(--green-9)"),
            (-1, "4px solid var(--red-9)"),
            (0, "4px solid var(--gray-6)"),
            "4px solid var(--gray-6)",
        ),
    )


def milestones_section() -> rx.Component:
    """Milestones & Reporting section (Step 8)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("flag", size=18, color="var(--blue-9)"),
                rx.heading("Future Indicators & Milestones", size="5"),
                rx.spacer(),
                rx.cond(
                    ACHState.has_hypotheses,
                    rx.hstack(
                        rx.select.root(
                            rx.select.trigger(
                                placeholder="All",
                                width="90px",
                            ),
                            rx.select.content(
                                rx.select.group(
                                    rx.select.item("All", value="all"),
                                    rx.foreach(
                                        ACHState.hypotheses,
                                        lambda h: rx.select.item(
                                            h.label,
                                            value=h.label,
                                        ),
                                    ),
                                ),
                            ),
                            value=ACHState.milestone_hypothesis_id,
                            on_change=ACHState.set_milestone_hypothesis_id,
                            size="1",
                        ),
                        rx.button(
                            rx.cond(
                                ACHState.is_ai_loading,
                                rx.spinner(size="1"),
                                rx.icon("sparkles", size=12),
                            ),
                            "AI Suggest",
                            on_click=ACHState.request_milestone_suggestions,
                            size="1",
                            variant="soft",
                            color_scheme="purple",
                            loading=ACHState.is_ai_loading,
                        ),
                        spacing="1",
                    ),
                    rx.fragment(),
                ),
                rx.button(
                    rx.icon("plus", size=14),
                    "Add Milestone",
                    on_click=lambda: ACHState.open_add_milestone_dialog(),
                    size="1",
                    variant="soft",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Monitor these indicators to validate or disprove your conclusions over time.",
                size="2",
                color="gray.11",
            ),
            # List of milestones
            rx.cond(
                ACHState.milestones.length() > 0,
                rx.vstack(
                    rx.foreach(ACHState.milestones, lambda m, i: milestone_card(m, i)),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
                rx.center(
                    rx.text("No milestones defined yet.", size="2", color="gray.11"),
                    padding="4",
                ),
            ),
            rx.divider(),
            # History
            history_section(),
            rx.divider(),
            # Export controls (merged into Step 8)
            rx.heading("Final Report", size="4"),
            rx.hstack(
                rx.button(
                    rx.icon("file-text", size=14),
                    "Export Markdown",
                    on_click=ACHState.export_markdown,
                    variant="outline",
                ),
                rx.button(
                    rx.icon("braces", size=14),
                    "Export JSON",
                    on_click=ACHState.export_json,
                    variant="outline",
                ),
                rx.button(
                    rx.icon("file-type", size=14),
                    "Export PDF",
                    on_click=ACHState.open_pdf_preview_dialog,
                    variant="solid",
                    color_scheme="red",
                ),
                spacing="2",
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - EXPORT (Step 8)
# =============================================================================


def export_pdf_preview_dialog() -> rx.Component:
    """Pre-export summary dialog for PDF."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Export PDF Summary"),
                rx.dialog.description(
                    "Review your analysis summary before exporting to PDF.",
                    size="2",
                ),
                rx.divider(),
                # Current Best Hypothesis
                rx.text("Best Hypothesis:", weight="bold", size="2"),
                rx.text(ACHState.best_hypothesis, size="4", color="var(--accent-9)"),
                # AI Disclosure Check
                rx.cond(
                    # If we had a way to check has_ai_content directly on state, we'd use it.
                    # For now, we'll assume if there are any suggestions, we show the notice.
                    # Or simpler: Just a standard notice that AI disclosure will be included.
                    True,
                    rx.callout(
                        "AI Disclosure: This report will include a section noting any AI-assisted elements.",
                        icon="info",
                        color="blue",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.divider(),
                rx.flex(
                    rx.dialog.close(
                        rx.button("Cancel", variant="soft", color_scheme="gray")
                    ),
                    rx.button(
                        "Confirm Download",
                        on_click=ACHState.confirm_export_pdf,
                        variant="solid",
                        color_scheme="red",
                    ),
                    spacing="3",
                    justify="end",
                ),
                spacing="4",
            ),
            style={"max_width": "450px"},
        ),
        open=ACHState.show_pdf_preview_dialog,
        on_open_change=ACHState.close_pdf_preview_dialog,
    )


def export_section() -> rx.Component:
    """Export section (Step 8)."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("file-output", size=18, color="var(--violet-9)"),
                rx.heading("Export Analysis", size="5"),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("file-text", size=14),
                    "Export Markdown",
                    on_click=ACHState.export_markdown,
                    variant="outline",
                ),
                rx.button(
                    rx.icon("braces", size=14),
                    "Export JSON",
                    on_click=ACHState.export_json,
                    variant="outline",
                ),
                rx.button(
                    rx.icon("file-type", size=14),
                    "Export PDF",
                    on_click=ACHState.open_pdf_preview_dialog,
                    variant="solid",
                    color_scheme="red",
                ),
                spacing="2",
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


# =============================================================================
# ANALYSIS DETAIL VIEW - MAIN
# =============================================================================


def analysis_detail_view() -> rx.Component:
    """Main view for an open analysis."""
    return rx.vstack(
        # Header with back button
        rx.hstack(
            rx.button(
                rx.icon("arrow-left", size=14),
                "Back to List",
                on_click=ACHState.close_analysis,
                variant="ghost",
                size="1",
            ),
            rx.spacer(),
            rx.badge(ACHState.status, variant="soft"),
            rx.button(
                rx.icon("download", size=14),
                "Export",
                on_click=ACHState.open_export_dialog,
                variant="outline",
                size="1",
            ),
            width="100%",
            align="center",
        ),
        # Title and focus question
        rx.vstack(
            rx.heading(ACHState.analysis_title, size="7"),
            rx.text(
                ACHState.focus_question,
                size="3",
                color="gray.11",
            ),
            align="start",
            spacing="1",
            width="100%",
        ),
        # Step indicator
        ach_step_indicator(),
        # Step guidance
        ach_guidance_for_current_step(),
        # Content based on current step
        rx.match(
            ACHState.current_step,
            # Step 1: Hypotheses
            (1, hypotheses_section()),
            # Step 2: Evidence
            (2, evidence_section()),
            # Step 3: Matrix
            (
                3,
                rx.vstack(
                    matrix_section(),
                    spacing=SPACING["md"],
                    width="100%",
                ),
            ),
            # Step 4: Diagnosticity - show matrix with sorting
            (
                4,
                rx.vstack(
                    evidence_section(),
                    spacing=SPACING["md"],
                    width="100%",
                ),
            ),
            # Step 5: Refine - show all editable
            (
                5,
                rx.vstack(
                    hypotheses_section(),
                    evidence_section(),
                    matrix_section(),
                    spacing=SPACING["md"],
                    width="100%",
                ),
            ),
            # Step 6: Scores
            (
                6,
                rx.vstack(
                    scores_section(),
                    consistency_section(),
                    spacing=SPACING["md"],
                    width="100%",
                ),
            ),
            # Step 7: Sensitivity
            (7, sensitivity_section()),
            # Step 8: Export -> Milestones & Export
            (8, milestones_section()),
            # Default
            hypotheses_section(),
        ),
        # Always show scores after step 3
        rx.cond(
            ACHState.current_step >= 3,
            rx.accordion.root(
                rx.accordion.item(
                    header="Quick View: Scores",
                    content=scores_section(),
                ),
                rx.accordion.item(
                    header="Quick View: Consistency Checks",
                    content=consistency_section(),
                ),
                type="multiple",
                variant="soft",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing=SPACING["md"],
        width="100%",
        align="start",
    )


# =============================================================================
# DIALOGS
# =============================================================================


def new_analysis_dialog() -> rx.Component:
    """Dialog for creating a new analysis."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("New ACH Analysis"),
            rx.dialog.description(
                "Define your focus question - the central question you want to analyze."
            ),
            rx.vstack(
                rx.text("Title", weight="medium", size="2"),
                rx.input(
                    value=ACHState.new_analysis_title,
                    on_change=ACHState.set_new_analysis_title,
                    placeholder="Short title for this analysis",
                    width="100%",
                ),
                rx.text("Focus Question", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_focus_question,
                    on_change=ACHState.set_new_focus_question,
                    placeholder="What question are you trying to answer?",
                    width="100%",
                ),
                rx.text("Description (optional)", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_analysis_description,
                    on_change=ACHState.set_new_analysis_description,
                    placeholder="Additional context or background",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_new_analysis_dialog,
                    ),
                ),
                rx.button(
                    "Create Analysis",
                    on_click=ACHState.create_analysis,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_new_analysis_dialog,
        on_open_change=ACHState.set_show_new_analysis_dialog,
    )


def add_hypothesis_dialog() -> rx.Component:
    """Dialog for adding a hypothesis."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Add Hypothesis"),
            rx.dialog.description(
                "Add a plausible explanation for your focus question."
            ),
            rx.vstack(
                rx.text("Hypothesis Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_hypothesis_description,
                    on_change=ACHState.set_new_hypothesis_description,
                    placeholder="Describe this hypothesis...",
                    width="100%",
                    min_height="100px",
                ),
                rx.callout(
                    "Remember: Include unlikely explanations too. Consider a 'null hypothesis' - what if nothing unusual happened?",
                    icon="info",
                    color="blue",
                    size="1",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_add_hypothesis_dialog,
                    ),
                ),
                rx.button(
                    "Add Hypothesis",
                    on_click=ACHState.add_hypothesis,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_add_hypothesis_dialog,
        on_open_change=ACHState.set_show_add_hypothesis_dialog,
    )


def add_evidence_dialog() -> rx.Component:
    """Dialog for adding evidence."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Add Evidence"),
            rx.dialog.description("Add a piece of evidence or argument."),
            rx.vstack(
                rx.text("Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_evidence_description,
                    on_change=ACHState.set_new_evidence_description,
                    placeholder="Describe this evidence...",
                    width="100%",
                ),
                rx.hstack(
                    rx.vstack(
                        rx.text("Type", weight="medium", size="2"),
                        rx.select(
                            EVIDENCE_TYPES,
                            value=ACHState.new_evidence_type,
                            on_change=ACHState.set_new_evidence_type,
                        ),
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("Reliability", weight="medium", size="2"),
                        rx.select(
                            RELIABILITY_OPTIONS,
                            value=ACHState.new_evidence_reliability,
                            on_change=ACHState.set_new_evidence_reliability,
                        ),
                        flex="1",
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.text("Source Quote (optional)", weight="medium", size="2"),
                rx.input(
                    value=ACHState.new_evidence_source,
                    on_change=ACHState.set_new_evidence_source,
                    placeholder="Original text or citation",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_add_evidence_dialog,
                    ),
                ),
                rx.button(
                    "Add Evidence",
                    on_click=ACHState.add_evidence,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_add_evidence_dialog,
        on_open_change=ACHState.set_show_add_evidence_dialog,
    )


def edit_hypothesis_dialog() -> rx.Component:
    """Dialog for editing a hypothesis."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Edit Hypothesis"),
            rx.vstack(
                rx.text("Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.edit_hypothesis_description,
                    on_change=ACHState.set_edit_hypothesis_description,
                    width="100%",
                ),
                rx.text("Future Indicators (Step 8)", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.edit_hypothesis_future_indicators,
                    on_change=ACHState.set_edit_hypothesis_future_indicators,
                    placeholder="If this hypothesis is true, what would we expect to see in the future?",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_edit_hypothesis_dialog,
                    ),
                ),
                rx.button(
                    "Save Changes",
                    on_click=ACHState.save_hypothesis,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_edit_hypothesis_dialog,
        on_open_change=ACHState.set_show_edit_hypothesis_dialog,
    )


def edit_evidence_dialog() -> rx.Component:
    """Dialog for editing evidence."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Edit Evidence"),
            rx.vstack(
                rx.text("Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.edit_evidence_description,
                    on_change=ACHState.set_edit_evidence_description,
                    width="100%",
                ),
                rx.hstack(
                    rx.vstack(
                        rx.text("Type", weight="medium", size="2"),
                        rx.select(
                            EVIDENCE_TYPES,
                            value=ACHState.edit_evidence_type,
                            on_change=ACHState.set_edit_evidence_type,
                        ),
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("Reliability", weight="medium", size="2"),
                        rx.select(
                            RELIABILITY_OPTIONS,
                            value=ACHState.edit_evidence_reliability,
                            on_change=ACHState.set_edit_evidence_reliability,
                        ),
                        flex="1",
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.text("Source Quote", weight="medium", size="2"),
                rx.input(
                    value=ACHState.edit_evidence_source,
                    on_change=ACHState.set_edit_evidence_source,
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_edit_evidence_dialog,
                    ),
                ),
                rx.button(
                    "Save Changes",
                    on_click=ACHState.save_evidence,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_edit_evidence_dialog,
        on_open_change=ACHState.set_show_edit_evidence_dialog,
    )


def delete_confirm_dialog() -> rx.Component:
    """Confirmation dialog for deletions."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Confirm Delete"),
            rx.dialog.description(
                f"Are you sure you want to delete '{ACHState.delete_label}'? This cannot be undone."
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.cancel_delete,
                    ),
                ),
                rx.button(
                    "Delete",
                    on_click=ACHState.confirm_delete,
                    color_scheme="red",
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
        ),
        open=ACHState.show_delete_confirm_dialog,
        on_open_change=ACHState.set_show_delete_confirm_dialog,
    )


# =============================================================================
# AI ASSISTANCE DIALOGS
# =============================================================================


def snapshot_dialog() -> rx.Component:
    """Dialog for creating a snapshot."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Create Snapshot"),
            rx.dialog.description("Save a read-only version of the current analysis."),
            rx.vstack(
                rx.text("Label", weight="medium", size="2"),
                rx.input(
                    value=ACHState.new_snapshot_label,
                    on_change=ACHState.set_new_snapshot_label,
                    placeholder="E.g., Initial Hypotheses",
                    width="100%",
                ),
                rx.text("Description (Optional)", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_snapshot_description,
                    on_change=ACHState.set_new_snapshot_description,
                    placeholder="What changed in this version?",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_snapshot_dialog,
                    )
                ),
                rx.button(
                    "Create Snapshot",
                    on_click=ACHState.save_snapshot,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="450px",
        ),
        open=ACHState.show_snapshot_dialog,
        on_open_change=ACHState.set_show_snapshot_dialog,
    )


def history_card(snapshot: dict) -> rx.Component:
    """Render a single snapshot card with compare action."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text(snapshot["label"], weight="bold", size="2"),
                rx.text(snapshot["description"], size="1", color="gray.11"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.text(
                    snapshot["created_at"].split("T")[0],
                    size="1",
                    color="gray.11",
                ),
                rx.button(
                    rx.icon("git-compare", size=12),
                    "vs Current",
                    size="1",
                    variant="ghost",
                    loading=ACHState.is_loading,
                    on_click=lambda sid=snapshot["id"]: ACHState.compare_snapshot_to_current(sid),
                ),
                align="end",
                spacing="1",
            ),
            width="100%",
            align="center",
        ),
        size="1",
        width="100%",
    )


def diff_line(text: str, prefix: str, color: str) -> rx.Component:
    """Render a git-style diff line with configurable prefix and color."""
    return rx.box(
        rx.text(
            f"{prefix} {text}",
            size="1",
            style={"fontFamily": "monospace"},
        ),
        padding="4px 8px",
        background=f"var(--{color}-3)",
        border_radius="4px",
        width="100%",
    )


def diff_rating_line(rating: dict) -> rx.Component:
    """Render a rating change diff line (for use in rx.foreach)."""
    return rx.box(
        rx.text(
            "~ ",
            rating["evidence_label"],
            " / ",
            rating["hypothesis_label"],
            ": ",
            rating["old"],
            " -> ",
            rating["new"],
            size="1",
            style={"fontFamily": "monospace"},
        ),
        padding="4px 8px",
        background="var(--amber-3)",
        border_radius="4px",
        width="100%",
    )


def diff_milestone_status_line(milestone: dict) -> rx.Component:
    """Render a milestone status change diff line (for use in rx.foreach)."""
    return rx.box(
        rx.text(
            "~ ",
            milestone["description"],
            ": ",
            milestone["old_status"],
            " -> ",
            milestone["new_status"],
            size="1",
            style={"fontFamily": "monospace"},
        ),
        padding="4px 8px",
        background="var(--amber-3)",
        border_radius="4px",
        width="100%",
    )


def snapshot_comparison_dialog() -> rx.Component:
    """Dialog showing comparison between two snapshots with git-diff styling."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Version Comparison"),
            rx.dialog.description(
                rx.hstack(
                    rx.text("Comparing ", color="gray.11"),
                    rx.badge(ACHState.diff_meta_s1_label, variant="soft"),
                    rx.text(" -> ", color="gray.11"),
                    rx.badge(ACHState.diff_meta_s2_label, variant="soft", color="blue"),
                )
            ),
            rx.scroll_area(
                rx.vstack(
                    # No changes indicator
                    rx.cond(
                        ~ACHState.diff_has_changes,
                        rx.callout(
                            "No changes detected between versions.",
                            icon="check",
                            color="green",
                            size="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Score Changes
                    rx.cond(
                        ACHState.diff_scores_winner_changed,
                        rx.callout(
                            rx.hstack(
                                rx.text("Winner Changed: "),
                                rx.text(ACHState.diff_scores_old_winner, weight="bold"),
                                rx.text(" -> "),
                                rx.text(ACHState.diff_scores_new_winner, weight="bold"),
                            ),
                            icon="triangle-alert",
                            color="amber",
                            size="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Hypotheses Changes
                    rx.cond(
                        (ACHState.diff_hypotheses_added.length() > 0)
                        | (ACHState.diff_hypotheses_removed.length() > 0),
                        rx.vstack(
                            rx.heading("Hypotheses", size="3"),
                            rx.foreach(
                                ACHState.diff_hypotheses_added,
                                lambda x: diff_line(x, "+", "green"),
                            ),
                            rx.foreach(
                                ACHState.diff_hypotheses_removed,
                                lambda x: diff_line(x, "-", "red"),
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Evidence Changes
                    rx.cond(
                        (ACHState.diff_evidence_added.length() > 0)
                        | (ACHState.diff_evidence_removed.length() > 0),
                        rx.vstack(
                            rx.heading("Evidence", size="3"),
                            rx.foreach(
                                ACHState.diff_evidence_added,
                                lambda x: diff_line(x, "+", "green"),
                            ),
                            rx.foreach(
                                ACHState.diff_evidence_removed,
                                lambda x: diff_line(x, "-", "red"),
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Rating Changes (limited with "and X more..." indicator)
                    rx.cond(
                        ACHState.diff_ratings_total_count > 0,
                        rx.vstack(
                            rx.hstack(
                                rx.heading("Rating Changes", size="3"),
                                rx.badge(
                                    ACHState.diff_ratings_total_count.to(str),
                                    variant="soft",
                                    size="1",
                                ),
                                align="center",
                                spacing="2",
                            ),
                            rx.foreach(
                                ACHState.diff_ratings_changes,
                                diff_rating_line,
                            ),
                            rx.cond(
                                ACHState.diff_ratings_has_more,
                                rx.text(
                                    "... and "
                                    + ACHState.diff_ratings_remaining_count.to(str)
                                    + " more rating changes",
                                    size="1",
                                    color="gray.11",
                                    style={"fontStyle": "italic"},
                                ),
                                rx.fragment(),
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    # Milestone Changes
                    rx.cond(
                        (ACHState.diff_milestones_added.length() > 0)
                        | (ACHState.diff_milestones_removed.length() > 0)
                        | (ACHState.diff_milestones_status_changes.length() > 0),
                        rx.vstack(
                            rx.heading("Milestones", size="3"),
                            rx.foreach(
                                ACHState.diff_milestones_added,
                                lambda x: diff_line(x, "+", "green"),
                            ),
                            rx.foreach(
                                ACHState.diff_milestones_removed,
                                lambda x: diff_line(x, "-", "red"),
                            ),
                            rx.foreach(
                                ACHState.diff_milestones_status_changes,
                                diff_milestone_status_line,
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    spacing="3",
                    width="100%",
                ),
                max_height="60vh",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_comparison_dialog,
                    )
                ),
                justify="end",
                margin_top="4",
            ),
            max_width="650px",
        ),
        open=ACHState.show_comparison_dialog,
        on_open_change=ACHState.set_show_comparison_dialog,
    )


def history_section() -> rx.Component:
    """Analysis history and versioning section."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("history", size=18, color="var(--amber-9)"),
                rx.heading("Version History", size="4"),
                rx.spacer(),
                rx.button(
                    rx.icon("camera", size=14),
                    "Snapshot",
                    on_click=ACHState.open_snapshot_dialog,
                    size="1",
                    variant="soft",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Track how your analysis evolves over time.",
                size="2",
                color="gray.11",
            ),
            # Comparison Controls
            rx.cond(
                ACHState.snapshots.length() >= 2,
                rx.hstack(
                    rx.select(
                        ACHState.snapshot_labels,
                        placeholder="Old Version",
                        value=ACHState.comparison_snapshot_label,
                        on_change=ACHState.set_comparison_by_label,
                        width="40%",
                    ),
                    rx.icon("arrow-right", size=14, color="gray.9"),
                    rx.select(
                        ACHState.snapshot_labels,
                        placeholder="New Version",
                        value=ACHState.selected_snapshot_label,
                        on_change=ACHState.set_selected_by_label,
                        width="40%",
                    ),
                    rx.button(
                        "Compare",
                        on_click=ACHState.compare_snapshots,
                        disabled=~(
                            ACHState.selected_snapshot_id
                            & ACHState.comparison_snapshot_id
                        ),
                        width="20%",
                        variant="soft",
                    ),
                    width="100%",
                    align="center",
                    spacing="2",
                ),
                rx.fragment(),
            ),
            rx.divider(),
            # History List
            rx.cond(
                ACHState.snapshots.length() > 0,
                rx.vstack(
                    rx.foreach(ACHState.snapshots, history_card),
                    spacing="2",
                    width="100%",
                    max_height="200px",
                    overflow="auto",
                    on_mount=ACHState.load_snapshots,
                ),
                rx.center(
                    rx.button(
                        "Load History",
                        on_click=ACHState.load_snapshots,
                        variant="ghost",
                        size="1",
                    ),
                    padding="2",
                ),
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


def add_milestone_dialog() -> rx.Component:
    """Dialog for adding a milestone."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Add Milestone"),
            rx.dialog.description(
                "What future event indicates a hypothesis is coming true?"
            ),
            rx.vstack(
                rx.text("Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.new_milestone_description,
                    on_change=ACHState.set_new_milestone_description,
                    placeholder="E.g., 'If H1 is true, we expect to see X by next month'",
                    width="100%",
                ),
                rx.text("Related Hypothesis", weight="medium", size="2"),
                rx.select.root(
                    rx.select.trigger(placeholder="Select Hypothesis...", width="100%"),
                    rx.select.content(
                        rx.select.group(
                            rx.foreach(
                                ACHState.hypotheses,
                                lambda h: rx.select.item(
                                    h.label,
                                    value=h.id.to(str),
                                ),
                            ),
                        ),
                    ),
                    value=ACHState.new_milestone_hypothesis_id,
                    on_change=ACHState.set_new_milestone_hypothesis_id,
                    width="100%",
                ),
                rx.text("Expected By (Optional)", weight="medium", size="2"),
                rx.input(
                    type="date",
                    value=ACHState.new_milestone_expected_by,
                    on_change=ACHState.set_new_milestone_expected_by,
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_add_milestone_dialog,
                    )
                ),
                rx.button(
                    "Add Milestone",
                    on_click=ACHState.add_milestone,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_add_milestone_dialog,
        on_open_change=ACHState.set_show_add_milestone_dialog,
    )


def edit_milestone_dialog() -> rx.Component:
    """Dialog for editing a milestone."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Edit Milestone"),
            rx.vstack(
                rx.text("Description", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.edit_milestone_description,
                    on_change=ACHState.set_edit_milestone_description,
                    width="100%",
                ),
                rx.hstack(
                    rx.vstack(
                        rx.text("Status", weight="medium", size="2"),
                        rx.select(
                            ["0", "1", "-1"],
                            value=ACHState.edit_milestone_observed,
                            on_change=ACHState.set_edit_milestone_observed,
                        ),
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("Expected By", weight="medium", size="2"),
                        rx.input(
                            type="date",
                            value=ACHState.edit_milestone_expected_by,
                            on_change=ACHState.set_edit_milestone_expected_by,
                            width="100%",
                        ),
                        flex="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.text("Observation Notes", weight="medium", size="2"),
                rx.text_area(
                    value=ACHState.edit_milestone_notes,
                    on_change=ACHState.set_edit_milestone_notes,
                    placeholder="Details about the observation...",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_edit_milestone_dialog,
                    )
                ),
                rx.button(
                    "Save Changes",
                    on_click=ACHState.save_milestone,
                    loading=ACHState.is_loading,
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=ACHState.show_edit_milestone_dialog,
        on_open_change=ACHState.set_show_edit_milestone_dialog,
    )


def ai_hypothesis_suggestion_card(suggestion, index: int) -> rx.Component:
    """Render a single hypothesis suggestion card."""
    return rx.card(
        rx.vstack(
            rx.text(suggestion["description"], weight="medium"),
            rx.text(
                suggestion.get("rationale", ""),
                size="2",
                color="gray.11",
            ),
            rx.cond(
                suggestion.get("is_null", False),
                rx.badge("Null Hypothesis", variant="soft", color_scheme="gray"),
                rx.fragment(),
            ),
            rx.hstack(
                rx.button(
                    rx.icon("check", size=12),
                    "Accept",
                    on_click=lambda: ACHState.accept_hypothesis_suggestion(index),
                    size="1",
                    color_scheme="green",
                ),
                rx.button(
                    rx.icon("x", size=12),
                    "Skip",
                    variant="ghost",
                    size="1",
                ),
                justify="end",
                spacing="1",
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
    )


def ai_hypothesis_dialog() -> rx.Component:
    """Dialog for AI hypothesis suggestions."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--violet-9)"),
                    "AI Hypothesis Suggestions",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "The AI has suggested these hypotheses based on your focus question. "
                "Accept the ones you want to add, or skip them."
            ),
            rx.vstack(
                rx.foreach(
                    ACHState.ai_hypothesis_suggestions,
                    lambda s, i: ai_hypothesis_suggestion_card(s, i),
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_ai_hypothesis_dialog,
                    ),
                ),
                rx.button(
                    "Accept All",
                    on_click=ACHState.accept_all_hypothesis_suggestions,
                    color_scheme="green",
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="600px",
        ),
        open=ACHState.show_ai_hypothesis_dialog,
        on_open_change=ACHState.set_show_ai_hypothesis_dialog,
    )


def ai_challenge_card(challenge) -> rx.Component:
    """Render a single challenge card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(challenge.get("hypothesis_label", ""), color_scheme="blue"),
                rx.text("Challenge", weight="bold", size="2"),
                spacing="2",
            ),
            rx.box(
                rx.text("Counter-argument:", weight="medium", size="2", color="red.11"),
                rx.text(challenge.get("counter_argument", ""), size="2"),
                width="100%",
            ),
            rx.box(
                rx.text(
                    "Would be disproved if:",
                    weight="medium",
                    size="2",
                    color="orange.11",
                ),
                rx.text(challenge.get("disproof_evidence", ""), size="2"),
                width="100%",
            ),
            rx.box(
                rx.text(
                    "Alternative angle:", weight="medium", size="2", color="violet.11"
                ),
                rx.text(challenge.get("alternative_angle", ""), size="2"),
                width="100%",
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
        border_left="3px solid var(--orange-8)",
    )


def ai_challenge_dialog() -> rx.Component:
    """Dialog for AI devil's advocate challenges."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("swords", size=18, color="var(--orange-9)"),
                    "Devil's Advocate Challenges",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "The AI has generated challenges to your hypotheses. "
                "Consider these counter-arguments to strengthen your analysis."
            ),
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(ACHState.ai_challenges, ai_challenge_card),
                    spacing="3",
                    width="100%",
                ),
                max_height="400px",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("save", size=14),
                    "Save to Notes",
                    on_click=ACHState.save_challenges_to_notes,
                    variant="soft",
                    color_scheme="green",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        on_click=ACHState.close_ai_challenge_dialog,
                    ),
                ),
                width="100%",
                margin_top="4",
            ),
            max_width="700px",
        ),
        open=ACHState.show_ai_challenge_dialog,
        on_open_change=ACHState.set_show_ai_challenge_dialog,
    )


def ai_evidence_suggestion_card(suggestion, index: int) -> rx.Component:
    """Render a single evidence suggestion card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    suggestion.get("evidence_type", "fact"), variant="outline", size="1"
                ),
                rx.text(suggestion["description"], weight="medium", flex="1"),
                spacing="2",
            ),
            rx.text(
                suggestion.get("importance", ""),
                size="2",
                color="gray.11",
            ),
            # Note: would_support/would_contradict info displayed via tooltips or description
            rx.hstack(
                rx.button(
                    rx.icon("check", size=12),
                    "Add",
                    on_click=lambda: ACHState.accept_evidence_suggestion(index),
                    size="1",
                    color_scheme="green",
                ),
                rx.button(
                    rx.icon("x", size=12),
                    "Skip",
                    variant="ghost",
                    size="1",
                ),
                justify="end",
                spacing="1",
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
    )


def ai_evidence_dialog() -> rx.Component:
    """Dialog for AI evidence suggestions."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--violet-9)"),
                    "AI Evidence Suggestions",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "The AI suggests considering these evidence items. "
                "They are designed to help discriminate between your hypotheses."
            ),
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        ACHState.ai_evidence_suggestions,
                        lambda s, i: ai_evidence_suggestion_card(s, i),
                    ),
                    spacing="2",
                    width="100%",
                ),
                max_height="400px",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_ai_evidence_dialog,
                    ),
                ),
                justify="end",
                margin_top="4",
            ),
            max_width="650px",
        ),
        open=ACHState.show_ai_evidence_dialog,
        on_open_change=ACHState.set_show_ai_evidence_dialog,
    )


def ai_rating_suggestion_card(suggestion) -> rx.Component:
    """Render a single rating suggestion card."""
    rating = suggestion.get("rating", "N")
    return rx.hstack(
        rx.badge(
            suggestion.get("hypothesis_label", ""),
            color_scheme="blue",
            variant="solid",
            min_width="40px",
        ),
        rx.badge(
            rating,
            color_scheme=RATING_COLORS.get(rating, "gray"),
            variant="solid",
        ),
        rx.text(
            suggestion.get("explanation", ""),
            size="2",
            flex="1",
        ),
        rx.button(
            rx.icon("check", size=10),
            on_click=lambda: ACHState.accept_rating_suggestion(
                suggestion.get("hypothesis_id", 0), rating
            ),
            size="1",
            variant="soft",
            color_scheme="green",
        ),
        spacing="2",
        width="100%",
        align="center",
    )


def ai_rating_dialog() -> rx.Component:
    """Dialog for AI rating suggestions."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--violet-9)"),
                    f"AI Rating Suggestions for {ACHState.ai_rating_evidence_label}",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "The AI suggests these ratings based on the evidence and hypotheses. "
                "You can accept them individually or all at once."
            ),
            rx.vstack(
                rx.foreach(ACHState.ai_rating_suggestions, ai_rating_suggestion_card),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_ai_rating_dialog,
                    ),
                ),
                rx.button(
                    "Accept All",
                    on_click=ACHState.accept_all_rating_suggestions,
                    color_scheme="green",
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="600px",
        ),
        open=ACHState.show_ai_rating_dialog,
        on_open_change=ACHState.set_show_ai_rating_dialog,
    )


def ai_milestone_suggestion_card(suggestion) -> rx.Component:
    """Render a single milestone suggestion card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    suggestion["hypothesis_label"],
                    color_scheme="blue",
                    size="1",
                ),
                rx.badge(
                    suggestion.get("expected_timeframe", "N/A"),
                    color_scheme="gray",
                    size="1",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("plus", size=12),
                    "Accept",
                    on_click=lambda: ACHState.accept_milestone_suggestion(suggestion),
                    size="1",
                    variant="soft",
                    color_scheme="green",
                ),
                width="100%",
                align="center",
            ),
            rx.text(suggestion.get("description", ""), size="2"),
            rx.text(
                suggestion.get("rationale", ""),
                size="1",
                color="gray.11",
                style={"font_style": "italic"},
            ),
            spacing="2",
            width="100%",
        ),
        width="100%",
    )


def ai_milestone_dialog() -> rx.Component:
    """Dialog for AI milestone suggestions."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--purple-9)"),
                    "AI Milestone Suggestions",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "Suggested observable milestones to track your hypotheses over time. "
                "Click 'Accept' to add any suggestion as a milestone."
            ),
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        ACHState.ai_milestone_suggestions, ai_milestone_suggestion_card
                    ),
                    spacing="2",
                    width="100%",
                ),
                max_height="400px",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_ai_milestone_dialog,
                    ),
                ),
                rx.button(
                    "Accept All",
                    on_click=ACHState.accept_all_milestone_suggestions,
                    color_scheme="green",
                ),
                justify="end",
                spacing="2",
                margin_top="4",
            ),
            max_width="600px",
        ),
        open=ACHState.show_ai_milestone_dialog,
        on_open_change=ACHState.set_show_ai_milestone_dialog,
    )


# =============================================================================
# PHASE 3: CORPUS IMPORT DIALOG
# =============================================================================


def import_search_result_item(result) -> rx.Component:
    """Render a search result item for import."""
    return rx.hstack(
        rx.checkbox(
            checked=ACHState.import_selected_ids.contains(result["id"]),
            on_change=lambda _: ACHState.toggle_import_selection(result["id"]),
        ),
        rx.vstack(
            rx.hstack(
                rx.badge(f"{result['score']:.2f}", color_scheme="blue", size="1"),
                rx.text(result["doc_title"], size="2", weight="medium"),
                spacing="2",
            ),
            rx.text(result["text"], size="1", color="gray.11"),
            align="start",
            spacing="1",
            flex="1",
        ),
        width="100%",
        padding="2",
        border_radius="4px",
        _hover={"background": "var(--gray-3)"},
        align="start",
    )


def import_contradiction_item(contradiction) -> rx.Component:
    """Render a contradiction item for import."""
    return rx.hstack(
        rx.checkbox(
            checked=ACHState.import_selected_ids.contains(contradiction["id"]),
            on_change=lambda _: ACHState.toggle_import_selection(contradiction["id"]),
        ),
        rx.vstack(
            rx.hstack(
                rx.badge(
                    contradiction["severity"],
                    color_scheme=rx.match(
                        contradiction["severity"],
                        ("high", "red"),
                        ("medium", "yellow"),
                        ("low", "gray"),
                        "gray",
                    ),
                    size="1",
                ),
                rx.text(contradiction["entity_name"], size="2", weight="medium"),
                spacing="2",
            ),
            rx.text(contradiction["description"], size="1", color="gray.11"),
            align="start",
            spacing="1",
            flex="1",
        ),
        width="100%",
        padding="2",
        border_radius="4px",
        _hover={"background": "var(--gray-3)"},
        align="start",
    )


def import_timeline_item(event) -> rx.Component:
    """Render a timeline event item for import."""
    return rx.hstack(
        rx.checkbox(
            checked=ACHState.import_selected_ids.contains(event["id"]),
            on_change=lambda _: ACHState.toggle_import_selection(event["id"]),
        ),
        rx.vstack(
            rx.hstack(
                rx.badge(event["date"], color_scheme="blue", size="1"),
                rx.cond(
                    event["event_type"],
                    rx.badge(event["event_type"], variant="outline", size="1"),
                    rx.fragment(),
                ),
                spacing="2",
            ),
            rx.text(event["description"], size="1", color="gray.11"),
            align="start",
            spacing="1",
            flex="1",
        ),
        width="100%",
        padding="2",
        border_radius="4px",
        _hover={"background": "var(--gray-3)"},
        align="start",
    )


def import_search_tab() -> rx.Component:
    """Search tab content for import dialog."""
    return rx.vstack(
        rx.hstack(
            rx.input(
                value=ACHState.import_search_query,
                on_change=ACHState.set_import_search_query,
                placeholder="Search documents...",
                width="100%",
            ),
            rx.button(
                rx.icon("search", size=14),
                "Search",
                on_click=ACHState.execute_import_search,
                loading=ACHState.is_import_loading,
            ),
            width="100%",
        ),
        rx.cond(
            ACHState.import_search_results.length() > 0,
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        ACHState.import_search_results, import_search_result_item
                    ),
                    spacing="1",
                    width="100%",
                ),
                max_height="300px",
            ),
            rx.center(
                rx.text(
                    "Enter a search query to find documents", size="2", color="gray.11"
                ),
                padding="4",
            ),
        ),
        spacing="3",
        width="100%",
    )


def import_contradictions_tab() -> rx.Component:
    """Contradictions tab content for import dialog."""
    return rx.cond(
        ACHState.is_import_loading,
        rx.center(rx.spinner(size="3"), padding="4"),
        rx.cond(
            ACHState.import_contradictions.length() > 0,
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        ACHState.import_contradictions, import_contradiction_item
                    ),
                    spacing="1",
                    width="100%",
                ),
                max_height="350px",
            ),
            rx.center(
                rx.text(
                    "No contradictions found in this project", size="2", color="gray.11"
                ),
                padding="4",
            ),
        ),
    )


def import_timeline_tab() -> rx.Component:
    """Timeline tab content for import dialog."""
    return rx.cond(
        ACHState.is_import_loading,
        rx.center(rx.spinner(size="3"), padding="4"),
        rx.cond(
            ACHState.import_timeline_events.length() > 0,
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(ACHState.import_timeline_events, import_timeline_item),
                    spacing="1",
                    width="100%",
                ),
                max_height="350px",
            ),
            rx.center(
                rx.text(
                    "No timeline events found in this project",
                    size="2",
                    color="gray.11",
                ),
                padding="4",
            ),
        ),
    )


def import_dialog() -> rx.Component:
    """Dialog for importing evidence from corpus."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("download", size=18, color="var(--cyan-9)"),
                    "Import Evidence from Corpus",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.dialog.description(
                "Search your documents or browse contradictions and timeline events to import as evidence."
            ),
            # Tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Search", value="search"),
                    rx.tabs.trigger("Contradictions", value="contradictions"),
                    rx.tabs.trigger("Timeline", value="timeline"),
                ),
                rx.tabs.content(import_search_tab(), value="search"),
                rx.tabs.content(import_contradictions_tab(), value="contradictions"),
                rx.tabs.content(import_timeline_tab(), value="timeline"),
                default_value="search",
                value=ACHState.import_tab,
                on_change=ACHState.set_import_tab,
            ),
            # Error message
            rx.cond(
                ACHState.import_error,
                rx.callout(
                    ACHState.import_error,
                    icon="circle-alert",
                    color="red",
                    size="1",
                ),
                rx.fragment(),
            ),
            # Footer
            rx.hstack(
                rx.text(
                    f"Selected: {ACHState.import_selected_count} items",
                    size="2",
                    color="gray.11",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_import_dialog,
                    ),
                ),
                rx.button(
                    "Import Selected",
                    on_click=ACHState.import_selected_items,
                    color_scheme="cyan",
                    disabled=ACHState.import_selected_count == 0,
                    loading=ACHState.is_import_loading,
                ),
                width="100%",
                margin_top="4",
            ),
            max_width="700px",
        ),
        open=ACHState.show_import_dialog,
        on_open_change=ACHState.set_show_import_dialog,
    )


def sensitivity_results_dialog() -> rx.Component:
    """Dialog showing sensitivity analysis results."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Sensitivity Analysis Results"),
            rx.dialog.description(
                "How vulnerable are your conclusions to changes in evidence?"
            ),
            rx.cond(
                ACHState.sensitivity_results.length() > 0,
                rx.vstack(
                    rx.foreach(
                        ACHState.sensitivity_results,
                        lambda s: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    rx.text(s["evidence_label"], weight="bold"),
                                    rx.spacer(),
                                    rx.badge(
                                        s["impact"],
                                        color_scheme=rx.match(
                                            s["impact"],
                                            ("critical", "red"),
                                            ("moderate", "yellow"),
                                            "gray",
                                        ),
                                    ),
                                    width="100%",
                                ),
                                rx.text(s["description"], size="2"),
                                width="100%",
                            ),
                            width="100%",
                        ),
                    ),
                    spacing="2",
                    max_height="60vh",
                    overflow_y="auto",
                    width="100%",
                ),
                rx.text("No sensitivity issues found or not run yet."),
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ACHState.close_sensitivity_dialog,
                    )
                ),
                justify="end",
                margin_top="4",
            ),
            max_width="600px",
        ),
        open=ACHState.show_sensitivity_dialog,
        on_open_change=ACHState.set_show_sensitivity_dialog,
    )


def save_confirmation_dialog() -> rx.Component:
    """Dialog confirming challenges were saved to notes."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.hstack(
                    rx.icon("circle-check", size=18, color="var(--green-9)"),
                    "Challenges Saved!",
                    spacing="2",
                    align="center",
                ),
            ),
            rx.vstack(
                rx.text(
                    "Your AI-generated challenges have been saved to the ",
                    rx.text("Sensitivity Notes", weight="bold"),
                    " field.",
                ),
                rx.callout(
                    rx.vstack(
                        rx.text("To view your saved challenges:", size="2"),
                        rx.text(
                            "1. Go to Step 7: Sensitivity Analysis",
                            size="2",
                            color="gray.11",
                        ),
                        rx.text(
                            '2. Look under "Key Assumptions & Notes"',
                            size="2",
                            color="gray.11",
                        ),
                        spacing="1",
                    ),
                    icon="info",
                    color="blue",
                    size="1",
                ),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Got It",
                        color_scheme="green",
                        on_click=ACHState.close_save_confirmation,
                    ),
                ),
                justify="end",
                margin_top="4",
            ),
            max_width="450px",
        ),
        open=ACHState.show_save_confirmation,
        on_open_change=ACHState.close_save_confirmation,
    )


# =============================================================================
# MAIN PAGE
# =============================================================================


def ach_page() -> rx.Component:
    """Main ACH page."""
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.cond(
                ACHState.has_analysis,
                analysis_detail_view(),
                analysis_list_view(),
            ),
            # Dialogs
            new_analysis_dialog(),
            add_hypothesis_dialog(),
            add_evidence_dialog(),
            snapshot_dialog(),
            snapshot_comparison_dialog(),
            add_milestone_dialog(),
            edit_hypothesis_dialog(),
            edit_evidence_dialog(),
            edit_milestone_dialog(),
            delete_confirm_dialog(),
            # AI Assistance Dialogs
            ai_hypothesis_dialog(),
            ai_challenge_dialog(),
            ai_evidence_dialog(),
            ai_rating_dialog(),
            ai_milestone_dialog(),
            # Phase 3: Corpus Import Dialog
            import_dialog(),
            # Phase 4: PDF Preview Dialog
            export_pdf_preview_dialog(),
            # Phase 5: Sensitivity Analysis Dialog
            sensitivity_results_dialog(),
            # Save confirmation dialog
            save_confirmation_dialog(),
            padding="2em",
            width="100%",
            overflow_y="auto",
            height="100vh",
            on_mount=ACHState.load_analyses,
        ),
        width="100%",
        height="100vh",
    )
