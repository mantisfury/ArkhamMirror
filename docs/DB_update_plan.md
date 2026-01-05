# Database Persistence Update Plan

## Executive Summary

This document outlines the plan to add database persistence across SHATTERED shards. Based on comprehensive analysis of all 25+ shards, three shards require immediate attention for data persistence, plus LLM settings need to be connected to the Settings shard.

**Priority Items:**
1. **HIGH**: ACH Matrices - Core analysis data lost on restart
2. **HIGH**: Ingest Jobs - Job tracking/progress lost on restart
3. **MEDIUM**: Graph - Graph data rebuilt from scratch on restart
4. **HIGH**: LLM Settings - Configuration lost on restart

---

## Current State Analysis

### Shards WITH Database Persistence (Already Implemented)
| Shard | Tables | Schema |
|-------|--------|--------|
| Projects | 4 | arkham_projects |
| Provenance | 8 | arkham_provenance |
| Settings | 3 | arkham_settings |
| Timeline | 2 | arkham_timeline |
| Claims | 2 | arkham_claims |
| Credibility | 2 | arkham_credibility |
| Anomalies | 3 | arkham_anomalies |
| Contradictions | 2 | arkham_contradictions |
| Entities | 3 | arkham_entities |
| Patterns | 2 | arkham_patterns |
| Reports | 3 | arkham_reports |
| Letters | 2 | arkham_letters |
| Templates | 2 | arkham_templates |
| Packets | 4 | arkham_packets |
| Export | 1 | arkham_export |

### Shards WITHOUT Persistence (Need Implementation)
| Shard | Current Storage | Data Lost on Restart |
|-------|-----------------|---------------------|
| **ACH** | In-memory dict | Matrices, hypotheses, evidence, ratings |
| **Ingest** | In-memory dict | Jobs, batches, checksums |
| **Graph** | In-memory dict | Computed graphs, nodes, edges |

### Shards That Don't Need Persistence (Stateless)
| Shard | Reason |
|-------|--------|
| Search | Queries vectors service (Qdrant) |
| Parse | Stores via Frame services |
| Embed | Stores via Qdrant vectors |
| OCR | Cache-only with configurable TTL |
| Dashboard | Reads from other services |

---

## Phase 1: ACH Matrices Persistence

### Current State
- `MatrixManager._matrices` - In-memory dict stores all ACH matrices
- Matrices contain: hypotheses, evidence, ratings, scores
- **Premortems/Scenarios already persisted** (6 tables in arkham_ach schema)

### Schema Design
```sql
CREATE SCHEMA IF NOT EXISTS arkham_ach;

-- Already exists: premortems, failure_modes, scenario_trees,
-- scenario_nodes, scenario_indicators, scenario_drivers

-- NEW: Core matrix persistence
CREATE TABLE IF NOT EXISTS arkham_ach.matrices (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    question TEXT,
    project_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    status TEXT DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS arkham_ach.hypotheses (
    id TEXT PRIMARY KEY,
    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    column_index INTEGER DEFAULT 0,
    is_lead BOOLEAN DEFAULT FALSE,
    notes TEXT,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS arkham_ach.evidence (
    id TEXT PRIMARY KEY,
    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    source TEXT,
    evidence_type TEXT DEFAULT 'FACT',
    credibility REAL DEFAULT 1.0,
    relevance REAL DEFAULT 1.0,
    row_index INTEGER DEFAULT 0,
    notes TEXT,
    author TEXT,
    document_ids JSONB DEFAULT '[]',
    source_document_id TEXT,
    source_chunk_id TEXT,
    source_page_number INTEGER,
    source_quote TEXT,
    extraction_method TEXT DEFAULT 'manual',
    similarity_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS arkham_ach.ratings (
    id TEXT PRIMARY KEY,
    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
    hypothesis_id TEXT NOT NULL REFERENCES arkham_ach.hypotheses(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES arkham_ach.evidence(id) ON DELETE CASCADE,
    rating TEXT NOT NULL, -- CC, C, N, I, II, NA
    notes TEXT,
    rated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(matrix_id, hypothesis_id, evidence_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ach_matrices_project ON arkham_ach.matrices(project_id);
CREATE INDEX IF NOT EXISTS idx_ach_hypotheses_matrix ON arkham_ach.hypotheses(matrix_id);
CREATE INDEX IF NOT EXISTS idx_ach_evidence_matrix ON arkham_ach.evidence(matrix_id);
CREATE INDEX IF NOT EXISTS idx_ach_ratings_matrix ON arkham_ach.ratings(matrix_id);
CREATE INDEX IF NOT EXISTS idx_ach_ratings_hypothesis ON arkham_ach.ratings(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_ach_ratings_evidence ON arkham_ach.ratings(evidence_id);
```

### Implementation Tasks

#### Checkpoint 1.1: Schema Creation ✅ COMPLETED
- [x] Add schema creation SQL to `ACHShard._create_schema()`
- [x] Test schema creates correctly on startup
- [x] Verify indexes are created

#### Checkpoint 1.2: Matrix CRUD ✅ COMPLETED
- [x] Implement `_save_matrix()` method
- [x] Implement `_load_matrix()` method
- [x] Implement `_delete_matrix()` method
- [x] Update `MatrixManager` to use database methods

#### Checkpoint 1.3: Hypothesis CRUD ✅ COMPLETED
- [x] Implement `_save_hypothesis()` method
- [x] Implement `_load_hypotheses()` method (for matrix)
- [x] Implement `_delete_hypothesis()` method
- [x] Update matrix creation/edit flows

#### Checkpoint 1.4: Evidence CRUD ✅ COMPLETED
- [x] Implement `_save_evidence()` method
- [x] Implement `_load_evidence()` method (for matrix)
- [x] Implement `_delete_evidence()` method
- [x] Update evidence creation/edit flows

#### Checkpoint 1.5: Ratings CRUD ✅ COMPLETED
- [x] Implement `_save_rating()` method
- [x] Implement `_load_ratings()` method (for matrix)
- [x] Implement rating upsert logic
- [x] Update rating change flows

#### Checkpoint 1.6: Migration & Testing ✅ COMPLETED
- [x] Add migration for existing in-memory matrices (optional)
- [x] Test full matrix lifecycle (create, edit, delete)
- [x] Verify data survives server restart
- [x] Test with multiple matrices
- [x] Fixed API to use async `list_matrices_async()` for database loading

### Files to Modify
- `packages/arkham-shard-ach/arkham_shard_ach/shard.py`
- `packages/arkham-shard-ach/arkham_shard_ach/matrix.py`
- `packages/arkham-shard-ach/arkham_shard_ach/models.py` (if needed)

---

## Phase 2: Ingest Jobs Persistence

### Current State
- `IntakeManager._jobs` - In-memory dict for job tracking
- `IntakeManager._batches` - In-memory dict for batch tracking
- `IntakeManager._checksums` - In-memory dict for deduplication
- Files stored in DataSilo/documents (this IS persistent)

### Schema Design
```sql
CREATE SCHEMA IF NOT EXISTS arkham_ingest;

CREATE TABLE IF NOT EXISTS arkham_ingest.jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT,
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    file_category TEXT, -- PDF, IMAGE, ARCHIVE, TEXT, etc.
    mime_type TEXT,
    file_size INTEGER,
    checksum TEXT,
    quality_score REAL,
    quality_class TEXT, -- CLEAN, FIXABLE, MESSY
    worker_route TEXT,
    batch_id TEXT,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    document_id TEXT, -- Created document ID after completion
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS arkham_ingest.batches (
    id TEXT PRIMARY KEY,
    name TEXT,
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    total_files INTEGER DEFAULT 0,
    completed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS arkham_ingest.checksums (
    checksum TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES arkham_ingest.jobs(id) ON DELETE CASCADE,
    filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status ON arkham_ingest.jobs(status);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_batch ON arkham_ingest.jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_checksum ON arkham_ingest.jobs(checksum);
CREATE INDEX IF NOT EXISTS idx_ingest_batches_status ON arkham_ingest.batches(status);
```

### Implementation Tasks

#### Checkpoint 2.1: Schema Creation
- [ ] Add schema creation SQL to `IngestShard._create_schema()`
- [ ] Test schema creates correctly

#### Checkpoint 2.2: Job Persistence
- [ ] Implement `_save_job()` method
- [ ] Implement `_load_job()` method
- [ ] Implement `_update_job_status()` method
- [ ] Implement `_list_jobs()` with filtering

#### Checkpoint 2.3: Batch Persistence
- [ ] Implement `_save_batch()` method
- [ ] Implement `_load_batch()` method
- [ ] Implement `_update_batch_progress()` method

#### Checkpoint 2.4: Checksum Deduplication
- [ ] Implement `_check_duplicate()` method (query checksums table)
- [ ] Implement `_record_checksum()` method
- [ ] Update ingest flow to use database

#### Checkpoint 2.5: Recovery Logic
- [ ] Implement `_recover_pending_jobs()` on startup
- [ ] Handle interrupted batches
- [ ] Test recovery after crash

### Files to Modify
- `packages/arkham-shard-ingest/arkham_shard_ingest/shard.py`
- `packages/arkham-shard-ingest/arkham_shard_ingest/intake.py`

---

## Phase 3: Graph Persistence

### Current State
- `GraphShard._graph_cache` - In-memory dict storing computed graphs
- Graphs rebuilt from scratch on each request if not cached
- No persistence layer implemented

### Schema Design
```sql
CREATE SCHEMA IF NOT EXISTS arkham_graph;

CREATE TABLE IF NOT EXISTS arkham_graph.graphs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS arkham_graph.nodes (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL REFERENCES arkham_graph.graphs(id) ON DELETE CASCADE,
    entity_id TEXT,
    entity_type TEXT,
    label TEXT,
    properties JSONB DEFAULT '{}',
    centrality_score REAL,
    community_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS arkham_graph.edges (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL REFERENCES arkham_graph.graphs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT,
    weight REAL DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_graph_graphs_project ON arkham_graph.graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph ON arkham_graph.nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_entity ON arkham_graph.nodes(entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_graph ON arkham_graph.edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON arkham_graph.edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON arkham_graph.edges(target_id);
```

### Implementation Tasks

#### Checkpoint 3.1: Schema Creation
- [ ] Add schema creation SQL to `GraphShard._create_schema()`
- [ ] Test schema creates correctly

#### Checkpoint 3.2: Graph Persistence
- [ ] Implement `_save_graph()` method
- [ ] Implement `_load_graph()` method
- [ ] Implement `_delete_graph()` method

#### Checkpoint 3.3: Cache + DB Strategy
- [ ] Load from DB on startup
- [ ] Write to DB on graph build
- [ ] Invalidate/update on entity changes

#### Checkpoint 3.4: Incremental Updates
- [ ] Handle node additions without full rebuild
- [ ] Handle edge updates
- [ ] Test performance with large graphs

### Files to Modify
- `packages/arkham-shard-graph/arkham_shard_graph/shard.py`
- `packages/arkham-shard-graph/arkham_shard_graph/storage.py`

---

## Phase 4: LLM Settings Persistence

### Current State
- LLM config read from environment variables at startup:
  - `LLM_ENDPOINT` or `LM_STUDIO_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`
- Dashboard shard has API to update config (`POST /api/dashboard/llm`)
- Changes are **runtime-only** - lost on restart
- Settings shard has full database persistence but isn't connected

### Solution Design
Connect Dashboard LLM updates to Settings shard for persistence.

### Implementation Tasks

#### Checkpoint 4.1: Settings Keys Definition ✅ COMPLETED
- [x] Define settings keys in Settings shard:
  - `llm.endpoint` - LLM API endpoint URL
  - `llm.model` - Model name
  - `llm.provider` - Provider type (openai, anthropic, openrouter, lm-studio)

#### Checkpoint 4.2: Dashboard Integration ✅ COMPLETED
- [x] Update Dashboard `update_llm_config()` to save to Settings shard
- [x] Add event emission: `settings.llm.updated`

#### Checkpoint 4.3: Frame LLM Service Integration ✅ COMPLETED
- [x] Update LLM service to read from Settings on startup
- [x] Pass db to LLMService constructor in frame.py
- [x] Add `_load_persisted_settings()` method to LLM service

#### Checkpoint 4.4: Fallback to Environment ✅ COMPLETED
- [x] Keep environment variables as fallback
- [x] Priority: Settings DB > Environment Variables > Defaults
- [x] Tested: LLM model setting persists across server restart

### Files to Modify
- `packages/arkham-shard-dashboard/arkham_shard_dashboard/shard.py`
- `packages/arkham-shard-settings/arkham_shard_settings/shard.py`
- `packages/arkham-frame/arkham_frame/services/llm.py`
- `packages/arkham-frame/arkham_frame/services/config.py`

---

## Implementation Order

### Week 1: ACH Matrices (Highest Impact)
1. Checkpoint 1.1: Schema Creation
2. Checkpoint 1.2: Matrix CRUD
3. Checkpoint 1.3: Hypothesis CRUD
4. Checkpoint 1.4: Evidence CRUD
5. Checkpoint 1.5: Ratings CRUD
6. Checkpoint 1.6: Testing

### Week 2: LLM Settings + Ingest Jobs
1. Checkpoint 4.1-4.4: LLM Settings (can be done quickly)
2. Checkpoint 2.1: Ingest Schema
3. Checkpoint 2.2: Job Persistence
4. Checkpoint 2.3: Batch Persistence
5. Checkpoint 2.4: Checksum Deduplication
6. Checkpoint 2.5: Recovery Logic

### Week 3: Graph Persistence
1. Checkpoint 3.1: Schema Creation
2. Checkpoint 3.2: Graph Persistence
3. Checkpoint 3.3: Cache + DB Strategy
4. Checkpoint 3.4: Incremental Updates

---

## Testing Checklist

### ACH Matrices
- [ ] Create matrix, restart server, matrix still exists
- [ ] Add hypotheses, restart, hypotheses preserved
- [ ] Add evidence, restart, evidence preserved
- [ ] Set ratings, restart, ratings preserved
- [ ] Delete matrix, verify cascade delete

### Ingest Jobs
- [ ] Start job, restart, job status correct
- [ ] Upload duplicate file, detected without re-upload
- [ ] Batch progress survives restart
- [ ] Failed jobs can be retried after restart

### Graph
- [ ] Build graph, restart, graph loads from DB
- [ ] Add entity, graph updates correctly
- [ ] Delete entity, graph reflects change

### LLM Settings
- [ ] Configure LLM via Dashboard, restart, config persists
- [ ] Change endpoint, LLM service uses new endpoint
- [ ] Remove config, falls back to environment variables

---

## Schema Naming Convention

All schemas follow the pattern: `arkham_{shard_name}`

| Shard | Schema Name |
|-------|-------------|
| ACH | arkham_ach |
| Ingest | arkham_ingest |
| Graph | arkham_graph |
| Settings | arkham_settings |
| Projects | arkham_projects |
| etc. | arkham_{name} |

---

## Notes

### Project Isolation
- All new tables should include `project_id` column where appropriate
- Use indexes on `project_id` for efficient filtering
- ACH matrices should support project scoping
- Ingest jobs can be project-scoped
- Graphs should be per-project

### Event Integration
When data changes, emit events:
- `ach.matrix.created`, `ach.matrix.updated`, `ach.matrix.deleted`
- `ingest.job.created`, `ingest.job.completed`, `ingest.job.failed`
- `graph.graph.built`, `graph.graph.updated`
- `settings.llm.updated`

### Backward Compatibility
- Existing in-memory data is ephemeral - no migration needed
- New persistence is additive
- Falls back to empty state if database unavailable

---

## Quick Reference: Database Helper Pattern

```python
def _parse_json_field(value: Any, default: Any = None) -> Any:
    """Parse a JSON field that may already be parsed by the database driver."""
    if value is None:
        return default if default is not None else []
    if isinstance(value, (list, dict)):
        return value  # Already parsed by PostgreSQL JSONB
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []
    return default if default is not None else []
```

Use this helper for all JSONB fields to avoid double-parsing errors.
