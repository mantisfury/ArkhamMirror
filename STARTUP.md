# SHATTERED Startup Guide

Quick reference for starting the SHATTERED development environment.

---

## Prerequisites

### Required Services
- **PostgreSQL 15+** with **pgvector** extension - All data storage (documents, vectors, job queue)

### Development Tools
- Python 3.10+
- Node.js 18+
- npm

---

## Quick Start (Docker - Recommended)

The easiest way to run SHATTERED is with Docker Compose:

```bash
# Start all services (PostgreSQL + App)
docker compose up -d

# View logs
docker compose logs -f app

# Stop services
docker compose down

# Stop and delete all data
docker compose down -v
```

**Access Points:**
- UI: http://localhost:8100
- API Docs: http://localhost:8100/docs
- Health: http://localhost:8100/health

---

## Manual Setup (Development)

### 1. Start PostgreSQL with pgvector

Start PostgreSQL with the pgvector extension:

```bash
# Using Docker for PostgreSQL only
docker compose up -d postgres
```

Or use a local PostgreSQL instance with pgvector installed:
```bash
export DATABASE_URL=postgresql://arkham:arkhampass@localhost:5432/arkhamdb
```

The migration script (`migrations/001_consolidation.sql`) creates required extensions and schemas automatically.

### 2. Install Python Packages

```bash
# Install the Frame (required)
cd packages/arkham-frame && pip install -e .

# Install all shards
for dir in packages/arkham-shard-*/; do pip install -e "$dir"; done

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

### 4. Metadata extraction (optional)

Document metadata is extracted during ingest (single source of truth). For the richest metadata (PDF, images, Office, etc.):

- **EXIFTool** (recommended): Install [ExifTool](https://exiftool.org/) and ensure `exiftool` is on your PATH. The ingest extract worker uses it when available; otherwise it falls back to pypdf, python-docx, openpyxl, and Pillow.
- **Magika** (optional): For content-based MIME detection, install the ingest shard with `pip install -e ".[magika]"` from `packages/arkham-shard-ingest`.

**PII detection**: The **PII shard** (`arkham-shard-pii`) is the single source for PII. Install it with `pip install -e .` from `packages/arkham-shard-pii`. During document registration, ingest calls the PII shard (when installed) to analyze metadata; results are stored in document metadata (`pii_detected`, `pii_types`, `pii_entities`, `pii_count`). If the PII shard is not installed, ingest uses a built-in regex/heuristic fallback. For stronger detection, run [Microsoft Presidio](https://github.com/microsoft/presidio) and set `PII_PRESIDIO_URL` (e.g. `http://localhost:3000`); see `packages/arkham-shard-pii/README.md` for Presidio Docker setup.

### 5. Install Node Dependencies

```bash
cd packages/arkham-shard-shell && npm install
```

### 6. Start Backend

```bash
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100
```

With auto-reload for development:
```bash
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100 --reload
```

### 7. Start UI Shell

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

## Architecture

SHATTERED uses a **PostgreSQL-only** architecture:

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | PostgreSQL 15+ | Relational data, schema per shard |
| **Vectors** | pgvector extension | Semantic search, embeddings |
| **Job Queue** | PostgreSQL (SKIP LOCKED) | Background task processing |
| **Events** | PostgreSQL LISTEN/NOTIFY | Real-time event distribution |

This consolidation (replacing Redis + Qdrant) provides:
- Single dependency for deployment
- Air-gap compatible operation
- ACID transactions across vectors and data
- Simplified operations

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

### Required Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://arkham:arkhampass@localhost:5432/arkhamdb` | PostgreSQL connection |
| `AUTH_SECRET_KEY` | (generate for prod) | JWT signing key - use `openssl rand -hex 32` |

### Optional LLM Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENDPOINT` | `http://localhost:1234/v1` | LLM API endpoint (LM Studio, OpenAI, etc.) |
| `LM_STUDIO_URL` | - | Convenience variable for LM Studio |
| `VLM_ENDPOINT` | - | Vision model for OCR (Qwen-VL, GPT-4o) |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |

### API Keys (environment only, never in config files)
- `LLM_API_KEY` - Generic LLM API key
- `OPENAI_API_KEY` - OpenAI
- `OPENROUTER_API_KEY` - OpenRouter
- `ANTHROPIC_API_KEY` - Anthropic
- `TOGETHER_API_KEY` - Together AI
- `GROQ_API_KEY` - Groq

### Other Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `localhost:5173,localhost:8100` | Allowed CORS origins |
| `ARKHAM_OFFLINE_MODE` | `false` | Air-gap mode (no model downloads) |
| `ARKHAM_SERVE_SHELL` | `false` | Serve static UI from backend |

---

## Worker Pools

Workers auto-spawn when jobs are submitted. Available pools:

| Pool | Type | Workers | Purpose |
|------|------|---------|---------|
| `io-file` | IO | 20 | File operations |
| `io-db` | IO | 10 | Database operations |
| `cpu-light` | CPU | 50 | Light processing |
| `cpu-heavy` | CPU | 6 | Heavy computations |
| `cpu-ner` | CPU | 8 | Named Entity Recognition |
| `cpu-extract` | CPU | 4 | Data extraction |
| `cpu-image` | CPU | 4 | Image processing |
| `cpu-archive` | CPU | 2 | Archive processing |
| `gpu-paddle` | GPU | 1 | OCR (2GB VRAM) |
| `gpu-qwen` | GPU | 1 | Vision tasks (8GB VRAM) |
| `gpu-whisper` | GPU | 1 | Audio transcription (4GB VRAM) |
| `gpu-embed` | GPU | 1 | Embedding generation (2GB VRAM) |
| `llm-enrich` | LLM | 4 | Data enrichment |
| `llm-analysis` | LLM | 2 | Analysis tasks |

Workers are managed via the Dashboard shard's Workers tab.

---

## Troubleshooting

### Backend won't start
1. Check Python version: `python --version` (need 3.10+)
2. Verify packages installed: `pip list | grep arkham`
3. Check port availability: `netstat -an | grep 8100`
4. Verify PostgreSQL is running and accessible

### UI won't start
1. Check Node version: `node --version` (need 18+)
2. Delete node_modules and reinstall: `rm -rf node_modules && npm install`
3. Check for port conflicts on 5173

### Database connection errors
1. Verify PostgreSQL is running
2. Check DATABASE_URL in .env
3. Ensure database exists with pgvector extension

### Vector search not working
1. Check pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname = 'vector';`
2. Verify embedding model is downloaded (check logs for download progress)
3. For air-gap mode, ensure models are pre-cached in `ARKHAM_MODEL_CACHE`

### Shards not discovered
1. Verify shard package installed: `pip show arkham-shard-ach`
2. Check entry_points in shard's pyproject.toml
3. Look for import errors in backend logs
4. Restart the backend after installing new shards

### LLM features not working
1. LLM is optional - app works without it
2. Check LLM_ENDPOINT in .env
3. Verify LLM service is running (LM Studio, Ollama, etc.)
4. Check API key is set in environment (not config file)

---

## Development Tips

### Adding a new shard
1. Create package in `packages/arkham-shard-{name}/`
2. Use `arkham-shard-ach` as reference implementation
3. Add `pyproject.toml` with entry_points
4. Create `shard.yaml` manifest (v5 format)
5. Install with `pip install -e .`
6. Restart backend to discover

### Hot reload
- **Backend**: Use `--reload` flag with uvicorn
- **Frontend**: Vite HMR is automatic

### Checking shard registration
```bash
curl http://localhost:8100/api/shards | jq
```

### Checking service health
```bash
curl http://localhost:8100/health | jq
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
