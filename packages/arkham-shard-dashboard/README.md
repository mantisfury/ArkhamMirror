# arkham-shard-dashboard

System monitoring and controls shard for ArkhamMirror.

## Overview

The Dashboard shard provides centralized system monitoring and configuration capabilities. It serves as the primary interface for:

- Service health monitoring
- LLM configuration and testing
- Database management
- Worker pool management
- Event log viewing

## Installation

```bash
cd packages/arkham-shard-dashboard
pip install -e .
```

The shard is auto-discovered by ArkhamFrame via entry points.

## Dependencies

### Required Services
- `config` - Configuration access
- `database` - Database health and controls
- `events` - Event monitoring
- `workers` - Worker management

### Optional Services
- `llm` - LLM configuration and testing
- `resources` - Hardware tier information
- `vectors` - Vector store status

## API Endpoints

All endpoints are prefixed with `/api/dashboard`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Get all service health status |

### LLM Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/llm` | Get LLM configuration |
| PUT | `/llm` | Update LLM configuration |
| POST | `/llm/test` | Test LLM connection |

### Database

| Method | Path | Description |
|--------|------|-------------|
| GET | `/database` | Get database info |
| POST | `/database/migrate` | Run migrations |
| POST | `/database/reset` | Reset database (requires confirm) |
| POST | `/database/vacuum` | Run VACUUM ANALYZE |

### Workers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/workers` | List active workers |
| GET | `/queues` | Get queue statistics |
| POST | `/workers/scale` | Scale workers for a pool |
| POST | `/workers/start` | Start a worker |
| POST | `/workers/{id}/stop` | Stop a worker |

### Events

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events` | Get recent events |
| GET | `/events/errors` | Get recent error events |

## Events

### Published Events

| Event | Payload | Description |
|-------|---------|-------------|
| `dashboard.service.checked` | `{services: [...]}` | Health check completed |
| `dashboard.database.migrated` | `{success: bool}` | Migrations ran |
| `dashboard.database.reset` | `{success: bool}` | Database reset |
| `dashboard.database.vacuumed` | `{success: bool}` | VACUUM completed |
| `dashboard.worker.scaled` | `{pool, count}` | Workers scaled |
| `dashboard.worker.started` | `{pool, worker_id}` | Worker started |
| `dashboard.worker.stopped` | `{worker_id}` | Worker stopped |
| `dashboard.llm.configured` | `{endpoint, model}` | LLM config updated |

### Subscribed Events

The dashboard subscribes to all events (`*`) for monitoring purposes.

## Navigation

- **Category:** System
- **Order:** 0 (primary system shard)
- **Route:** `/dashboard`

### Sub-routes

| Route | Label | Description |
|-------|-------|-------------|
| `/dashboard` | Overview | System overview |
| `/dashboard/llm` | LLM Config | LLM configuration |
| `/dashboard/database` | Database | Database controls |
| `/dashboard/workers` | Workers | Worker management |
| `/dashboard/events` | Events | Event log |

## URL State

The dashboard uses URL state strategy with these parameters:

- `tab` - Active tab (overview, llm, database, workers, events)
- `timeRange` - Time range filter for events

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run frame with dashboard
cd ../arkham-frame
python -m uvicorn arkham_frame.main:app --reload
```

## License

Part of the ArkhamMirror SHATTERED project.
