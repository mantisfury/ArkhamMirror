"""State for the graph explorer with integrated settings."""

import reflex as rx
from typing import List, Dict, Any, Optional
import plotly.graph_objects as go
import json
import networkx as nx
import asyncio

from .graph_settings_state import GraphSettingsState


class GraphState(GraphSettingsState):
    """
    State for the graph explorer.

    Inherits from GraphSettingsState to have direct access to settings
    variables in computed vars and event handlers.
    """

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    selected_node_id: Optional[str] = None
    error_message: str = ""

    # Loading state
    is_loading: bool = False

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    # Plotly figure (cached, computed in background)
    graph_figure: go.Figure = go.Figure()

    @rx.var
    def has_data(self) -> bool:
        """Check if graph data has been loaded."""
        return len(self.nodes) > 0

    def _compute_graph_figure(self) -> go.Figure:
        """Internal method to compute Plotly figure for network graph."""
        if not self.nodes or not self.edges:
            return go.Figure()

        # Build NetworkX graph for layout
        G = nx.Graph()
        for node in self.nodes:
            G.add_node(node["id"], **node)
        for edge in self.edges:
            G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1))

        # Compute layout positions based on settings (from inherited GraphSettingsState)
        if self.layout_algorithm == "spring":
            pos = nx.spring_layout(G, k=self.spring_k, iterations=50)
        elif self.layout_algorithm == "circular":
            pos = nx.circular_layout(G)
        else:
            pos = nx.kamada_kawai_layout(G)

        # Create edge traces with configurable opacity
        edge_color = f"rgba(136,136,136,{self.edge_opacity})"
        edge_trace = go.Scatter(
            x=[],
            y=[],
            line=dict(width=0.5, color=edge_color),
            hoverinfo="none",
            mode="lines",
        )

        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace["x"] += (x0, x1, None)
            edge_trace["y"] += (y0, y1, None)

        # Create node traces with dynamic sizing and labels
        node_x = []
        node_y = []
        node_text = []
        node_hover = []
        node_color = []
        node_size = []

        # Calculate degree for label visibility
        degrees = dict(G.degree())
        if degrees:
            sorted_degrees = sorted(degrees.values(), reverse=True)
            threshold_idx = max(1, len(sorted_degrees) * self.label_percent // 100)
            degree_threshold = sorted_degrees[
                min(threshold_idx - 1, len(sorted_degrees) - 1)
            ]
        else:
            degree_threshold = 0

        # Normalize node sizes
        mentions = [n.get("total_mentions", n.get("size", 1)) for n in self.nodes]
        min_m = min(mentions) if mentions else 1
        max_m = max(mentions) if mentions else 1
        mention_range = max_m - min_m if max_m > min_m else 1

        for node_id in G.nodes():
            x, y = pos[node_id]
            node_x.append(x)
            node_y.append(y)
            node_data = G.nodes[node_id]

            # Get node properties
            label = node_data.get("label", str(node_id))
            node_type = node_data.get("type", "unknown")
            node_mentions = node_data.get("total_mentions", node_data.get("size", 1))
            node_degree = degrees.get(node_id, 0)

            # Hover text always shows full info
            node_hover.append(
                f"{label}<br>Type: {node_type}<br>Mentions: {node_mentions}<br>Connections: {node_degree}"
            )

            # Label visibility based on mode (from inherited settings)
            if self.label_visibility_mode == "all":
                node_text.append(label)
            elif self.label_visibility_mode == "none":
                node_text.append("")
            else:  # top_percent
                if node_degree >= degree_threshold:
                    node_text.append(label)
                else:
                    node_text.append("")

            node_color.append(node_data.get("group", 0))

            # Normalize size to [node_size_min, node_size_max]
            normalized_size = (node_mentions - min_m) / mention_range
            size = self.node_size_min + normalized_size * (
                self.node_size_max - self.node_size_min
            )
            node_size.append(size)

        # Determine mode based on settings
        mode = "markers+text" if self.show_labels else "markers"

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode=mode,
            text=node_text,
            hovertext=node_hover,
            textposition="top center",
            hoverinfo="text",
            marker=dict(
                showscale=True,
                colorscale="Viridis",
                color=node_color,
                size=node_size,
                colorbar=dict(
                    thickness=15,
                    title=dict(text="Community", side="right"),
                    xanchor="left",
                ),
                line_width=2,
            ),
        )

        # Create figure
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=dict(text="Entity Relationship Graph", font=dict(size=16)),
                showlegend=False,
                hovermode="closest",
                margin=dict(b=0, l=0, r=0, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=700,
            ),
        )

        return fig

    @rx.event(background=True)
    async def load_graph(self):
        """Load graph data from service using current settings."""
        # Skip if already loaded (session cache)
        if self._has_loaded and self.nodes:
            return

        async with self:
            self.is_loading = True
            self.error_message = ""

        try:
            from ..services.graph_service import get_filtered_entity_graph

            # Use settings from inherited GraphSettingsState
            # get_filtered_entity_graph is synchronous, run in thread
            graph_data = await asyncio.to_thread(
                get_filtered_entity_graph,
                min_strength=self.min_edge_strength,
                min_degree=self.min_degree,
                max_doc_ratio=self.max_doc_ratio,
                exclude_types=self.exclude_entity_types,
                hide_singletons=self.hide_singletons,
            )

            async with self:
                self.nodes = graph_data["nodes"]
                self.edges = graph_data["edges"]
                self._has_loaded = True  # Mark as loaded for session cache

                if not self.nodes:
                    self.error_message = "No entities found after filtering. Try adjusting settings or process documents with entity extraction enabled."

            # Compute figure in background thread to avoid lock warning
            fig = await asyncio.to_thread(self._compute_graph_figure)

            async with self:
                self.graph_figure = fig
                self.is_loading = False
        except Exception as e:
            import logging

            logging.error(f"Error loading graph: {e}")

            async with self:
                self.error_message = f"Error loading graph: {str(e)}"
                self.is_loading = False

    def refresh_graph(self):
        """Force reload graph, clearing cache."""
        self._has_loaded = False
        return GraphState.load_graph

    def handle_node_click(self, node_data: Dict[str, Any]):
        """Handle click on a graph node."""
        if isinstance(node_data, dict) and "id" in node_data:
            self.selected_node_id = node_data["id"]
        elif isinstance(node_data, str):
            self.selected_node_id = node_data

    async def export_graph_csv(self):
        """Export graph data to CSV (nodes and edges)."""
        if not self.nodes:
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_warning("No graph data to export")
            return

        try:
            import csv
            from datetime import datetime
            import os

            # Create exports directory if it doesn't exist
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Export nodes
            nodes_filename = f"{export_dir}/graph_nodes_{timestamp}.csv"
            with open(nodes_filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Label", "Type", "Size", "Group/Community"])

                for node in self.nodes:
                    writer.writerow(
                        [
                            node.get("id", ""),
                            node.get("label", ""),
                            node.get("type", ""),
                            node.get("size", ""),
                            node.get("group", ""),
                        ]
                    )

            # Export edges
            edges_filename = f"{export_dir}/graph_edges_{timestamp}.csv"
            with open(edges_filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Source", "Target", "Weight", "Relationship Type"])

                for edge in self.edges:
                    writer.writerow(
                        [
                            edge.get("source", ""),
                            edge.get("target", ""),
                            edge.get("weight", ""),
                            edge.get("type", ""),
                        ]
                    )

            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_success(
                f"Graph exported to {nodes_filename} and {edges_filename}"
            )

        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="permission"
                if "permission" in str(e).lower()
                else "default",
                context={
                    "action": "export_graph_csv",
                    "nodes": len(self.nodes),
                    "edges": len(self.edges),
                },
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))

    async def export_graph_json(self):
        """Export graph data to JSON format."""
        if not self.nodes:
            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_warning("No graph data to export")
            return

        try:
            from datetime import datetime
            import os

            # Create exports directory if it doesn't exist
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{export_dir}/graph_{timestamp}.json"

            # Export complete graph structure with settings
            graph_data = {
                "nodes": self.nodes,
                "edges": self.edges,
                "metadata": {
                    "node_count": len(self.nodes),
                    "edge_count": len(self.edges),
                    "exported_at": timestamp,
                    "settings": {
                        "layout_algorithm": self.layout_algorithm,
                        "min_edge_strength": self.min_edge_strength,
                        "min_degree": self.min_degree,
                        "exclude_types": self.exclude_entity_types,
                    },
                },
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)

            from ..state.toast_state import ToastState

            toast_state = await self.get_state(ToastState)
            toast_state.show_success(f"Graph exported to {filename}")

        except Exception as e:
            from ..utils.error_handler import handle_file_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_file_error(
                e,
                error_type="permission"
                if "permission" in str(e).lower()
                else "default",
                context={
                    "action": "export_graph_json",
                    "nodes": len(self.nodes),
                    "edges": len(self.edges),
                },
            )

            toast_state = await self.get_state(ToastState)
            toast_state.show_error(format_error_for_ui(error_info))
