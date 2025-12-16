"""
Hidden Content Detection Page

Detects steganography, metadata anomalies, and embedded content.
"""

import reflex as rx
from app.arkham.state.hidden_content_state import HiddenContentState
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


def risk_badge(score: int) -> rx.Component:
    """Badge showing risk level based on score."""
    return rx.cond(
        score >= 50,
        rx.badge("HIGH", color_scheme="red", size="2"),
        rx.cond(
            score >= 20,
            rx.badge("MEDIUM", color_scheme="orange", size="2"),
            rx.cond(
                score > 0,
                rx.badge("LOW", color_scheme="yellow", size="2"),
                rx.badge("CLEAN", color_scheme="green", size="2"),
            ),
        ),
    )


def scan_result_row(result) -> rx.Component:
    """Row displaying a scan result."""
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.text(result.filename, weight="medium", size="2"),
                rx.text(
                    f"{result.size:,} bytes",
                    size="1",
                    color="gray",
                ),
                align_items="start",
                spacing="0",
            )
        ),
        rx.table.cell(risk_badge(result.risk_score)),
        rx.table.cell(
            rx.hstack(
                rx.cond(
                    result.anomaly_count > 0,
                    rx.badge(
                        f"{result.anomaly_count} anomalies",
                        color_scheme="red",
                        variant="soft",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    result.warning_count > 0,
                    rx.badge(
                        f"{result.warning_count} warnings",
                        color_scheme="orange",
                        variant="soft",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                spacing="1",
            )
        ),
        rx.table.cell(
            rx.button(
                rx.icon("eye", size=14),
                "Details",
                size="1",
                variant="ghost",
                on_click=lambda: HiddenContentState.analyze_file(result.path),
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def anomaly_card(anomaly) -> rx.Component:
    """Card showing an anomaly or warning."""
    return rx.hstack(
        rx.icon(
            rx.match(
                anomaly.severity,
                ("High", "triangle-alert"),
                ("Medium", "circle-alert"),
                "info",
            ),
            size=16,
            color=rx.match(
                anomaly.severity,
                ("High", "var(--red-9)"),
                ("Medium", "var(--orange-9)"),
                "var(--yellow-9)",
            ),
        ),
        rx.vstack(
            rx.hstack(
                rx.text(
                    anomaly.type.replace("_", " ").title(), weight="medium", size="2"
                ),
                rx.badge(anomaly.severity, size="1", variant="outline"),
                spacing="2",
            ),
            rx.text(anomaly.description, size="1", color="gray"),
            align_items="start",
            spacing="0",
        ),
        spacing="3",
        width="100%",
        padding="2",
    )


def detail_modal() -> rx.Component:
    """Modal showing detailed analysis of a file."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.heading("File Analysis Details", size="6"),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            variant="ghost",
                            on_click=HiddenContentState.close_detail,
                        )
                    ),
                    width="100%",
                ),
                rx.cond(
                    HiddenContentState.is_analyzing,
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="3"),
                            rx.text("Analyzing file...", color="gray"),
                            spacing="2",
                        ),
                        padding="8",
                    ),
                    rx.cond(
                        HiddenContentState.has_selected,
                        rx.scroll_area(
                            rx.vstack(
                                # File info
                                rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text(
                                                HiddenContentState.selected_result.filename,
                                                weight="bold",
                                            ),
                                            rx.spacer(),
                                            risk_badge(
                                                HiddenContentState.selected_result.risk_score
                                            ),
                                            width="100%",
                                        ),
                                        rx.text(
                                            HiddenContentState.selected_result.path,
                                            size="1",
                                            color="gray",
                                        ),
                                        rx.hstack(
                                            rx.text("Size:", size="1", color="gray"),
                                            rx.text(
                                                f"{HiddenContentState.selected_result.size:,} bytes",
                                                size="1",
                                            ),
                                            rx.text(
                                                "Risk Score:", size="1", color="gray"
                                            ),
                                            rx.text(
                                                HiddenContentState.selected_result.risk_score,
                                                size="1",
                                                weight="bold",
                                            ),
                                            spacing="3",
                                        ),
                                        align_items="start",
                                        spacing="2",
                                    ),
                                    padding="4",
                                    width="100%",
                                ),
                                # Signature check
                                rx.cond(
                                    ~HiddenContentState.selected_result.signature_match,
                                    rx.callout(
                                        "File signature does not match extension!",
                                        icon="triangle-alert",
                                        color="red",
                                    ),
                                    rx.fragment(),
                                ),
                                # Appended data
                                rx.cond(
                                    HiddenContentState.selected_result.has_appended_data,
                                    rx.callout(
                                        f"File contains {HiddenContentState.selected_result.extra_bytes} bytes of appended data (possible steganography)",
                                        icon="file-warning",
                                        color="red",
                                    ),
                                    rx.fragment(),
                                ),
                                # Anomalies section
                                rx.cond(
                                    HiddenContentState.selected_result.anomalies.length()
                                    > 0,
                                    rx.vstack(
                                        rx.heading("Anomalies", size="4", color="red"),
                                        rx.foreach(
                                            HiddenContentState.selected_result.anomalies,
                                            anomaly_card,
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                # Warnings section
                                rx.cond(
                                    HiddenContentState.selected_result.warnings.length()
                                    > 0,
                                    rx.vstack(
                                        rx.heading(
                                            "Warnings", size="4", color="orange"
                                        ),
                                        rx.foreach(
                                            HiddenContentState.selected_result.warnings,
                                            anomaly_card,
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                # Clean file notice
                                rx.cond(
                                    (
                                        HiddenContentState.selected_result.anomalies.length()
                                        == 0
                                    )
                                    & (
                                        HiddenContentState.selected_result.warnings.length()
                                        == 0
                                    ),
                                    rx.callout(
                                        "No anomalies or warnings detected.",
                                        icon="circle-check",
                                        color="green",
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            type="always",
                            scrollbars="vertical",
                            style={"max-height": "60vh"},
                        ),
                        rx.text("No file selected", color="gray"),
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            max_width="700px",
        ),
        open=HiddenContentState.show_detail,
    )


def filter_buttons() -> rx.Component:
    """Filter buttons for risk levels."""
    return rx.hstack(
        rx.button(
            "All",
            variant=rx.cond(HiddenContentState.filter_risk == "all", "solid", "ghost"),
            size="1",
            on_click=lambda: HiddenContentState.set_filter("all"),
        ),
        rx.button(
            rx.icon("triangle-alert", size=12),
            "High",
            variant=rx.cond(HiddenContentState.filter_risk == "high", "solid", "ghost"),
            color_scheme="red",
            size="1",
            on_click=lambda: HiddenContentState.set_filter("high"),
        ),
        rx.button(
            rx.icon("circle-alert", size=12),
            "Medium",
            variant=rx.cond(
                HiddenContentState.filter_risk == "medium", "solid", "ghost"
            ),
            color_scheme="orange",
            size="1",
            on_click=lambda: HiddenContentState.set_filter("medium"),
        ),
        rx.button(
            "Low",
            variant=rx.cond(HiddenContentState.filter_risk == "low", "solid", "ghost"),
            color_scheme="yellow",
            size="1",
            on_click=lambda: HiddenContentState.set_filter("low"),
        ),
        rx.button(
            rx.icon("circle-check", size=12),
            "Clean",
            variant=rx.cond(
                HiddenContentState.filter_risk == "clean", "solid", "ghost"
            ),
            color_scheme="green",
            size="1",
            on_click=lambda: HiddenContentState.set_filter("clean"),
        ),
        spacing="1",
    )


def hidden_content_page() -> rx.Component:
    """Main Hidden Content Detection page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Hidden Content Detection", size="8"),
                    rx.text(
                        "Detect steganography, metadata anomalies, and embedded content.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("scan"),
                    "Scan Library",
                    on_click=HiddenContentState.run_library_scan,
                    loading=HiddenContentState.is_scanning,
                ),
                width="100%",
                align_items="end",
            ),
            # Stats cards
            rx.grid(
                stat_card(
                    "Total Scanned",
                    HiddenContentState.total_scanned,
                    "files",
                    "blue",
                ),
                stat_card(
                    "High Risk",
                    HiddenContentState.high_risk_count,
                    "triangle-alert",
                    "red",
                ),
                stat_card(
                    "Medium Risk",
                    HiddenContentState.medium_risk_count,
                    "circle-alert",
                    "orange",
                ),
                stat_card(
                    "Clean",
                    HiddenContentState.clean_count,
                    "circle-check",
                    "green",
                ),
                columns="4",
                spacing="4",
                width="100%",
            ),
            # Results section
            rx.cond(
                HiddenContentState.has_results,
                rx.vstack(
                    rx.hstack(
                        rx.heading("Scan Results", size="5"),
                        rx.spacer(),
                        filter_buttons(),
                        width="100%",
                    ),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("File"),
                                rx.table.column_header_cell("Risk"),
                                rx.table.column_header_cell("Findings"),
                                rx.table.column_header_cell(""),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                HiddenContentState.filtered_results, scan_result_row
                            )
                        ),
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                ),
                rx.cond(
                    HiddenContentState.is_scanning,
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="3"),
                            rx.text("Scanning document library...", color="gray"),
                            rx.text(
                                "Checking for steganography, metadata anomalies, and embedded content",
                                size="1",
                                color="gray",
                            ),
                            spacing="2",
                            align_items="center",
                        ),
                        padding="8",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text(
                                "Click 'Scan Library' to analyze your documents for hidden content.",
                                weight="medium",
                            ),
                            rx.text(
                                "Detection includes: file signature verification, metadata anomalies, "
                                "appended data (steganography), embedded macros, GPS data, and more.",
                                size="2",
                            ),
                            align_items="start",
                            spacing="1",
                        ),
                        icon="info",
                    ),
                ),
            ),
            detail_modal(),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
        ),
        width="100%",
        height="100vh",
    )
