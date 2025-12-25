"""Graph algorithms - path finding, centrality, community detection."""

import logging
from collections import defaultdict, deque
from typing import Any
import math

from .models import (
    Graph,
    GraphEdge,
    GraphPath,
    CentralityResult,
    Community,
    GraphStatistics,
)

logger = logging.getLogger(__name__)


class GraphAlgorithms:
    """
    Graph analysis algorithms.

    Implements pure Python versions of common graph algorithms.
    """

    def __init__(self):
        """Initialize graph algorithms."""
        pass

    def find_shortest_path(
        self,
        graph: Graph,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 6,
    ) -> GraphPath | None:
        """
        Find shortest path between two entities using BFS.

        Args:
            graph: Graph to search
            source_entity_id: Source entity ID
            target_entity_id: Target entity ID
            max_depth: Maximum path length

        Returns:
            GraphPath if found, None otherwise
        """
        # Build adjacency list
        adjacency = self._build_adjacency_dict(graph.edges)

        # BFS
        queue = deque([(source_entity_id, [source_entity_id])])
        visited = {source_entity_id}

        while queue:
            current, path = queue.popleft()

            # Check depth limit
            if len(path) > max_depth:
                continue

            # Found target
            if current == target_entity_id:
                # Reconstruct edges
                edges = self._get_path_edges(graph.edges, path)
                total_weight = sum(e.weight for e in edges)

                return GraphPath(
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    path=path,
                    edges=edges,
                    total_weight=total_weight,
                    path_length=len(path) - 1,
                )

            # Explore neighbors
            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def calculate_degree_centrality(
        self, graph: Graph, limit: int = 50
    ) -> list[CentralityResult]:
        """
        Calculate degree centrality.

        Args:
            graph: Graph to analyze
            limit: Top N results

        Returns:
            List of CentralityResult objects
        """
        # Degree is already calculated on nodes
        node_map = {n.id: n for n in graph.nodes}

        # Sort by degree
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.degree, reverse=True)

        # Normalize scores
        max_degree = sorted_nodes[0].degree if sorted_nodes else 1

        results = []
        for rank, node in enumerate(sorted_nodes[:limit], start=1):
            score = node.degree / max_degree if max_degree > 0 else 0.0

            results.append(
                CentralityResult(
                    entity_id=node.entity_id,
                    label=node.label,
                    score=score,
                    rank=rank,
                    entity_type=node.entity_type,
                )
            )

        return results

    def calculate_betweenness_centrality(
        self, graph: Graph, limit: int = 50
    ) -> list[CentralityResult]:
        """
        Calculate betweenness centrality.

        Measures how often a node appears on shortest paths.

        Args:
            graph: Graph to analyze
            limit: Top N results

        Returns:
            List of CentralityResult objects
        """
        node_ids = [n.id for n in graph.nodes]
        betweenness = defaultdict(float)

        # Build adjacency
        adjacency = self._build_adjacency_dict(graph.edges)

        # For each pair of nodes, find all shortest paths
        for source in node_ids:
            # BFS from source
            paths_through = self._count_paths_through(adjacency, source, node_ids)

            for node_id, count in paths_through.items():
                betweenness[node_id] += count

        # Normalize
        n = len(node_ids)
        max_betweenness = (n - 1) * (n - 2) / 2 if n > 2 else 1

        # Sort by betweenness
        sorted_items = sorted(
            betweenness.items(), key=lambda x: x[1], reverse=True
        )

        node_map = {n.id: n for n in graph.nodes}

        results = []
        for rank, (node_id, value) in enumerate(sorted_items[:limit], start=1):
            node = node_map.get(node_id)
            if not node:
                continue

            score = value / max_betweenness if max_betweenness > 0 else 0.0

            results.append(
                CentralityResult(
                    entity_id=node.entity_id,
                    label=node.label,
                    score=score,
                    rank=rank,
                    entity_type=node.entity_type,
                )
            )

        return results

    def calculate_pagerank(
        self,
        graph: Graph,
        limit: int = 50,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> list[CentralityResult]:
        """
        Calculate PageRank using power iteration method.

        Args:
            graph: Graph to analyze
            limit: Top N results
            damping: Damping factor (typically 0.85)
            max_iterations: Maximum iterations
            tolerance: Convergence threshold

        Returns:
            List of CentralityResult objects
        """
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)

        if n == 0:
            return []

        # Build adjacency with out-degree
        adjacency = self._build_adjacency_dict(graph.edges)
        out_degree = {node_id: len(adjacency.get(node_id, [])) for node_id in node_ids}

        # Initialize PageRank
        pagerank = {node_id: 1.0 / n for node_id in node_ids}

        # Power iteration
        for iteration in range(max_iterations):
            new_pagerank = {}
            max_diff = 0.0

            for node_id in node_ids:
                # Sum contributions from incoming edges
                rank_sum = 0.0

                for other_id in node_ids:
                    if node_id in adjacency.get(other_id, []):
                        if out_degree[other_id] > 0:
                            rank_sum += pagerank[other_id] / out_degree[other_id]

                # Apply damping factor
                new_rank = (1 - damping) / n + damping * rank_sum
                new_pagerank[node_id] = new_rank

                # Track convergence
                max_diff = max(max_diff, abs(new_rank - pagerank[node_id]))

            pagerank = new_pagerank

            # Check convergence
            if max_diff < tolerance:
                logger.info(f"PageRank converged after {iteration + 1} iterations")
                break

        # Sort by PageRank
        sorted_items = sorted(
            pagerank.items(), key=lambda x: x[1], reverse=True
        )

        node_map = {n.id: n for n in graph.nodes}

        results = []
        for rank, (node_id, score) in enumerate(sorted_items[:limit], start=1):
            node = node_map.get(node_id)
            if not node:
                continue

            results.append(
                CentralityResult(
                    entity_id=node.entity_id,
                    label=node.label,
                    score=score,
                    rank=rank,
                    entity_type=node.entity_type,
                )
            )

        return results

    def detect_communities_louvain(
        self,
        graph: Graph,
        min_community_size: int = 3,
        resolution: float = 1.0,
    ) -> tuple[list[Community], float]:
        """
        Detect communities using Louvain-style modularity optimization.

        Simplified implementation without hierarchical levels.

        Args:
            graph: Graph to analyze
            min_community_size: Minimum community size
            resolution: Resolution parameter for community size

        Returns:
            Tuple of (communities list, modularity score)
        """
        node_ids = [n.id for n in graph.nodes]
        node_map = {n.id: n for n in graph.nodes}

        # Initialize each node in its own community
        community_map = {node_id: node_id for node_id in node_ids}

        # Build adjacency with weights
        adjacency = self._build_weighted_adjacency(graph.edges)

        # Calculate total edge weight
        total_weight = sum(e.weight for e in graph.edges)

        if total_weight == 0:
            return [], 0.0

        # Iterative optimization
        improved = True
        iterations = 0
        max_iterations = 50

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1

            for node_id in node_ids:
                current_community = community_map[node_id]

                # Calculate modularity gain for moving to neighbor communities
                best_community = current_community
                best_gain = 0.0

                neighbor_communities = set()
                for neighbor, _ in adjacency.get(node_id, []):
                    neighbor_communities.add(community_map[neighbor])

                for candidate_community in neighbor_communities:
                    if candidate_community == current_community:
                        continue

                    gain = self._modularity_gain(
                        node_id,
                        current_community,
                        candidate_community,
                        community_map,
                        adjacency,
                        total_weight,
                        resolution,
                    )

                    if gain > best_gain:
                        best_gain = gain
                        best_community = candidate_community

                if best_community != current_community:
                    community_map[node_id] = best_community
                    improved = True

        # Build communities
        community_members = defaultdict(list)
        for node_id, comm_id in community_map.items():
            community_members[comm_id].append(node_id)

        # Create Community objects
        communities = []
        for comm_id, members in community_members.items():
            if len(members) < min_community_size:
                continue

            # Calculate community metrics
            internal_edges = 0
            external_edges = 0

            for member in members:
                for neighbor, weight in adjacency.get(member, []):
                    if neighbor in members:
                        internal_edges += 1
                    else:
                        external_edges += 1

            # Density
            n_members = len(members)
            max_edges = n_members * (n_members - 1)
            density = internal_edges / max_edges if max_edges > 0 else 0.0

            community = Community(
                id=f"comm_{comm_id}",
                entity_ids=members,
                size=len(members),
                density=density,
                internal_edges=internal_edges // 2,  # Each edge counted twice
                external_edges=external_edges,
            )
            communities.append(community)

        # Calculate overall modularity
        modularity = self._calculate_modularity(
            community_map, adjacency, total_weight
        )

        logger.info(
            f"Detected {len(communities)} communities (modularity: {modularity:.3f})"
        )

        return communities, modularity

    def calculate_statistics(self, graph: Graph) -> GraphStatistics:
        """
        Calculate comprehensive graph statistics.

        Args:
            graph: Graph to analyze

        Returns:
            GraphStatistics object
        """
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)

        if node_count == 0:
            return GraphStatistics(
                project_id=graph.project_id,
                node_count=0,
                edge_count=0,
                density=0.0,
                avg_degree=0.0,
                avg_clustering=0.0,
                connected_components=0,
                diameter=0,
                avg_path_length=0.0,
            )

        # Density
        max_edges = node_count * (node_count - 1) / 2
        density = edge_count / max_edges if max_edges > 0 else 0.0

        # Average degree
        avg_degree = sum(n.degree for n in graph.nodes) / node_count

        # Clustering coefficient
        avg_clustering = self._calculate_avg_clustering(graph)

        # Connected components
        components = self._find_connected_components(graph)
        connected_components = len(components)

        # Diameter and average path length
        diameter, avg_path_length = self._calculate_distance_metrics(graph)

        # Entity type distribution
        entity_type_dist = defaultdict(int)
        for node in graph.nodes:
            entity_type_dist[node.entity_type] += 1

        # Relationship type distribution
        relationship_type_dist = defaultdict(int)
        for edge in graph.edges:
            relationship_type_dist[edge.relationship_type] += 1

        return GraphStatistics(
            project_id=graph.project_id,
            node_count=node_count,
            edge_count=edge_count,
            density=density,
            avg_degree=avg_degree,
            avg_clustering=avg_clustering,
            connected_components=connected_components,
            diameter=diameter,
            avg_path_length=avg_path_length,
            entity_type_distribution=dict(entity_type_dist),
            relationship_type_distribution=dict(relationship_type_dist),
        )

    def get_neighbors(
        self,
        graph: Graph,
        entity_id: str,
        depth: int = 1,
        min_weight: float = 0.0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Get neighbors of an entity.

        Args:
            graph: Graph to search
            entity_id: Entity ID
            depth: Hop distance (1 or 2)
            min_weight: Minimum edge weight
            limit: Maximum neighbors

        Returns:
            Dictionary with neighbor information
        """
        adjacency = self._build_weighted_adjacency(graph.edges)

        # 1-hop neighbors
        neighbors_1hop = []
        for neighbor, weight in adjacency.get(entity_id, []):
            if weight >= min_weight:
                neighbors_1hop.append((neighbor, weight, 1))

        neighbors = neighbors_1hop[:limit]

        # 2-hop neighbors if requested
        if depth >= 2:
            neighbors_2hop = []
            for neighbor, _, _ in neighbors_1hop:
                for second_hop, weight in adjacency.get(neighbor, []):
                    if second_hop != entity_id and weight >= min_weight:
                        # Check if not already in 1-hop
                        if second_hop not in {n[0] for n in neighbors_1hop}:
                            neighbors_2hop.append((second_hop, weight, 2))

            # Add 2-hop neighbors up to limit
            remaining = limit - len(neighbors)
            if remaining > 0:
                neighbors.extend(neighbors_2hop[:remaining])

        # Build result
        node_map = {n.id: n for n in graph.nodes}

        result_neighbors = []
        for neighbor_id, weight, hop_distance in neighbors:
            node = node_map.get(neighbor_id)
            if node:
                result_neighbors.append({
                    "entity_id": node.entity_id,
                    "label": node.label,
                    "entity_type": node.entity_type,
                    "weight": weight,
                    "hop_distance": hop_distance,
                })

        return {
            "entity_id": entity_id,
            "neighbor_count": len(result_neighbors),
            "neighbors": result_neighbors,
        }

    # --- Helper Methods ---

    def _build_adjacency_dict(
        self, edges: list[GraphEdge]
    ) -> dict[str, list[str]]:
        """Build adjacency dictionary (unweighted)."""
        adjacency = defaultdict(list)

        for edge in edges:
            adjacency[edge.source].append(edge.target)
            adjacency[edge.target].append(edge.source)

        return adjacency

    def _build_weighted_adjacency(
        self, edges: list[GraphEdge]
    ) -> dict[str, list[tuple[str, float]]]:
        """Build weighted adjacency dictionary."""
        adjacency = defaultdict(list)

        for edge in edges:
            adjacency[edge.source].append((edge.target, edge.weight))
            adjacency[edge.target].append((edge.source, edge.weight))

        return adjacency

    def _get_path_edges(
        self, edges: list[GraphEdge], path: list[str]
    ) -> list[GraphEdge]:
        """Get edges along a path."""
        # Build edge lookup
        edge_map = {}
        for edge in edges:
            key1 = (edge.source, edge.target)
            key2 = (edge.target, edge.source)
            edge_map[key1] = edge
            edge_map[key2] = edge

        path_edges = []
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            edge = edge_map.get(key)
            if edge:
                path_edges.append(edge)

        return path_edges

    def _count_paths_through(
        self,
        adjacency: dict[str, list[str]],
        source: str,
        all_nodes: list[str],
    ) -> dict[str, int]:
        """Count how many shortest paths pass through each node."""
        paths_through = defaultdict(int)

        # BFS from source to all other nodes
        for target in all_nodes:
            if target == source:
                continue

            # Find all shortest paths
            queue = deque([(source, [source])])
            visited_distances = {source: 0}
            all_shortest_paths = []
            shortest_length = None

            while queue:
                current, path = queue.popleft()
                current_dist = len(path) - 1

                if shortest_length is not None and current_dist > shortest_length:
                    break

                if current == target:
                    if shortest_length is None:
                        shortest_length = current_dist
                    all_shortest_paths.append(path)
                    continue

                for neighbor in adjacency.get(current, []):
                    new_dist = current_dist + 1

                    if neighbor not in visited_distances or visited_distances[neighbor] == new_dist:
                        visited_distances[neighbor] = new_dist
                        queue.append((neighbor, path + [neighbor]))

            # Count nodes on shortest paths
            for path in all_shortest_paths:
                for node in path[1:-1]:  # Exclude source and target
                    paths_through[node] += 1

        return paths_through

    def _modularity_gain(
        self,
        node_id: str,
        from_community: str,
        to_community: str,
        community_map: dict[str, str],
        adjacency: dict[str, list[tuple[str, float]]],
        total_weight: float,
        resolution: float,
    ) -> float:
        """Calculate modularity gain for moving a node."""
        # Simplified calculation
        # Count edges to nodes in target community vs current community
        edges_to_target = 0.0
        edges_to_current = 0.0

        for neighbor, weight in adjacency.get(node_id, []):
            if community_map[neighbor] == to_community:
                edges_to_target += weight
            elif community_map[neighbor] == from_community:
                edges_to_current += weight

        gain = (edges_to_target - edges_to_current) * resolution

        return gain

    def _calculate_modularity(
        self,
        community_map: dict[str, str],
        adjacency: dict[str, list[tuple[str, float]]],
        total_weight: float,
    ) -> float:
        """Calculate modularity of community structure."""
        if total_weight == 0:
            return 0.0

        modularity = 0.0

        # For each node pair in same community
        communities = defaultdict(list)
        for node_id, comm_id in community_map.items():
            communities[comm_id].append(node_id)

        for members in communities.values():
            for i, node_a in enumerate(members):
                for node_b in members[i:]:
                    # Actual edges
                    actual_weight = 0.0
                    for neighbor, weight in adjacency.get(node_a, []):
                        if neighbor == node_b:
                            actual_weight += weight

                    # Expected edges (degree product / total weight)
                    degree_a = sum(w for _, w in adjacency.get(node_a, []))
                    degree_b = sum(w for _, w in adjacency.get(node_b, []))
                    expected = (degree_a * degree_b) / (2 * total_weight)

                    modularity += (actual_weight - expected) / total_weight

        return modularity

    def _calculate_avg_clustering(self, graph: Graph) -> float:
        """Calculate average clustering coefficient."""
        adjacency = self._build_adjacency_dict(graph.edges)

        clustering_coefficients = []

        for node in graph.nodes:
            neighbors = set(adjacency.get(node.id, []))
            k = len(neighbors)

            if k < 2:
                continue

            # Count edges between neighbors
            neighbor_edges = 0
            for n1 in neighbors:
                for n2 in neighbors:
                    if n1 < n2 and n2 in adjacency.get(n1, []):
                        neighbor_edges += 1

            max_edges = k * (k - 1) / 2
            clustering = neighbor_edges / max_edges if max_edges > 0 else 0.0
            clustering_coefficients.append(clustering)

        if not clustering_coefficients:
            return 0.0

        return sum(clustering_coefficients) / len(clustering_coefficients)

    def _find_connected_components(self, graph: Graph) -> list[set[str]]:
        """Find connected components using union-find."""
        node_ids = [n.id for n in graph.nodes]
        parent = {node_id: node_id for node_id in node_ids}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            root_x = find(x)
            root_y = find(y)
            if root_x != root_y:
                parent[root_x] = root_y

        # Union nodes connected by edges
        for edge in graph.edges:
            union(edge.source, edge.target)

        # Group by root
        components = defaultdict(set)
        for node_id in node_ids:
            root = find(node_id)
            components[root].add(node_id)

        return list(components.values())

    def _calculate_distance_metrics(
        self, graph: Graph
    ) -> tuple[int, float]:
        """Calculate diameter and average path length."""
        node_ids = [n.id for n in graph.nodes]
        adjacency = self._build_adjacency_dict(graph.edges)

        all_distances = []
        max_distance = 0

        # BFS from each node
        for source in node_ids[:50]:  # Sample for performance
            distances = self._bfs_distances(source, adjacency, node_ids)
            for dist in distances.values():
                if dist < float('inf'):
                    all_distances.append(dist)
                    max_distance = max(max_distance, dist)

        diameter = max_distance if all_distances else 0
        avg_path_length = (
            sum(all_distances) / len(all_distances) if all_distances else 0.0
        )

        return diameter, avg_path_length

    def _bfs_distances(
        self, source: str, adjacency: dict, all_nodes: list[str]
    ) -> dict[str, float]:
        """BFS to calculate distances from source."""
        distances = {node: float('inf') for node in all_nodes}
        distances[source] = 0

        queue = deque([source])
        while queue:
            current = queue.popleft()
            current_dist = distances[current]

            for neighbor in adjacency.get(current, []):
                if distances[neighbor] == float('inf'):
                    distances[neighbor] = current_dist + 1
                    queue.append(neighbor)

        return distances
