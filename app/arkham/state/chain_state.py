"""
Chain State - State management for Contradiction Chain visualization.
"""

import reflex as rx
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import plotly.graph_objects as go
import logging
import textwrap

logger = logging.getLogger(__name__)


def wrap_text(text: str, width: int = 60) -> str:
    """Insert <br> tags to wrap text at specified width."""
    if not text:
        return ""
    return "<br>".join(textwrap.wrap(text, width=width))


# Pydantic models for chain visualization
class ChainPoint(BaseModel):
    id: str
    contradiction_id: int
    entity_name: str
    entity_id: Optional[int] = None
    claim_text: str
    source_doc: str
    document_id: int
    x_position: Any  # float for sequence, ISO string for time
    x_sequence: int
    confidence: float
    severity: str
    status: str
    category: str = "factual"  # For category-based shapes


class ChainConnection(BaseModel):
    from_point_id: str
    to_point_id: str
    contradiction_id: int
    confidence: float


class SelectableEntity(BaseModel):
    id: int
    name: str
    label: str
    mentions: int


# Models for Lie Web visualization
class WebNode(BaseModel):
    """Node representing a contradiction in the force-directed graph."""

    id: str
    contradiction_id: int
    description: str
    entity_name: str
    entity_id: Optional[int] = None
    severity: str
    confidence: float
    category: str
    status: str
    connected_entity_ids: List[int] = []


class WebEdge(BaseModel):
    """Edge connecting two contradictions that share an entity."""

    from_id: str
    to_id: str
    shared_entity_id: int
    strength: float


class WebEntity(BaseModel):
    """Entity for the Lie Web legend."""

    id: int
    name: str
    color: str


# Color and shape mappings
SEVERITY_COLORS = {
    "High": "#ef4444",  # Red
    "Medium": "#f97316",  # Orange
    "Low": "#9ca3af",  # Gray
}

STATUS_SYMBOLS = {
    "Open": "circle",
    "Resolved": "diamond",
    "False Positive": "x",
    "Escalated": "square",
}

# Shape mapping for contradiction categories
CATEGORY_SHAPES = {
    "timeline": "circle",
    "financial": "diamond",
    "location": "square",
    "identity": "star",
    "factual": "circle",
    "procedural": "triangle-up",
    "quantitative": "hexagon",
}


class ChainState(rx.State):
    """State for the Contradiction Chain visualization."""

    # Data
    points: List[ChainPoint] = []
    connections: List[ChainConnection] = []
    available_entities: List[SelectableEntity] = []
    entity_names: List[str] = []  # Sorted for swimlanes
    total_count: int = 0

    # Applied filters (used by chart) - only change on "Apply Settings"
    min_confidence: float = 0.0
    high_only: bool = False
    selected_entity_ids: List[int] = []
    limit: int = 50
    sort_by: str = "mentions"  # mentions, alpha, contradictions
    x_axis_mode: str = "sequence"  # time, sequence
    group_by_severity: bool = False  # Collapse swimlanes into severity levels

    # Pending filters (modified by UI controls) - don't trigger chart updates
    pending_min_confidence: float = 0.0
    pending_high_only: bool = False
    pending_selected_entity_ids: List[int] = []
    pending_limit: int = 50
    pending_sort_by: str = "mentions"
    pending_x_axis_mode: str = "sequence"
    pending_group_by_severity: bool = False

    # Interaction state
    is_loading: bool = False
    hovered_contradiction_id: Optional[int] = None
    selected_point_id: Optional[str] = None

    # For modal
    selected_contradiction_id: Optional[int] = None

    # === NEW: Visualization Mode Support ===
    visualization_mode: str = "conspiracy"  # "conspiracy", "web", "timeline"
    focused_entity_id: Optional[int] = None  # For "Focus" feature in Lie Web
    focused_entity_name: str = ""  # Display name for focused entity
    time_range: str = "all"  # "all", "last_week", "last_month", "last_year"

    # Web visualization data
    web_nodes: List[WebNode] = []
    web_edges: List[WebEdge] = []
    web_entities: List[WebEntity] = []

    # UI state
    controls_collapsed: bool = False

    def toggle_controls(self):
        """Toggle the controls panel visibility."""
        self.controls_collapsed = not self.controls_collapsed

    @rx.var
    def limit_display(self) -> str:
        """Display value for limit dropdown (from pending state)."""
        if self.pending_limit >= 1000:
            return "All"
        return str(self.pending_limit)

    @rx.var
    def showing_count(self) -> str:
        """Display showing X of Y."""
        return (
            f"Showing {len(self.points)} points from {self.total_count} contradictions"
        )

    @rx.var
    def has_data(self) -> bool:
        """Check if we have chain data."""
        return len(self.points) > 0

    @rx.var
    def chart_min_width(self) -> str:
        """Dynamic min-width for chart container based on points."""
        num_points = len(self.points) if self.points else 1
        width_px = max(1200, num_points * 50)
        return f"{width_px}px"

    @rx.var
    def chain_figure(self) -> go.Figure:
        """Build the Plotly figure for the chain visualization."""
        fig = go.Figure()

        if not self.points or not self.entity_names:
            # Empty figure
            fig.update_layout(
                title="No data to display",
                height=200,
            )
            return fig

        # Create point lookup for connections
        point_lookup = {p.id: p for p in self.points}

        # Build entity color lookup from web_entities
        entity_colors = {e.id: e.color for e in self.web_entities}

        # Determine swimlane categories based on grouping mode
        if self.group_by_severity:
            swimlane_categories = ["High", "Medium", "Low"]

            def get_swimlane(p):
                return p.severity
        else:
            swimlane_categories = self.entity_names

            def get_swimlane(p):
                return p.entity_name

        # Add connection lines first (so they're behind points)
        for conn in self.connections:
            p1 = point_lookup.get(conn.from_point_id)
            p2 = point_lookup.get(conn.to_point_id)
            if not p1 or not p2:
                continue

            # Check if this connection should be highlighted
            is_highlighted = (
                self.hovered_contradiction_id is not None
                and conn.contradiction_id == self.hovered_contradiction_id
            )

            # Get swimlane positions for connection
            y1 = get_swimlane(p1)
            y2 = get_swimlane(p2)

            fig.add_trace(
                go.Scatter(
                    x=[p1.x_position, p2.x_position],
                    y=[y1, y2],
                    mode="lines",
                    line=dict(
                        color="rgba(255, 0, 0, 0.8)"
                        if is_highlighted
                        else "rgba(255, 0, 0, 0.3)",
                        width=4 if is_highlighted else 2,
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        # Group points by swimlane category
        for category in swimlane_categories:
            if self.group_by_severity:
                category_points = [p for p in self.points if p.severity == category]
            else:
                category_points = [p for p in self.points if p.entity_name == category]

            if not category_points:
                continue

            # Determine if any point should be highlighted
            sizes = []
            for p in category_points:
                if (
                    self.hovered_contradiction_id is not None
                    and p.contradiction_id == self.hovered_contradiction_id
                ):
                    sizes.append(28)  # Highlighted size (larger)
                else:
                    sizes.append(20)  # Normal size (larger for visibility)

            fig.add_trace(
                go.Scatter(
                    x=[p.x_position for p in category_points],
                    y=[get_swimlane(p) for p in category_points],
                    mode="markers",
                    marker=dict(
                        size=sizes,
                        color=[
                            SEVERITY_COLORS.get(p.severity, "#9ca3af")
                            for p in category_points
                        ],
                        symbol=[
                            CATEGORY_SHAPES.get(p.category, "circle")
                            for p in category_points
                        ],
                        line=dict(
                            width=3,
                            color=[
                                entity_colors.get(p.entity_id, "#ffffff")
                                for p in category_points
                            ],
                        ),
                    ),
                    text=[
                        wrap_text(
                            p.claim_text[:300]
                            + ("..." if len(p.claim_text) > 300 else "")
                        )
                        for p in category_points
                    ],
                    customdata=[
                        [
                            p.id,
                            p.source_doc,
                            p.contradiction_id,
                            p.confidence,
                            p.entity_name,
                            p.category,
                            p.severity,
                        ]
                        for p in category_points
                    ],
                    hovertemplate="<b>%{text}</b><br><br>Entity: %{customdata[4]}<br>Category: %{customdata[5]}<br>Severity: %{customdata[6]}<br>Source: %{customdata[1]}<br>Strength: %{customdata[3]:.0%}<extra></extra>",
                    showlegend=False,
                    name=category,
                )
            )

        # Layout - Make chart LARGE
        # Height: Based on number of swimlanes
        num_swimlanes = len(swimlane_categories)
        chart_height = max(400, num_swimlanes * 150 + 100)

        # Width: 50px per point, minimum 1200px for readability
        # This ensures points are spread out horizontally
        num_points = len(self.points) if self.points else 1
        chart_width = max(1200, num_points * 50)

        # Configure x-axis based on mode
        if self.x_axis_mode == "time":
            xaxis_config = dict(
                title="Time",
                type="date",  # Plotly will parse ISO strings as dates
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
                autorange=True,  # Auto-fit to show all data
                rangemode="tozero",
            )
        else:
            xaxis_config = dict(
                title="Sequence",
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
                tickmode="linear",
                dtick=10,  # Tick every 10 units
            )

        fig.update_layout(
            height=chart_height,
            width=chart_width,
            margin=dict(l=150, r=50, t=40, b=60),  # More left margin for entity names
            xaxis=xaxis_config,
            yaxis=dict(
                title="Severity" if self.group_by_severity else "",
                categoryorder="array",
                categoryarray=list(reversed(swimlane_categories)),  # Top to bottom
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
            ),
            # Enable click events (no selection to avoid highlight/deselect issue)
            clickmode="event",
            dragmode="pan",
            # Show modebar with export options
            modebar=dict(
                orientation="v",
                bgcolor="rgba(0,0,0,0.1)",
            ),
        )

        # Enable download button in modebar
        fig.update_layout(
            updatemenus=[],
        )

        return fig

    @rx.var
    def web_figure(self) -> go.Figure:
        """Build force-directed web visualization using NetworkX spring layout."""
        import networkx as nx

        if not self.web_nodes:
            fig = go.Figure()
            fig.update_layout(
                title="No data - Apply settings to load",
                height=600,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        # Build NetworkX graph
        G = nx.Graph()
        for node in self.web_nodes:
            G.add_node(node.id)
        for edge in self.web_edges:
            G.add_edge(edge.from_id, edge.to_id, weight=edge.strength)

        # Compute layout - spring layout for force-directed effect
        # Use seed for reproducibility
        if len(G.nodes()) > 0:
            pos = nx.spring_layout(G, k=0.8, iterations=50, seed=42)
        else:
            pos = {}

        # Build entity color lookup from web_entities
        entity_colors = {e.id: e.color for e in self.web_entities}

        # Build edge traces (draw first, behind nodes)
        edge_traces = []
        for edge in self.web_edges:
            if edge.from_id in pos and edge.to_id in pos:
                x0, y0 = pos[edge.from_id]
                x1, y1 = pos[edge.to_id]
                # Single trace per edge for thickness based on strength
                edge_traces.append(
                    go.Scatter(
                        x=[x0, x1, None],
                        y=[y0, y1, None],
                        mode="lines",
                        line=dict(
                            width=1 + (edge.strength * 4),  # thickness by confidence
                            color="rgba(255, 0, 0, 0.4)",
                        ),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

        # Build node trace
        node_x = [pos[n.id][0] for n in self.web_nodes if n.id in pos]
        node_y = [pos[n.id][1] for n in self.web_nodes if n.id in pos]
        node_colors = [
            SEVERITY_COLORS.get(n.severity, "#9ca3af")
            for n in self.web_nodes
            if n.id in pos
        ]
        node_sizes = [12 + (n.confidence * 15) for n in self.web_nodes if n.id in pos]
        node_symbols = [
            CATEGORY_SHAPES.get(n.category, "circle")
            for n in self.web_nodes
            if n.id in pos
        ]
        node_outlines = [
            entity_colors.get(n.entity_id, "#ffffff")
            for n in self.web_nodes
            if n.id in pos
        ]

        # Hover text
        hover_text = [
            f"<b>{wrap_text(n.description[:300] + ('...' if len(n.description) > 300 else ''))}</b><br><br>"
            f"Entity: {n.entity_name}<br>"
            f"Category: {n.category}<br>"
            f"Severity: {n.severity}<br>"
            f"Status: {n.status}<br>"
            f"Strength: {n.confidence:.0%}"
            for n in self.web_nodes
            if n.id in pos
        ]

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            marker=dict(
                size=node_sizes,
                color=node_colors,
                symbol=node_symbols,
                line=dict(width=3, color=node_outlines),  # entity color outline
            ),
            text=hover_text,
            customdata=[
                [n.id, n.entity_id, n.contradiction_id]
                for n in self.web_nodes
                if n.id in pos
            ],
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )

        # Combine all traces
        fig = go.Figure(data=edge_traces + [node_trace])

        # Dynamic size based on node count
        num_nodes = len(self.web_nodes)
        chart_width = max(1000, num_nodes * 40)
        chart_height = max(700, num_nodes * 30)

        fig.update_layout(
            showlegend=False,
            hovermode="closest",
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=20, b=20),
            width=chart_width,
            height=chart_height,
            clickmode="event",  # No selection to avoid highlight/deselect issue
            dragmode="pan",
        )

        return fig

    @rx.var
    def timeline_figure(self) -> go.Figure:
        """Build vertical swimlane timeline visualization."""
        from collections import defaultdict

        if not self.points or not self.entity_names:
            fig = go.Figure()
            fig.update_layout(
                title="No data - Apply settings to load",
                height=600,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        # Create point lookup for connections
        point_lookup = {p.id: p for p in self.points}

        # Build entity color lookup from web_entities
        entity_colors = {e.id: e.color for e in self.web_entities}

        # Group claims by entity
        entity_claims = defaultdict(list)
        # Note: "No Date" lane could be added in future for undated claims

        for point in self.points:
            # Check if we have a real date (x_position is ISO string in time mode)
            if self.x_axis_mode == "time" and isinstance(point.x_position, str):
                entity_claims[point.entity_name].append(point)
            else:
                # Sequence mode or synthetic dates - group by entity
                entity_claims[point.entity_name].append(point)

        fig = go.Figure()

        # Add trace per entity
        for entity_name in self.entity_names:
            claims = entity_claims.get(entity_name, [])
            if not claims:
                continue

            fig.add_trace(
                go.Scatter(
                    x=[c.x_position for c in claims],
                    y=[entity_name] * len(claims),
                    mode="markers",
                    name=entity_name,
                    marker=dict(
                        size=18,
                        color=[
                            SEVERITY_COLORS.get(c.severity, "#9ca3af") for c in claims
                        ],
                        symbol=[
                            CATEGORY_SHAPES.get(c.category, "circle") for c in claims
                        ],
                        line=dict(
                            width=3,
                            color=[
                                entity_colors.get(c.entity_id, "#ffffff")
                                for c in claims
                            ],
                        ),
                    ),
                    text=[
                        wrap_text(
                            c.claim_text[:300]
                            + ("..." if len(c.claim_text) > 300 else "")
                        )
                        for c in claims
                    ],
                    customdata=[
                        [
                            c.id,
                            c.source_doc,
                            c.contradiction_id,
                            c.confidence,
                            c.entity_name,
                            c.category,
                            c.severity,
                        ]
                        for c in claims
                    ],
                    hovertemplate="<b>%{text}</b><br><br>Entity: %{customdata[4]}<br>Category: %{customdata[5]}<br>Severity: %{customdata[6]}<br>Source: %{customdata[1]}<br>Date: %{x}<br>Strength: %{customdata[3]:.0%}<extra></extra>",
                    showlegend=False,
                )
            )

        # Add red dashed lines for contradictions
        for conn in self.connections:
            p1 = point_lookup.get(conn.from_point_id)
            p2 = point_lookup.get(conn.to_point_id)
            if p1 and p2:
                fig.add_shape(
                    type="line",
                    x0=p1.x_position,
                    x1=p2.x_position,
                    y0=p1.entity_name,
                    y1=p2.entity_name,
                    line=dict(color="red", width=2, dash="dot"),
                )

        # Configure x-axis based on mode
        if self.x_axis_mode == "time":
            xaxis_config = dict(
                title="Time",
                type="date",
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
            )
        else:
            xaxis_config = dict(
                title="Sequence",
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
            )

        # Height based on number of entities
        chart_height = max(400, len(self.entity_names) * 60 + 100)

        # Width: 50px per point, minimum 1200px for readability (same as conspiracy chart)
        num_points = len(self.points) if self.points else 1
        chart_width = max(1200, num_points * 50)

        fig.update_layout(
            xaxis=xaxis_config,
            yaxis=dict(
                title="",
                categoryorder="array",
                categoryarray=list(reversed(self.entity_names)),
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.2)",
            ),
            showlegend=False,
            height=chart_height,
            width=chart_width,
            margin=dict(l=200, r=50, t=40, b=60),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(bgcolor="white", font_size=12),
            clickmode="event",  # No selection to avoid highlight/deselect issue
            dragmode="pan",
        )

        return fig

    def load_chain_data(self):
        """Load chain visualization data from service."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.chain_service import get_chain_service

            service = get_chain_service()

            # Apply pending settings to actual state
            self.min_confidence = self.pending_min_confidence
            self.high_only = self.pending_high_only
            self.selected_entity_ids = self.pending_selected_entity_ids
            self.limit = self.pending_limit
            self.sort_by = self.pending_sort_by
            self.x_axis_mode = self.pending_x_axis_mode
            self.group_by_severity = self.pending_group_by_severity

            # Apply high_only filter to severity
            severity_filter = ["High"] if self.high_only else None

            # Get data
            data = service.get_chain_data(
                min_confidence=self.min_confidence,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
                severity_filter=severity_filter,
                limit=self.limit,
                sort_by=self.sort_by,
                x_axis_mode=self.x_axis_mode,
            )

            self.points = [ChainPoint(**p) for p in data["points"]]
            self.connections = [ChainConnection(**c) for c in data["connections"]]
            self.entity_names = data["entities"]
            self.total_count = data["total_count"]

            # Also load web data for Lie Web mode
            web_data = service.get_web_data(
                min_confidence=self.min_confidence,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
                focused_entity_id=self.focused_entity_id,
                limit=self.limit,
            )
            self.web_nodes = [
                WebNode(
                    id=n["id"],
                    contradiction_id=n["contradiction_id"],
                    description=n["description"],
                    entity_name=n["entity_name"],
                    entity_id=n["entity_id"],
                    severity=n["severity"],
                    confidence=n["confidence"],
                    category=n["category"],
                    status=n["status"],
                    connected_entity_ids=n["connected_entity_ids"],
                )
                for n in web_data["nodes"]
            ]
            self.web_edges = [
                WebEdge(
                    from_id=e["from"],
                    to_id=e["to"],
                    shared_entity_id=e["shared_entity_id"],
                    strength=e["strength"],
                )
                for e in web_data["edges"]
            ]
            self.web_entities = [
                WebEntity(
                    id=ent["id"],
                    name=ent["name"],
                    color=ent["color"],
                )
                for ent in web_data["entities"]
            ]

        except Exception as e:
            logger.error(f"Error loading chain data: {e}", exc_info=True)
        finally:
            self.is_loading = False

    def load_filter_options(self):
        """Load available entities for filtering."""
        try:
            from app.arkham.services.chain_service import get_chain_service

            service = get_chain_service()
            entities = service.get_available_entities_for_chain()
            logger.debug(f"Loaded {len(entities)} entities for filter")
            for e in entities[:10]:  # Log first 10
                logger.debug(
                    f"  Entity: {e['name']} (id={e['id']}, mentions={e['mentions']})"
                )
            self.available_entities = [SelectableEntity(**e) for e in entities]
        except Exception as e:
            logger.error(f"Error loading filter options: {e}")

    def set_visualization_mode(self, mode: str | list[str]):
        """Switch visualization mode: conspiracy, web, or timeline."""
        # Handle both single value and list (from segmented_control)
        if isinstance(mode, list):
            self.visualization_mode = mode[0] if mode else "conspiracy"
        else:
            self.visualization_mode = mode

    def focus_entity(self, entity_id: int):
        """Focus view on specific entity's lies and connections.

        Sets the focused_entity_id which will filter the web data
        to show only contradictions involving this entity + 1 hop.
        """
        # Find entity name for display
        for entity in self.web_entities:
            if entity.id == entity_id:
                self.focused_entity_name = entity.name
                break
        else:
            self.focused_entity_name = "Unknown"

        self.focused_entity_id = entity_id
        # Reload data with focus filter
        return ChainState.load_chain_data

    def clear_focus(self):
        """Return to full view (clear entity focus)."""
        self.focused_entity_id = None
        self.focused_entity_name = ""
        return ChainState.load_chain_data

    def set_min_confidence(self, value: float):
        """Set minimum confidence filter (pending)."""
        self.pending_min_confidence = value

    def set_min_confidence_dropdown(self, value: str):
        """Set minimum confidence from dropdown (e.g., '50%' -> 0.5)."""
        # Parse the percentage string
        self.pending_min_confidence = int(value.replace("%", "")) / 100

    def toggle_high_only(self, checked: bool):
        """Toggle high severity only filter (pending)."""
        self.pending_high_only = checked

    def toggle_entity(self, entity_id: int):
        """Toggle entity selection (pending). Max 10 entities."""
        if entity_id in self.pending_selected_entity_ids:
            # Always allow deselection
            self.pending_selected_entity_ids = [
                e for e in self.pending_selected_entity_ids if e != entity_id
            ]
        else:
            # Limit to 10 selections
            if len(self.pending_selected_entity_ids) < 10:
                self.pending_selected_entity_ids = self.pending_selected_entity_ids + [
                    entity_id
                ]
            else:
                logger.warning("Maximum 10 entities can be selected for the chart")

    def set_sort_by(self, value: str):
        """Set entity sort order (pending)."""
        self.pending_sort_by = value

    def set_x_axis_mode(self, value: str):
        """Set x-axis mode (pending)."""
        self.pending_x_axis_mode = value

    def toggle_group_by_severity(self, checked: bool):
        """Toggle severity grouping (pending)."""
        self.pending_group_by_severity = checked

    def set_limit(self, value: str):
        """Set result limit (pending)."""
        if value == "All":
            self.pending_limit = 1000
        else:
            self.pending_limit = int(value)

    def zoom_to_high_confidence(self):
        """Quick action: set high confidence filter and apply."""
        self.pending_min_confidence = 0.7
        self.pending_high_only = True
        return ChainState.load_chain_data

    def reset_filters(self):
        """Reset all filters to defaults and apply."""
        self.pending_min_confidence = 0.0
        self.pending_high_only = False
        self.pending_selected_entity_ids = []
        self.pending_limit = 50
        self.pending_sort_by = "mentions"
        self.pending_x_axis_mode = "sequence"
        self.pending_group_by_severity = False
        return ChainState.load_chain_data

    def select_point_by_id(self, point_id: str) -> bool:
        """Select a point and load its contradiction details.

        Works across all visualization modes:
        - conspiracy/timeline: searches self.points
        - web: searches self.web_nodes

        Returns True if point was found, False otherwise.
        """
        logger.debug(f"select_point_by_id called with: {point_id}")
        logger.debug(f"Visualization mode: {self.visualization_mode}")
        logger.debug(
            f"Total points: {len(self.points)}, Total web_nodes: {len(self.web_nodes)}"
        )

        # First try points (conspiracy/timeline mode)
        for p in self.points:
            if p.id == point_id:
                logger.debug(
                    f"Found matching point: {p.id}, contradiction_id: {p.contradiction_id}"
                )
                self.selected_point_id = point_id
                self.selected_contradiction_id = p.contradiction_id
                self._load_contradiction_detail(p.contradiction_id)
                logger.debug(
                    f"After load - selected_contradiction_id: {self.selected_contradiction_id}"
                )
                return True

        # If not found in points, try web_nodes (web mode)
        for n in self.web_nodes:
            if n.id == point_id:
                logger.debug(
                    f"Found matching web_node: {n.id}, contradiction_id: {n.contradiction_id}"
                )
                self.selected_point_id = point_id
                self.selected_contradiction_id = n.contradiction_id
                self._load_contradiction_detail(n.contradiction_id)
                logger.debug(
                    f"After load - selected_contradiction_id: {self.selected_contradiction_id}"
                )
                return True

        logger.debug(f"No matching point found for id: {point_id}")
        return False

    def _load_contradiction_detail(self, contradiction_id: int):
        """Load contradiction details for modal display."""
        try:
            from app.arkham.services.contradiction_service import (
                get_contradiction_service,
            )

            service = get_contradiction_service()
            data = service.get_contradictions(limit=100)

            for item in data:
                if item["id"] == contradiction_id:
                    self.selected_contradiction_detail = item
                    break
        except Exception as e:
            logger.error(f"Error loading contradiction detail: {e}")

    # Store full contradiction detail for modal
    selected_contradiction_detail: Dict = {}

    @rx.var
    def has_modal_open(self) -> bool:
        """Check if modal should be open."""
        # Check both the ID and the detail dict for robustness
        has_id = self.selected_contradiction_id is not None
        has_detail = bool(self.selected_contradiction_detail)
        result = has_id or has_detail
        logger.debug(
            f"has_modal_open: id={self.selected_contradiction_id}, has_detail={has_detail}, result={result}"
        )
        return result

    @rx.var
    def modal_entity_name(self) -> str:
        """Get entity name for modal."""
        return self.selected_contradiction_detail.get("entity_name", "Unknown")

    @rx.var
    def modal_description(self) -> str:
        """Get description for modal."""
        return self.selected_contradiction_detail.get("description", "")

    @rx.var
    def modal_severity(self) -> str:
        """Get severity for modal."""
        return self.selected_contradiction_detail.get("severity", "Medium")

    @rx.var
    def modal_status(self) -> str:
        """Get status for modal."""
        return self.selected_contradiction_detail.get("status", "Open")

    @rx.var
    def modal_evidence(self) -> List[Dict]:
        """Get evidence for modal."""
        return self.selected_contradiction_detail.get("evidence", [])

    def set_hovered_contradiction(self, contradiction_id: Optional[int]):
        """Set which contradiction is being hovered for highlighting."""
        self.hovered_contradiction_id = contradiction_id

    def clear_hover(self):
        """Clear hover state."""
        self.hovered_contradiction_id = None

    def on_plotly_click(self, points: List):
        """Handle Plotly click event - open contradiction detail modal.

        Reflex Plotly sends a list of Point objects on click.
        Each Point has: x, y, customdata, etc.
        """
        logger.debug(f"Plotly click - received {len(points) if points else 0} points")

        if not points:
            return

        # Get the first clicked point - it's a dict!
        point = points[0]

        # Debug - log all keys if it's a dict
        logger.debug(f"Point type: {type(point)}")
        if isinstance(point, dict):
            logger.debug(f"Point keys: {list(point.keys())}")
            logger.debug(f"Point values: {point}")

        # Access as dict (Point is actually a dict in Reflex)
        if isinstance(point, dict):
            x_val = point.get("x")
            y_val = point.get("y")
            customdata = point.get("customdata", [])
        else:
            x_val = getattr(point, "x", None)
            y_val = getattr(point, "y", None)
            customdata = getattr(point, "customdata", [])

        logger.debug(f"x={x_val}, y={y_val}, customdata={customdata}")

        if customdata and len(customdata) >= 1:
            point_id = customdata[0]
            logger.debug(f"Selected point from customdata: {point_id}")

            # Try to find the point by ID first
            found = self.select_point_by_id(point_id)

            # If not found and we have contradiction_id in customdata[2], use it directly
            # (This handles web nodes which have format [node_id, entity_id, contradiction_id])
            if not found and len(customdata) >= 3:
                contradiction_id = customdata[2]
                logger.debug(
                    f"Using contradiction_id from customdata: {contradiction_id}"
                )
                if contradiction_id:
                    self.selected_contradiction_id = contradiction_id
                    self._load_contradiction_detail(contradiction_id)
        elif x_val is not None and y_val is not None:
            # Fallback: find point by x,y coordinates
            logger.debug(f"Fallback - finding point by x={x_val}, y={y_val}")

            # First try web_nodes (for lie web mode where customdata may be empty)
            if self.visualization_mode == "web" and self.web_nodes:
                import networkx as nx

                # Rebuild the layout to get positions
                G = nx.Graph()
                for node in self.web_nodes:
                    G.add_node(node.id)
                if len(G.nodes()) > 0:
                    pos = nx.spring_layout(G, k=0.8, iterations=50, seed=42)
                    # Find closest node by position
                    min_dist = float("inf")
                    closest_node = None
                    for n in self.web_nodes:
                        if n.id in pos:
                            nx_pos, ny_pos = pos[n.id]
                            dist = (float(x_val) - nx_pos) ** 2 + (
                                float(y_val) - ny_pos
                            ) ** 2
                            if dist < min_dist:
                                min_dist = dist
                                closest_node = n
                    if closest_node and min_dist < 0.1:  # Close enough
                        logger.debug(
                            f"Found closest web node: {closest_node.id}, contradiction_id: {closest_node.contradiction_id}"
                        )
                        self.selected_contradiction_id = closest_node.contradiction_id
                        self._load_contradiction_detail(closest_node.contradiction_id)
                        return

            # Standard points fallback for conspiracy/timeline
            for p in self.points:
                # Check x coordinate - handle both float and string (time mode)
                try:
                    if isinstance(p.x_position, str):
                        # Time mode: compare strings directly
                        x_match = str(p.x_position) == str(x_val)
                    else:
                        # Sequence mode: compare floats with tolerance
                        x_match = abs(float(p.x_position) - float(x_val)) < 0.5
                except (ValueError, TypeError):
                    x_match = False

                if x_match:
                    # Check y coordinate (entity name or severity)
                    swimlane = p.severity if self.group_by_severity else p.entity_name
                    if str(swimlane) == str(y_val):
                        logger.debug(f"Found point by coordinates: {p.id}")
                        self.select_point_by_id(p.id)
                        return
            logger.debug("No matching point found by coordinates")
        else:
            logger.debug("No valid x,y or customdata - cannot identify point")

    def on_point_click(self, point_data: Dict):
        """Handle click on a point - open contradiction detail."""
        # point_data comes from Plotly click event
        if point_data and "customdata" in point_data:
            customdata = point_data["customdata"]
            if len(customdata) >= 3:
                point_id = customdata[0]
                self.select_point_by_id(point_id)

    def clear_selection(self):
        """Clear selected contradiction."""
        self.selected_contradiction_id = None
        self.selected_point_id = None
        self.selected_contradiction_detail = {}

    def on_modal_close(self, is_open: bool):
        """Handle modal close."""
        if not is_open:
            self.clear_selection()

    # Keyboard navigation
    _current_point_index: int = -1

    def navigate_next(self):
        """Navigate to next point (J or Down arrow)."""
        if not self.points:
            return
        self._current_point_index = (self._current_point_index + 1) % len(self.points)
        point = self.points[self._current_point_index]
        self.hovered_contradiction_id = point.contradiction_id

    def navigate_prev(self):
        """Navigate to previous point (K or Up arrow)."""
        if not self.points:
            return
        self._current_point_index = (self._current_point_index - 1) % len(self.points)
        point = self.points[self._current_point_index]
        self.hovered_contradiction_id = point.contradiction_id

    def open_current(self):
        """Open modal for current point (Enter)."""
        if self._current_point_index >= 0 and self._current_point_index < len(
            self.points
        ):
            point = self.points[self._current_point_index]
            self.select_point_by_id(point.id)

    def toggle_high_filter(self):
        """Toggle high only filter (H key)."""
        self.high_only = not self.high_only
        return ChainState.load_chain_data
