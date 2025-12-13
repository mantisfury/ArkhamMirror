"""
Entity Influence Mapping Page

Visualizes entity power dynamics, centrality metrics, and hidden relationships.
"""

import reflex as rx
from app.arkham.state.influence_state import InfluenceState
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


def entity_row(entity) -> rx.Component:
    """Row for entity ranking table."""
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.badge(entity.type, variant="soft", size="1"),
                rx.text(entity.name, weight="medium"),
                spacing="2",
            )
        ),
        rx.table.cell(rx.text(f"{entity.influence_score:.1f}", weight="bold")),
        rx.table.cell(rx.text(entity.degree)),
        rx.table.cell(rx.text(f"{entity.betweenness:.3f}")),
        rx.table.cell(rx.text(f"{entity.pagerank:.3f}")),
        rx.table.cell(rx.badge(f"C{entity.community}", variant="outline", size="1")),
        rx.table.cell(
            rx.button(
                rx.icon("eye", size=14),
                variant="ghost",
                size="1",
                on_click=lambda: InfluenceState.select_entity(entity),
            )
        ),
        _hover={"bg": "var(--gray-a3)"},
    )


def broker_card(broker) -> rx.Component:
    """Card for information broker."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("network", size=18, color="var(--orange-9)"),
                rx.text(broker.name, weight="bold"),
                spacing="2",
            ),
            rx.hstack(
                rx.text("Betweenness:", size="1", color="gray"),
                rx.text(f"{broker.betweenness:.4f}", size="1", weight="medium"),
                rx.spacer(),
                rx.text("Connections:", size="1", color="gray"),
                rx.text(broker.degree, size="1", weight="medium"),
                width="100%",
            ),
            rx.badge(f"Community {broker.community}", variant="soft", size="1"),
            align_items="start",
            spacing="2",
        ),
        padding="3",
    )


def bridge_row(bridge) -> rx.Component:
    """Row for community bridge connection."""
    return rx.table.row(
        rx.table.cell(rx.text(bridge.entity1_name)),
        rx.table.cell(rx.icon("arrow-right", size=14)),
        rx.table.cell(rx.text(bridge.entity2_name)),
        rx.table.cell(
            rx.hstack(
                rx.badge(f"C{bridge.community1}", size="1", variant="outline"),
                rx.icon("link", size=12),
                rx.badge(f"C{bridge.community2}", size="1", variant="outline"),
                spacing="1",
            )
        ),
        rx.table.cell(rx.text(f"{bridge.strength:.2f}")),
    )


def rankings_tab() -> rx.Component:
    """Tab showing entity influence rankings."""
    return rx.vstack(
        rx.heading("Influence Rankings", size="5"),
        rx.text(
            "Entities ranked by composite influence score (degree, betweenness, PageRank, eigenvector centrality).",
            color="gray",
            size="2",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Entity"),
                    rx.table.column_header_cell("Influence"),
                    rx.table.column_header_cell("Connections"),
                    rx.table.column_header_cell("Betweenness"),
                    rx.table.column_header_cell("PageRank"),
                    rx.table.column_header_cell("Community"),
                    rx.table.column_header_cell(""),
                )
            ),
            rx.table.body(rx.foreach(InfluenceState.entities, entity_row)),
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def power_dynamics_tab() -> rx.Component:
    """Tab showing brokers and bridges."""
    return rx.vstack(
        # Brokers section
        rx.heading("Information Brokers", size="5"),
        rx.text(
            "Entities that control information flow between groups (high betweenness centrality).",
            color="gray",
            size="2",
        ),
        rx.cond(
            InfluenceState.brokers.length() > 0,
            rx.grid(
                rx.foreach(InfluenceState.brokers, broker_card),
                columns="3",
                spacing="3",
                width="100%",
            ),
            rx.callout(
                "No significant brokers detected. Network may be too small or densely connected.",
                icon="info",
            ),
        ),
        rx.divider(margin_y="4"),
        # Bridges section
        rx.heading("Community Bridges", size="5"),
        rx.text(
            "Connections that link different communities together.",
            color="gray",
            size="2",
        ),
        rx.cond(
            InfluenceState.bridges.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Entity 1"),
                        rx.table.column_header_cell(""),
                        rx.table.column_header_cell("Entity 2"),
                        rx.table.column_header_cell("Communities"),
                        rx.table.column_header_cell("Strength"),
                    )
                ),
                rx.table.body(rx.foreach(InfluenceState.bridges, bridge_row)),
                width="100%",
            ),
            rx.callout(
                "No cross-community bridges found.",
                icon="info",
            ),
        ),
        spacing="4",
        width="100%",
    )


def communities_tab() -> rx.Component:
    """Tab showing community breakdown."""
    return rx.vstack(
        rx.heading("Community Analysis", size="5"),
        rx.text(
            "Groups of closely connected entities detected via Louvain algorithm.",
            color="gray",
            size="2",
        ),
        rx.grid(
            rx.foreach(
                InfluenceState.communities,
                lambda comm: rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.badge(f"Community {comm['id']}", color_scheme="blue"),
                            rx.spacer(),
                            rx.text(f"{comm['size']} members", size="2", color="gray"),
                            width="100%",
                        ),
                        rx.cond(
                            comm["key_member"],
                            rx.text(
                                f"Key member: {comm['key_member']}",
                                size="2",
                                weight="medium",
                            ),
                            rx.text(""),
                        ),
                        align_items="start",
                        spacing="2",
                    ),
                    padding="3",
                ),
            ),
            columns="4",
            spacing="3",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def entity_detail_modal() -> rx.Component:
    """Modal showing selected entity details."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.heading("Entity Detail", size="5"),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            variant="ghost",
                            on_click=InfluenceState.clear_selection,
                        )
                    ),
                    justify="between",
                    width="100%",
                ),
                rx.cond(
                    InfluenceState.selected_entity,
                    rx.vstack(
                        rx.hstack(
                            rx.badge(
                                InfluenceState.selected_entity.type,
                                size="2",
                            ),
                            rx.heading(
                                InfluenceState.selected_entity.name,
                                size="6",
                            ),
                            spacing="2",
                        ),
                        rx.grid(
                            stat_card(
                                "Influence Score",
                                InfluenceState.selected_entity.influence_score,
                                "trending-up",
                                "blue",
                            ),
                            rx.box(
                                rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.icon(
                                                "git-branch",
                                                size=20,
                                                color="var(--green-9)",
                                            ),
                                            rx.text(
                                                "Connections", size="2", color="gray"
                                            ),
                                            spacing="2",
                                        ),
                                        rx.heading(
                                            InfluenceState.selected_entity.degree,
                                            size="6",
                                        ),
                                        rx.button(
                                            rx.icon("external-link", size=12),
                                            "View Connections",
                                            size="1",
                                            variant="soft",
                                            color_scheme="green",
                                            on_click=lambda: InfluenceState.load_connection_sources(
                                                InfluenceState.selected_entity.id
                                            ),
                                        ),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="4",
                                ),
                            ),
                            rx.box(
                                rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.icon(
                                                "message-circle",
                                                size=20,
                                                color="var(--purple-9)",
                                            ),
                                            rx.text("Mentions", size="2", color="gray"),
                                            spacing="2",
                                        ),
                                        rx.heading(
                                            InfluenceState.selected_entity.mentions,
                                            size="6",
                                        ),
                                        rx.button(
                                            rx.icon("external-link", size=12),
                                            "View Sources",
                                            size="1",
                                            variant="soft",
                                            color_scheme="purple",
                                            on_click=lambda: InfluenceState.load_mention_sources(
                                                InfluenceState.selected_entity.id
                                            ),
                                        ),
                                        align_items="start",
                                        spacing="1",
                                    ),
                                    padding="4",
                                ),
                            ),
                            columns="3",
                            spacing="3",
                            width="100%",
                        ),
                        rx.divider(),
                        rx.heading("Centrality Metrics", size="4"),
                        rx.table.root(
                            rx.table.body(
                                rx.table.row(
                                    rx.table.cell("Degree Centrality"),
                                    rx.table.cell(
                                        InfluenceState.selected_entity.degree_centrality
                                    ),
                                ),
                                rx.table.row(
                                    rx.table.cell("Betweenness"),
                                    rx.table.cell(
                                        InfluenceState.selected_entity.betweenness
                                    ),
                                ),
                                rx.table.row(
                                    rx.table.cell("Closeness"),
                                    rx.table.cell(
                                        InfluenceState.selected_entity.closeness
                                    ),
                                ),
                                rx.table.row(
                                    rx.table.cell("PageRank"),
                                    rx.table.cell(
                                        InfluenceState.selected_entity.pagerank
                                    ),
                                ),
                                rx.table.row(
                                    rx.table.cell("Eigenvector"),
                                    rx.table.cell(
                                        InfluenceState.selected_entity.eigenvector
                                    ),
                                ),
                            ),
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    rx.spinner(),
                ),
                spacing="4",
                width="100%",
            ),
            max_width="700px",
        ),
        open=InfluenceState.selected_entity.bool(),
        on_open_change=InfluenceState.on_open_change,
    )


def mention_sources_modal() -> rx.Component:
    """Modal showing where an entity was mentioned."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon("file-text", size=20),
                    rx.heading(
                        f"Mentions: {InfluenceState.mention_sources_entity_name}",
                        size="5",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            variant="ghost",
                            on_click=InfluenceState.close_mentions_modal,
                        )
                    ),
                    width="100%",
                ),
                rx.text(
                    f"Found in {InfluenceState.mention_sources_unique_docs} unique documents",
                    color="gray",
                    size="2",
                ),
                rx.divider(),
                rx.cond(
                    InfluenceState.mention_sources.length() > 0,
                    rx.scroll_area(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Mention Text"),
                                    rx.table.column_header_cell("Document"),
                                    rx.table.column_header_cell("Type"),
                                    rx.table.column_header_cell("Count"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    InfluenceState.mention_sources,
                                    lambda src: rx.table.row(
                                        rx.table.cell(
                                            rx.text(
                                                src["mention_text"], weight="medium"
                                            )
                                        ),
                                        rx.table.cell(
                                            rx.link(
                                                src["doc_title"],
                                                href=f"/document/{src['doc_id']}",
                                                color="blue",
                                            )
                                        ),
                                        rx.table.cell(
                                            rx.badge(
                                                src["doc_type"],
                                                variant="soft",
                                                size="1",
                                            )
                                        ),
                                        rx.table.cell(rx.text(src["mention_count"])),
                                    ),
                                )
                            ),
                            width="100%",
                        ),
                        max_height="400px",
                    ),
                    rx.callout(
                        "No mention sources found.",
                        icon="info",
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            max_width="800px",
        ),
        open=InfluenceState.show_mentions_modal,
        on_open_change=InfluenceState.on_mentions_modal_change,
    )


def connection_sources_modal() -> rx.Component:
    """Modal showing entity connections with shared documents."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon("git-branch", size=20),
                    rx.heading(
                        f"Connections: {InfluenceState.connection_sources_entity_name}",
                        size="5",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            variant="ghost",
                            on_click=InfluenceState.close_connections_modal,
                        )
                    ),
                    width="100%",
                ),
                rx.text(
                    f"Total connections: {InfluenceState.connection_sources_total}",
                    color="gray",
                    size="2",
                ),
                rx.divider(),
                rx.cond(
                    InfluenceState.connection_sources.length() > 0,
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                InfluenceState.connection_sources,
                                lambda conn: rx.card(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(
                                                conn["connected_entity_type"],
                                                variant="soft",
                                                size="1",
                                            ),
                                            rx.text(
                                                conn["connected_entity_name"],
                                                weight="bold",
                                            ),
                                            rx.spacer(),
                                            rx.hstack(
                                                rx.text(
                                                    "Strength:", size="1", color="gray"
                                                ),
                                                rx.text(
                                                    f"{conn['strength']:.2f}",
                                                    size="1",
                                                    weight="medium",
                                                ),
                                                spacing="1",
                                            ),
                                            width="100%",
                                        ),
                                        rx.hstack(
                                            rx.text(
                                                f"Co-occurrences: {conn['co_occurrence_count']}",
                                                size="1",
                                                color="gray",
                                            ),
                                            rx.text(
                                                f"Shared documents: {conn['shared_document_count']}",
                                                size="1",
                                                color="gray",
                                            ),
                                            spacing="4",
                                        ),
                                        spacing="2",
                                        align_items="start",
                                    ),
                                    padding="3",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        max_height="500px",
                    ),
                    rx.callout(
                        "No connections found.",
                        icon="info",
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            max_width="800px",
        ),
        open=InfluenceState.show_connections_modal,
        on_open_change=InfluenceState.on_connections_modal_change,
    )


def influence_page() -> rx.Component:
    """Main Entity Influence Mapping page."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Entity Influence Mapping", size="8"),
                    rx.text(
                        "Analyze power dynamics, central actors, and hidden relationships.",
                        color="gray",
                    ),
                    align_items="start",
                ),
                rx.spacer(),
                # Load or Refresh button based on data state
                rx.cond(
                    InfluenceState.has_data,
                    rx.button(
                        rx.icon("refresh-cw"),
                        "Refresh",
                        on_click=InfluenceState.refresh_influence_data,
                        loading=InfluenceState.is_loading,
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("play"),
                        "Load Influence Data",
                        on_click=InfluenceState.load_influence_data,
                        loading=InfluenceState.is_loading,
                        color_scheme="blue",
                    ),
                ),
                width="100%",
                align_items="end",
            ),
            # Summary stats
            rx.grid(
                stat_card(
                    "Total Entities",
                    InfluenceState.summary_total_entities,
                    "users",
                    "blue",
                ),
                stat_card(
                    "Connections",
                    InfluenceState.summary_total_connections,
                    "git-branch",
                    "green",
                ),
                stat_card(
                    "Communities",
                    InfluenceState.summary_num_communities,
                    "layers",
                    "purple",
                ),
                stat_card(
                    "Most Influential",
                    InfluenceState.summary_most_influential,
                    "crown",
                    "orange",
                ),
                columns="4",
                spacing="4",
                width="100%",
            ),
            # Tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Rankings", value="rankings"),
                    rx.tabs.trigger("Power Dynamics", value="dynamics"),
                    rx.tabs.trigger("Communities", value="communities"),
                ),
                rx.tabs.content(
                    rankings_tab(),
                    value="rankings",
                    padding_top="4",
                ),
                rx.tabs.content(
                    power_dynamics_tab(),
                    value="dynamics",
                    padding_top="4",
                ),
                rx.tabs.content(
                    communities_tab(),
                    value="communities",
                    padding_top="4",
                ),
                default_value="rankings",
                width="100%",
            ),
            # Modals
            entity_detail_modal(),
            mention_sources_modal(),
            connection_sources_modal(),
            padding="2em",
            width="100%",
            align_items="start",
            # Removed on_mount - user must click Load button
        ),
        width="100%",
        height="100vh",
    )
