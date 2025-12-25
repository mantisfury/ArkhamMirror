# ArkhamFrame Architecture Analysis Report

> Comprehensive analysis of the SHATTERED modular architecture
> Generated: December 2025

---

## Executive Summary

The SHATTERED project implements a **Voltron-style modular architecture** where the **ArkhamFrame** serves as immutable core infrastructure, and **shards** are self-contained feature modules that plug into the frame. After thorough analysis of the codebase, documentation, and architectural patterns, this report addresses whether the frame should be streamlined by moving services to shards.

**Key Finding:** The current frame architecture is **well-designed and appropriately scoped**. While some services are currently stub implementations, moving them to shards would violate the architectural principles and introduce unwanted coupling. The frame correctly owns infrastructure, global state, and orchestration.

---

## Table of Contents

1. [Current Frame Architecture](#1-current-frame-architecture)
2. [Service Analysis](#2-service-analysis)
3. [Pipeline Analysis](#3-pipeline-analysis)
4. [Shard Compliance Assessment](#4-shard-compliance-assessment)
5. [Streamlining Recommendations](#5-streamlining-recommendations)
6. [What Should Stay in Frame](#6-what-should-stay-in-frame)
7. [What Could Theoretically Move](#7-what-could-theoretically-move)
8. [Final Recommendations](#8-final-recommendations)

---

## 1. Current Frame Architecture

### Overview

```
packages/arkham-frame/
├── arkham_frame/
│   ├── __init__.py          # Package exports
│   ├── frame.py              # ArkhamFrame orchestrator
│   ├── shard_interface.py    # ArkhamShard ABC + ShardManifest
│   ├── main.py               # FastAPI app + shard loading
│   ├── api/                  # REST endpoints
│   │   ├── health.py         # Health checks
│   │   ├── documents.py      # Document CRUD
│   │   ├── entities.py       # Entity CRUD
│   │   ├── projects.py       # Project CRUD
│   │   ├── events.py         # Event emission
│   │   ├── shards.py         # Shard management
│   │   └── frame.py          # Frame state/badges
│   ├── services/             # Core services
│   │   ├── config.py         # ConfigService
│   │   ├── database.py       # DatabaseService (PostgreSQL)
│   │   ├── documents.py      # DocumentService
│   │   ├── entities.py       # EntityService
│   │   ├── events.py         # EventBus
│   │   ├── llm.py            # LLMService
│   │   ├── projects.py       # ProjectService
│   │   ├── vectors.py        # VectorService (Qdrant)
│   │   └── workers.py        # WorkerService (Redis)
│   ├── models/               # SQLAlchemy models
│   │   ├── base.py           # Base, TimestampMixin
│   │   ├── document.py       # Project, Document, Chunk, etc.
│   │   ├── entity.py         # CanonicalEntity, EntityRelationship
│   │   └── event.py          # Event, ShardRegistry
│   └── pipeline/             # Document processing
│       ├── base.py           # PipelineStage ABC
│       ├── ingest.py         # IngestStage
│       ├── ocr.py            # OCRStage
│       ├── parse.py          # ParseStage
│       ├── embed.py          # EmbedStage
│       └── coordinator.py    # PipelineCoordinator
```

### Dependencies (from pyproject.toml)

```
fastapi>=0.104.0      # Web framework
uvicorn>=0.24.0       # ASGI server
sqlalchemy>=2.0.0     # Database ORM
httpx>=0.25.0         # HTTP client (for LLM)
pyyaml>=6.0           # Manifest parsing
redis>=5.0.0          # Worker queues
qdrant-client>=1.6.0  # Vector storage
```

---

## 2. Service Analysis

### Core Infrastructure Services (MUST remain in Frame)

| Service | Purpose | Status | Rationale |
|---------|---------|--------|-----------|
| **ConfigService** | Environment/YAML config loading | Complete | Foundation for all other services |
| **DatabaseService** | PostgreSQL connection pooling | Complete | Schema isolation, connection management |
| **VectorService** | Qdrant vector store | Stub | Vector operations are foundational |
| **LLMService** | OpenAI-compatible LLM | Complete | Shared resource, connection pooling |
| **EventBus** | Pub/sub messaging | Complete | Inter-shard communication backbone |
| **WorkerService** | Redis job queues | Complete | Distributed processing infrastructure |

### Data Access Services (Currently in Frame)

| Service | Purpose | Status | Analysis |
|---------|---------|--------|----------|
| **DocumentService** | Document CRUD | Stub | Provides read access to Frame-owned data |
| **EntityService** | Entity CRUD | Stub | Provides read access to Frame-owned data |
| **ProjectService** | Project management | Stub | Provides access to project containers |

### Why Data Services Should Stay in Frame

1. **Frame Owns the Data Models**: Document, Entity, Chunk, and Project models are defined in `arkham_frame.models`. Moving the service without the models would create circular dependencies.

2. **Schema Isolation Pattern**: Each shard gets `arkham_{shard_name}` schema, but documents/entities live in the core `arkham_frame` schema. Frame must own access to its schema.

3. **Cross-Shard Data Access**: Multiple shards need document/entity access (search, parse, graph, timeline, anomalies, contradictions). Having Frame provide this prevents N-to-1 shard dependencies.

4. **Read-Only Interface**: These services provide READ access to shared data. Write operations happen through the pipeline, which is Frame-owned.

---

## 3. Pipeline Analysis

### Current Pipeline Structure

The frame includes a document processing pipeline with 4 stages:

```
Ingest -> OCR -> Parse -> Embed
   |        |       |       |
   v        v       v       v
[stub]   [stub]  [stub]  [stub]
```

### Stage Analysis

| Stage | Worker Pools | Current State | Should Move? |
|-------|-------------|---------------|--------------|
| **IngestStage** | io-file, cpu-light | Stub | No - coordinates file intake |
| **OCRStage** | gpu-paddle, gpu-qwen | Stub | No - GPU resource management |
| **ParseStage** | cpu-ner | Stub | No - entity extraction |
| **EmbedStage** | gpu-embed | Stub | No - vector generation |

### Pipeline Architecture Decision

**The pipeline should remain in Frame for several reasons:**

1. **Resource Coordination**: The pipeline manages GPU memory allocation across exclusive model groups (qwen vs whisper). This requires global visibility.

2. **Fast Path Optimization**: The router determines skip conditions (text PDFs skip OCR). This decision needs global context.

3. **Context Propagation**: Each stage passes output to the next. Distributing this across shards would require additional event choreography.

4. **Worker Pool Ownership**: Per WORKER_ARCHITECTURE.md, specific shards "own" worker pools but the pipeline routes work. The routing logic should be centralized.

### Relationship to Shards

While the **pipeline stays in Frame**, specific shards can:
- **Subscribe to events** like `document.processed` to trigger their own workflows
- **Add processing** through their own worker pool handlers
- **Extend functionality** without modifying the core pipeline

Example: The **contradictions shard** subscribes to `document.ingested` to run its analysis after ingestion completes. This is the correct pattern.

---

## 4. Shard Compliance Assessment

### Manifest v5 Compliance

| Shard | pyproject.toml | shard.yaml | v5 Compliant | Priority |
|-------|----------------|------------|--------------|----------|
| **ach** (reference) | Complete | Complete | YES | - |
| **dashboard** | Complete | Complete | YES | - |
| **ingest** | Complete | Complete | YES | - |
| **search** | Complete | Minimal | PARTIAL | High |
| **parse** | Complete | Minimal | PARTIAL | High |
| **embed** | Complete | Partial | PARTIAL | High |
| **graph** | Complete | MISSING | NO | Critical |
| **timeline** | Complete | MISSING | NO | Critical |
| **anomalies** | Complete | MISSING | NO | Critical |
| **contradictions** | Complete | MISSING | NO | Critical |

### Inter-Shard Dependencies

**Status: COMPLIANT**

Zero direct Python imports between shards were found. All communication follows the event-driven pattern:

```python
# Publishing shard (ingest)
await self.frame.events.emit("ingest.job.completed", {...}, source="ingest")

# Subscribing shard (parse)
event_bus.subscribe("ingest.job.completed", self.handle_job_completed)
```

### Frame Service Usage Patterns

All shards correctly use `frame.get_service()` for service access:

```python
async def initialize(self, frame):
    self.frame = frame
    self.db = frame.get_service("database")
    self.events = frame.get_service("events")
    # Graceful degradation for optional services
    self.llm = frame.get_service("llm")  # May be None
```

---

## 5. Streamlining Recommendations

### What "Streamlining" Could Mean

The question asks whether the frame should be more streamlined by moving services to shards. Let's analyze the options:

#### Option A: Move Database Service to Shard

**Result:** REJECTED

- Every shard would depend on the "database shard"
- Violates "no shard-to-shard dependencies" rule
- Creates single point of failure that ISN'T the frame

#### Option B: Move Entity Extraction to Shard

**Result:** ALREADY THE CASE

- EntityService in Frame is just a stub accessor
- Actual entity extraction logic can (and should) be in the **parse shard**
- Frame provides storage access; shards provide intelligence

#### Option C: Move LLM Service to Shard

**Result:** REJECTED

- LLM is used by multiple shards: ACH (optional), contradictions (optional), analysis features
- Moving to shard creates "LLM shard" dependency
- Frame correctly provides shared resource access

#### Option D: Move Vector Service to Shard

**Result:** REJECTED

- Vectors are foundational for search, embeddings, similarity
- Multiple shards need vector access
- Same reasoning as database

#### Option E: Make Services Lazy/Optional

**Result:** ALREADY IMPLEMENTED

```python
async def initialize(self) -> None:
    try:
        # ...initialize service...
    except Exception as e:
        logger.warning(f"Service failed to initialize: {e}")
```

Services that fail to initialize become None, and shards gracefully degrade.

---

## 6. What Should Stay in Frame

### Absolutely Immutable (Never Move)

1. **ConfigService** - Foundation for all configuration
2. **DatabaseService** - Connection pooling, schema management
3. **EventBus** - Inter-shard communication backbone
4. **WorkerService** - Distributed job queue coordination
5. **Shard loading/discovery** - Entry point mechanism
6. **All data models** - Document, Entity, Project, etc.
7. **Health/Frame API endpoints** - System visibility

### Should Stay (Even Though Currently Stubs)

1. **VectorService** - Shared vector store access
2. **LLMService** - Shared LLM access
3. **DocumentService** - Read-only document access
4. **EntityService** - Read-only entity access
5. **ProjectService** - Project container access
6. **PipelineCoordinator** - Stage orchestration

### Rationale

The Frame provides:
- **Infrastructure** that multiple shards need
- **Global state** that must be consistent
- **Resource pooling** for expensive connections
- **Coordination** across independent modules

If any of these moved to a shard, other shards would need to depend on that shard, violating the core architectural principle.

---

## 7. What Could Theoretically Move

### Business Logic That Happens to Be in Frame

The following are currently stub implementations in Frame but could have their **implementation logic** (not service interface) in shards:

| Current Location | Could Move To | Mechanism |
|-----------------|---------------|-----------|
| ParseStage.process() | parse shard | Worker handler |
| EmbedStage.process() | embed shard | Worker handler |
| OCRStage.process() | ingest shard | Worker handler |

**Important Distinction**: The **stage definitions and coordinator** stay in Frame. The **actual processing logic** runs in shard-owned worker handlers.

This is already the designed pattern per WORKER_ARCHITECTURE.md:

```yaml
ingest_shard:
  owns_queues:
    - cpu-archive
    - cpu-heavy
    - cpu-image
    - io-file
  routes_to:
    - gpu-paddle    # OCR shard handles
    - gpu-qwen      # OCR shard handles
```

### Recommendation: Implement, Don't Move

Instead of moving services, **complete the stub implementations**:

1. **DocumentService/EntityService/ProjectService**: Implement the actual CRUD operations using the existing models.

2. **Pipeline Stages**: Implement actual processing logic that dispatches to worker pools.

3. **VectorService**: Implement search, upsert, and delete operations.

The services provide the **interface**; shards can provide **extended functionality** through events and workers.

---

## 8. Final Recommendations

### Keep the Current Architecture

The Frame/Shell/Shard separation is **correctly designed**. The frame is not bloated - it contains exactly what should be centralized:

- Connection pooling (database, vectors, LLM, Redis)
- Event orchestration
- Worker coordination
- Data model definitions
- Pipeline orchestration
- Shard discovery and loading

### Complete the Stubs

Rather than streamlining, **finish the implementation**:

1. Complete `DocumentService`, `EntityService`, `ProjectService` methods
2. Implement actual logic in pipeline stages
3. Connect stages to worker pools via shard handlers
4. Implement VectorService search operations

### Fix Manifest Compliance

**Critical Priority** - Create shard.yaml for:
- arkham-shard-graph
- arkham-shard-timeline
- arkham-shard-anomalies
- arkham-shard-contradictions

**High Priority** - Complete shard.yaml for:
- arkham-shard-search (add navigation)
- arkham-shard-parse (add navigation)
- arkham-shard-embed (add navigation)

### Architectural Validation

The current design correctly implements:

| Principle | Status |
|-----------|--------|
| Frame is immutable core | YES |
| Shards cannot depend on shards | YES |
| Event-driven communication | YES |
| Schema isolation | YES |
| Service graceful degradation | YES |
| Worker pool isolation | YES |

---

## Conclusion

**The frame should NOT be streamlined by moving services to shards.**

The current architecture follows the Voltron philosophy correctly:
- Frame provides infrastructure, global state, and orchestration
- Shards provide features, business logic, and UI
- Communication happens through events, not imports
- Services are appropriately scoped

The path forward is **completion, not extraction**:
1. Finish stub implementations in existing services
2. Create missing shard manifests
3. Implement worker handlers in shards that own processing logic

The only "streamlining" that might be considered is removing unused exports from `__init__.py`, but that's cosmetic. The core architecture is sound.

---

## Appendix: Service Availability Matrix

| Service | Shards Using It | Required? |
|---------|-----------------|-----------|
| database | 8 of 10 | Required |
| events | 10 of 10 | Required |
| vectors | 4 of 10 | Required for those 4 |
| workers | 4 of 10 | Required for async |
| llm | 3 of 10 | Optional |
| documents | 5 of 10 | Optional |
| entities | 4 of 10 | Optional |
| config | 1 of 10 | Required by dashboard |

---

*Report generated by analyzing all source files in packages/arkham-frame and packages/arkham-shard-*, along with documentation in docs/*.*
