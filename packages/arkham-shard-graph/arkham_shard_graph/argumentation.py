"""
Transform ACH data into argumentation graph structure.

Converts ACH matrices (hypotheses, evidence, ratings) into graph format
suitable for visualization as an argumentation framework.
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum
import logging

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class ArgumentNodeType(str, Enum):
    """Types of nodes in an argumentation graph."""
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    ASSUMPTION = "assumption"


class ArgumentEdgeType(str, Enum):
    """Types of edges in an argumentation graph."""
    SUPPORTS = "supports"
    ATTACKS = "attacks"
    NEUTRAL = "neutral"


@dataclass
class ArgumentNode:
    """Node in an argumentation graph."""
    id: str
    node_type: ArgumentNodeType
    label: str
    description: str = ""
    confidence: float | None = None
    # For hypotheses
    consistency_score: float | None = None
    rank: int | None = None
    is_lead: bool = False
    # For evidence
    credibility: float | None = None
    evidence_type: str | None = None
    source: str | None = None


@dataclass
class ArgumentEdge:
    """Edge in an argumentation graph."""
    source: str
    target: str
    edge_type: ArgumentEdgeType
    strength: float  # From ACH rating (-2 to +2)
    rating_value: str = ""  # Original rating (++, +, N, -, --)
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class ArgumentStatus:
    """Status of an argument based on Dung semantics."""
    node_id: str
    status: str  # "accepted", "rejected", "undecided"
    support_count: int = 0
    attack_count: int = 0
    net_score: float = 0.0


@dataclass
class ArgumentationGraph:
    """An argumentation graph derived from ACH data."""
    matrix_id: str
    matrix_title: str
    nodes: list[ArgumentNode] = field(default_factory=list)
    edges: list[ArgumentEdge] = field(default_factory=list)
    statuses: list[ArgumentStatus] = field(default_factory=list)
    leading_hypothesis_id: str | None = None


class ArgumentationBuilder:
    """Build argumentation graphs from ACH data."""

    # Rating value to numeric strength mapping
    RATING_STRENGTHS = {
        "++": 2.0,
        "+": 1.0,
        "N": 0.0,
        "-": -1.0,
        "--": -2.0,
        "N/A": 0.0,
    }

    def build_from_ach_matrix(
        self,
        matrix_data: dict[str, Any],
    ) -> ArgumentationGraph:
        """
        Transform ACH matrix into argumentation graph.

        - Hypotheses become hypothesis nodes (top layer)
        - Evidence becomes evidence nodes (bottom layer)
        - Ratings become support/attack edges

        Args:
            matrix_data: ACH matrix data dictionary

        Returns:
            ArgumentationGraph with nodes, edges, and computed statuses
        """
        matrix_id = matrix_data.get("id", "")
        matrix_title = matrix_data.get("title", "Untitled Matrix")

        nodes: list[ArgumentNode] = []
        edges: list[ArgumentEdge] = []

        # Get hypotheses, evidence, ratings, and scores
        hypotheses = matrix_data.get("hypotheses", [])
        evidence_list = matrix_data.get("evidence", [])
        ratings = matrix_data.get("ratings", [])
        scores = matrix_data.get("scores", [])

        # Build score lookup
        score_lookup = {s.get("hypothesis_id"): s for s in scores}

        # Find leading hypothesis
        leading_hypothesis_id = None
        if scores:
            sorted_scores = sorted(scores, key=lambda s: s.get("rank", 999))
            if sorted_scores:
                leading_hypothesis_id = sorted_scores[0].get("hypothesis_id")

        # Create hypothesis nodes
        for hyp in hypotheses:
            hyp_id = hyp.get("id", "")
            score_data = score_lookup.get(hyp_id, {})

            nodes.append(ArgumentNode(
                id=f"hyp_{hyp_id}",
                node_type=ArgumentNodeType.HYPOTHESIS,
                label=hyp.get("title", "Untitled"),
                description=hyp.get("description", ""),
                confidence=score_data.get("normalized_score"),
                consistency_score=score_data.get("consistency_score"),
                rank=score_data.get("rank"),
                is_lead=(hyp_id == leading_hypothesis_id),
            ))

        # Create evidence nodes
        for ev in evidence_list:
            ev_id = ev.get("id", "")
            nodes.append(ArgumentNode(
                id=f"ev_{ev_id}",
                node_type=ArgumentNodeType.EVIDENCE,
                label=ev.get("description", "")[:100] + ("..." if len(ev.get("description", "")) > 100 else ""),
                description=ev.get("description", ""),
                credibility=ev.get("credibility", 1.0),
                evidence_type=ev.get("evidence_type"),
                source=ev.get("source"),
            ))

        # Create edges from ratings
        for rating in ratings:
            evidence_id = rating.get("evidence_id", "")
            hypothesis_id = rating.get("hypothesis_id", "")
            rating_value = rating.get("rating", "N")
            reasoning = rating.get("reasoning", "")
            confidence = rating.get("confidence", 1.0)

            # Get numeric strength
            strength = self.RATING_STRENGTHS.get(rating_value, 0.0)

            # Skip N/A ratings (they don't represent a relationship)
            if rating_value == "N/A":
                continue

            # Determine edge type based on strength
            if strength > 0:
                edge_type = ArgumentEdgeType.SUPPORTS
            elif strength < 0:
                edge_type = ArgumentEdgeType.ATTACKS
            else:
                edge_type = ArgumentEdgeType.NEUTRAL

            edges.append(ArgumentEdge(
                source=f"ev_{evidence_id}",
                target=f"hyp_{hypothesis_id}",
                edge_type=edge_type,
                strength=strength,
                rating_value=rating_value,
                reasoning=reasoning,
                confidence=confidence,
            ))

        # Calculate argument statuses
        statuses = self._calculate_argument_status(nodes, edges)

        return ArgumentationGraph(
            matrix_id=matrix_id,
            matrix_title=matrix_title,
            nodes=nodes,
            edges=edges,
            statuses=statuses,
            leading_hypothesis_id=f"hyp_{leading_hypothesis_id}" if leading_hypothesis_id else None,
        )

    def _calculate_argument_status(
        self,
        nodes: list[ArgumentNode],
        edges: list[ArgumentEdge],
    ) -> list[ArgumentStatus]:
        """
        Calculate acceptance status for each hypothesis using Dung semantics.

        Uses a simplified grounded extension approach:
        - Count supporting and attacking evidence
        - Calculate net score
        - Determine status based on net score and relative position
        """
        statuses = []

        # Only calculate status for hypotheses
        hypothesis_nodes = [n for n in nodes if n.node_type == ArgumentNodeType.HYPOTHESIS]

        for node in hypothesis_nodes:
            support_count = 0
            attack_count = 0
            net_score = 0.0

            for edge in edges:
                if edge.target == node.id:
                    if edge.edge_type == ArgumentEdgeType.SUPPORTS:
                        support_count += 1
                        net_score += edge.strength * edge.confidence
                    elif edge.edge_type == ArgumentEdgeType.ATTACKS:
                        attack_count += 1
                        net_score += edge.strength * edge.confidence  # Already negative

            # Determine status
            if attack_count == 0 and support_count > 0:
                status = "accepted"
            elif support_count == 0 and attack_count > 0:
                status = "rejected"
            elif net_score > 1.0:
                status = "accepted"
            elif net_score < -1.0:
                status = "rejected"
            else:
                status = "undecided"

            statuses.append(ArgumentStatus(
                node_id=node.id,
                status=status,
                support_count=support_count,
                attack_count=attack_count,
                net_score=net_score,
            ))

        return statuses

    def to_graph(self, arg_graph: ArgumentationGraph) -> Graph:
        """
        Convert ArgumentationGraph to standard Graph format for visualization.

        Returns:
            Graph with nodes and edges suitable for force-directed layout
        """
        nodes = []
        edges = []

        # Convert argument nodes to graph nodes
        for arg_node in arg_graph.nodes:
            # Determine layer based on node type (for hierarchical layout)
            if arg_node.node_type == ArgumentNodeType.HYPOTHESIS:
                layer = 0
            else:
                layer = 1

            # Find status for hypotheses
            status = None
            for s in arg_graph.statuses:
                if s.node_id == arg_node.id:
                    status = s.status
                    break

            nodes.append(GraphNode(
                id=arg_node.id,
                label=arg_node.label,
                type=arg_node.node_type.value,
                entity_type=arg_node.node_type.value,
                weight=1.0,
                properties={
                    "description": arg_node.description,
                    "confidence": arg_node.confidence,
                    "consistency_score": arg_node.consistency_score,
                    "rank": arg_node.rank,
                    "is_lead": arg_node.is_lead,
                    "credibility": arg_node.credibility,
                    "evidence_type": arg_node.evidence_type,
                    "source": arg_node.source,
                    "layer": layer,
                    "status": status,
                },
            ))

        # Convert argument edges to graph edges
        for arg_edge in arg_graph.edges:
            edges.append(GraphEdge(
                source=arg_edge.source,
                target=arg_edge.target,
                weight=abs(arg_edge.strength),
                type=arg_edge.edge_type.value,
                relationship_type=arg_edge.edge_type.value,
                properties={
                    "strength": arg_edge.strength,
                    "rating_value": arg_edge.rating_value,
                    "reasoning": arg_edge.reasoning,
                    "confidence": arg_edge.confidence,
                },
            ))

        return Graph(
            id=f"arg_{arg_graph.matrix_id}",
            nodes=nodes,
            edges=edges,
            properties={
                "graph_type": "argumentation",
                "matrix_id": arg_graph.matrix_id,
                "matrix_title": arg_graph.matrix_title,
                "leading_hypothesis_id": arg_graph.leading_hypothesis_id,
            },
        )

    def to_dict(self, arg_graph: ArgumentationGraph) -> dict[str, Any]:
        """Convert ArgumentationGraph to dictionary for JSON serialization."""
        return {
            "matrix_id": arg_graph.matrix_id,
            "matrix_title": arg_graph.matrix_title,
            "leading_hypothesis_id": arg_graph.leading_hypothesis_id,
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type.value,
                    "label": n.label,
                    "description": n.description,
                    "confidence": n.confidence,
                    "consistency_score": n.consistency_score,
                    "rank": n.rank,
                    "is_lead": n.is_lead,
                    "credibility": n.credibility,
                    "evidence_type": n.evidence_type,
                    "source": n.source,
                }
                for n in arg_graph.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type.value,
                    "strength": e.strength,
                    "rating_value": e.rating_value,
                    "reasoning": e.reasoning,
                    "confidence": e.confidence,
                }
                for e in arg_graph.edges
            ],
            "statuses": [
                {
                    "node_id": s.node_id,
                    "status": s.status,
                    "support_count": s.support_count,
                    "attack_count": s.attack_count,
                    "net_score": s.net_score,
                }
                for s in arg_graph.statuses
            ],
            "summary": {
                "hypothesis_count": len([n for n in arg_graph.nodes if n.node_type == ArgumentNodeType.HYPOTHESIS]),
                "evidence_count": len([n for n in arg_graph.nodes if n.node_type == ArgumentNodeType.EVIDENCE]),
                "support_edges": len([e for e in arg_graph.edges if e.edge_type == ArgumentEdgeType.SUPPORTS]),
                "attack_edges": len([e for e in arg_graph.edges if e.edge_type == ArgumentEdgeType.ATTACKS]),
                "neutral_edges": len([e for e in arg_graph.edges if e.edge_type == ArgumentEdgeType.NEUTRAL]),
            },
        }
