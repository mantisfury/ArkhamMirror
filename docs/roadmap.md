# SHATTERED - Development Roadmap

> **For Future Sessions:** This document is designed to be self-contained. Start here before exploring the codebase.

## Quick Reference

### Start the System
```bash
# Terminal 1: Backend
cd packages/arkham-frame && pip install -e . && cd ../..
pip install -e packages/arkham-shard-*
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Terminal 2: Frontend
cd packages/arkham-shard-shell && npm install && npm run dev
```

### Key URLs
- Frontend: http://localhost:5173
- API Docs: http://127.0.0.1:8100/docs
- Health Check: http://127.0.0.1:8100/health

### Reference Implementation
**Use `arkham-shard-ach` as the gold standard** for how a shard should be implemented:
- `packages/arkham-shard-ach/arkham_shard_ach/shard.py` - Proper initialization, schema creation, event handling
- `packages/arkham-shard-ach/arkham_shard_ach/api.py` - Complete API with proper error handling
- `packages/arkham-shard-shell/src/pages/ach/` - Full React UI with list/detail/create views

---

## Executive Summary

This roadmap outlines the remaining work to bring all shards to full operational status and containerize the entire SHATTERED system. The project follows the **Voltron** philosophy: modular shards that plug into an immutable Frame.

---

## Architecture Quick Reference

```
packages/
├── arkham-frame/                    # IMMUTABLE CORE - DO NOT MODIFY
│   └── arkham_frame/
│       ├── frame.py                 # Frame class, service registration
│       ├── main.py                  # FastAPI app, shard loading
│       ├── shard_interface.py       # ArkhamShard ABC (inherit from this)
│       └── services/
│           ├── database.py          # PostgreSQL via asyncpg
│           ├── events.py            # EventBus for pub/sub
│           ├── vectors.py           # Qdrant vector DB
│           ├── llm.py               # LLM client (OpenAI-compatible)
│           └── workers.py           # Background job pools
│
├── arkham-shard-shell/              # React frontend
│   └── src/
│       ├── pages/{shard}/           # One folder per shard
│       ├── components/common/       # Shared UI components
│       └── hooks/                   # useFetch, usePaginatedFetch
│
└── arkham-shard-{name}/             # Individual shards
    ├── shard.yaml                   # Manifest (navigation, events, capabilities)
    ├── pyproject.toml               # Python package definition
    └── arkham_shard_{name}/
        ├── __init__.py              # Exports {Name}Shard
        ├── shard.py                 # Main shard class
        ├── api.py                   # FastAPI router
        └── models.py                # Pydantic/dataclass models
```

### Accessing Frame Services (in shard.py)
```python
# In your shard's initialize() method:
async def initialize(self, frame) -> None:
    self.frame = frame
    self.db = frame.db                    # Database service
    self.events = frame.events            # Event bus
    self.vectors = getattr(frame, 'vectors', None)  # Optional
    self.llm = getattr(frame, 'llm', None)          # Optional
    self.workers = getattr(frame, 'workers', None)  # Optional
```

---

## Current State Overview

### Fully Operational Shards (14 total)
These shards are functional with complete backend/frontend integration:

| Shard | Status | Notes |
|-------|--------|-------|
| dashboard | Operational | System monitoring, LLM config, DB controls |
| settings | Operational | User preferences, configuration |
| ingest | Operational | File upload, queue management |
| documents | Operational | Document CRUD, viewer |
| parse | Operational | NER extraction, chunking |
| ocr | Operational | PaddleOCR, Qwen VLM workers |
| embed | Operational | Embeddings, similarity |
| search | Operational | Semantic/keyword/hybrid search |
| entities | Operational | Entity management, relationships |
| claims | Operational | Claim extraction, linking |
| contradictions | Operational | Contradiction detection |
| credibility | Operational | Credibility assessment, deception detection |
| ach | Operational | **REFERENCE IMPLEMENTATION** - Full ACH matrix |
| projects | Operational | Project CRUD, scoping |

### Shards Requiring Work (11 total)

| Shard | Category | Backend % | Frontend % | Priority | Critical Gap |
|-------|----------|-----------|------------|----------|--------------|
| provenance | Analysis | 40% | 60% | High | Missing 4 DB tables (chains, links, artifacts, lineage) |
| patterns | Analysis | 70% | 30% | High | `_source_matches_pattern()` returns False |
| anomalies | Analysis | 60% | 50% | Medium | Event handlers only log, don't trigger detection |
| summary | Analysis | 70% | 40% | Medium | `_fetch_source_content()` returns mock data |
| graph | Visualize | 75% | 60% | High | No graph visualization library, no DB persistence |
| timeline | Visualize | 85% | 50% | Medium | Event handlers stubbed |
| export | Export | 70% | 90% | High | `_generate_export_file()` creates placeholder files |
| templates | Export | 90% | 95% | Medium | Using in-memory cache, no DB persistence |
| reports | Export | 95% | 95% | Low | Content generation stub, PDF needs library |
| letters | Export | 85% | 85% | Low | PDF/DOCX generation stubbed |
| packets | Export | 95% | 90% | Low | Export/import placeholders, checksum not calculated |

> **Note:** Reports and Packets are more complete than other shards - they have full CRUD, events, and UI. Only file generation features are stubbed.

---

## Phase 1: Analysis Shards

### 1.1 Provenance Shard

**File Locations:**
- Backend: `packages/arkham-shard-provenance/arkham_shard_provenance/`
- Frontend: `packages/arkham-shard-shell/src/pages/provenance/`
- Manifest: `packages/arkham-shard-provenance/shard.yaml`

**Current State:**
- Has 3 tables (records, transformations, audit) but missing 4 core tables
- API endpoints return stubs like `{"id": "stub_chain_id"}`
- Event handlers subscribed but do nothing

**Known Stub Locations:**
```python
# shard.py - These methods return hardcoded stubs:
def create_chain(self, title, ...):      # Returns {"id": "stub_chain_id", ...}
def add_link(self, chain_id, ...):       # Returns {"id": "stub_link_id", ...}
def get_lineage(self, artifact_id):      # Returns {"nodes": [], "edges": []}
def verify_chain(self, chain_id):        # Returns {"verified": True, "issues": []}

# api.py - These endpoints raise 501 or return empty:
POST /chains                             # Raises 501
GET  /chains/{id}                        # Raises 404
POST /chains/{chain_id}/links            # Raises 501
GET  /lineage/{artifact_id}              # Returns empty graph
```

**Database Schema Needed:**
```sql
-- Add these tables (records/transformations/audit already exist)
CREATE TABLE arkham_provenance_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE arkham_provenance_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id UUID REFERENCES arkham_provenance_chains(id) ON DELETE CASCADE,
    source_artifact_id UUID NOT NULL,
    target_artifact_id UUID NOT NULL,
    link_type VARCHAR(50) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE arkham_provenance_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    entity_type VARCHAR(50),
    metadata JSONB DEFAULT '{}'
);
```

**Implementation Priority:**
1. Add missing database tables in `_create_schema()`
2. Implement chain CRUD in shard.py
3. Implement link management
4. Wire event handlers to create artifacts automatically
5. Connect frontend to real API

---

### 1.2 Patterns Shard

**File Locations:**
- Backend: `packages/arkham-shard-patterns/arkham_shard_patterns/`
- Frontend: `packages/arkham-shard-shell/src/pages/patterns/`

**Current State:**
- Database schema complete (2 tables: patterns, matches)
- 20+ methods implemented in shard.py
- Pattern detection logic exists but matching is placeholder

**Known Stub Locations:**
```python
# shard.py - Line ~450
def _source_matches_pattern(self, source, pattern) -> bool:
    return False  # TODO: Implement actual matching

# shard.py - Line ~480
def _check_source_against_patterns(self, source_type, source_id, content):
    # Returns empty list, correlation detection returns 0.5 score placeholder
```

**Event Subscriptions (already configured):**
- `document.processed` -> `_on_document_processed()`
- `entity.created` -> `_on_entity_created()`
- `claims.claim.created` -> `_on_claim_created()`
- `timeline.event.created` -> `_on_timeline_event()`

**Implementation Priority:**
1. Implement `_source_matches_pattern()` with text/regex matching
2. Implement co-occurrence analysis in `find_correlations()`
3. Add LLM-based pattern detection (prompt exists in code)
4. Build frontend PatternsPage.tsx (currently minimal)

---

### 1.3 Anomalies Shard

**File Locations:**
- Backend: `packages/arkham-shard-anomalies/arkham_shard_anomalies/`
  - `shard.py` - Main class
  - `detector.py` - Detection algorithms (actually implemented!)
  - `storage.py` - Data persistence
- Frontend: `packages/arkham-shard-shell/src/pages/anomalies/`

**Current State:**
- Database schema complete (3 tables)
- `detector.py` has 6 real detection strategies:
  - `detect_content_anomalies()` - z-score outlier detection
  - `detect_red_flags()` - money/date/sensitive keyword patterns
  - `detect_statistical_anomalies()` - word count, sentence length
  - `detect_metadata_anomalies()` - file size, creation date
  - `detect_temporal_anomalies()` - date reference checking
  - `detect_structural_anomalies()` - document format analysis

**Known Stub Locations:**
```python
# shard.py - Event handlers only log, don't trigger detection:
async def _on_embedding_created(self, event_data):
    logger.info("Would trigger anomaly detection...")  # Does nothing

async def _on_document_indexed(self, event_data):
    logger.info("Would trigger anomaly detection...")  # Does nothing
```

**Implementation Priority:**
1. Wire event handlers to call `check_document()`
2. Verify vector service integration in detector.py
3. Add background job queueing for bulk detection
4. Enhance frontend with anomaly triage workflow

---

### 1.4 Summary Shard

**File Locations:**
- Backend: `packages/arkham-shard-summary/arkham_shard_summary/`
- Frontend: `packages/arkham-shard-shell/src/pages/summary/`

**Current State:**
- Database schema exists
- LLM integration code exists with fallback to extractive
- Source fetching returns mock data

**Known Stub Locations:**
```python
# shard.py - Line ~300
async def _fetch_source_content(self, source_type, source_ids):
    # Returns mock data like "Sample document content for {source_id}"
    # TODO: Actually fetch from documents/entities/claims shards
```

**Implementation Priority:**
1. Implement `_fetch_source_content()` to query other shards
2. Test LLM summarization with real documents
3. Improve extractive fallback (currently just first N sentences)
4. Build frontend generation form

---

## Phase 2: Visualization Shards

### 2.1 Graph Shard

**File Locations:**
- Backend: `packages/arkham-shard-graph/arkham_shard_graph/`
  - `shard.py` - Main class
  - `builder.py` - Graph construction from entities
  - `algorithms.py` - BFS, PageRank, Louvain community detection
  - `storage.py` - In-memory + optional DB persistence
  - `exporter.py` - JSON, GraphML, GEXF export
- Frontend: `packages/arkham-shard-shell/src/pages/graph/`

**Current State:**
- Backend algorithms implemented (shortest path, centrality, communities)
- No database persistence (in-memory only)
- Frontend is placeholder - no actual graph rendering

**Known Issues:**
```python
# shard.py - Wrong event names (should be graph.graph.built):
await self.events.emit("graph.built", {...})  # Wrong!

# storage.py - Persistence not implemented:
def _persist_graph(self, graph):
    pass  # TODO: Save to database
```

**Frontend Gap:**
```tsx
// GraphPage.tsx - Line ~343-374: Placeholder instead of actual graph
<div className="graph-placeholder">
  <p className="graph-note">
    Interactive graph visualization would render here using a library like D3.js,
    vis.js, or react-force-graph.
  </p>
</div>
```

**Implementation Priority:**
1. Add database table `arkham_graphs` for persistence
2. Fix event names to match manifest
3. **Install graph library:** `npm install react-force-graph` (recommended)
4. Implement actual graph rendering in GraphPage.tsx
5. Add interactive features (click, drag, zoom)

**Graph Library Recommendation:**
```tsx
// Install: npm install react-force-graph
import ForceGraph2D from 'react-force-graph-2d';

// Usage:
<ForceGraph2D
  graphData={{ nodes: graphData.nodes, links: graphData.edges }}
  nodeLabel="label"
  nodeColor={node => getColorByType(node.type)}
  onNodeClick={handleNodeClick}
/>
```

---

### 2.2 Timeline Shard

**File Locations:**
- Backend: `packages/arkham-shard-timeline/arkham_shard_timeline/`
  - `extraction.py` - DateExtractor with regex patterns
  - `merging.py` - Timeline merge strategies
  - `conflicts.py` - Temporal conflict detection
- Frontend: `packages/arkham-shard-shell/src/pages/timeline/`

**Current State:**
- Database schema complete (events, conflicts tables)
- Date extraction logic implemented
- Event handlers stubbed

**Known Stub Locations:**
```python
# shard.py - Event handlers don't extract:
async def _on_document_indexed(self, event_data):
    # TODO: Extract timeline from document
    pass

async def _on_document_deleted(self, event_data):
    # Cleanup code is commented out
    pass
```

**Event Name Mismatch:**
```python
# shard.py subscribes to:
"document.document.indexed"  # But frame may emit "documents.indexed"
```

**Implementation Priority:**
1. Wire `_on_document_indexed()` to extract timeline
2. Verify event names match frame emissions
3. Enhance frontend with actual timeline visualization
4. Add date range picker (currently native inputs)

---

## Phase 3: Export Shards

### 3.1 Export Shard

**File Locations:**
- Backend: `packages/arkham-shard-export/arkham_shard_export/`
- Frontend: `packages/arkham-shard-shell/src/pages/export/`

**Current State:**
- Frontend UI complete and polished
- Backend job management works
- Actual file generation is stubbed

**Known Stub Locations:**
```python
# shard.py - Line ~531-555
async def _generate_export_file(self, job):
    # Creates placeholder file with "Export placeholder" content
    # TODO: Actually export data based on job.target and job.format

    # PDF/DOCX marked as placeholder:
    if job.format in ['pdf', 'docx', 'xlsx']:
        # placeholder=True in format metadata
```

**Implementation Priority:**
1. Implement data fetching for each target (documents, entities, claims, etc.)
2. Add PDF generation: `pip install weasyprint` or `reportlab`
3. Add DOCX generation: `pip install python-docx`
4. Wire to actual data sources

---

### 3.2 Templates Shard

**File Locations:**
- Backend: `packages/arkham-shard-templates/arkham_shard_templates/`
- Frontend: `packages/arkham-shard-shell/src/pages/templates/`

**Current State:**
- Frontend UI complete with editor, preview, versioning
- Backend uses Jinja2 (good!)
- **Using in-memory cache instead of database**

**Known Issue:**
```python
# shard.py - Line ~69-72
# Templates stored in memory dict, not database:
self._templates: Dict[str, Template] = {}
self._versions: Dict[str, List[TemplateVersion]] = {}

# Database schema is created but not used for writes
```

**Implementation Priority:**
1. Replace in-memory cache with database queries
2. Implement `_save_template()` and `_load_templates()`
3. Verify Jinja2 auto-escaping for security

---

### 3.3 Reports Shard

**File Locations:**
- Backend: `packages/arkham-shard-reports/arkham_shard_reports/`
- Frontend: `packages/arkham-shard-shell/src/pages/reports/`

**Current State: NEARLY COMPLETE (95%)**
- Full CRUD operations implemented (19 API endpoints)
- Database schema complete (3 tables: reports, templates, schedules)
- Events published (7 events)
- Frontend UI fully functional (481 lines)

**Database Schema (already exists):**
```sql
arkham_reports (id, report_type, title, status, created_at, completed_at,
                parameters, output_format, file_path, file_size, error, metadata)
arkham_report_templates (id, name, report_type, description, parameters_schema,
                         default_format, template_content, created_at, updated_at)
arkham_report_schedules (id, template_id, cron_expression, enabled, last_run,
                         next_run, parameters, output_format, retention_days)
```

**Known Stub Locations:**
```python
# shard.py - Content generation is stub:
async def _generate_report_content(self, report):
    # Returns placeholder content
    # TODO: Implement actual report generation

# PDF rendering requires library installation
```

**Implementation Priority:**
1. Implement actual content generation (query other shards for data)
2. Add PDF rendering: `pip install weasyprint`
3. Integrate with Templates shard for Jinja2 rendering
4. Implement schedule execution (requires background worker)

---

### 3.4 Letters Shard

**File Locations:**
- Backend: `packages/arkham-shard-letters/arkham_shard_letters/`
- Frontend: `packages/arkham-shard-shell/src/pages/letters/`

**Current State:**
- Database schema complete
- CRUD operations work
- Template system works
- PDF/DOCX export stubbed

**Known Stub Locations:**
```python
# shard.py - Line ~778-783
async def _export_to_pdf(self, letter):
    # Returns stub: "PDF export not yet implemented"

async def _export_to_docx(self, letter):
    # Returns stub: "DOCX export not yet implemented"
```

**Implementation Priority:**
1. Add PDF generation with weasyprint/reportlab
2. Add DOCX generation with python-docx
3. Test letter workflow end-to-end

---

### 3.5 Packets Shard

**File Locations:**
- Backend: `packages/arkham-shard-packets/arkham_shard_packets/`
- Frontend: `packages/arkham-shard-shell/src/pages/packets/`

**Current State: NEARLY COMPLETE (95%)**
- Full CRUD operations implemented (23 API endpoints)
- Database schema complete (4 tables: packets, contents, shares, versions)
- Events published (9 events)
- Frontend UI functional (449 lines)

**Concept:** Packets are bundled collections of documents, reports, letters for delivery/archival.

**Database Schema (already exists):**
```sql
arkham_packets (id, name, description, status, visibility, created_by,
                version, contents_count, size_bytes, checksum, metadata)
arkham_packet_contents (id, packet_id, content_type, content_id, content_title,
                        added_at, added_by, order_num)
arkham_packet_shares (id, packet_id, shared_with, permissions, shared_at,
                      expires_at, access_token)
arkham_packet_versions (id, packet_id, version_number, created_at,
                        changes_summary, snapshot_path)
```

**Known Stub Locations:**
```python
# shard.py - Export/import are placeholders:
async def export_packet(self, packet_id, format):
    # Creates placeholder file, no actual ZIP/TAR bundling

async def import_packet(self, file_path):
    # Placeholder parsing, no actual import logic

# Checksum not calculated
# Version snapshots use placeholder paths
# Share expiration not enforced (needs background job)
```

**Implementation Priority:**
1. Implement actual ZIP/TAR bundling for export
2. Implement file parsing for import
3. Add checksum calculation
4. Add Bates numbering for legal packets
5. Implement share expiration enforcement

---

## Phase 4: Docker Containerization

### Current Docker Files
- `Dockerfile` - Multi-stage build (Python backend + Node frontend)
- `docker-compose.yml` - PostgreSQL, Qdrant, Redis, App
- `docker/entrypoint.sh` - Startup with service wait logic

### Docker Verification Commands
```bash
# Build and start
docker compose up --build

# Verify services
docker compose ps
docker compose logs app

# Check shard loading
curl http://localhost:8100/health
curl http://localhost:8100/docs

# Database check
docker compose exec postgres psql -U arkham -d arkhamdb -c "\dt arkham_*"
```

### Environment Variables
```bash
# Required
DATABASE_URL=postgresql://user:pass@postgres:5432/arkhamdb
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379

# Optional - LLM
LLM_ENDPOINT=http://host.docker.internal:1234/v1
LLM_API_KEY=
```

---

## Event System Reference

### Correct Event Naming Convention
```
{shard_name}.{entity_type}.{action}

Examples:
- documents.document.created
- entities.entity.created
- ach.matrix.created
- graph.graph.built (NOT graph.built)
```

### Known Event Name Mismatches to Fix
| Shard | Current | Should Be |
|-------|---------|-----------|
| graph | `graph.built` | `graph.graph.built` |
| timeline | subscribes to `document.processed` | may need `documents.document.created` |
| summary | subscribes to `document.processed` | may need `documents.document.created` |

### Common Event Subscriptions
```python
# In shard initialize():
self.events.subscribe("documents.document.created", self._on_document_created)
self.events.subscribe("entities.entity.created", self._on_entity_created)
self.events.subscribe("documents.document.deleted", self._on_document_deleted)
```

---

## Verification Checklist

### Per-Shard Verification
```bash
# 1. Check shard loads
curl http://127.0.0.1:8100/health | jq '.shards'

# 2. Check API endpoints exist
curl http://127.0.0.1:8100/api/{shard}/health

# 3. Check badge/count endpoint
curl http://127.0.0.1:8100/api/{shard}/count

# 4. Check database tables created
# In psql: \dt arkham_{shard}*

# 5. Check frontend page loads
# Navigate to http://localhost:5173/{shard}
```

### Full System Verification
```bash
# Run all tests
cd packages/arkham-frame && python -m pytest
cd packages/arkham-shard-{name} && python -m pytest

# Check for Python syntax errors
python -m py_compile packages/arkham-shard-{name}/arkham_shard_{name}/*.py

# Check TypeScript compilation
cd packages/arkham-shard-shell && npx tsc --noEmit
```

---

## Implementation Patterns

### Adding a New API Endpoint
```python
# In api.py
from fastapi import APIRouter, HTTPException
router = APIRouter()

@router.get("/{id}")
async def get_item(id: str, shard = Depends(get_shard)):
    result = await shard.get_item(id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result
```

### Creating Database Schema
```python
# In shard.py initialize()
async def _create_schema(self):
    await self.db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_{shard}_{table} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            -- other fields
        )
    """)
    await self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_{table}_created
        ON arkham_{shard}_{table}(created_at)
    """)
```

### Emitting Events
```python
# In shard.py
await self.events.emit(
    f"{self.name}.{entity_type}.created",
    {"id": entity_id, "data": data},
    source=f"{self.name}-shard"
)
```

### Frontend API Calls
```tsx
// Using useFetch hook
const { data, loading, error, refetch } = useFetch<ResponseType>('/api/shard/endpoint');

// Using usePaginatedFetch for lists
const { items, loading, hasMore, loadMore } = usePaginatedFetch<ItemType>('/api/shard/');
```

---

## Recommended Implementation Order

### Sprint 1: Core Analysis (Highest Priority)
1. **Graph** - High visual impact, algorithms exist
2. **Provenance** - Critical for evidence chain tracking
3. **Patterns** - Key intelligence analysis feature

### Sprint 2: Visualization & Summaries
4. **Timeline** - Event handlers need wiring
5. **Summary** - Source fetching needs implementation
6. **Anomalies** - Event handlers need wiring

### Sprint 3: Export Infrastructure
7. **Templates** - Switch from in-memory to DB
8. **Export** - Implement actual file generation
9. **Reports** - Build on Templates shard

### Sprint 4: Document Production
10. **Letters** - Add PDF/DOCX generation
11. **Packets** - Full implementation

### Sprint 5: Docker & Deployment
12. Docker configuration updates
13. Testing and validation
14. Documentation

---

## Technical Dependencies

### Python Packages to Add
```bash
pip install weasyprint  # or reportlab for PDF
pip install python-docx  # for DOCX
pip install networkx     # if not present, for graph algorithms
```

### JavaScript Packages to Add
```bash
npm install react-force-graph  # Recommended for graph
# OR
npm install vis-network        # Alternative
```

---

## Appendix: Full File Reference

### Backend Files by Shard

| Shard | shard.py | api.py | models.py | Extra Files |
|-------|----------|--------|-----------|-------------|
| provenance | 661 lines | 706 lines | 251 lines | - |
| patterns | 1055 lines | 336 lines | 236 lines | - |
| anomalies | 375 lines | 825 lines | 206 lines | detector.py, storage.py |
| summary | ~500 lines | ~400 lines | ~200 lines | - |
| graph | ~600 lines | ~300 lines | ~150 lines | builder.py, algorithms.py, storage.py, exporter.py |
| timeline | ~500 lines | ~400 lines | ~150 lines | extraction.py, merging.py, conflicts.py |
| export | 666 lines | 409 lines | 173 lines | - |
| templates | 934 lines | 671 lines | 313 lines | - |
| reports | ~300 lines | ~250 lines | ~150 lines | - |
| letters | 936 lines | 615 lines | 181 lines | - |
| packets | ~200 lines | ~200 lines | ~100 lines | - |

### Frontend Files by Shard

| Shard | Main Page | Extra Components | CSS |
|-------|-----------|------------------|-----|
| provenance | ProvenancePage.tsx (438 lines) | - | ProvenancePage.css |
| patterns | PatternsPage.tsx | - | PatternsPage.css |
| anomalies | AnomaliesPage.tsx | AnomalyDetail.tsx | AnomaliesPage.css |
| summary | SummaryPage.tsx (561 lines) | - | SummaryPage.css |
| graph | GraphPage.tsx (391 lines) | - | GraphPage.css |
| timeline | TimelinePage.tsx (262 lines) | - | TimelinePage.css |
| export | ExportPage.tsx (571 lines) | - | ExportPage.css |
| templates | TemplatesPage.tsx (686 lines) | TemplateEditor, TemplatePreview, TemplateVersions | TemplatesPage.css |
| reports | ReportsPage.tsx (480 lines) | - | ReportsPage.css |
| letters | LettersPage.tsx (663 lines) | TemplateSelector, LetterEditor | LettersPage.css |
| packets | PacketsPage.tsx | - | PacketsPage.css |

---

*Generated: 2026-01-03*
*Last Updated: 2026-01-03*
*Context: Full codebase analysis by 5 parallel agents*
