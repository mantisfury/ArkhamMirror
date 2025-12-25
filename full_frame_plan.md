# Full Frame Implementation Plan

> Comprehensive plan to flesh out the ArkhamFrame core infrastructure
> Based on analysis of shards_and_bundles.md and current codebase state

---

## Executive Summary

The ArkhamFrame currently has the correct architectural foundation, but many services are stubs awaiting implementation. Additionally, analysis of the 58 planned shards and 67 bundles reveals several missing capabilities that the Frame must provide.

**This plan covers:**
1. New services required to support planned shards
2. Completing existing stub implementations
3. Moving parse/embed/OCR logic to shards while keeping interfaces in Frame
4. Manifest compliance fixes for existing shards
5. Phased implementation approach

**Key Metrics:**
- 7 new Frame services required
- 5 existing services need full implementation
- 4 shards missing manifests (critical)
- 6 shards need manifest updates
- 4 pipeline stages need refactoring

---

## Table of Contents

1. [New Services Required](#1-new-services-required)
2. [Existing Service Implementations](#2-existing-service-implementations)
3. [Pipeline Refactoring](#3-pipeline-refactoring)
4. [Manifest Compliance](#4-manifest-compliance)
5. [Implementation Phases](#5-implementation-phases)
6. [Detailed Specifications](#6-detailed-specifications)

---

## 1. New Services Required

Based on shards_and_bundles.md analysis, the following services must be added to the Frame:

### 1.1 ResourceService (CRITICAL)

**Purpose:** Hardware detection, tier assignment, dynamic scaling

**Justification:** Per RESOURCE_DETECTION.md, the Frame must adapt to available hardware. Currently no detection exists.

**Dependencies:** None (runs at startup before other services)

**Interface:**
```python
class ResourceService:
    """System resource detection and management."""

    # Detection
    async def detect() -> SystemResources
    async def determine_tier() -> str  # minimal|standard|recommended|power

    # GPU Management
    async def gpu_available() -> bool
    async def gpu_can_load(model: str) -> bool
    async def gpu_allocate(model: str) -> bool
    async def gpu_release(model: str) -> None

    # CPU Management
    async def cpu_available_threads() -> int
    async def cpu_acquire(threads: int) -> bool
    async def cpu_release(threads: int) -> None

    # Pool Configuration
    def get_pool_limits() -> Dict[str, PoolConfig]
    def get_disabled_pools() -> List[str]
    def get_fallback_pool(pool: str) -> Optional[str]
```

**Used By:** WorkerService, all GPU-based shards (embed, ocr, parse)

---

### 1.2 StorageService (HIGH)

**Purpose:** File and blob storage for documents, exports, evidence packets

**Justification:** Multiple shards need to store/retrieve files:
- `ingest` - incoming documents
- `export` - generated outputs
- `evidence-packet` - bundled evidence
- `report-generator` - generated reports
- `letter-generator` - generated letters

**Dependencies:** ConfigService (storage path configuration)

**Interface:**
```python
class StorageService:
    """File and blob storage management."""

    # File Operations
    async def store(path: str, content: bytes, metadata: dict = None) -> str  # returns storage_id
    async def retrieve(storage_id: str) -> tuple[bytes, dict]  # content, metadata
    async def delete(storage_id: str) -> bool
    async def exists(storage_id: str) -> bool

    # Temp Files
    async def create_temp(suffix: str = "") -> str  # returns temp path
    async def cleanup_temp(path: str) -> None

    # Directory Operations
    async def list_files(prefix: str) -> List[FileInfo]
    async def get_storage_stats() -> StorageStats

    # Project-scoped Storage
    async def get_project_path(project_id: str) -> str
    async def migrate_to_project(storage_id: str, project_id: str) -> str
```

**Storage Locations:**
- `{DATA_SILO}/documents/` - Ingested documents
- `{DATA_SILO}/exports/` - Generated exports
- `{DATA_SILO}/temp/` - Temporary processing files
- `{DATA_SILO}/models/` - Cached ML models

---

### 1.3 NotificationService (MEDIUM)

**Purpose:** Alert delivery, deadline notifications, webhook dispatch

**Justification:** Required by:
- `alert-manager` shard (35% of bundles use this)
- `workflow-manager` shard (25% of bundles)
- `checklist-generator` shard (30% of bundles)

**Dependencies:** ConfigService, EventBus

**Interface:**
```python
class NotificationService:
    """Notification and alert delivery."""

    # Alert Creation
    async def create_alert(
        title: str,
        message: str,
        severity: str,  # info|warning|critical
        due_at: datetime = None,
        tags: List[str] = None,
        action_url: str = None,
    ) -> Alert

    # Alert Management
    async def list_alerts(status: str = "active") -> List[Alert]
    async def dismiss_alert(alert_id: str) -> bool
    async def snooze_alert(alert_id: str, until: datetime) -> bool

    # Delivery Channels
    async def register_channel(channel: NotificationChannel) -> None
    async def send(alert: Alert, channels: List[str] = None) -> DeliveryResult

    # Webhooks
    async def register_webhook(url: str, events: List[str]) -> WebhookRegistration
    async def trigger_webhook(event: str, payload: dict) -> None
```

**Channels (extensible):**
- In-app (stored in DB, shown in UI)
- Desktop notification (via OS APIs)
- Webhook (HTTP POST to user-defined URL)
- Email (optional, requires SMTP config)

---

### 1.4 SchedulerService (MEDIUM)

**Purpose:** Scheduled tasks, recurring jobs, deadline tracking

**Justification:** Required by:
- `alert-manager` - deadline reminders
- `workflow-manager` - scheduled transitions
- `regulatory-database` - periodic update checks
- `news-archive` - periodic scraping

**Dependencies:** ConfigService, WorkerService, EventBus

**Interface:**
```python
class SchedulerService:
    """Task scheduling and deadline management."""

    # One-time Jobs
    async def schedule_at(
        job_id: str,
        run_at: datetime,
        handler: str,  # shard.handler_name
        payload: dict,
    ) -> ScheduledJob

    # Recurring Jobs
    async def schedule_recurring(
        job_id: str,
        cron: str,  # cron expression
        handler: str,
        payload: dict,
    ) -> ScheduledJob

    # Deadline Tracking
    async def set_deadline(
        item_id: str,
        due_at: datetime,
        reminder_before: timedelta = None,
        escalation_after: timedelta = None,
    ) -> Deadline

    # Management
    async def cancel(job_id: str) -> bool
    async def list_scheduled(shard: str = None) -> List[ScheduledJob]
    async def get_upcoming_deadlines(hours: int = 24) -> List[Deadline]
```

---

### 1.5 ExportService (HIGH)

**Purpose:** Multi-format document export pipeline

**Justification:** 85% of bundles need export capabilities:
- PDF generation
- HTML export
- Markdown export
- JSON/CSV data export
- DOCX generation

**Dependencies:** StorageService, ConfigService

**Interface:**
```python
class ExportService:
    """Multi-format document export."""

    # Export Operations
    async def export(
        content: ExportContent,
        format: str,  # pdf|html|md|json|csv|docx
        options: ExportOptions = None,
    ) -> ExportResult

    # Batch Export
    async def export_batch(
        items: List[ExportContent],
        format: str,
        options: ExportOptions = None,
    ) -> List[ExportResult]

    # Template-based Export
    async def export_from_template(
        template_id: str,
        data: dict,
        format: str,
    ) -> ExportResult

    # Format Registration
    def register_format(format: str, handler: ExportHandler) -> None
    def list_formats() -> List[str]
```

**Export Formats:**
| Format | Library | Use Case |
|--------|---------|----------|
| PDF | WeasyPrint or ReportLab | Reports, evidence packets |
| HTML | Jinja2 | Web-viewable exports |
| Markdown | Built-in | Documentation, notes |
| JSON | Built-in | Data interchange |
| CSV | Built-in | Spreadsheet import |
| DOCX | python-docx | Editable documents |

---

### 1.6 ChunkService (MEDIUM)

**Purpose:** Text chunking for embedding and processing

**Justification:** Currently embedded in EmbedStage, but needed by:
- `embed` shard - vector generation
- `search` shard - search result snippets
- `summary-generator` - document segmentation
- `claim-extractor` - assertion extraction

**Dependencies:** ConfigService

**Interface:**
```python
class ChunkService:
    """Text chunking and segmentation."""

    # Basic Chunking
    async def chunk_text(
        text: str,
        strategy: str = "sentence",  # sentence|paragraph|semantic|fixed
        max_tokens: int = 512,
        overlap: int = 50,
    ) -> List[Chunk]

    # Document Chunking
    async def chunk_document(
        document_id: str,
        strategy: str = "semantic",
        max_tokens: int = 512,
    ) -> List[Chunk]

    # Strategy Registration
    def register_strategy(name: str, chunker: ChunkStrategy) -> None

    # Token Counting
    async def count_tokens(text: str, model: str = "default") -> int
```

**Chunking Strategies:**
| Strategy | Description | Use Case |
|----------|-------------|----------|
| `sentence` | Split on sentence boundaries | General purpose |
| `paragraph` | Split on paragraph breaks | Structured documents |
| `semantic` | Use embeddings to find natural breaks | Long-form content |
| `fixed` | Fixed token count | Consistent size needed |
| `recursive` | Hierarchical splitting | Large documents |

---

### 1.7 TemplateService (MEDIUM)

**Purpose:** Template management for generated content

**Justification:** Required by:
- `letter-generator` - FOIA requests, complaint letters
- `report-generator` - narrative reports
- `checklist-generator` - task list generation
- `evidence-packet` - document bundling

**Dependencies:** StorageService, ConfigService

**Interface:**
```python
class TemplateService:
    """Template management and rendering."""

    # Template CRUD
    async def create_template(
        name: str,
        content: str,
        category: str,
        variables: List[TemplateVariable],
    ) -> Template

    async def get_template(template_id: str) -> Template
    async def list_templates(category: str = None) -> List[Template]
    async def update_template(template_id: str, content: str) -> Template
    async def delete_template(template_id: str) -> bool

    # Rendering
    async def render(
        template_id: str,
        variables: dict,
        format: str = "text",  # text|html|md
    ) -> str

    # Template Discovery
    async def extract_variables(content: str) -> List[TemplateVariable]
    async def validate_variables(template_id: str, variables: dict) -> ValidationResult
```

**Template Categories:**
- `letter` - Correspondence templates
- `report` - Analysis report templates
- `checklist` - Task list templates
- `export` - Export format templates

---

## 2. Existing Service Implementations

The following services exist but are stubs that need full implementation:

### 2.1 DocumentService (Complete Implementation)

**Current State:** All methods return None or empty lists

**Required Implementation:**

```python
class DocumentService:
    """Full document management service."""

    # Document CRUD
    async def create_document(
        filename: str,
        content: bytes,
        project_id: str,
        metadata: dict = None,
    ) -> Document

    async def get_document(doc_id: str) -> Optional[Document]

    async def list_documents(
        project_id: str = None,
        status: str = None,
        offset: int = 0,
        limit: int = 50,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[List[Document], int]  # items, total

    async def update_document(
        doc_id: str,
        metadata: dict = None,
        status: str = None,
    ) -> Document

    async def delete_document(doc_id: str) -> bool

    # Content Access
    async def get_document_text(doc_id: str) -> Optional[str]
    async def get_document_chunks(doc_id: str) -> List[Chunk]
    async def get_document_pages(doc_id: str) -> List[Page]

    # Search (delegates to VectorService)
    async def search(
        query: str,
        project_id: str = None,
        limit: int = 10,
        filters: dict = None,
    ) -> List[SearchResult]

    # Batch Operations
    async def batch_delete(doc_ids: List[str]) -> BatchResult
    async def batch_update_status(doc_ids: List[str], status: str) -> BatchResult
```

**Database Tables Used:**
- `arkham_frame.documents`
- `arkham_frame.chunks`
- `arkham_frame.pages`

---

### 2.2 EntityService (Complete Implementation)

**Current State:** All methods return None or empty lists

**Required Implementation:**

```python
class EntityService:
    """Full entity management service."""

    # Entity CRUD
    async def create_entity(
        text: str,
        entity_type: str,
        document_id: str,
        start_char: int,
        end_char: int,
        confidence: float = 1.0,
        metadata: dict = None,
    ) -> Entity

    async def get_entity(entity_id: str) -> Optional[Entity]

    async def list_entities(
        entity_type: str = None,
        document_id: str = None,
        project_id: str = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[List[Entity], int]

    # Canonical Entity Management
    async def create_canonical(
        name: str,
        entity_type: str,
        aliases: List[str] = None,
        metadata: dict = None,
    ) -> CanonicalEntity

    async def link_to_canonical(
        entity_id: str,
        canonical_id: str,
    ) -> Entity

    async def merge_canonicals(
        source_id: str,
        target_id: str,
    ) -> CanonicalEntity

    # Relationship Management
    async def create_relationship(
        source_id: str,
        target_id: str,
        relationship_type: str,
        strength: float = 1.0,
        evidence_ids: List[str] = None,
    ) -> EntityRelationship

    async def get_relationships(
        entity_id: str,
        relationship_type: str = None,
    ) -> List[EntityRelationship]

    # Search
    async def search_entities(
        query: str,
        entity_type: str = None,
        limit: int = 10,
    ) -> List[Entity]

    # Analytics
    async def get_entity_mentions(
        canonical_id: str,
    ) -> List[EntityMention]

    async def get_co_occurrences(
        entity_id: str,
        limit: int = 10,
    ) -> List[CoOccurrence]
```

**Database Tables Used:**
- `arkham_frame.entities`
- `arkham_frame.canonical_entities`
- `arkham_frame.entity_relationships`

---

### 2.3 ProjectService (Complete Implementation)

**Current State:** Returns placeholder data

**Required Implementation:**

```python
class ProjectService:
    """Full project management service."""

    # Project CRUD
    async def create_project(
        name: str,
        description: str = "",
        settings: dict = None,
    ) -> Project

    async def get_project(project_id: str) -> Optional[Project]

    async def list_projects(
        offset: int = 0,
        limit: int = 50,
        sort: str = "updated_at",
    ) -> tuple[List[Project], int]

    async def update_project(
        project_id: str,
        name: str = None,
        description: str = None,
        settings: dict = None,
    ) -> Project

    async def delete_project(project_id: str, cascade: bool = False) -> bool

    # Project Statistics
    async def get_stats(project_id: str) -> ProjectStats

    # Project Settings
    async def get_setting(project_id: str, key: str) -> Any
    async def set_setting(project_id: str, key: str, value: Any) -> None

    # Project Export/Import
    async def export_project(project_id: str, format: str = "zip") -> bytes
    async def import_project(data: bytes, name: str = None) -> Project
```

---

### 2.4 VectorService (Complete Implementation)

**Current State:** Only has stub search method

**Required Implementation:**

```python
class VectorService:
    """Full Qdrant vector store service."""

    # Collection Management
    async def create_collection(
        name: str,
        vector_size: int = 1024,
        distance: str = "cosine",
    ) -> bool

    async def delete_collection(name: str) -> bool
    async def list_collections() -> List[CollectionInfo]

    # Vector Operations
    async def upsert(
        collection: str,
        vectors: List[Vector],
        payloads: List[dict] = None,
    ) -> int  # count inserted

    async def search(
        collection: str,
        query_vector: List[float],
        limit: int = 10,
        filter: dict = None,
        score_threshold: float = None,
    ) -> List[SearchResult]

    async def delete(
        collection: str,
        ids: List[str] = None,
        filter: dict = None,
    ) -> int  # count deleted

    # Batch Operations
    async def batch_upsert(
        collection: str,
        vectors: List[Vector],
        batch_size: int = 100,
    ) -> int

    # Embedding Generation (delegates to worker)
    async def embed_text(
        text: str,
        model: str = "bge-m3",
    ) -> List[float]

    async def embed_texts(
        texts: List[str],
        model: str = "bge-m3",
    ) -> List[List[float]]
```

---

### 2.5 LLMService (Enhancements)

**Current State:** Basic chat/generate methods exist

**Enhancements Needed:**

```python
class LLMService:
    """Enhanced LLM service with structured output support."""

    # Existing (keep)
    async def chat(messages: List[dict], **kwargs) -> str
    async def generate(prompt: str, **kwargs) -> dict

    # NEW: Structured Output
    async def generate_json(
        prompt: str,
        schema: dict,  # JSON schema for validation
        system_prompt: str = None,
        retries: int = 3,
    ) -> dict

    async def generate_list(
        prompt: str,
        item_schema: dict = None,
        system_prompt: str = None,
    ) -> List[Any]

    # NEW: Prompt Management
    async def register_prompt(
        name: str,
        template: str,
        variables: List[str],
        default_params: dict = None,
    ) -> PromptTemplate

    async def execute_prompt(
        name: str,
        variables: dict,
        **kwargs,
    ) -> str

    # NEW: Function Calling (if model supports)
    async def call_with_functions(
        messages: List[dict],
        functions: List[FunctionDef],
        **kwargs,
    ) -> FunctionCallResult

    # NEW: Streaming
    async def stream_generate(
        prompt: str,
        **kwargs,
    ) -> AsyncIterator[str]

    # NEW: Token Management
    async def count_tokens(text: str) -> int
    async def truncate_to_tokens(text: str, max_tokens: int) -> str
```

---

## 3. Pipeline Refactoring

The goal is to keep pipeline **orchestration in Frame** while moving **processing logic to shards**.

### 3.1 Current State

```
Frame Pipeline (arkham_frame/pipeline/):
├── base.py         # PipelineStage ABC, StageResult
├── coordinator.py  # PipelineCoordinator
├── ingest.py      # IngestStage (stub)
├── ocr.py         # OCRStage (stub)
├── parse.py       # ParseStage (stub)
└── embed.py       # EmbedStage (stub)
```

### 3.2 Target State

```
Frame (keeps):
├── pipeline/
│   ├── base.py           # PipelineStage ABC (unchanged)
│   ├── coordinator.py    # Orchestration + routing
│   └── dispatchers/
│       ├── ingest.py     # Dispatches to ingest shard workers
│       ├── ocr.py        # Dispatches to ocr shard workers
│       ├── parse.py      # Dispatches to parse shard workers
│       └── embed.py      # Dispatches to embed shard workers

Shards (own processing):
├── arkham-shard-ingest/
│   └── workers/
│       ├── file_intake.py    # cpu-archive, io-file
│       └── format_detect.py  # cpu-light
├── arkham-shard-ocr/         # NEW SHARD
│   └── workers/
│       ├── paddle_ocr.py     # gpu-paddle
│       └── qwen_ocr.py       # gpu-qwen
├── arkham-shard-parse/
│   └── workers/
│       ├── ner_extract.py    # cpu-ner
│       └── chunker.py        # cpu-light
└── arkham-shard-embed/
    └── workers/
        └── embedding.py      # gpu-embed
```

### 3.3 Dispatcher Pattern

Frame stages become thin dispatchers:

```python
# arkham_frame/pipeline/dispatchers/ocr.py

class OCRDispatcher(PipelineStage):
    """
    Dispatches OCR work to shard-owned worker pools.
    Does NOT contain OCR logic.
    """

    def __init__(self, frame):
        super().__init__("ocr", frame)

    async def process(self, context: dict) -> StageResult:
        """Dispatch to appropriate OCR worker."""
        workers = self.frame.get_service("workers")
        resources = self.frame.get_service("resources")

        # Determine best pool based on image quality
        quality = context.get("image_quality", {})

        if quality.get("classification") == "MESSY":
            pool = resources.get_fallback_pool("gpu-qwen") or "gpu-paddle"
        else:
            pool = "gpu-paddle"

        # Dispatch to shard's worker
        job = await workers.enqueue(
            pool=pool,
            job_id=f"ocr-{context['document_id']}",
            payload={
                "document_id": context["document_id"],
                "page_paths": context.get("page_paths", []),
                "quality": quality,
            },
        )

        # Wait for completion (or return pending for async)
        result = await workers.wait_for_job(job.id, timeout=60)

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED if result.success else StageStatus.FAILED,
            output=result.data,
            error=result.error,
        )
```

### 3.4 Shard Worker Implementation

```python
# arkham_shard_ocr/workers/paddle_ocr.py

from arkham_frame import get_frame

class PaddleOCRWorker:
    """
    Actual OCR processing logic.
    Registered with gpu-paddle worker pool.
    """

    def __init__(self):
        self.model = None

    async def initialize(self):
        """Load PaddleOCR model."""
        from paddleocr import PaddleOCR
        self.model = PaddleOCR(use_gpu=True)

    async def process(self, job: Job) -> dict:
        """Process OCR job."""
        page_paths = job.payload["page_paths"]
        results = []

        for path in page_paths:
            ocr_result = self.model.ocr(path)
            results.append({
                "path": path,
                "text": self._extract_text(ocr_result),
                "confidence": self._calculate_confidence(ocr_result),
                "boxes": self._extract_boxes(ocr_result),
            })

        return {
            "pages": results,
            "total_confidence": sum(r["confidence"] for r in results) / len(results),
        }

    async def shutdown(self):
        """Release GPU memory."""
        self.model = None
        import torch
        torch.cuda.empty_cache()
```

### 3.5 Worker Registration

Shards register workers during initialization:

```python
# arkham_shard_ocr/shard.py

class OCRShard(ArkhamShard):
    name = "ocr"
    version = "0.1.0"

    async def initialize(self, frame):
        self.frame = frame
        workers = frame.get_service("workers")

        # Register our workers
        from .workers.paddle_ocr import PaddleOCRWorker
        from .workers.qwen_ocr import QwenOCRWorker

        workers.register_handler("gpu-paddle", PaddleOCRWorker())
        workers.register_handler("gpu-qwen", QwenOCRWorker())
```

### 3.6 Event Flow

```
1. Document ingested
2. Frame PipelineCoordinator starts
3. IngestDispatcher -> ingest shard workers -> returns document info
4. OCRDispatcher -> ocr shard workers -> returns text + boxes
5. ParseDispatcher -> parse shard workers -> returns entities + chunks
6. EmbedDispatcher -> embed shard workers -> returns vector IDs
7. Frame emits "document.processed" event
8. Analysis shards (ach, contradictions, etc.) react to event
```

---

## 4. Manifest Compliance

### 4.1 Critical: Missing Manifests

Create complete v5 manifests for:

#### arkham-shard-graph/shard.yaml

```yaml
name: graph
version: 0.1.0
description: Entity relationship visualization and graph analysis
entry_point: arkham_shard_graph:GraphShard
api_prefix: /api/graph
requires_frame: ">=0.1.0"

navigation:
  category: Visualize
  order: 40
  icon: Network
  label: Relationship Graph
  route: /graph
  sub_routes:
    - id: explore
      label: Explore
      route: /graph/explore
      icon: Search
    - id: communities
      label: Communities
      route: /graph/communities
      icon: Users

dependencies:
  services:
    - database
    - events
  optional:
    - entities
    - documents

capabilities:
  - entity_graph_visualization
  - centrality_metrics
  - community_detection
  - graph_export
  - path_finding

events:
  publishes:
    - graph.computed
    - graph.community.detected
  subscribes:
    - entities.created
    - entities.relationship.created

state:
  strategy: url
  url_params:
    - entityId
    - depth
    - layout

ui:
  has_custom_ui: true
```

#### arkham-shard-timeline/shard.yaml

```yaml
name: timeline
version: 0.1.0
description: Chronological event reconstruction and visualization
entry_point: arkham_shard_timeline:TimelineShard
api_prefix: /api/timeline
requires_frame: ">=0.1.0"

navigation:
  category: Visualize
  order: 41
  icon: Calendar
  label: Timeline
  route: /timeline

dependencies:
  services:
    - database
    - events
  optional:
    - documents
    - entities

capabilities:
  - date_extraction
  - timeline_visualization
  - conflict_detection
  - entity_timelines
  - period_analysis

events:
  publishes:
    - timeline.event.created
    - timeline.conflict.detected
  subscribes:
    - documents.parsed
    - entities.created

state:
  strategy: url
  url_params:
    - startDate
    - endDate
    - entityId
    - projectId

ui:
  has_custom_ui: true
```

#### arkham-shard-anomalies/shard.yaml

```yaml
name: anomalies
version: 0.1.0
description: Multi-dimensional anomaly detection across documents
entry_point: arkham_shard_anomalies:AnomaliesShard
api_prefix: /api/anomalies
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 35
  icon: AlertTriangle
  label: Anomalies
  route: /anomalies
  badge_endpoint: /api/anomalies/unreviewed/count
  badge_type: count

dependencies:
  services:
    - database
    - vectors
    - events
  optional:
    - documents

capabilities:
  - content_anomaly_detection
  - metadata_anomaly_detection
  - temporal_anomaly_detection
  - structural_anomaly_detection
  - statistical_anomaly_detection

events:
  publishes:
    - anomaly.detected
    - anomaly.reviewed
  subscribes:
    - documents.embedded
    - documents.parsed

state:
  strategy: url
  url_params:
    - anomalyType
    - severity
    - reviewed

ui:
  has_custom_ui: false
  list_endpoint: /api/anomalies/list

  list_filters:
    - name: search
      type: search
      label: Search...
      param: q
    - name: type
      type: select
      label: Type
      param: type
      options:
        - { value: "", label: All Types }
        - { value: content, label: Content }
        - { value: metadata, label: Metadata }
        - { value: temporal, label: Temporal }
        - { value: structural, label: Structural }
    - name: severity
      type: select
      label: Severity
      param: severity
      options:
        - { value: "", label: All }
        - { value: high, label: High }
        - { value: medium, label: Medium }
        - { value: low, label: Low }
    - name: reviewed
      type: boolean
      label: Show Reviewed
      param: reviewed
      default: false

  list_columns:
    - { field: document_title, label: Document, type: link, link_route: /document/{document_id}, width: 30% }
    - { field: anomaly_type, label: Type, type: badge, width: 15% }
    - { field: severity, label: Severity, type: badge, width: 10% }
    - { field: description, label: Description, type: text, width: 30% }
    - { field: detected_at, label: Detected, type: date, format: relative, width: 15%, sortable: true, default_sort: desc }

  row_actions:
    - { label: View, type: link, route: /anomalies/{id}, icon: Eye }
    - { label: Dismiss, type: api, endpoint: /api/anomalies/{id}/dismiss, method: POST, icon: X }
```

#### arkham-shard-contradictions/shard.yaml

```yaml
name: contradictions
version: 0.1.0
description: Multi-document contradiction detection and analysis
entry_point: arkham_shard_contradictions:ContradictionsShard
api_prefix: /api/contradictions
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 36
  icon: GitCompare
  label: Contradictions
  route: /contradictions
  badge_endpoint: /api/contradictions/unresolved/count
  badge_type: count

dependencies:
  services:
    - database
    - events
  optional:
    - vectors
    - llm
    - workers

capabilities:
  - claim_extraction
  - contradiction_detection
  - llm_verification
  - chain_detection
  - resolution_tracking

events:
  publishes:
    - contradiction.detected
    - contradiction.resolved
    - contradiction.chain.found
  subscribes:
    - documents.parsed
    - documents.embedded
    - llm.analysis.completed

state:
  strategy: url
  url_params:
    - status
    - severity
    - documentId

ui:
  has_custom_ui: true
```

### 4.2 High: Incomplete Manifests

Update these manifests to add missing sections:

#### arkham-shard-search/shard.yaml (add navigation)

```yaml
# Add to existing:
navigation:
  category: Search
  order: 20
  icon: Search
  label: Search
  route: /search
  sub_routes:
    - id: semantic
      label: Semantic
      route: /search/semantic
      icon: Brain
    - id: keyword
      label: Keyword
      route: /search/keyword
      icon: Type
```

#### arkham-shard-parse/shard.yaml (add navigation)

```yaml
navigation:
  category: Data
  order: 12
  icon: FileText
  label: Parse
  route: /parse
  badge_endpoint: /api/parse/pending/count
```

#### arkham-shard-embed/shard.yaml (add navigation)

```yaml
navigation:
  category: Search
  order: 21
  icon: Binary
  label: Embeddings
  route: /embed
  badge_endpoint: /api/embed/pending/count
```

#### arkham-shard-ingest/shard.yaml (add navigation)

```yaml
navigation:
  category: Data
  order: 10
  icon: Upload
  label: Ingest
  route: /ingest
  badge_endpoint: /api/ingest/queue/count
  sub_routes:
    - id: upload
      label: Upload
      route: /ingest/upload
      icon: Upload
    - id: queue
      label: Queue
      route: /ingest/queue
      icon: ListTodo
```

---

## 5. Implementation Phases

### Phase 1: Foundation ✅ COMPLETE

**Goal:** Core services that everything depends on

1. **ResourceService** implementation ✅
   - Hardware detection (GPU via PyTorch, CPU/RAM via psutil)
   - Tier assignment (minimal/standard/recommended/power)
   - GPU memory management (allocate/release/wait_for_memory)
   - CPU thread management (acquire/release)
   - Per-tier pool configurations with fallbacks
   - Startup report logging
   - Configuration overrides (force_tier, disabled_pools, pool_overrides, gpu_vram_override_mb)
   - Service availability checks (Redis, PostgreSQL, Qdrant, LM Studio)
   - **File:** `services/resources.py`

2. **StorageService** implementation ✅
   - File/blob storage with categories (documents, exports, temp, models, projects)
   - File operations (store, retrieve, delete, exists)
   - Temp file management with automatic cleanup
   - Project-scoped storage (get_project_path, migrate_to_project)
   - Metadata cache with JSON persistence
   - Storage statistics
   - **File:** `services/storage.py`

3. **DocumentService** completion ✅
   - Full CRUD (create_document, get_document, list_documents, update_document, delete_document)
   - Content access (get_document_text, get_document_chunks, get_document_pages)
   - Page and chunk management (add_page, add_chunk)
   - Vector search integration
   - Batch operations (batch_delete, batch_update_status)
   - Database table creation with schema isolation (arkham_frame.documents, chunks, pages)
   - **File:** `services/documents.py`

4. **ProjectService** completion ✅
   - Full CRUD with unique name enforcement
   - Settings management (get_setting, set_setting, delete_setting with dot notation)
   - Project statistics (get_stats)
   - Basic export/import
   - Database table creation (arkham_frame.projects)
   - **File:** `services/projects.py`

**Phase 1 Completed:** 2025-12-25

---

### Phase 2: Data Services ✅ COMPLETE

**Goal:** Complete data access layer

**Status:** ✅ Complete

1. **EntityService** completion ✅
   - [x] Full CRUD (create_entity, get_entity, list_entities, update_entity, delete_entity)
   - [x] Batch entity creation (create_entities_batch)
   - [x] Canonical entity management (create_canonical, get_canonical, update_canonical, delete_canonical, link_to_canonical, unlink_from_canonical, merge_canonicals, find_or_create_canonical)
   - [x] Relationship management (create_relationship, get_relationship, delete_relationship, get_relationships)
   - [x] Entity search with filters (entity_type, document_id, canonical_id, search_text)
   - [x] Co-occurrence analysis (get_cooccurrences, get_entity_network)
   - [x] Entity types enum (PERSON, ORGANIZATION, LOCATION, DATE, MONEY, EVENT, PRODUCT, DOCUMENT, CONCEPT, OTHER)
   - [x] Relationship types enum (WORKS_FOR, LOCATED_IN, MEMBER_OF, OWNS, RELATED_TO, MENTIONED_WITH, etc.)
   - [x] Database tables (arkham_frame.entities, canonical_entities, entity_relationships)
   - [x] Statistics (get_stats)
   - **File:** `services/entities.py`

2. **VectorService** completion ✅
   - [x] Collection management (create_collection, delete_collection, get_collection, list_collections, collection_exists)
   - [x] Standard collections auto-creation (arkham_documents, arkham_chunks, arkham_entities)
   - [x] Vector operations (upsert, upsert_single, delete_vectors, delete_by_filter, get_vector)
   - [x] Search operations (search, search_text, search_batch)
   - [x] Embedding generation (embed_text, embed_texts, embed_and_upsert)
   - [x] Optional local embedding model support (sentence-transformers)
   - [x] Scroll functionality for large collections
   - [x] Distance metrics (COSINE, EUCLIDEAN, DOT)
   - [x] Filter support for search and delete operations
   - [x] Statistics (get_stats with collection details)
   - **File:** `services/vectors.py`

3. **ChunkService** implementation (NEW) ✅
   - [x] Text chunking strategies (FIXED_SIZE, FIXED_TOKENS, SENTENCE, PARAGRAPH, SEMANTIC, RECURSIVE, MARKDOWN, CODE)
   - [x] Token counting with tiktoken support (falls back to character estimation)
   - [x] Document chunking (chunk_document for multi-page documents)
   - [x] Configuration (ChunkConfig with chunk_size, overlap, min/max, separators)
   - [x] Token truncation (truncate_to_tokens)
   - [x] Chunk merging (merge_chunks)
   - [x] Batch token counting (count_tokens_batch)
   - [x] Strategy-specific implementations (recursive split, markdown-aware, code-aware)
   - **File:** `services/chunks.py`

4. **LLMService** enhancements ✅
   - [x] Enhanced chat with stop sequences
   - [x] Structured output (extract_json with schema validation, extract_list)
   - [x] Prompt management (register_prompt, get_prompt, list_prompts, run_prompt)
   - [x] Default prompts (summarize, extract_entities, qa, classify)
   - [x] Streaming (stream_chat, stream_generate)
   - [x] LLMResponse dataclass with token usage tracking
   - [x] JSON extraction patterns (code blocks, objects, arrays)
   - [x] PromptTemplate with variable rendering
   - [x] Statistics (get_stats with request/token counts)
   - **File:** `services/llm.py`

**Phase 2 Completed:** 2025-12-25

---

### Phase 3: Pipeline Refactoring

**Goal:** Move processing logic to shards

**Status:** 🔲 Not Started

1. **Create OCR shard** (NEW SHARD)
   - [ ] Package structure (arkham-shard-ocr)
   - [ ] shard.yaml manifest v5
   - [ ] PaddleOCR worker (gpu-paddle pool)
   - [ ] Qwen-VL worker (gpu-qwen pool)
   - [ ] Quality check worker
   - **Directory:** `packages/arkham-shard-ocr/`

2. **Refactor pipeline stages to dispatchers**
   - [ ] IngestDispatcher - routes to ingest shard workers
   - [ ] OCRDispatcher - routes to OCR shard workers
   - [ ] ParseDispatcher - routes to parse shard workers
   - [ ] EmbedDispatcher - routes to embed shard workers
   - **Directory:** `arkham_frame/pipeline/dispatchers/`

3. **Update existing shards with worker handlers**
   - [ ] ingest shard workers (file_intake, format_detect)
   - [ ] parse shard workers (ner_extract, chunker)
   - [ ] embed shard workers (embedding)

---

### Phase 4: Output Services

**Goal:** Export and notification capabilities

**Status:** 🔲 Not Started

1. **ExportService** implementation (NEW)
   - [ ] Multi-format export (pdf, html, md, json, csv, docx)
   - [ ] Batch export
   - [ ] Template-based export
   - [ ] Format handler registration
   - **File:** `services/export.py`

2. **TemplateService** implementation (NEW)
   - [ ] Template CRUD
   - [ ] Variable extraction
   - [ ] Jinja2 rendering
   - [ ] Template categories (letter, report, checklist, export)
   - **File:** `services/templates.py`

3. **NotificationService** implementation (NEW)
   - [ ] Alert creation and management
   - [ ] Delivery channels (in-app, desktop, webhook, email)
   - [ ] Webhook registration
   - **File:** `services/notifications.py`

4. **SchedulerService** implementation (NEW)
   - [ ] One-time jobs (schedule_at)
   - [ ] Recurring jobs (schedule_recurring with cron)
   - [ ] Deadline tracking with reminders
   - **File:** `services/scheduler.py`

---

### Phase 5: Manifest Compliance

**Goal:** All shards compliant with v5 manifest

**Status:** 🔲 Not Started

1. **Create missing manifests** (CRITICAL)
   - [ ] arkham-shard-graph/shard.yaml
   - [ ] arkham-shard-timeline/shard.yaml
   - [ ] arkham-shard-anomalies/shard.yaml
   - [ ] arkham-shard-contradictions/shard.yaml

2. **Update incomplete manifests** (HIGH)
   - [ ] arkham-shard-search/shard.yaml (add navigation)
   - [ ] arkham-shard-parse/shard.yaml (add navigation)
   - [ ] arkham-shard-embed/shard.yaml (add navigation)
   - [ ] arkham-shard-ingest/shard.yaml (add navigation)

3. **Validate all manifests**
   - [ ] Schema validation against v5 spec
   - [ ] Entry point verification
   - [ ] Navigation category consistency

---

### Phase 6: Integration Testing

**Goal:** Verify all components work together

**Status:** 🔲 Not Started

1. **End-to-end pipeline tests**
   - [ ] Document ingest → parse → embed flow
   - [ ] Multi-format document handling
   - [ ] Error recovery and retry logic

2. **Shard communication tests**
   - [ ] Event bus publish/subscribe
   - [ ] Cross-shard data access
   - [ ] Shard discovery and loading

3. **Worker pool tests**
   - [ ] Pool configuration per tier
   - [ ] GPU memory management
   - [ ] CPU throttling under load

4. **Resource scaling tests**
   - [ ] Tier transitions
   - [ ] Fallback activation
   - [ ] Memory pressure handling

---

## 6. Detailed Specifications

### 6.1 Service Files Status

```
packages/arkham-frame/arkham_frame/services/
├── __init__.py          # ✅ Updated with all exports
├── config.py            # ✅ Exists
├── database.py          # ✅ Exists
├── documents.py         # ✅ COMPLETE (Phase 1)
├── entities.py          # ✅ COMPLETE (Phase 2) - CRUD, canonicals, relationships, co-occurrence
├── events.py            # ✅ Exists
├── llm.py               # ✅ COMPLETE (Phase 2) - streaming, structured output, prompts
├── projects.py          # ✅ COMPLETE (Phase 1)
├── vectors.py           # ✅ COMPLETE (Phase 2) - collections, vectors, embeddings, search
├── workers.py           # ✅ Exists
├── resources.py         # ✅ COMPLETE (Phase 1)
├── storage.py           # ✅ COMPLETE (Phase 1)
├── chunks.py            # ✅ NEW - COMPLETE (Phase 2) - strategies, token counting
├── notifications.py     # 🔲 NEW - Phase 4
├── scheduler.py         # 🔲 NEW - Phase 4
├── export.py            # 🔲 NEW - Phase 4
└── templates.py         # 🔲 NEW - Phase 4
```

### 6.2 New API Routes

```
packages/arkham-frame/arkham_frame/api/
├── resources.py         # NEW: /api/resources
├── storage.py           # NEW: /api/storage
├── notifications.py     # NEW: /api/notifications
├── scheduler.py         # NEW: /api/scheduler
├── export.py            # NEW: /api/export
└── templates.py         # NEW: /api/templates
```

### 6.3 OCR Shard Structure

```
packages/arkham-shard-ocr/
├── pyproject.toml
├── shard.yaml
├── arkham_shard_ocr/
│   ├── __init__.py
│   ├── shard.py
│   ├── api.py
│   ├── models.py
│   └── workers/
│       ├── __init__.py
│       ├── paddle_ocr.py
│       ├── qwen_ocr.py
│       └── quality_check.py
```

### 6.4 Config Extensions

```yaml
# config/frame.yaml additions

# Storage configuration
storage:
  base_path: ${DATA_SILO}
  max_file_size_mb: 500
  cleanup_temp_after_hours: 24

# Export configuration
export:
  pdf_engine: weasyprint  # or reportlab
  default_format: pdf
  temp_dir: ${DATA_SILO}/temp/exports

# Notification configuration
notifications:
  channels:
    - type: inapp
      enabled: true
    - type: desktop
      enabled: true
    - type: webhook
      enabled: false
  retention_days: 30

# Scheduler configuration
scheduler:
  check_interval_seconds: 60
  max_concurrent_jobs: 10
  job_timeout_seconds: 300
```

---

## Summary

This plan provides a comprehensive roadmap to:

1. **Add 7 new services** that enable the full range of planned shards and bundles
2. **Complete 5 existing stub services** with full implementations
3. **Refactor the pipeline** to move processing logic to shards while keeping orchestration in Frame
4. **Fix all manifest compliance issues** so shards load correctly

The phased approach ensures dependencies are satisfied at each stage, with the most critical infrastructure implemented first.

---

## Progress Tracker

| Phase | Description | Status | Completed |
|-------|-------------|--------|-----------|
| **Phase 1** | Foundation (ResourceService, StorageService, DocumentService, ProjectService) | ✅ Complete | 2025-12-25 |
| **Phase 2** | Data Services (EntityService, VectorService, ChunkService, LLMService) | ✅ Complete | 2025-12-25 |
| **Phase 3** | Pipeline Refactoring (OCR shard, Dispatchers) | 🔲 Not Started | - |
| **Phase 4** | Output Services (Export, Template, Notification, Scheduler) | 🔲 Not Started | - |
| **Phase 5** | Manifest Compliance (4 missing + 4 incomplete) | 🔲 Not Started | - |
| **Phase 6** | Integration Testing | 🔲 Not Started | - |

**Services Completed:** 8/11 (ResourceService, StorageService, DocumentService, ProjectService, EntityService, VectorService, ChunkService, LLMService)

**Next Up:** Phase 3 - Pipeline Refactoring (OCR shard, Dispatchers)

---

*Document generated based on analysis of shards_and_bundles.md, current Frame implementation, and architecture documentation.*

*Last Updated: 2025-12-25*
