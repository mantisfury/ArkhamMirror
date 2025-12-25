import reflex as rx
from ..state.visualization_state import VisualizationState
from ..components.layout import layout


def cluster_map_view():
    return rx.vstack(
        # Controls row - always visible
        rx.hstack(
            rx.button(
                rx.icon(tag="refresh_cw", size=14),
                "Run Clustering",
                on_click=VisualizationState.run_clustering,
                loading=VisualizationState.is_loading,
                color_scheme="blue",
                size="2",
                variant="soft",
            ),
            rx.cond(
                VisualizationState.error_message != "",
                rx.text(VisualizationState.error_message, color="blue", font_size="sm"),
            ),
            spacing="4",
            align="center",
        ),
        # Graph or empty state
        rx.box(
            rx.cond(
                VisualizationState.cluster_map_data,
                rx.plotly(data=VisualizationState.cluster_map_figure),
                rx.center(
                    rx.vstack(
                        rx.icon(tag="layers", size=40, color="gray"),
                        rx.text("No cluster data available.", color="gray"),
                        rx.text(
                            "Click 'Run Clustering' to group documents by semantic similarity.",
                            color="gray.8",
                            font_size="sm",
                        ),
                        spacing="4",
                        align="center",
                    ),
                    height="100%",
                ),
            ),
            width="100%",
            height="550px",
        ),
        width="100%",
        spacing="4",
    )


def wordcloud_view():
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon(tag="refresh_cw", size=14),
                "Generate",
                on_click=VisualizationState.load_wordcloud,
                loading=VisualizationState.is_loading,
                color_scheme="blue",
                size="2",
            ),
            rx.select(
                ["all", "cluster", "doctype"],
                value=VisualizationState.wordcloud_scope,
                on_change=VisualizationState.set_wordcloud_scope,
                placeholder="Scope",
            ),
            rx.cond(
                VisualizationState.wordcloud_scope == "cluster",
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.foreach(
                            VisualizationState.cluster_select_items,
                            lambda item: rx.select.item(
                                item[1],
                                value=item[0],
                            ),
                        ),
                    ),
                    placeholder="Select Cluster",
                    on_change=VisualizationState.set_wordcloud_filter,
                ),
            ),
            rx.cond(
                VisualizationState.wordcloud_scope == "doctype",
                rx.select(
                    VisualizationState.available_doctypes,
                    placeholder="Select Type",
                    on_change=VisualizationState.set_wordcloud_filter,
                ),
            ),
            spacing="4",
        ),
        # Exclusions section
        rx.box(
            rx.text("Excluded Words:", weight="bold", size="2"),
            rx.hstack(
                rx.input(
                    placeholder="Add word to exclude...",
                    value=VisualizationState.new_exclusion_word,
                    on_change=VisualizationState.set_new_exclusion_word,
                    size="2",
                    width="200px",
                ),
                rx.button(
                    rx.icon(tag="plus", size=14),
                    "Add",
                    on_click=VisualizationState.add_exclusion,
                    size="2",
                    variant="soft",
                ),
                spacing="2",
            ),
            rx.cond(
                VisualizationState.wordcloud_exclusions.length() > 0,
                rx.hstack(
                    rx.foreach(
                        VisualizationState.wordcloud_exclusions,
                        lambda word: rx.badge(
                            word,
                            rx.icon(
                                tag="x",
                                size=12,
                                cursor="pointer",
                                on_click=lambda: VisualizationState.remove_exclusion(
                                    word
                                ),
                            ),
                            color_scheme="gray",
                            size="2",
                        ),
                    ),
                    wrap="wrap",
                    spacing="2",
                ),
                rx.text(
                    "No custom exclusions. Default artifacts (page, start, end...) are already filtered.",
                    color="gray",
                    font_size="xs",
                ),
            ),
            padding="3",
            border="1px solid var(--gray-6)",
            border_radius="md",
            width="100%",
        ),
        rx.cond(
            VisualizationState.is_loading,
            rx.center(rx.spinner(), padding="8"),
            rx.cond(
                VisualizationState.wordcloud_image,
                rx.image(
                    src=f"data:image/png;base64,{VisualizationState.wordcloud_image}",
                    width="100%",
                    height="auto",
                    object_fit="contain",
                    style={"border_radius": "8px"},
                ),
                rx.center(
                    rx.vstack(
                        rx.icon(tag="cloud", size=40, color="gray"),
                        rx.text("No word cloud generated yet.", color="gray"),
                        rx.text(
                            "Click 'Generate' to create a word cloud from your documents.",
                            color="gray.8",
                            font_size="sm",
                        ),
                        spacing="4",
                        align="center",
                    ),
                    padding="8",
                ),
            ),
        ),
        width="100%",
        spacing="4",
    )


def heatmap_view():
    return rx.vstack(
        rx.hstack(
            rx.text("Top Entities:"),
            rx.slider(
                min=5,
                max=30,
                default_value=15,
                on_value_commit=VisualizationState.set_heatmap_top_n,
                width="200px",
            ),
            rx.text(VisualizationState.heatmap_top_n),
            spacing="4",
            align_items="center",
        ),
        rx.cond(
            VisualizationState.heatmap_labels.length() > 0,
            rx.plotly(data=VisualizationState.heatmap_figure),
            rx.center(rx.text("No entity relationships found.", color="gray")),
        ),
        width="100%",
        height="700px",
    )


def visualizations_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Visual Intelligence", size="8"),
                    rx.text(
                        "Explore your data through semantic clusters, word clouds, and entity relationships.",
                        color="gray",
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                # Load or Refresh button based on data state
                rx.cond(
                    VisualizationState.has_data,
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Refresh",
                        on_click=VisualizationState.refresh_heatmap,
                        loading=VisualizationState.is_loading,
                        variant="soft",
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Load Visualizations",
                        on_click=VisualizationState.load_heatmap,
                        loading=VisualizationState.is_loading,
                        color_scheme="blue",
                    ),
                ),
                width="100%",
                align="end",
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Cluster Map", value="Cluster Map"),
                    rx.tabs.trigger("Word Clouds", value="Word Clouds"),
                    rx.tabs.trigger("Entity Heatmap", value="Entity Heatmap"),
                ),
                rx.tabs.content(cluster_map_view(), value="Cluster Map"),
                rx.tabs.content(wordcloud_view(), value="Word Clouds"),
                rx.tabs.content(heatmap_view(), value="Entity Heatmap"),
                default_value="Cluster Map",
                on_change=VisualizationState.set_view_mode,
                width="100%",
            ),
            spacing="6",
            width="100%",
            # Removed on_mount - user must click Load button
        )
    )
