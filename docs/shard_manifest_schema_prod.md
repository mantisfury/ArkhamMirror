# Shard Manifest Schema - Production v1.0

> Production-ready schema for `shard.yaml` files aligned with ArkhamFrame v0.1.0

---

## Overview

This document defines the **production requirements** for shard manifests to be compatible with the current ArkhamFrame architecture. It extends and supersedes `SHARD_MANIFEST_SCHEMA_v5.md` with Frame-aligned specifications.

**Key Changes from v5:**
- Aligned service dependencies with actual Frame services (16 services)
- Worker pool names match Frame's ResourceService definitions
- Event naming conventions enforced
- Output service integration patterns defined
- Capability declarations mapped to Frame features

---

## Quick Reference

```yaml
# === REQUIRED ===
name: string              # ^[a-z][a-z0-9-]*$ (starts with letter, lowercase + hyphens)
version: string           # semver (MAJOR.MINOR.PATCH)
description: string       # 1-2 sentences
entry_point: string       # module.path:ClassName
api_prefix: string        # /api/{name}
requires_frame: string    # ">=0.1.0"

navigation:
  category: string        # System|Data|Search|Analysis|Visualize|Export
  order: integer          # 0-99 (see Category Order Ranges)
  icon: string            # Lucide icon (PascalCase)
  label: string           # Display name
  route: string           # /{name} (must be unique)
  badge_endpoint: string  # optional: /api/{name}/count
  badge_type: string      # optional: count|dot
  sub_routes: []          # optional

# === OPTIONAL ===
dependencies:
  services: []            # Frame service names (see Service Dependencies)
  optional: []            # Services that enhance but aren't required
  shards: []              # MUST be empty (no shard dependencies)

capabilities: []          # Feature declarations (see Capability Registry)

events:
  publishes: []           # {shard}.{entity}.{action} format
  subscribes: []          # Pattern matching with wildcards

state:
  strategy: string        # url|local|session|none
  url_params: []          # Non-filter URL params
  local_keys: []          # localStorage keys (no shard prefix)

ui:                       # See UI Configuration (unchanged from v5)
  has_custom_ui: boolean
  # ...
```

---

## Service Dependencies

### Available Frame Services

Shards can declare dependencies on the following Frame services:

| Service Name | Attribute | Description | Common Use Case |
|--------------|-----------|-------------|-----------------|
| `config` | `frame.config` | Configuration access | Reading settings |
| `resources` | `frame.resources` | Hardware tier, pools | GPU/CPU allocation |
| `storage` | `frame.storage` | File/blob storage | Document files |
| `database` | `frame.db` | PostgreSQL access | Data persistence |
| `vectors` | `frame.vectors` | Qdrant vector store | Semantic search |
| `llm` | `frame.llm` | LM Studio integration | Text generation |
| `chunks` | `frame.chunks` | Text chunking | Document processing |
| `events` | `frame.events` | Event pub/sub | Shard communication |
| `workers` | `frame.workers` | Job queues | Background tasks |
| `documents` | `frame.documents` | Document service | Document CRUD |
| `entities` | `frame.entities` | Entity service | Entity extraction |
| `projects` | `frame.projects` | Project service | Project management |
| `export` | (via API) | Export service | Data export |
| `templates` | (via API) | Template service | Report generation |
| `notifications` | (via API) | Notification service | Alerts |
| `scheduler` | (via API) | Scheduler service | Recurring tasks |

### Dependency Declaration Rules

```yaml
dependencies:
  services:
    # Core services most shards need
    - database      # For data persistence
    - events        # For event communication

  optional:
    # Services that enhance functionality
    - llm           # For AI features
    - vectors       # For similarity search
    - workers       # For background processing

  shards: []        # ALWAYS empty - no shard imports allowed
```

### Service Availability Check

Shards should check service availability at runtime:

```python
async def initialize(self, frame):
    self.frame = frame

    # Required service - fail if unavailable
    if not self.frame.db:
        raise RuntimeError("Database service required")

    # Optional service - graceful degradation
    self.llm_available = self.frame.llm and self.frame.llm.is_available()
```

---

## Worker Pool Declarations

### Available Worker Pools

When using the WorkerService, reference only these pool names:

**IO Pools:**
| Pool | Max Workers | Use Case |
|------|-------------|----------|
| `io-file` | 20 | File read/write operations |
| `io-db` | 10 | Database-heavy operations |

**CPU Pools:**
| Pool | Max Workers | Use Case |
|------|-------------|----------|
| `cpu-light` | 50 | Quick CPU tasks |
| `cpu-heavy` | 6 | Intensive CPU tasks |
| `cpu-ner` | 8 | NER processing |
| `cpu-extract` | 4 | Text extraction |
| `cpu-image` | 4 | Image processing |
| `cpu-archive` | 2 | Archive handling |

**GPU Pools:**
| Pool | Max Workers | VRAM | Use Case |
|------|-------------|------|----------|
| `gpu-paddle` | 1 | 2GB | PaddleOCR |
| `gpu-qwen` | 1 | 8GB | Qwen vision |
| `gpu-whisper` | 1 | 4GB | Audio transcription |
| `gpu-embed` | 1 | 2GB | Embeddings |

**LLM Pools:**
| Pool | Max Workers | Use Case |
|------|-------------|----------|
| `llm-enrich` | 4 | Document enrichment |
| `llm-analysis` | 2 | Deep analysis |

### Pool Usage in Capabilities

```yaml
capabilities:
  - background_processing  # Indicates use of workers
  - gpu_acceleration       # Indicates GPU pool usage
```

### Pool Selection Pattern

Use `frame.resources.get_best_pool()` for tier-aware pool selection:

```python
# Request preferred pool, get fallback if unavailable
pool = self.frame.resources.get_best_pool("gpu-paddle")
if pool:
    await self.frame.workers.enqueue(pool, job_id, payload)
```

---

## Event Conventions

### Event Naming Format

```
{source}.{entity}.{action}

source: shard name or "frame" or "worker"
entity: object type (singular)
action: past tense verb
```

### Standard Actions

| Action | Meaning |
|--------|---------|
| `created` | New entity created |
| `updated` | Entity modified |
| `deleted` | Entity removed |
| `started` | Process began |
| `completed` | Process finished |
| `failed` | Process errored |

### Event Declaration

```yaml
events:
  publishes:
    - ach.matrix.created
    - ach.matrix.updated
    - ach.hypothesis.added
    - ach.evidence.linked
    - ach.analysis.completed

  subscribes:
    - document.processed    # Exact match
    - llm.*                 # Wildcard - all llm events
    - "*.completed"         # All completion events
```

### Reserved Event Prefixes

| Prefix | Reserved For |
|--------|--------------|
| `frame.*` | Frame internal events |
| `worker.*` | Worker service events |
| `scheduler.*` | Scheduler service events |
| `notification.*` | Notification service events |

---

## Capability Registry

### Standard Capabilities

Declare capabilities that describe what the shard provides:

**Data Capabilities:**
```yaml
capabilities:
  - document_storage      # Stores documents
  - entity_extraction     # Extracts entities from text
  - embedding_generation  # Creates vector embeddings
  - similarity_search     # Semantic search functionality
```

**Analysis Capabilities:**
```yaml
capabilities:
  - hypothesis_management  # ACH-style hypothesis tracking
  - evidence_management    # Evidence linking
  - contradiction_detection
  - anomaly_detection
  - timeline_construction
  - graph_visualization
```

**Processing Capabilities:**
```yaml
capabilities:
  - ocr_processing        # Optical character recognition
  - audio_transcription   # Audio to text
  - pdf_parsing           # PDF document processing
  - image_analysis        # Image understanding
  - llm_enrichment        # LLM-based enrichment
```

**Export Capabilities:**
```yaml
capabilities:
  - report_generation     # Creates reports
  - data_export           # Exports to various formats
  - batch_export          # Bulk export operations
```

### Capability Naming Rules

- Lowercase with underscores
- Descriptive of function, not implementation
- No version numbers
- No shard-specific prefixes

---

## Output Service Integration

### Export Service Integration

Shards can use the Export Service for data export:

```python
# In shard code
from arkham_frame.services import ExportService, ExportFormat, ExportOptions

async def export_matrix(self, matrix_id: str, format: str):
    export_service = ExportService()

    data = await self.get_matrix_data(matrix_id)

    options = ExportOptions(
        format=ExportFormat(format),
        title=f"ACH Matrix {matrix_id}",
        include_metadata=True
    )

    result = export_service.export(data, options=options)
    return result
```

### Template Service Integration

For report generation with templates:

```python
from arkham_frame.services import TemplateService

async def generate_report(self, matrix_id: str):
    template_service = TemplateService()

    # Register custom template
    template_service.register(
        "ach_report",
        self.REPORT_TEMPLATE,
        category="ach"
    )

    # Render
    result = template_service.render(
        "ach_report",
        matrix=await self.get_matrix(matrix_id),
        hypotheses=await self.get_hypotheses(matrix_id)
    )

    return result.content
```

### Notification Integration

For alerts and notifications:

```yaml
# In shard.yaml
events:
  publishes:
    - ach.analysis.completed  # Notification service can subscribe
```

```python
# In shard code - emit event for notification
await self.frame.events.emit(
    "ach.analysis.completed",
    {
        "matrix_id": matrix_id,
        "result": "significant_finding",
        "message": "Analysis complete with 3 key findings"
    },
    source=self.name
)
```

### Scheduler Integration

For recurring tasks:

```python
# In shard initialize
from arkham_frame.services import SchedulerService

async def initialize(self, frame):
    self.frame = frame

    # Register a scheduled job via API or direct service
    # Jobs are registered with the scheduler service
    if hasattr(frame, 'scheduler'):
        frame.scheduler.register_job(
            "ach_cleanup",
            self.cleanup_old_matrices
        )
        frame.scheduler.schedule_interval(
            "ACH Daily Cleanup",
            "ach_cleanup",
            hours=24
        )
```

---

## State Management

### URL State (Shareable)

For shareable, bookmarkable state:

```yaml
state:
  strategy: url
  url_params:
    - matrixId      # Entity identifier
    - tab           # UI tab
    - view          # Display mode
    # Note: Filter params from list_filters are auto-managed
```

**URL Format:** `/{shard}?matrixId=abc&tab=evidence&view=expanded`

### Local State (Persistent)

For user preferences:

```yaml
state:
  strategy: local
  local_keys:
    - column_widths     # Stored as {shard}_column_widths
    - show_tooltips     # Stored as {shard}_show_tooltips
    - zoom_level
```

### Session State (Temporary)

For unsaved work:

```yaml
state:
  strategy: session
  local_keys:
    - draft_hypothesis
    - unsaved_ratings
```

---

## Category Order Ranges

| Category | Range | Description | Example Shards |
|----------|-------|-------------|----------------|
| System | 0-9 | Infrastructure, monitoring | Dashboard (0), Settings (5) |
| Data | 10-19 | Document management | Ingest (10), Documents (15) |
| Search | 20-29 | Search interfaces | Search (20), Embeddings (25) |
| Analysis | 30-39 | Analytical tools | ACH (30), Contradictions (35) |
| Visualize | 40-49 | Visualization | Graph (40), Timeline (45) |
| Export | 50-59 | Export and reporting | Export (50), Reports (55) |

---

## API Contract Requirements

### List Endpoint (Required for Generic UI)

```
GET /api/{shard}/items?page=1&page_size=20&sort=created_at&order=desc&q=search
```

**Response:**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

**Requirements:**
- MUST support `page` (default: 1, minimum: 1)
- MUST support `page_size` (default: 20, max: 100)
- MUST support `sort` and `order` for sortable columns
- MUST clamp out-of-range values
- MUST NOT return more than `page_size` items

### Badge Endpoint

```
GET /api/{shard}/count
```

**Response:**
```json
{
  "count": 42
}
```

### Bulk Action Endpoint

```
POST /api/{shard}/batch/{action}
Content-Type: application/json

{
  "ids": ["id1", "id2", "id3"]
}
```

**Response:**
```json
{
  "success": true,
  "processed": 3,
  "failed": 0,
  "errors": [],
  "message": "3 items processed"
}
```

---

## Validation Checklist

### Manifest Validation

| Field | Rule | Error |
|-------|------|-------|
| `name` | `^[a-z][a-z0-9-]*$` | Invalid shard name |
| `version` | Valid semver | Invalid version |
| `entry_point` | `module:Class` format | Invalid entry point |
| `api_prefix` | Starts with `/api/` | Invalid API prefix |
| `requires_frame` | Valid semver constraint | Invalid Frame requirement |
| `navigation.route` | Starts with `/`, unique | Route conflict |
| `navigation.category` | Valid category | Invalid category |
| `navigation.order` | 0-99 | Order out of range |
| `dependencies.shards` | Empty list | Shard dependencies forbidden |

### Service Dependency Validation

| Check | Action |
|-------|--------|
| Unknown service name | Warning logged |
| Required service unavailable | Shard fails to load |
| Optional service unavailable | Graceful degradation |

### Event Validation

| Check | Action |
|-------|--------|
| Reserved prefix in publishes | Error |
| Invalid event format | Warning |
| Duplicate event declaration | Warning |

---

## Complete Production Example

```yaml
# arkham-shard-ach/shard.yaml
# Production Manifest v1.0

name: ach
version: 0.1.0
description: Analysis of Competing Hypotheses matrix for intelligence analysis
entry_point: arkham_shard_ach:ACHShard
api_prefix: /api/ach
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 30
  icon: Scale
  label: ACH Analysis
  route: /ach
  badge_endpoint: /api/ach/matrices/count
  badge_type: count
  sub_routes:
    - id: matrices
      label: All Matrices
      route: /ach/matrices
      icon: List
    - id: new
      label: New Analysis
      route: /ach/new
      icon: Plus

dependencies:
  services:
    - database     # Required: stores matrices, hypotheses, evidence
    - events       # Required: publishes analysis events
  optional:
    - llm          # Optional: enables devil's advocate mode
    - vectors      # Optional: enables evidence similarity search
  shards: []       # MUST be empty

capabilities:
  - hypothesis_management
  - evidence_management
  - consistency_scoring
  - matrix_export
  - devils_advocate       # Only if LLM available

events:
  publishes:
    - ach.matrix.created
    - ach.matrix.updated
    - ach.matrix.deleted
    - ach.hypothesis.added
    - ach.hypothesis.removed
    - ach.evidence.added
    - ach.evidence.removed
    - ach.rating.updated
    - ach.analysis.completed
  subscribes:
    - llm.analysis.completed
    - document.processed     # To suggest evidence from new documents

state:
  strategy: url
  url_params:
    - matrixId
    - hypothesisId
    - tab
    - view
  local_keys:
    - matrix_zoom
    - show_tooltips
    - evidence_sort_order

ui:
  has_custom_ui: true
```

---

## Migration from v5

### Service Name Changes

```diff
dependencies:
  services:
-   - db           # Old name
+   - database     # Correct name (alias: db still works)
```

### Capability Alignment

```diff
capabilities:
-   - achmgmt              # Too vague
+   - hypothesis_management
+   - evidence_management
```

### Event Format

```diff
events:
  publishes:
-   - matrix_created       # Wrong format
+   - ach.matrix.created   # Correct: shard.entity.action
```

---

## Related Documents

- [frame_spec.md](frame_spec.md) - Frame service specifications
- [SHARD_MANIFEST_SCHEMA_v5.md](SHARD_MANIFEST_SCHEMA_v5.md) - UI-focused manifest schema
- [voltron_plan.md](voltron_plan.md) - Architecture overview

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-25 | Initial production schema aligned with Frame 0.1.0 |

---

*Shard Manifest Schema - Production v1.0 - 2024-12-25*
