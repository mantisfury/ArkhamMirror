import reflex as rx
from ..components.layout import layout
from ..state.timeline_state import TimelineState
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING


def timeline_page() -> rx.Component:
    """Timeline analysis page."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.heading("Timeline Analysis", size="8"),
                rx.spacer(),
                # Load or Refresh button based on data state
                rx.cond(
                    TimelineState.has_data,
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Refresh",
                        on_click=TimelineState.refresh_timeline,
                        loading=TimelineState.is_loading,
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Load Timeline",
                        on_click=TimelineState.load_all,
                        loading=TimelineState.is_loading,
                        color_scheme="blue",
                    ),
                ),
                width="100%",
                align="center",
            ),
            # Controls
            rx.card(
                rx.hstack(
                    rx.vstack(
                        rx.text("Start Date", size="1", weight="bold", color="gray.11"),
                        rx.input(
                            type_="date",
                            value=TimelineState.date_range_start,
                            on_change=TimelineState.set_date_range_start,
                        ),
                        spacing=SPACING["xs"],
                    ),
                    rx.vstack(
                        rx.text("End Date", size="1", weight="bold", color="gray.11"),
                        rx.input(
                            type_="date",
                            value=TimelineState.date_range_end,
                            on_change=TimelineState.set_date_range_end,
                        ),
                        spacing=SPACING["xs"],
                    ),
                    rx.spacer(),
                    rx.cond(
                        TimelineState.events.length() > 0,
                        rx.button(
                            rx.icon(tag="download", size=16),
                            "Export Timeline",
                            on_click=TimelineState.export_timeline,
                            size="2",
                            variant="soft",
                            color_scheme="green",
                        ),
                        rx.fragment(),
                    ),
                    spacing=SPACING["md"],
                    align="center",
                    width="100%",
                ),
                width="100%",
                padding=CARD_PADDING,
            ),
            # Activity Heatmap Section
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Activity Patterns", size="5"),
                        rx.spacer(),
                        rx.select.root(
                            rx.select.trigger(),
                            rx.select.content(
                                rx.select.item("Day & Hour", value="day_hour"),
                                rx.select.item("Weekly", value="weekly"),
                                rx.select.item("Monthly", value="monthly"),
                            ),
                            value=TimelineState.heatmap_type,
                            on_change=TimelineState.set_heatmap_type,
                            size="2",
                        ),
                        width="100%",
                        align="center",
                    ),
                    # Heatmap stats summary
                    rx.cond(
                        TimelineState.heatmap_stats,
                        rx.hstack(
                            rx.badge(
                                f"Total Events: {TimelineState.heatmap_stats.get('total_events', 0)}",
                                color_scheme="blue",
                            ),
                            rx.badge(
                                f"Busiest Day: {TimelineState.heatmap_stats.get('busiest_day_of_week', 'N/A')}",
                                color_scheme="purple",
                            ),
                            rx.badge(
                                f"Peak Hour: {TimelineState.heatmap_stats.get('busiest_hour', 'N/A')}:00",
                                color_scheme="green",
                            ),
                            spacing=SPACING["sm"],
                        ),
                        rx.fragment(),
                    ),
                    # Heatmap visualization
                    rx.cond(
                        TimelineState.is_loading_heatmap,
                        rx.center(
                            rx.spinner(size="3"),
                            padding=SPACING["xl"],
                        ),
                        rx.cond(
                            TimelineState.heatmap_figure,
                            rx.plotly(data=TimelineState.heatmap_figure),
                            rx.center(
                                rx.text(
                                    "No activity data available",
                                    color="gray.10",
                                ),
                                padding=SPACING["xl"],
                            ),
                        ),
                    ),
                    spacing=SPACING["md"],
                    width="100%",
                ),
                width="100%",
                padding=CARD_PADDING,
                margin_top=SPACING["md"],
            ),
            # Events List (Placeholder for visual timeline)
            rx.heading("Events", size="5", margin_top=SPACING["md"]),
            rx.cond(
                TimelineState.is_loading,
                rx.spinner(),
                rx.vstack(
                    rx.foreach(
                        TimelineState.events,
                        lambda event: rx.card(
                            rx.hstack(
                                rx.badge(event["date"], color_scheme="purple"),
                                rx.text(event["description"], font_weight="medium"),
                                rx.spacer(),
                                rx.badge(event["type"], variant="outline"),
                                width="100%",
                                align="center",
                            ),
                            width="100%",
                            padding=SPACING["sm"],
                        ),
                    ),
                    spacing=SPACING["sm"],
                    width="100%",
                ),
            ),
            # Gaps panel
            rx.cond(
                TimelineState.gaps,
                rx.card(
                    rx.heading("Suspicious Gaps", size="4", color="red.9"),
                    rx.foreach(
                        TimelineState.gaps,
                        lambda g: rx.text(
                            f"Gap: {g['start']} - {g['end']} ({g['duration']} days)",
                            color="gray.11",
                            font_size=FONT_SIZE["sm"],
                        ),
                    ),
                    padding=CARD_PADDING,
                ),
                rx.fragment(),
            ),
            spacing=SPACING["md"],
            width="100%",
            # Removed on_mount - user must click Load button
        )
    )
