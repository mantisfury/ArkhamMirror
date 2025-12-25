# Graph Shard Usage Guide

Complete guide to using the Graph Shard for entity relationship analysis.

## Table of Contents

- [Quick Start](#quick-start)
- [Graph Building](#graph-building)
- [Path Finding](#path-finding)
- [Centrality Analysis](#centrality-analysis)
- [Community Detection](#community-detection)
- [Graph Export](#graph-export)
- [API Reference](#api-reference)
- [Integration Examples](#integration-examples)

## Quick Start

### Installation

The Graph Shard is automatically discovered by ArkhamFrame via entry points:

```bash
pip install arkham-shard-graph
```

### Basic Usage

```python
from arkham_frame import ArkhamFrame

# Initialize frame and load shard
frame = ArkhamFrame()
await frame.load_shard("graph")

# Get the graph shard
graph_shard = frame.get_shard("graph")

# Build graph
graph = await graph_shard.build_graph(
    project_id="my-project",
    min_co_occurrence=2,
)

print(f"Built graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
```

## Graph Building

### Build Graph from Documents

```python
# Build graph with all entities
graph = await graph_shard.build_graph(
    project_id="investigation-001",
    min_co_occurrence=1,
)

# Build graph with specific documents
graph = await graph_shard.build_graph(
    project_id="investigation-001",
    document_ids=["doc1", "doc2", "doc3"],
    min_co_occurrence=2,
)

# Build graph with entity type filter
graph = await graph_shard.build_graph(
    project_id="investigation-001",
    entity_types=["person", "organization"],
    min_co_occurrence=2,
)
```

### Filter Existing Graph

```python
from arkham_shard_graph.models import FilterRequest

# Filter by entity type and minimum degree
filtered_graph = graph_shard.builder.filter_graph(
    graph=graph,
    entity_types=["person", "organization"],
    min_degree=3,  # Only entities with 3+ connections
    min_edge_weight=0.5,
)

# Filter by relationship type
filtered_graph = graph_shard.builder.filter_graph(
    graph=graph,
    relationship_types=["works_for", "affiliated_with"],
)
```

### Extract Subgraph

```python
# Extract 2-hop neighborhood around entity
subgraph = graph_shard.builder.extract_subgraph(
    graph=graph,
    entity_id="person-123",
    depth=2,
    max_nodes=100,
    min_weight=0.3,
)

print(f"Subgraph: {len(subgraph.nodes)} nodes, {len(subgraph.edges)} edges")
```

## Path Finding

### Find Shortest Path

```python
# Find connection between two entities
path = await graph_shard.find_path(
    project_id="investigation-001",
    source="person-123",
    target="org-456",
    max_depth=6,
)

if path:
    print(f"Found path of length {path.path_length}")
    print(f"Path: {' -> '.join(path.path)}")
    print(f"Total weight: {path.total_weight}")

    # Examine edges along path
    for edge in path.edges:
        print(f"  {edge.source} --[{edge.relationship_type}]--> {edge.target}")
else:
    print("No path found (entities not connected)")
```

### API Usage

```bash
curl -X POST http://localhost:8000/api/graph/path \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "investigation-001",
    "source_entity_id": "person-123",
    "target_entity_id": "org-456",
    "max_depth": 6
  }'
```

## Centrality Analysis

### Calculate Centrality Metrics

```python
# Degree centrality (most connected)
degree_results = await graph_shard.calculate_centrality(
    project_id="investigation-001",
    metric="degree",
    limit=20,
)

for result in degree_results[:10]:
    print(f"{result.rank}. {result.label} ({result.entity_type})")
    print(f"   Score: {result.score:.4f}")

# PageRank (most influential)
pagerank_results = await graph_shard.calculate_centrality(
    project_id="investigation-001",
    metric="pagerank",
    limit=20,
)

# Betweenness centrality (most important connectors)
betweenness_results = await graph_shard.calculate_centrality(
    project_id="investigation-001",
    metric="betweenness",
    limit=20,
)
```

### API Usage

```bash
# Get PageRank centrality
curl "http://localhost:8000/api/graph/centrality/investigation-001?metric=pagerank&limit=20"

# Get all centrality metrics
curl "http://localhost:8000/api/graph/centrality/investigation-001?metric=all&limit=50"
```

## Community Detection

### Detect Communities (Louvain Algorithm)

```python
# Detect communities
communities, modularity = await graph_shard.detect_communities(
    project_id="investigation-001",
    min_size=3,
    resolution=1.0,
)

print(f"Found {len(communities)} communities")
print(f"Modularity score: {modularity:.4f}")

for i, community in enumerate(communities, 1):
    print(f"\nCommunity {i}:")
    print(f"  Size: {community.size} entities")
    print(f"  Density: {community.density:.4f}")
    print(f"  Internal edges: {community.internal_edges}")
    print(f"  External edges: {community.external_edges}")

    # Get entity details for this community
    entity_labels = []
    for entity_id in community.entity_ids[:5]:
        # Look up entity in graph
        for node in graph.nodes:
            if node.entity_id == entity_id:
                entity_labels.append(node.label)
                break

    print(f"  Sample entities: {', '.join(entity_labels)}")
```

### API Usage

```bash
curl -X POST http://localhost:8000/api/graph/communities \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "investigation-001",
    "algorithm": "louvain",
    "min_community_size": 3,
    "resolution": 1.0
  }'
```

## Graph Export

### Export to Multiple Formats

```python
# Export as JSON
json_data = await graph_shard.export_graph(
    project_id="investigation-001",
    format="json",
    include_metadata=True,
)

# Save to file
with open("graph.json", "w") as f:
    f.write(json_data)

# Export as GraphML (for Gephi, Cytoscape)
graphml_data = await graph_shard.export_graph(
    project_id="investigation-001",
    format="graphml",
    include_metadata=True,
)

with open("graph.graphml", "w") as f:
    f.write(graphml_data)

# Export as GEXF (Gephi native format)
gexf_data = await graph_shard.export_graph(
    project_id="investigation-001",
    format="gexf",
    include_metadata=True,
)

with open("graph.gexf", "w") as f:
    f.write(gexf_data)
```

### Export with Filters

```python
# Export filtered graph
filtered_export = await graph_shard.export_graph(
    project_id="investigation-001",
    format="graphml",
    include_metadata=True,
)

# The builder's filter_graph method can be used before export
filtered = graph_shard.builder.filter_graph(
    graph=original_graph,
    entity_types=["person", "organization"],
    min_edge_weight=0.5,
)

# Then export the filtered graph
exporter = graph_shard.exporter
from arkham_shard_graph.models import ExportFormat
data = exporter.export_graph(filtered, ExportFormat.GRAPHML, True)
```

### API Usage

```bash
curl -X POST http://localhost:8000/api/graph/export \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "investigation-001",
    "format": "graphml",
    "include_metadata": true,
    "filter": {
      "entity_types": ["person", "organization"],
      "min_edge_weight": 0.5
    }
  }' > graph.graphml
```

## Graph Statistics

### Calculate Comprehensive Statistics

```python
# Get graph statistics
stats = await graph_shard.calculate_statistics(
    project_id="investigation-001"
)

print(f"Graph Statistics:")
print(f"  Nodes: {stats.node_count}")
print(f"  Edges: {stats.edge_count}")
print(f"  Density: {stats.density:.4f}")
print(f"  Average degree: {stats.avg_degree:.2f}")
print(f"  Average clustering: {stats.avg_clustering:.4f}")
print(f"  Connected components: {stats.connected_components}")
print(f"  Diameter: {stats.diameter}")
print(f"  Average path length: {stats.avg_path_length:.2f}")

print(f"\nEntity type distribution:")
for entity_type, count in stats.entity_type_distribution.items():
    print(f"  {entity_type}: {count}")

print(f"\nRelationship type distribution:")
for rel_type, count in stats.relationship_type_distribution.items():
    print(f"  {rel_type}: {count}")
```

### API Usage

```bash
curl "http://localhost:8000/api/graph/stats?project_id=investigation-001"
```

## Neighbor Queries

### Get Entity Neighbors

```python
# Get 1-hop neighbors
neighbors = await graph_shard.get_neighbors(
    entity_id="person-123",
    project_id="investigation-001",
    depth=1,
    limit=50,
)

print(f"Entity has {neighbors['neighbor_count']} neighbors")

for neighbor in neighbors['neighbors']:
    print(f"  {neighbor['label']} ({neighbor['entity_type']})")
    print(f"    Weight: {neighbor['weight']:.4f}")
    print(f"    Hops: {neighbor['hop_distance']}")

# Get 2-hop neighbors (friends of friends)
extended = await graph_shard.get_neighbors(
    entity_id="person-123",
    project_id="investigation-001",
    depth=2,
    limit=100,
)
```

### API Usage

```bash
curl "http://localhost:8000/api/graph/neighbors/person-123?project_id=investigation-001&depth=2&limit=50"
```

## API Reference

### POST /api/graph/build

Build entity relationship graph.

**Request:**
```json
{
  "project_id": "investigation-001",
  "document_ids": ["doc1", "doc2"],
  "entity_types": ["person", "organization"],
  "min_co_occurrence": 2,
  "include_temporal": false
}
```

**Response:**
```json
{
  "project_id": "investigation-001",
  "node_count": 150,
  "edge_count": 342,
  "graph_id": "graph-investigation-001",
  "build_time_ms": 1234.5
}
```

### GET /api/graph/{project_id}

Get complete graph.

**Response:**
```json
{
  "project_id": "investigation-001",
  "nodes": [...],
  "edges": [...],
  "metadata": {...}
}
```

### GET /api/graph/entity/{entity_id}

Get entity-centric subgraph.

**Query Parameters:**
- `project_id`: Project ID (required)
- `depth`: Maximum distance (default: 2)
- `max_nodes`: Maximum nodes (default: 100)
- `min_weight`: Minimum edge weight (default: 0.0)

### POST /api/graph/path

Find shortest path between entities.

### GET /api/graph/centrality/{project_id}

Calculate centrality metrics.

**Query Parameters:**
- `metric`: "degree", "betweenness", "pagerank", "all"
- `limit`: Top N results (default: 50)

### POST /api/graph/communities

Detect communities.

### GET /api/graph/neighbors/{entity_id}

Get entity neighbors.

### POST /api/graph/export

Export graph.

### GET /api/graph/stats

Get graph statistics.

### POST /api/graph/filter

Filter graph by criteria.

## Integration Examples

### Integration with ACH Shard

```python
# Build graph from ACH analysis
ach_shard = frame.get_shard("ach")
graph_shard = frame.get_shard("graph")

# Get hypotheses
hypotheses = await ach_shard.get_hypotheses(project_id="investigation-001")

# Build graph for entities in hypothesis evidence
evidence_entities = []
for hyp in hypotheses:
    for evidence in hyp.evidence:
        evidence_entities.extend(evidence.entity_ids)

# Build focused graph
graph = await graph_shard.build_graph(
    project_id="investigation-001",
    entity_types=["person", "organization"],
    min_co_occurrence=2,
)

# Find key connectors (betweenness centrality)
connectors = await graph_shard.calculate_centrality(
    project_id="investigation-001",
    metric="betweenness",
    limit=10,
)

# These are entities that connect different parts of the narrative
print("Key connectors in investigation:")
for connector in connectors:
    print(f"  {connector.label} (score: {connector.score:.4f})")
```

### Integration with Timeline Shard

```python
# Build temporal graph
timeline_shard = frame.get_shard("timeline")
graph_shard = frame.get_shard("graph")

# Get timeline events
events = await timeline_shard.get_events(
    project_id="investigation-001",
    start_date="2020-01-01",
    end_date="2023-12-31",
)

# Build graph for entities active in timeline
entity_ids = []
for event in events:
    entity_ids.extend(event.entity_ids)

# Analyze how relationships evolved over time
graph_early = await graph_shard.build_graph(
    project_id="investigation-001",
    document_ids=docs_2020_2021,
)

graph_late = await graph_shard.build_graph(
    project_id="investigation-001",
    document_ids=docs_2022_2023,
)

# Compare community structures
communities_early, _ = await graph_shard.detect_communities(
    project_id="early-period"
)

communities_late, _ = await graph_shard.detect_communities(
    project_id="late-period"
)
```

### Investigative Workflow

```python
async def investigate_connections(project_id: str, person_of_interest: str):
    """
    Investigate connections of a person of interest.
    """
    graph_shard = frame.get_shard("graph")

    # Build full graph
    graph = await graph_shard.build_graph(project_id=project_id)

    # Get immediate connections
    neighbors = await graph_shard.get_neighbors(
        entity_id=person_of_interest,
        project_id=project_id,
        depth=1,
    )

    print(f"\n{person_of_interest} is connected to {neighbors['neighbor_count']} entities:")
    for neighbor in neighbors['neighbors'][:10]:
        print(f"  - {neighbor['label']} ({neighbor['entity_type']})")

    # Find paths to known entities of interest
    known_entities = ["suspect-1", "suspect-2", "org-123"]

    for target in known_entities:
        path = await graph_shard.find_path(
            project_id=project_id,
            source=person_of_interest,
            target=target,
            max_depth=4,
        )

        if path:
            print(f"\nPath to {target} (length {path.path_length}):")
            print(f"  {' -> '.join(path.path)}")

    # Identify their community
    communities, modularity = await graph_shard.detect_communities(
        project_id=project_id,
        min_size=3,
    )

    for community in communities:
        if person_of_interest in community.entity_ids:
            print(f"\n{person_of_interest} belongs to community of {community.size} entities")
            print(f"  Community density: {community.density:.4f}")
            break

    # Export subgraph for visualization
    subgraph = graph_shard.builder.extract_subgraph(
        graph=graph,
        entity_id=person_of_interest,
        depth=2,
        max_nodes=50,
    )

    graphml_data = graph_shard.exporter.export_graph(
        graph=subgraph,
        format=ExportFormat.GRAPHML,
    )

    with open(f"{person_of_interest}_network.graphml", "w") as f:
        f.write(graphml_data)

    print(f"\nSubgraph exported to {person_of_interest}_network.graphml")
    print(f"Open in Gephi for visualization")
```

## Best Practices

### Performance Optimization

1. **Use appropriate min_co_occurrence**: Higher values create sparser graphs
2. **Filter early**: Apply entity type and document filters during build
3. **Limit subgraph size**: Use max_nodes parameter for large graphs
4. **Cache graphs**: Storage service automatically caches in memory

### Graph Analysis Tips

1. **Start with overview statistics**: Understand graph structure first
2. **Use centrality for key entities**: Different metrics reveal different aspects
3. **Community detection for clustering**: Find groups of related entities
4. **Export for visualization**: Use Gephi/Cytoscape for visual exploration
5. **Combine with other shards**: Graph + Timeline + ACH = powerful analysis

### Common Patterns

```python
# Pattern 1: Find influencers
pagerank = await graph_shard.calculate_centrality(
    project_id=pid,
    metric="pagerank",
    limit=20,
)

# Pattern 2: Find connectors
betweenness = await graph_shard.calculate_centrality(
    project_id=pid,
    metric="betweenness",
    limit=20,
)

# Pattern 3: Find hubs (most connections)
degree = await graph_shard.calculate_centrality(
    project_id=pid,
    metric="degree",
    limit=20,
)

# Pattern 4: Explore unknown connections
path = await graph_shard.find_path(
    project_id=pid,
    source=known_entity,
    target=unknown_entity,
)

# Pattern 5: Map communities
communities, modularity = await graph_shard.detect_communities(
    project_id=pid,
    min_size=5,
)
```
