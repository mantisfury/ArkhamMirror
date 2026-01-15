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

    def find_all_paths(
        self,
        graph: Graph,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 6,
        max_paths: int = 10,
    ) -> list[GraphPath]:
        """
        Find all paths between two entities up to max_depth.

        Uses DFS with backtracking to enumerate paths.

        Args:
            graph: Graph to search
            source_entity_id: Source entity ID
            target_entity_id: Target entity ID
            max_depth: Maximum path length
            max_paths: Maximum number of paths to return

        Returns:
            List of GraphPath objects, shortest first
        """
        adjacency = self._build_adjacency_dict(graph.edges)
        all_paths: list[GraphPath] = []

        def dfs(current: str, target: str, path: list[str], visited: set[str]):
            if len(all_paths) >= max_paths:
                return

            if len(path) > max_depth + 1:
                return

            if current == target:
                # Found a path
                edges = self._get_path_edges(graph.edges, path)
                total_weight = sum(e.weight for e in edges)
                all_paths.append(GraphPath(
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    path=path.copy(),
                    edges=edges,
                    total_weight=total_weight,
                    path_length=len(path) - 1,
                ))
                return

            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, target, path, visited)
                    path.pop()
                    visited.remove(neighbor)

        # Start DFS
        dfs(source_entity_id, target_entity_id, [source_entity_id], {source_entity_id})

        # Sort by path length (shortest first)
        all_paths.sort(key=lambda p: p.path_length)

        return all_paths

    def find_weighted_path(
        self,
        graph: Graph,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 10,
        use_max_weight: bool = True,
    ) -> GraphPath | None:
        """
        Find optimal weighted path using Dijkstra's algorithm.

        Can find either maximum weight path (strongest connections)
        or minimum weight path (weakest connections).

        Args:
            graph: Graph to search
            source_entity_id: Source entity ID
            target_entity_id: Target entity ID
            max_depth: Maximum path length
            use_max_weight: If True, find path with maximum total weight

        Returns:
            GraphPath if found, None otherwise
        """
        import heapq

        # Build weighted adjacency
        adjacency = self._build_weighted_adjacency(graph.edges)

        # For max weight, we negate weights and use min-heap
        # For min weight, we use positive weights
        def get_edge_cost(weight: float) -> float:
            if use_max_weight:
                return -weight  # Negate for max-heap behavior
            return weight

        # Dijkstra's algorithm
        # heap entries: (cost, path_length, node_id, path)
        heap = [(0.0, 0, source_entity_id, [source_entity_id])]
        visited: dict[str, float] = {}

        while heap:
            cost, path_len, current, path = heapq.heappop(heap)

            if path_len > max_depth:
                continue

            if current in visited:
                continue
            visited[current] = cost

            if current == target_entity_id:
                # Found target - reconstruct path
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

            for neighbor, weight in adjacency.get(current, []):
                if neighbor not in visited:
                    new_cost = cost + get_edge_cost(weight)
                    heapq.heappush(
                        heap,
                        (new_cost, path_len + 1, neighbor, path + [neighbor])
                    )

        return None

    def find_constrained_path(
        self,
        graph: Graph,
        source_entity_id: str,
        target_entity_id: str,
        required_entities: list[str] | None = None,
        excluded_entities: list[str] | None = None,
        required_relationship_types: list[str] | None = None,
        min_edge_weight: float = 0.0,
        max_depth: int = 8,
    ) -> GraphPath | None:
        """
        Find path with constraints on nodes and edges.

        Args:
            graph: Graph to search
            source_entity_id: Source entity ID
            target_entity_id: Target entity ID
            required_entities: Entities that MUST be on the path
            excluded_entities: Entities that MUST NOT be on the path
            required_relationship_types: Only traverse these relationship types
            min_edge_weight: Minimum weight for edges to traverse
            max_depth: Maximum path length

        Returns:
            GraphPath if found, None otherwise
        """
        required = set(required_entities or [])
        excluded = set(excluded_entities or [])
        required_types = set(required_relationship_types) if required_relationship_types else None

        # Build filtered adjacency
        adjacency: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for edge in graph.edges:
            # Filter by relationship type
            if required_types and edge.relationship_type not in required_types:
                continue
            # Filter by weight
            if edge.weight < min_edge_weight:
                continue

            adjacency[edge.source].append((edge.target, edge.weight, edge.relationship_type))
            adjacency[edge.target].append((edge.source, edge.weight, edge.relationship_type))

        # Use BFS with required entity tracking
        # State: (current_node, path, required_visited)
        from collections import deque

        initial_required = required & {source_entity_id}
        queue = deque([(source_entity_id, [source_entity_id], initial_required)])
        visited: dict[tuple[str, frozenset], bool] = {(source_entity_id, frozenset(initial_required)): True}

        while queue:
            current, path, req_visited = queue.popleft()

            if len(path) > max_depth + 1:
                continue

            # Check if we found the target with all required nodes visited
            if current == target_entity_id and req_visited >= required:
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

            for neighbor, weight, rel_type in adjacency.get(current, []):
                # Skip excluded entities
                if neighbor in excluded:
                    continue

                # Skip already visited in this path
                if neighbor in path:
                    continue

                # Update required visited
                new_req = req_visited | ({neighbor} & required)
                state_key = (neighbor, frozenset(new_req))

                if state_key not in visited:
                    visited[state_key] = True
                    queue.append((neighbor, path + [neighbor], new_req))

        return None

    def find_paths_through(
        self,
        graph: Graph,
        intermediate_entity_id: str,
        max_sources: int = 5,
        max_targets: int = 5,
        max_depth: int = 3,
    ) -> list[GraphPath]:
        """
        Find paths that pass through a specific entity.

        Useful for finding what connections an entity bridges.

        Args:
            graph: Graph to search
            intermediate_entity_id: Entity that paths must pass through
            max_sources: Maximum source entities to consider
            max_targets: Maximum target entities to consider
            max_depth: Maximum hops on each side of intermediate

        Returns:
            List of paths passing through the intermediate entity
        """
        adjacency = self._build_adjacency_dict(graph.edges)

        # Find entities reachable from intermediate (potential targets)
        reachable_from: dict[str, int] = {}  # entity_id -> distance
        queue = deque([(intermediate_entity_id, 0)])
        visited = {intermediate_entity_id}

        while queue:
            current, dist = queue.popleft()
            if dist > max_depth:
                continue
            if current != intermediate_entity_id:
                reachable_from[current] = dist

            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        # Find entities that can reach intermediate (potential sources)
        # (Same search since graph is undirected)
        can_reach: dict[str, int] = reachable_from.copy()

        # Select top sources and targets by degree (most connected)
        node_degrees = {n.id: n.degree for n in graph.nodes}

        source_candidates = sorted(
            can_reach.keys(),
            key=lambda x: node_degrees.get(x, 0),
            reverse=True
        )[:max_sources]

        target_candidates = sorted(
            reachable_from.keys(),
            key=lambda x: node_degrees.get(x, 0),
            reverse=True
        )[:max_targets]

        # Find paths between sources and targets that pass through intermediate
        paths = []
        for source in source_candidates:
            for target in target_candidates:
                if source == target:
                    continue

                # Find path requiring intermediate
                path = self.find_constrained_path(
                    graph,
                    source,
                    target,
                    required_entities=[intermediate_entity_id],
                    max_depth=max_depth * 2 + 1,
                )
                if path:
                    paths.append(path)

        # Sort by total weight descending
        paths.sort(key=lambda p: p.total_weight, reverse=True)

        return paths

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

    # === Ego Network Analysis ===

    def extract_ego_network(
        self,
        graph: Graph,
        ego_entity_id: str,
        depth: int = 2,
        include_alter_alter_ties: bool = True,
    ) -> Graph:
        """
        Extract ego network centered on a specific entity.

        The ego network includes:
        - The ego (center node)
        - Alters (nodes directly connected to ego)
        - Optionally: alter-alter ties (edges between alters)
        - At depth 2: alters of alters

        Args:
            graph: Source graph
            ego_entity_id: ID of the ego (center) entity
            depth: Network depth (1 = ego + alters, 2 = includes alters of alters)
            include_alter_alter_ties: Include edges between alters

        Returns:
            New Graph containing the ego network
        """
        from .models import Graph as GraphModel, GraphNode, GraphEdge

        # Find the ego node
        ego_node = None
        for node in graph.nodes:
            if node.id == ego_entity_id or node.entity_id == ego_entity_id:
                ego_node = node
                break

        if not ego_node:
            logger.warning(f"Ego node {ego_entity_id} not found in graph")
            return GraphModel(
                project_id=graph.project_id,
                nodes=[],
                edges=[],
                metadata={"ego_id": ego_entity_id, "error": "ego_not_found"},
            )

        adjacency = self._build_weighted_adjacency(graph.edges)

        # Collect nodes at each depth
        nodes_by_depth: dict[int, set[str]] = {0: {ego_node.id}}
        all_node_ids: set[str] = {ego_node.id}

        # BFS to find nodes at each depth
        current_frontier = {ego_node.id}
        for d in range(1, depth + 1):
            next_frontier = set()
            for node_id in current_frontier:
                for neighbor_id, _ in adjacency.get(node_id, []):
                    if neighbor_id not in all_node_ids:
                        next_frontier.add(neighbor_id)
                        all_node_ids.add(neighbor_id)

            nodes_by_depth[d] = next_frontier
            current_frontier = next_frontier

        # Collect relevant nodes
        node_map = {n.id: n for n in graph.nodes}
        ego_nodes = []
        for node_id in all_node_ids:
            node = node_map.get(node_id)
            if node:
                # Clone node with ego network metadata
                ego_nodes.append(GraphNode(
                    id=node.id,
                    entity_id=node.entity_id,
                    label=node.label,
                    entity_type=node.entity_type,
                    document_count=node.document_count,
                    degree=node.degree,
                    properties={
                        **node.properties,
                        "ego_distance": next(
                            d for d, nodes in nodes_by_depth.items() if node_id in nodes
                        ),
                        "is_ego": node_id == ego_node.id,
                    },
                ))

        # Collect edges
        ego_edges = []
        edge_set = set()  # Track unique edges

        for edge in graph.edges:
            source_in = edge.source in all_node_ids
            target_in = edge.target in all_node_ids

            # Both endpoints must be in the ego network
            if not (source_in and target_in):
                continue

            # Check if this is an alter-alter tie
            source_is_ego = edge.source == ego_node.id
            target_is_ego = edge.target == ego_node.id
            is_ego_tie = source_is_ego or target_is_ego
            is_alter_alter = not is_ego_tie

            # Include alter-alter ties only if requested
            if is_alter_alter and not include_alter_alter_ties:
                continue

            # Avoid duplicates
            edge_key = tuple(sorted([edge.source, edge.target]))
            if edge_key in edge_set:
                continue
            edge_set.add(edge_key)

            ego_edges.append(GraphEdge(
                source=edge.source,
                target=edge.target,
                relationship_type=edge.relationship_type,
                weight=edge.weight,
                co_occurrence_count=edge.co_occurrence_count,
                document_ids=edge.document_ids,
                properties={
                    **edge.properties,
                    "is_ego_tie": is_ego_tie,
                },
            ))

        return GraphModel(
            project_id=graph.project_id,
            nodes=ego_nodes,
            edges=ego_edges,
            metadata={
                "ego_id": ego_entity_id,
                "ego_label": ego_node.label,
                "depth": depth,
                "include_alter_alter_ties": include_alter_alter_ties,
                "node_count": len(ego_nodes),
                "edge_count": len(ego_edges),
                "nodes_by_depth": {d: len(nodes) for d, nodes in nodes_by_depth.items()},
            },
        )

    def calculate_ego_metrics(
        self,
        graph: Graph,
        ego_entity_id: str,
    ) -> dict[str, Any]:
        """
        Calculate ego-centric network metrics.

        Metrics include:
        - Effective size: Ego's network size accounting for redundancy
        - Efficiency: Effective size normalized by actual size
        - Constraint: Degree to which ego's network is controlled by others
        - Hierarchy: Concentration of constraint across contacts

        Args:
            graph: Graph to analyze (can be full graph or ego network)
            ego_entity_id: ID of the ego entity

        Returns:
            Dictionary of ego network metrics
        """
        # Find ego node
        ego_node_id = None
        for node in graph.nodes:
            if node.id == ego_entity_id or node.entity_id == ego_entity_id:
                ego_node_id = node.id
                break

        if not ego_node_id:
            return {
                "error": "ego_not_found",
                "ego_id": ego_entity_id,
            }

        adjacency = self._build_weighted_adjacency(graph.edges)

        # Get direct alters (1-hop neighbors)
        alters = []
        for neighbor_id, weight in adjacency.get(ego_node_id, []):
            alters.append(neighbor_id)

        n_alters = len(alters)

        if n_alters == 0:
            return {
                "ego_id": ego_entity_id,
                "network_size": 0,
                "effective_size": 0.0,
                "efficiency": 0.0,
                "constraint": 1.0,
                "hierarchy": 0.0,
                "density": 0.0,
                "avg_tie_strength": 0.0,
            }

        # Calculate structural holes metrics
        structural_holes = self.calculate_structural_holes(graph, ego_entity_id)

        # Network density among alters
        alter_set = set(alters)
        alter_edges = 0
        for alter in alters:
            for neighbor, _ in adjacency.get(alter, []):
                if neighbor in alter_set and neighbor != alter:
                    alter_edges += 1

        alter_edges //= 2  # Each edge counted twice
        max_alter_edges = n_alters * (n_alters - 1) / 2 if n_alters > 1 else 1
        density = alter_edges / max_alter_edges if max_alter_edges > 0 else 0.0

        # Average tie strength to ego
        tie_strengths = [w for _, w in adjacency.get(ego_node_id, [])]
        avg_tie_strength = sum(tie_strengths) / len(tie_strengths) if tie_strengths else 0.0

        # Identify structural position types
        broker_score = structural_holes.get("effective_size", 0) / max(1, n_alters)

        return {
            "ego_id": ego_entity_id,
            "network_size": n_alters,
            "effective_size": structural_holes.get("effective_size", 0.0),
            "efficiency": structural_holes.get("efficiency", 0.0),
            "constraint": structural_holes.get("constraint", 1.0),
            "hierarchy": structural_holes.get("hierarchy", 0.0),
            "density": density,
            "avg_tie_strength": avg_tie_strength,
            "broker_score": broker_score,
            "alter_alter_ties": alter_edges,
            "is_bridge": broker_score > 0.7 and density < 0.3,
            "is_coordinator": density > 0.7,
        }

    def calculate_structural_holes(
        self,
        graph: Graph,
        entity_id: str,
    ) -> dict[str, float]:
        """
        Calculate Burt's structural holes metrics.

        Structural holes are gaps between non-redundant contacts.
        Entities that bridge structural holes have information advantages.

        Metrics:
        - Effective Size: Number of alters minus redundancy
        - Efficiency: Effective size / actual size
        - Constraint: Sum of constraints from each alter
        - Hierarchy: Concentration of constraint

        Based on: Burt, R. S. (1992). Structural Holes.

        Args:
            graph: Graph to analyze
            entity_id: ID of the focal entity

        Returns:
            Dictionary of structural holes metrics
        """
        # Find node
        node_id = None
        for node in graph.nodes:
            if node.id == entity_id or node.entity_id == entity_id:
                node_id = node.id
                break

        if not node_id:
            return {
                "effective_size": 0.0,
                "efficiency": 0.0,
                "constraint": 1.0,
                "hierarchy": 0.0,
            }

        adjacency = self._build_weighted_adjacency(graph.edges)

        # Get alters
        alters = []
        alter_weights = {}
        total_weight = 0.0

        for neighbor_id, weight in adjacency.get(node_id, []):
            alters.append(neighbor_id)
            alter_weights[neighbor_id] = weight
            total_weight += weight

        n_alters = len(alters)

        if n_alters == 0:
            return {
                "effective_size": 0.0,
                "efficiency": 0.0,
                "constraint": 1.0,
                "hierarchy": 0.0,
            }

        # Normalize weights to proportions
        p = {}  # Proportion of tie to each alter
        for alter_id in alters:
            p[alter_id] = alter_weights[alter_id] / total_weight if total_weight > 0 else 0.0

        # Calculate redundancy for each alter
        # Redundancy = sum of marginal strength with each alter through third parties
        redundancy = {}
        for j in alters:
            r_j = 0.0
            # For each other alter q
            for q in alters:
                if q == j:
                    continue
                # Proportion of i's relations invested in q
                p_iq = p[q]
                # Marginal strength of q's relation with j
                # (proportion of q's ties that go to j)
                q_neighbors = adjacency.get(q, [])
                q_total = sum(w for _, w in q_neighbors)
                m_qj = 0.0
                for neighbor, weight in q_neighbors:
                    if neighbor == j:
                        m_qj = weight / q_total if q_total > 0 else 0.0
                        break
                r_j += p_iq * m_qj
            redundancy[j] = r_j

        # Effective size = n - sum of redundancies
        total_redundancy = sum(redundancy.values())
        effective_size = n_alters - total_redundancy

        # Efficiency = effective_size / n
        efficiency = effective_size / n_alters if n_alters > 0 else 0.0

        # Constraint = sum of (p_ij + sum_q(p_iq * p_qj))^2
        constraint = 0.0
        individual_constraints = {}

        for j in alters:
            # Direct proportion
            c_j = p[j]

            # Indirect through q
            for q in alters:
                if q == j:
                    continue
                # p_iq * proportion of q's ties to j
                p_iq = p[q]
                q_neighbors = adjacency.get(q, [])
                q_total = sum(w for _, w in q_neighbors)
                p_qj = 0.0
                for neighbor, weight in q_neighbors:
                    if neighbor == j:
                        p_qj = weight / q_total if q_total > 0 else 0.0
                        break
                c_j += p_iq * p_qj

            individual_constraints[j] = c_j * c_j
            constraint += c_j * c_j

        # Hierarchy = concentration of constraint
        # (Coleman-Theil index of constraint concentration)
        if constraint > 0 and n_alters > 1:
            # Normalize individual constraints
            c_values = list(individual_constraints.values())
            c_sum = sum(c_values)
            if c_sum > 0:
                # Calculate hierarchy as concentration
                n = len(c_values)
                avg_c = c_sum / n
                sum_sq = sum((c - avg_c) ** 2 for c in c_values)
                hierarchy = sum_sq / (n * avg_c * avg_c) if avg_c > 0 else 0.0
                # Normalize to 0-1
                hierarchy = min(1.0, hierarchy / n)
            else:
                hierarchy = 0.0
        else:
            hierarchy = 0.0

        return {
            "effective_size": effective_size,
            "efficiency": efficiency,
            "constraint": constraint,
            "hierarchy": hierarchy,
            "redundancy": total_redundancy,
            "individual_constraints": individual_constraints,
        }
