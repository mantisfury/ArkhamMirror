"""Layout algorithms for graph visualization.

Provides server-side layout calculation for hierarchical, radial, circular,
and bipartite graph layouts. The frontend can use these pre-calculated
positions instead of force simulation.
"""

import logging
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class LayoutType(Enum):
    """Available layout algorithms."""
    FORCE_DIRECTED = "force"
    HIERARCHICAL = "hierarchical"
    RADIAL = "radial"
    CIRCULAR = "circular"
    TREE = "tree"
    BIPARTITE = "bipartite"
    GRID = "grid"


class HierarchicalDirection(Enum):
    """Direction for hierarchical layouts."""
    TOP_TO_BOTTOM = "TB"
    BOTTOM_TO_TOP = "BT"
    LEFT_TO_RIGHT = "LR"
    RIGHT_TO_LEFT = "RL"


@dataclass
class LayoutPosition:
    """Node position from layout calculation."""
    node_id: str
    x: float
    y: float
    layer: int | None = None  # For hierarchical layouts
    angle: float | None = None  # For radial/circular layouts
    column: int | None = None  # For bipartite layouts


@dataclass
class LayoutResult:
    """Result of layout calculation."""
    layout_type: str
    positions: dict[str, LayoutPosition]
    width: float
    height: float
    layers: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "layout_type": self.layout_type,
            "positions": {
                node_id: {
                    "x": pos.x,
                    "y": pos.y,
                    "layer": pos.layer,
                    "angle": pos.angle,
                    "column": pos.column,
                }
                for node_id, pos in self.positions.items()
            },
            "width": self.width,
            "height": self.height,
            "layers": self.layers,
            "metadata": self.metadata,
        }


class LayoutEngine:
    """
    Calculate node positions using various graph layout algorithms.

    All layouts return positions normalized to a canvas coordinate system.
    The frontend can scale these to fit the actual viewport.
    """

    def __init__(self):
        """Initialize layout engine."""
        pass

    def calculate_layout(
        self,
        graph: Graph,
        layout_type: LayoutType,
        options: dict[str, Any] | None = None,
    ) -> LayoutResult:
        """
        Calculate positions for all nodes using specified layout.

        Args:
            graph: Graph to layout
            layout_type: Algorithm to use
            options: Algorithm-specific options

        Returns:
            LayoutResult with positions for all nodes
        """
        options = options or {}

        if layout_type == LayoutType.HIERARCHICAL:
            return self.hierarchical_layout(
                graph,
                root_node_id=options.get("root_node_id"),
                direction=HierarchicalDirection(options.get("direction", "TB")),
                layer_spacing=options.get("layer_spacing", 100),
                node_spacing=options.get("node_spacing", 50),
            )
        elif layout_type == LayoutType.RADIAL:
            return self.radial_layout(
                graph,
                center_node_id=options.get("center_node_id"),
                radius_step=options.get("radius_step", 100),
            )
        elif layout_type == LayoutType.CIRCULAR:
            return self.circular_layout(
                graph,
                radius=options.get("radius", 300),
                start_angle=options.get("start_angle", 0),
            )
        elif layout_type == LayoutType.TREE:
            return self.tree_layout(
                graph,
                root_node_id=options.get("root_node_id"),
                direction=HierarchicalDirection(options.get("direction", "TB")),
                level_spacing=options.get("level_spacing", 80),
                sibling_spacing=options.get("sibling_spacing", 40),
            )
        elif layout_type == LayoutType.BIPARTITE:
            return self.bipartite_layout(
                graph,
                left_types=options.get("left_types", ["document"]),
                right_types=options.get("right_types", ["person", "organization", "location"]),
                spacing=options.get("spacing", 300),
            )
        elif layout_type == LayoutType.GRID:
            return self.grid_layout(
                graph,
                columns=options.get("columns"),
                cell_width=options.get("cell_width", 100),
                cell_height=options.get("cell_height", 100),
            )
        else:
            # Force-directed is handled by frontend
            raise ValueError(f"Layout type {layout_type} should be handled by frontend")

    def hierarchical_layout(
        self,
        graph: Graph,
        root_node_id: str | None = None,
        direction: HierarchicalDirection = HierarchicalDirection.TOP_TO_BOTTOM,
        layer_spacing: float = 100,
        node_spacing: float = 50,
    ) -> LayoutResult:
        """
        Sugiyama-style hierarchical layout.

        Assigns nodes to layers based on distance from root,
        then positions nodes within each layer.

        Args:
            graph: Graph to layout
            root_node_id: Root node (auto-detected if None)
            direction: Layout direction
            layer_spacing: Vertical spacing between layers
            node_spacing: Horizontal spacing between nodes

        Returns:
            LayoutResult with hierarchical positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="hierarchical",
                positions={},
                width=0,
                height=0,
                layers=0,
            )

        # Build adjacency
        adjacency = self._build_adjacency(graph.edges)

        # Find root if not specified
        if not root_node_id:
            root_node_id = self._find_best_root(graph.nodes, adjacency)

        # Assign layers using BFS from root
        layers = self._assign_layers_bfs(root_node_id, graph.nodes, adjacency)

        # Group nodes by layer
        layer_nodes: dict[int, list[str]] = defaultdict(list)
        for node_id, layer in layers.items():
            layer_nodes[layer].append(node_id)

        # Sort nodes within each layer to minimize edge crossings
        for layer_idx in layer_nodes:
            layer_nodes[layer_idx] = self._sort_layer_by_barycenter(
                layer_nodes[layer_idx],
                layer_nodes.get(layer_idx - 1, []),
                adjacency,
            )

        # Calculate positions
        positions = {}
        num_layers = max(layers.values()) + 1 if layers else 0
        max_width = 0

        for layer_idx, nodes_in_layer in layer_nodes.items():
            layer_width = len(nodes_in_layer) * node_spacing
            max_width = max(max_width, layer_width)
            start_x = -layer_width / 2 + node_spacing / 2

            for i, node_id in enumerate(nodes_in_layer):
                x = start_x + i * node_spacing
                y = layer_idx * layer_spacing

                # Adjust for direction
                if direction == HierarchicalDirection.BOTTOM_TO_TOP:
                    y = (num_layers - 1 - layer_idx) * layer_spacing
                elif direction == HierarchicalDirection.LEFT_TO_RIGHT:
                    x, y = y, x
                elif direction == HierarchicalDirection.RIGHT_TO_LEFT:
                    x, y = (num_layers - 1 - layer_idx) * layer_spacing, x

                positions[node_id] = LayoutPosition(
                    node_id=node_id,
                    x=x,
                    y=y,
                    layer=layer_idx,
                )

        # Calculate dimensions
        if direction in [HierarchicalDirection.TOP_TO_BOTTOM, HierarchicalDirection.BOTTOM_TO_TOP]:
            width = max_width
            height = num_layers * layer_spacing
        else:
            width = num_layers * layer_spacing
            height = max_width

        return LayoutResult(
            layout_type="hierarchical",
            positions=positions,
            width=width,
            height=height,
            layers=num_layers,
            metadata={
                "root_node_id": root_node_id,
                "direction": direction.value,
            },
        )

    def radial_layout(
        self,
        graph: Graph,
        center_node_id: str | None = None,
        radius_step: float = 100,
    ) -> LayoutResult:
        """
        Radial layout centered on a node.

        Places center node at origin, with connected nodes in
        concentric circles based on distance.

        Args:
            graph: Graph to layout
            center_node_id: Center node (auto-detected if None)
            radius_step: Radius increment per layer

        Returns:
            LayoutResult with radial positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="radial",
                positions={},
                width=0,
                height=0,
            )

        adjacency = self._build_adjacency(graph.edges)

        # Find center if not specified (use highest degree)
        if not center_node_id:
            center_node_id = self._find_best_root(graph.nodes, adjacency)

        # Assign layers using BFS
        layers = self._assign_layers_bfs(center_node_id, graph.nodes, adjacency)

        # Group nodes by layer
        layer_nodes: dict[int, list[str]] = defaultdict(list)
        for node_id, layer in layers.items():
            layer_nodes[layer].append(node_id)

        # Calculate positions
        positions = {}
        max_radius = 0

        for layer_idx, nodes_in_layer in layer_nodes.items():
            if layer_idx == 0:
                # Center node
                positions[center_node_id] = LayoutPosition(
                    node_id=center_node_id,
                    x=0,
                    y=0,
                    layer=0,
                    angle=0,
                )
            else:
                radius = layer_idx * radius_step
                max_radius = radius
                angle_step = 2 * math.pi / len(nodes_in_layer) if nodes_in_layer else 0

                for i, node_id in enumerate(nodes_in_layer):
                    angle = i * angle_step
                    x = radius * math.cos(angle)
                    y = radius * math.sin(angle)

                    positions[node_id] = LayoutPosition(
                        node_id=node_id,
                        x=x,
                        y=y,
                        layer=layer_idx,
                        angle=angle,
                    )

        diameter = max_radius * 2 + radius_step

        return LayoutResult(
            layout_type="radial",
            positions=positions,
            width=diameter,
            height=diameter,
            layers=max(layers.values()) + 1 if layers else 0,
            metadata={
                "center_node_id": center_node_id,
            },
        )

    def circular_layout(
        self,
        graph: Graph,
        radius: float = 300,
        start_angle: float = 0,
    ) -> LayoutResult:
        """
        Circular layout - all nodes on a circle.

        Nodes are ordered to minimize edge crossings.

        Args:
            graph: Graph to layout
            radius: Circle radius
            start_angle: Starting angle in radians

        Returns:
            LayoutResult with circular positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="circular",
                positions={},
                width=0,
                height=0,
            )

        # Sort nodes to minimize crossings (simple degree-based ordering)
        sorted_nodes = sorted(
            graph.nodes,
            key=lambda n: n.degree,
            reverse=True,
        )

        positions = {}
        n = len(sorted_nodes)
        angle_step = 2 * math.pi / n if n > 0 else 0

        for i, node in enumerate(sorted_nodes):
            angle = start_angle + i * angle_step
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            positions[node.id] = LayoutPosition(
                node_id=node.id,
                x=x,
                y=y,
                angle=angle,
            )

        diameter = radius * 2

        return LayoutResult(
            layout_type="circular",
            positions=positions,
            width=diameter,
            height=diameter,
        )

    def tree_layout(
        self,
        graph: Graph,
        root_node_id: str | None = None,
        direction: HierarchicalDirection = HierarchicalDirection.TOP_TO_BOTTOM,
        level_spacing: float = 80,
        sibling_spacing: float = 40,
    ) -> LayoutResult:
        """
        Reingold-Tilford tree layout.

        Best for tree-structured graphs. Falls back to hierarchical
        for graphs with cycles.

        Args:
            graph: Graph to layout
            root_node_id: Root node (auto-detected if None)
            direction: Layout direction
            level_spacing: Spacing between tree levels
            sibling_spacing: Spacing between siblings

        Returns:
            LayoutResult with tree positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="tree",
                positions={},
                width=0,
                height=0,
            )

        adjacency = self._build_adjacency(graph.edges)

        # Find root if not specified
        if not root_node_id:
            root_node_id = self._find_best_root(graph.nodes, adjacency)

        # Build tree structure using BFS (ignores cycles)
        children: dict[str, list[str]] = defaultdict(list)
        visited = {root_node_id}
        queue = deque([root_node_id])
        parent: dict[str, str | None] = {root_node_id: None}
        levels: dict[str, int] = {root_node_id: 0}

        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    children[node].append(neighbor)
                    parent[neighbor] = node
                    levels[neighbor] = levels[node] + 1
                    queue.append(neighbor)

        # Assign positions using modified Reingold-Tilford
        positions: dict[str, tuple[float, float, int]] = {}
        x_offset = [0]  # Mutable counter for x position

        def layout_subtree(node_id: str, depth: int) -> tuple[float, float]:
            """Layout subtree and return (min_x, max_x) bounds."""
            node_children = children.get(node_id, [])

            if not node_children:
                # Leaf node
                x = x_offset[0]
                x_offset[0] += sibling_spacing
                positions[node_id] = (x, depth * level_spacing, depth)
                return x, x

            # Layout children first
            child_bounds = []
            for child in node_children:
                bounds = layout_subtree(child, depth + 1)
                child_bounds.append(bounds)

            # Position this node centered over children
            min_x = child_bounds[0][0]
            max_x = child_bounds[-1][1]
            x = (min_x + max_x) / 2
            positions[node_id] = (x, depth * level_spacing, depth)

            return min_x, max_x

        layout_subtree(root_node_id, 0)

        # Convert to LayoutPosition objects and adjust for direction
        final_positions = {}
        max_x = max(p[0] for p in positions.values()) if positions else 0
        max_y = max(p[1] for p in positions.values()) if positions else 0

        for node_id, (x, y, depth) in positions.items():
            # Adjust for direction
            if direction == HierarchicalDirection.BOTTOM_TO_TOP:
                y = max_y - y
            elif direction == HierarchicalDirection.LEFT_TO_RIGHT:
                x, y = y, x
            elif direction == HierarchicalDirection.RIGHT_TO_LEFT:
                x, y = max_y - y, x

            final_positions[node_id] = LayoutPosition(
                node_id=node_id,
                x=x,
                y=y,
                layer=depth,
            )

        # Calculate dimensions
        if direction in [HierarchicalDirection.TOP_TO_BOTTOM, HierarchicalDirection.BOTTOM_TO_TOP]:
            width = max_x + sibling_spacing
            height = max_y + level_spacing
        else:
            width = max_y + level_spacing
            height = max_x + sibling_spacing

        return LayoutResult(
            layout_type="tree",
            positions=final_positions,
            width=width,
            height=height,
            layers=max(levels.values()) + 1 if levels else 0,
            metadata={
                "root_node_id": root_node_id,
                "direction": direction.value,
            },
        )

    def bipartite_layout(
        self,
        graph: Graph,
        left_types: list[str],
        right_types: list[str],
        spacing: float = 300,
        vertical_spacing: float = 50,
    ) -> LayoutResult:
        """
        Two-column bipartite layout.

        Places nodes in two columns based on entity type.

        Args:
            graph: Graph to layout
            left_types: Entity types for left column
            right_types: Entity types for right column
            spacing: Horizontal spacing between columns
            vertical_spacing: Vertical spacing between nodes

        Returns:
            LayoutResult with bipartite positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="bipartite",
                positions={},
                width=0,
                height=0,
            )

        # Partition nodes
        left_nodes = [n for n in graph.nodes if n.entity_type in left_types]
        right_nodes = [n for n in graph.nodes if n.entity_type in right_types]
        other_nodes = [n for n in graph.nodes
                       if n.entity_type not in left_types and n.entity_type not in right_types]

        # Sort by degree within each column
        left_nodes.sort(key=lambda n: n.degree, reverse=True)
        right_nodes.sort(key=lambda n: n.degree, reverse=True)

        positions = {}

        # Left column
        left_height = len(left_nodes) * vertical_spacing
        for i, node in enumerate(left_nodes):
            y = i * vertical_spacing - left_height / 2
            positions[node.id] = LayoutPosition(
                node_id=node.id,
                x=-spacing / 2,
                y=y,
                column=0,
            )

        # Right column
        right_height = len(right_nodes) * vertical_spacing
        for i, node in enumerate(right_nodes):
            y = i * vertical_spacing - right_height / 2
            positions[node.id] = LayoutPosition(
                node_id=node.id,
                x=spacing / 2,
                y=y,
                column=1,
            )

        # Other nodes in center
        other_height = len(other_nodes) * vertical_spacing
        for i, node in enumerate(other_nodes):
            y = i * vertical_spacing - other_height / 2
            positions[node.id] = LayoutPosition(
                node_id=node.id,
                x=0,
                y=y,
                column=2,
            )

        max_height = max(left_height, right_height, other_height)

        return LayoutResult(
            layout_type="bipartite",
            positions=positions,
            width=spacing,
            height=max_height,
            metadata={
                "left_types": left_types,
                "right_types": right_types,
                "left_count": len(left_nodes),
                "right_count": len(right_nodes),
                "other_count": len(other_nodes),
            },
        )

    def grid_layout(
        self,
        graph: Graph,
        columns: int | None = None,
        cell_width: float = 100,
        cell_height: float = 100,
    ) -> LayoutResult:
        """
        Simple grid layout.

        Arranges nodes in a grid, sorted by degree.

        Args:
            graph: Graph to layout
            columns: Number of columns (auto-calculated if None)
            cell_width: Width of each cell
            cell_height: Height of each cell

        Returns:
            LayoutResult with grid positions
        """
        if not graph.nodes:
            return LayoutResult(
                layout_type="grid",
                positions={},
                width=0,
                height=0,
            )

        n = len(graph.nodes)

        # Auto-calculate columns for roughly square grid
        if columns is None:
            columns = max(1, int(math.ceil(math.sqrt(n))))

        rows = math.ceil(n / columns)

        # Sort by degree
        sorted_nodes = sorted(graph.nodes, key=lambda node: node.degree, reverse=True)

        positions = {}
        for i, node in enumerate(sorted_nodes):
            row = i // columns
            col = i % columns
            x = col * cell_width
            y = row * cell_height

            positions[node.id] = LayoutPosition(
                node_id=node.id,
                x=x,
                y=y,
            )

        return LayoutResult(
            layout_type="grid",
            positions=positions,
            width=columns * cell_width,
            height=rows * cell_height,
            metadata={
                "columns": columns,
                "rows": rows,
            },
        )

    # --- Helper Methods ---

    def _build_adjacency(self, edges: list[GraphEdge]) -> dict[str, list[str]]:
        """Build undirected adjacency list."""
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            adjacency[edge.source].append(edge.target)
            adjacency[edge.target].append(edge.source)
        return adjacency

    def _find_best_root(
        self,
        nodes: list[GraphNode],
        adjacency: dict[str, list[str]],
    ) -> str:
        """Find best root node (highest degree or first node)."""
        if not nodes:
            raise ValueError("Cannot find root in empty graph")

        # Use node with highest degree
        best_node = max(nodes, key=lambda n: len(adjacency.get(n.id, [])))
        return best_node.id

    def _assign_layers_bfs(
        self,
        root_id: str,
        nodes: list[GraphNode],
        adjacency: dict[str, list[str]],
    ) -> dict[str, int]:
        """Assign layer numbers using BFS from root."""
        layers = {root_id: 0}
        queue = deque([root_id])
        node_ids = {n.id for n in nodes}

        while queue:
            current = queue.popleft()
            current_layer = layers[current]

            for neighbor in adjacency.get(current, []):
                if neighbor not in layers and neighbor in node_ids:
                    layers[neighbor] = current_layer + 1
                    queue.append(neighbor)

        # Handle disconnected nodes
        max_layer = max(layers.values()) if layers else 0
        for node in nodes:
            if node.id not in layers:
                layers[node.id] = max_layer + 1

        return layers

    def _sort_layer_by_barycenter(
        self,
        layer_nodes: list[str],
        previous_layer_nodes: list[str],
        adjacency: dict[str, list[str]],
    ) -> list[str]:
        """
        Sort nodes in a layer by barycenter method.

        Positions each node based on average position of its
        neighbors in the previous layer.
        """
        if not previous_layer_nodes:
            return layer_nodes

        # Create position map for previous layer
        prev_positions = {node_id: i for i, node_id in enumerate(previous_layer_nodes)}

        def barycenter(node_id: str) -> float:
            neighbors = adjacency.get(node_id, [])
            prev_neighbors = [n for n in neighbors if n in prev_positions]
            if not prev_neighbors:
                return float('inf')
            return sum(prev_positions[n] for n in prev_neighbors) / len(prev_neighbors)

        return sorted(layer_nodes, key=barycenter)
