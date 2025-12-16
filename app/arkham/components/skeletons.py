import reflex as rx


def skeleton_card() -> rx.Component:
    """Skeleton loader for a card/result item."""
    return rx.card(
        rx.vstack(
            rx.skeleton(height="20px", width="60%"),
            rx.skeleton(height="16px", width="100%"),
            rx.skeleton(height="16px", width="90%"),
            rx.skeleton(height="16px", width="80%"),
            spacing="2",
        ),
        width="100%",
    )


def skeleton_table_row() -> rx.Component:
    """Skeleton loader for a table row."""
    return rx.table.row(
        rx.table.cell(rx.skeleton(height="16px", width="80%")),
        rx.table.cell(rx.skeleton(height="16px", width="40px")),
        rx.table.cell(rx.skeleton(height="16px", width="60px")),
        rx.table.cell(rx.skeleton(height="16px", width="100px")),
        rx.table.cell(rx.skeleton(height="24px", width="60px")),
    )


def skeleton_stat_card() -> rx.Component:
    """Skeleton loader for a stat card."""
    return rx.card(
        rx.hstack(
            rx.skeleton(height="48px", width="48px", border_radius="full"),
            rx.vstack(
                rx.skeleton(height="14px", width="80px"),
                rx.skeleton(height="24px", width="60px"),
                spacing="1",
            ),
            spacing="4",
            align="center",
        ),
        width="100%",
    )


def skeleton_search_results(count: int = 5) -> rx.Component:
    """Multiple skeleton cards for search results."""
    return rx.vstack(
        *[skeleton_card() for _ in range(count)],
        spacing="4",
        width="100%",
    )


def skeleton_table(rows: int = 5) -> rx.Component:
    """Skeleton loader for a table."""
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell(rx.skeleton(height="16px", width="100px")),
                rx.table.column_header_cell(rx.skeleton(height="16px", width="60px")),
                rx.table.column_header_cell(rx.skeleton(height="16px", width="80px")),
                rx.table.column_header_cell(rx.skeleton(height="16px", width="100px")),
                rx.table.column_header_cell(rx.skeleton(height="16px", width="80px")),
            )
        ),
        rx.table.body(*[skeleton_table_row() for _ in range(rows)]),
        width="100%",
    )


def skeleton_stats_grid() -> rx.Component:
    """Skeleton loader for stats grid."""
    return rx.grid(
        skeleton_stat_card(),
        skeleton_stat_card(),
        skeleton_stat_card(),
        skeleton_stat_card(),
        columns="4",
        spacing="4",
        width="100%",
    )


# Aliases for compatibility with error_boundary.py
card_skeleton = skeleton_card
table_skeleton = skeleton_table
