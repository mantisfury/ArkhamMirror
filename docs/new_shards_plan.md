# New Shards Development Plan

> Master plan for building production-ready shards for the SHATTERED architecture
> Based on `shard_manifest_schema_prod.md` and reference implementation `arkham-shard-ach`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current State](#2-current-state)
3. [Navigation Slot Allocation](#3-navigation-slot-allocation)
4. [Shard Development Checklist](#4-shard-development-checklist)
5. [Production Compliance Requirements](#5-production-compliance-requirements)
6. [Shard Templates](#6-shard-templates)
7. [New Shard Candidates](#7-new-shard-candidates)
8. [Bundle Composition](#8-bundle-composition)
9. [Implementation Guidelines](#9-implementation-guidelines)
10. [Quality Gates](#10-quality-gates)

---

## 1. Overview

### 1.1 Architecture Pattern

All shards follow the intelligence analysis pipeline:

```
INGEST → EXTRACT → ORGANIZE → ANALYZE → ACT
  ↓        ↓         ↓          ↓       ↓
 Data     Parse    Search    Analysis  Export
 Shards   Shards   Shards    Shards   Shards
```

### 1.2 Core Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards MUST NOT import other shards directly
3. **Schema Isolation**: Each shard gets `arkham_{shard_name}` database schema
4. **Event-Driven Communication**: Shards communicate via EventBus only
5. **Self-Contained**: Each shard has manifest, API, workers, and optionally UI

### 1.3 Production Standards

All new shards MUST comply with `shard_manifest_schema_prod.md`:
- Valid manifest structure
- Correct navigation category and order range
- Event naming: `{shard}.{entity}.{action}`
- Standard capability names from registry
- Empty `dependencies.shards: []`

---

## 2. Current State

### 2.1 Implemented Shards (20)

| Shard | Category | Order | Status |
|-------|----------|-------|--------|
| dashboard | System | 0 | Production |
| projects | System | 2 | Production |
| settings | System | 5 | Production |
| ingest | Data | 10 | Production |
| ocr | Data | 11 | Production |
| parse | Data | 12 | Production |
| documents | Data | 13 | Production |
| entities | Data | 14 | Production |
| search | Search | 20 | Production |
| embed | Search | 25 | Production |
| ach | Analysis | 30 | Production (Reference) |
| claims | Analysis | 31 | Production |
| provenance | Analysis | 32 | Production |
| contradictions | Analysis | 35 | Production |
| anomalies | Analysis | 37 | Production |
| graph | Visualize | 40 | Production |
| timeline | Visualize | 45 | Production |
| export | Export | 50 | Production |
| reports | Export | 55 | Production |
| packets | Export | 58 | Production |

### 2.2 Available Slots

| Category | Range | Used Slots | Available Slots |
|----------|-------|------------|-----------------|
| System | 0-9 | 0, 2, 5 | 1, 3-4, 6-9 (7 slots) |
| Data | 10-19 | 10, 11, 12, 13, 14 | 15-19 (5 slots) |
| Search | 20-29 | 20, 25 | 21-24, 26-29 (8 slots) |
| Analysis | 30-39 | 30, 31, 32, 35, 37 | 33-34, 36, 38-39 (5 slots) |
| Visualize | 40-49 | 40, 45 | 41-44, 46-49 (8 slots) |
| Export | 50-59 | 50, 55, 58 | 51-54, 56-57, 59 (7 slots) |

**Total available slots: 40**

---

## 3. Navigation Slot Allocation

### 3.1 Slot Assignment Rules

1. **Primary shards** get base slots (x0, x5): dashboard=0, search=20, ach=30, graph=40, export=50
2. **Supporting shards** fill in between
3. **Reserve gaps** for future expansion (don't use all consecutive slots)
4. **Sub-routes** don't consume slots (belong to parent shard)

### 3.2 Recommended Slot Plan

#### System Category (0-9)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 0 | dashboard | System monitoring (EXISTS) | - |
| 2 | projects | Project management UI (EXISTS) | - |
| 5 | settings | User preferences, configuration (EXISTS) | - |
| 1 | notifications | Alert center, notification history | MEDIUM |
| 3 | admin | Admin tools, user management | LOW |
| 8 | audit | Audit log viewer | LOW |

#### Data Category (10-19)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 10 | ingest | File intake (EXISTS) | - |
| 11 | ocr | OCR processing (EXISTS) | - |
| 12 | parse | NER/parsing (EXISTS) | - |
| 13 | documents | Document browser/viewer (EXISTS) | - |
| 14 | entities | Entity browser/editor (EXISTS) | - |
| 15 | sources | Source/reference management | MEDIUM |
| 16 | archive | Archive management, cold storage | LOW |
| 18 | import | Bulk import tools | LOW |

#### Search Category (20-29)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 20 | search | Semantic/keyword search (EXISTS) | - |
| 21 | filters | Advanced filter builder | MEDIUM |
| 22 | saved-searches | Saved search management | MEDIUM |
| 25 | embed | Embeddings (EXISTS) | - |
| 26 | similarity | Document similarity explorer | LOW |
| 28 | facets | Faceted navigation builder | LOW |

#### Analysis Category (30-39)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 30 | ach | ACH analysis (EXISTS) | - |
| 31 | claims | Claim extraction and tracking (EXISTS) | - |
| 32 | provenance | Evidence chain tracking (EXISTS) | - |
| 33 | credibility | Source credibility scoring | MEDIUM |
| 35 | contradictions | Contradiction detection (EXISTS) | - |
| 36 | patterns | Pattern detection across docs | MEDIUM |
| 37 | anomalies | Anomaly detection (EXISTS) | - |
| 38 | sentiment | Sentiment/tone analysis | LOW |
| 39 | summary | Auto-summarization | MEDIUM |

#### Visualize Category (40-49)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 40 | graph | Entity graph (EXISTS) | - |
| 41 | map | Geographic visualization | MEDIUM |
| 42 | network | Network analysis visualization | MEDIUM |
| 45 | timeline | Timeline (EXISTS) | - |
| 46 | calendar | Calendar view of events | LOW |
| 47 | charts | Statistical charts/dashboards | MEDIUM |
| 48 | compare | Side-by-side document comparison | MEDIUM |

#### Export Category (50-59)
| Order | Shard | Purpose | Priority |
|-------|-------|---------|----------|
| 50 | export | General export tools (EXISTS) | - |
| 55 | reports | Report generation (EXISTS) | - |
| 58 | packets | Evidence packet bundling (EXISTS) | - |
| 51 | letters | Letter/document generation | MEDIUM |
| 52 | templates | Template management UI | MEDIUM |
| 53 | print | Print-optimized views | LOW |
| 56 | api-export | API/webhook export | LOW |

---

## 4. Shard Development Checklist

### 4.1 Pre-Development Checklist

- [ ] Review `shard_manifest_schema_prod.md`
- [ ] Review reference implementation `arkham-shard-ach`
- [ ] Check slot availability in target category
- [ ] Verify no route collision with existing shards
- [ ] Define Frame service dependencies (required vs optional)
- [ ] Design event contracts (publishes/subscribes)
- [ ] Determine if custom UI needed or generic list sufficient

### 4.2 Package Structure Checklist

```
packages/arkham-shard-{name}/
├── [ ] pyproject.toml          # With entry point
├── [ ] shard.yaml              # Production-compliant manifest
├── [ ] README.md               # Documentation
├── [ ] production.md           # Compliance report
└── arkham_shard_{name}/
    ├── [ ] __init__.py         # Exports {Name}Shard
    ├── [ ] shard.py            # Shard implementation
    ├── [ ] api.py              # FastAPI routes
    ├── [ ] models.py           # Pydantic models (if needed)
    └── [ ] workers/            # Worker classes (if needed)
        └── __init__.py
```

### 4.3 Implementation Checklist

- [ ] Shard class extends `ArkhamShard`
- [ ] Class has `name`, `version`, `description` attributes
- [ ] `initialize()` calls `super().__init__()` first
- [ ] `initialize()` stores `self.frame = frame`
- [ ] `initialize()` registers workers if any
- [ ] `shutdown()` unregisters workers and cleans up
- [ ] `get_routes()` returns FastAPI router
- [ ] Service availability checked before use
- [ ] Events follow `{shard}.{entity}.{action}` format
- [ ] Database schema uses `arkham_{shard_name}` prefix

### 4.4 Manifest Checklist

- [ ] `name` matches `^[a-z][a-z0-9-]*$`
- [ ] `version` is valid semver
- [ ] `entry_point` format: `arkham_shard_{name}:{Name}Shard`
- [ ] `api_prefix` starts with `/api/`
- [ ] `requires_frame` set to `">=0.1.0"`
- [ ] `navigation.category` is valid
- [ ] `navigation.order` within category range
- [ ] `navigation.route` unique, starts with `/`
- [ ] `dependencies.shards` is empty `[]`
- [ ] `events.publishes` follow naming convention
- [ ] `events.subscribes` reference valid events
- [ ] `capabilities` use standard names
- [ ] `state.strategy` is valid (url|local|session|none)

### 4.5 Testing Checklist

- [ ] Unit tests for business logic
- [ ] API endpoint tests
- [ ] Manifest validation passes
- [ ] Shard loads successfully with Frame
- [ ] Events publish correctly
- [ ] Event subscriptions receive events
- [ ] Optional service degradation works
- [ ] Worker registration/unregistration works (if applicable)

### 4.6 Documentation Checklist

- [ ] README.md with overview and usage
- [ ] API endpoint documentation
- [ ] Event contract documentation
- [ ] production.md compliance report
- [ ] Dependencies clearly documented

---

## 5. Production Compliance Requirements

### 5.1 Manifest Field Requirements

| Field | Requirement | Example |
|-------|-------------|---------|
| `name` | `^[a-z][a-z0-9-]*$` | `claims` |
| `version` | Valid semver | `"0.1.0"` |
| `entry_point` | `module:Class` | `arkham_shard_claims:ClaimsShard` |
| `api_prefix` | Starts with `/api/` | `/api/claims` |
| `requires_frame` | Semver constraint | `">=0.1.0"` |
| `navigation.category` | Valid category | `Analysis` |
| `navigation.order` | Within category range | `31` |
| `navigation.route` | Unique, starts with `/` | `/claims` |
| `dependencies.shards` | MUST be `[]` | `[]` |

### 5.2 Event Naming Convention

```
{shard}.{entity}.{action}

shard:  shard name (e.g., claims)
entity: object type, singular (e.g., claim)
action: past tense verb (e.g., created, updated, deleted)

Examples:
- claims.claim.created
- claims.claim.verified
- claims.extraction.completed
- claims.link.established
```

### 5.3 Standard Actions

| Action | Meaning |
|--------|---------|
| `created` | New entity created |
| `updated` | Entity modified |
| `deleted` | Entity removed |
| `started` | Process began |
| `completed` | Process finished |
| `failed` | Process errored |
| `linked` | Relationship established |
| `verified` | Validation passed |
| `detected` | Discovery made |

### 5.4 Capability Registry

#### Data Capabilities
- `document_storage`, `document_processing`
- `entity_extraction`, `entity_management`
- `embedding_generation`, `similarity_search`

#### Analysis Capabilities
- `hypothesis_management`, `evidence_management`
- `contradiction_detection`, `anomaly_detection`
- `timeline_construction`, `graph_visualization`
- `claim_extraction`, `credibility_scoring`

#### Processing Capabilities
- `ocr_processing`, `audio_transcription`
- `pdf_parsing`, `image_analysis`
- `llm_enrichment`, `background_processing`

#### Export Capabilities
- `report_generation`, `data_export`
- `batch_export`, `template_rendering`

---

## 6. Shard Templates

### 6.1 Minimal Shard Template

```yaml
# shard.yaml
# {Name} Shard - Production Manifest v1.0
# Compliant with shard_manifest_schema_prod.md

name: {name}
version: "0.1.0"
description: {One-line description}
entry_point: arkham_shard_{name}:{Name}Shard
api_prefix: /api/{name}
requires_frame: ">=0.1.0"

navigation:
  category: {Category}           # System|Data|Search|Analysis|Visualize|Export
  order: {order}                 # Within category range
  icon: {LucideIcon}            # PascalCase Lucide icon name
  label: {Display Name}
  route: /{name}

dependencies:
  services:
    - database
    - events
  optional: []
  shards: []                    # MUST be empty

capabilities:
  - {capability_1}
  - {capability_2}

events:
  publishes:
    - {name}.{entity}.created
    - {name}.{entity}.updated
  subscribes: []

state:
  strategy: url
  url_params: []
  local_keys: []

ui:
  has_custom_ui: false
```

### 6.2 Shard Class Template

```python
# arkham_shard_{name}/shard.py
"""
{Name} Shard - {Description}
"""

from arkham_frame import ArkhamShard


class {Name}Shard(ArkhamShard):
    """
    {Description}

    Events Published:
        - {name}.{entity}.created
        - {name}.{entity}.updated

    Events Subscribed:
        - (none)
    """

    name = "{name}"
    version = "0.1.0"
    description = "{Description}"

    async def initialize(self, frame) -> None:
        """Initialize the shard with Frame reference."""
        super().__init__()
        self.frame = frame

        # Get required services
        self.db = frame.get_service("database")
        self.events = frame.get_service("events")

        if not self.db:
            raise RuntimeError(f"{self.name}: Database service required")

        # Get optional services
        self.llm = frame.get_service("llm")
        self.llm_available = self.llm and self.llm.is_available()

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        if self.events:
            # self.events.subscribe("other.event.completed", self._on_event)
            pass

        # Register workers if any
        workers = frame.get_service("workers")
        if workers:
            # from .workers import MyWorker
            # workers.register_worker(MyWorker)
            pass

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        # Unsubscribe from events
        if self.events:
            # self.events.unsubscribe("other.event.completed", self._on_event)
            pass

        # Unregister workers
        if self._frame:
            workers = self._frame.get_service("workers")
            if workers:
                # from .workers import MyWorker
                # workers.unregister_worker(MyWorker)
                pass

    def get_routes(self):
        """Return FastAPI router with shard endpoints."""
        from .api import router
        return router

    async def _create_schema(self) -> None:
        """Create database schema for this shard."""
        # Schema creation SQL
        pass

    # Public methods for other shards (via Frame)
    async def get_items(self, limit: int = 50) -> list:
        """Get items from this shard."""
        # Implementation
        return []
```

### 6.3 API Router Template

```python
# arkham_shard_{name}/api.py
"""
{Name} Shard API Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/{name}", tags=["{name}"])


# === Models ===

class {Name}Item(BaseModel):
    id: str
    # Add fields


class {Name}Create(BaseModel):
    # Add create fields
    pass


class {Name}ListResponse(BaseModel):
    items: List[{Name}Item]
    total: int
    page: int
    page_size: int


# === Endpoints ===

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "shard": "{name}"}


@router.get("/items", response_model={Name}ListResponse)
async def list_items(
    page: int = 1,
    page_size: int = 20,
    sort: str = "created_at",
    order: str = "desc",
    q: Optional[str] = None,
):
    """List all items with pagination."""
    # Implementation
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/items/{item_id}", response_model={Name}Item)
async def get_item(item_id: str):
    """Get a single item by ID."""
    # Implementation
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("/items", response_model={Name}Item)
async def create_item(item: {Name}Create):
    """Create a new item."""
    # Implementation
    pass


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete an item."""
    # Implementation
    return {"deleted": True}


@router.get("/count")
async def get_count():
    """Get total item count (for badge)."""
    return {"count": 0}
```

### 6.4 pyproject.toml Template

```toml
[project]
name = "arkham-shard-{name}"
version = "0.1.0"
description = "{Description}"
readme = "README.md"
requires-python = ">=3.10"

dependencies = [
    "arkham-frame>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]

[project.entry-points."arkham.shards"]
{name} = "arkham_shard_{name}:{Name}Shard"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 7. New Shard Candidates

### 7.1 Implemented Shards (Previously High Priority)

The following shards have been implemented and are production-ready:

#### claims (Analysis, order 31) - IMPLEMENTED
**Purpose**: Extract and track factual claims from documents
**Status**: Production-ready with full API, models, and tests

#### provenance (Analysis, order 32) - IMPLEMENTED
**Purpose**: Track evidence chains and data lineage
**Status**: Production-ready with full API, models, and tests

#### documents (Data, order 13) - IMPLEMENTED
**Purpose**: Document browser with viewer and metadata editor
**Status**: Production-ready with full API, models, and tests

#### entities (Data, order 14) - IMPLEMENTED
**Purpose**: Entity browser with merge/link/edit capabilities
**Status**: Production-ready with full API, models, and tests

#### reports (Export, order 55) - IMPLEMENTED
**Purpose**: Generate formatted reports from analysis
**Status**: Production-ready with full API, models, and tests

#### packets (Export, order 58) - IMPLEMENTED
**Purpose**: Bundle evidence into shareable packets
**Status**: Production-ready with full API, models, and tests

#### settings (System, order 5) - IMPLEMENTED
**Purpose**: User preferences and system configuration
**Status**: Production-ready with full API, models, and tests

#### projects (System, order 2) - IMPLEMENTED
**Purpose**: Project management interface
**Status**: Production-ready with full API, models, and tests

#### export (Export, order 50) - IMPLEMENTED
**Purpose**: Data export in various formats (JSON, CSV, PDF, DOCX)
**Status**: Production-ready with full API, models, and tests

### 7.2 Medium Priority (Enhanced Functionality)

#### notifications (System, order 1)
**Purpose**: Notification center and alert management
**Dependencies**: database, events, notifications (Frame service)
**Events**: `notifications.alert.dismissed`
**Capabilities**: `alert_management`, `notification_display`

#### sources (Data, order 15)
**Purpose**: Source and reference management
**Dependencies**: database, events
**Events**:
- `sources.source.added`
- `sources.credibility.rated`
**Capabilities**: `source_management`, `reference_tracking`

#### credibility (Analysis, order 33)
**Purpose**: Source credibility assessment
**Dependencies**: database, events, llm (optional)
**Events**:
- `credibility.assessment.completed`
- `credibility.score.updated`
**Capabilities**: `credibility_scoring`, `source_assessment`

#### summary (Analysis, order 39)
**Purpose**: Auto-summarization of documents and collections
**Dependencies**: database, events, llm
**Events**:
- `summary.summary.generated`
**Capabilities**: `summarization`, `llm_enrichment`

#### charts (Visualize, order 47)
**Purpose**: Statistical charts and dashboards
**Dependencies**: database, events
**Events**: `charts.dashboard.updated`
**Capabilities**: `chart_generation`, `dashboard_display`

#### compare (Visualize, order 48)
**Purpose**: Side-by-side document comparison
**Dependencies**: database, events, vectors
**Events**: `compare.comparison.completed`
**Capabilities**: `document_comparison`, `diff_visualization`

#### letters (Export, order 52)
**Purpose**: Generate formal letters (FOIA, complaints, etc.)
**Dependencies**: database, events, templates, export
**Events**:
- `letters.letter.generated`
**Capabilities**: `letter_generation`, `template_rendering`

#### templates-ui (Export, order 54)
**Purpose**: Template management interface
**Dependencies**: database, events, templates (Frame service)
**Events**: `templates.template.updated`
**Capabilities**: `template_management`

### 7.3 Lower Priority (Specialized)

#### audit (System, order 8)
**Purpose**: View audit logs and system history

#### archive (Data, order 16)
**Purpose**: Cold storage and archive management

#### filters (Search, order 21)
**Purpose**: Advanced filter builder

#### saved-searches (Search, order 22)
**Purpose**: Save and manage search queries

#### patterns (Analysis, order 36)
**Purpose**: Cross-document pattern detection

#### sentiment (Analysis, order 38)
**Purpose**: Sentiment and tone analysis

#### map (Visualize, order 41)
**Purpose**: Geographic visualization

#### network (Visualize, order 42)
**Purpose**: Network analysis visualization

#### calendar (Visualize, order 46)
**Purpose**: Calendar view of temporal events

---

## 8. Bundle Composition

### 8.1 Bundle Concept

Bundles are **curated shard combinations** for specific use cases. They are NOT runtime configurations—they are documentation for "which shards to install."

### 8.2 Bundle Structure

```yaml
# bundles/journalism-investigative.yaml
name: journalism-investigative
description: Investigative journalism toolkit
version: "1.0.0"

# Required shards
shards:
  core:
    - dashboard
    - ingest
    - parse
    - search
  analysis:
    - claims
    - contradictions
    - credibility
    - timeline
  export:
    - reports
    - packets

# Optional enhancements
optional:
  - graph
  - anomalies
  - provenance

# Shell configuration
shell:
  default_route: /search
  domain_banner: "INVESTIGATIVE JOURNALISM MODE"
  visible_categories:
    - Data
    - Search
    - Analysis
    - Export
```

### 8.3 Example Bundles

#### Journalism Investigative
- **Core**: dashboard, ingest, parse, search, embed
- **Analysis**: claims, contradictions, credibility, timeline, ach
- **Export**: reports, packets
- **Visualize**: graph, timeline

#### Legal Self-Advocacy
- **Core**: dashboard, ingest, parse, search
- **Analysis**: claims, contradictions, timeline, provenance
- **Export**: reports, letters, packets
- **Domain Banner**: "LEGAL RESEARCH - NOT LEGAL ADVICE"

#### Research Academic
- **Core**: dashboard, ingest, parse, search, embed
- **Analysis**: claims, summary, anomalies
- **Export**: reports
- **Visualize**: graph, timeline, charts

#### Healthcare Records
- **Core**: dashboard, ingest, ocr, parse, search
- **Analysis**: timeline, contradictions
- **Export**: reports, packets
- **Domain Banner**: "MEDICAL RECORD ANALYSIS - NOT MEDICAL ADVICE"

---

## 9. Implementation Guidelines

### 9.1 Service Usage Patterns

#### Required Service Check
```python
async def initialize(self, frame):
    super().__init__()
    self.frame = frame

    # Required - fail if unavailable
    self.db = frame.get_service("database")
    if not self.db:
        raise RuntimeError(f"{self.name}: Database service required")
```

#### Optional Service Check
```python
    # Optional - graceful degradation
    self.llm = frame.get_service("llm")
    self.llm_available = self.llm and self.llm.is_available()

    # Use conditional features
    if self.llm_available:
        # Enable LLM-powered features
        pass
```

### 9.2 Event Publishing Pattern

```python
async def create_item(self, data: dict) -> Item:
    """Create item and publish event."""
    item = await self._store_item(data)

    # Publish event
    if self.events:
        await self.events.emit(
            f"{self.name}.item.created",
            {
                "item_id": item.id,
                "item_type": item.type,
                "created_by": "user",
            },
            source=self.name,
        )

    return item
```

### 9.3 Event Subscription Pattern

```python
async def initialize(self, frame):
    # ... setup ...

    if self.events:
        self.events.subscribe("document.processed", self._on_document_processed)
        self.events.subscribe("entity.entity.created", self._on_entity_created)

async def shutdown(self):
    if self.events:
        self.events.unsubscribe("document.processed", self._on_document_processed)
        self.events.unsubscribe("entity.entity.created", self._on_entity_created)

async def _on_document_processed(self, event: dict):
    """Handle document processed event."""
    doc_id = event["payload"]["document_id"]
    # Process the document
```

### 9.4 Database Schema Pattern

```python
async def _create_schema(self) -> None:
    """Create database schema for this shard."""
    if not self.db:
        return

    await self.db.execute("""
        CREATE SCHEMA IF NOT EXISTS arkham_{name};

        CREATE TABLE IF NOT EXISTS arkham_{name}.items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT NOT NULL,
            content TEXT,
            status TEXT DEFAULT 'active',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_items_status
        ON arkham_{name}.items(status);

        CREATE INDEX IF NOT EXISTS idx_items_created
        ON arkham_{name}.items(created_at DESC);
    """)
```

### 9.5 Worker Registration Pattern

```python
# In shard.py
async def initialize(self, frame):
    # ... other setup ...

    workers = frame.get_service("workers")
    if workers:
        from .workers.processor import ProcessorWorker
        workers.register_worker(ProcessorWorker)

async def shutdown(self):
    if self._frame:
        workers = self._frame.get_service("workers")
        if workers:
            from .workers.processor import ProcessorWorker
            workers.unregister_worker(ProcessorWorker)

# In workers/processor.py
from arkham_frame.workers import BaseWorker

class ProcessorWorker(BaseWorker):
    pool = "cpu-light"  # Which pool this worker belongs to

    async def process(self, job) -> dict:
        """Process a job from the queue."""
        # Implementation
        return {"result": "success"}
```

---

## 10. Quality Gates

### 10.1 Pre-Commit Checklist

Before committing a new shard:

- [ ] All files created per package structure
- [ ] `pyproject.toml` has correct entry point
- [ ] `shard.yaml` passes manifest validation
- [ ] Shard class has required attributes
- [ ] `initialize()` and `shutdown()` properly implemented
- [ ] API routes work and return correct formats
- [ ] No imports from other shards
- [ ] Events follow naming convention
- [ ] README.md documents the shard

### 10.2 Pre-PR Checklist

Before creating a pull request:

- [ ] Unit tests pass
- [ ] Integration test: shard loads with Frame
- [ ] Event publication verified
- [ ] Event subscription verified (if any)
- [ ] Optional service degradation tested
- [ ] production.md compliance report created
- [ ] No route collisions with existing shards
- [ ] Documentation complete

### 10.3 Production Readiness Checklist

Before marking a shard as production-ready:

- [ ] All quality gates pass
- [ ] Tested with target bundle combination
- [ ] Error handling covers all failure modes
- [ ] Logging provides useful debugging info
- [ ] Performance acceptable under expected load
- [ ] Database migrations documented
- [ ] Rollback procedure documented

---

## Appendix A: Reference Files

| Document | Purpose |
|----------|---------|
| `docs/shard_manifest_schema_prod.md` | Production schema specification |
| `docs/frame_spec.md` | Frame service specifications |
| `packages/arkham-shard-ach/` | Reference implementation |
| `CLAUDE.md` | Project-wide guidelines |

---

## Appendix B: Quick Start

### Creating a New Shard (5-Step Process)

1. **Copy template**:
   ```bash
   cp -r packages/arkham-shard-template packages/arkham-shard-{name}
   ```

2. **Update manifest** (`shard.yaml`):
   - Set name, description, category, order
   - Define events and capabilities
   - Configure UI options

3. **Implement shard class** (`shard.py`):
   - Add initialization logic
   - Register workers if needed
   - Implement public methods

4. **Create API routes** (`api.py`):
   - Define endpoints
   - Implement handlers
   - Add Pydantic models

5. **Install and test**:
   ```bash
   cd packages/arkham-shard-{name}
   pip install -e .
   # Frame auto-discovers on next restart
   ```

---

*New Shards Development Plan - Version 2.0*
*Updated: 2025-12-25*
*Compliant with: shard_manifest_schema_prod.md v1.0*

**Changelog v2.0:**
- Updated to reflect 20 implemented shards (was 11)
- All high-priority shards now implemented: claims, provenance, documents, entities, reports, packets, settings, projects, export
- Updated slot allocation tables with current assignments
- Corrected navigation order values to comply with category ranges
