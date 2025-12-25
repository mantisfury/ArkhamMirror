# ArkhamFrame Specification

**Version:** 0.1.0
**Date:** 2025-12-24

The Frame is the core orchestrator of SHATTERED. This document defines the Frame's architecture, contracts, and invariants that shard developers must understand.

---

## 1. Core Architecture

### 1.1 Startup Sequence

```
1. FastAPI app created with lifespan context manager
2. Frame Initialization:
   a. ConfigService initialized (environment vars + optional YAML)
   b. DatabaseService initialized (PostgreSQL via SQLAlchemy)
   c. VectorService initialized (Qdrant connection)
   d. LLMService initialized (OpenAI-compatible endpoint)
   e. EventBus initialized (in-memory pub/sub)
   f. WorkerService initialized (Redis queue connection)
   g. Document/Entity/Project services initialized
3. Shard Discovery (via entry_points):
   a. Load arkham.shards entry point group
   b. For each entry point:
      - Instantiate shard class (no args)
      - Call await shard.initialize(frame)
      - Get router via shard.get_routes() or shard.get_api_router()
      - Include router in FastAPI app
      - Add to frame.shards[shard_name]
4. API routes mounted:
   - Health: / and /health and /api/status
   - Documents: /api/documents/*
   - Entities: /api/entities/*
   - Projects: /api/projects/*
   - Shards: /api/shards/*
   - Events: /api/events/*
   - Frame: /api/frame/*
5. Optional: Shell static serving (if ARKHAM_SERVE_SHELL=true)
```

### 1.2 Shutdown Sequence

```
1. For each shard in frame.shards:
   a. Call await shard.shutdown()
   b. Log success/failure
2. Frame shutdown (reverse order):
   a. WorkerService.shutdown()
   b. EventBus.shutdown()
   c. LLMService.shutdown()
   d. VectorService.shutdown()
   e. DatabaseService.shutdown()
```

### 1.3 Shard Lifecycle

| Phase | Method | Description |
|-------|--------|-------------|
| Load | `shard_class()` | Constructor called with no arguments |
| Initialize | `await shard.initialize(frame)` | Shard receives Frame reference, sets up subscriptions |
| Running | N/A | Shard handles requests, emits events |
| Shutdown | `await shard.shutdown()` | Cleanup, unsubscribe from events |

**Failure Handling:**
- If a shard fails to load (exception in constructor or initialize), it is logged and skipped
- Other shards continue to load normally
- Frame continues operation with partial shard set
- No cascade failure - one shard crash does not affect others

---

## 2. Service Catalog

### 2.1 Available Services

| Service | Name(s) | Type | Description |
|---------|---------|------|-------------|
| config | `config` | ConfigService | Environment/YAML configuration |
| database | `database`, `db` | DatabaseService | PostgreSQL with schema isolation |
| vectors | `vectors` | VectorService | Qdrant vector store |
| llm | `llm` | LLMService | OpenAI-compatible LLM |
| events | `events` | EventBus | Pub/sub messaging |
| workers | `workers` | WorkerService | Redis job queues |
| documents | `documents` | DocumentService | Document CRUD |
| entities | `entities` | EntityService | Entity CRUD |
| projects | `projects` | ProjectService | Project management |

### 2.2 Service Access Pattern

```python
class MyShard(ArkhamShard):
    async def initialize(self, frame):
        self.frame = frame

        # Get services
        self.events = frame.get_service("events")
        self.llm = frame.get_service("llm")
        self.db = frame.get_service("database")

        # Services may be None if unavailable
        if self.llm and self.llm.is_available():
            # Use LLM
            pass
```

### 2.3 Service Availability

Services may fail to initialize. Shards must handle missing services gracefully:

```python
# GOOD - Check before use
if self.llm and self.llm.is_available():
    response = await self.llm.generate(prompt)
else:
    return {"error": "LLM unavailable"}, 503

# BAD - Assume service exists
response = await self.llm.generate(prompt)  # Crashes if llm is None
```

---

## 3. EventBus Implementation

### 3.1 Architecture

- **Type:** In-memory pub/sub with fnmatch pattern matching
- **Async:** Events delivered asynchronously via `await emit()`
- **History:** Last 1000 events retained in memory
- **Sequence:** Monotonic sequence numbers for ordering

### 3.2 API

```python
# Subscribe (synchronous, non-async)
event_bus.subscribe("ach.matrix.*", handler_callback)
event_bus.subscribe("document.processed", handler_callback)

# Unsubscribe (synchronous, non-async)
event_bus.unsubscribe("ach.matrix.*", handler_callback)

# Emit (async)
await event_bus.emit(
    event_type="ach.matrix.created",
    payload={"matrix_id": "abc123", "title": "My Matrix"},
    source="ach-shard"
)

# Query history
events = event_bus.get_events(source="ach-shard", limit=50)
```

### 3.3 Pattern Matching

Uses Python `fnmatch` for patterns:
- `*` matches any sequence of characters
- `?` matches any single character
- `[seq]` matches any character in seq

Examples:
- `ach.*` matches `ach.matrix.created`, `ach.evidence.added`
- `*.created` matches `ach.matrix.created`, `document.created`
- `document.processed` matches exactly

### 3.4 Ordering Guarantees

| Guarantee | Status |
|-----------|--------|
| Sequential delivery to single subscriber | YES |
| Cross-subscriber ordering | NO |
| At-least-once delivery | NO (best effort) |
| Exactly-once delivery | NO |
| Persistent (survives restart) | NO |

### 3.5 Error Handling

- Callback exceptions are caught and logged
- Other callbacks continue to receive the event
- No dead letter queue (failed deliveries are lost)

---

## 4. Manifest Validation

### 4.1 What Frame Validates

| Field | Validation |
|-------|------------|
| Entry point loadable | Must resolve to a class |
| Constructor callable | Must work with no arguments |
| initialize() async | Must be awaitable |
| get_routes() | Must return Router or None |

### 4.2 What Frame Does NOT Validate

| Field | Status |
|-------|--------|
| Manifest schema version | Not validated |
| Required services availability | Not validated |
| API prefix uniqueness | Not validated (first wins) |
| Route collision detection | Not validated |
| Navigation category | Not validated |
| Event names | Not validated |
| Capability declarations | Not validated |

### 4.3 Rejection Causes

A shard is rejected (not loaded) if:
1. Entry point cannot be resolved (import error)
2. Shard class constructor throws exception
3. `initialize(frame)` throws exception

On rejection:
- Exception is logged with traceback
- Other shards continue loading
- Frame continues with partial shard set

---

## 5. API Surface

### 5.1 Frame Endpoints (`/api/frame/*`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/frame/badges` | Aggregate badge counts from all shards |
| GET | `/api/frame/health` | Frame health status |
| GET | `/api/frame/state` | Detailed Frame state |

### 5.2 Shard Management (`/api/shards/*`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/shards/` | List all shards with v5 manifests |
| GET | `/api/shards/{name}` | Get specific shard manifest |
| POST | `/api/shards/load` | Load shard dynamically (NOT IMPLEMENTED) |
| POST | `/api/shards/{name}/unload` | Unload shard (NOT IMPLEMENTED) |
| GET | `/api/shards/{name}/routes` | Get shard's API routes |

### 5.3 Event Management (`/api/events/*`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/events/` | List recent events |
| POST | `/api/events/emit` | Emit an event |

### 5.4 Health (`/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root endpoint with version |
| GET | `/health` | Health check with Frame state |
| GET | `/api/status` | Detailed service status |

### 5.5 Data APIs

| Prefix | Description |
|--------|-------------|
| `/api/documents/*` | Document CRUD |
| `/api/entities/*` | Entity CRUD |
| `/api/projects/*` | Project management |

---

## 6. Shard Route Registration

### 6.1 Route Mounting

Shards register routes by returning a FastAPI APIRouter:

```python
class MyShard(ArkhamShard):
    def get_routes(self):
        from .api import router  # Router with prefix="/api/myshard"
        return router
```

**Important:** Shard routers should include their own `/api/{shard_name}` prefix. The Frame mounts them directly to the app without additional prefixing.

### 6.2 Collision Behavior

If multiple shards register the same route:
- **First registered wins**
- No error raised
- No warning logged
- Second shard's route is silently ignored

**Best Practice:** Always use unique prefixes matching shard name: `/api/{shard_name}/`

---

## 7. Database Architecture

### 7.1 Schema Isolation

Each shard gets its own PostgreSQL schema: `arkham_{shard_name}`

```python
# Shard creates its own tables in its schema
async def initialize(self, frame):
    self.db = frame.get_service("database")
    # Create schema: arkham_myshard
    # Create tables within that schema
```

### 7.2 Frame-Owned State

The Frame itself owns these schemas:
- `arkham_core` - Core metadata (projects, etc.)
- Individual shard schemas are shard-owned

### 7.3 Project Context

- Projects are global Frame state
- Shards can filter by `project_id`
- No automatic project context injection

---

## 8. Hard Invariants for Shard Development

### 8.1 MUST Do

| Rule | Reason |
|------|--------|
| Inherit from `ArkhamShard` | Required for discovery |
| Implement `initialize(frame)` and `shutdown()` | Lifecycle management |
| Store Frame reference as `self.frame` | Service access |
| Check service availability before use | Services may be None |
| Use `frame.get_service()` for services | Only official access method |
| Handle own exceptions in callbacks | Don't crash EventBus |
| Use own API prefix `/api/{shard_name}/` | Avoid collisions |

### 8.2 MUST NOT Do

| Rule | Reason |
|------|--------|
| Import other shards directly | Breaks isolation |
| Modify Frame services | Frame owns services |
| Assume services exist | May be unavailable |
| Block in event callbacks | Degrades system |
| Use hard-coded database schemas | Use shard-specific schemas |
| Mount routes at root `/` | Reserved for Frame |
| Modify Frame.shards dict | Frame-owned state |

### 8.3 Constructor Rules

```python
# GOOD - No required arguments
class MyShard(ArkhamShard):
    def __init__(self):
        super().__init__()
        self.my_state = {}

# BAD - Required arguments
class MyShard(ArkhamShard):
    def __init__(self, config):  # Frame can't provide this
        ...
```

### 8.4 Initialization Rules

```python
async def initialize(self, frame):
    # MUST store frame reference
    self.frame = frame

    # SHOULD get services
    self.events = frame.get_service("events")

    # SHOULD subscribe to events
    if self.events:
        self.events.subscribe("document.processed", self.on_document)

    # SHOULD NOT block for long periods
    # SHOULD NOT make external API calls that may hang
```

---

## 9. Graceful Degradation

### 9.1 Service Unavailability

| Service | Shard Response |
|---------|----------------|
| LLM unavailable | Return 503, disable AI features |
| Database unavailable | In-memory operation or 503 |
| Vectors unavailable | Disable semantic search |
| Events unavailable | Log warning, continue without events |
| Workers unavailable | Synchronous processing |

### 9.2 Partial Shard Loading

If 3 of 5 shards fail to load:
- Frame continues with 2 working shards
- `/api/shards/` returns only loaded shards
- Failed shards logged but not retried

### 9.3 Runtime Shard Failure

If a shard throws during request handling:
- FastAPI returns 500 to client
- Other shards unaffected
- No automatic recovery/restart

---

## 10. Configuration

### 10.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://anom:anompass@localhost:5435/anomdb` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6380` | Redis connection |
| `QDRANT_URL` | `http://localhost:6343` | Qdrant connection |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LLM endpoint |
| `CONFIG_PATH` | None | Path to YAML config file |
| `ARKHAM_SERVE_SHELL` | `false` | Enable Shell static serving |

### 10.2 Config Access

```python
# In shard
config = frame.get_service("config")
value = config.get("some.nested.key", default="fallback")
```

---

## 11. Worker Pool Architecture

### 11.1 Pool Definitions

| Pool | Type | Max Workers | Purpose |
|------|------|-------------|---------|
| io-file | IO | 20 | File operations |
| io-db | IO | 10 | Database operations |
| cpu-light | CPU | 50 | Light processing |
| cpu-heavy | CPU | 6 | Heavy computation |
| cpu-ner | CPU | 8 | Named entity recognition |
| cpu-extract | CPU | 4 | Text extraction |
| cpu-image | CPU | 4 | Image processing |
| cpu-archive | CPU | 2 | Archive extraction |
| gpu-paddle | GPU | 1 | PaddleOCR |
| gpu-qwen | GPU | 1 | Qwen vision |
| gpu-whisper | GPU | 1 | Audio transcription |
| gpu-embed | GPU | 1 | Embedding generation |
| llm-enrich | LLM | 4 | LLM enrichment |
| llm-analysis | LLM | 2 | LLM analysis |

### 11.2 Job Enqueue Pattern

```python
workers = frame.get_service("workers")
if workers and workers.is_available():
    job = await workers.enqueue(
        pool="cpu-light",
        job_id=f"task-{uuid4()}",
        payload={"document_id": doc_id, "action": "process"},
        priority=1,  # Lower = higher priority
    )
```

---

## 12. Public Exports

### 12.1 Main Exports (from `arkham_frame`)

```python
from arkham_frame import (
    # Shard interface
    ArkhamShard,
    ShardManifest,

    # Frame
    ArkhamFrame,
    get_frame,

    # Services
    ConfigService,

    # All exception types...
)
```

### 12.2 Shard Manifest v5 Dataclasses

```python
from arkham_frame.shard_interface import (
    ShardManifest,
    NavigationConfig,
    SubRoute,
    DependencyConfig,
    EventConfig,
    StateConfig,
    UIConfig,
)
```

---

## 13. Testing Against Frame

### 13.1 Minimal Test Setup

```python
import pytest
from arkham_frame import ArkhamFrame

@pytest.fixture
async def frame():
    f = ArkhamFrame()
    await f.initialize()
    yield f
    await f.shutdown()

async def test_my_shard(frame):
    from my_shard import MyShard
    shard = MyShard()
    await shard.initialize(frame)

    # Test shard functionality

    await shard.shutdown()
```

### 13.2 Service Mocking

```python
class MockEventBus:
    def __init__(self):
        self.emitted = []

    async def emit(self, event_type, payload, source):
        self.emitted.append((event_type, payload, source))

    def subscribe(self, pattern, callback):
        pass

# Inject mock
frame.events = MockEventBus()
```

---

## Summary

The Frame provides:
1. **Service orchestration** - Initialize/shutdown in correct order
2. **Shard lifecycle** - Discovery, loading, shutdown
3. **Event messaging** - In-memory pub/sub with patterns
4. **Service access** - `get_service()` for dependency injection
5. **API hosting** - FastAPI with shard route mounting
6. **Graceful degradation** - Continue with partial services/shards

Shards must:
1. Inherit from `ArkhamShard`
2. Implement `initialize()` and `shutdown()`
3. Access services only via Frame
4. Handle service unavailability
5. Use unique API prefixes
6. Never import other shards
