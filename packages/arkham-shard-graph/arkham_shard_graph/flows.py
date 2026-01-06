"""
Flow analysis for Sankey diagrams.

Extracts flow data from graphs for visualization of resource,
information, or relationship flows between entities.
"""

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

from .models import Graph


@dataclass
class FlowLink:
    """A flow between two nodes."""
    source: str
    target: str
    value: float
    category: str | None = None
    relationship_type: str | None = None


@dataclass
class FlowNode:
    """A node in the flow diagram."""
    id: str
    label: str
    entity_type: str
    layer: int = 0
    value: float = 0.0  # Total flow through this node


@dataclass
class FlowData:
    """Data for Sankey diagram."""
    nodes: list[FlowNode] = field(default_factory=list)
    links: list[FlowLink] = field(default_factory=list)
    total_flow: float = 0.0
    layer_count: int = 0


class FlowAnalyzer:
    """Extract flow data from graphs for Sankey visualization."""

    def extract_entity_flows(
        self,
        graph: Graph,
        source_types: list[str] | None = None,
        target_types: list[str] | None = None,
        intermediate_types: list[str] | None = None,
        relationship_types: list[str] | None = None,
        min_weight: float = 0.0,
    ) -> FlowData:
        """
        Extract flows between entity types.

        Creates a multi-layer Sankey where:
        - Layer 0: Source entities (e.g., persons)
        - Layer 1: Intermediate entities (e.g., organizations)
        - Layer 2: Target entities (e.g., locations)

        Args:
            graph: The graph to analyze
            source_types: Entity types for the left side (layer 0)
            target_types: Entity types for the right side (final layer)
            intermediate_types: Entity types for middle layers
            relationship_types: Filter to specific relationship types
            min_weight: Minimum edge weight to include

        Returns:
            FlowData with nodes and links for Sankey diagram
        """
        if not graph.nodes:
            return FlowData()

        # Default types if not specified
        source_types = [t.lower() for t in (source_types or ["person"])]
        target_types = [t.lower() for t in (target_types or ["organization", "location"])]
        intermediate_types = [t.lower() for t in (intermediate_types or [])]

        # Build node lookup
        node_map = {node.id: node for node in graph.nodes}

        # Categorize nodes by type
        source_nodes = set()
        target_nodes = set()
        intermediate_nodes = set()

        for node in graph.nodes:
            node_type = (node.entity_type or node.type or "unknown").lower()
            if node_type in source_types:
                source_nodes.add(node.id)
            elif node_type in target_types:
                target_nodes.add(node.id)
            elif intermediate_types and node_type in intermediate_types:
                intermediate_nodes.add(node.id)

        # Assign layers
        node_layers: dict[str, int] = {}
        for node_id in source_nodes:
            node_layers[node_id] = 0
        for node_id in intermediate_nodes:
            node_layers[node_id] = 1
        for node_id in target_nodes:
            node_layers[node_id] = 2 if intermediate_nodes else 1

        # Filter edges and create flow links
        flow_links: list[FlowLink] = []
        node_values: dict[str, float] = defaultdict(float)

        for edge in graph.edges:
            # Skip edges below weight threshold
            if edge.weight < min_weight:
                continue

            # Filter by relationship type if specified
            edge_type = edge.relationship_type or edge.type or "related"
            if relationship_types and edge_type.lower() not in [rt.lower() for rt in relationship_types]:
                continue

            source_id = edge.source
            target_id = edge.target

            # Only include edges between relevant node types
            source_layer = node_layers.get(source_id)
            target_layer = node_layers.get(target_id)

            if source_layer is None or target_layer is None:
                continue

            # Ensure flow goes from lower to higher layer
            if source_layer > target_layer:
                source_id, target_id = target_id, source_id
                source_layer, target_layer = target_layer, source_layer

            # Skip self-loops and same-layer connections in strict mode
            if source_layer == target_layer:
                continue

            flow_links.append(FlowLink(
                source=source_id,
                target=target_id,
                value=edge.weight,
                category=edge_type,
                relationship_type=edge_type,
            ))

            # Track flow values for nodes
            node_values[source_id] += edge.weight
            node_values[target_id] += edge.weight

        # Create flow nodes (only include nodes with flows)
        flow_nodes: list[FlowNode] = []
        included_nodes = set()

        for link in flow_links:
            included_nodes.add(link.source)
            included_nodes.add(link.target)

        for node_id in included_nodes:
            node = node_map.get(node_id)
            if node:
                flow_nodes.append(FlowNode(
                    id=node_id,
                    label=node.label or node_id,
                    entity_type=(node.entity_type or node.type or "unknown").lower(),
                    layer=node_layers.get(node_id, 0),
                    value=node_values.get(node_id, 0),
                ))

        # Sort nodes by layer then by value
        flow_nodes.sort(key=lambda n: (n.layer, -n.value))

        total_flow = sum(link.value for link in flow_links)
        layer_count = max((n.layer for n in flow_nodes), default=0) + 1

        return FlowData(
            nodes=flow_nodes,
            links=flow_links,
            total_flow=total_flow,
            layer_count=layer_count,
        )

    def extract_relationship_flows(
        self,
        graph: Graph,
        flow_relationship_types: list[str] | None = None,
        min_weight: float = 0.0,
        aggregate_by_type: bool = True,
    ) -> FlowData:
        """
        Extract flows based on relationship types.

        Creates flows where the relationship type determines the flow category.
        Useful for visualizing information flow, communication patterns, etc.

        Args:
            graph: The graph to analyze
            flow_relationship_types: Relationship types to include
            min_weight: Minimum edge weight
            aggregate_by_type: If True, aggregate flows by entity type pairs

        Returns:
            FlowData for Sankey diagram
        """
        if not graph.nodes:
            return FlowData()

        # Build node lookup
        node_map = {node.id: node for node in graph.nodes}

        # Determine node layers by analyzing edge directions
        # Nodes with more outgoing edges go on left, more incoming on right
        outgoing_count: dict[str, int] = defaultdict(int)
        incoming_count: dict[str, int] = defaultdict(int)

        for edge in graph.edges:
            if flow_relationship_types:
                edge_type = (edge.relationship_type or edge.type or "related").lower()
                if edge_type not in [rt.lower() for rt in flow_relationship_types]:
                    continue
            outgoing_count[edge.source] += 1
            incoming_count[edge.target] += 1

        # Assign layers based on net flow direction
        node_layers: dict[str, int] = {}
        for node in graph.nodes:
            out_flow = outgoing_count.get(node.id, 0)
            in_flow = incoming_count.get(node.id, 0)

            if out_flow > in_flow * 1.5:
                node_layers[node.id] = 0  # Source
            elif in_flow > out_flow * 1.5:
                node_layers[node.id] = 2  # Sink
            else:
                node_layers[node.id] = 1  # Intermediate

        # Create flow links
        flow_links: list[FlowLink] = []
        node_values: dict[str, float] = defaultdict(float)

        if aggregate_by_type:
            # Aggregate by entity type pairs
            type_flows: dict[tuple[str, str, str], float] = defaultdict(float)

            for edge in graph.edges:
                if edge.weight < min_weight:
                    continue

                edge_type = (edge.relationship_type or edge.type or "related").lower()
                if flow_relationship_types and edge_type not in [rt.lower() for rt in flow_relationship_types]:
                    continue

                source_node = node_map.get(edge.source)
                target_node = node_map.get(edge.target)

                if not source_node or not target_node:
                    continue

                source_type = (source_node.entity_type or source_node.type or "unknown").lower()
                target_type = (target_node.entity_type or target_node.type or "unknown").lower()

                key = (source_type, target_type, edge_type)
                type_flows[key] += edge.weight

            # Create aggregated flow nodes and links
            type_node_ids: dict[str, str] = {}

            for (source_type, target_type, rel_type), value in type_flows.items():
                # Create type-based node IDs
                source_id = f"type_{source_type}"
                target_id = f"type_{target_type}"

                type_node_ids[source_type] = source_id
                type_node_ids[target_type] = target_id

                flow_links.append(FlowLink(
                    source=source_id,
                    target=target_id,
                    value=value,
                    category=rel_type,
                    relationship_type=rel_type,
                ))

                node_values[source_id] += value
                node_values[target_id] += value

            # Create type-based flow nodes
            flow_nodes = []
            for entity_type, node_id in type_node_ids.items():
                # Determine layer by flow direction
                out_val = sum(l.value for l in flow_links if l.source == node_id)
                in_val = sum(l.value for l in flow_links if l.target == node_id)

                if out_val > in_val * 1.5:
                    layer = 0
                elif in_val > out_val * 1.5:
                    layer = 2
                else:
                    layer = 1

                flow_nodes.append(FlowNode(
                    id=node_id,
                    label=entity_type.title(),
                    entity_type=entity_type,
                    layer=layer,
                    value=node_values.get(node_id, 0),
                ))
        else:
            # Individual node flows
            for edge in graph.edges:
                if edge.weight < min_weight:
                    continue

                edge_type = (edge.relationship_type or edge.type or "related").lower()
                if flow_relationship_types and edge_type not in [rt.lower() for rt in flow_relationship_types]:
                    continue

                source_layer = node_layers.get(edge.source, 1)
                target_layer = node_layers.get(edge.target, 1)

                # Ensure flow direction
                source_id, target_id = edge.source, edge.target
                if source_layer > target_layer:
                    source_id, target_id = target_id, source_id

                flow_links.append(FlowLink(
                    source=source_id,
                    target=target_id,
                    value=edge.weight,
                    category=edge_type,
                    relationship_type=edge_type,
                ))

                node_values[source_id] += edge.weight
                node_values[target_id] += edge.weight

            # Create flow nodes
            included_nodes = set()
            for link in flow_links:
                included_nodes.add(link.source)
                included_nodes.add(link.target)

            flow_nodes = []
            for node_id in included_nodes:
                node = node_map.get(node_id)
                if node:
                    flow_nodes.append(FlowNode(
                        id=node_id,
                        label=node.label or node_id,
                        entity_type=(node.entity_type or node.type or "unknown").lower(),
                        layer=node_layers.get(node_id, 1),
                        value=node_values.get(node_id, 0),
                    ))

        # Sort and calculate totals
        flow_nodes.sort(key=lambda n: (n.layer, -n.value))
        total_flow = sum(link.value for link in flow_links)
        layer_count = max((n.layer for n in flow_nodes), default=0) + 1

        return FlowData(
            nodes=flow_nodes,
            links=flow_links,
            total_flow=total_flow,
            layer_count=layer_count,
        )

    def aggregate_flows(
        self,
        flow_data: FlowData,
        min_value: float = 0.1,
        max_links: int = 50,
    ) -> FlowData:
        """
        Aggregate small flows into an "Other" category for cleaner visualization.

        Args:
            flow_data: Original flow data
            min_value: Minimum flow value to keep individually
            max_links: Maximum number of links to display

        Returns:
            Aggregated FlowData
        """
        if not flow_data.links:
            return flow_data

        # Sort links by value
        sorted_links = sorted(flow_data.links, key=lambda l: l.value, reverse=True)

        # Keep top links and aggregate the rest
        kept_links: list[FlowLink] = []
        other_by_layer: dict[tuple[int, int], float] = defaultdict(float)

        node_layer_map = {n.id: n.layer for n in flow_data.nodes}

        for i, link in enumerate(sorted_links):
            if i < max_links and link.value >= min_value:
                kept_links.append(link)
            else:
                # Aggregate into "other" flows by layer pair
                source_layer = node_layer_map.get(link.source, 0)
                target_layer = node_layer_map.get(link.target, 1)
                other_by_layer[(source_layer, target_layer)] += link.value

        # Create "Other" nodes and links if needed
        other_nodes: list[FlowNode] = []
        other_links: list[FlowLink] = []

        for (source_layer, target_layer), value in other_by_layer.items():
            if value > 0:
                source_id = f"other_layer_{source_layer}"
                target_id = f"other_layer_{target_layer}"

                # Add other nodes if not already present
                if not any(n.id == source_id for n in other_nodes):
                    other_nodes.append(FlowNode(
                        id=source_id,
                        label="Other",
                        entity_type="other",
                        layer=source_layer,
                        value=value,
                    ))
                if not any(n.id == target_id for n in other_nodes):
                    other_nodes.append(FlowNode(
                        id=target_id,
                        label="Other",
                        entity_type="other",
                        layer=target_layer,
                        value=value,
                    ))

                other_links.append(FlowLink(
                    source=source_id,
                    target=target_id,
                    value=value,
                    category="aggregated",
                ))

        # Combine kept nodes with other nodes
        kept_node_ids = set()
        for link in kept_links:
            kept_node_ids.add(link.source)
            kept_node_ids.add(link.target)

        final_nodes = [n for n in flow_data.nodes if n.id in kept_node_ids]
        final_nodes.extend(other_nodes)
        final_links = kept_links + other_links

        return FlowData(
            nodes=final_nodes,
            links=final_links,
            total_flow=flow_data.total_flow,
            layer_count=flow_data.layer_count,
        )

    def to_dict(self, flow_data: FlowData) -> dict[str, Any]:
        """Convert FlowData to dictionary for JSON serialization."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "entity_type": n.entity_type,
                    "layer": n.layer,
                    "value": n.value,
                }
                for n in flow_data.nodes
            ],
            "links": [
                {
                    "source": l.source,
                    "target": l.target,
                    "value": l.value,
                    "category": l.category,
                    "relationship_type": l.relationship_type,
                }
                for l in flow_data.links
            ],
            "total_flow": flow_data.total_flow,
            "layer_count": flow_data.layer_count,
            "node_count": len(flow_data.nodes),
            "link_count": len(flow_data.links),
        }
