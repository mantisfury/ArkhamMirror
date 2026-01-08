# SHATTERED Startup Guide

Quick reference for starting the SHATTERED development environment.

---

## Prerequisites

### Required Services
- **PostgreSQL 14+** - Document and metadata storage
- **Redis 6+** - Job queues and caching
- **Qdrant** - Vector embeddings for semantic search

### Development Tools
- Python 3.10+
- Node.js 18+
- npm or pnpm

---

## Quick Start (Docker - Recommended)

The easiest way to run SHATTERED is with Docker Compose:

```bash
# Start all services (PostgreSQL, Redis, Qdrant, Frame, Shell)
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Access Points:**
- UI: http://localhost:8100
- API Docs: http://localhost:8100/docs
- Health: http://localhost:8100/health

---

## Manual Setup (Development)

### 1. Start External Services

Start PostgreSQL, Redis, and Qdrant (via Docker or locally):

```bash
# Using Docker for services only
docker compose up -d postgres redis qdrant
```

Or configure your own instances and set environment variables:
```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/shattered
export REDIS_URL=redis://localhost:6379
export QDRANT_URL=http://localhost:6333
```

### 2. Install Python Packages

```bash
# Install the Frame (required)
cd packages/arkham-frame && pip install -e .

# Install all shards
for dir in ../arkham-shard-*/; do pip install -e "$dir"; done

# Or install specific shards
pip install -e packages/arkham-shard-dashboard
pip install -e packages/arkham-shard-ach
pip install -e packages/arkham-shard-ingest
# ... etc
```

### 3. Install spaCy Model (for entity extraction)

```bash
python -m spacy download en_core_web_sm
```

### 4. Install Node Dependencies

```bash
cd packages/arkham-shard-shell && npm install
```

### 5. Start Backend

```bash
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100
```

With auto-reload for development:
```bash
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100 --reload
```

### 6. Start UI Shell

In a new terminal:
```bash
cd packages/arkham-shard-shell
npm run dev
```

---

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| UI Shell | http://localhost:5173 | Development UI (Vite) |
| Backend API | http://localhost:8100 | FastAPI backend |
| Health Check | http://localhost:8100/health | Service status |
| API Docs | http://localhost:8100/docs | Swagger UI |
| OpenAPI Spec | http://localhost:8100/openapi.json | API specification |

When using Docker Compose, both UI and API are served from port 8100.

---

## Available Shards (25)

All shards auto-register when installed:

| Category | Shards |
|----------|--------|
| **System** | dashboard, projects, settings |
| **Data** | ingest, documents, parse, embed, ocr, entities |
| **Search** | search |
| **Analysis** | ach, claims, credibility, contradictions, anomalies, patterns, provenance, summary |
| **Visualize** | graph, timeline |
| **Export** | export, reports, letters, packets, templates |

---

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:
- `APP_PORT` - API port (default: 8100)
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `QDRANT_URL` - Vector store connection
- `LLM_ENDPOINT` - Optional LLM API (LM Studio, OpenAI, etc.)
- `LLM_API_KEY` - API key if required

---

## Running Workers (Optional)

Background workers process jobs like document parsing and embedding:

```bash
# List available worker pools
python -m arkham_frame.workers --list-pools

# Start workers for specific pools
python -m arkham_frame.workers --pool cpu-light --count 2
python -m arkham_frame.workers --pool cpu-parse --count 2
python -m arkham_frame.workers --pool gpu-embed --count 1
```

---

## Troubleshooting

### Backend won't start
1. Check Python version: `python --version` (need 3.10+)
2. Verify packages installed: `pip list | grep arkham`
3. Check port availability: `netstat -an | grep 8100`
4. Verify PostgreSQL is running and accessible
5. Check Redis is running

### UI won't start
1. Check Node version: `node --version` (need 18+)
2. Delete node_modules and reinstall: `rm -rf node_modules && npm install`
3. Check for port conflicts on 5173

### Database connection errors
1. Verify PostgreSQL is running
2. Check DATABASE_URL in .env
3. Ensure database exists: `createdb shattered`

### Vector search not working
1. Verify Qdrant is running: `curl http://localhost:6333/health`
2. Check QDRANT_URL in .env

### Shards not discovered
1. Verify shard package installed: `pip show arkham-shard-ach`
2. Check entry_points in shard's pyproject.toml
3. Look for import errors in backend logs
4. Restart the backend after installing new shards

### LLM features not working
1. LLM is optional - app works without it
2. Check LLM_ENDPOINT and LLM_API_KEY in .env
3. Verify LLM service is running (LM Studio, Ollama, etc.)

---

## Development Tips

### Adding a new shard
1. Create package in `packages/arkham-shard-{name}/`
2. Use `arkham-shard-ach` as reference implementation
3. Add `pyproject.toml` with entry_points
4. Create `shard.yaml` manifest
5. Install with `pip install -e .`
6. Restart backend to discover

### Hot reload
- **Backend**: Use `--reload` flag with uvicorn
- **Frontend**: Vite HMR is automatic

### Checking shard registration
```bash
curl http://localhost:8100/health | jq '.shards'
```

---

## Stop Services

```bash
# Docker
docker compose down

# Manual
# Ctrl+C in each terminal, or:

# Windows
netstat -ano | findstr :8100
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8100
kill -9 <pid>
```
