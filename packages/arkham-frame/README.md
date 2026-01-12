# arkham-frame

> Core infrastructure for the SHATTERED modular architecture

**Version:** 0.1.0
**Python:** >=3.10
**License:** MIT

---

## Overview

ArkhamFrame is the immutable core infrastructure that powers the SHATTERED modular architecture. It provides all essential services that shards (feature modules) depend upon, following the **Voltron philosophy**: plug-and-play components that combine into a unified application.

**Key Principles:**
- **Immutable Core**: Shards depend on the Frame; the Frame never depends on shards
- **Service-Oriented**: All functionality exposed through well-defined service interfaces
- **Auto-Discovery**: Shards are automatically discovered and loaded via Python entry points
- **Event-Driven**: Loose coupling between shards via the EventBus

```
                    +------------------+
                    |   ArkhamFrame    |    <-- THE FRAME (immutable core)
                    |   (Core Infra)   |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |         |          |          |         |
   +----v----+ +--v--+ +-----v-----+ +--v--+ +---v---+
   |Dashboard| | ACH | |  Search   | |Parse| | Graph |  <-- SHARDS
   | Shard   | |Shard| |  Shard    | |Shard| | Shard |
   +---------+ +-----+ +-----------+ +-----+ +-------+
```

---

## Architecture

ArkhamFrame provides 16+ services organized into functional layers:

```
+---------------------------------------------------------------------+
|                         ArkhamFrame                                  |
+---------------------------------------------------------------------+
|  Infrastructure Layer                                                |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
|  |   Config    | |  Resources  | |   Storage   | |  Database   |     |
|  |  Service    | |  Service    | |  Service    | |  Service    |     |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
+---------------------------------------------------------------------+
|  AI & Search Layer                                                   |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
|  |   Vectors   | |    LLM      | |   Chunks    | | AI Analyst  |     |
|  |  Service    | |  Service    | |  Service    | |  Service    |     |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
+---------------------------------------------------------------------+
|  Data Layer                                                          |
|  +-------------+ +-------------+ +-------------+                     |
|  | Documents   | |  Entities   | |  Projects   |                     |
|  |  Service    | |  Service    | |  Service    |                     |
|  +-------------+ +-------------+ +-------------+                     |
+---------------------------------------------------------------------+
|  Communication Layer                                                 |
|  +-------------+ +-------------+                                     |
|  |   Events    | |   Workers   |                                     |
|  |    Bus      | |  Service    |                                     |
|  +-------------+ +-------------+                                     |
+---------------------------------------------------------------------+
|  Output Layer                                                        |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
|  |   Export    | |  Templates  | |Notifications| |  Scheduler  |     |
|  |  Service    | |  Service    | |  Service    | |  Service    |     |
|  +-------------+ +-------------+ +-------------+ +-------------+     |
+---------------------------------------------------------------------+
```

---

## Services

### Database Service

PostgreSQL database access with schema isolation per shard.

**Schema Convention:** Each shard gets its own schema named `arkham_{shard_name}`.

```python
# Access via frame
db = frame.db  # or frame.database

# Execute queries
await db.execute("INSERT INTO table VALUES (?)", [value])
row = await db.fetch_one("SELECT * FROM table WHERE id = ?", [id])
rows = await db.fetch_all("SELECT * FROM table")

# Database administration
schemas = await db.list_schemas()  # ['arkham_ach', 'arkham_documents', ...]
stats = await db.get_stats()       # {connected, schemas, total_tables, total_rows}
tables = await db.get_table_info("arkham_ach")  # [{name, row_count, size_bytes}]
await db.vacuum_analyze()          # Run VACUUM ANALYZE on all schemas
```

**Exceptions:** `DatabaseError`, `SchemaNotFoundError`, `SchemaExistsError`, `QueryExecutionError`

---

### Vector Service

pgvector-based vector storage for embeddings and similarity search, using PostgreSQL's native vector extension.

```python
vectors = frame.vectors

# Check availability
if vectors.is_available():
    if vectors.embedding_available():
        # Generate embeddings
        vector = await vectors.embed_text("search query")
        vectors_batch = await vectors.embed_texts(["text1", "text2"])

# Collection management (creates tables with vector columns)
await vectors.create_collection("my_collection", vector_size=384)
await vectors.delete_collection("my_collection")
collections = await vectors.list_collections()
info = await vectors.get_collection("arkham_documents")

# Vector operations
from arkham_frame.services import VectorPoint

point = VectorPoint(id="doc1", vector=[0.1, 0.2, ...], payload={"title": "Doc"})
await vectors.upsert("arkham_documents", [point])
await vectors.delete_vectors("arkham_documents", ["doc1"])

# Search (uses pgvector's ivfflat or hnsw indexes)
results = await vectors.search(
    collection="arkham_documents",
    query_vector=[0.1, 0.2, ...],
    limit=10,
    filter={"type": "article"},
    score_threshold=0.7
)

# Text search (auto-embeds query)
results = await vectors.search_text("arkham_documents", "search query", limit=10)
```

**Standard Collections (stored as PostgreSQL tables):**
- `arkham_documents` - Document embeddings
- `arkham_chunks` - Chunk embeddings
- `arkham_entities` - Entity embeddings

**Exceptions:** `VectorServiceError`, `VectorStoreUnavailableError`, `CollectionNotFoundError`, `EmbeddingError`

---

### LLM Service

OpenAI-compatible LLM abstraction with structured output support.

```python
llm = frame.llm

# Check availability
if llm.is_available():
    print(f"Model: {llm.get_model()}")
    print(f"Endpoint: {llm.get_endpoint()}")

# Simple generation
response = await llm.generate(
    prompt="Summarize this document...",
    system_prompt="You are a helpful assistant.",
    temperature=0.7,
    max_tokens=500
)
print(response.text)

# Chat completion
response = await llm.chat([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
])

# Streaming
async for chunk in llm.stream_generate("Tell me a story..."):
    print(chunk.text, end="")
    if chunk.is_final:
        break

# Structured JSON extraction
data = await llm.extract_json(
    prompt="Extract entities from: John works at Acme Corp",
    schema={"type": "object", "properties": {"entities": {"type": "array"}}}
)

# Prompt templates
llm.register_prompt(PromptTemplate(
    name="summarize",
    template="Summarize: {text}",
    system_prompt="Be concise.",
    variables=["text"]
))
response = await llm.run_prompt("summarize", variables={"text": document_text})
```

**Built-in Prompts:** `summarize`, `extract_entities`, `qa`, `classify`

**API Key Sources:** `LLM_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`

**Exceptions:** `LLMError`, `LLMUnavailableError`, `LLMRequestError`, `JSONExtractionError`

---

### Event Bus

Publish/subscribe messaging for inter-shard communication.

```python
events = frame.events

# Subscribe to events (supports wildcards)
async def handle_document(event_data):
    print(f"Document processed: {event_data['payload']}")

await events.subscribe("document.*", handle_document)
await events.subscribe("ach.matrix.created", my_handler)

# Emit events
await events.emit(
    event_type="ach.matrix.created",
    payload={"matrix_id": "abc123", "hypotheses": 3},
    source="ach-shard"
)

# Query event history
recent = events.get_events(source="ach-shard", limit=100)
event_types = events.get_event_types()    # Unique event types
sources = events.get_event_sources()       # Unique sources
count = events.get_event_count(source="ach-shard", event_type="ach.*")

# Unsubscribe
await events.unsubscribe("document.*", handle_document)
```

**Event Naming Convention:** `{shard}.{entity}.{action}` (e.g., `ach.matrix.created`, `document.processed`)

**Exceptions:** `EventValidationError`, `EventDeliveryError`

---

### Worker Pools

PostgreSQL-backed job queues using SKIP LOCKED pattern for reliable, transactional job processing.

```python
workers = frame.workers

# Enqueue a job
job = await workers.enqueue(
    pool="cpu-heavy",
    job_id="parse-doc-123",
    payload={"file_path": "/path/to/doc.pdf"},
    priority=1  # 1 = highest
)

# Enqueue and wait for result
result = await workers.enqueue_and_wait(
    pool="cpu-extract",
    payload={"document_id": "doc123"},
    timeout=300.0
)

# Scale workers
await workers.scale("cpu-heavy", count=4)
await workers.start_worker("gpu-paddle")
await workers.stop_worker("worker-abc123")

# Queue management
stats = await workers.get_queue_stats()
jobs = await workers.get_jobs(pool="cpu-heavy", status="pending")
await workers.clear_queue("cpu-heavy", status="failed")
await workers.retry_failed_jobs("cpu-heavy")
await workers.cancel_job("job-123")

# Get pool info
pools = workers.get_pool_info()
```

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

**Exceptions:** `WorkerError`, `WorkerNotFoundError`, `QueueUnavailableError`

---

### Storage Service

File and blob storage management.

```python
storage = frame.storage

# Store content
storage_id = await storage.store(
    path="2024/01/document.pdf",
    content=file_bytes,
    metadata={"source": "upload"},
    category="documents"  # documents, exports, temp, models, projects
)

# Retrieve content
content, metadata = await storage.retrieve(storage_id)

# File operations
exists = await storage.exists(storage_id)
info = await storage.get_file_info(storage_id)
await storage.delete(storage_id)

# Temporary files
temp_path = await storage.create_temp(suffix=".pdf")
# ... use temp file ...
await storage.cleanup_temp(temp_path)

# Project-scoped storage
project_path = await storage.get_project_path("project-123")
new_id = await storage.migrate_to_project(storage_id, "project-123")

# Statistics
stats = await storage.get_storage_stats()
files = await storage.list_files(prefix="2024/", category="documents", limit=100)
```

**Storage Categories:**
- `documents` - Ingested documents
- `exports` - Generated exports
- `temp` - Temporary processing files
- `models` - Cached ML models
- `projects` - Project-scoped storage

**Exceptions:** `StorageError`, `StorageFileNotFoundError`, `StorageFullError`, `InvalidPathError`

---

### Resource Service

Hardware detection and resource tier assignment.

```python
resources = frame.resources

# Get resource tier
tier = resources.get_tier()       # ResourceTier enum
tier_name = resources.get_tier_name()  # "minimal", "standard", "recommended", "power"

# System resources
sys_resources = resources.get_resources()
print(f"GPU: {sys_resources.gpu_name} ({sys_resources.gpu_vram_mb}MB)")
print(f"CPU: {sys_resources.cpu_cores_physical} cores")
print(f"RAM: {sys_resources.ram_total_mb}MB")

# GPU management
if resources.gpu_available():
    available_mb = resources.get_gpu_available_mb()
    if await resources.gpu_can_load("paddle"):
        await resources.gpu_allocate("paddle")
        # ... use GPU ...
        await resources.gpu_release("paddle")

# CPU management
threads = resources.get_available_cpu_threads()
if await resources.cpu_acquire(4):
    # ... use 4 threads ...
    await resources.cpu_release(4)

# Pool configuration
config = resources.get_pool_config("gpu-paddle")
best_pool = resources.get_best_pool("gpu-paddle")  # Returns fallback if GPU unavailable
```

**Resource Tiers:**

| Tier | GPU VRAM | Description |
|------|----------|-------------|
| `minimal` | None | CPU-only, limited concurrency |
| `standard` | < 6GB | Basic GPU support |
| `recommended` | 6-12GB | Full feature support |
| `power` | > 12GB | Maximum concurrency |

**Exceptions:** `ResourceError`, `GPUMemoryError`, `CPUAllocationError`

---

### Chunk Service

Text chunking and tokenization for document processing.

```python
chunks = frame.chunks

# Count tokens
token_count = chunks.count_tokens("Hello world")
counts = chunks.count_tokens_batch(["text1", "text2"])

# Truncate to token limit
truncated = chunks.truncate_to_tokens(long_text, max_tokens=1000)

# Chunk text
from arkham_frame.services import ChunkConfig, ChunkStrategy

config = ChunkConfig(
    strategy=ChunkStrategy.RECURSIVE,  # or FIXED_SIZE, SENTENCE, PARAGRAPH, MARKDOWN, CODE
    chunk_size=1000,
    chunk_overlap=200,
    min_chunk_size=100,
    respect_sentence_boundary=True
)

text_chunks = chunks.chunk(document_text, config, document_id="doc123")
for chunk in text_chunks:
    print(f"Chunk {chunk.index}: {chunk.token_count} tokens")

# Chunk multi-page document
pages = [{"text": "Page 1 content...", "page_number": 1}, ...]
all_chunks = chunks.chunk_document(pages, config, document_id="doc123")

# Merge small chunks
merged = chunks.merge_chunks(text_chunks, max_size=2000)
```

**Chunking Strategies:**
- `FIXED_SIZE` - Fixed character count
- `FIXED_TOKENS` - Fixed token count
- `SENTENCE` - Sentence boundaries
- `PARAGRAPH` - Paragraph boundaries
- `RECURSIVE` - Recursive character splitting (LangChain-style)
- `MARKDOWN` - Markdown-aware splitting
- `CODE` - Code-aware splitting

**Exceptions:** `ChunkServiceError`, `TokenizerError`

---

### AI Junior Analyst Service

Shared AI-powered analysis across all shards.

```python
ai_analyst = frame.ai_analyst

# Check availability
if ai_analyst.is_available():
    # Perform analysis
    from arkham_frame.services import AnalysisRequest, AnalysisDepth

    request = AnalysisRequest(
        shard="graph",
        target_id="node-123",
        context={
            "selected_item": {"id": "node-123", "name": "John Doe"},
            "related_items": [...],
            "statistics": {"node_count": 50}
        },
        depth=AnalysisDepth.DETAILED
    )

    response = await ai_analyst.analyze(request)
    print(response.analysis)

    # Streaming analysis
    async for chunk in ai_analyst.stream_analyze(request):
        print(chunk, end="")

    # Register custom shard prompt
    ai_analyst.register_shard_prompt("my_shard", """
        You are an analyst for my custom shard...
    """)
```

**Supported Shards:** `graph`, `timeline`, `ach`, `anomalies`, `contradictions`, `patterns`, `entities`, `claims`, `credibility`, `provenance`, `documents`

---

## Shard Interface

All shards must implement the `ArkhamShard` abstract base class.

```python
from arkham_frame import ArkhamShard, ShardManifest

class MyShard(ArkhamShard):
    name = "my-shard"
    version = "0.1.0"
    description = "My custom shard"

    async def initialize(self, frame) -> None:
        """Called when the shard is loaded."""
        self.frame = frame

        # Access Frame services
        await self.frame.db.execute("CREATE SCHEMA IF NOT EXISTS arkham_my_shard")

        # Subscribe to events
        await self.frame.events.subscribe("document.processed", self.handle_document)

    async def shutdown(self) -> None:
        """Called when the shard is being unloaded."""
        await self.frame.events.unsubscribe("document.processed", self.handle_document)

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    async def handle_document(self, event_data):
        """Event handler example."""
        doc_id = event_data["payload"]["document_id"]
        # Process document...
```

### Manifest (shard.yaml)

```yaml
name: my-shard
version: 0.1.0
description: "My custom shard"
entry_point: arkham_shard_my:MyShard
api_prefix: /api/my-shard
requires_frame: ">=0.1.0"

navigation:
  category: Analysis  # System, Data, Search, Analysis, Visualize, Export
  order: 50
  icon: Sparkles
  label: My Shard
  route: /my-shard

dependencies:
  services:
    - database
    - events
  optional:
    - llm
    - vectors
  shards: []  # Always empty - no shard dependencies!

events:
  publishes:
    - my-shard.item.created
    - my-shard.item.updated
  subscribes:
    - document.processed
```

### Package Configuration (pyproject.toml)

```toml
[project]
name = "arkham-shard-my"
version = "0.1.0"
description = "My custom shard"
requires-python = ">=3.10"
dependencies = [
    "arkham-frame>=0.1.0",
]

[project.entry-points."arkham.shards"]
my-shard = "arkham_shard_my:MyShard"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://anom:anompass@localhost:5435/anomdb` | PostgreSQL connection (includes pgvector) |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio endpoint |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `ARKHAM_SERVE_SHELL` | `false` | Serve Shell UI from Frame |

**Note:** PostgreSQL 14+ with pgvector extension is the only required infrastructure dependency. Job queues and vector storage are both handled within PostgreSQL.

### Configuration Service

```python
config = frame.config

# Get configuration values
db_url = config.database_url
llm_endpoint = config.llm_endpoint

# Get custom values (dot notation)
value = config.get("resources.force_tier", default="recommended")

# Set values
config.set("custom.setting", "value")
```

### Resource Overrides

```python
# Force a specific resource tier
config.set("resources.force_tier", "recommended")

# Disable specific pools
config.set("resources.disabled_pools", ["gpu-qwen", "gpu-whisper"])

# Override pool settings
config.set("resources.pool_overrides", {
    "cpu-heavy": {"max_workers": 8}
})
```

---

## Installation

### From Source

```bash
cd packages/arkham-frame
pip install -e .
```

### With Embedding Support

```bash
pip install -e ".[embedding]"
```

### Development Dependencies

```bash
pip install -e ".[dev]"
```

### Dependencies

**Required:**
- `fastapi>=0.104.0`
- `uvicorn>=0.24.0`
- `sqlalchemy>=2.0.0`
- `asyncpg>=0.29.0` - Async PostgreSQL driver
- `pgvector>=0.2.0` - Vector operations for PostgreSQL
- `httpx>=0.25.0`
- `pyyaml>=6.0`
- `psycopg2-binary>=2.9.0`
- `python-multipart>=0.0.6`
- `python-dotenv>=1.0.0`

**Optional (embedding):**
- `sentence-transformers>=2.2.0`
- `torch>=2.0.0`

---

## Running

### Start Frame Server

```bash
cd packages/arkham-frame
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100 --reload
```

### With Workers

```bash
# In a separate terminal
arkham-workers --pool cpu-heavy --count 2
```

### Docker Compose

The Frame is typically run as part of the full SHATTERED stack:

```bash
docker compose up
```

### API Documentation

Once running, access the interactive API docs at:
- Swagger UI: http://127.0.0.1:8100/docs
- ReDoc: http://127.0.0.1:8100/redoc

---

## API Reference

### Core Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/frame` | Frame state |
| GET | `/api/shards` | List loaded shards |
| GET | `/api/shards/{name}` | Shard details |
| GET | `/api/events` | Recent events |
| POST | `/api/events/emit` | Emit event |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |

### Frame Instance

```python
from arkham_frame import get_frame

frame = get_frame()  # Returns singleton Frame instance

# Access services
frame.db          # DatabaseService
frame.database    # Alias for db
frame.vectors     # VectorService
frame.llm         # LLMService
frame.events      # EventBus
frame.workers     # WorkerService
frame.storage     # StorageService
frame.resources   # ResourceService
frame.chunks      # ChunkService
frame.ai_analyst  # AIJuniorAnalystService
frame.documents   # DocumentService
frame.entities    # EntityService
frame.projects    # ProjectService

# Get service by name
service = frame.get_service("vectors")

# Get frame state
state = frame.get_state()
```

### Active Project Context

```python
# Set active project (affects collection routing)
await frame.set_active_project("project-123")

# Get active project
project = await frame.get_active_project()

# Get collection name for current context
collection = frame.get_collection_name("documents")
# Returns "project_123_documents" if project active
# Returns "arkham_documents" otherwise
```

---

## External Dependencies

### Required Services

| Service | Default Port | Purpose |
|---------|--------------|---------|
| PostgreSQL 14+ | 5435 | All data storage (documents, entities, job queues, vectors) |

PostgreSQL must have the **pgvector** extension installed for vector storage capabilities.

### Optional Services

| Service | Default Port | Purpose |
|---------|--------------|---------|
| LM Studio | 1234 | LLM inference |

---

## License

MIT License - See LICENSE file for details.

---

*ArkhamFrame v0.1.0 - Core infrastructure for SHATTERED*
