# arkham-shard-dashboard

> System monitoring, service health, LLM configuration, database controls, and worker management for ArkhamFrame.

## Overview

The Dashboard shard provides centralized system monitoring and administration capabilities. It serves as the primary control center for:

- **Service Health Monitoring** - Real-time status of all Frame services
- **LLM Configuration** - Configure and test LLM endpoints with provider presets
- **Database Management** - Schema statistics, VACUUM ANALYZE, and database reset
- **Worker Management** - Pool scaling, job queue controls, and worker lifecycle
- **Event Monitoring** - System event log with filtering and payload inspection

## Features

### Health Monitoring
- Real-time service status (Database, Vectors, LLM, Workers, Events)
- PostgreSQL-backed queue statistics with pending/active/completed/failed counts
- Docker environment detection and indicator

### LLM Configuration
- Provider presets: LM Studio, Ollama, OpenAI, OpenRouter, Together AI, Groq
- Custom endpoint configuration for any OpenAI-compatible API
- Connection testing with response preview
- OpenRouter fallback routing with model priority configuration
- API key status detection (without exposing keys)
- Docker-aware endpoints (automatic `host.docker.internal` support)

### Database Management
- Schema and table statistics with row counts and sizes
- Per-table information including last vacuum/analyze dates
- VACUUM ANALYZE for performance optimization
- Database reset with confirmation (dangerous operation)

### Worker Management
- Worker pool overview grouped by type (IO, CPU, GPU, LLM)
- Scale workers up/down per pool
- Start/stop individual workers or all workers in a pool
- Clear pending jobs from queues
- Retry failed jobs

### Event Monitoring
- Real-time event log with auto-refresh (5-second interval)
- Filter by event type and source
- Color-coded event categories (error, success, warning, etc.)
- Payload inspection modal with full JSON view
- Clear event history

## Installation

```bash
cd packages/arkham-shard-dashboard
pip install -e .
```

The shard is auto-discovered by ArkhamFrame via entry points.

## API Endpoints

All endpoints are prefixed with `/api/dashboard`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Get all service health status |

### LLM Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/llm` | Get current LLM configuration |
| POST | `/llm` | Update LLM configuration (endpoint, model) |
| POST | `/llm/test` | Test LLM connection with a simple prompt |
| POST | `/llm/reset` | Reset LLM configuration to defaults |
| GET | `/llm/fallback` | Get fallback model configuration |
| POST | `/llm/fallback` | Set OpenRouter fallback models |

### Database

| Method | Path | Description |
|--------|------|-------------|
| GET | `/database` | Get database connection info and schemas |
| GET | `/database/stats` | Get detailed database statistics |
| GET | `/database/tables/{schema}` | Get table info for a specific schema |
| POST | `/database/migrate` | Run database migrations |
| POST | `/database/reset` | Reset database (requires `confirm: true`) |
| POST | `/database/vacuum` | Run VACUUM ANALYZE |

### Workers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/workers` | Get list of active workers |
| GET | `/queues` | Get queue statistics |
| GET | `/pools` | Get worker pool information |
| GET | `/jobs` | Get jobs (optional: `pool`, `status`, `limit`) |
| POST | `/workers/scale` | Scale workers for a queue |
| POST | `/workers/start` | Start a worker for a queue |
| POST | `/workers/stop` | Stop a specific worker |
| POST | `/workers/stop-all` | Stop all workers (optional: by pool) |
| POST | `/queues/clear` | Clear jobs from a queue |
| POST | `/jobs/retry` | Retry failed jobs |
| POST | `/jobs/cancel` | Cancel a specific job |

### Events

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events` | Get events (optional: `limit`, `offset`, `source`, `event_type`) |
| GET | `/events/types` | Get unique event types |
| GET | `/events/sources` | Get unique event sources |
| POST | `/events/clear` | Clear event history |
| GET | `/errors` | Get recent error events |

### API Examples

```bash
# Get service health
curl http://localhost:8100/api/dashboard/health

# Update LLM endpoint
curl -X POST http://localhost:8100/api/dashboard/llm \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "http://localhost:11434/v1", "model": "llama3.2"}'

# Test LLM connection
curl -X POST http://localhost:8100/api/dashboard/llm/test

# Get database stats
curl http://localhost:8100/api/dashboard/database/stats

# Scale workers
curl -X POST http://localhost:8100/api/dashboard/workers/scale \
  -H "Content-Type: application/json" \
  -d '{"queue": "cpu-heavy", "count": 4}'

# Get filtered events
curl "http://localhost:8100/api/dashboard/events?source=ingest&limit=50"

# Configure OpenRouter fallback models
curl -X POST http://localhost:8100/api/dashboard/llm/fallback \
  -H "Content-Type: application/json" \
  -d '{"models": ["google/gemini-2.0-flash-exp", "anthropic/claude-3.5-sonnet"], "enabled": true}'
```

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

## Database Schema

The Dashboard shard does not create its own database tables. It reads from Frame services and other shard schemas for monitoring purposes.

## UI Routes

| Route | Tab | Description |
|-------|-----|-------------|
| `/dashboard` | Overview | Service health and queue status |
| `/dashboard/llm` | LLM Config | Configure LLM connection |
| `/dashboard/database` | Database | Database operations |
| `/dashboard/workers` | Workers | Queue management |
| `/dashboard/events` | Events | System event log |

## Dependencies

### Required Services
- `config` - Configuration access
- `database` - Database health and controls
- `events` - Event monitoring
- `workers` - Worker management

### Optional Services
- `llm` - LLM configuration and testing
- `resources` - Hardware tier information
- `vectors` - pgvector status (PostgreSQL extension)

## Configuration

LLM settings are persisted to the Settings shard database for survival across restarts. Environment variables can also configure default endpoints:

| Variable | Description |
|----------|-------------|
| `LLM_ENDPOINT` | Default LLM endpoint URL |
| `LLM_MODEL` | Default model name |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `TOGETHER_API_KEY` | Together AI API key |
| `GROQ_API_KEY` | Groq API key |

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

# Access dashboard UI
# http://localhost:5173/dashboard (with shell running)
```

## License

MIT License - Part of the SHATTERED project.
