"""
Metadata Forensics Dashboard Page

Displays comprehensive metadata analysis including software distribution,
temporal patterns, author analysis, and document authenticity verification.
"""

import reflex as rx
from app.arkham.state.metadata_forensics_state import MetadataForensicsState
from app.arkham.components.layout import layout


def stat_card(title: str, value: str, icon: str, color: str = "blue") -> rx.Component:
    """Render a summary statistic card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=24, color=color),
                rx.text(title, size="3", weight="bold", color="gray"),
                spacing="2",
                align="center",
            ),
            rx.text(value, size="7", weight="bold"),
            spacing="2",
            align="start",
        ),
        size="2",
    )


def overview_tab() -> rx.Component:
    """Overview tab with summary statistics."""
    return rx.vstack(
        # Top-level stats
        rx.heading("Metadata Overview", size="6", margin_bottom="4"),
        rx.grid(
            stat_card(
                "Total Documents",
                MetadataForensicsState.total_documents,
                "file-text",
                "blue",
            ),
            stat_card(
                "With Metadata",
                MetadataForensicsState.with_metadata,
                "circle-check",
                "green",
            ),
            stat_card(
                "Encrypted", MetadataForensicsState.encrypted_count, "lock", "orange"
            ),
            stat_card(
                "Backdated Docs",
                MetadataForensicsState.backdated_count,
                "triangle-alert",
                "red",
            ),
            columns="4",
            spacing="4",
            margin_bottom="6",
        ),
        # Missing metadata section
        rx.heading("Missing Metadata", size="5", margin_bottom="3"),
        rx.card(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Field"),
                        rx.table.column_header_cell("Missing Count"),
                        rx.table.column_header_cell("Percentage"),
                    )
                ),
                rx.table.body(
                    rx.table.row(
                        rx.table.cell("Creation Date"),
                        rx.table.cell(MetadataForensicsState.missing_creation_date),
                        rx.table.cell(
                            rx.cond(
                                MetadataForensicsState.total_documents > 0,
                                f"{(MetadataForensicsState.missing_creation_date / MetadataForensicsState.total_documents * 100):.1f}%",
                                "0%",
                            )
                        ),
                    ),
                    rx.table.row(
                        rx.table.cell("Modification Date"),
                        rx.table.cell(MetadataForensicsState.missing_modification_date),
                        rx.table.cell(
                            rx.cond(
                                MetadataForensicsState.total_documents > 0,
                                f"{(MetadataForensicsState.missing_modification_date / MetadataForensicsState.total_documents * 100):.1f}%",
                                "0%",
                            )
                        ),
                    ),
                    rx.table.row(
                        rx.table.cell("Author"),
                        rx.table.cell(MetadataForensicsState.missing_author),
                        rx.table.cell(
                            rx.cond(
                                MetadataForensicsState.total_documents > 0,
                                f"{(MetadataForensicsState.missing_author / MetadataForensicsState.total_documents * 100):.1f}%",
                                "0%",
                            )
                        ),
                    ),
                    rx.table.row(
                        rx.table.cell("Producer"),
                        rx.table.cell(MetadataForensicsState.missing_producer),
                        rx.table.cell(
                            rx.cond(
                                MetadataForensicsState.total_documents > 0,
                                f"{(MetadataForensicsState.missing_producer / MetadataForensicsState.total_documents * 100):.1f}%",
                                "0%",
                            )
                        ),
                    ),
                    rx.table.row(
                        rx.table.cell("Creator"),
                        rx.table.cell(MetadataForensicsState.missing_creator),
                        rx.table.cell(
                            rx.cond(
                                MetadataForensicsState.total_documents > 0,
                                f"{(MetadataForensicsState.missing_creator / MetadataForensicsState.total_documents * 100):.1f}%",
                                "0%",
                            )
                        ),
                    ),
                ),
            ),
            size="2",
            margin_bottom="6",
        ),
        # Date anomalies section
        rx.heading("Date Anomalies", size="5", margin_bottom="3"),
        rx.grid(
            stat_card(
                "Backdated",
                MetadataForensicsState.backdated_count,
                "circle-alert",
                "red",
            ),
            stat_card(
                "Future Dates",
                MetadataForensicsState.future_dates_count,
                "calendar",
                "orange",
            ),
            stat_card(
                "Very Old", MetadataForensicsState.very_old_count, "clock", "yellow"
            ),
            stat_card(
                "Same Create/Modify",
                MetadataForensicsState.same_create_modify_count,
                "info",
                "blue",
            ),
            columns="4",
            spacing="4",
        ),
        spacing="4",
        width="100%",
    )


def software_tab() -> rx.Component:
    """Software distribution tab."""
    return rx.vstack(
        rx.heading("Software Distribution", size="6", margin_bottom="4"),
        # PDF Producers
        rx.heading("PDF Producers", size="5", margin_bottom="3"),
        rx.card(
            rx.cond(
                MetadataForensicsState.producers_list,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Producer"),
                            rx.table.column_header_cell("Count"),
                            rx.table.column_header_cell("Percentage"),
                            rx.table.column_header_cell("Risk"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            MetadataForensicsState.producers_list,
                            lambda item: rx.table.row(
                                rx.table.cell(item.name),
                                rx.table.cell(item.count),
                                rx.table.cell(f"{item.percentage:.1f}%"),
                                rx.table.cell(
                                    rx.badge(
                                        item.suspicion,
                                        color_scheme=rx.cond(
                                            item.suspicion == "HIGH",
                                            "red",
                                            rx.cond(
                                                item.suspicion == "MEDIUM",
                                                "yellow",
                                                "green",
                                            ),
                                        ),
                                    )
                                ),
                            ),
                        )
                    ),
                ),
                rx.text("No producer data available", color="gray"),
            ),
            size="2",
            margin_bottom="6",
        ),
        # PDF Creators
        rx.heading("PDF Creators", size="5", margin_bottom="3"),
        rx.card(
            rx.cond(
                MetadataForensicsState.creators_list,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Creator"),
                            rx.table.column_header_cell("Count"),
                            rx.table.column_header_cell("Percentage"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            MetadataForensicsState.creators_list,
                            lambda item: rx.table.row(
                                rx.table.cell(item.name),
                                rx.table.cell(item.count),
                                rx.table.cell(f"{item.percentage:.1f}%"),
                            ),
                        )
                    ),
                ),
                rx.text("No creator data available", color="gray"),
            ),
            size="2",
        ),
        spacing="4",
        width="100%",
    )


def timeline_tab() -> rx.Component:
    """Temporal distribution tab."""
    return rx.vstack(
        rx.heading("Temporal Distribution", size="6", margin_bottom="4"),
        # By year
        rx.heading("Documents by Year", size="5", margin_bottom="3"),
        rx.card(
            rx.cond(
                MetadataForensicsState.years_list,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Year"),
                            rx.table.column_header_cell("Document Count"),
                            rx.table.column_header_cell("Percentage"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            MetadataForensicsState.years_list,
                            lambda item: rx.table.row(
                                rx.table.cell(item.get("year", "Unknown")),
                                rx.table.cell(item.count),
                                rx.table.cell(f"{item.percentage:.1f}%"),
                            ),
                        )
                    ),
                ),
                rx.text("No temporal data available", color="gray"),
            ),
            size="2",
            margin_bottom="6",
        ),
        # Recent activity
        rx.heading("Recent Activity", size="5", margin_bottom="3"),
        rx.card(
            rx.cond(
                MetadataForensicsState.recent_months_list,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Month"),
                            rx.table.column_header_cell("Documents Created"),
                            rx.table.column_header_cell("Documents Modified"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            MetadataForensicsState.recent_months_list,
                            lambda item: rx.table.row(
                                rx.table.cell(item.get("month", "Unknown")),
                                rx.table.cell(item.created),
                                rx.table.cell(item.modified),
                            ),
                        )
                    ),
                ),
                rx.text("No recent activity data", color="gray"),
            ),
            size="2",
        ),
        spacing="4",
        width="100%",
    )


def authors_tab() -> rx.Component:
    """Author analysis tab."""
    return rx.vstack(
        rx.heading("Author Analysis", size="6", margin_bottom="4"),
        # Top authors
        rx.heading("Top Authors", size="5", margin_bottom="3"),
        rx.card(
            rx.cond(
                MetadataForensicsState.authors_list,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Author"),
                            rx.table.column_header_cell("Document Count"),
                            rx.table.column_header_cell("Percentage"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            MetadataForensicsState.authors_list,
                            lambda item: rx.table.row(
                                rx.table.cell(item.name),
                                rx.table.cell(item.count),
                                rx.table.cell(f"{item.percentage:.1f}%"),
                            ),
                        )
                    ),
                ),
                rx.text("No author data available", color="gray"),
            ),
            size="2",
            margin_bottom="6",
        ),
        # Statistics
        rx.heading("Author Statistics", size="5", margin_bottom="3"),
        rx.grid(
            stat_card(
                "Unique Authors",
                MetadataForensicsState.author_analysis.get("total_authors", 0),
                "users",
                "blue",
            ),
            stat_card(
                "Single-Doc Authors",
                MetadataForensicsState.author_analysis.get(
                    "single_document_authors", 0
                ),
                "user",
                "green",
            ),
            stat_card(
                "Prolific Authors",
                MetadataForensicsState.author_analysis.get("prolific_authors", 0),
                "award",
                "orange",
            ),
            columns="3",
            spacing="4",
        ),
        spacing="4",
        width="100%",
    )


def document_detail_modal() -> rx.Component:
    """Modal showing detailed metadata for a single document."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.heading("Document Metadata", size="5"),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            on_click=MetadataForensicsState.close_document_modal,
                            variant="ghost",
                        )
                    ),
                    justify="between",
                    width="100%",
                    margin_bottom="4",
                ),
                # Authenticity score
                rx.card(
                    rx.vstack(
                        rx.text("Authenticity Score", weight="bold", size="4"),
                        rx.hstack(
                            rx.text(
                                MetadataForensicsState.selected_doc_authenticity_score,
                                size="8",
                                weight="bold",
                            ),
                            rx.badge(
                                MetadataForensicsState.selected_doc_risk_level,
                                color_scheme=rx.match(
                                    MetadataForensicsState.selected_doc_risk_level,
                                    ("CRITICAL", "red"),
                                    ("HIGH", "orange"),
                                    ("MEDIUM", "yellow"),
                                    ("LOW", "green"),
                                    "gray",
                                ),
                            ),
                            spacing="3",
                            align="center",
                        ),
                        spacing="2",
                    ),
                    size="2",
                    margin_bottom="4",
                ),
                # Basic metadata
                rx.card(
                    rx.vstack(
                        rx.text(
                            "Basic Metadata", weight="bold", size="4", margin_bottom="2"
                        ),
                        rx.grid(
                            rx.vstack(
                                rx.text("Filename:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_filename,
                                    size="2",
                                ),
                            ),
                            rx.vstack(
                                rx.text("Author:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_author, size="2"
                                ),
                            ),
                            rx.vstack(
                                rx.text("Creator:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_creator,
                                    size="2",
                                ),
                            ),
                            rx.vstack(
                                rx.text("Producer:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_producer,
                                    size="2",
                                ),
                            ),
                            columns="2",
                            spacing="4",
                        ),
                        spacing="3",
                    ),
                    size="2",
                    margin_bottom="4",
                ),
                # Dates
                rx.card(
                    rx.vstack(
                        rx.text("Dates", weight="bold", size="4", margin_bottom="2"),
                        rx.grid(
                            rx.vstack(
                                rx.text("Creation:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_creation_date,
                                    size="2",
                                ),
                            ),
                            rx.vstack(
                                rx.text("Modification:", weight="bold", size="2"),
                                rx.text(
                                    MetadataForensicsState.selected_doc_modification_date,
                                    size="2",
                                ),
                            ),
                            columns="2",
                            spacing="4",
                        ),
                        spacing="3",
                    ),
                    size="2",
                    margin_bottom="4",
                ),
                # Anomalies
                rx.cond(
                    MetadataForensicsState.selected_doc_anomalies,
                    rx.card(
                        rx.vstack(
                            rx.text(
                                "Anomalies Detected",
                                weight="bold",
                                size="4",
                                color="red",
                                margin_bottom="2",
                            ),
                            rx.foreach(
                                MetadataForensicsState.selected_doc_anomalies,
                                lambda anomaly: rx.box(
                                    rx.hstack(
                                        rx.badge(
                                            anomaly.get("type", "UNKNOWN"),
                                            color_scheme="red",
                                        ),
                                        rx.badge(
                                            anomaly.get("severity", "LOW"),
                                            color_scheme="orange",
                                        ),
                                        spacing="2",
                                    ),
                                    rx.text(
                                        anomaly.get("description", ""),
                                        size="2",
                                        margin_top="1",
                                    ),
                                    margin_bottom="3",
                                ),
                            ),
                            spacing="2",
                        ),
                        size="2",
                        margin_bottom="4",
                    ),
                ),
                # Suspicious indicators
                rx.cond(
                    MetadataForensicsState.selected_doc_suspicious_indicators,
                    rx.card(
                        rx.vstack(
                            rx.text(
                                "Suspicious Indicators",
                                weight="bold",
                                size="4",
                                color="orange",
                                margin_bottom="2",
                            ),
                            rx.foreach(
                                MetadataForensicsState.selected_doc_suspicious_indicators,
                                lambda indicator: rx.box(
                                    rx.hstack(
                                        rx.badge(
                                            indicator.get("type", "UNKNOWN"),
                                            color_scheme="yellow",
                                        ),
                                        spacing="2",
                                    ),
                                    rx.text(
                                        indicator.get("description", ""),
                                        size="2",
                                        margin_top="1",
                                    ),
                                    margin_bottom="3",
                                ),
                            ),
                            spacing="2",
                        ),
                        size="2",
                    ),
                ),
                spacing="4",
                width="100%",
                max_height="80vh",
                overflow_y="auto",
            ),
            max_width="800px",
        ),
        open=MetadataForensicsState.show_document_modal,
    )


def metadata_forensics_page() -> rx.Component:
    """Main metadata forensics dashboard page."""
    return layout(
        rx.box(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.heading("Metadata Forensics", size="8"),
                    # Load or Refresh button based on data state
                    rx.cond(
                        MetadataForensicsState.has_data,
                        rx.button(
                            rx.icon("refresh-cw", size=18),
                            "Refresh",
                            on_click=MetadataForensicsState.refresh_data,
                            loading=MetadataForensicsState.is_loading,
                            variant="soft",
                        ),
                        rx.button(
                            rx.icon("play", size=18),
                            "Load Data",
                            on_click=MetadataForensicsState.load_dashboard_data,
                            loading=MetadataForensicsState.is_loading,
                            color_scheme="blue",
                        ),
                    ),
                    justify="between",
                    width="100%",
                    margin_bottom="6",
                ),
                # Error/Success messages
                rx.cond(
                    MetadataForensicsState.error_message != "",
                    rx.callout(
                        MetadataForensicsState.error_message,
                        icon="circle-alert",
                        color_scheme="red",
                        role="alert",
                        margin_bottom="4",
                    ),
                ),
                rx.cond(
                    MetadataForensicsState.success_message != "",
                    rx.callout(
                        MetadataForensicsState.success_message,
                        icon="circle-check",
                        color_scheme="green",
                        margin_bottom="4",
                    ),
                ),
                # Tabs
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Overview", value="overview"),
                        rx.tabs.trigger("Software", value="software"),
                        rx.tabs.trigger("Timeline", value="timeline"),
                        rx.tabs.trigger("Authors", value="authors"),
                    ),
                    rx.tabs.content(overview_tab(), value="overview"),
                    rx.tabs.content(software_tab(), value="software"),
                    rx.tabs.content(timeline_tab(), value="timeline"),
                    rx.tabs.content(authors_tab(), value="authors"),
                    default_value="overview",
                    value=MetadataForensicsState.active_tab,
                    on_change=MetadataForensicsState.set_active_tab,
                ),
                spacing="4",
                width="100%",
            ),
            # Document detail modal
            document_detail_modal(),
            width="100%",
            padding="6",
            # Removed on_mount - user must click Load button
        )
    )
