"""
Export Investigation Packages Page

Export investigation data in various formats.
"""

import reflex as rx
from app.arkham.state.export_state import ExportState
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


def export_option(
    label: str, description: str, checked: bool, on_change
) -> rx.Component:
    """Toggle option for export."""
    return rx.hstack(
        rx.switch(
            checked=checked,
            on_change=on_change,
        ),
        rx.vstack(
            rx.text(label, weight="medium", size="2"),
            rx.text(description, size="1", color="gray"),
            align_items="start",
            spacing="0",
        ),
        spacing="3",
        padding="3",
        width="100%",
        border_radius="md",
        _hover={"bg": "var(--gray-a3)"},
    )


def csv_export_button(label: str, data_type: str, icon: str) -> rx.Component:
    """Button to export CSV data."""
    return rx.button(
        rx.icon(icon, size=14),
        label,
        variant="soft",
        on_click=lambda: ExportState.export_csv(data_type),
    )


def entity_chip(entity) -> rx.Component:
    """Chip showing an entity for selection."""
    return rx.box(
        rx.hstack(
            rx.checkbox(
                checked=ExportState.selected_entity_ids.contains(entity.id),
                on_change=lambda: ExportState.toggle_entity(entity.id),
            ),
            rx.text(entity.name, size="2"),
            rx.badge(entity.type, size="1", variant="soft"),
            spacing="2",
        ),
        padding="2",
        border="1px solid var(--gray-6)",
        border_radius="md",
        cursor="pointer",
        on_click=lambda: ExportState.toggle_entity(entity.id),
        _hover={"bg": "var(--gray-a3)"},
    )


def export_page() -> rx.Component:
    """Main Export page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Export", size="8"),
                    rx.text(
                        "Export investigation packages and data.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("package", size=14),
                    "Create Package",
                    on_click=ExportState.create_package,
                    loading=ExportState.is_exporting,
                    size="3",
                ),
                width="100%",
                align_items="end",
            ),
            # Stats
            rx.grid(
                stat_card("Documents", ExportState.doc_count, "file-text", "blue"),
                stat_card("Entities", ExportState.entity_count, "users", "green"),
                stat_card(
                    "Relationships", ExportState.rel_count, "git-branch", "purple"
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            # Export options
            rx.grid(
                # Package options
                rx.card(
                    rx.vstack(
                        rx.heading("Package Contents", size="4"),
                        rx.divider(),
                        export_option(
                            "Include Entities",
                            "Entity profiles and evidence",
                            ExportState.include_entities,
                            ExportState.set_include_entities,
                        ),
                        export_option(
                            "Include Timeline",
                            "Chronological event list",
                            ExportState.include_timeline,
                            ExportState.set_include_timeline,
                        ),
                        export_option(
                            "Include Relationships",
                            "Entity network graph data",
                            ExportState.include_relationships,
                            ExportState.set_include_relationships,
                        ),
                        spacing="2",
                        align_items="start",
                        width="100%",
                    ),
                    padding="4",
                ),
                # Quick exports
                rx.card(
                    rx.vstack(
                        rx.heading("Quick CSV Exports", size="4"),
                        rx.divider(),
                        rx.text(
                            "Export individual data types as CSV files.",
                            size="2",
                            color="gray",
                        ),
                        rx.hstack(
                            csv_export_button("Entities", "entities", "users"),
                            csv_export_button("Documents", "documents", "file-text"),
                            csv_export_button(
                                "Relationships", "relationships", "git-branch"
                            ),
                            spacing="2",
                            wrap="wrap",
                        ),
                        spacing="3",
                        align_items="start",
                        width="100%",
                    ),
                    padding="4",
                ),
                columns="2",
                spacing="4",
                width="100%",
            ),
            # Entity selection
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Entity Selection", size="4"),
                        rx.spacer(),
                        rx.hstack(
                            rx.button(
                                "Select All",
                                size="1",
                                variant="ghost",
                                on_click=ExportState.select_all_entities,
                            ),
                            rx.button(
                                "Clear",
                                size="1",
                                variant="ghost",
                                on_click=ExportState.clear_selection,
                            ),
                            spacing="2",
                        ),
                        width="100%",
                    ),
                    rx.text(
                        "Select specific entities to include detailed reports for:",
                        size="2",
                        color="gray",
                    ),
                    rx.text(
                        f"{ExportState.selected_entity_ids.length()} entities selected",
                        size="1",
                        weight="medium",
                    ),
                    rx.divider(),
                    rx.cond(
                        ExportState.available_entities.length() > 0,
                        rx.box(
                            rx.flex(
                                rx.foreach(ExportState.available_entities, entity_chip),
                                wrap="wrap",
                                spacing="2",
                            ),
                            max_height="200px",
                            overflow_y="auto",
                            width="100%",
                        ),
                        rx.text("No entities available", color="gray"),
                    ),
                    spacing="3",
                    align_items="start",
                    width="100%",
                ),
                padding="4",
            ),
            # Export result
            rx.cond(
                ExportState.export_ready,
                rx.callout(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("circle-check", size=16, color="var(--green-9)"),
                            rx.text(
                                f"Package ready: {ExportState.export_filename}",
                                weight="medium",
                            ),
                            spacing="2",
                        ),
                        rx.text(
                            "Your investigation package has been generated with the selected data.",
                            size="2",
                        ),
                        align_items="start",
                        spacing="1",
                    ),
                    icon="package",
                    color="green",
                ),
                rx.fragment(),
            ),
            # CSV preview
            rx.cond(
                ExportState.csv_data != "",
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.heading(
                                f"{ExportState.csv_type.to(str).upper()} CSV Export",
                                size="4",
                            ),
                            rx.spacer(),
                            rx.button(
                                rx.icon("download", size=14),
                                "Download",
                                variant="soft",
                                size="1",
                                on_click=ExportState.download_csv,
                            ),
                            rx.button(
                                rx.icon("x", size=14),
                                "Close",
                                variant="ghost",
                                size="1",
                                on_click=ExportState.clear_export,
                            ),
                            width="100%",
                        ),
                        rx.divider(),
                        rx.code_block(
                            ExportState.csv_data,
                            language="csv",
                            show_line_numbers=True,
                        ),
                        spacing="3",
                        align_items="start",
                        width="100%",
                    ),
                    padding="4",
                ),
                rx.fragment(),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=ExportState.load_options,
        ),
        width="100%",
        height="100vh",
    )
