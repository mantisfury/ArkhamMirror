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
                    |   ArkhamFrame    |
                    |   (Core Infra)   |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |                    |                    |
+-------v-------+   +--------v--------+   +-------v-------+
| Dashboard     |   | Search Shard    |   | Analysis      |
| Shard         |   | (Future)        |   | Shard         |
| - Health      |   | - Semantic      |   | (Future)      |
| - LLM Config  |   | - Keyword       |   | - Contradictions
| - DB Controls |   | - Filters       |   | - Timeline    |
| - Workers     |   |                 |   | - Entities    |
+---------------+   +-----------------+   +---------------+
```

### Core Principles

1. **Frame is the Single Source of Truth**: Shards MUST NOT import other shards directly
2. **Schema Isolation**: Each shard gets its own PostgreSQL schema (`arkham_{shard_name}`)
3. **Event-Driven Communication**: Shards communicate via the EventBus
4. **Self-Contained**: Each shard has its own manifest, API routes, and UI components

---

## Phase 1: Frame Foundation [COMPLETE]

### Goals
- Create the core ArkhamFrame package
- Implement all base services
- Define the Shard interface (ABC)
- Build the document processing pipeline

### Deliverables

1. **ArkhamFrame Package** (`packages/arkham-frame/`)
   - `arkham_frame/__init__.py` - Package exports
   - `arkham_frame/frame.py` - Main Frame orchestrator
   - `arkham_frame/shard_interface.py` - ArkhamShard ABC, ShardManifest dataclass
   - `arkham_frame/main.py` - FastAPI application entry point

2. **Services** (`arkham_frame/services/`)
   - `config.py` - ConfigService (env + YAML loading)
   - `database.py` - DatabaseService (SQLAlchemy async)
   - `documents.py` - DocumentService
   - `entities.py` - EntityService
   - `projects.py` - ProjectService
   - `vectors.py` - VectorService (Qdrant)
   - `llm.py` - LLMService (OpenAI-compatible)
   - `events.py` - EventBus (pub/sub)
   - `workers.py` - WorkerService (Redis/RQ)

3. **Pipeline** (`arkham_frame/pipeline/`)
   - `base.py` - PipelineStage ABC, StageResult
   - `ingest.py` - IngestStage
   - `ocr.py` - OCRStage
   - `parse.py` - ParseStage
   - `embed.py` - EmbedStage
   - `coordinator.py` - PipelineCoordinator

4. **API Routes** (`arkham_frame/api/`)
   - `health.py` - Health check endpoints
   - `documents.py` - Document CRUD
   - `entities.py` - Entity CRUD
   - `projects.py` - Project CRUD
   - `shards.py` - Shard management
   - `events.py` - Event emission

### Status: COMPLETE
- All services implemented
- Pipeline stages implemented
- API routes implemented
- Frame boots successfully
- OpenAPI docs available at `/docs`

---

## Phase 2: Dashboard Shard [COMPLETE]

### Goals
- Create the first shard as a template for others
- Implement system monitoring and controls
- Add LLM configuration UI
- Add database controls
- Add worker management

### Deliverables

1. **Dashboard Shard Package** (`packages/arkham-shard-dashboard/`)
   - `pyproject.toml` - Package definition
   - `shard.yaml` - Shard manifest
   - `arkham_shard_dashboard/__init__.py`
   - `arkham_shard_dashboard/shard.py` - DashboardShard class
   - `arkham_shard_dashboard/api.py` - FastAPI routes

2. **API Endpoints**
   - `GET /api/dashboard/health` - Service health status
   - `GET /api/dashboard/llm` - LLM configuration
   - `POST /api/dashboard/llm` - Update LLM config
   - `POST /api/dashboard/llm/test` - Test LLM connection
   - `GET /api/dashboard/database` - Database info
   - `POST /api/dashboard/database/migrate` - Run migrations
   - `POST /api/dashboard/database/reset` - Reset database
   - `POST /api/dashboard/database/vacuum` - VACUUM ANALYZE
   - `GET /api/dashboard/workers` - Active workers
   - `GET /api/dashboard/queues` - Queue statistics
   - `POST /api/dashboard/workers/scale` - Scale workers
   - `POST /api/dashboard/workers/start` - Start worker
   - `POST /api/dashboard/workers/stop` - Stop worker
   - `GET /api/dashboard/events` - Recent events
   - `GET /api/dashboard/errors` - Recent errors

3. **UI Components** (Future)
   - Service health cards
   - LLM provider selector
   - Database control panel
   - Worker management table
   - Event log viewer

### Status: COMPLETE
- Shard package created
- Manifest defined
- DashboardShard class implemented
- All API routes implemented
- Successfully loads into Frame
- All endpoints tested and working

---

## Phase 3: Search Shard [PLANNED]

### Goals
- Port search functionality from existing ArkhamMirror app
- Implement semantic search with Qdrant
- Add keyword/regex search
- Build search filters

### Deliverables
- `packages/arkham-shard-search/`
- Search API endpoints
- Search UI components

---

## Phase 4: Analysis Shard [PLANNED]

### Goals
- Port analysis features from existing app
- Contradiction detection
- Timeline analysis
- Entity analysis

---

## Phase 5: Ingest Shard [PLANNED]

### Goals
- Port document ingestion
- OCR processing
- Document splitting

---

## Development Commands

```bash
# Install Frame (from packages/arkham-frame/)
pip install -e .

# Install Dashboard Shard (from packages/arkham-shard-dashboard/)
pip install -e .

# Run Frame with all shards
cd packages/arkham-frame
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Access API docs
# Open http://127.0.0.1:8100/docs

# Test endpoints
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8100/api/dashboard/health
curl http://127.0.0.1:8100/api/dashboard/llm
```

---

## File Structure

```
SHATTERED/
|-- docs/
|   |-- voltron_plan.md       # This file
|
|-- packages/
|   |-- arkham-frame/          # Core infrastructure
|   |   |-- pyproject.toml
|   |   |-- arkham_frame/
|   |       |-- __init__.py
|   |       |-- main.py        # FastAPI app
|   |       |-- frame.py       # ArkhamFrame orchestrator
|   |       |-- shard_interface.py
|   |       |-- api/           # REST API routes
|   |       |-- services/      # Core services
|   |       |-- pipeline/      # Processing pipeline
|   |       |-- models/        # Data models (future)
|   |       |-- registry/      # Shard registry (future)
|   |
|   |-- arkham-shard-dashboard/ # Dashboard shard
|   |   |-- pyproject.toml
|   |   |-- shard.yaml         # Shard manifest
|   |   |-- arkham_shard_dashboard/
|   |       |-- __init__.py
|   |       |-- shard.py       # DashboardShard class
|   |       |-- api.py         # FastAPI routes
|   |
|   |-- arkham-shard-search/   # Search shard (future)
|   |-- arkham-shard-analysis/ # Analysis shard (future)
|   |-- arkham-shard-ingest/   # Ingest shard (future)
```

---

## Shard Development Guide

### Creating a New Shard

1. Create package directory:
   ```
   packages/arkham-shard-{name}/
   |-- pyproject.toml
   |-- shard.yaml
   |-- arkham_shard_{name}/
       |-- __init__.py
       |-- shard.py
       |-- api.py
   ```

2. Define manifest (`shard.yaml`):
   ```yaml
   name: {name}
   version: "0.1.0"
   description: "Description of the shard"
   entry_point: arkham_shard_{name}.shard:{Name}Shard
   api_prefix: /api/{name}
   menu:
     - id: main
       label: Main
       icon: Icon
       path: /{name}
   requires:
     - database
     - events
   ```

3. Implement shard class:
   ```python
   from arkham_frame import ArkhamShard, ShardManifest

   class {Name}Shard(ArkhamShard):
       @property
       def manifest(self) -> ShardManifest:
           # Load and return manifest

       async def initialize(self) -> None:
           # Setup

       async def shutdown(self) -> None:
           # Cleanup

       def get_api_router(self):
           from .api import router
           return router
   ```

4. Install and test:
   ```bash
   pip install -e .
   # Restart Frame - shard auto-loads
   ```

---

## Configuration

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `QDRANT_URL` - Qdrant connection string
- `LM_STUDIO_URL` - LLM API endpoint

### Default Ports
| Service    | Port |
|------------|------|
| PostgreSQL | 5435 |
| Redis      | 6380 |
| Qdrant     | 6343 |
| LM Studio  | 1234 |
| Frame API  | 8100 |

---

## Progress Log

### 2024-12-20
- Phase 1 Complete: Frame Foundation
  - All services implemented
  - Pipeline stages implemented
  - API routes implemented
  - Frame boots successfully

- Phase 2 Complete: Dashboard Shard
  - Shard package created
  - All endpoints implemented
  - Successfully integrates with Frame

### Next Steps
- Phase 3: Search Shard
- Phase 4: Analysis Shard
- Phase 5: Ingest Shard
- Add UI components to shards
