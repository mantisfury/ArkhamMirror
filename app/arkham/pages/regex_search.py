import reflex as rx
from ..state.regex_state import RegexState
from ..components.layout import layout
from ..components.design_tokens import SPACING, FONT_SIZE, CARD_PADDING, CARD_GAP


def result_card(match: dict):
    """Component to display a single match result."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    match["pattern_type"],
                    color_scheme="blue",
                ),
                rx.text(match["document_title"], font_weight="bold"),
                rx.spacer(),
                rx.text(
                    match["confidence"],
                    font_size=FONT_SIZE["sm"],
                    color="gray.11",
                ),
                width="100%",
            ),
            rx.code(match["match_text"]),
            rx.text(match["context"], font_size=FONT_SIZE["sm"], color="gray.9"),
            align_items="start",
            width="100%",
        ),
        width="100%",
        margin_bottom=SPACING["sm"],
        padding=CARD_PADDING,
    )


def search_tab():
    return rx.vstack(
        rx.text("Search Documents for Patterns", font_size="lg", font_weight="bold"),
        rx.text(
            "This searches through ALL text in the database using real-time pattern matching.",
            color="gray.11",
        ),
        rx.button(
            "Run Search",
            on_click=RegexState.run_search,
            loading=RegexState.is_searching,
            width="100%",
            color_scheme="blue",
        ),
        rx.divider(),
        rx.cond(
            RegexState.search_results,
            rx.vstack(
                rx.text(
                    f"Found {RegexState.search_results.length()} matches",
                    color="green.9",
                ),
                rx.foreach(RegexState.search_results, result_card),
                width="100%",
            ),
            rx.cond(
                RegexState.is_searching,
                rx.center(rx.spinner()),
                rx.text("No results found or search not run.", color="gray.11"),
            ),
        ),
        width="100%",
        spacing=SPACING["md"],
    )


def detected_tab():
    return rx.vstack(
        rx.text(
            "Previously Detected Sensitive Data", font_size="lg", font_weight="bold"
        ),
        rx.text(
            "Patterns automatically detected during document processing.",
            color="gray.11",
        ),
        rx.hstack(
            rx.select.root(
                rx.select.trigger(placeholder="Filter by Pattern"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.foreach(
                        RegexState.pattern_options,
                        lambda opt: rx.select.item(opt, value=opt),
                    ),
                ),
                on_change=RegexState.set_detected_pattern_filter,
            ),
            rx.text("Min Strength:", color="gray.11"),
            rx.select.root(
                rx.select.trigger(),
                rx.select.content(
                    rx.select.item("0% Confidence", value="0.0"),
                    rx.select.item("10% Confidence", value="0.1"),
                    rx.select.item("25% Confidence", value="0.25"),
                    rx.select.item("50% Confidence", value="0.5"),
                    rx.select.item("75% Confidence", value="0.75"),
                    rx.select.item("90% Confidence", value="0.9"),
                ),
                default_value="0.0",
                on_change=RegexState.set_detected_min_confidence,
            ),
            align_items="center",
            spacing=SPACING["md"],
        ),
        rx.divider(),
        rx.cond(
            RegexState.detected_matches,
            rx.vstack(
                rx.text(
                    f"Showing {RegexState.detected_matches.length()} matches",
                    color="green.9",
                ),
                rx.foreach(RegexState.detected_matches, result_card),
                width="100%",
            ),
            rx.text("No detected matches found.", color="gray.11"),
        ),
        width="100%",
        spacing=SPACING["md"],
    )


def sidebar_controls():
    return rx.vstack(
        rx.heading("Search Patterns", size="4"),
        rx.text(
            "Select patterns to search:", font_size=FONT_SIZE["sm"], color="gray.11"
        ),
        rx.select.root(
            rx.select.trigger(placeholder="Select Pattern"),
            rx.select.content(
                rx.select.item("All", value="all"),
                rx.foreach(
                    RegexState.pattern_options,
                    lambda opt: rx.select.item(opt, value=opt),
                ),
            ),
            on_change=RegexState.toggle_pattern,
        ),
        rx.divider(),
        rx.heading("Custom Regex", size="4"),
        rx.input(
            placeholder=r"\b\d{3}-\d{3}-\d{4}\b",
            on_change=RegexState.set_custom_regex,
            value=RegexState.custom_regex,
        ),
        rx.divider(),
        rx.text("Strength Threshold", font_size=FONT_SIZE["sm"], color="gray.11"),
        rx.select.root(
            rx.select.trigger(),
            rx.select.content(
                rx.select.item("0% Confidence", value="0.0"),
                rx.select.item("10% Confidence", value="0.1"),
                rx.select.item("25% Confidence", value="0.25"),
                rx.select.item("50% Confidence", value="0.5"),
                rx.select.item("75% Confidence", value="0.75"),
                rx.select.item("90% Confidence", value="0.9"),
            ),
            default_value="0.5",
            on_change=RegexState.set_confidence_threshold,
        ),
        spacing=SPACING["md"],
        align_items="start",
        width="100%",
    )


def regex_search_page() -> rx.Component:
    return layout(
        rx.hstack(
            # Left sidebar (25% width)
            rx.box(
                sidebar_controls(),
                padding=SPACING["md"],
                background="var(--gray-3)",
                border_radius="md",
                width="25%",
                min_width="250px",
            ),
            # Main content (75% width)
            rx.box(
                rx.vstack(
                    rx.heading("Regex Search & Sensitive Data", size="8"),
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Search Documents", value="search"),
                            rx.tabs.trigger("Already Detected", value="detected"),
                        ),
                        rx.tabs.content(
                            search_tab(), value="search", padding_top=SPACING["md"]
                        ),
                        rx.tabs.content(
                            detected_tab(), value="detected", padding_top=SPACING["md"]
                        ),
                        default_value="search",
                        width="100%",
                    ),
                    width="100%",
                    spacing=SPACING["lg"],
                ),
                padding=SPACING["md"],
                flex="1",
            ),
            spacing=CARD_GAP,
            width="100%",
            align_items="start",
            on_mount=RegexState.on_load,
        )
    )
