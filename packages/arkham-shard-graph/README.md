# ArkhamFrame Graph Shard

Entity relationship visualization and graph analysis for ArkhamMirror.

## Features

- **Entity Graph Building**: Construct relationship graphs from documents and entities
- **Graph Queries**: Shortest path, connected components, neighborhood exploration
- **Centrality Metrics**: Degree, betweenness, PageRank analysis
- **Community Detection**: Identify clusters and communities in entity networks
- **Graph Export**: Export graphs in multiple formats (JSON, GraphML, GEXF)
- **Subgraph Extraction**: Extract entity-centric subgraphs for focused analysis
- **Path Finding**: Find connections between entities across documents
- **Graph Statistics**: Comprehensive graph metrics and analysis

## Installation

```bash
pip install arkham-shard-graph
```

The shard is automatically discovered by ArkhamFrame via entry points.

## API Endpoints

### POST /api/graph/build
Build entity relationship graph from documents.

**Request:**
```json
{
  "project_id": "proj123",
  "document_ids": ["doc1", "doc2"],
  "entity_types": ["person", "organization"],
  "min_co_occurrence": 2,
  "include_temporal": true
}
```

**Response:**
```json
{
  "project_id": "proj123",
  "node_count": 150,
  "edge_count": 342,
  "graph_id": "graph-abc123",
  "build_time_ms": 1234.5
}
```

### GET /api/graph/{project_id}
Get complete graph for a project.

**Response:**
```json
{
  "project_id": "proj123",
  "nodes": [
    {
      "id": "node1",
      "entity_id": "ent123",
      "label": "John Doe",
      "entity_type": "person",
      "document_count": 15,
      "properties": {}
    }
  ],
  "edges": [
    {
      "source": "node1",
      "target": "node2",
      "relationship_type": "works_for",
      "weight": 0.85,
      "document_ids": ["doc1", "doc2"]
    }
  ],
  "metadata": {
    "created_at": "2024-01-15T10:30:00",
    "entity_count": 150,
    "relationship_count": 342
  }
}
```

### GET /api/graph/entity/{entity_id}
Get subgraph centered on an entity.

**Query Parameters:**
- `depth`: Maximum distance from entity (default: 2)
- `max_nodes`: Maximum nodes to return (default: 100)
- `min_weight`: Minimum edge weight (default: 0.0)

### POST /api/graph/path
Find shortest path between two entities.

**Request:**
```json
{
  "project_id": "proj123",
  "source_entity_id": "ent1",
  "target_entity_id": "ent2",
  "max_depth": 6
}
```

**Response:**
```json
{
  "path_found": true,
  "path_length": 3,
  "path": ["ent1", "ent5", "ent8", "ent2"],
  "edges": [
    {
      "source": "ent1",
      "target": "ent5",
      "relationship_type": "mentioned_with",
      "weight": 0.8
    }
  ],
  "total_weight": 2.4
}
```

### GET /api/graph/centrality/{project_id}
Calculate centrality metrics.

**Query Parameters:**
- `metric`: "degree", "betweenness", "pagerank", "all" (default: "all")
- `limit`: Top N entities to return (default: 50)

**Response:**
```json
{
  "project_id": "proj123",
  "metric": "pagerank",
  "results": [
    {
      "entity_id": "ent123",
      "label": "John Doe",
      "score": 0.0342,
      "rank": 1
    }
  ],
  "calculated_at": "2024-01-15T10:30:00"
}
```

### POST /api/graph/communities
Detect communities in graph.

**Request:**
```json
{
  "project_id": "proj123",
  "algorithm": "louvain",
  "min_community_size": 3,
  "resolution": 1.0
}
```

**Response:**
```json
{
  "project_id": "proj123",
  "community_count": 12,
  "communities": [
    {
      "id": "comm1",
      "size": 25,
      "entity_ids": ["ent1", "ent2", "ent3"],
      "density": 0.68,
      "description": "Political figures group"
    }
  ],
  "modularity": 0.72
}
```

### GET /api/graph/neighbors/{entity_id}
Get neighbors of an entity.

**Query Parameters:**
- `project_id`: Project ID (required)
- `depth`: Hop distance (1 or 2, default: 1)
- `min_weight`: Minimum edge weight (default: 0.0)
- `limit`: Maximum neighbors (default: 50)

### POST /api/graph/export
Export graph in various formats.

**Request:**
```json
{
  "project_id": "proj123",
  "format": "graphml",
  "include_metadata": true,
  "filter": {
    "entity_types": ["person", "organization"],
    "min_edge_weight": 0.3
  }
}
```

**Response:**
```json
{
  "format": "graphml",
  "data": "<?xml version=\"1.0\"...>",
  "node_count": 150,
  "edge_count": 342,
  "file_size_bytes": 52341
}
```

**Supported Formats:**
- `json`: Native JSON format
- `graphml`: XML-based format (Gephi, Cytoscape compatible)
- `gexf`: Graph Exchange XML Format (Gephi native)

### GET /api/graph/stats
Get comprehensive graph statistics.

**Query Parameters:**
- `project_id`: Project ID (required)

**Response:**
```json
{
  "project_id": "proj123",
  "node_count": 150,
  "edge_count": 342,
  "density": 0.0305,
  "avg_degree": 4.56,
  "avg_clustering": 0.42,
  "connected_components": 3,
  "diameter": 8,
  "avg_path_length": 3.2,
  "entity_type_distribution": {
    "person": 85,
    "organization": 45,
    "location": 20
  },
  "relationship_type_distribution": {
    "works_for": 120,
    "mentioned_with": 180,
    "located_in": 42
  }
}
```

### POST /api/graph/filter
Filter graph by criteria.

**Request:**
```json
{
  "project_id": "proj123",
  "entity_types": ["person", "organization"],
  "min_degree": 3,
  "min_edge_weight": 0.5,
  "relationship_types": ["works_for", "affiliated_with"],
  "document_ids": ["doc1", "doc2"]
}
```

## Usage from Other Shards

```python
# Get the graph shard
graph_shard = frame.get_shard("graph")

# Build graph
await graph_shard.build_graph(
    project_id="proj123",
    document_ids=["doc1", "doc2"],
)

# Find path
path = await graph_shard.find_path(
    project_id="proj123",
    source="ent1",
    target="ent2",
)

# Calculate centrality
centrality = await graph_shard.calculate_centrality(
    project_id="proj123",
    metric="pagerank",
)

# Get neighbors
neighbors = await graph_shard.get_neighbors(
    entity_id="ent123",
    depth=2,
)
```

## Architecture

### Graph Builder
- Constructs entity relationship graphs from document co-occurrences
- Supports multiple relationship types
- Configurable edge weighting strategies

### Graph Algorithms
- **Path Finding**: BFS-based shortest path
- **Centrality**: Degree, betweenness, PageRank
- **Community Detection**: Louvain-style modularity optimization
- **Connected Components**: Union-find algorithm

### Export Formats
- **JSON**: Native format with full metadata
- **GraphML**: XML format for Gephi/Cytoscape
- **GEXF**: Gephi Exchange Format

### Graph Storage
- In-memory graph structures
- Optional persistence via Frame database
- Efficient neighbor lookups via adjacency lists

## Dependencies

- `arkham-frame>=0.1.0`
- Entities service (for entity data)
- Documents service (for co-occurrence analysis)
- Database service (optional, for persistence)

## Events

**Published:**
- `graph.built` - When graph construction completes
- `graph.updated` - When graph is modified
- `graph.exported` - When graph is exported

**Subscribed:**
- `entities.created` - To update graph nodes
- `entities.merged` - To merge graph nodes
- `documents.deleted` - To update edge weights

## Configuration

Graph algorithms can be configured via Frame services:
- Entity service provides entity data
- Document service provides co-occurrence data
- Database service enables persistence

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black arkham_shard_graph/
```

## Algorithm Details

### PageRank Calculation
- Iterative power method
- Damping factor: 0.85
- Convergence threshold: 1e-6
- Maximum iterations: 100

### Community Detection
- Louvain-inspired modularity optimization
- Resolution parameter for community size control
- Two-phase algorithm: modularity maximization + aggregation

### Centrality Metrics
- **Degree**: Count of connections
- **Betweenness**: Frequency on shortest paths
- **PageRank**: Iterative importance measure
