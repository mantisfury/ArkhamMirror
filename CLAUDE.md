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

### Completed (Standards Finalized)
- **arkham-frame**: Core infrastructure (IMMUTABLE)
- **arkham-shard-shell**: UI shell (React/TypeScript)
- **arkham-shard-ach**: Reference shard implementation
- **arkham-shard-dashboard**: System monitoring shard

### Needs Update to Standards
- arkham-shard-ingest
- arkham-shard-search
- arkham-shard-parse
- arkham-shard-embed
- arkham-shard-graph
- arkham-shard-timeline
- arkham-shard-anomalies
- arkham-shard-contradictions

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
await self.frame.events.publish("ach.matrix.created", {"matrix_id": id})

# Subscribing (in initialize)
await self.frame.events.subscribe("document.processed", self.handle_document)
```

## Navigation Categories

Shards declare their navigation category in `shard.yaml`:
- **System**: Dashboard, settings, admin tools
- **Data**: Ingest, documents, raw data management
- **Search**: Search interfaces
- **Analysis**: ACH, contradictions, anomalies
- **Visualize**: Graph, timeline, visual tools
- **Export**: Export and reporting tools
