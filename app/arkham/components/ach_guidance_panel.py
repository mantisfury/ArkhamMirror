"""
ACH Guidance Panel Component.

Provides contextual guidance for each step of Heuer's 8-step ACH methodology.
"""

import reflex as rx
from ..state.ach_state import ACHState
from .design_tokens import SPACING, FONT_SIZE


# Guidance content for each step
STEP_GUIDANCE = {
    1: {
        "title": "STEP 1: IDENTIFY HYPOTHESES",
        "icon": "lightbulb",
        "color": "blue",
        "sections": [
            {
                "heading": "Best Practices",
                "items": [
                    "List ALL plausible explanations, not just likely ones",
                    "Include a 'null hypothesis' - what if nothing unusual happened?",
                    "Consider adversarial perspectives: What would a skeptic argue?",
                    "If working with a team, brainstorm together before individual analysis",
                ],
            },
            {
                "heading": "Tip",
                "text": "You can always add more hypotheses later if you discover alternatives you hadn't considered.",
            },
        ],
    },
    2: {
        "title": "STEP 2: LIST EVIDENCE",
        "icon": "file-text",
        "color": "green",
        "sections": [
            {
                "heading": "What counts as evidence",
                "items": [
                    "Facts you can verify",
                    "Documents and records",
                    "Witness statements and testimony",
                    "Physical observations",
                ],
            },
            {
                "heading": "Also include",
                "items": [
                    "Key assumptions you're making",
                    "Logical arguments or inferences",
                    "Absence of expected evidence (significant gaps)",
                ],
            },
            {
                "heading": "Reliability Ratings",
                "items": [
                    "HIGH: Verified, multiple sources, no reason to doubt",
                    "MEDIUM: Single source, plausible, unverified",
                    "LOW: Uncertain source, possible deception, hearsay",
                ],
            },
        ],
    },
    3: {
        "title": "STEP 3: RATE THE MATRIX",
        "icon": "grid-3x3",
        "color": "purple",
        "sections": [
            {
                "heading": "Key Question",
                "text": "For each cell, ask: 'If this hypothesis is true, how likely is it that I would see this evidence?'",
            },
            {
                "heading": "Rating Scale",
                "items": [
                    "CC (Very Consistent) - Evidence strongly supports",
                    "C (Consistent) - Evidence somewhat supports",
                    "N (Neutral) - Evidence neither helps nor hurts",
                    "I (Inconsistent) - Evidence somewhat contradicts",
                    "II (Very Inconsistent) - Evidence strongly contradicts",
                ],
            },
            {
                "heading": "Key Insight",
                "text": "Focus on INCONSISTENCIES. The winning hypothesis isn't the one with most support - it's the one with LEAST contradiction.",
            },
        ],
    },
    4: {
        "title": "STEP 4: ANALYZE DIAGNOSTICITY",
        "icon": "bar-chart-2",
        "color": "amber",
        "sections": [
            {
                "heading": "What is Diagnosticity?",
                "text": "'Diagnostic' evidence helps you distinguish between hypotheses.",
            },
            {
                "heading": "HIGH DIAGNOSTIC VALUE (helpful)",
                "items": [
                    "Evidence rated differently across hypotheses",
                    "Example: 'CC' for H1, 'II' for H2 - this discriminates!",
                ],
            },
            {
                "heading": "LOW DIAGNOSTIC VALUE (less helpful)",
                "items": [
                    "Evidence rated the same for all hypotheses",
                    "Example: 'N' for H1, H2, H3, H4 - doesn't help choose",
                ],
            },
            {
                "heading": "Visual Indicators",
                "items": [
                    "GOLD highlighting = high diagnostic value",
                    "GRAY highlighting = low diagnostic value",
                    "Consider removing non-diagnostic evidence to simplify",
                ],
            },
        ],
    },
    5: {
        "title": "STEP 5: REFINE THE MATRIX",
        "icon": "pencil-line",
        "color": "cyan",
        "sections": [
            {
                "heading": "1. Review Non-Diagnostic Evidence",
                "items": [
                    "Look at gray-highlighted rows",
                    "Does this evidence actually help distinguish?",
                    "Should I remove it to simplify the analysis?",
                ],
            },
            {
                "heading": "2. Reconsider Hypotheses",
                "items": [
                    "Are any hypotheses essentially the same? Merge them.",
                    "Did you think of new alternatives? Add them.",
                    "Is one hypothesis clearly wrong? Consider removing.",
                ],
            },
            {
                "heading": "3. Check for Gaps",
                "items": [
                    "What evidence are you missing?",
                    "What would definitively prove/disprove a hypothesis?",
                    "Can you obtain that evidence?",
                ],
            },
            {
                "heading": "Note",
                "text": "This step is ITERATIVE. You may return here multiple times.",
            },
        ],
    },
    6: {
        "title": "STEP 6: DRAW TENTATIVE CONCLUSIONS",
        "icon": "target",
        "color": "red",
        "sections": [
            {
                "heading": "Reading the Scores",
                "items": [
                    "Lower score = fewer inconsistencies = more likely true",
                    "The hypothesis with the LOWEST score is the best fit",
                ],
            },
            {
                "heading": "Important Caveats",
                "items": [
                    "Scores are NOT probabilities",
                    "A low score doesn't mean 'definitely true'",
                    "A high score doesn't mean 'definitely false'",
                    "Scores depend on evidence quality and rating accuracy",
                ],
            },
            {
                "heading": "If Scores Are Close",
                "items": [
                    "You need more evidence that discriminates between them",
                    "Reconsider your rating accuracy",
                    "Accept that you may not have a clear answer yet",
                ],
            },
            {
                "heading": "Visual Guide",
                "text": "The bar chart shows relative scores. Green = low score (good). Red = high score (problematic).",
            },
        ],
    },
    7: {
        "title": "STEP 7: SENSITIVITY ANALYSIS",
        "icon": "shield-question",
        "color": "orange",
        "sections": [
            {
                "heading": "Test the Robustness of Your Conclusion",
                "text": "Before finalizing, ask yourself these critical questions:",
            },
            {
                "heading": "1. What if my most important evidence is WRONG?",
                "items": [
                    "Identify the 2-3 pieces of evidence that most influenced your conclusion",
                    "For each: What if it's inaccurate, deceptive, or misinterpreted?",
                    "Would your conclusion change?",
                ],
            },
            {
                "heading": "2. What assumptions am I making?",
                "items": [
                    "List assumptions underlying your ratings",
                    "Which are well-supported? Which are guesses?",
                    "What if a key assumption is wrong?",
                ],
            },
            {
                "heading": "3. Is any evidence from an unreliable source?",
                "items": [
                    "Review the reliability ratings you assigned",
                    "Be especially skeptical of LOW reliability evidence that heavily influenced your conclusion",
                ],
            },
            {
                "heading": "Record Your Notes",
                "text": "Use the Sensitivity Notes field to document your key vulnerabilities and what would change your conclusion.",
            },
        ],
    },
    8: {
        "title": "STEP 8: REPORT & SET MILESTONES",
        "icon": "file-output",
        "color": "violet",
        "sections": [
            {
                "heading": "Reporting Your Conclusions",
                "items": [
                    "Export your analysis to share with stakeholders",
                    "The report includes your focus question, all hypotheses with rankings, full evidence matrix, consistency warnings, and sensitivity notes",
                ],
            },
            {
                "heading": "Setting Milestones (Critical)",
                "text": "For EACH hypothesis, answer: 'If this hypothesis is true, what would we expect to see in the future?'",
            },
            {
                "heading": "Examples",
                "items": [
                    "H1 (Embezzlement): 'Expect to find hidden accounts'",
                    "H2 (Incompetence): 'Expect similar errors in other depts'",
                    "H3 (Deliberate fraud): 'Expect more whistleblowers'",
                ],
            },
            {
                "heading": "Why Milestones Matter",
                "items": [
                    "Validate your conclusion over time",
                    "Know when to revisit and update your analysis",
                    "Demonstrate the scientific rigor of your process",
                ],
            },
        ],
    },
}


def guidance_section(section: dict) -> rx.Component:
    """Render a single guidance section."""
    if "items" in section:
        return rx.vstack(
            rx.text(
                section["heading"],
                font_weight="600",
                font_size=FONT_SIZE["sm"],
                color="gray.12",
            ),
            rx.vstack(
                *[
                    rx.hstack(
                        rx.text("-", color="gray.9", width="16px"),
                        rx.text(item, font_size=FONT_SIZE["sm"], color="gray.11"),
                        spacing="1",
                        align="start",
                        width="100%",
                    )
                    for item in section["items"]
                ],
                spacing="1",
                width="100%",
                padding_left=SPACING["xs"],
            ),
            spacing="1",
            width="100%",
            align="start",
        )
    elif "text" in section:
        return rx.vstack(
            rx.text(
                section["heading"],
                font_weight="600",
                font_size=FONT_SIZE["sm"],
                color="gray.12",
            ),
            rx.text(
                section["text"],
                font_size=FONT_SIZE["sm"],
                color="gray.11",
            ),
            spacing="1",
            width="100%",
            align="start",
        )
    return rx.fragment()


def ach_guidance_panel(step: int) -> rx.Component:
    """
    Render guidance panel for a specific step.

    Args:
        step: Step number (1-8)
    """
    guidance = STEP_GUIDANCE.get(step, {})

    if not guidance:
        return rx.fragment()

    return rx.card(
        rx.vstack(
            # Header with collapse toggle
            rx.hstack(
                rx.icon(
                    tag=guidance.get("icon", "info"),
                    size=18,
                    color=f"var(--{guidance.get('color', 'blue')}-9)",
                ),
                rx.text(
                    guidance.get("title", ""),
                    font_weight="600",
                    font_size=FONT_SIZE["md"],
                ),
                rx.spacer(),
                rx.button(
                    rx.cond(
                        ACHState.show_step_guidance,
                        rx.icon("chevron-up", size=14),
                        rx.icon("chevron-down", size=14),
                    ),
                    on_click=ACHState.toggle_step_guidance,
                    variant="ghost",
                    size="1",
                ),
                width="100%",
                align="center",
            ),
            # Collapsible content
            rx.cond(
                ACHState.show_step_guidance,
                rx.vstack(
                    rx.divider(margin_y=SPACING["xs"]),
                    *[guidance_section(s) for s in guidance.get("sections", [])],
                    spacing=SPACING["sm"],
                    width="100%",
                    align="start",
                ),
                rx.fragment(),
            ),
            spacing=SPACING["xs"],
            width="100%",
        ),
        padding=SPACING["md"],
        bg=f"var(--{guidance.get('color', 'blue')}-2)",
        border=f"1px solid var(--{guidance.get('color', 'blue')}-6)",
        width="100%",
    )


def ach_guidance_for_current_step() -> rx.Component:
    """
    Dynamic guidance panel that shows content for the current step.
    Uses rx.match to switch content based on current_step.
    """
    return rx.match(
        ACHState.current_step,
        (1, ach_guidance_panel(1)),
        (2, ach_guidance_panel(2)),
        (3, ach_guidance_panel(3)),
        (4, ach_guidance_panel(4)),
        (5, ach_guidance_panel(5)),
        (6, ach_guidance_panel(6)),
        (7, ach_guidance_panel(7)),
        (8, ach_guidance_panel(8)),
        ach_guidance_panel(1),  # Default
    )
