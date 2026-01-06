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

### Fully Operational Shards (24 total) - ALL COMPLETE

All shards are now functional with complete backend/frontend integration:

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
| provenance | Operational | Evidence chains, artifact tracking, lineage graphs |
| patterns | Operational | Cross-document pattern detection, statistical correlation |
| anomalies | Operational | Hybrid detection (sync+async), bulk triage, 6 detection strategies |
| summary | Operational | LLM-powered summarization, source browser, statistics dashboard |
| graph | Operational | Advanced controls, cross-shard integration, composite scoring, collapsible UI |
| timeline | Operational | Event extraction, conflict detection, interactive visualization |
| export | Operational | Real data export (JSON, CSV, PDF, XLSX), job management |
| templates | Operational | Full PostgreSQL persistence, Jinja2 rendering, versioning |
| reports | Operational | Real data fetching, PDF/HTML/MD/JSON generation, cross-shard integration |
| letters | Operational | PDF/DOCX generation with reportlab/python-docx, professional formatting |
| packets | Operational | ZIP/JSON bundling, content export, import, SHA256 checksum verification |

### Shards Requiring Work (0 total)

**All 24 shards are now complete!**

> **Note:** Graph shard now has advanced controls, cross-shard data integration, composite scoring, and collapsible UI (2026-01-06).

> **Note:** Export and Templates shards completed with full data fetching, PDF/XLSX generation, and PostgreSQL persistence (2026-01-06).

> **Note:** Reports and Letters shards completed with real data fetching, PDF/DOCX generation (2026-01-06).

> **Note:** Timeline shard is now fully operational with event extraction, conflict detection, and interactive visualization (2026-01-06).

> **Note:** Packets shard completed with ZIP/JSON bundling, import, and SHA256 checksum calculation (2026-01-06).

---

## Phase 1: Analysis Shards

### 1.1 Provenance Shard - COMPLETED (2026-01-04)

**Status: Fully Operational**

The provenance shard is now fully implemented with:
- 4 database tables: chains, links, artifacts, records
- Full CRUD for artifacts, chains, and links
- BFS-based lineage traversal with graph visualization
- Chain verification with integrity checking
- Event handlers that auto-create artifacts for documents/entities/claims
- Complete frontend with 3 tabs: Artifacts, Chains, Lineage

---

### 1.2 Patterns Shard - COMPLETED (2026-01-04)

**Status: Fully Operational**

The patterns shard is now fully implemented with:
- Database schema: 2 tables (patterns, pattern_matches)
- Full pattern matching with graceful degradation:
  - Keyword matching (always available)
  - Regex matching (always available)
  - Vector similarity (if vectors service available)
- Statistical correlation analysis (Pearson correlation)
- LLM-based pattern detection with structured prompts
- Event handlers for documents, entities, claims, timeline events
- Complete frontend with:
  - Tabbed views (All, Recurring, Behavioral, Temporal)
  - Create/Edit pattern modals
  - Text analysis panel
  - Pattern criteria display
  - Match evidence viewer

---

### 1.3 Anomalies Shard - COMPLETED (2026-01-04)

**Status: Fully Operational**

The anomalies shard is now fully implemented with:
- 3 database tables: anomalies, notes, patterns
- 6 detection strategies in `detector.py`:
  - `detect_content_anomalies()` - z-score outlier detection via vector similarity
  - `detect_red_flags()` - money/date/sensitive keyword patterns (sync)
  - `detect_statistical_anomalies()` - word count, sentence length
  - `detect_metadata_anomalies()` - file size, creation date
- Hybrid detection approach:
  - Quick red flag detection runs synchronously for immediate results
  - Deep analysis (statistical, metadata, content) runs via background workers or sync fallback
- Event handlers wired to `embed.document.completed` and `documents.metadata.updated`
- Complete frontend with:
  - Stats dashboard
  - Filtering by type/status/severity/score
  - Bulk selection with checkboxes
  - Bulk triage actions (confirm/dismiss/false positive)
  - Detailed anomaly view with status management
  - Analyst notes
  - Investigation actions

---

### 1.4 Contradictions Shard - COMPLETED (2026-01-04)

**Status: Fully Operational**

The contradictions shard is now fully implemented with:
- Database schema: 2 tables (contradictions, contradiction_chains)
- Full contradiction detection pipeline:
  - Claim extraction from documents via LLM
  - Semantic similarity matching between claims
  - LLM-based verification of contradictions
  - Confidence scoring with configurable thresholds
- Chain detection for multi-document contradictions
- Event handlers wired to `documents.document.created`, `documents.document.updated`, `embed.document.completed`
- Complete frontend with:
  - Stats dashboard with severity/status breakdown
  - Filtering by type/status/severity
  - Bulk selection with checkboxes
  - Bulk status actions (confirm/dismiss/investigate)
  - Pagination
  - Analysis dialog for running contradiction detection
  - Detail view with source documents and chain visualization
  - Analyst notes

**Key API Endpoints:**
- `GET /api/contradictions/count` - Total count (navigation badge)
- `GET /api/contradictions/pending/count` - Pending count
- `GET /api/contradictions/stats` - Full statistics
- `POST /api/contradictions/analyze` - Run contradiction detection
- `POST /api/contradictions/bulk-status` - Bulk status updates

---

### 1.5 Summary Shard - COMPLETED (2026-01-05)

**Status: Fully Operational**

The summary shard is now fully implemented with:
- Full LLM-powered summarization with extractive fallback
- 5 summary types: brief, detailed, executive, bullet_points, abstract
- 5 target lengths: very_short, short, medium, long, very_long
- Source browser for documents, entities, projects, claims, timeline events
- Database persistence with comprehensive statistics
- Event handlers for auto-summarization

**Backend Features:**
- Fixed `_fetch_source_content()` to query `arkham_frame.chunks` table
- Fixed LLMResponse handling (extract `.text` from response object)
- Fixed `/stats` route ordering (moved before `/{summary_id}`)
- Statistics aggregation from database with breakdowns by type/source/status/model

**Frontend Features:**
- 3-tab layout: Summaries list, Generate, Statistics
- Source picker modal with document browser
- Filters panel (search, type, source type, status)
- Statistics dashboard with metric cards
- Regenerate button on summary detail view
- Pagination support

**Key API Endpoints:**
- `GET /api/summary/stats` - Full statistics with aggregations
- `GET /api/summary/types` - Available summary types
- `GET /api/summary/sources/documents` - Browse documents for summarization
- `POST /api/summary/` - Generate new summary
- `GET /api/summary/{id}` - Get summary details

---

## Phase 2: Visualization Shards

### 2.1 Graph Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

The graph shard is now fully implemented with advanced visualization controls and cross-shard data integration.

**File Locations:**
- Backend: `packages/arkham-shard-graph/arkham_shard_graph/`
  - `shard.py` - Main class
  - `builder.py` - Graph construction from entities
  - `algorithms.py` - BFS, PageRank, Louvain community detection
  - `scoring.py` - Composite scoring engine (NEW)
  - `storage.py` - In-memory + optional DB persistence
  - `exporter.py` - JSON, GraphML, GEXF export
- Frontend: `packages/arkham-shard-shell/src/pages/graph/`
  - `components/` - GraphControls, DataSourcesPanel, FilterControls, etc.
  - `hooks/` - useGraphSettings, useUrlParams, useDebounce

**Completed Implementation:**
- [x] Backend algorithms (shortest path, centrality, communities)
- [x] Database persistence (arkham_graph schema: graphs, nodes, edges)
- [x] Cache + DB hybrid storage strategy
- [x] react-force-graph visualization with ForceGraph2D
- [x] Interactive features: click, drag, zoom, pan
- [x] Path finding with visual highlighting
- [x] Entity type color coding and legend

**New Features (2026-01-06):**
- [x] **Advanced Controls Panel** - Labels, layout physics, node sizing, filtering
- [x] **Composite Scoring Engine** - Configurable weights for centrality, frequency, recency, credibility
- [x] **Cross-Shard Data Integration** - Pull nodes/edges from Timeline, Claims, ACH, Provenance, Patterns
- [x] **Per-Document Entity Selection** - Choose specific documents to include in graph
- [x] **Collapsible Sidebar** - Collapse button to maximize graph view
- [x] **Accordion Categories** - Collapsible sections in Data Sources panel
- [x] **URL Parameters** - Shareable graph views with settings encoded in URL
- [x] **Smart Weighting** - 5 centrality algorithms (PageRank, betweenness, eigenvector, HITS, closeness)

**Key API Endpoints:**
- `POST /api/graph/build` - Build graph with data source selection
- `POST /api/graph/scores` - Calculate composite scores
- `GET /api/graph/sources/status` - Check cross-shard source availability
- `POST /api/graph/path` - Find shortest path between entities
- `GET /api/graph/centrality` - Calculate centrality metrics

**Data Source Settings:**
```typescript
interface DataSourceSettings {
  documentEntities: boolean;       // Include entities from documents
  selectedDocumentIds: string[];   // Specific documents (empty = all)
  entityCooccurrences: boolean;    // Co-occurrence edges
  // Cross-shard sources
  timelineEvents: boolean;
  claims: boolean;
  achEvidence: boolean;
  achHypotheses: boolean;
  provenanceArtifacts: boolean;
  contradictions: boolean;
  patterns: boolean;
  credibilityRatings: boolean;
}
```

---

### 2.2 Timeline Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

The timeline shard is now fully implemented with event extraction and interactive visualization.

**File Locations:**
- Backend: `packages/arkham-shard-timeline/arkham_shard_timeline/`
  - `shard.py` - Main class with event handlers
  - `api.py` - Full CRUD API with extraction endpoints
  - `extraction.py` - DateExtractor with regex patterns
  - `merging.py` - Timeline merge strategies
  - `conflicts.py` - Temporal conflict detection
- Frontend: `packages/arkham-shard-shell/src/pages/timeline/`

**Completed Implementation:**
- [x] Database schema (events, conflicts tables)
- [x] Date extraction from text via regex patterns
- [x] Event CRUD operations
- [x] Conflict detection between overlapping events
- [x] Interactive timeline visualization
- [x] Event filtering by date range and type
- [x] Event detail panel with edit/delete
- [x] Bulk extraction from documents

**Key API Endpoints:**
- `GET /api/timeline/events` - List events with filtering
- `POST /api/timeline/events` - Create event
- `POST /api/timeline/extract` - Extract events from text
- `GET /api/timeline/conflicts` - List temporal conflicts
- `GET /api/timeline/stats` - Timeline statistics

---

## Phase 3: Export Shards

### 3.1 Export Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

**File Locations:**
- Backend: `packages/arkham-shard-export/arkham_shard_export/`
- Frontend: `packages/arkham-shard-shell/src/pages/export/`

The export shard is now fully implemented with:
- Real data fetching for all targets (documents, entities, claims, timeline, graph, ACH matrices)
- JSON export with metadata
- CSV export with JSON flattening for nested structures
- PDF export using reportlab library
- XLSX export using openpyxl library
- Internal API calls via httpx to fetch data from other shards
- Full job management with status tracking
- File expiration handling

**Key API Endpoints:**
- `POST /api/export/jobs` - Create export job
- `GET /api/export/jobs/{id}` - Get job status
- `GET /api/export/jobs/{id}/download` - Download exported file
- `GET /api/export/formats` - List supported formats
- `GET /api/export/targets` - List export targets
- `GET /api/export/stats` - Export statistics

---

### 3.2 Templates Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

**File Locations:**
- Backend: `packages/arkham-shard-templates/arkham_shard_templates/`
- Frontend: `packages/arkham-shard-shell/src/pages/templates/`

The templates shard is now fully implemented with:
- Full PostgreSQL persistence (removed in-memory caches)
- Database methods: `_save_template()`, `_load_template()`, `_row_to_template()`, `_row_to_version()`, `_save_version()`
- Jinja2 template rendering with auto-escaping
- Template versioning with full history
- Placeholder auto-detection from template content
- Template types: REPORT, LETTER, EXPORT, EMAIL, CUSTOM

**Key API Endpoints:**
- `POST /api/templates/` - Create template
- `GET /api/templates/` - List templates with filtering
- `GET /api/templates/{id}` - Get template
- `PUT /api/templates/{id}` - Update template
- `POST /api/templates/{id}/render` - Render template with data
- `GET /api/templates/{id}/versions` - Get version history
- `POST /api/templates/{id}/versions/{vid}/restore` - Restore version
- `GET /api/templates/stats` - Template statistics

---

### 3.3 Reports Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

**File Locations:**
- Backend: `packages/arkham-shard-reports/arkham_shard_reports/`
- Frontend: `packages/arkham-shard-shell/src/pages/reports/`

The reports shard is now fully implemented with:
- Real data fetching from other shards via httpx internal API calls
- 6 report types: summary, entity_profile, timeline, contradiction, ach_analysis, custom
- 4 output formats: PDF (reportlab), HTML (styled), Markdown (tables), JSON
- Cross-shard integration: documents, entities, claims, contradictions, anomalies, timeline, ACH
- Full CRUD operations (19 API endpoints)
- Database schema (3 tables: reports, templates, schedules)
- Events published (7 events)
- Frontend UI (481 lines)

**Key API Endpoints:**
- `POST /api/reports/` - Generate report with real data
- `GET /api/reports/{id}` - Get report details
- `GET /api/reports/{id}/download` - Download generated file
- `GET /api/reports/stats` - Report statistics
- `POST /api/reports/preview` - Preview before generation

---

### 3.4 Letters Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

**File Locations:**
- Backend: `packages/arkham-shard-letters/arkham_shard_letters/`
- Frontend: `packages/arkham-shard-shell/src/pages/letters/`

The letters shard is now fully implemented with:
- PDF generation using reportlab (professional letter format with Times Roman)
- DOCX generation using python-docx (proper Word document formatting)
- HTML generation with styled layout
- Markdown generation for portable text
- Template system with placeholder substitution
- Multiple letter types: FOIA, complaint, demand, notice, custom
- Full CRUD operations
- Database schema (2 tables: letters, letter_templates)
- Event publishing

**Key API Endpoints:**
- `POST /api/letters/` - Create letter
- `GET /api/letters/{id}` - Get letter details
- `POST /api/letters/{id}/export` - Export to PDF/DOCX/HTML/MD/TXT
- `POST /api/letters/templates/{id}/apply` - Apply template with placeholders
- `GET /api/letters/stats` - Letter statistics

---

### 3.5 Packets Shard - COMPLETED (2026-01-06)

**Status: Fully Operational**

**File Locations:**
- Backend: `packages/arkham-shard-packets/arkham_shard_packets/`
- Frontend: `packages/arkham-shard-shell/src/pages/packets/`

The packets shard is now fully implemented with:
- ZIP export with manifest and bundled content data
- JSON export for portable/readable format
- Import from ZIP/JSON with content reconstruction
- SHA256 checksum calculation on finalization
- Content fetching from all shard types (documents, entities, claims, ACH, etc.)
- Full CRUD operations (23 API endpoints)
- Database schema (4 tables: packets, contents, shares, versions)
- Events published (9 events)
- Frontend UI (449 lines)

**Key API Endpoints:**
- `POST /api/packets/` - Create packet
- `GET /api/packets/{id}` - Get packet details
- `POST /api/packets/{id}/contents` - Add content to packet
- `POST /api/packets/{id}/finalize` - Finalize with checksum
- `POST /api/packets/{id}/export` - Export to ZIP/JSON
- `POST /api/packets/import` - Import from ZIP/JSON
- `POST /api/packets/{id}/share` - Create share link
- `GET /api/packets/stats` - Packet statistics

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
6. ~~**Anomalies**~~ - COMPLETED (2026-01-04)

### Sprint 3: Export Infrastructure
7. ~~**Templates**~~ - COMPLETED (2026-01-06)
8. ~~**Export**~~ - COMPLETED (2026-01-06)
9. ~~**Reports**~~ - COMPLETED (2026-01-06)

### Sprint 4: Document Production
10. ~~**Letters**~~ - COMPLETED (2026-01-06)
11. ~~**Packets**~~ - COMPLETED (2026-01-06)

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
| graph | ~600 lines | ~800 lines | ~400 lines | builder.py, algorithms.py, scoring.py, storage.py, exporter.py |
| timeline | ~500 lines | ~500 lines | ~150 lines | extraction.py, merging.py, conflicts.py |
| export | 1292 lines | 409 lines | 173 lines | - |
| templates | 1289 lines | 671 lines | 313 lines | - |
| reports | 1530 lines | 551 lines | 200 lines | - |
| letters | 1248 lines | 615 lines | 181 lines | - |
| packets | 1128 lines | 449 lines | 200 lines | - |

### Frontend Files by Shard

| Shard | Main Page | Extra Components | CSS |
|-------|-----------|------------------|-----|
| provenance | ProvenancePage.tsx (438 lines) | - | ProvenancePage.css |
| patterns | PatternsPage.tsx | - | PatternsPage.css |
| anomalies | AnomaliesPage.tsx | AnomalyDetail.tsx | AnomaliesPage.css |
| summary | SummaryPage.tsx (561 lines) | - | SummaryPage.css |
| graph | GraphPage.tsx (1064 lines) | GraphControls, DataSourcesPanel, FilterControls, hooks/ | GraphPage.css (1500+ lines) |
| timeline | TimelinePage.tsx (537 lines) | - | TimelinePage.css (327 lines) |
| export | ExportPage.tsx (571 lines) | - | ExportPage.css |
| templates | TemplatesPage.tsx (686 lines) | TemplateEditor, TemplatePreview, TemplateVersions | TemplatesPage.css |
| reports | ReportsPage.tsx (480 lines) | - | ReportsPage.css |
| letters | LettersPage.tsx (663 lines) | TemplateSelector, LetterEditor | LettersPage.css |
| packets | PacketsPage.tsx | - | PacketsPage.css |

---

*Generated: 2026-01-03*
*Last Updated: 2026-01-06*
*Context: Full codebase analysis by 5 parallel agents*
*Anomalies shard completed: 2026-01-04*
*Contradictions shard completed: 2026-01-04*
*Summary shard completed: 2026-01-05*
*Graph shard advanced features completed: 2026-01-06*
*Timeline shard completed: 2026-01-06*
*Export shard completed: 2026-01-06*
*Templates shard completed: 2026-01-06*
*Reports shard completed: 2026-01-06*
*Letters shard completed: 2026-01-06*
*Packets shard completed: 2026-01-06*

**ALL 24 SHARDS NOW COMPLETE!**
