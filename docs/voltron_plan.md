# Project Voltron / Shattered - Implementation Plan

## Vision

**Voltron** is the architectural philosophy: A modular, plug-and-play system where:
- The **Frame** is the core infrastructure (database, vectors, LLM, events, workers)
- **Shards** are self-contained feature modules that plug into the Frame

**Shattered** is the codename for this implementation, emphasizing the "broken into pieces" nature of the modular design.

---

## Architecture Overview

```
                    +------------------+
                    |   ArkhamFrame    |    <-- THE FRAME (immutable core)
                    |   (Core Infra)   |
                    +--------+---------+
                             |
                    +--------+---------+
                    |   arkham-shell   |    <-- THE SHELL (UI renderer)
                    | (React/TypeScript)|
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |         |          |          |         |
   +----v----+ +--v--+ +-----v-----+ +--v--+ +---v---+
   |Dashboard| | ACH | |  Search   | |Parse| | Graph |  <-- SHARDS
   | Shard   | |Shard| |  Shard    | |Shard| | Shard |
   +---------+ +-----+ +-----------+ +-----+ +-------+
```

### Core Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards MUST NOT import other shards directly
3. **Schema Isolation**: Each shard gets its own PostgreSQL schema (`arkham_{shard_name}`)
4. **Event-Driven Communication**: Shards communicate via the EventBus
5. **Self-Contained**: Each shard has its own manifest, API routes, workers, and UI components

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Frame Foundation Services | COMPLETE |
| Phase 2 | Data Services | COMPLETE |
| Phase 3 | Pipeline Refactoring | COMPLETE |
| Phase 4 | UI Shell Integration | COMPLETE |
| Phase 5 | Output Services + Shard Compliance | COMPLETE |

---

## Phase 1: Frame Foundation Services [COMPLETE]

### Goals
- Create the core ArkhamFrame package
- Implement foundational services
- Define the Shard interface (ABC)

### Deliverables

1. **ArkhamFrame Package** (`packages/arkham-frame/`)
   - `arkham_frame/__init__.py` - Package exports
   - `arkham_frame/frame.py` - Main Frame orchestrator
   - `arkham_frame/shard_interface.py` - ArkhamShard ABC, ShardManifest dataclass
   - `arkham_frame/main.py` - FastAPI application entry point

2. **Foundation Services** (`arkham_frame/services/`)
   - `config.py` - ConfigService (env + YAML loading)
   - `database.py` - DatabaseService (SQLAlchemy async)
   - `events.py` - EventBus (pub/sub)
   - `workers.py` - WorkerService (Redis-based job queues)
   - `resources.py` - ResourceService (hardware detection, GPU/CPU management)
   - `storage.py` - StorageService (file/blob storage with categories)
   - `documents.py` - DocumentService (full CRUD, content access)
   - `projects.py` - ProjectService (CRUD with settings management)

3. **Pipeline** (`arkham_frame/pipeline/`)
   - `base.py` - PipelineStage ABC, StageResult
   - `ingest.py` - IngestStage (thin dispatcher)
   - `ocr.py` - OCRStage (thin dispatcher)
   - `parse.py` - ParseStage (thin dispatcher)
   - `embed.py` - EmbedStage (thin dispatcher)
   - `coordinator.py` - PipelineCoordinator

4. **API Routes** (`arkham_frame/api/`)
   - `health.py` - Health check endpoints
   - `documents.py` - Document CRUD
   - `entities.py` - Entity CRUD
   - `projects.py` - Project CRUD
   - `shards.py` - Shard management
   - `events.py` - Event emission

### Status: COMPLETE

---

## Phase 2: Data Services [COMPLETE]

### Goals
- Implement data-focused services
- Add entity and vector management
- Enhance LLM service

### Deliverables

1. **EntityService** (`services/entities.py`)
   - Full CRUD for entities with batch creation
   - Canonical entity management (create, link, merge, find_or_create)
   - Relationship management with typed relationships
   - Entity types: PERSON, ORGANIZATION, LOCATION, DATE, MONEY, EVENT, PRODUCT, DOCUMENT, CONCEPT, OTHER
   - Relationship types: WORKS_FOR, LOCATED_IN, MEMBER_OF, OWNS, RELATED_TO, MENTIONED_WITH, etc.
   - Co-occurrence analysis (get_cooccurrences, get_entity_network)

2. **VectorService** (`services/vectors.py`)
   - Collection management (create, delete, list, get)
   - Standard collections auto-created: arkham_documents, arkham_chunks, arkham_entities
   - Vector operations: upsert, delete, search, scroll
   - Embedding generation with optional sentence-transformers
   - Distance metrics: COSINE, EUCLIDEAN, DOT

3. **ChunkService** (`services/chunks.py`)
   - 8 chunking strategies: FIXED_SIZE, FIXED_TOKENS, SENTENCE, PARAGRAPH, SEMANTIC, RECURSIVE, MARKDOWN, CODE
   - Token counting with tiktoken (falls back to character estimation)
   - Multi-page document chunking with page metadata

4. **LLMService** (`services/llm.py`) - Enhanced
   - Streaming support (stream_chat, stream_generate)
   - Structured output extraction (extract_json, extract_list)
   - JSON schema validation
   - Prompt template system with variables
   - Default prompts: summarize, extract_entities, qa, classify
   - Token usage tracking and statistics

### Status: COMPLETE

---

## Phase 3: Pipeline Refactoring [COMPLETE]

### Goals
- Move workers from Frame to shards (Option B architecture)
- Pipeline stages become thin dispatchers
- Shards register their own workers

### Deliverables

1. **WorkerService Enhancements** (`services/workers.py`)
   - Worker registration: `register_worker()`, `unregister_worker()`
   - Result waiting: `wait_for_result()`, `enqueue_and_wait()`
   - Shard-based worker discovery

2. **Worker Infrastructure** (`workers/`)
   - `base.py` - BaseWorker ABC with lifecycle management
   - `registry.py` - Redis-based worker registry
   - `runner.py` - Multiprocessing worker runner
   - `cli.py` - CLI for worker management
   - Core workers kept in Frame: `light_worker.py`, `db_worker.py`, `enrich_worker.py`, `whisper_worker.py`, `analysis_worker.py`

3. **Shard Workers Created**
   - arkham-shard-ingest: `extract_worker.py`, `file_worker.py`, `archive_worker.py`, `image_worker.py`
   - arkham-shard-parse: `ner_worker.py`
   - arkham-shard-embed: `embed_worker.py`
   - arkham-shard-ocr: `paddle_worker.py`, `qwen_worker.py`

4. **New Shard: arkham-shard-ocr**
   - Complete package with PaddleOCR and Qwen VLM workers
   - API endpoints: /health, /page, /document, /upload

### Worker Pools (14 total)

```
IO Pools:
  io-file         max=20                     [IMPLEMENTED]
  io-db           max=10                     [IMPLEMENTED]

CPU Pools:
  cpu-light       max=50                     [IMPLEMENTED]
  cpu-heavy       max= 6                     [IMPLEMENTED]
  cpu-ner         max= 8                     [IMPLEMENTED]
  cpu-extract     max= 4                     [IMPLEMENTED]
  cpu-image       max= 4                     [IMPLEMENTED]
  cpu-archive     max= 2                     [IMPLEMENTED]

GPU Pools:
  gpu-paddle      max= 1 (2000MB VRAM)       [IMPLEMENTED]
  gpu-qwen        max= 1 (8000MB VRAM)       [IMPLEMENTED]
  gpu-whisper     max= 1 (4000MB VRAM)       [IMPLEMENTED]
  gpu-embed       max= 1 (2000MB VRAM)       [IMPLEMENTED]

LLM Pools:
  llm-enrich      max= 4                     [IMPLEMENTED]
  llm-analysis    max= 2                     [IMPLEMENTED]
```

### Status: COMPLETE

---

## Phase 4: UI Shell Integration [COMPLETE]

### Goals
- Create React/TypeScript UI shell
- Build pages for all shards
- Integrate navigation from shard manifests

### Deliverables

1. **Shell Application** (`packages/arkham-shard-shell/`)
   - React + Vite + TypeScript
   - TailwindCSS styling
   - React Router navigation
   - API hooks for all shards

2. **UI Pages Created**
   - Dashboard: Service health, LLM config, database controls, worker management
   - Ingest: File upload, queue management
   - Search: Semantic/keyword/hybrid search with filters
   - OCR: Job submission and results viewer
   - Parse: Entity browser
   - Embed: Similarity calculator
   - Contradictions: Detection and detail view
   - Anomalies: Detection and detail view
   - ACH: Full ACH matrix interface

3. **Frame Updates**
   - `shard_interface.py`: Added `load_manifest_from_yaml()` utility
   - `ArkhamShard` base class auto-loads manifests in `__init__()`

### Status: COMPLETE

---

## Phase 5: Output Services + Shard Compliance [COMPLETE]

### Goals
- Verify all shards comply with v5 manifest schema
- Add Frame-level Output Services

### Part A: Shard Compliance Audit

All 11 shards verified and fixed for v5 compliance:

| Shard | Status | Fixes Applied |
|-------|--------|---------------|
| arkham-shard-dashboard | COMPLIANT | Added `super().__init__()`, renamed `get_routes()`, added events/state/capabilities |
| arkham-shard-ingest | COMPLIANT | Added `super().__init__()` |
| arkham-shard-search | COMPLIANT | Complete shard.yaml rewrite with v5 sections |
| arkham-shard-parse | COMPLIANT | Added `super().__init__()` |
| arkham-shard-embed | COMPLIANT | Already compliant |
| arkham-shard-ocr | COMPLIANT | Added `super().__init__()` |
| arkham-shard-contradictions | COMPLIANT | Added navigation, state, ui sections |
| arkham-shard-anomalies | COMPLIANT | Added navigation, state, ui sections |
| arkham-shard-graph | COMPLIANT | Created shard.yaml from scratch |
| arkham-shard-timeline | COMPLIANT | Created shard.yaml from scratch |
| arkham-shard-ach | COMPLIANT | Reference implementation |

### Part B: Output Services

1. **ExportService** (`services/export.py`)
   - Format exporters: JSON, CSV, Markdown, HTML, Text
   - Export options (metadata, pretty print, title, author)
   - Batch export to multiple formats
   - Export history tracking

2. **TemplateService** (`services/templates.py`)
   - Jinja2 template engine (with fallback for basic rendering)
   - Default templates: report_basic, document_summary, entity_report, analysis_report, email_notification
   - Variable extraction and validation

3. **NotificationService** (`services/notifications.py`)
   - Channel types: Log (default), Email (aiosmtplib), Webhook (aiohttp)
   - Notification types: info, success, warning, error, alert
   - Retry logic with exponential backoff

4. **SchedulerService** (`services/scheduler.py`)
   - APScheduler integration (with basic fallback)
   - Trigger types: cron, interval, date (one-time)
   - Job management: pause, resume, remove

### API Routes Added

- `/api/export/` - Export data to various formats
- `/api/templates/` - Template management and rendering
- `/api/notifications/` - Notification channels and sending
- `/api/scheduler/` - Job scheduling and management

### Status: COMPLETE

---

## Current Shard Inventory (11 Shards)

```
packages/
├── arkham-frame/                    # Core (IMMUTABLE)
├── arkham-shard-dashboard/          # System monitoring
├── arkham-shard-ingest/             # File intake + workers
├── arkham-shard-parse/              # NER/parsing + workers
├── arkham-shard-search/             # Semantic/keyword search
├── arkham-shard-ach/                # ACH analysis (reference impl)
├── arkham-shard-embed/              # Embeddings + workers
├── arkham-shard-contradictions/     # Contradiction detection
├── arkham-shard-anomalies/          # Anomaly detection
├── arkham-shard-ocr/                # OCR + workers
├── arkham-shard-graph/              # Entity graph visualization
├── arkham-shard-timeline/           # Timeline analysis
└── arkham-shard-shell/              # React UI shell
```

---

## Frame Services Summary

| Service | Description | Status |
|---------|-------------|--------|
| ConfigService | Environment + YAML configuration | COMPLETE |
| DatabaseService | PostgreSQL async operations | COMPLETE |
| VectorService | Qdrant vector operations | COMPLETE |
| LLMService | OpenAI-compatible LLM with streaming | COMPLETE |
| EventBus | Pub/sub event system | COMPLETE |
| WorkerService | Redis job queues with worker registration | COMPLETE |
| ResourceService | Hardware detection, GPU/CPU management | COMPLETE |
| StorageService | File/blob storage with categories | COMPLETE |
| DocumentService | Document CRUD and content access | COMPLETE |
| ProjectService | Project CRUD with settings | COMPLETE |
| EntityService | Entity and relationship management | COMPLETE |
| ChunkService | Text chunking strategies | COMPLETE |
| ExportService | Multi-format export | COMPLETE |
| TemplateService | Jinja2 template management | COMPLETE |
| NotificationService | Email/Webhook/Log notifications | COMPLETE |
| SchedulerService | APScheduler job scheduling | COMPLETE |

**Total: 16 services implemented**

---

## Development Commands

```bash
# Install Frame (from packages/arkham-frame/)
pip install -e .

# Install a shard (from packages/arkham-shard-{name}/)
pip install -e .

# Run Frame with all shards
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Run UI Shell
cd packages/arkham-shard-shell && npm run dev

# Start workers for a specific pool
python -m arkham_frame.workers --pool cpu-light --count 2

# List all worker pools
python -m arkham_frame.workers --list-pools

# Access API docs
# Open http://127.0.0.1:8100/docs
```

---

## Configuration

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `QDRANT_URL` - Qdrant connection string
- `LM_STUDIO_URL` - LLM API endpoint
- `VLM_ENDPOINT` - Vision LLM endpoint (for Qwen OCR)
- `WHISPER_MODEL` - Whisper model name

### Default Ports
| Service    | Port |
|------------|------|
| PostgreSQL | 5435 |
| Redis      | 6380 |
| Qdrant     | 6343 |
| LM Studio  | 1234 |
| Frame API  | 8100 |
| Shell UI   | 3100 |

---

## File Structure

```
SHATTERED/
├── docs/
│   ├── voltron_plan.md           # This file
│   ├── WORKER_ARCHITECTURE.md    # Worker pool design
│   ├── RESOURCE_DETECTION.md     # Hardware detection
│   └── SHARD_DISTRIBUTION.md     # Distribution strategy
│
├── packages/
│   ├── arkham-frame/             # Core infrastructure
│   │   ├── pyproject.toml
│   │   └── arkham_frame/
│   │       ├── __init__.py
│   │       ├── main.py           # FastAPI app
│   │       ├── frame.py          # ArkhamFrame orchestrator
│   │       ├── shard_interface.py
│   │       ├── api/              # REST API routes
│   │       ├── services/         # Core services (16)
│   │       ├── pipeline/         # Processing pipeline
│   │       └── workers/          # Worker infrastructure
│   │
│   ├── arkham-shard-dashboard/   # System monitoring
│   ├── arkham-shard-ingest/      # File intake
│   ├── arkham-shard-parse/       # NER/parsing
│   ├── arkham-shard-search/      # Search
│   ├── arkham-shard-ach/         # ACH analysis
│   ├── arkham-shard-embed/       # Embeddings
│   ├── arkham-shard-contradictions/
│   ├── arkham-shard-anomalies/
│   ├── arkham-shard-ocr/         # OCR
│   ├── arkham-shard-graph/       # Graph visualization
│   ├── arkham-shard-timeline/    # Timeline analysis
│   └── arkham-shard-shell/       # React UI
│
├── tests/
│   ├── test_workers.py           # Worker unit tests
│   ├── test_integration.py       # Integration tests
│   └── test_e2e_pipeline.py      # End-to-end pipeline tests
│
├── CLAUDE.md                     # Project guidelines
└── WORK_LOG.md                   # Development log
```

---

## Shard Development Guide

### Creating a New Shard

1. Create package directory:
   ```
   packages/arkham-shard-{name}/
   ├── pyproject.toml
   ├── shard.yaml
   ├── README.md
   └── arkham_shard_{name}/
       ├── __init__.py
       ├── shard.py
       ├── api.py
       └── workers/          # Optional
           └── my_worker.py
   ```

2. Define manifest (`shard.yaml` v5):
   ```yaml
   name: {name}
   version: 0.1.0
   description: "Shard description"
   entry_point: arkham_shard_{name}:{Name}Shard
   api_prefix: /api/{name}
   requires_frame: ">=0.1.0"

   navigation:
     category: Analysis|Data|Search|System|Visualize|Export
     order: 10-99
     icon: LucideIconName
     label: Display Name
     route: /{name}

   dependencies:
     services:
       - database
       - events
     optional:
       - llm
     shards: []  # Always empty!

   capabilities:
     - feature_one

   events:
     publishes:
       - {name}.entity.created
     subscribes:
       - other.event.completed

   state:
     strategy: url|local|session|none

   ui:
     has_custom_ui: true|false
   ```

3. Implement shard class:
   ```python
   from arkham_frame import ArkhamShard

   class {Name}Shard(ArkhamShard):
       name = "{name}"
       version = "0.1.0"
       description = "Shard description"

       async def initialize(self, frame) -> None:
           super().__init__()  # Required!
           self.frame = frame
           # Register workers if any
           worker_service = frame.get_service("workers")
           if worker_service:
               from .workers import MyWorker
               worker_service.register_worker(MyWorker)

       async def shutdown(self) -> None:
           # Unregister workers
           if self._frame:
               worker_service = self._frame.get_service("workers")
               if worker_service:
                   from .workers import MyWorker
                   worker_service.unregister_worker(MyWorker)

       def get_routes(self):
           from .api import router
           return router
   ```

4. Install and test:
   ```bash
   pip install -e .
   # Restart Frame - shard auto-loads via entry_points
   ```

---

## Progress Log

### 2024-12-20
- Initial architecture design
- Phase 1 & 2 started

### 2024-12-21
- Frame Foundation complete
- Dashboard Shard complete
- Ingest, Search, Parse, ACH shards implemented
- Worker infrastructure complete (14 pools)
- 4 production workers implemented
- Integration tests passing
- E2E pipeline verified
- ACH LLM integration complete
- OCR workers implemented
- Additional workers: FileWorker, ImageWorker, EnrichWorker
- Final 4 workers: DBWorker, ArchiveWorker, WhisperWorker, AnalysisWorker
- Embed, Contradictions, Anomalies shards implemented

### 2024-12-25
- Phase 1 & 2 services finalized (8 core services)
- Phase 3: Pipeline refactoring complete (workers moved to shards)
- Phase 4: UI Shell integration complete (pages for all shards)
- Phase 5: Output Services complete (Export, Template, Notification, Scheduler)
- Phase 5: All 11 shards v5 manifest compliant

---

## Future Considerations

- Graph shard full implementation (visualization)
- Timeline shard full implementation
- Additional UI polish
- Production deployment documentation
- Performance optimization
- Comprehensive test coverage
