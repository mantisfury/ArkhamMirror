"""
Test script for Graph Shard functionality.

Tests all major features:
- Graph building
- Path finding
- Centrality calculations
- Community detection
- Graph export
- Statistics calculation
"""

import asyncio
import sys
from datetime import datetime

# Mock Frame and services
class MockEventBus:
    def __init__(self):
        self.events = []

    async def subscribe(self, event_name, handler):
        pass

    async def unsubscribe(self, event_name, handler):
        pass

    async def publish(self, event_name, data):
        self.events.append((event_name, data))
        print(f"Event published: {event_name}")


class MockFrame:
    def __init__(self):
        self.event_bus = MockEventBus()

    def get_service(self, name):
        if name == "events":
            return self.event_bus
        return None


async def test_graph_shard():
    """Test the Graph Shard."""
    print("=" * 60)
    print("Graph Shard Test Suite")
    print("=" * 60)

    # Import shard components
    from arkham_shard_graph import GraphShard
    from arkham_shard_graph.models import (
        Graph, GraphNode, GraphEdge, RelationshipType,
        ExportFormat
    )

    # Create shard
    print("\n1. Initializing Graph Shard...")
    shard = GraphShard()
    frame = MockFrame()

    await shard.initialize(frame)
    print("   SUCCESS: Shard initialized")

    # Test graph building
    print("\n2. Testing Graph Building...")
    try:
        graph = await shard.build_graph(
            project_id="test-project",
            min_co_occurrence=1,
        )
        print(f"   SUCCESS: Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test statistics
    print("\n3. Testing Graph Statistics...")
    try:
        stats = await shard.calculate_statistics("test-project")
        print(f"   SUCCESS: Calculated statistics")
        print(f"   - Nodes: {stats.node_count}")
        print(f"   - Edges: {stats.edge_count}")
        print(f"   - Density: {stats.density:.4f}")
        print(f"   - Avg Degree: {stats.avg_degree:.2f}")
        print(f"   - Connected Components: {stats.connected_components}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test centrality calculations
    print("\n4. Testing Centrality Calculations...")

    # Degree centrality
    try:
        degree_results = await shard.calculate_centrality(
            project_id="test-project",
            metric="degree",
            limit=5,
        )
        print(f"   SUCCESS: Degree centrality (top 5)")
        for i, result in enumerate(degree_results[:3], 1):
            print(f"   {i}. {result.label} (score: {result.score:.4f})")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # PageRank
    try:
        pagerank_results = await shard.calculate_centrality(
            project_id="test-project",
            metric="pagerank",
            limit=5,
        )
        print(f"   SUCCESS: PageRank centrality (top 5)")
        for i, result in enumerate(pagerank_results[:3], 1):
            print(f"   {i}. {result.label} (score: {result.score:.6f})")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test path finding
    print("\n5. Testing Path Finding...")
    if len(graph.nodes) >= 2:
        try:
            source = graph.nodes[0].entity_id
            target = graph.nodes[-1].entity_id

            path = await shard.find_path(
                project_id="test-project",
                source=source,
                target=target,
                max_depth=6,
            )

            if path:
                print(f"   SUCCESS: Found path from {source} to {target}")
                print(f"   - Path length: {path.path_length}")
                print(f"   - Total weight: {path.total_weight:.4f}")
                print(f"   - Path: {' -> '.join(path.path[:4])}...")
            else:
                print(f"   INFO: No path found (disconnected graph)")
        except Exception as e:
            print(f"   ERROR: {e}")
            return False
    else:
        print("   SKIPPED: Not enough nodes")

    # Test community detection
    print("\n6. Testing Community Detection...")
    try:
        communities, modularity = await shard.detect_communities(
            project_id="test-project",
            min_size=2,
            resolution=1.0,
        )
        print(f"   SUCCESS: Detected {len(communities)} communities")
        print(f"   - Modularity: {modularity:.4f}")
        for i, community in enumerate(communities[:3], 1):
            print(f"   Community {i}: {community.size} entities, density: {community.density:.4f}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test neighbors
    print("\n7. Testing Neighbor Queries...")
    if len(graph.nodes) > 0:
        try:
            entity_id = graph.nodes[0].entity_id
            neighbors = await shard.get_neighbors(
                entity_id=entity_id,
                project_id="test-project",
                depth=1,
                limit=5,
            )
            print(f"   SUCCESS: Found {neighbors['neighbor_count']} neighbors for {entity_id}")
            for neighbor in neighbors['neighbors'][:3]:
                print(f"   - {neighbor['label']} (weight: {neighbor['weight']:.4f})")
        except Exception as e:
            print(f"   ERROR: {e}")
            return False
    else:
        print("   SKIPPED: No nodes")

    # Test graph export
    print("\n8. Testing Graph Export...")

    # JSON export
    try:
        json_data = await shard.export_graph(
            project_id="test-project",
            format="json",
            include_metadata=True,
        )
        print(f"   SUCCESS: JSON export ({len(json_data)} bytes)")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # GraphML export
    try:
        graphml_data = await shard.export_graph(
            project_id="test-project",
            format="graphml",
            include_metadata=True,
        )
        print(f"   SUCCESS: GraphML export ({len(graphml_data)} bytes)")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # GEXF export
    try:
        gexf_data = await shard.export_graph(
            project_id="test-project",
            format="gexf",
            include_metadata=True,
        )
        print(f"   SUCCESS: GEXF export ({len(gexf_data)} bytes)")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test shutdown
    print("\n9. Testing Shutdown...")
    try:
        await shard.shutdown()
        print("   SUCCESS: Shard shut down cleanly")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("All Tests Passed!")
    print("=" * 60)
    print("\nGraph Shard Features:")
    print("  - Graph building from entities and co-occurrences")
    print("  - Path finding (BFS shortest path)")
    print("  - Centrality metrics (degree, betweenness, PageRank)")
    print("  - Community detection (Louvain-style)")
    print("  - Neighbor queries (1-hop and 2-hop)")
    print("  - Graph export (JSON, GraphML, GEXF)")
    print("  - Comprehensive graph statistics")
    print("  - Subgraph extraction")
    print("  - Graph filtering by entity type, degree, weight")
    print("\nAPI Endpoints Available:")
    print("  - POST /api/graph/build")
    print("  - GET /api/graph/{project_id}")
    print("  - GET /api/graph/entity/{entity_id}")
    print("  - POST /api/graph/path")
    print("  - GET /api/graph/centrality/{project_id}")
    print("  - POST /api/graph/communities")
    print("  - GET /api/graph/neighbors/{entity_id}")
    print("  - POST /api/graph/export")
    print("  - GET /api/graph/stats")
    print("  - POST /api/graph/filter")

    return True


if __name__ == "__main__":
    result = asyncio.run(test_graph_shard())
    sys.exit(0 if result else 1)
