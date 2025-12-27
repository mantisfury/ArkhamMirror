# Shattered KANDOR v2: Cloud Deployment Plan

> *"Even a shard can show you truth - now in the cloud."*

## Executive Summary

**Shattered KANDOR** is the containerized, cloud-deployable distribution of SHATTERED - the modular Frame + Shards architecture for document analysis and investigative research.

This document provides a complete roadmap for building, publishing, and deploying SHATTERED as a prepackaged Docker solution. Users select which Shards (feature modules) they want, then deploy to any cloud VPS with a single command.

### Current Implementation Status

| Component | Status | Details |
|-----------|--------|---------|
| **ArkhamFrame** | Complete | 16 services, production-ready |
| **Shards** | 25 implemented | All production manifest compliant |
| **Test Coverage** | 1,469+ tests | Comprehensive coverage |
| **UI Shell** | Complete | React + TypeScript + Vite |

### Goals

- **Modular deployment**: Users run only the Shards they need
- **One-command deployment**: `docker compose up -d`
- **Bundle-based selection**: Pre-configured shard combinations for specific use cases
- **Production-grade security**: VPN, firewall, encrypted secrets
- **Privacy-first**: All data stays in user-controlled infrastructure
- **Local-first**: Works offline, data never leaves the machine unless requested

### Non-Goals (This Phase)

- Lite mode containers (SQLite/ChromaDB) - future expansion
- Team mode (remote shared services) - future expansion
- GPU-accelerated containers - future expansion
- LLM bundled in container - external LM Studio required

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Requirements](#2-system-requirements)
3. [Shard & Bundle Selection](#3-shard--bundle-selection)
4. [Building the Container](#4-building-the-container)
5. [Publishing to Container Registries](#5-publishing-to-container-registries)
6. [Deployment Paths](#6-deployment-paths)
7. [VPS Provider Guide](#7-vps-provider-guide)
8. [Security Hardening](#8-security-hardening)
9. [Operations & Maintenance](#9-operations--maintenance)
10. [Troubleshooting](#10-troubleshooting)
11. [Future Enhancements](#11-future-enhancements)
12. [Quick Reference](#12-quick-reference)

---

## 1. Architecture Overview

### 1.1 The SHATTERED Architecture

SHATTERED follows the **Voltron** architectural philosophy - a modular, plug-and-play system:

```
+------------------------------------------------------------------+
|                         SHATTERED                                 |
+------------------------------------------------------------------+
|                                                                  |
|  +------------------------------------------------------------+  |
|  |                   FRAME (arkham-frame)                     |  |
|  |  Immutable core providing 16 infrastructure services        |  |
|  |                                                            |  |
|  |  Foundation:                                               |  |
|  |  - ConfigService (env + YAML)    - ResourceService (GPU/CPU)|  |
|  |  - StorageService (files/blobs)  - DatabaseService (Postgres)|  |
|  |                                                            |  |
|  |  Data:                                                     |  |
|  |  - VectorService (Qdrant)        - LLMService (LM Studio)  |  |
|  |  - ChunkService (8 strategies)   - EventBus (pub/sub)      |  |
|  |  - WorkerService (14 pools)      - DocumentService         |  |
|  |  - EntityService                 - ProjectService          |  |
|  |                                                            |  |
|  |  Output:                                                   |  |
|  |  - ExportService (JSON/CSV/PDF)  - TemplateService (Jinja2)|  |
|  |  - NotificationService           - SchedulerService        |  |
|  +------------------------------------------------------------+  |
|         |              |              |              |           |
|         v              v              v              v           |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|  |  SHARD:   |  |  SHARD:   |  |  SHARD:   |  |  SHARD:   |     |
|  | Dashboard |  |    ACH    |  |  Search   |  |Contradict |     |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|                                                                  |
|  Each shard has:                                                 |
|  - Own database schema (arkham_{shard})                          |
|  - Own FastAPI routes (/api/{shard}/*)                           |
|  - Own shard.yaml manifest (per shard_manifest_schema_prod.md)   |
|  - Optional workers registered to Frame pools                    |
|  - Event emission and subscription via EventBus                  |
|                                                                  |
+------------------------------------------------------------------+
```

**Core Principles:**

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards communicate via events, not imports
3. **Schema Isolation**: Each shard gets its own PostgreSQL schema (`arkham_{shard}`)
4. **Graceful Degradation**: Works with or without AI/GPU capabilities

### 1.2 The Meta-Pattern

All workflows follow the same fundamental flow:

```
INGEST → EXTRACT → ORGANIZE → ANALYZE → ACT
  │         │          │          │        │
  │         │          │          │        └── Export, Generate, Notify
  │         │          │          └── ACH, Contradictions, Patterns
  │         │          └── Timeline, Graph, Matrix, Inventory
  │         └── Entities, Claims, Events, Relationships
  └── Documents, Data, Communications, Records
```

- **Core shards** handle INGEST and EXTRACT
- **Domain shards** handle ORGANIZE and ANALYZE
- **Output shards** handle ACT

### 1.3 Container Architecture

Shattered KANDOR packages the Frame + selected Shards into a single deployable container:

```
+------------------------------------------------------------------------+
|                      Shattered KANDOR Stack                             |
|                    docker-compose.prod.yml                              |
+------------------------------------------------------------------------+
|                                                                        |
|  +------------------------------------------------------------------+  |
|  |              shattered-app (Main Application Container)          |  |
|  |                                                                  |  |
|  |  +------------------------+  +-----------------------------+     |  |
|  |  |      FastAPI Server    |  |      React Frontend         |     |  |
|  |  |       (Backend)        |  |    (Served as static)       |     |  |
|  |  +------------------------+  +-----------------------------+     |  |
|  |  | Frame API endpoints    |  | Shell (routing, sidebar)    |     |  |
|  |  | Shard API endpoints    |  | Shard pages & components    |     |  |
|  |  | WebSocket server       |  | Real-time updates (WS)      |     |  |
|  |  | Static file serving    |  |                             |     |  |
|  |  +------------------------+  +-----------------------------+     |  |
|  |                                                                  |  |
|  |  +------------------------------------------------------------+  |  |
|  |  |                    Workers (14 Pool Types)                 |  |  |
|  |  | IO: io-file, io-db                                         |  |  |
|  |  | CPU: cpu-light, cpu-heavy, cpu-ner, cpu-extract,           |  |  |
|  |  |      cpu-image, cpu-archive                                |  |  |
|  |  | GPU: gpu-paddle, gpu-qwen, gpu-whisper, gpu-embed          |  |  |
|  |  | LLM: llm-enrich, llm-analysis                              |  |  |
|  |  +------------------------------------------------------------+  |  |
|  |                                                                  |  |
|  |  Configured by: /config/shattered.yaml (mounted volume)         |  |
|  +------------------------------------------------------------------+  |
|         |                    |                    |                    |
|         v                    v                    v                    |
|  +----------------+  +----------------+  +------------------------+    |
|  |   PostgreSQL   |  |    Qdrant      |  |         Redis          |    |
|  |     :5435      |  |     :6343      |  |         :6380          |    |
|  |   (internal)   |  |   (internal)   |  |       (internal)       |    |
|  +----------------+  +----------------+  +------------------------+    |
|                                                                        |
|  Volumes:                                                              |
|  - shattered_postgres_data   (Frame + Shard schemas)                   |
|  - shattered_qdrant_data     (vector embeddings)                       |
|  - shattered_redis_data      (job queue)                               |
|  - shattered_datasilo        (documents, exports, temp, models)        |
|  - ./config/shattered.yaml   (shard configuration - bind mount)        |
|                                                                        |
+------------------------------------------------------------------------+
         |
         | Exposed Ports
         v
    8100 (Frame API)
    3100 (Shell UI)
```

### 1.4 Component Summary

| Component | Purpose | Image/Package | Port |
|-----------|---------|---------------|------|
| **App** | FastAPI backend + React frontend + Workers | `ghcr.io/mantisfury/shattered-kandor` | 8100, 3100 |
| **PostgreSQL** | Frame schema + Shard schemas | `postgres:15-alpine` | Internal (5435) |
| **Qdrant** | Vector embeddings for semantic search | `qdrant/qdrant:latest` | Internal (6343) |
| **Redis** | Task queue for async processing | `redis:7-alpine` | Internal (6380) |

### 1.5 Frame Services (16 Total)

| Service | Attribute | Description |
|---------|-----------|-------------|
| **ConfigService** | `frame.config` | Environment + YAML configuration |
| **ResourceService** | `frame.resources` | Hardware detection, GPU/CPU management, tier assignment |
| **StorageService** | `frame.storage` | File/blob storage with categories |
| **DatabaseService** | `frame.db` | PostgreSQL with schema isolation per shard |
| **VectorService** | `frame.vectors` | Qdrant vector store (3 standard collections) |
| **LLMService** | `frame.llm` | OpenAI-compatible LLM (streaming, structured output) |
| **ChunkService** | `frame.chunks` | 8 chunking strategies with tiktoken |
| **EventBus** | `frame.events` | Pub/sub with wildcards and history |
| **WorkerService** | `frame.workers` | Redis job queues (14 pools) |
| **DocumentService** | `frame.documents` | Document CRUD with content access |
| **EntityService** | `frame.entities` | Entity extraction and relationships |
| **ProjectService** | `frame.projects` | Project CRUD with settings |
| **ExportService** | (via API) | Multi-format export (JSON, CSV, PDF, DOCX, HTML) |
| **TemplateService** | (via API) | Jinja2 template management |
| **NotificationService** | (via API) | Email/Webhook/Log notifications |
| **SchedulerService** | (via API) | APScheduler job scheduling |

### 1.6 Worker Pools (14 Total)

| Category | Pool | Max Workers | Use Case |
|----------|------|-------------|----------|
| **IO** | `io-file` | 20 | File read/write operations |
| **IO** | `io-db` | 10 | Database-heavy operations |
| **CPU** | `cpu-light` | 50 | Quick CPU tasks |
| **CPU** | `cpu-heavy` | 6 | Intensive CPU tasks |
| **CPU** | `cpu-ner` | 8 | NER processing |
| **CPU** | `cpu-extract` | 4 | Text extraction |
| **CPU** | `cpu-image` | 4 | Image processing |
| **CPU** | `cpu-archive` | 2 | Archive handling |
| **GPU** | `gpu-paddle` | 1 (2GB VRAM) | PaddleOCR |
| **GPU** | `gpu-qwen` | 1 (8GB VRAM) | Qwen vision |
| **GPU** | `gpu-whisper` | 1 (4GB VRAM) | Audio transcription |
| **GPU** | `gpu-embed` | 1 (2GB VRAM) | Embeddings |
| **LLM** | `llm-enrich` | 4 | Document enrichment |
| **LLM** | `llm-analysis` | 2 | Deep analysis |

### 1.7 Database Schema Architecture

PostgreSQL uses schema isolation for Frame and each Shard:

```sql
-- Frame's schema (managed by Frame)
CREATE SCHEMA arkham_frame;
-- Tables: documents, chunks, pages, projects, entities,
--         canonical_entities, entity_relationships

-- Each shard gets isolated schema
CREATE SCHEMA arkham_dashboard;
CREATE SCHEMA arkham_ach;
CREATE SCHEMA arkham_search;
CREATE SCHEMA arkham_contradictions;
CREATE SCHEMA arkham_anomalies;
CREATE SCHEMA arkham_graph;
CREATE SCHEMA arkham_timeline;
-- ... etc

-- Shards reference Frame tables by ID only (soft references, no FK constraints)
```

### 1.8 Network Security Model

- **Internal Network**: All containers communicate via `shattered-network` bridge
- **External Access**: Only ports 8100 (API) and 3100 (UI) exposed
- **Database Isolation**: PostgreSQL, Qdrant, Redis have no external port bindings
- **LLM Connection**: App connects outbound to LM Studio (host machine or remote)
- **Inter-Shard**: Communication via Frame's EventBus only (no direct shard-to-shard)

---

## 2. System Requirements

### 2.1 Hardware Requirements

| Resource | Minimum | Recommended | Power | Notes |
|----------|---------|-------------|-------|-------|
| **vCPU** | 2 cores | 4 cores | 8+ cores | Workers are CPU-intensive |
| **RAM** | 8 GB | 16 GB | 32+ GB | BGE-M3 embeddings use ~2.2GB |
| **GPU VRAM** | None | 6 GB | 12+ GB | Optional, for OCR/embeddings |
| **Storage** | 20 GB | 50 GB | 100+ GB | NVMe/SSD strongly recommended |
| **Network** | 100 Mbps | 1 Gbps | 10 Gbps | For image pulls and LLM traffic |

### 2.2 Resource Tiers

The Frame's ResourceService automatically detects hardware and assigns a tier:

| Tier | RAM | GPU VRAM | CPU Threads | Use Case |
|------|-----|----------|-------------|----------|
| **minimal** | < 8 GB | None | < 4 | Basic operation, limited concurrency |
| **standard** | 8-16 GB | < 6 GB | 4-8 | Normal use, some GPU pools disabled |
| **recommended** | 16-32 GB | 6-12 GB | 8-16 | Full features, all pools available |
| **power** | 32+ GB | 12+ GB | 16+ | Maximum concurrency, all features |

### 2.3 Software Requirements

| Software | Version | Notes |
|----------|---------|-------|
| **OS** | Ubuntu 22.04+ / Debian 12+ | Any Linux with Docker support |
| **Docker** | 24.0+ | With Docker Compose V2 |
| **LM Studio** | Latest | Running on host or accessible remotely |

### 2.4 Per-Component Resource Usage

| Component | RAM Usage | Storage |
|-----------|-----------|---------|
| **App Container** | 2-4 GB | ~6 GB (image) |
| **PostgreSQL** | 256-512 MB | Variable (schemas) |
| **Qdrant** | 512 MB - 2 GB | Variable (vectors) |
| **Redis** | 64-256 MB | Minimal |
| **Total Base** | ~4-6 GB | ~8 GB |

---

## 3. Shard & Bundle Selection

### 3.1 Implemented Shards (25 Total)

#### System Category (order 0-9)
| Shard | Description | Order |
|-------|-------------|-------|
| `dashboard` | System monitoring, LLM config, worker management | 0 |
| `projects` | Project workspace management | 2 |
| `settings` | Application settings, user preferences | 5 |

#### Data Category (order 10-19)
| Shard | Description | Order |
|-------|-------------|-------|
| `ingest` | Document upload, file classification, batch processing | 10 |
| `ocr` | OCR processing with PaddleOCR and Qwen-VL | 11 |
| `parse` | Named Entity Recognition, relationship extraction | 12 |
| `documents` | Document browser with viewer, metadata editor | 13 |
| `entities` | Entity browser with merge/link/edit | 14 |

#### Search Category (order 20-29)
| Shard | Description | Order |
|-------|-------------|-------|
| `search` | Semantic + keyword hybrid search with RRF | 20 |
| `embed` | Document embedding generation, similarity search | 25 |

#### Analysis Category (order 30-39)
| Shard | Description | Order |
|-------|-------------|-------|
| `ach` | Analysis of Competing Hypotheses | 30 |
| `claims` | Claim extraction and tracking | 31 |
| `provenance` | Evidence chain tracking, audit trails | 32 |
| `credibility` | Source credibility assessment | 33 |
| `contradictions` | Multi-document contradiction detection | 35 |
| `patterns` | Cross-document pattern detection | 36 |
| `anomalies` | Anomaly detection in documents | 37 |
| `summary` | AI-powered summarization | 39 |

#### Visualize Category (order 40-49)
| Shard | Description | Order |
|-------|-------------|-------|
| `graph` | Entity relationship visualization, graph algorithms | 40 |
| `timeline` | Temporal event extraction, timeline construction | 45 |

#### Export Category (order 50-59)
| Shard | Description | Order |
|-------|-------------|-------|
| `export` | Data export (JSON, CSV, PDF, DOCX) | 50 |
| `letters` | Formal letter generation (FOIA, complaints) | 52 |
| `templates` | Template management UI | 54 |
| `reports` | Analytical report generation | 55 |
| `packets` | Investigation packet bundling | 58 |

### 3.2 Bundle Configurations

Bundles are pre-configured shard combinations for specific use cases:

#### Core Bundles

| Bundle | Shards | Use Case |
|--------|--------|----------|
| **minimal** | dashboard | Base system only |
| **standard** | dashboard, ingest, parse, search, documents | Basic document processing |
| **analysis** | standard + ach, contradictions, timeline, graph | Intelligence analysis |
| **full** | All 25 shards | Complete installation |

#### Domain Bundles (from SHARDS_AND_BUNDLES.md)

| Bundle | Shards | Target User |
|--------|--------|-------------|
| **journalist** | ingest, parse, search, entities, timeline, contradictions, graph, export | Journalists & Investigators |
| **legal** | ingest, parse, search, timeline, letters, evidence-packet, export | Legal self-advocacy |
| **research** | ingest, parse, search, ach, claims, citations, summary, export | Academics & Researchers |
| **civic** | ingest, parse, search, entities, timeline, graph, patterns, export | Civic engagement |

### 3.3 Configuration File

Shard selection is controlled by `shattered.yaml`:

```yaml
# shattered.yaml - Shard Configuration
# Mount to /config/shattered.yaml in the container

# Frame version compatibility
frame_version: "0.1.0"

# Enabled shards (dashboard always required)
shards:
  # System (required)
  dashboard: true
  projects: true
  settings: true

  # Data
  ingest: true
  ocr: true
  parse: true
  documents: true
  entities: true

  # Search
  search: true
  embed: true

  # Analysis
  ach: true
  claims: false
  provenance: false
  credibility: false
  contradictions: true
  patterns: false
  anomalies: true
  summary: false

  # Visualize
  graph: true
  timeline: true

  # Export
  export: true
  letters: false
  templates: true
  reports: true
  packets: false

# Frame configuration
frame:
  # Resource tier (auto-detected if not specified)
  # tier: standard  # minimal|standard|recommended|power

  # Worker pool overrides
  workers:
    # disabled_pools:
    #   - gpu-qwen  # Disable if VRAM insufficient

  # LLM (if not using LM_STUDIO_URL env var)
  llm:
    provider: lm_studio
    timeout: 120

  # Logging
  logging:
    level: INFO
    format: structured
```

### 3.4 Pre-Built Image Tags

| Tag | Shards Included |
|-----|-----------------|
| `latest` | Full build with all 25 shards |
| `minimal` | Dashboard only |
| `standard` | Core document processing (9 shards) |
| `analysis` | Standard + analysis tools (15 shards) |
| `full` | All 25 shards |
| `journalist` | Journalist bundle |
| `legal` | Legal self-advocacy bundle |
| `research` | Academic research bundle |
| `YYYYMMDD` | Date-stamped builds |
| `vX.Y.Z` | Semantic version releases |

---

## 4. Building the Container

### 4.1 Repository Structure

```
SHATTERED/
├── README.md
├── CLAUDE.md                      # Project guidelines
├── SHARDS_AND_BUNDLES.md          # Bundle definitions
├── full_frame_plan.md             # Frame implementation
├── Dockerfile                     # Multi-stage build
├── docker-compose.prod.yml        # Production compose
├── shattered.yaml.example         # Example config
│
├── packages/
│   ├── arkham-frame/              # The Frame (core)
│   │   ├── pyproject.toml
│   │   ├── arkham_frame/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # FastAPI app
│   │   │   ├── frame.py           # ArkhamFrame class
│   │   │   ├── shard_interface.py # ArkhamShard ABC
│   │   │   ├── api/               # REST endpoints
│   │   │   ├── services/          # 16 services
│   │   │   ├── pipeline/          # Processing pipeline
│   │   │   └── workers/           # Worker infrastructure
│   │   └── tests/
│   │
│   ├── arkham-shard-shell/        # React UI shell
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── src/
│   │
│   ├── arkham-shard-dashboard/
│   │   ├── pyproject.toml
│   │   ├── shard.yaml             # Production manifest
│   │   └── arkham_shard_dashboard/
│   │       ├── __init__.py
│   │       ├── shard.py
│   │       └── api.py
│   │
│   ├── arkham-shard-ach/          # Reference implementation
│   ├── arkham-shard-ingest/
│   ├── arkham-shard-ocr/
│   ├── arkham-shard-parse/
│   ├── arkham-shard-search/
│   ├── arkham-shard-embed/
│   ├── arkham-shard-contradictions/
│   ├── arkham-shard-anomalies/
│   ├── arkham-shard-graph/
│   ├── arkham-shard-timeline/
│   └── ... (other shards)
│
└── docs/
    ├── voltron_plan.md
    ├── frame_spec.md
    ├── shard_manifest_schema_prod.md
    └── WORKER_ARCHITECTURE.md
```

### 4.2 Dockerfile (Multi-Stage Build)

```dockerfile
# =============================================================================
# Shattered KANDOR: Multi-Stage Dockerfile
# Builds Frame + All Shards into a single deployable container
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Frontend Build (React Shell)
# -----------------------------------------------------------------------------
FROM node:18-alpine AS frontend-builder

WORKDIR /build

# Copy package files
COPY packages/arkham-shard-shell/package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY packages/arkham-shard-shell/ ./

# Build
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Python Backend Build
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS backend-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Install Frame
COPY packages/arkham-frame/pyproject.toml ./packages/arkham-frame/
COPY packages/arkham-frame/arkham_frame/ ./packages/arkham-frame/arkham_frame/
RUN pip install --no-cache-dir --upgrade pip wheel setuptools
RUN pip install --no-cache-dir ./packages/arkham-frame

# Install all Shards
COPY packages/arkham-shard-*/pyproject.toml ./packages/
COPY packages/arkham-shard-*/arkham_shard_*/ ./packages/
RUN for shard_dir in ./packages/arkham-shard-*/; do \
      if [ -f "$shard_dir/pyproject.toml" ]; then \
        pip install --no-cache-dir "$shard_dir" || true; \
      fi \
    done

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# -----------------------------------------------------------------------------
# Stage 3: Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/mantisfury/SHATTERED"
LABEL org.opencontainers.image.description="SHATTERED - Modular Document Analysis Platform"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="Shattered KANDOR"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Copy shard manifests (needed for discovery)
COPY packages/arkham-shard-*/shard.yaml /app/packages/

WORKDIR /app

# Create directories
RUN mkdir -p /app/DataSilo/documents \
             /app/DataSilo/exports \
             /app/DataSilo/temp \
             /app/DataSilo/models \
             /app/config

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8100/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

### 4.3 Docker Compose (Production)

```yaml
# docker-compose.prod.yml
name: shattered-kandor

services:
  # ---------------------------------------------------------------------------
  # Main Application
  # ---------------------------------------------------------------------------
  app:
    image: ghcr.io/mantisfury/shattered-kandor:latest
    container_name: shattered-app
    restart: unless-stopped
    ports:
      - "${APP_PORT:-8100}:8100"
      - "${UI_PORT:-3100}:3100"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-arkham}:${POSTGRES_PASSWORD:-arkhampass}@postgres:5435/${POSTGRES_DB:-arkhamdb}
      - QDRANT_URL=http://qdrant:6343
      - REDIS_URL=redis://redis:6380
      - LM_STUDIO_URL=${LM_STUDIO_URL:-http://host.docker.internal:1234/v1}
      - CONFIG_FILE=/config/shattered.yaml
    volumes:
      - ./config/shattered.yaml:/config/shattered.yaml:ro
      - datasilo:/app/DataSilo
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - shattered-net
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # ---------------------------------------------------------------------------
  # PostgreSQL
  # ---------------------------------------------------------------------------
  postgres:
    image: postgres:15-alpine
    container_name: shattered-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-arkham}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-arkhampass}
      - POSTGRES_DB=${POSTGRES_DB:-arkhamdb}
    command: -p 5435
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-arkham} -d ${POSTGRES_DB:-arkhamdb} -p 5435"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - shattered-net

  # ---------------------------------------------------------------------------
  # Qdrant
  # ---------------------------------------------------------------------------
  qdrant:
    image: qdrant/qdrant:latest
    container_name: shattered-qdrant
    restart: unless-stopped
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6343
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6343/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - shattered-net

  # ---------------------------------------------------------------------------
  # Redis
  # ---------------------------------------------------------------------------
  redis:
    image: redis:7-alpine
    container_name: shattered-redis
    restart: unless-stopped
    command: redis-server --port 6380 --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6380", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - shattered-net

volumes:
  postgres_data:
    name: shattered_postgres_data
  qdrant_data:
    name: shattered_qdrant_data
  redis_data:
    name: shattered_redis_data
  datasilo:
    name: shattered_datasilo

networks:
  shattered-net:
    name: shattered-network
    driver: bridge
```

### 4.4 Build Commands

```bash
# Clone repository
git clone https://github.com/mantisfury/SHATTERED.git
cd SHATTERED

# Build locally
docker build -t shattered-kandor:local .

# Build with specific tag
docker build -t shattered-kandor:$(date +%Y%m%d) .

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/mantisfury/shattered-kandor:latest \
  --push .
```

---

## 5. Publishing to Container Registries

### 5.1 GitHub Container Registry

```bash
# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u mantisfury --password-stdin

# Tag and push
docker tag shattered-kandor:local ghcr.io/mantisfury/shattered-kandor:latest
docker push ghcr.io/mantisfury/shattered-kandor:latest
```

### 5.2 GitHub Actions CI/CD

```yaml
# .github/workflows/build.yml
name: Build Shattered KANDOR

on:
  push:
    branches: [main]
    tags: ['v*']
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: mantisfury/shattered-kandor

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=tag
            type=sha,prefix=
            type=raw,value=latest,enable={{is_default_branch}}

      - uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

---

## 6. Deployment Paths

### 6.1 Quick Deploy (10 minutes)

For evaluation, development, personal use on trusted networks:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Create directory
mkdir -p ~/shattered/config && cd ~/shattered

# Download compose file
curl -O https://raw.githubusercontent.com/mantisfury/SHATTERED/main/docker-compose.prod.yml

# Create config
cat > config/shattered.yaml << 'EOF'
frame_version: "0.1.0"
shards:
  dashboard: true
  ingest: true
  parse: true
  search: true
  ach: true
EOF

# Start
docker compose -f docker-compose.prod.yml up -d

# Access at http://localhost:8100 (API) / http://localhost:3100 (UI)
```

### 6.2 Production Hardened Deploy

For journalists, investigators, handling sensitive documents:

```
Step 1: Provision VPS (Section 7)
    ↓
Step 2: Configure VPN - WireGuard or Tailscale (Section 8.1)
    ↓
Step 3: Harden Server - UFW, SSH, fail2ban (Section 8.2-8.4)
    ↓
Step 4: Configure Shard Selection (config/shattered.yaml)
    ↓
Step 5: Deploy via Docker Compose
    ↓
Step 6: Configure Backups (Section 9)
```

---

## 7. VPS Provider Guide

### 7.1 Provider Comparison

| Provider | Plan | vCPU | RAM | Storage | Monthly Cost | Best For |
|----------|------|------|-----|---------|--------------|----------|
| **Hostinger** | KVM 4 | 4 | 16 GB | 200 GB NVMe | $10.49 | Budget-friendly |
| **Hetzner** | CPX31 | 4 | 8 GB | 160 GB | ~$15 | European hosting |
| **Vultr** | Cloud Compute | 4 | 16 GB | 100 GB SSD | $80 | Good performance |
| **DigitalOcean** | General Purpose | 4 | 16 GB | 100 GB | $96 | Developer-friendly |

### 7.2 Recommended: Hostinger KVM 4 or Hetzner CPX31

- 4 vCPU handles document processing
- 16 GB RAM (or 8 GB for light use) accommodates embeddings
- NVMe storage for fast I/O

---

## 8. Security Hardening

### 8.1 VPN Options

**Option A: Tailscale (Easiest)**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
# Access via Tailscale IP: http://100.x.x.x:8100
```

**Option B: WireGuard (Best Performance)**
```bash
sudo apt install -y wireguard
# Configure as per original document
```

**Option C: Cloudflare Tunnel (Zero Trust)**
```bash
# Configure cloudflared for public access with auth
```

### 8.2 Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 51820/udp  # WireGuard
sudo ufw allow from 10.200.200.0/24 to any port 22  # SSH via VPN
sudo ufw allow from 10.200.200.0/24 to any port 8100  # API via VPN
sudo ufw allow from 10.200.200.0/24 to any port 3100  # UI via VPN
sudo ufw enable
```

### 8.3 SSH Hardening

```bash
sudo tee /etc/ssh/sshd_config.d/hardening.conf << EOF
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
MaxAuthTries 3
EOF
sudo systemctl restart sshd
```

---

## 9. Operations & Maintenance

### 9.1 Health Check

```bash
# Container status
docker compose -f docker-compose.prod.yml ps

# Application health
curl http://localhost:8100/api/health | jq

# Enabled shards
curl http://localhost:8100/api/shards | jq '.shards[].name'
```

### 9.2 Backup

```bash
#!/bin/bash
# backup_shattered.sh
BACKUP_DIR="/home/shattered/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# PostgreSQL
docker exec shattered-postgres pg_dumpall -U arkham -p 5435 > "$BACKUP_DIR/postgres_$DATE.sql"

# DataSilo
docker run --rm -v shattered_datasilo:/data -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/datasilo_$DATE.tar.gz -C /data .

# Config
cp ~/shattered/config/shattered.yaml "$BACKUP_DIR/config_$DATE.yaml"

# Cleanup (keep 7 days)
find $BACKUP_DIR -type f -mtime +7 -delete
```

### 9.3 Updates

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker image prune -f
```

### 9.4 Changing Shards

```bash
# Edit config
nano ~/shattered/config/shattered.yaml

# Restart app (migrations run automatically)
docker compose -f docker-compose.prod.yml restart app

# Verify
curl http://localhost:8100/api/shards | jq '.shards[].name'
```

---

## 10. Troubleshooting

### Container Won't Start
```bash
docker compose -f docker-compose.prod.yml logs app
# Check: config file exists, memory available, port conflicts
```

### Database Connection Failed
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U arkham -p 5435 -d arkhamdb -c "SELECT 1;"
docker compose -f docker-compose.prod.yml exec postgres psql -U arkham -p 5435 -d arkhamdb -c "\dn"
```

### LLM Connection Failed
```bash
curl http://localhost:1234/v1/models
# For Linux Docker, may need host IP instead of host.docker.internal
```

### Reset Everything
```bash
docker compose -f docker-compose.prod.yml down -v
docker rmi ghcr.io/mantisfury/shattered-kandor:latest
docker compose -f docker-compose.prod.yml up -d
```

---

## 11. Future Enhancements

### 11.1 Planned Shards (33 more from roadmap)

See [SHARDS_AND_BUNDLES.md](SHARDS_AND_BUNDLES.md) for the complete 58-shard inventory:

- **Domain Bridges**: public-records, regulatory-database, financial-data, news-archive
- **Document Specialists**: contract-parser, medical-record-parser, email-parser
- **Analysis Specialists**: benford-analyzer, network-analyzer, geospatial
- **Collaboration**: annotation, tagging, workflow-manager, audit-trail

### 11.2 Lite Mode Containers

Future variant using SQLite + ChromaDB instead of PostgreSQL + Qdrant.

### 11.3 Team Mode

Future variant with shared remote services for collaborative analysis.

### 11.4 GPU Container Variant

NVIDIA CUDA container for GPU-accelerated OCR and embeddings.

---

## 12. Quick Reference

### Essential Commands

```bash
# Start
docker compose -f docker-compose.prod.yml up -d

# Stop
docker compose -f docker-compose.prod.yml down

# Status
docker compose -f docker-compose.prod.yml ps

# Logs
docker compose -f docker-compose.prod.yml logs -f app

# Shell
docker compose -f docker-compose.prod.yml exec app bash

# Update
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d
```

### URLs

| Service | URL |
|---------|-----|
| Frame API | http://localhost:8100 |
| Shell UI | http://localhost:3100 |
| API Docs | http://localhost:8100/docs |
| Health | http://localhost:8100/api/health |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `arkham` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `arkhampass` | PostgreSQL password |
| `POSTGRES_DB` | `arkhamdb` | PostgreSQL database |
| `LM_STUDIO_URL` | `http://host.docker.internal:1234/v1` | LLM endpoint |
| `APP_PORT` | `8100` | API port |
| `UI_PORT` | `3100` | UI port |

### Volumes

| Volume | Purpose |
|--------|---------|
| `shattered_postgres_data` | Frame + Shard schemas |
| `shattered_qdrant_data` | Vector embeddings |
| `shattered_redis_data` | Job queue |
| `shattered_datasilo` | Documents, exports, temp |

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-12-26 | Updated for current SHATTERED architecture (25 shards, 16 services) |
| 1.0 | 2025-12-18 | Initial draft |

---

**Document Version**: 2.0
**Based On**: Current SHATTERED implementation, SHARDS_AND_BUNDLES.md, full_frame_plan.md
**Status**: Ready for Implementation
