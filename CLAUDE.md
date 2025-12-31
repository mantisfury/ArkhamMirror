# SHATTERED - Project Guidelines

## Project Overview

SHATTERED is a modular "distro-style" architecture where **shards** (feature modules) are loaded into a **frame** (core infrastructure). The system follows the **Voltron** philosophy: plug-and-play components that combine into a unified application.

## Architecture

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

## Critical Rules

### The Frame (`packages/arkham-frame/`)
- **IMMUTABLE**: Shards are NOT allowed to alter the frame
- Provides core services: database, vectors, LLM, events, workers
- Defines the `ArkhamShard` ABC that all shards must implement
- Shards depend on the frame, never the reverse

### The Shell (`packages/arkham-shard-shell/`)
- React/TypeScript UI application
- Renders navigation from shard manifests
- Provides generic list/form components for shards
- Shards can have custom UIs or use generic rendering

### Shards (`packages/arkham-shard-*/`)
- Self-contained feature modules
- **CAN** depend on the frame (`arkham-frame>=0.1.0`)
- **CAN** optionally utilize outputs of other shards (via events/shared data)
- **CANNOT** depend on other shards (no direct imports)
- **CANNOT** modify the frame
- Communicate via the EventBus for loose coupling

## Shard Standards (Reference Implementation: `arkham-shard-ach`)

### Package Structure
```
packages/arkham-shard-{name}/
├── pyproject.toml          # Package definition with entry point
├── shard.yaml              # Manifest v5 format
├── README.md               # Documentation
├── arkham_shard_{name}/
│   ├── __init__.py         # Exports {Name}Shard class
│   ├── shard.py            # Shard implementation (extends ArkhamShard)
│   ├── api.py              # FastAPI routes
│   ├── models.py           # Pydantic models (optional)
│   └── services/           # Business logic (optional)
```

### pyproject.toml Requirements
```toml
[project]
name = "arkham-shard-{name}"
version = "0.1.0"
description = "Description of shard"
requires-python = ">=3.10"

dependencies = [
    "arkham-frame>=0.1.0",  # REQUIRED: frame dependency
    # Additional dependencies...
]

[project.entry-points."arkham.shards"]
{name} = "arkham_shard_{name}:{Name}Shard"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### shard.yaml (Manifest v5)
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
  badge_endpoint: /api/{name}/count  # optional
  badge_type: count|dot              # optional
  sub_routes:                        # optional
    - id: sub-id
      label: Sub Label
      route: /{name}/sub
      icon: Icon

dependencies:
  services:
    - database
    - events
  optional:
    - llm
  shards: []  # Always empty - no shard dependencies!

capabilities:
  - feature_one
  - feature_two

events:
  publishes:
    - {name}.entity.created
    - {name}.entity.updated
  subscribes:
    - other.event.completed

state:
  strategy: url|local|session|none
  url_params:
    - param1

ui:
  has_custom_ui: true|false
  # If false, uses generic list/form rendering
```

### Shard Class Implementation
```python
from arkham_frame import ArkhamShard, ShardManifest

class {Name}Shard(ArkhamShard):
    name = "{name}"
    version = "0.1.0"
    description = "Shard description"

    async def initialize(self, frame) -> None:
        self.frame = frame
        # Setup: create schema, subscribe to events

    async def shutdown(self) -> None:
        # Cleanup: unsubscribe, close connections

    def get_routes(self):
        from .api import router
        return router
```

## Current State

### Core Infrastructure
- **arkham-frame**: Core infrastructure (IMMUTABLE)
- **arkham-shard-shell**: UI shell (React/TypeScript)

### Complete Shards (25 total)
All shards have backend (shard.py + api.py) and frontend (pages/) implementations:

**System**: dashboard, settings
**Data**: ingest, documents, parse, embed
**Search**: search, ocr
**Analysis**: ach, anomalies, contradictions, entities, claims, credibility, patterns, provenance
**Visualize**: graph, timeline
**Export**: export, reports, letters, packets, templates, summary, projects

## Development Commands

```bash
# Install frame
cd packages/arkham-frame && pip install -e .

# Install a shard
cd packages/arkham-shard-{name} && pip install -e .

# Run frame (auto-discovers installed shards)
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Run shell (UI)
cd packages/arkham-shard-shell && npm run dev

# API docs: http://127.0.0.1:8100/docs
```

## Key Files

- `packages/arkham-frame/arkham_frame/shard_interface.py` - Shard ABC and manifest dataclasses
- `packages/arkham-shard-ach/shard.yaml` - Reference manifest v5
- `packages/arkham-shard-ach/pyproject.toml` - Reference package config
- `docs/voltron_plan.md` - Architecture documentation

## Event-Driven Communication

Shards communicate via the EventBus, never by direct import:

```python
# Publishing (in shard)
await self.frame.events.emit("ach.matrix.created", {"matrix_id": id}, source="ach-shard")

# Subscribing (in initialize)
self.frame.events.subscribe("document.processed", self.handle_document)

# Querying events
events = self.frame.events.get_events(source="ach-shard", limit=100)
types = self.frame.events.get_event_types()
sources = self.frame.events.get_event_sources()
```

## Navigation Categories

Shards declare their navigation category in `shard.yaml`:
- **System**: Dashboard, settings, admin tools
- **Data**: Ingest, documents, raw data management
- **Search**: Search interfaces
- **Analysis**: ACH, contradictions, anomalies
- **Visualize**: Graph, timeline, visual tools
- **Export**: Export and reporting tools

## Dashboard Shard

The Dashboard shard provides system monitoring and administration:

### Tabs
- **Health**: Service status overview (database, vectors, LLM, workers, events)
- **LLM**: LLM endpoint configuration and connection testing
- **Database**: Schema/table statistics, VACUUM ANALYZE, database reset
- **Workers**: Worker pool management, scaling, job queue controls
- **Events**: Event log with filtering by type/source, payload inspection

### Database Statistics API
```python
# Get database stats (sizes, row counts per schema)
stats = await frame.db.get_stats()

# Get table info for a schema
tables = await frame.db.get_table_info("arkham_ach")

# Run VACUUM ANALYZE
result = await frame.db.vacuum_analyze()
```

### Worker Management API
```python
# Scale workers for a pool
await frame.workers.scale("cpu-parse", count=4)

# Get pool info
pools = frame.workers.get_pool_info()

# Clear queue, retry failed jobs
await frame.workers.clear_queue("cpu-parse", status="pending")
await frame.workers.retry_failed_jobs("cpu-parse")
```

## Claude Code File Write Workaround

When Claude Code's native Write/Edit tools fail with "File has not been read yet" or "File has been unexpectedly modified" errors, use Python via Bash as a workaround:

### For Simple Content
```bash
python -c "from pathlib import Path; Path('FILE_PATH').write_text('CONTENT')"
```

### For Complex Files (TypeScript, React, etc.)
Write content to a temp file first, then use Python to read and write:
```bash
# Write content to temp file
cat > /tmp/content.txt << 'CONTENT_EOF'
file content here
CONTENT_EOF

# Use Python to copy to target
python -c "
from pathlib import Path
content = Path('/tmp/content.txt').read_text()
Path('TARGET_PATH').write_text(content)
"
```

### For Files with Special Characters
Use base64 encoding:
```bash
echo 'BASE64_CONTENT' | base64 -d > file.txt
```

This is a known bug in Claude Code (GitHub issues #4230, #10437, #12805) affecting Windows/MINGW environments.
