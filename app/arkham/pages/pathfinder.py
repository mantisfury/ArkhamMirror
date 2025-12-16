"""
Shortest Path Finder Page

Find connections between entities in the graph.
"""

import reflex as rx
from app.arkham.state.pathfinder_state import PathFinderState
from app.arkham.components.sidebar import sidebar


def entity_selector(label: str, value: int, on_change, entities) -> rx.Component:
    """Entity selection dropdown."""
    return rx.vstack(
        rx.text(label, size="2", weight="bold"),
        rx.select.root(
            rx.select.trigger(placeholder="Select entity...", width="100%"),
            rx.select.content(
                rx.select.group(
                    rx.foreach(
                        entities,
                        lambda e: rx.select.item(
                            f"{e.name} ({e.type})",
                            value=e.id.to(str),
                        ),
                    ),
                ),
            ),
            value=value.to(str),
            on_change=on_change,
        ),
        spacing="1",
        width="100%",
    )


def path_step(node, index, is_last: bool) -> rx.Component:
    """Single step in the path."""
    return rx.hstack(
        rx.vstack(
            rx.box(
                rx.text((index + 1).to(str), size="1", weight="bold"),
                width="24px",
                height="24px",
                border_radius="full",
                bg="var(--blue-9)",
                display="flex",
                align_items="center",
                justify_content="center",
                color="white",
            ),
            rx.cond(
                is_last == False,
                rx.box(
                    width="2px",
                    height="30px",
                    bg="var(--gray-6)",
                ),
                rx.fragment(),
            ),
            spacing="0",
        ),
        rx.card(
            rx.hstack(
                rx.icon("user", size=16),
                rx.text(node.name, weight="medium"),
                rx.badge(node.type, size="1", variant="outline"),
                rx.badge(f"{node.mentions} mentions", size="1", variant="soft"),
                spacing="2",
            ),
            padding="3",
        ),
        spacing="3",
        align_items="start",
    )


def neighbor_row(neighbor) -> rx.Component:
    """Row showing a neighboring entity."""
    return rx.hstack(
        rx.box(
            rx.text(neighbor.distance, size="1", weight="bold"),
            width="24px",
            height="24px",
            border_radius="full",
            bg="var(--purple-9)",
            display="flex",
            align_items="center",
            justify_content="center",
            color="white",
        ),
        rx.text(neighbor.name, weight="medium", size="2"),
        rx.badge(neighbor.type, size="1", variant="outline"),
        rx.spacer(),
        rx.badge(f"{neighbor.mentions} mentions", size="1", variant="soft"),
        width="100%",
        padding="2",
        border_bottom="1px solid var(--gray-4)",
    )


def pathfinder_page() -> rx.Component:
    """Main Path Finder page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Path Finder", size="8"),
                    rx.text(
                        "Find shortest paths between entities in the graph.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                width="100%",
            ),
            # Main content
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Shortest Path", value="shortest"),
                    rx.tabs.trigger("Neighbors", value="neighbors"),
                ),
                rx.tabs.content(
                    # Shortest path tab
                    rx.vstack(
                        rx.grid(
                            rx.card(
                                rx.vstack(
                                    rx.heading("Select Entities", size="4"),
                                    rx.divider(),
                                    entity_selector(
                                        "From Entity",
                                        PathFinderState.source_id,
                                        PathFinderState.set_source,
                                        PathFinderState.entities,
                                    ),
                                    rx.center(
                                        rx.button(
                                            rx.icon("arrow-up-down", size=14),
                                            "Swap",
                                            variant="ghost",
                                            size="1",
                                            on_click=PathFinderState.swap_entities,
                                        ),
                                    ),
                                    entity_selector(
                                        "To Entity",
                                        PathFinderState.target_id,
                                        PathFinderState.set_target,
                                        PathFinderState.entities,
                                    ),
                                    rx.divider(),
                                    rx.hstack(
                                        rx.text("Min Connection Strength:", size="1"),
                                        rx.input(
                                            type="number",
                                            value=PathFinderState.min_weight.to(str),
                                            on_change=PathFinderState.set_min_weight,
                                            width="60px",
                                            size="1",
                                        ),
                                        spacing="2",
                                    ),
                                    rx.button(
                                        rx.icon("route", size=14),
                                        "Find Path",
                                        width="100%",
                                        on_click=PathFinderState.find_path,
                                        loading=PathFinderState.is_loading,
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="4",
                            ),
                            rx.card(
                                rx.vstack(
                                    rx.heading("Path Result", size="4"),
                                    rx.divider(),
                                    rx.cond(
                                        PathFinderState.error_message != "",
                                        rx.callout(
                                            PathFinderState.error_message,
                                            icon="triangle-alert",
                                            color="red",
                                        ),
                                        rx.cond(
                                            PathFinderState.path_found,
                                            rx.vstack(
                                                rx.hstack(
                                                    rx.icon(
                                                        "circle-check",
                                                        size=16,
                                                        color="var(--green-9)",
                                                    ),
                                                    rx.text(
                                                        f"Path found! ({PathFinderState.path_length} steps)",
                                                        weight="medium",
                                                    ),
                                                    spacing="2",
                                                ),
                                                rx.divider(),
                                                rx.vstack(
                                                    rx.foreach(
                                                        PathFinderState.path_nodes,
                                                        lambda node, i: path_step(
                                                            node,
                                                            i,
                                                            i
                                                            == PathFinderState.path_nodes.length()
                                                            - 1,
                                                        ),
                                                    ),
                                                    spacing="0",
                                                    align_items="start",
                                                    width="100%",
                                                ),
                                                spacing="3",
                                                width="100%",
                                            ),
                                            rx.text(
                                                "Select entities and click 'Find Path' to discover connections.",
                                                size="2",
                                                color="gray",
                                            ),
                                        ),
                                    ),
                                    spacing="4",
                                    align_items="start",
                                    width="100%",
                                ),
                                padding="4",
                            ),
                            columns="2",
                            spacing="4",
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                        padding_top="4",
                    ),
                    value="shortest",
                ),
                rx.tabs.content(
                    # Neighbors tab
                    rx.vstack(
                        rx.grid(
                            rx.card(
                                rx.vstack(
                                    rx.heading("Find Neighbors", size="4"),
                                    rx.divider(),
                                    entity_selector(
                                        "Entity",
                                        PathFinderState.source_id,
                                        PathFinderState.set_source,
                                        PathFinderState.entities,
                                    ),
                                    rx.hstack(
                                        rx.text("Degrees of separation:", size="1"),
                                        rx.select.root(
                                            rx.select.trigger(
                                                placeholder="Select...",
                                                width="80px",
                                            ),
                                            rx.select.content(
                                                rx.select.item("1 degree", value="1"),
                                                rx.select.item("2 degrees", value="2"),
                                                rx.select.item("3 degrees", value="3"),
                                            ),
                                            value=PathFinderState.neighbor_degree.to(
                                                str
                                            ),
                                            on_change=PathFinderState.set_neighbor_degree,
                                        ),
                                        spacing="2",
                                    ),
                                    rx.button(
                                        rx.icon("users", size=14),
                                        "Find Neighbors",
                                        width="100%",
                                        on_click=PathFinderState.find_neighbors,
                                        loading=PathFinderState.is_loading,
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="4",
                            ),
                            rx.card(
                                rx.vstack(
                                    rx.hstack(
                                        rx.heading("Neighbors", size="4"),
                                        rx.spacer(),
                                        rx.badge(
                                            f"{PathFinderState.neighbors.length()} found",
                                            size="1",
                                        ),
                                        width="100%",
                                    ),
                                    rx.divider(),
                                    rx.cond(
                                        PathFinderState.neighbors.length() > 0,
                                        rx.vstack(
                                            rx.foreach(
                                                PathFinderState.neighbors,
                                                neighbor_row,
                                            ),
                                            spacing="0",
                                            width="100%",
                                            max_height="400px",
                                            overflow_y="auto",
                                        ),
                                        rx.text(
                                            "Select an entity to find connected neighbors.",
                                            size="2",
                                            color="gray",
                                        ),
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="4",
                            ),
                            columns="2",
                            spacing="4",
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                        padding_top="4",
                    ),
                    value="neighbors",
                ),
                value=PathFinderState.active_tab,
                on_change=PathFinderState.set_active_tab,
                width="100%",
            ),
            padding="2em",
            width="100%",
            align_items="start",
            spacing="6",
            on_mount=PathFinderState.load_entities,
        ),
        width="100%",
        height="100vh",
    )
