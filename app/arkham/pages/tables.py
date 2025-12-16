import reflex as rx
from ..components.layout import layout
from ..state.table_state import TableState
from ..components.design_tokens import SPACING, FONT_SIZE


def table_row(table: dict) -> rx.Component:
    """A row in the tables list."""
    return rx.table.row(
        rx.table.cell(table["doc_title"]),
        rx.table.cell(str(table["page_num"])),
        rx.table.cell(f"{table['row_count']} x {table['col_count']}"),
        rx.table.cell(table["created_at"]),
        rx.table.cell(
            rx.button(
                "View",
                size="1",
                on_click=lambda: TableState.select_table(table["id"]),
            )
        ),
    )


def tables_list() -> rx.Component:
    """The list of extracted tables."""
    return rx.vstack(
        rx.heading("Extracted Tables", size="6"),
        rx.text(
            "Tables automatically extracted from documents.",
            color="gray.11",
            font_size=FONT_SIZE["sm"],
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Document"),
                    rx.table.column_header_cell("Page"),
                    rx.table.column_header_cell("Dimensions"),
                    rx.table.column_header_cell("Extracted At"),
                    rx.table.column_header_cell("Actions"),
                )
            ),
            rx.table.body(rx.foreach(TableState.tables, table_row)),
            width="100%",
            variant="surface",
        ),
        # Pagination
        rx.hstack(
            rx.button(
                "Previous",
                on_click=lambda: TableState.set_current_page(
                    TableState.current_page - 1
                ),
                disabled=TableState.current_page <= 1,
                variant="outline",
            ),
            rx.text(f"Page {TableState.current_page}", color="gray.11"),
            rx.button(
                "Next",
                on_click=lambda: TableState.set_current_page(
                    TableState.current_page + 1
                ),
                disabled=TableState.tables.length() < TableState.items_per_page,
                variant="outline",
            ),
            justify="center",
            width="100%",
            spacing=SPACING["md"],
        ),
        width="100%",
        spacing=SPACING["md"],
    )


def table_viewer() -> rx.Component:
    """The detailed view of a selected table."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Table Viewer", size="6"),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    "Export CSV",
                    on_click=TableState.export_csv,
                    variant="surface",
                    high_contrast=True,
                ),
                rx.button(
                    "Back to List",
                    variant="soft",
                    on_click=TableState.clear_selection,
                ),
                spacing=SPACING["sm"],
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            TableState.selected_table_content,
            rx.scroll_area(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.foreach(
                                TableState.table_headers,
                                lambda h: rx.table.column_header_cell(h),
                            )
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            TableState.table_rows,
                            lambda row: rx.table.row(
                                rx.foreach(
                                    row,
                                    lambda cell: rx.table.cell(cell),
                                )
                            ),
                        )
                    ),
                    variant="surface",
                    width="100%",
                ),
                height="600px",
                width="100%",
            ),
            rx.text("No content available or error loading table.", color="red.9"),
        ),
        width="100%",
        spacing=SPACING["md"],
    )


def tables_page() -> rx.Component:
    """The main tables page."""
    return layout(
        rx.vstack(
            rx.heading("📊 Data Tables", size="8"),
            # Error message
            rx.cond(
                TableState.error_message != "",
                rx.callout(
                    TableState.error_message,
                    icon="triangle-alert",
                    color_scheme="red",
                    width="100%",
                ),
            ),
            # Loading indicator
            rx.cond(
                TableState.is_loading,
                rx.center(rx.spinner(size="3"), width="100%", padding=SPACING["md"]),
            ),
            # Main content area
            rx.cond(
                TableState.selected_table_id,
                table_viewer(),
                tables_list(),
            ),
            spacing=SPACING["md"],
            width="100%",
            on_mount=TableState.load_tables,
        )
    )
