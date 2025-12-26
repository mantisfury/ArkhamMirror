# ArkhamFrame Specification v1.0

> Technical specification for the ArkhamFrame core infrastructure

---

## Overview

ArkhamFrame is the immutable core infrastructure that provides all services to shards in the SHATTERED architecture. Shards depend on the Frame; the Frame never depends on shards.

```
Frame Version: 0.1.0
Python: >=3.10
FastAPI: REST API server
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ArkhamFrame                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │   Config    │ │  Resources  │ │   Storage   │ │  Database   │   │
│  │  Service    │ │  Service    │ │  Service    │ │  Service    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │   Vectors   │ │    LLM      │ │   Chunks    │ │   Events    │   │
│  │  Service    │ │  Service    │ │  Service    │ │    Bus      │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │   Workers   │ │  Documents  │ │  Entities   │ │  Projects   │   │
│  │  Service    │ │  Service    │ │  Service    │ │  Service    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │   Export    │ │  Templates  │ │Notifications│ │  Scheduler  │   │
│  │  Service    │ │  Service    │ │  Service    │ │  Service    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Shard Loader    │
                    │ (Entry Points)    │
                    └─────────┬─────────┘
                              │
     ┌──────────┬──────────┬──┴───┬──────────┬──────────┐
     ▼          ▼          ▼      ▼          ▼          ▼
 ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
 │Dashboard│ │ Ingest │ │ Search │ │  ACH   │ │ Graph  │ │ ...    │
 │ Shard  │ │ Shard  │ │ Shard  │ │ Shard  │ │ Shard  │ │ Shards │
 └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## Core Class: ArkhamFrame

The central orchestrator that initializes and manages all services.

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `config` | `ConfigService` | Configuration management |
| `resources` | `ResourceService` | Hardware detection, tier management |
| `storage` | `StorageService` | File and blob storage |
| `db` | `DatabaseService` | PostgreSQL with schema isolation |
| `vectors` | `VectorService` | Qdrant vector store |
| `llm` | `LLMService` | LM Studio integration |
| `chunks` | `ChunkService` | Text chunking and tokenization |
| `events` | `EventBus` | Pub/sub event system |
| `workers` | `WorkerService` | Redis job queues |
| `documents` | `DocumentService` | Document management |
| `entities` | `EntityService` | Entity extraction/management |
| `projects` | `ProjectService` | Project management |
| `shards` | `Dict[str, ArkhamShard]` | Loaded shard instances |

### Methods

```python
async def initialize() -> None:
    """Initialize all Frame services in order."""

async def shutdown() -> None:
    """Shutdown all Frame services in reverse order."""

def get_service(name: str) -> Optional[Any]:
    """Get a service by name."""

def get_state() -> Dict[str, Any]:
    """Get current Frame state for API."""
```

### Global Access

```python
from arkham_frame import get_frame

frame = get_frame()  # Returns the singleton Frame instance
```

---

## Services Reference

### 1. ConfigService

Configuration management via environment variables and YAML files.

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://anom:anompass@localhost:5435/anomdb` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6380` | Redis connection |
| `QDRANT_URL` | `http://localhost:6343` | Qdrant connection |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio endpoint |
| `CONFIG_PATH` | None | Optional YAML config path |

**Properties:**
- `database_url: str`
- `redis_url: str`
- `qdrant_url: str`
- `llm_endpoint: str`

**Methods:**
```python
def get(key: str, default: Any = None) -> Any:
    """Get config value by dot-notation key (e.g., 'resources.force_tier')."""

def set(key: str, value: Any) -> None:
    """Set a config value."""
```

---

### 2. ResourceService

Hardware detection and resource tier assignment.

**Resource Tiers:**
| Tier | GPU VRAM | Description |
|------|----------|-------------|
| `minimal` | None | CPU-only, limited concurrency |
| `standard` | < 6GB | Basic GPU support |
| `recommended` | 6-12GB | Full feature support |
| `power` | > 12GB | Maximum concurrency |

**Detected Resources (`SystemResources`):**
- GPU: `gpu_available`, `gpu_name`, `gpu_vram_mb`, `cuda_version`
- CPU: `cpu_cores_physical`, `cpu_cores_logical`, `cpu_model`
- Memory: `ram_total_mb`, `ram_available_mb`
- Disk: `disk_free_mb`, `data_silo_path`
- Services: `redis_available`, `postgres_available`, `qdrant_available`, `lm_studio_available`

**Key Methods:**
```python
def get_tier() -> ResourceTier
def get_tier_name() -> str
def get_resources() -> SystemResources
def get_pool_config(pool: str) -> PoolConfig
def get_pool_limits() -> Dict[str, PoolConfig]
def get_best_pool(preferred: str) -> Optional[str]

# GPU Management
def gpu_available() -> bool
def get_gpu_vram_mb() -> int
def get_gpu_available_mb() -> int
async def gpu_can_load(model: str) -> bool
async def gpu_allocate(model: str) -> bool
async def gpu_release(model: str) -> None

# CPU Management
def get_max_cpu_threads() -> int
def get_available_cpu_threads() -> int
async def cpu_acquire(threads: int) -> bool
async def cpu_release(threads: int) -> None
```

---

### 3. DatabaseService

PostgreSQL database with schema isolation per shard.

**Schema Convention:** `arkham_{shard_name}`

**Methods:**
```python
async def initialize() -> None
async def shutdown() -> None
async def is_connected() -> bool
async def list_schemas() -> List[str]
async def get_stats() -> Dict[str, Any]
```

**Exceptions:**
- `DatabaseError` - Base exception
- `SchemaNotFoundError`
- `SchemaExistsError`
- `QueryExecutionError`

**Connection Details:**
- Uses SQLAlchemy with connection pooling
- `pool_size=5`, `max_overflow=10`
- `pool_pre_ping=True` for connection health checks

---

### 4. StorageService

File and blob storage management.

**Types:**
```python
@dataclass
class FileInfo:
    path: str
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    content_type: str

@dataclass
class StorageStats:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    file_count: int
```

**Exceptions:**
- `StorageError`
- `StorageFileNotFoundError`
- `StorageFullError`
- `InvalidPathError`

---

### 5. VectorService

Qdrant vector store for embeddings and similarity search.

**Types:**
```python
@dataclass
class VectorPoint:
    id: str
    vector: List[float]
    payload: Dict[str, Any]

@dataclass
class CollectionInfo:
    name: str
    vector_size: int
    point_count: int
    distance_metric: DistanceMetric

class DistanceMetric(Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT = "dot"
```

**Constants:**
```python
EMBEDDING_DIMENSIONS = {
    "bge-m3": 1024,
    "bge-small": 384,
    "minilm": 384,
}
```

**Exceptions:**
- `VectorServiceError`
- `VectorStoreUnavailableError`
- `CollectionNotFoundError`
- `CollectionExistsError`
- `EmbeddingError`
- `VectorDimensionError`

---

### 6. LLMService

LM Studio integration for language model inference.

**Types:**
```python
@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str

@dataclass
class StreamChunk:
    content: str
    finished: bool

@dataclass
class PromptTemplate:
    name: str
    template: str
    variables: List[str]
```

**Methods:**
```python
def is_available() -> bool
async def complete(prompt: str, **kwargs) -> LLMResponse
async def stream(prompt: str, **kwargs) -> AsyncIterator[StreamChunk]
async def extract_json(prompt: str, schema: dict) -> dict
```

**Exceptions:**
- `LLMError`
- `LLMUnavailableError`
- `LLMRequestError`
- `JSONExtractionError`
- `PromptNotFoundError`

---

### 7. ChunkService

Text chunking and tokenization.

**Types:**
```python
class ChunkStrategy(Enum):
    FIXED = "fixed"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"

@dataclass
class ChunkConfig:
    strategy: ChunkStrategy
    chunk_size: int
    overlap: int
    min_chunk_size: int

@dataclass
class TextChunk:
    text: str
    start_char: int
    end_char: int
    token_count: int
    metadata: Dict[str, Any]
```

**Exceptions:**
- `ChunkServiceError`
- `TokenizerError`

---

### 8. EventBus

Pub/sub event system for inter-shard communication.

**Types:**
```python
@dataclass
class Event:
    event_type: str
    payload: Dict[str, Any]
    source: str
    timestamp: datetime
    sequence: int
```

**Methods:**
```python
def subscribe(pattern: str, callback: Callable) -> None:
    """Subscribe to events matching pattern (supports wildcards)."""

def unsubscribe(pattern: str, callback: Callable) -> None

async def emit(event_type: str, payload: Dict[str, Any], source: str) -> None:
    """Emit an event to all matching subscribers."""

def get_events(source: Optional[str] = None, limit: int = 100) -> List[Event]:
    """Get recent events from history."""
```

**Event Naming Convention:**
```
{shard}.{entity}.{action}

Examples:
- ach.matrix.created
- document.parsed
- ingest.file.uploaded
- worker.job.completed
```

**Exceptions:**
- `EventValidationError`
- `EventDeliveryError`

---

### 9. WorkerService

Redis job queues with priority handling.

**Worker Pools:**

| Pool | Type | Max Workers | Description |
|------|------|-------------|-------------|
| `io-file` | IO | 20 | File I/O operations |
| `io-db` | IO | 10 | Database operations |
| `cpu-light` | CPU | 50 | Light CPU tasks |
| `cpu-heavy` | CPU | 6 | Heavy CPU tasks |
| `cpu-ner` | CPU | 8 | NER processing |
| `cpu-extract` | CPU | 4 | Text extraction |
| `cpu-image` | CPU | 4 | Image processing |
| `cpu-archive` | CPU | 2 | Archive handling |
| `gpu-paddle` | GPU | 1 | PaddleOCR (2GB VRAM) |
| `gpu-qwen` | GPU | 1 | Qwen VL (8GB VRAM) |
| `gpu-whisper` | GPU | 1 | Whisper (4GB VRAM) |
| `gpu-embed` | GPU | 1 | Embeddings (2GB VRAM) |
| `llm-enrich` | LLM | 4 | LLM enrichment |
| `llm-analysis` | LLM | 2 | LLM analysis |

**Types:**
```python
@dataclass
class Job:
    id: str
    pool: str
    payload: Dict[str, Any]
    priority: int  # 1 = highest
    status: str  # pending, active, completed, failed
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
```

**Methods:**
```python
async def enqueue(pool: str, job_id: str, payload: Dict, priority: int = 1) -> Job
async def dequeue(pool: str) -> Optional[Job]
async def complete_job(job_id: str, result: Dict = None) -> None
async def fail_job(job_id: str, error: str) -> None
async def wait_for_result(job_id: str, timeout: float = 300.0) -> Dict
async def enqueue_and_wait(pool: str, payload: Dict, priority: int = 1, timeout: float = 300.0) -> Dict
async def get_queue_stats() -> List[Dict[str, Any]]

# Worker Registration (for shards)
def register_worker(worker_class: type) -> None
def unregister_worker(worker_class: type) -> None
def get_registered_workers() -> Dict[str, type]
```

**Exceptions:**
- `WorkerError`
- `WorkerNotFoundError`
- `QueueUnavailableError`

---

### 10. DocumentService

Document management service.

**Types:**
```python
class DocumentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    EMBEDDED = "embedded"
    FAILED = "failed"

@dataclass
class Document:
    id: str
    title: str
    content: str
    status: DocumentStatus
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    position: int
    metadata: Dict[str, Any]

@dataclass
class Page:
    number: int
    content: str
    metadata: Dict[str, Any]

@dataclass
class SearchResult:
    document_id: str
    score: float
    content: str
    metadata: Dict[str, Any]

@dataclass
class BatchResult:
    processed: int
    failed: int
    errors: List[str]
```

**Exceptions:**
- `DocumentError`
- `DocumentNotFoundError`

---

### 11. EntityService

Entity extraction and management.

**Types:**
```python
class EntityType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    EVENT = "event"
    PRODUCT = "product"
    CONCEPT = "concept"

class RelationshipType(Enum):
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    LOCATED_IN = "located_in"
    WORKS_FOR = "works_for"
    KNOWS = "knows"

@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    mentions: List[Dict]
    metadata: Dict[str, Any]

@dataclass
class CanonicalEntity:
    id: str
    name: str
    type: EntityType
    aliases: List[str]
    merged_from: List[str]

@dataclass
class EntityRelationship:
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    confidence: float
    evidence: List[str]

@dataclass
class CoOccurrence:
    entity1_id: str
    entity2_id: str
    count: int
    documents: List[str]
```

**Exceptions:**
- `EntityError`
- `EntityNotFoundError`
- `CanonicalNotFoundError`
- `RelationshipNotFoundError`

---

### 12. ProjectService

Project management for organizing documents.

**Types:**
```python
@dataclass
class Project:
    id: str
    name: str
    description: str
    document_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

@dataclass
class ProjectStats:
    document_count: int
    entity_count: int
    total_chunks: int
    storage_bytes: int
```

**Exceptions:**
- `ProjectError`
- `ProjectNotFoundError`
- `ProjectExistsError`

---

### 13. ExportService

Multi-format document and data export.

**Types:**
```python
class ExportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"

@dataclass
class ExportOptions:
    format: ExportFormat
    template: Optional[str]
    include_metadata: bool = True
    include_timestamps: bool = True
    pretty_print: bool = True
    title: Optional[str] = None
    author: Optional[str] = None
    page_size: str = "letter"
    orientation: str = "portrait"

@dataclass
class ExportResult:
    format: ExportFormat
    content: Union[str, bytes]
    filename: str
    content_type: str
    size_bytes: int
    exported_at: datetime
```

**Methods:**
```python
def export(data: Any, format: ExportFormat, options: ExportOptions = None) -> ExportResult
async def export_to_file(data: Any, filepath: Path, format: ExportFormat = None) -> ExportResult
def batch_export(data: Any, formats: List[ExportFormat]) -> Dict[ExportFormat, ExportResult]
def register_exporter(exporter: BaseExporter) -> None
def get_history(limit: int = 100) -> List[Dict]
```

**Exceptions:**
- `ExportError`
- `ExportFormatError`
- `ExportRenderError`
- `TemplateNotFoundError`

---

### 14. TemplateService

Jinja2 template management for reports and documents.

**Types:**
```python
@dataclass
class Template:
    name: str
    content: str
    description: str
    category: str
    variables: List[str]
    created_at: datetime
    updated_at: datetime

@dataclass
class RenderResult:
    content: str
    template_name: str
    rendered_at: datetime
    variables_used: Dict[str, Any]
```

**Default Templates:**
- `report_basic` - Basic report with title and content
- `document_summary` - Document summary with entities
- `entity_report` - Entity report with relationships
- `analysis_report` - Analysis report with findings
- `email_notification` - Email notification template

**Methods:**
```python
def register(name: str, content: str, description: str = "", category: str = "general") -> Template
def get(name: str) -> Optional[Template]
def list(category: Optional[str] = None) -> List[Template]
def delete(name: str) -> bool
def render(name: str, variables: Dict = None, **kwargs) -> RenderResult
def render_string(content: str, variables: Dict = None, **kwargs) -> str
def validate(content: str) -> List[str]
def load_from_directory(directory: Path) -> int
```

**Exceptions:**
- `TemplateError`
- `TemplateNotFoundError`
- `TemplateRenderError`
- `TemplateSyntaxError`

---

### 15. NotificationService

Email and webhook notifications.

**Types:**
```python
class NotificationType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"

class ChannelType(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"

class DeliveryStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class Notification:
    id: str
    type: NotificationType
    title: str
    message: str
    recipient: str
    channel: ChannelType
    status: DeliveryStatus
    created_at: datetime
    sent_at: Optional[datetime]
    retry_count: int
    max_retries: int = 3
```

**Methods:**
```python
def configure_email(name: str, smtp_host: str, smtp_port: int = 587, ...) -> None
def configure_webhook(name: str, url: str, method: str = "POST", ...) -> None
def list_channels() -> List[str]
def remove_channel(name: str) -> bool
async def send(title: str, message: str, recipient: str, channel: str = "log", type: NotificationType = NotificationType.INFO) -> Notification
async def send_batch(notifications: List[Dict]) -> List[Notification]
def subscribe_to_event(event_pattern: str, channel: str, recipient: str, ...) -> None
def get_history(limit: int = 100, status: DeliveryStatus = None) -> List[Notification]
def get_stats() -> Dict[str, Any]
```

**Exceptions:**
- `NotificationError`
- `DeliveryError`
- `ConfigurationError`
- `ChannelNotFoundError`

---

### 16. SchedulerService

Cron-like scheduled task execution.

**Types:**
```python
class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class TriggerType(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    DATE = "date"

@dataclass
class ScheduledJob:
    id: str
    name: str
    func_name: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    status: JobStatus
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    run_count: int
    error_count: int

@dataclass
class JobResult:
    job_id: str
    started_at: datetime
    finished_at: datetime
    status: JobStatus
    result: Any
    error: Optional[str]
    execution_time_ms: float
```

**Methods:**
```python
async def start() -> None
async def stop() -> None
def register_job(name: str, func: Callable) -> None
def schedule_cron(name: str, func_name: str, cron_expression: str = None, **cron_fields) -> ScheduledJob
def schedule_interval(name: str, func_name: str, hours: int = 0, minutes: int = 0, seconds: int = 0, ...) -> ScheduledJob
def schedule_once(name: str, func_name: str, run_date: datetime) -> ScheduledJob
def get_job(job_id: str) -> Optional[ScheduledJob]
def list_jobs(status: JobStatus = None) -> List[ScheduledJob]
def pause_job(job_id: str) -> bool
def resume_job(job_id: str) -> bool
def remove_job(job_id: str) -> bool
def get_history(job_id: str = None, limit: int = 100) -> List[JobResult]
def get_stats() -> Dict[str, Any]
```

**Exceptions:**
- `SchedulerError`
- `JobNotFoundError`
- `JobExecutionError`
- `InvalidScheduleError`

---

## Shard Loading

Shards are discovered and loaded via Python entry points.

### Entry Point Configuration

In `pyproject.toml`:
```toml
[project.entry-points."arkham.shards"]
dashboard = "arkham_shard_dashboard:DashboardShard"
ach = "arkham_shard_ach:ACHShard"
```

### Loading Process

1. Frame initializes all services
2. Entry points discovered via `importlib.metadata.entry_points(group="arkham.shards")`
3. Each shard class is instantiated (no arguments)
4. `shard.initialize(frame)` is called with Frame reference
5. Shard routes are registered with FastAPI app
6. Shard stored in `frame.shards[name]`

### Shutdown Process

1. Each shard's `shutdown()` method is called
2. Frame services shut down in reverse initialization order

---

## API Routes

### Frame Core Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/frame` | Frame state |
| GET | `/api/frame/services` | Service status |
| GET | `/api/shards` | List loaded shards |
| GET | `/api/shards/{name}` | Shard details |
| GET | `/api/events` | Recent events |
| POST | `/api/events/emit` | Emit event |

### Data Service Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Get document |
| POST | `/api/documents` | Create document |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/entities` | List entities |
| GET | `/api/entities/{id}` | Get entity |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |

### Output Service Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/export` | Export data |
| GET | `/api/export/formats` | List formats |
| GET | `/api/templates` | List templates |
| POST | `/api/templates` | Create template |
| POST | `/api/templates/render` | Render template |
| GET | `/api/notifications` | Notification history |
| POST | `/api/notifications/send` | Send notification |
| GET | `/api/scheduler/jobs` | List jobs |
| POST | `/api/scheduler/jobs` | Create job |

---

## Service Dependencies

```
ConfigService
    └── (no dependencies)

ResourceService
    └── ConfigService

StorageService
    └── ConfigService

DatabaseService
    └── ConfigService

VectorService
    └── ConfigService

LLMService
    └── ConfigService

ChunkService
    └── ConfigService

EventBus
    └── ConfigService

WorkerService
    └── ConfigService

DocumentService
    ├── DatabaseService
    ├── VectorService
    └── StorageService

EntityService
    └── DatabaseService

ProjectService
    ├── DatabaseService
    └── StorageService

ExportService
    ├── StorageService (optional)
    └── TemplateService (optional)

TemplateService
    └── (no dependencies)

NotificationService
    ├── EventBus (optional)
    └── TemplateService (optional)

SchedulerService
    └── EventBus (optional)
```

---

## Configuration Override Examples

### YAML Configuration

```yaml
# config.yaml
database:
  pool_size: 10
  max_overflow: 20

resources:
  force_tier: recommended
  disabled_pools:
    - gpu-qwen
  pool_overrides:
    cpu-heavy:
      max_workers: 8

redis:
  timeout: 30

llm:
  default_model: qwen2.5-coder
  max_tokens: 4096
```

### Environment Overrides

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/db
export REDIS_URL=redis://host:6379
export QDRANT_URL=http://host:6333
export LM_STUDIO_URL=http://host:1234/v1
export CONFIG_PATH=/path/to/config.yaml
```

---

## External Dependencies

### Required Services

| Service | Default Port | Purpose |
|---------|--------------|---------|
| PostgreSQL | 5435 | Document and entity storage |
| Redis | 6380 | Job queues |
| Qdrant | 6343 | Vector storage |

### Optional Services

| Service | Default Port | Purpose |
|---------|--------------|---------|
| LM Studio | 1234 | LLM inference |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2024-12 | Initial release with 16 services |

---

*ArkhamFrame Specification v1.0 - 2024-12-25*
