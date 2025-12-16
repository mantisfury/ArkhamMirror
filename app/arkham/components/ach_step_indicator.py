"""
ACH Step Indicator Component.

Shows the 8-step ACH methodology progress with clickable steps.
"""

import reflex as rx
from ..state.ach_state import ACHState
from .design_tokens import SPACING, FONT_SIZE


# Step metadata
STEP_ICONS = {
    1: "lightbulb",  # Identify Hypotheses
    2: "file-text",  # List Evidence
    3: "grid-3x3",  # Create Matrix
    4: "bar-chart-2",  # Analyze Diagnosticity
    5: "pencil-line",  # Refine the Matrix
    6: "target",  # Draw Conclusions
    7: "shield-question",  # Sensitivity Analysis
    8: "file-output",  # Report & Milestones
}


def step_circle(step: int) -> rx.Component:
    """
    Render a single step circle in the indicator.

    States:
    - Completed: solid blue with checkmark
    - Current: solid blue with number
    - Future: outline with number
    """
    is_current = ACHState.current_step == step
    is_completed = ACHState.steps_completed.contains(step)

    return rx.tooltip(
        rx.box(
            rx.cond(
                is_completed,
                # Completed: checkmark
                rx.icon("check", size=14, color="white"),
                # Not completed: step number
                rx.text(
                    str(step),
                    font_size=FONT_SIZE["sm"],
                    font_weight="600",
                    color=rx.cond(
                        is_current,
                        "white",
                        "gray.11",
                    ),
                ),
            ),
            width="28px",
            height="28px",
            border_radius="50%",
            display="flex",
            align_items="center",
            justify_content="center",
            bg=rx.cond(
                is_completed | is_current,
                "var(--accent-9)",
                "transparent",
            ),
            border=rx.cond(
                is_completed | is_current,
                "2px solid var(--accent-9)",
                "2px solid var(--gray-7)",
            ),
            cursor="pointer",
            on_click=lambda: ACHState.go_to_step(step),
            _hover={
                "border_color": "var(--accent-9)",
                "transform": "scale(1.1)",
            },
            transition="all 0.2s ease",
        ),
        content=ACHState.step_names[step],
    )


def step_connector(completed: bool) -> rx.Component:
    """Connector line between steps."""
    return rx.box(
        width="24px",
        height="2px",
        bg=rx.cond(
            completed,
            "var(--accent-9)",
            "var(--gray-6)",
        ),
        margin_x="2px",
    )


def ach_step_indicator() -> rx.Component:
    """
    Horizontal step indicator showing all 8 ACH steps.

    Features:
    - Clickable steps for navigation
    - Visual state for completed/current/future
    - Tooltips with step names
    - Responsive connector lines
    """
    return rx.card(
        rx.vstack(
            # Header
            rx.hstack(
                rx.icon("compass", size=18, color="var(--accent-9)"),
                rx.text(
                    "ACH Methodology",
                    font_weight="600",
                    font_size=FONT_SIZE["sm"],
                ),
                rx.spacer(),
                rx.text(
                    f"Step {ACHState.current_step} of 8",
                    font_size=FONT_SIZE["xs"],
                    color="gray.11",
                ),
                width="100%",
                align="center",
            ),
            # Step indicators
            rx.hstack(
                step_circle(1),
                step_connector(ACHState.steps_completed.contains(1)),
                step_circle(2),
                step_connector(ACHState.steps_completed.contains(2)),
                step_circle(3),
                step_connector(ACHState.steps_completed.contains(3)),
                step_circle(4),
                step_connector(ACHState.steps_completed.contains(4)),
                step_circle(5),
                step_connector(ACHState.steps_completed.contains(5)),
                step_circle(6),
                step_connector(ACHState.steps_completed.contains(6)),
                step_circle(7),
                step_connector(ACHState.steps_completed.contains(7)),
                step_circle(8),
                justify="center",
                align="center",
                width="100%",
            ),
            # Current step name
            rx.hstack(
                rx.icon(
                    tag=STEP_ICONS.get(ACHState.current_step, "circle"),
                    size=16,
                    color="var(--accent-9)",
                ),
                rx.text(
                    ACHState.step_names[ACHState.current_step],
                    font_weight="500",
                    font_size=FONT_SIZE["md"],
                ),
                rx.spacer(),
                # Navigation buttons
                rx.button(
                    rx.icon("chevron-left", size=14),
                    on_click=ACHState.prev_step,
                    variant="ghost",
                    size="1",
                    disabled=ACHState.current_step <= 1,
                ),
                rx.button(
                    rx.icon("chevron-right", size=14),
                    on_click=ACHState.next_step,
                    variant="ghost",
                    size="1",
                    disabled=ACHState.current_step >= 8,
                ),
                width="100%",
                align="center",
            ),
            spacing=SPACING["sm"],
            width="100%",
        ),
        padding=SPACING["md"],
        width="100%",
    )


def ach_step_indicator_compact() -> rx.Component:
    """
    Compact version of step indicator for smaller spaces.
    Shows only current step with prev/next navigation.
    """
    return rx.hstack(
        rx.button(
            rx.icon("chevron-left", size=14),
            on_click=ACHState.prev_step,
            variant="ghost",
            size="1",
            disabled=ACHState.current_step <= 1,
        ),
        rx.hstack(
            rx.icon(
                tag=STEP_ICONS.get(ACHState.current_step, "circle"),
                size=16,
                color="var(--accent-9)",
            ),
            rx.text(
                f"Step {ACHState.current_step}: ",
                font_size=FONT_SIZE["sm"],
                color="gray.11",
            ),
            rx.text(
                ACHState.step_names[ACHState.current_step],
                font_size=FONT_SIZE["sm"],
                font_weight="500",
            ),
            spacing="1",
            align="center",
        ),
        rx.button(
            rx.icon("chevron-right", size=14),
            on_click=ACHState.next_step,
            variant="ghost",
            size="1",
            disabled=ACHState.current_step >= 8,
        ),
        spacing="2",
        align="center",
    )
