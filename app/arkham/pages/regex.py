import reflex as rx
from ..components.layout import layout
from ..state.regex_state import RegexState


def confidence_badge(confidence: float) -> rx.Component:
    """Return a colored badge based on confidence score."""
    return rx.cond(
        confidence > 0.8,
        rx.badge("High", color_scheme="green"),
        rx.cond(
            confidence > 0.5,
            rx.badge("Medium", color_scheme="yellow"),
            rx.badge("Low", color_scheme="red"),
        ),
    )


def pattern_selector() -> rx.Component:
    """Pattern selection sidebar."""
    return rx.card(
        rx.vstack(
            rx.heading("Search Patterns", size="4", margin_bottom="2"),
            # Built-in patterns with select all/clear buttons
            rx.hstack(
                rx.text("Built-in Patterns", weight="bold", size="2"),
                rx.spacer(),
                rx.hstack(
                    rx.button(
                        "All",
                        on_click=RegexState.select_all_patterns,
                        variant="ghost",
                        size="1",
                    ),
                    rx.button(
                        "Clear",
                        on_click=RegexState.clear_patterns,
                        variant="ghost",
                        size="1",
                    ),
                    spacing="1",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                RegexState.selected_patterns_display,
                size="1",
                color="gray",
            ),
            rx.vstack(
                rx.foreach(
                    RegexState.available_patterns.keys(),
                    lambda pattern: rx.checkbox(
                        RegexState.available_patterns[pattern],
                        checked=RegexState.selected_patterns.contains(pattern),
                        on_change=lambda _: RegexState.toggle_pattern(pattern),
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            rx.divider(margin_y="3"),
            # Custom regex (placeholder for future)
            rx.text("Custom Regex", weight="bold", size="2"),
            rx.input(
                placeholder=r"\b\d{3}-\d{3}-\d{4}\b",
                value=RegexState.custom_regex,
                on_change=RegexState.set_custom_regex,
                size="2",
            ),
            rx.input(
                placeholder="Pattern name",
                value=RegexState.custom_pattern_name,
                on_change=RegexState.set_custom_pattern_name,
                size="2",
            ),
            rx.divider(margin_y="3"),
            # Strength threshold
            rx.text(
                f"Min Strength: {RegexState.confidence_threshold:.1f}",
                weight="bold",
                size="2",
            ),
            rx.slider(
                default_value=0.5,
                min=0,
                max=1,
                step=0.1,
                on_change=RegexState.set_confidence_threshold,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def search_tab() -> rx.Component:
    """Search documents tab."""
    return rx.vstack(
        rx.heading("Search Documents for Patterns", size="5", margin_bottom="2"),
        rx.text(
            "This searches through ALL text in the database using real-time pattern matching",
            color="gray",
            margin_bottom="4",
        ),
        rx.button(
            rx.icon(tag="search", size=16),
            "Run Search",
            on_click=RegexState.run_search,
            disabled=RegexState.selected_patterns.length() == 0,
            loading=RegexState.is_searching,
            size="3",
        ),
        # Results
        rx.cond(
            RegexState.is_searching,
            rx.spinner(size="3"),
            rx.cond(
                RegexState.search_results.length() > 0,
                rx.vstack(
                    rx.text(
                        f"Found {RegexState.search_results.length()} matches",
                        size="3",
                        weight="bold",
                        margin_top="4",
                    ),
                    # Group results by pattern type
                    rx.foreach(
                        # Get unique pattern types
                        RegexState.search_results,
                        lambda result: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    confidence_badge(result["confidence"]),
                                    rx.text(
                                        result["document"],
                                        weight="bold",
                                        size="2",
                                    ),
                                    rx.code(result["match_text"]),
                                    rx.text(
                                        f"(Strength: {result['confidence']:.2f})",
                                        size="1",
                                        color="gray",
                                    ),
                                    spacing="2",
                                    align="center",
                                ),
                                rx.text(
                                    result["context"],
                                    size="1",
                                    color="gray",
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            margin_y="2",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.box(),  # Empty when no results
            ),
        ),
        spacing="4",
        width="100%",
    )


def detected_tab() -> rx.Component:
    """Previously detected sensitive data tab."""
    return rx.vstack(
        rx.heading("Previously Detected Sensitive Data", size="5", margin_bottom="2"),
        rx.text(
            "Patterns automatically detected during document processing",
            color="gray",
            margin_bottom="4",
        ),
        # Statistics
        rx.cond(
            RegexState.is_loading_detected,
            rx.spinner(size="3"),
            rx.cond(
                RegexState.detected_matches.length() > 0,
                rx.vstack(
                    # Stats row
                    rx.hstack(
                        rx.card(
                            rx.vstack(
                                rx.text("Total Matches", size="1", color="gray"),
                                rx.heading(
                                    RegexState.detected_matches.length(), size="6"
                                ),
                                spacing="1",
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Documents with Data", size="1", color="gray"),
                                rx.heading(
                                    RegexState.unique_doc_count,
                                    size="6",
                                ),
                                spacing="1",
                            )
                        ),
                        rx.card(
                            rx.vstack(
                                rx.text("Pattern Types", size="1", color="gray"),
                                rx.heading(
                                    RegexState.detected_stats.length(), size="6"
                                ),
                                spacing="1",
                            )
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.divider(margin_y="4"),
                    # Filters
                    rx.hstack(
                        rx.vstack(
                            rx.text("Filter by pattern type:", size="2"),
                            # TODO: Multi-select for pattern types
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text(
                                f"Min strength: {RegexState.conf_filter_detected:.1f}",
                                size="2",
                            ),
                            rx.slider(
                                default_value=0.0,
                                min=0,
                                max=1,
                                step=0.1,
                                on_change=RegexState.set_conf_filter_detected,
                                width="200px",
                            ),
                            spacing="1",
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    rx.divider(margin_y="4"),
                    # Results grouped by document
                    rx.foreach(
                        RegexState.detected_matches,
                        lambda match: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    confidence_badge(match["confidence"]),
                                    rx.text(match["document"], weight="bold", size="2"),
                                    rx.badge(
                                        match["pattern_type"].upper().replace("_", " ")
                                    ),
                                    rx.code(match["match_text"]),
                                    rx.text(
                                        f"(Strength: {match['confidence']:.2f})",
                                        size="1",
                                        color="gray",
                                    ),
                                    spacing="2",
                                    align="center",
                                ),
                                rx.text(match["context"], size="1", color="gray"),
                                spacing="2",
                                width="100%",
                            ),
                            margin_y="2",
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                rx.text(
                    "No sensitive data has been detected yet. Process documents to enable automatic detection.",
                    color="gray",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


def help_section() -> rx.Component:
    """Help and pattern information section."""
    return rx.accordion.root(
        rx.accordion.item(
            header=rx.hstack(
                rx.icon(tag="info", size=16),
                rx.text("Pattern Information", weight="bold"),
                spacing="2",
            ),
            content=rx.vstack(
                rx.heading("Supported Patterns", size="4", margin_bottom="2"),
                rx.vstack(
                    rx.text("Financial:", weight="bold", size="2"),
                    rx.text(
                        "• SSN: Social Security Numbers (US format)",
                        size="1",
                        color="gray",
                    ),
                    rx.text(
                        "• Credit Card: Major credit card numbers with Luhn validation",
                        size="1",
                        color="gray",
                    ),
                    rx.text(
                        "• IBAN: International Bank Account Numbers",
                        size="1",
                        color="gray",
                    ),
                    rx.text(
                        "• Bitcoin: Cryptocurrency addresses", size="1", color="gray"
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Contact Information:", weight="bold", size="2"),
                    rx.text("• Email: Email addresses", size="1", color="gray"),
                    rx.text(
                        "• Phone: US and international phone numbers",
                        size="1",
                        color="gray",
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Technical:", weight="bold", size="2"),
                    rx.text("• IP Address: IPv4 addresses", size="1", color="gray"),
                    rx.text(
                        "• API Key: Generic API keys (32+ characters)",
                        size="1",
                        color="gray",
                    ),
                    rx.text(
                        "• AWS Access Key: AWS access key IDs", size="1", color="gray"
                    ),
                    rx.text(
                        "• GitHub Token: GitHub personal access tokens",
                        size="1",
                        color="gray",
                    ),
                    spacing="1",
                ),
                rx.divider(margin_y="3"),
                rx.heading("Strength Scores", size="4", margin_bottom="2"),
                rx.vstack(
                    rx.hstack(
                        rx.badge("High", color_scheme="green"),
                        rx.text(
                            "(0.8-1.0): Pattern passed validation (e.g., Luhn algorithm)",
                            size="1",
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.badge("Medium", color_scheme="yellow"),
                        rx.text(
                            "(0.5-0.8): Pattern matched with reasonable entropy",
                            size="1",
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.badge("Low", color_scheme="red"),
                        rx.text(
                            "(0.0-0.5): Basic pattern match, may need verification",
                            size="1",
                        ),
                        spacing="2",
                    ),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        collapsible=True,
        width="100%",
        margin_top="4",
    )


def regex_page() -> rx.Component:
    """Main regex search page."""
    return layout(
        rx.vstack(
            rx.heading("Regex Search & Sensitive Data Detection", size="8"),
            rx.text("Search for sensitive patterns across all documents", color="gray"),
            rx.divider(margin_y="4"),
            rx.hstack(
                # Left sidebar - Pattern selection
                rx.box(
                    pattern_selector(),
                    width="300px",
                    flex_shrink="0",
                ),
                # Right content - Tabs
                rx.vstack(
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Search Documents", value="search"),
                            rx.tabs.trigger("Already Detected", value="detected"),
                        ),
                        rx.tabs.content(search_tab(), value="search"),
                        rx.tabs.content(detected_tab(), value="detected"),
                        default_value="search",
                        on_change=RegexState.set_active_tab,
                        width="100%",
                    ),
                    help_section(),
                    spacing="4",
                    width="100%",
                    flex="1",
                ),
                spacing="6",
                width="100%",
                align="start",
            ),
            spacing="4",
            width="100%",
        ),
        on_mount=RegexState.load_patterns,
    )
