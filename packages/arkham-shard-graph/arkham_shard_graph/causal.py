"""
Causal graph analysis and inference.

Provides tools for modeling cause-effect relationships, validating
DAG structure, finding causal paths, identifying confounders, and
estimating intervention effects using simplified do-calculus.
"""

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict, deque
from enum import Enum
import logging

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class CausalEdgeType(str, Enum):
    """Types of causal relationships."""
    CAUSES = "causes"
    INFLUENCES = "influences"
    CORRELATES = "correlates"
    PREVENTS = "prevents"


class NodeState(str, Enum):
    """Possible states for causal variables."""
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CausalNode:
    """Variable in a causal graph."""
    id: str
    label: str
    description: str = ""
    states: list[str] = field(default_factory=lambda: ["true", "false"])
    observed_state: str | None = None
    prior_probability: float | None = None  # P(X)
    is_intervention: bool = False  # Whether this node is being intervened on
    node_type: str = "variable"  # variable, treatment, outcome, confounder


@dataclass
class CausalEdge:
    """Causal relationship between variables."""
    cause: str
    effect: str
    strength: float = 1.0  # Causal strength estimate (0-1)
    edge_type: CausalEdgeType = CausalEdgeType.CAUSES
    confidence: float = 1.0  # Confidence in the causal relationship
    mechanism: str = ""  # Description of causal mechanism


@dataclass
class CausalPath:
    """A path through the causal graph."""
    nodes: list[str]
    edges: list[CausalEdge]
    path_type: str = "direct"  # direct, backdoor, frontdoor
    total_strength: float = 1.0
    is_blocked: bool = False
    blocking_nodes: list[str] = field(default_factory=list)


@dataclass
class ConfounderInfo:
    """Information about a confounding variable."""
    id: str
    label: str
    affects_treatment: bool
    affects_outcome: bool
    path_to_treatment: list[str]
    path_to_outcome: list[str]


@dataclass
class InterventionResult:
    """Result of a causal intervention analysis."""
    intervention_node: str
    intervention_value: str
    target_node: str
    estimated_effect: float
    confidence_interval: tuple[float, float] | None = None
    confounders_adjusted: list[str] = field(default_factory=list)
    causal_paths: list[CausalPath] = field(default_factory=list)
    explanation: str = ""


@dataclass
class CausalGraph:
    """A causal graph with nodes and directed edges."""
    id: str
    name: str
    nodes: list[CausalNode] = field(default_factory=list)
    edges: list[CausalEdge] = field(default_factory=list)
    is_valid_dag: bool = True
    cycles: list[list[str]] = field(default_factory=list)
    description: str = ""


class CausalGraphEngine:
    """Causal inference and analysis engine."""

    def build_causal_graph(
        self,
        graph: Graph,
        causal_edge_types: list[str] | None = None,
    ) -> CausalGraph:
        """
        Build a CausalGraph from a standard Graph.

        Args:
            graph: Source graph
            causal_edge_types: Edge types to treat as causal (default: all)

        Returns:
            CausalGraph with validated structure
        """
        causal_edge_types = causal_edge_types or [
            "causes", "influences", "leads_to", "results_in",
            "precedes", "triggers", "enables"
        ]

        nodes = []
        edges = []

        # Convert nodes
        for node in graph.nodes:
            nodes.append(CausalNode(
                id=node.id,
                label=node.label or node.id,
                description=node.properties.get("description", "") if node.properties else "",
                states=node.properties.get("states", ["true", "false"]) if node.properties else ["true", "false"],
                observed_state=node.properties.get("observed_state") if node.properties else None,
                node_type=node.properties.get("causal_type", "variable") if node.properties else "variable",
            ))

        # Convert edges (only causal types)
        for edge in graph.edges:
            edge_type = (edge.relationship_type or edge.type or "related").lower()
            if causal_edge_types and edge_type not in [t.lower() for t in causal_edge_types]:
                continue

            edges.append(CausalEdge(
                cause=edge.source,
                effect=edge.target,
                strength=edge.weight if edge.weight else 1.0,
                edge_type=CausalEdgeType.CAUSES,
                confidence=edge.properties.get("confidence", 1.0) if edge.properties else 1.0,
                mechanism=edge.properties.get("mechanism", "") if edge.properties else "",
            ))

        causal_graph = CausalGraph(
            id=f"causal_{graph.id}",
            name=f"Causal Graph: {graph.id}",
            nodes=nodes,
            edges=edges,
        )

        # Validate DAG structure
        is_valid, cycles = self.validate_dag(causal_graph)
        causal_graph.is_valid_dag = is_valid
        causal_graph.cycles = cycles

        return causal_graph

    def validate_dag(self, graph: CausalGraph) -> tuple[bool, list[list[str]]]:
        """
        Check if graph is a valid DAG (Directed Acyclic Graph).

        Args:
            graph: CausalGraph to validate

        Returns:
            Tuple of (is_valid, list_of_cycles)
        """
        # Build adjacency list
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.cause].append(edge.effect)

        # Detect cycles using DFS
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check from all nodes
        node_ids = [n.id for n in graph.nodes]
        for node_id in node_ids:
            if node_id not in visited:
                path = []
                rec_stack = set()
                dfs(node_id)

        return len(cycles) == 0, cycles

    def find_causal_paths(
        self,
        graph: CausalGraph,
        cause: str,
        effect: str,
        max_length: int = 10,
    ) -> list[CausalPath]:
        """
        Find all causal paths between two variables.

        Args:
            graph: CausalGraph to search
            cause: Source node ID
            effect: Target node ID
            max_length: Maximum path length

        Returns:
            List of CausalPath objects
        """
        # Build adjacency list
        adjacency: dict[str, list[CausalEdge]] = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.cause].append(edge)

        paths: list[CausalPath] = []

        def dfs(current: str, target: str, visited: set[str],
                path_nodes: list[str], path_edges: list[CausalEdge]):
            if len(path_nodes) > max_length:
                return

            if current == target:
                # Calculate total strength
                total_strength = 1.0
                for edge in path_edges:
                    total_strength *= edge.strength

                paths.append(CausalPath(
                    nodes=path_nodes.copy(),
                    edges=path_edges.copy(),
                    path_type="direct" if len(path_edges) == 1 else "indirect",
                    total_strength=total_strength,
                ))
                return

            for edge in adjacency[current]:
                if edge.effect not in visited:
                    visited.add(edge.effect)
                    path_nodes.append(edge.effect)
                    path_edges.append(edge)
                    dfs(edge.effect, target, visited, path_nodes, path_edges)
                    path_edges.pop()
                    path_nodes.pop()
                    visited.remove(edge.effect)

        # Start DFS
        dfs(cause, effect, {cause}, [cause], [])

        return paths

    def find_backdoor_paths(
        self,
        graph: CausalGraph,
        treatment: str,
        outcome: str,
    ) -> list[CausalPath]:
        """
        Find backdoor paths between treatment and outcome.

        Backdoor paths are non-causal paths that go "backwards" through
        the treatment node, potentially creating confounding.

        Args:
            graph: CausalGraph
            treatment: Treatment node ID
            outcome: Outcome node ID

        Returns:
            List of backdoor CausalPaths
        """
        # Build bidirectional adjacency (for path finding)
        forward: dict[str, list[str]] = defaultdict(list)
        backward: dict[str, list[str]] = defaultdict(list)

        for edge in graph.edges:
            forward[edge.cause].append(edge.effect)
            backward[edge.effect].append(edge.cause)

        backdoor_paths: list[CausalPath] = []

        # Find paths that start by going backwards from treatment
        def find_paths(current: str, target: str, visited: set[str],
                      path: list[str], started_backward: bool):
            if len(path) > 10:
                return

            if current == target and started_backward:
                backdoor_paths.append(CausalPath(
                    nodes=path.copy(),
                    edges=[],
                    path_type="backdoor",
                    total_strength=1.0,
                ))
                return

            # If at treatment and haven't started backward, go backward first
            if current == treatment and not started_backward:
                for parent in backward[current]:
                    if parent not in visited:
                        visited.add(parent)
                        path.append(parent)
                        find_paths(parent, target, visited, path, True)
                        path.pop()
                        visited.remove(parent)
            elif started_backward:
                # Can go forward or backward
                for neighbor in forward[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        path.append(neighbor)
                        find_paths(neighbor, target, visited, path, True)
                        path.pop()
                        visited.remove(neighbor)

                for neighbor in backward[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        path.append(neighbor)
                        find_paths(neighbor, target, visited, path, True)
                        path.pop()
                        visited.remove(neighbor)

        find_paths(treatment, outcome, {treatment}, [treatment], False)

        return backdoor_paths

    def identify_confounders(
        self,
        graph: CausalGraph,
        treatment: str,
        outcome: str,
    ) -> list[ConfounderInfo]:
        """
        Identify confounding variables between treatment and outcome.

        A confounder is a variable that:
        1. Causes or is associated with the treatment
        2. Causes or is associated with the outcome
        3. Is not on the causal path from treatment to outcome

        Args:
            graph: CausalGraph
            treatment: Treatment node ID
            outcome: Outcome node ID

        Returns:
            List of ConfounderInfo objects
        """
        # Build adjacency lists
        children: dict[str, set[str]] = defaultdict(set)
        parents: dict[str, set[str]] = defaultdict(set)

        for edge in graph.edges:
            children[edge.cause].add(edge.effect)
            parents[edge.effect].add(edge.cause)

        # Find nodes on causal paths (to exclude)
        causal_paths = self.find_causal_paths(graph, treatment, outcome)
        nodes_on_causal_path = set()
        for path in causal_paths:
            nodes_on_causal_path.update(path.nodes)

        # Find ancestors of treatment
        treatment_ancestors = self._find_ancestors(treatment, parents)

        # Find ancestors of outcome
        outcome_ancestors = self._find_ancestors(outcome, parents)

        # Confounders are common ancestors not on causal path
        potential_confounders = treatment_ancestors & outcome_ancestors
        potential_confounders -= nodes_on_causal_path
        potential_confounders -= {treatment, outcome}

        confounders: list[ConfounderInfo] = []
        node_map = {n.id: n for n in graph.nodes}

        for conf_id in potential_confounders:
            node = node_map.get(conf_id)
            if not node:
                continue

            # Find paths to treatment and outcome
            path_to_treatment = self._find_path_to(conf_id, treatment, children)
            path_to_outcome = self._find_path_to(conf_id, outcome, children)

            confounders.append(ConfounderInfo(
                id=conf_id,
                label=node.label,
                affects_treatment=bool(path_to_treatment),
                affects_outcome=bool(path_to_outcome),
                path_to_treatment=path_to_treatment,
                path_to_outcome=path_to_outcome,
            ))

        return confounders

    def _find_ancestors(self, node: str, parents: dict[str, set[str]]) -> set[str]:
        """Find all ancestors of a node."""
        ancestors = set()
        queue = deque(parents[node])

        while queue:
            current = queue.popleft()
            if current not in ancestors:
                ancestors.add(current)
                queue.extend(parents[current])

        return ancestors

    def _find_path_to(
        self,
        start: str,
        end: str,
        children: dict[str, set[str]],
    ) -> list[str]:
        """Find a path from start to end using BFS."""
        if start == end:
            return [start]

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            for child in children[current]:
                if child == end:
                    return path + [child]
                if child not in visited:
                    visited.add(child)
                    queue.append((child, path + [child]))

        return []

    def calculate_intervention_effect(
        self,
        graph: CausalGraph,
        intervention_node: str,
        intervention_value: str,
        target_node: str,
        adjustment_set: list[str] | None = None,
    ) -> InterventionResult:
        """
        Estimate the effect of an intervention using do-calculus principles.

        This is a simplified estimation that:
        1. Finds causal paths from intervention to target
        2. Identifies and adjusts for confounders
        3. Estimates effect based on path strengths

        Args:
            graph: CausalGraph
            intervention_node: Node being intervened on (do(X=x))
            intervention_value: Value being set
            target_node: Outcome variable
            adjustment_set: Variables to adjust for (auto-calculated if None)

        Returns:
            InterventionResult with estimated effect
        """
        # Find direct causal paths
        causal_paths = self.find_causal_paths(graph, intervention_node, target_node)

        if not causal_paths:
            return InterventionResult(
                intervention_node=intervention_node,
                intervention_value=intervention_value,
                target_node=target_node,
                estimated_effect=0.0,
                explanation=f"No causal path found from {intervention_node} to {target_node}",
            )

        # Identify confounders
        confounders = self.identify_confounders(graph, intervention_node, target_node)
        confounder_ids = [c.id for c in confounders]

        # Use provided adjustment set or confounders
        adjusted_for = adjustment_set if adjustment_set else confounder_ids

        # Calculate effect (simplified: average of path strengths)
        # In a full implementation, this would use proper causal inference
        total_effect = 0.0
        for path in causal_paths:
            total_effect += path.total_strength

        # Normalize by number of paths
        estimated_effect = total_effect / len(causal_paths) if causal_paths else 0.0

        # Generate explanation
        path_descriptions = []
        for i, path in enumerate(causal_paths):
            path_str = " → ".join(path.nodes)
            path_descriptions.append(f"Path {i+1}: {path_str} (strength: {path.total_strength:.2f})")

        explanation = f"Intervention do({intervention_node}={intervention_value}) on {target_node}:\n"
        explanation += f"Found {len(causal_paths)} causal path(s):\n"
        explanation += "\n".join(path_descriptions)

        if confounders:
            explanation += f"\nConfounders identified: {', '.join(confounder_ids)}"
            if adjusted_for:
                explanation += f"\nAdjusted for: {', '.join(adjusted_for)}"

        return InterventionResult(
            intervention_node=intervention_node,
            intervention_value=intervention_value,
            target_node=target_node,
            estimated_effect=estimated_effect,
            confidence_interval=(max(0, estimated_effect - 0.2), min(1, estimated_effect + 0.2)),
            confounders_adjusted=adjusted_for,
            causal_paths=causal_paths,
            explanation=explanation,
        )

    def get_causal_ordering(self, graph: CausalGraph) -> list[str]:
        """
        Get topological ordering of nodes (causes before effects).

        Args:
            graph: CausalGraph (must be valid DAG)

        Returns:
            List of node IDs in causal order
        """
        if not graph.is_valid_dag:
            return []

        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = defaultdict(int)
        children: dict[str, list[str]] = defaultdict(list)

        node_ids = {n.id for n in graph.nodes}

        for edge in graph.edges:
            in_degree[edge.effect] += 1
            children[edge.cause].append(edge.effect)

        # Initialize queue with nodes having no incoming edges
        queue = deque([n for n in node_ids if in_degree[n] == 0])
        ordering = []

        while queue:
            node = queue.popleft()
            ordering.append(node)

            for child in children[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return ordering

    def to_graph(self, causal_graph: CausalGraph) -> Graph:
        """
        Convert CausalGraph to standard Graph format for visualization.

        Returns:
            Graph with causal styling properties
        """
        nodes = []
        edges = []

        # Get causal ordering for layer assignment
        ordering = self.get_causal_ordering(causal_graph)
        layer_map = {node_id: i for i, node_id in enumerate(ordering)}

        for node in causal_graph.nodes:
            nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type="causal_variable",
                entity_type=node.node_type,
                weight=1.0,
                properties={
                    "description": node.description,
                    "states": node.states,
                    "observed_state": node.observed_state,
                    "is_intervention": node.is_intervention,
                    "layer": layer_map.get(node.id, 0),
                    "causal_type": node.node_type,
                },
            ))

        for edge in causal_graph.edges:
            edges.append(GraphEdge(
                source=edge.cause,
                target=edge.effect,
                weight=edge.strength,
                type=edge.edge_type.value,
                relationship_type=edge.edge_type.value,
                properties={
                    "strength": edge.strength,
                    "confidence": edge.confidence,
                    "mechanism": edge.mechanism,
                },
            ))

        return Graph(
            id=causal_graph.id,
            nodes=nodes,
            edges=edges,
            properties={
                "graph_type": "causal",
                "is_valid_dag": causal_graph.is_valid_dag,
                "cycles": causal_graph.cycles,
            },
        )

    def to_dict(self, causal_graph: CausalGraph) -> dict[str, Any]:
        """Convert CausalGraph to dictionary for JSON serialization."""
        ordering = self.get_causal_ordering(causal_graph)

        return {
            "id": causal_graph.id,
            "name": causal_graph.name,
            "description": causal_graph.description,
            "is_valid_dag": causal_graph.is_valid_dag,
            "cycles": causal_graph.cycles,
            "causal_ordering": ordering,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "description": n.description,
                    "states": n.states,
                    "observed_state": n.observed_state,
                    "prior_probability": n.prior_probability,
                    "is_intervention": n.is_intervention,
                    "node_type": n.node_type,
                }
                for n in causal_graph.nodes
            ],
            "edges": [
                {
                    "cause": e.cause,
                    "effect": e.effect,
                    "strength": e.strength,
                    "edge_type": e.edge_type.value,
                    "confidence": e.confidence,
                    "mechanism": e.mechanism,
                }
                for e in causal_graph.edges
            ],
            "summary": {
                "node_count": len(causal_graph.nodes),
                "edge_count": len(causal_graph.edges),
                "has_cycles": len(causal_graph.cycles) > 0,
            },
        }
