# SHATTERED System Data Reference

This document contains comprehensive system architecture details discovered through codebase analysis. Use this as a reference for wiring shards and understanding inter-shard communication.

---

## Event System

### Frame-Level Events (Worker Service)
| Event | Source | Payload |
|-------|--------|---------|
| `worker.job.completed` | worker-service | {job_id, result} |
| `worker.job.failed` | worker-service | {job_id, error} |
| `worker.started` | worker-service | {worker_id, pool, pid} |
| `worker.stopped` | worker-service | {worker_id, pool} |
| `worker.pool.scaled` | worker-service | {pool, old_count, new_count} |
| `worker.queue.cleared` | worker-service | {pool, status, count} |
| `worker.jobs.retried` | worker-service | {pool, count, jobs} |
| `worker.job.cancelled` | worker-service | {job_id, pool} |
| `shard.registered` | frame | Shard lifecycle |
| `shard.unregistered` | frame | Shard lifecycle |

### Shard Published Events

#### Ingest Shard
| Event | Payload |
|-------|---------|
| `ingest.job.completed` | {job_id, filename, result} |

#### Parse Shard
| Event | Payload |
|-------|---------|
| `parse.document.completed` | {document_id, entities, chunks, chunks_saved} |
| `parse.entity.extracted` | {document_id, entities} |
| `parse.relationships.extracted` | {document_id, relationships} |

#### Embed Shard
| Event | Payload |
|-------|---------|
| `embed.document.completed` | {document_id, chunks_embedded, dimensions} |

#### Entities Shard
| Event | Payload |
|-------|---------|
| `entities.entity.merged` | {entity_ids, merged_id} |
| `entities.relationship.created` | {relationship_id, source_entity, target_entity} |
| `entities.entity.viewed` | {entity_id} |

#### Documents Shard
| Event | Payload |
|-------|---------|
| `documents.metadata.updated` | {document_id, metadata} |
| `documents.selection.changed` | {selected_ids, deselected_ids} |
| `documents.status.changed` | {document_id, status} |
| `documents.view.opened` | {document_id} |

#### ACH Shard
| Event | Payload |
|-------|---------|
| `ach.matrix.created` | {matrix_id, title, created_by} |
| `ach.matrix.updated` | {matrix_id, title} |
| `ach.matrix.deleted` | {matrix_id} |
| `ach.hypothesis.added` | {hypothesis_id, matrix_id} |
| `ach.hypothesis.removed` | {hypothesis_id, matrix_id} |
| `ach.evidence.added` | {evidence_id, hypothesis_id, matrix_id} |
| `ach.evidence.removed` | {evidence_id, hypothesis_id, matrix_id} |
| `ach.score.calculated` | {matrix_id, scores} |
| `ach.rating.updated` | {evidence_id, rating} |
| `ach.documents.linked` | {document_ids, matrix_id} |
| `ach.documents.unlinked` | {document_ids, matrix_id} |
| `ach.corpus.evidence_accepted` | {evidence_ids, corpus_id} |

#### Anomalies Shard
| Event | Payload |
|-------|---------|
| `anomalies.detection_started` | {project_id, doc_ids, config} |
| `anomalies.detected` | {doc_id, count, types} |
| `anomalies.reviewed` | {anomaly_id, doc_id, reviewed_by} |
| `anomalies.confirmed` | {anomaly_id} |
| `anomalies.dismissed` | {anomaly_id} |

#### Contradictions Shard
| Event | Payload |
|-------|---------|
| `contradictions.detected` | {doc_a_id, doc_b_id, count, contradiction_ids} |
| `contradictions.chain_detected` | {chains_count, chain_ids} |
| `contradictions.status_updated` | {contradiction_id, status, analyst_id} |
| `contradictions.confirmed` | {contradiction_id} |
| `contradictions.dismissed` | {contradiction_id} |

#### Settings Shard
| Event | Payload |
|-------|---------|
| `settings.setting.updated` | {setting_key, value} |
| `settings.category.updated` | {category, updates} |
| `settings.profile.applied` | {profile_name} |
| `settings.backup.created` | {name} |
| `settings.backup.restored` | {name, restore_time} |

### Event Subscription Patterns

| Shard | Subscribes To |
|-------|---------------|
| Ingest | `worker.job.completed`, `worker.job.failed` |
| Parse | `ingest.job.completed`, `worker.job.completed` |
| OCR | `ingest.job.completed` |
| Embed | `parse.document.completed` |
| Entities | `parse.entity.extracted`, `parse.relationships.extracted` |
| Documents | `document.processed`, `document.deleted` |
| Anomalies | `embed.document.completed`, `documents.metadata.updated` |
| Contradictions | `parse.document.completed` |
| Claims | `parse.document.completed`, `parse.entity.extracted` |
| Credibility | `claims.claim.verified`, `claims.claim.disputed`, `contradictions.contradiction.detected` |
| Provenance | `*.*.created` (wildcard), `*.*.completed` (wildcard) |
| Timeline | `documents.indexed`, `documents.deleted`, `entities.created` |
| Graph | `entities.created`, `entities.merged`, `documents.deleted` |
| Search | `documents.indexed`, `documents.deleted` |
| Patterns | `parse.document.completed`, `claims.claim.created`, `timeline.event.created` |
| Summary | `parse.document.completed` |
| Settings | `shard.registered`, `shard.unregistered` |

### Event Service API

```python
# Emit an event
await event_bus.emit(event_type: str, payload: dict, source: str)

# Subscribe to events (supports fnmatch wildcards)
await event_bus.subscribe(pattern: str, callback: Callable)

# Unsubscribe
await event_bus.unsubscribe(pattern: str, callback: Callable)

# Query history
events = event_bus.get_events(source=None, event_type=None, limit=100, offset=0)
event_types = event_bus.get_event_types()
event_sources = event_bus.get_event_sources()
```

---

## LLM Service

### Accessing the Service

```python
# In shard initialize()
self._llm = frame.get_service("llm")

# Check availability
if self._llm and self._llm.is_available():
    # LLM is ready
    pass
```

### Core Methods

#### Text Generation
```python
response = await llm.generate(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> LLMResponse

# Access response
text = response.text
model = response.model
tokens = response.tokens_prompt
```

#### Chat Completion
```python
response = await llm.chat(
    messages: List[Dict[str, str]],  # [{"role": "user", "content": "..."}]
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> LLMResponse
```

#### JSON Extraction (Recommended for Structured Output)
```python
result = await llm.extract_json(
    prompt: str,
    schema: Optional[Dict] = None,
    temperature: float = 0.3,  # Lower for structured output
    max_retries: int = 2,
) -> Dict | List
```

#### Streaming
```python
async for chunk in llm.stream_generate(prompt, system_prompt=None):
    print(chunk.text)
    if chunk.is_final:
        break
```

#### Prompt Templates
```python
# Run registered template
response = await llm.run_prompt(
    name: str,  # "summarize", "extract_entities", "qa", "classify"
    variables: Dict = None,
)

# Register custom template
llm.register_prompt(PromptTemplate(
    name="my_prompt",
    template="Analyze: {text}",
    system_prompt="You are an analyst",
    variables=["text"],
))
```

### Response Types

```python
@dataclass
class LLMResponse:
    text: str                    # Generated text
    model: str                   # Model name
    tokens_prompt: Optional[int]
    tokens_completion: Optional[int]
    finish_reason: Optional[str]
    raw_response: Optional[Dict]
```

### Temperature Guidelines
- **0.0-0.3**: Structured output (JSON, classifications)
- **0.5-0.7**: Balanced (summaries, general text)
- **0.8-1.0**: Creative (brainstorming, hypotheses)

### Error Handling
```python
from arkham_frame.services.llm import (
    LLMError,
    LLMUnavailableError,
    LLMRequestError,
    JSONExtractionError,
)

try:
    response = await llm.generate(prompt)
except LLMUnavailableError:
    # Fallback to non-LLM method
    pass
```

---

## Database Service

### Core Methods

```python
# Execute (INSERT, UPDATE, DELETE, DDL)
await db.execute(query: str, params: Dict[str, Any] = None)

# Fetch single row (returns Dict or None)
row = await db.fetch_one(query: str, params: Dict[str, Any] = None)

# Fetch all rows (returns List[Dict])
rows = await db.fetch_all(query: str, params: Dict[str, Any] = None)
```

### CRITICAL: Parameter Syntax

**Use NAMED parameters with `:param_name` syntax and dictionary params:**

```python
# CORRECT
await db.execute(
    "INSERT INTO table (id, name) VALUES (:id, :name)",
    {"id": some_id, "name": some_name}
)

row = await db.fetch_one(
    "SELECT * FROM table WHERE id = :id AND status = :status",
    {"id": doc_id, "status": "active"}
)

# INCORRECT - DO NOT USE
await db.execute("INSERT INTO table VALUES (?, ?)", [id, name])  # Positional params fail
await db.execute("INSERT INTO table VALUES (%s, %s)", (id, name))  # Also fails
```

### Schema Creation Pattern

```python
async def _create_schema(self) -> None:
    if not self._db:
        return

    # Create table
    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_myshardname (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            metadata TEXT DEFAULT '{}',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Create indexes
    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_myshardname_status
        ON arkham_myshardname(status)
    """)

    logger.info("Schema created")
```

### JSONB Handling

```python
import json

# For insertion - convert dict to JSON string
params["metadata"] = json.dumps(metadata_dict)
params["entity_ids"] = json.dumps(entity_ids_list)

# For retrieval - parse JSON string back to dict/list
def _parse_jsonb(value):
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}

metadata = _parse_jsonb(row["metadata"])
```

### Dynamic Query Building

```python
query = "SELECT * FROM arkham_table WHERE 1=1"
params = {}

if status:
    query += " AND status = :status"
    params["status"] = status

if search:
    query += " AND name ILIKE :search"
    params["search"] = f"%{search}%"

query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
params["limit"] = limit
params["offset"] = offset

rows = await db.fetch_all(query, params)
```

### Row to Model Conversion

```python
def _row_to_model(self, row: Dict) -> MyModel:
    return MyModel(
        id=row["id"],
        name=row["name"],
        status=MyStatus(row["status"]),
        metadata=self._parse_jsonb(row["metadata"]),
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )
```

---

## Event-Driven Pipeline

The standard document processing pipeline:

```
ingest.job.completed
        │
        ▼
   Parse Shard
        │
        ├── parse.document.completed ──► Embed Shard ──► embed.document.completed
        │                                                        │
        ├── parse.entity.extracted ──► Entities Shard            ▼
        │                                                   Anomalies Shard
        └── parse.relationships.extracted ──► Entities Shard
                                                                 │
                                                                 ▼
                                              Claims, Contradictions, etc.
```

---

## Shard Integration Pattern

```python
from arkham_frame import ArkhamShard
import logging
import json

logger = logging.getLogger(__name__)

class MyShard(ArkhamShard):
    name = "myshard"
    version = "0.1.0"

    async def initialize(self, frame) -> None:
        self._frame = frame
        self._db = frame.get_service("database")
        self._events = frame.get_service("events")
        self._llm = frame.get_service("llm")

        # Create schema
        await self._create_schema()

        # Subscribe to events
        if self._events:
            await self._events.subscribe("parse.document.completed", self._on_document)

        logger.info(f"{self.name} shard initialized")

    async def shutdown(self) -> None:
        if self._events:
            await self._events.unsubscribe("parse.document.completed", self._on_document)

    async def _on_document(self, event: dict) -> None:
        document_id = event.get("document_id")
        # Process document...

        # Emit our own event
        if self._events:
            await self._events.emit(
                "myshard.processed",
                {"document_id": document_id, "result": "..."},
                source="myshard-shard"
            )
```

---

## Key File Locations

| Component | Path |
|-----------|------|
| Database Service | `packages/arkham-frame/arkham_frame/services/database.py` |
| Event Service | `packages/arkham-frame/arkham_frame/services/events.py` |
| LLM Service | `packages/arkham-frame/arkham_frame/services/llm.py` |
| Shard Interface | `packages/arkham-frame/arkham_frame/shard_interface.py` |
| Document Service | `packages/arkham-frame/arkham_frame/services/documents.py` |
| Entity Service | `packages/arkham-frame/arkham_frame/services/entities.py` |
| Vector Service | `packages/arkham-frame/arkham_frame/services/vectors.py` |

---

*Last updated: 2025-12-31*
