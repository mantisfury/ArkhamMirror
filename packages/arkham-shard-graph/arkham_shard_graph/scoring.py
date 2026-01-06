"""
Composite scoring engine for entity importance.

Combines multiple signals (centrality, frequency, recency, credibility, corroboration)
into a unified importance score for graph entities.
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .models import Graph, GraphNode

logger = logging.getLogger(__name__)


@dataclass
class ScoreConfig:
    """Configuration for composite scoring."""

    # Centrality settings
    centrality_type: str = "pagerank"  # pagerank, betweenness, eigenvector, hits, closeness, degree

    # Weight distribution (should sum to 1.0, will be normalized)
    centrality_weight: float = 0.25
    frequency_weight: float = 0.20
    recency_weight: float = 0.20
    credibility_weight: float = 0.20
    corroboration_weight: float = 0.15

    # Recency settings
    recency_half_life_days: int | None = 30  # None = disabled
    recency_reference_date: datetime | None = None  # None = use current time

    # Entity type weights (optional, e.g., {"person": 1.2, "organization": 1.0})
    entity_type_weights: dict[str, float] = field(default_factory=dict)

    def normalized_weights(self) -> dict[str, float]:
        """Get normalized weights that sum to 1.0."""
        total = (
            self.centrality_weight +
            self.frequency_weight +
            self.recency_weight +
            self.credibility_weight +
            self.corroboration_weight
        )
        if total == 0:
            return {
                "centrality": 0.2,
                "frequency": 0.2,
                "recency": 0.2,
                "credibility": 0.2,
                "corroboration": 0.2,
            }
        return {
            "centrality": self.centrality_weight / total,
            "frequency": self.frequency_weight / total,
            "recency": self.recency_weight / total,
            "credibility": self.credibility_weight / total,
            "corroboration": self.corroboration_weight / total,
        }


@dataclass
class EntityScore:
    """Composite score for an entity."""
    entity_id: str
    label: str
    entity_type: str

    # Individual scores (0-1 range)
    centrality_score: float = 0.0
    frequency_score: float = 0.0
    recency_score: float = 0.0
    credibility_score: float = 0.0
    corroboration_score: float = 0.0

    # Final composite score
    composite_score: float = 0.0

    # Rank (1 = highest)
    rank: int = 0

    # Additional metadata
    degree: int = 0
    document_count: int = 0
    source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "entity_type": self.entity_type,
            "composite_score": round(self.composite_score, 4),
            "centrality_score": round(self.centrality_score, 4),
            "frequency_score": round(self.frequency_score, 4),
            "recency_score": round(self.recency_score, 4),
            "credibility_score": round(self.credibility_score, 4),
            "corroboration_score": round(self.corroboration_score, 4),
            "rank": self.rank,
            "degree": self.degree,
            "document_count": self.document_count,
            "source_count": self.source_count,
        }


@dataclass
class ScoreResponse:
    """Response from scoring calculation."""
    project_id: str
    scores: list[EntityScore]
    config: ScoreConfig
    calculation_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "scores": [s.to_dict() for s in self.scores],
            "config": {
                "centrality_type": self.config.centrality_type,
                "weights": self.config.normalized_weights(),
                "recency_half_life_days": self.config.recency_half_life_days,
            },
            "calculation_time_ms": round(self.calculation_time_ms, 2),
            "entity_count": len(self.scores),
        }


class CompositeScorer:
    """
    Calculate composite entity scores using multiple signals.

    Combines:
    - Graph centrality (PageRank, betweenness, etc.)
    - Frequency (TF-IDF style rarity weighting)
    - Recency (exponential time decay)
    - Source credibility (from credibility ratings)
    - Corroboration (multiple independent sources)
    """

    def __init__(self):
        """Initialize the composite scorer."""
        self._centrality_cache: dict[str, dict[str, float]] = {}

    def calculate_scores(
        self,
        graph: Graph,
        config: ScoreConfig,
        entity_mentions: dict[str, list[dict]] | None = None,
        credibility_ratings: dict[str, float] | None = None,
    ) -> list[EntityScore]:
        """
        Calculate composite scores for all entities in the graph.

        Args:
            graph: The entity graph
            config: Scoring configuration
            entity_mentions: Optional dict of entity_id -> list of mention records
                            Each mention should have: document_id, date (optional), source_id (optional)
            credibility_ratings: Optional dict of source_id -> credibility score (0-1)

        Returns:
            List of EntityScore objects sorted by composite score (descending)
        """
        if not graph.nodes:
            return []

        entity_mentions = entity_mentions or {}
        credibility_ratings = credibility_ratings or {}

        weights = config.normalized_weights()

        # Calculate individual scores
        centrality_scores = self._calculate_centrality_scores(graph, config.centrality_type)
        frequency_scores = self._calculate_frequency_scores(graph, entity_mentions)
        recency_scores = self._calculate_recency_scores(graph, entity_mentions, config)
        credibility_scores = self._calculate_credibility_scores(graph, entity_mentions, credibility_ratings)
        corroboration_scores = self._calculate_corroboration_scores(graph, entity_mentions)

        # Build EntityScore objects
        scores = []
        for node in graph.nodes:
            entity_id = node.entity_id

            # Get individual scores
            centrality = centrality_scores.get(entity_id, 0.0)
            frequency = frequency_scores.get(entity_id, 0.0)
            recency = recency_scores.get(entity_id, 0.0)
            credibility = credibility_scores.get(entity_id, 0.5)  # Default to neutral
            corroboration = corroboration_scores.get(entity_id, 0.0)

            # Apply entity type weight if configured
            type_weight = config.entity_type_weights.get(node.entity_type, 1.0)

            # Calculate composite score
            composite = (
                weights["centrality"] * centrality +
                weights["frequency"] * frequency +
                weights["recency"] * recency +
                weights["credibility"] * credibility +
                weights["corroboration"] * corroboration
            ) * type_weight

            # Count sources
            mentions = entity_mentions.get(entity_id, [])
            source_ids = set(m.get("source_id") for m in mentions if m.get("source_id"))

            score = EntityScore(
                entity_id=entity_id,
                label=node.label,
                entity_type=node.entity_type,
                centrality_score=centrality,
                frequency_score=frequency,
                recency_score=recency,
                credibility_score=credibility,
                corroboration_score=corroboration,
                composite_score=composite,
                degree=node.degree,
                document_count=node.document_count,
                source_count=len(source_ids),
            )
            scores.append(score)

        # Sort by composite score and assign ranks
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        for rank, score in enumerate(scores, start=1):
            score.rank = rank

        return scores

    def _calculate_centrality_scores(
        self,
        graph: Graph,
        centrality_type: str
    ) -> dict[str, float]:
        """
        Calculate centrality-based scores (0-1 normalized).

        Supports: pagerank, betweenness, eigenvector, hits, closeness, degree
        """
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return {}

        # Build adjacency
        adjacency = self._build_adjacency(graph)

        if centrality_type == "degree":
            raw_scores = self._degree_centrality(graph)
        elif centrality_type == "betweenness":
            raw_scores = self._betweenness_centrality(graph, adjacency)
        elif centrality_type == "pagerank":
            raw_scores = self._pagerank(graph, adjacency)
        elif centrality_type == "eigenvector":
            raw_scores = self._eigenvector_centrality(graph, adjacency)
        elif centrality_type == "hits":
            raw_scores = self._hits_centrality(graph, adjacency)
        elif centrality_type == "closeness":
            raw_scores = self._closeness_centrality(graph, adjacency)
        else:
            # Default to PageRank
            raw_scores = self._pagerank(graph, adjacency)

        # Normalize to 0-1 range
        max_score = max(raw_scores.values()) if raw_scores else 1.0
        if max_score == 0:
            max_score = 1.0

        # Map node IDs to entity IDs
        node_to_entity = {n.id: n.entity_id for n in graph.nodes}

        return {
            node_to_entity[node_id]: score / max_score
            for node_id, score in raw_scores.items()
            if node_id in node_to_entity
        }

    def _calculate_frequency_scores(
        self,
        graph: Graph,
        entity_mentions: dict[str, list[dict]]
    ) -> dict[str, float]:
        """
        Calculate TF-IDF style frequency scores.

        Entities mentioned in fewer documents are weighted higher (more distinctive).
        """
        # Get total document count
        all_doc_ids = set()
        for node in graph.nodes:
            mentions = entity_mentions.get(node.entity_id, [])
            for m in mentions:
                if m.get("document_id"):
                    all_doc_ids.add(m["document_id"])

        total_docs = len(all_doc_ids) if all_doc_ids else 1

        scores = {}
        for node in graph.nodes:
            mentions = entity_mentions.get(node.entity_id, [])
            doc_ids = set(m.get("document_id") for m in mentions if m.get("document_id"))
            doc_count = len(doc_ids) if doc_ids else node.document_count

            if doc_count == 0:
                scores[node.entity_id] = 0.0
                continue

            # Term frequency (normalized by max in corpus)
            tf = doc_count

            # Inverse document frequency (log scale)
            # Higher score for entities in fewer documents (more distinctive)
            idf = math.log(total_docs / doc_count + 1)

            # TF-IDF score
            scores[node.entity_id] = tf * idf

        # Normalize to 0-1
        max_score = max(scores.values()) if scores else 1.0
        if max_score == 0:
            max_score = 1.0

        return {k: v / max_score for k, v in scores.items()}

    def _calculate_recency_scores(
        self,
        graph: Graph,
        entity_mentions: dict[str, list[dict]],
        config: ScoreConfig
    ) -> dict[str, float]:
        """
        Calculate recency scores using exponential decay.

        More recent mentions get higher scores.
        """
        if config.recency_half_life_days is None:
            # Recency disabled, return uniform scores
            return {n.entity_id: 1.0 for n in graph.nodes}

        reference_date = config.recency_reference_date or datetime.utcnow()
        half_life = timedelta(days=config.recency_half_life_days)
        decay_constant = math.log(2) / half_life.total_seconds()

        scores = {}
        for node in graph.nodes:
            mentions = entity_mentions.get(node.entity_id, [])

            if not mentions:
                scores[node.entity_id] = 0.0
                continue

            # Get most recent mention date
            max_recency = 0.0
            for mention in mentions:
                mention_date = mention.get("date")
                if mention_date:
                    if isinstance(mention_date, str):
                        try:
                            mention_date = datetime.fromisoformat(mention_date.replace("Z", "+00:00"))
                        except ValueError:
                            continue

                    # Calculate time difference
                    age_seconds = (reference_date - mention_date).total_seconds()
                    if age_seconds < 0:
                        age_seconds = 0

                    # Exponential decay
                    recency = math.exp(-decay_constant * age_seconds)
                    max_recency = max(max_recency, recency)

            scores[node.entity_id] = max_recency if max_recency > 0 else 0.5  # Default to middle

        return scores

    def _calculate_credibility_scores(
        self,
        graph: Graph,
        entity_mentions: dict[str, list[dict]],
        credibility_ratings: dict[str, float]
    ) -> dict[str, float]:
        """
        Calculate credibility scores based on source reliability.

        Uses NATO Admiralty Code style ratings (A-F, 1-6) if available.
        """
        if not credibility_ratings:
            # No credibility data, return neutral scores
            return {n.entity_id: 0.5 for n in graph.nodes}

        scores = {}
        for node in graph.nodes:
            mentions = entity_mentions.get(node.entity_id, [])

            if not mentions:
                scores[node.entity_id] = 0.5  # Neutral
                continue

            # Weighted average of source credibility
            total_weight = 0.0
            weighted_sum = 0.0

            for mention in mentions:
                source_id = mention.get("source_id")
                if source_id and source_id in credibility_ratings:
                    rating = credibility_ratings[source_id]
                    # Weight by mention count from this source
                    weight = 1.0
                    weighted_sum += rating * weight
                    total_weight += weight

            if total_weight > 0:
                scores[node.entity_id] = weighted_sum / total_weight
            else:
                scores[node.entity_id] = 0.5  # Neutral

        return scores

    def _calculate_corroboration_scores(
        self,
        graph: Graph,
        entity_mentions: dict[str, list[dict]]
    ) -> dict[str, float]:
        """
        Calculate corroboration scores based on independent source confirmation.

        Entities mentioned by multiple independent sources score higher.
        """
        scores = {}

        # First, find max source count for normalization
        max_sources = 1
        source_counts = {}

        for node in graph.nodes:
            mentions = entity_mentions.get(node.entity_id, [])
            source_ids = set(m.get("source_id") for m in mentions if m.get("source_id"))
            source_counts[node.entity_id] = len(source_ids)
            max_sources = max(max_sources, len(source_ids))

        # Calculate scores with diminishing returns (log scale)
        for node in graph.nodes:
            count = source_counts.get(node.entity_id, 0)
            if count == 0:
                # Fall back to document count
                count = node.document_count

            if count <= 1:
                scores[node.entity_id] = 0.0
            else:
                # Log scale for diminishing returns
                # 2 sources = 0.5, 4 sources = 0.75, 8 sources = 0.875, etc.
                scores[node.entity_id] = 1 - (1 / count)

        return scores

    # --- Centrality Algorithms ---

    def _build_adjacency(self, graph: Graph) -> dict[str, list[tuple[str, float]]]:
        """Build weighted adjacency list."""
        adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.source].append((edge.target, edge.weight))
            adjacency[edge.target].append((edge.source, edge.weight))
        return adjacency

    def _degree_centrality(self, graph: Graph) -> dict[str, float]:
        """Simple degree centrality."""
        return {n.id: float(n.degree) for n in graph.nodes}

    def _pagerank(
        self,
        graph: Graph,
        adjacency: dict[str, list[tuple[str, float]]],
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> dict[str, float]:
        """PageRank using power iteration."""
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return {}

        # Out-degree
        out_degree = {nid: len(adjacency.get(nid, [])) for nid in node_ids}

        # Initialize
        pagerank = {nid: 1.0 / n for nid in node_ids}

        for _ in range(max_iterations):
            new_pagerank = {}
            max_diff = 0.0

            for node_id in node_ids:
                rank_sum = 0.0
                for other_id in node_ids:
                    neighbors = [n for n, _ in adjacency.get(other_id, [])]
                    if node_id in neighbors and out_degree[other_id] > 0:
                        rank_sum += pagerank[other_id] / out_degree[other_id]

                new_rank = (1 - damping) / n + damping * rank_sum
                new_pagerank[node_id] = new_rank
                max_diff = max(max_diff, abs(new_rank - pagerank[node_id]))

            pagerank = new_pagerank
            if max_diff < tolerance:
                break

        return pagerank

    def _betweenness_centrality(
        self,
        graph: Graph,
        adjacency: dict[str, list[tuple[str, float]]]
    ) -> dict[str, float]:
        """Betweenness centrality (simplified)."""
        from collections import deque

        node_ids = [n.id for n in graph.nodes]
        betweenness = defaultdict(float)

        # Unweighted adjacency for BFS
        adj_simple = {nid: [t for t, _ in neighbors] for nid, neighbors in adjacency.items()}

        # Sample nodes for performance
        sample_size = min(50, len(node_ids))
        sample_nodes = node_ids[:sample_size]

        for source in sample_nodes:
            # BFS
            queue = deque([source])
            distances = {source: 0}
            paths = {source: [[source]]}

            while queue:
                current = queue.popleft()
                for neighbor in adj_simple.get(current, []):
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        paths[neighbor] = []
                        queue.append(neighbor)

                    if distances[neighbor] == distances[current] + 1:
                        paths[neighbor].extend([p + [neighbor] for p in paths[current]])

            # Count paths through each node
            for target, target_paths in paths.items():
                for path in target_paths:
                    for node in path[1:-1]:  # Exclude source and target
                        betweenness[node] += 1.0 / len(target_paths)

        return dict(betweenness)

    def _eigenvector_centrality(
        self,
        graph: Graph,
        adjacency: dict[str, list[tuple[str, float]]],
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> dict[str, float]:
        """Eigenvector centrality using power iteration."""
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return {}

        # Initialize
        scores = {nid: 1.0 for nid in node_ids}

        for _ in range(max_iterations):
            new_scores = {}
            max_diff = 0.0

            for node_id in node_ids:
                # Sum of neighbor scores weighted by edge weight
                score_sum = 0.0
                for neighbor, weight in adjacency.get(node_id, []):
                    score_sum += scores.get(neighbor, 0.0) * weight

                new_scores[node_id] = score_sum

            # Normalize
            norm = math.sqrt(sum(s * s for s in new_scores.values()))
            if norm > 0:
                new_scores = {k: v / norm for k, v in new_scores.items()}

            # Check convergence
            for node_id in node_ids:
                max_diff = max(max_diff, abs(new_scores[node_id] - scores[node_id]))

            scores = new_scores
            if max_diff < tolerance:
                break

        return scores

    def _hits_centrality(
        self,
        graph: Graph,
        adjacency: dict[str, list[tuple[str, float]]],
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> dict[str, float]:
        """HITS algorithm (Hubs and Authorities) - returns authority scores."""
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return {}

        # Initialize
        hub_scores = {nid: 1.0 for nid in node_ids}
        auth_scores = {nid: 1.0 for nid in node_ids}

        # Build reverse adjacency (incoming edges)
        reverse_adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for source, neighbors in adjacency.items():
            for target, weight in neighbors:
                reverse_adj[target].append((source, weight))

        for _ in range(max_iterations):
            # Update authority scores
            new_auth = {}
            for node_id in node_ids:
                score = sum(hub_scores.get(src, 0.0) * w for src, w in reverse_adj.get(node_id, []))
                new_auth[node_id] = score

            # Normalize authority
            norm = math.sqrt(sum(s * s for s in new_auth.values()))
            if norm > 0:
                new_auth = {k: v / norm for k, v in new_auth.items()}

            # Update hub scores
            new_hub = {}
            for node_id in node_ids:
                score = sum(new_auth.get(tgt, 0.0) * w for tgt, w in adjacency.get(node_id, []))
                new_hub[node_id] = score

            # Normalize hub
            norm = math.sqrt(sum(s * s for s in new_hub.values()))
            if norm > 0:
                new_hub = {k: v / norm for k, v in new_hub.items()}

            # Check convergence
            max_diff = max(abs(new_auth[n] - auth_scores[n]) for n in node_ids)

            hub_scores = new_hub
            auth_scores = new_auth

            if max_diff < tolerance:
                break

        # Return authority scores (more useful for entity importance)
        return auth_scores

    def _closeness_centrality(
        self,
        graph: Graph,
        adjacency: dict[str, list[tuple[str, float]]]
    ) -> dict[str, float]:
        """Closeness centrality (inverse of average distance)."""
        from collections import deque

        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return {}

        # Unweighted adjacency for BFS
        adj_simple = {nid: [t for t, _ in neighbors] for nid, neighbors in adjacency.items()}

        scores = {}

        # Sample for performance
        sample_size = min(50, n)

        for node_id in node_ids[:sample_size]:
            # BFS to find distances
            distances = {node_id: 0}
            queue = deque([node_id])

            while queue:
                current = queue.popleft()
                for neighbor in adj_simple.get(current, []):
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        queue.append(neighbor)

            # Closeness = (n-1) / sum of distances
            reachable = len(distances) - 1
            if reachable > 0:
                avg_distance = sum(distances.values()) / reachable
                scores[node_id] = 1.0 / avg_distance if avg_distance > 0 else 0.0
            else:
                scores[node_id] = 0.0

        # Fill in unsampled nodes with average
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        for node_id in node_ids:
            if node_id not in scores:
                scores[node_id] = avg_score

        return scores
