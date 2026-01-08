# arkham-shard-graph

> Entity relationship graph analysis and visualization

**Version:** 0.1.0
**Category:** Visualize
**Frame Requirement:** >=0.1.0

## Overview

The Graph shard provides entity relationship graph construction, analysis, and visualization for SHATTERED. It builds graphs from document co-occurrences and entity relationships, supports multiple layout algorithms, offers graph analytics (centrality, community detection, path finding), and integrates data from other shards for comprehensive network analysis.

### Key Capabilities

1. **Graph Visualization** - Interactive entity relationship graphs
2. **Path Finding** - Find shortest paths between entities
3. **Centrality Analysis** - PageRank, betweenness, eigenvector, HITS, closeness
4. **Community Detection** - Identify clusters and communities
5. **Graph Export** - Export to GEXF, GraphML, JSON, CSV
6. **Subgraph Extraction** - Extract ego networks and subgraphs
7. **Temporal Analysis** - Graph evolution over time
8. **Flow Analysis** - Information flow and cascade detection
9. **Causal Inference** - Causal graph analysis
10. **Geo-Spatial** - Geographic entity mapping

## Features

### Graph Building
- Build from document co-occurrences
- Entity relationship extraction
- Cross-shard data integration
- Configurable minimum co-occurrence threshold

### Layout Algorithms
- **Force-Directed** - Physics simulation (frontend)
- **Hierarchical** - Sugiyama layered layout
- **Radial** - Concentric circles from center
- **Circular** - All nodes on circle
- **Tree** - Reingold-Tilford layout
- **Bipartite** - Two-column by entity type
- **Grid** - Simple grid arrangement

### Centrality Metrics
- PageRank
- Betweenness centrality
- Eigenvector centrality
- HITS (hub/authority)
- Closeness centrality

### Composite Scoring
Combines multiple signals for entity importance:
- Centrality scores
- Frequency (TF-IDF style)
- Recency (exponential decay)
- Credibility (source reliability)
- Corroboration (independent sources)

### Cross-Shard Integration
Integrate data from other shards as nodes/edges:
- Claims as nodes
- ACH evidence and hypotheses
- Provenance artifacts
- Timeline events
- Contradictions as edges
- Pattern matches as edges
- Credibility weight adjustments

### Temporal Analysis
- Generate time-series snapshots
- Track network evolution
- Identify growth patterns
- Visualize temporal changes

### Relationship Types
50+ relationship types organized by category:
- **Organizational**: works_for, owns, member_of, reports_to
- **Personal**: married_to, child_of, knows, friend_of
- **Interaction**: communicated_with, met_with, transacted_with
- **Spatial**: located_in, visited, resides_in
- **Temporal**: preceded_by, followed_by, concurrent_with
- **Analysis**: contradicts, supports, evidence_for

## Installation

```bash
pip install -e packages/arkham-shard-graph
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/stats` | Graph statistics |

### Graph Building

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/build` | Build graph from documents |
| GET | `/api/graph/{project_id}` | Get project graph |
| POST | `/api/graph/filter` | Filter existing graph |

### Entity Networks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/entity/{id}` | Get entity details |
| GET | `/api/graph/ego/{id}` | Get ego network |
| GET | `/api/graph/ego/{id}/metrics` | Ego network metrics |
| GET | `/api/graph/neighbors/{id}` | Get entity neighbors |

### Path Finding

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/path` | Find shortest path |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/centrality/{project_id}` | Centrality analysis |
| POST | `/api/graph/communities` | Community detection |
| POST | `/api/graph/scores` | Composite scoring |
| GET | `/api/graph/scores/{project_id}` | Get scores (default config) |

### Layouts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/layout` | Calculate layout |
| GET | `/api/graph/layout/types` | Available layout types |

### Temporal Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/temporal/range` | Get time range |
| POST | `/api/graph/temporal/snapshots` | Generate snapshots |
| GET | `/api/graph/temporal/snapshot/{ts}` | Snapshot at time |
| GET | `/api/graph/temporal/evolution` | Evolution metrics |

### Flow Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/flows` | Analyze information flows |
| GET | `/api/graph/flows/{project_id}` | Get flow analysis |

### Causal Inference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/causal/{project_id}` | Build causal graph |
| GET | `/api/graph/causal/{project_id}/validate` | Validate DAG |
| GET | `/api/graph/causal/{project_id}/paths` | Causal paths |
| GET | `/api/graph/causal/{project_id}/confounders` | Find confounders |
| POST | `/api/graph/causal/{project_id}/intervention` | Intervention analysis |
| GET | `/api/graph/causal/{project_id}/ordering` | Topological ordering |

### Geo-Spatial

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/geo/{project_id}` | Geographic nodes |
| GET | `/api/graph/geo/{project_id}/bounds` | Geographic bounds |
| GET | `/api/graph/geo/{project_id}/distance` | Distance analysis |
| GET | `/api/graph/geo/{project_id}/clusters` | Geographic clusters |

### ACH Argumentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/argumentation/{matrix_id}` | ACH as graph |
| GET | `/api/graph/argumentation/matrices/{project_id}` | List matrices |

### Positions and Annotations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/positions` | Save node positions |
| GET | `/api/graph/positions/{project_id}` | Get positions |
| DELETE | `/api/graph/positions/{project_id}` | Clear positions |
| POST | `/api/graph/annotations` | Create annotation |
| GET | `/api/graph/annotations/{project_id}` | Get annotations |
| PUT | `/api/graph/annotations/{id}` | Update annotation |
| DELETE | `/api/graph/annotations/{id}` | Delete annotation |

### Cross-Shard Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/sources/status` | Source availability |
| POST | `/api/graph/sources/nodes` | Fetch cross-shard nodes |
| POST | `/api/graph/sources/edges` | Fetch cross-shard edges |
| GET | `/api/graph/sources/credibility` | Credibility weights |

### Relationship Types

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/relationship-types` | Get all relationship types |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/export` | Export graph |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/graph/ai/junior-analyst` | AI network analysis |
| POST | `/api/graph/ai/feedback` | Submit feedback |

## API Examples

### Build Graph

```json
POST /api/graph/build
{
  "project_id": "proj_123",
  "entity_types": ["PERSON", "ORGANIZATION", "GPE"],
  "min_co_occurrence": 2,
  "include_document_entities": true,
  "include_cooccurrences": true,
  "include_temporal": true,
  "include_claims": false,
  "include_ach_evidence": false
}
```

### Get Ego Network

```bash
GET /api/graph/ego/{entity_id}?depth=2&min_weight=0.5
```

Response:
```json
{
  "center": {"id": "ent_123", "label": "John Smith", "entity_type": "PERSON"},
  "nodes": [...],
  "edges": [...],
  "node_count": 25,
  "edge_count": 40,
  "depth": 2
}
```

### Find Shortest Path

```json
POST /api/graph/path
{
  "project_id": "proj_123",
  "source_id": "ent_person_123",
  "target_id": "ent_org_456",
  "max_depth": 5
}
```

Response:
```json
{
  "found": true,
  "path_length": 3,
  "path": [
    {"id": "ent_person_123", "label": "John Smith"},
    {"id": "ent_org_789", "label": "Acme Corp"},
    {"id": "ent_org_456", "label": "Target Inc"}
  ],
  "edges": [...]
}
```

### Centrality Analysis

```bash
GET /api/graph/centrality/{project_id}?metric=pagerank&top_k=20
```

Response:
```json
{
  "metric": "pagerank",
  "results": [
    {"entity_id": "ent_123", "label": "John Smith", "score": 0.125, "rank": 1},
    {"entity_id": "ent_456", "label": "Acme Corp", "score": 0.098, "rank": 2}
  ]
}
```

### Community Detection

```json
POST /api/graph/communities
{
  "project_id": "proj_123",
  "algorithm": "louvain",
  "resolution": 1.0
}
```

### Calculate Layout

```json
POST /api/graph/layout
{
  "project_id": "proj_123",
  "layout_type": "hierarchical",
  "direction": "TB",
  "layer_spacing": 100,
  "node_spacing": 50
}
```

### Temporal Snapshots

```json
POST /api/graph/temporal/snapshots
{
  "project_id": "proj_123",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "interval_days": 30,
  "cumulative": true
}
```

### Composite Scoring

```json
POST /api/graph/scores
{
  "project_id": "proj_123",
  "centrality_type": "pagerank",
  "centrality_weight": 0.3,
  "frequency_weight": 0.2,
  "recency_weight": 0.2,
  "credibility_weight": 0.15,
  "corroboration_weight": 0.15,
  "limit": 50
}
```

### Export Graph

```json
POST /api/graph/export
{
  "project_id": "proj_123",
  "format": "gexf",
  "include_attributes": true
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `graph.graph.built` | Graph constructed |
| `graph.graph.updated` | Graph updated |
| `graph.graph.exported` | Graph exported |
| `graph.communities.detected` | Communities found |
| `graph.path.found` | Path discovered |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `entities.entity.created` | Add entity to graph |
| `entities.entity.merged` | Update merged entities |
| `documents.document.deleted` | Remove document connections |

## UI Routes

| Route | Description |
|-------|-------------|
| `/graph` | Graph visualization |

## Dependencies

### Required Services
- **database** - Graph data storage
- **events** - Event publishing

### Optional Services
- **entities** - Entity service for data
- **documents** - Document service

## URL State

| Parameter | Description |
|-----------|-------------|
| `projectId` | Current project |
| `entityId` | Selected entity |
| `depth` | Network depth |

## Export Formats

| Format | Description |
|--------|-------------|
| `gexf` | Gephi exchange format |
| `graphml` | GraphML format |
| `json` | JSON graph format |
| `csv` | CSV node/edge lists |

## Layout Options

### Hierarchical
- `direction`: TB, BT, LR, RL
- `layer_spacing`: Vertical spacing
- `node_spacing`: Horizontal spacing

### Radial
- `root_node_id`: Center node
- `radius_step`: Ring spacing

### Bipartite
- `left_types`: Entity types for left column
- `right_types`: Entity types for right column

## Link Analysis Mode

The graph supports an i2 Analyst's Notebook-style link analysis mode:
- Manual node positioning
- Save/load positions per project
- Annotations on nodes and edges
- Labels, notes, and highlights
- Export to PNG/SVG

## Development

```bash
# Run tests
pytest packages/arkham-shard-graph/tests/

# Type checking
mypy packages/arkham-shard-graph/
```

## License

MIT
