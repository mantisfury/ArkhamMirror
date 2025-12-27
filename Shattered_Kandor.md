# Shattered KANDOR: ArkhamMirror Shattered Cloud Deployment Plan

> *"Even a shard can show you truth - now in the cloud."*

## Executive Summary

**Shattered KANDOR** is the containerized, cloud-deployable distribution of ArkhamMirror Shattered - the modular, extensible rewrite of ArkhamMirror based on the Frame + Shards architecture (Project Voltron).

This document provides a complete roadmap for building, publishing, and deploying ArkhamMirror Shattered as a prepackaged Docker solution. Users select which Shards (feature modules) they want, then deploy to any cloud VPS with a single command.

### Relationship to Other Projects

| Project | Description | Status |
|---------|-------------|--------|
| **ArkhamMirror (Monolith)** | Original Reflex-based unified application | Existing |
| **ArkhamMirror Shattered (Voltron)** | Modular Frame + Shards rewrite (FastAPI + React) | Planning |
| **KANDOR (Monolith)** | Containerized deployment of the Monolith | Planning |
| **Shattered KANDOR** | Containerized deployment of Shattered | **This Document** |

### Goals

- **Modular deployment**: Users run only the Shards they need
- **One-command deployment**: `docker compose up -d`
- **Linux distro style selection**: Choose your shards, then build
- **Production-grade security**: VPN, firewall, encrypted secrets
- **Privacy-first**: All data stays in user-controlled infrastructure

### Non-Goals (This Phase)

- Lite mode containers (SQLite/ChromaDB) - future expansion
- Team mode (remote shared services) - future expansion
- GPU-accelerated containers - future expansion
- LLM bundled in container - pending infrastructure decisions

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Requirements](#2-system-requirements)
3. [Shard Selection](#3-shard-selection)
4. [Building the Container](#4-building-the-container)
5. [Publishing to Container Registries](#5-publishing-to-container-registries)
6. [Deployment Paths](#6-deployment-paths)
7. [VPS Provider Guide](#7-vps-provider-guide)
8. [Security Hardening](#8-security-hardening)
9. [Operations & Maintenance](#9-operations--maintenance)
10. [Troubleshooting](#10-troubleshooting)
11. [Future Enhancements](#11-future-enhancements)
12. [Quick Reference](#12-quick-reference)
13. [Appendices](#13-appendices)

---

## 1. Architecture Overview

### 1.1 The Shattered Architecture

ArkhamMirror Shattered transforms the monolithic application into a modular framework:

```
+------------------------------------------------------------------+
|                    ArkhamMirror Shattered                         |
+------------------------------------------------------------------+
|                                                                  |
|  +------------------------------------------------------------+  |
|  |                     FRAME (arkham-frame)                   |  |
|  |  Headless core providing infrastructure services           |  |
|  |                                                            |  |
|  |  - Database connectivity (PostgreSQL)                      |  |
|  |  - Vector operations (Qdrant)                              |  |
|  |  - Job queue (Redis)                                       |  |
|  |  - LLM abstraction                                         |  |
|  |  - Event bus                                               |  |
|  |  - Worker management                                       |  |
|  |  - Document pipeline (ingest, OCR, parse, embed)           |  |
|  |  - Shard registry & lifecycle                              |  |
|  +------------------------------------------------------------+  |
|         |              |              |              |           |
|         v              v              v              v           |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|  |  SHARD:   |  |  SHARD:   |  |  SHARD:   |  |  SHARD:   |     |
|  | Dashboard |  |    ACH    |  |  Search   |  | Contradict|     |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|  | - Status  |  | - Heuer's |  | - Semantic|  | - Detect  |     |
|  | - Health  |  |   8-step  |  | - Filters |  | - Chains  |     |
|  | - Metrics |  | - Matrix  |  | - Export  |  | - Compare |     |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|                                                                  |
|  Each shard has:                                                 |
|  - Own database schema (arkham_{shard})                          |
|  - Own FastAPI routes (/api/{shard}/*)                           |
|  - Own React pages and components                                |
|  - Optional workers                                              |
|  - Event emission and subscription                               |
|                                                                  |
+------------------------------------------------------------------+
```

**Key Principles:**

1. **Frame is infrastructure** - provides services but makes no analytical decisions
2. **Shards are features** - self-contained modules that use Frame services
3. **Shards are independent** - each works with only Frame installed
4. **Shards communicate via events** - optional enhancements, not requirements

### 1.2 Container Architecture

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
|  |  |                    RQ Workers (Background)                 |  |  |
|  |  | ingest | splitter | ocr | parser | embed | cluster | event |  |  |
|  |  +------------------------------------------------------------+  |  |
|  |                                                                  |  |
|  |  Configured by: /config/shattered.yaml (mounted volume)         |  |
|  +------------------------------------------------------------------+  |
|         |                    |                    |                    |
|         | depends_on         |                    |                    |
|         v                    v                    v                    |
|  +----------------+  +----------------+  +------------------------+    |
|  |   PostgreSQL   |  |    Qdrant      |  |         Redis          |    |
|  |     :5432      |  |     :6333      |  |         :6379          |    |
|  |   (internal)   |  |   (internal)   |  |       (internal)       |    |
|  +----------------+  +----------------+  +------------------------+    |
|                                                                        |
|  Volumes:                                                              |
|  - shattered_postgres_data   (Frame + Shard schemas)                   |
|  - shattered_qdrant_data     (vector embeddings)                       |
|  - shattered_redis_data      (job queue)                               |
|  - shattered_datasilo        (documents, pages, logs)                  |
|  - ./config/shattered.yaml   (shard configuration - bind mount)        |
|                                                                        |
+------------------------------------------------------------------------+
         |
         | Exposed Port
         v
    3000 (App - Frontend + API at /api)
```

### 1.3 Component Summary

| Component | Purpose | Image/Package | Port |
|-----------|---------|---------------|------|
| **App** | FastAPI backend + React frontend + RQ workers | `ghcr.io/mantisfury/shattered-kandor` | 3000 |
| **PostgreSQL** | Frame schema + Shard schemas | `postgres:15-alpine` | Internal (5432) |
| **Qdrant** | Vector embeddings for semantic search | `qdrant/qdrant:latest` | Internal (6333) |
| **Redis** | Task queue for async processing | `redis:7-alpine` | Internal (6379) |

### 1.4 Technology Stack

| Layer | Monolith KANDOR | Shattered KANDOR |
|-------|-----------------|------------------|
| **Frontend Framework** | Reflex (generates Next.js) | React 18 + React Router |
| **Backend Framework** | Reflex (wraps FastAPI) | Pure FastAPI |
| **Build System** | Reflex CLI | Turborepo + Vite + pnpm |
| **Package Structure** | Single Python package | Monorepo (Frame + Shards) |
| **Database Schema** | Single schema | `arkham_frame` + `arkham_{shard}` |
| **State Management** | Reflex state classes | React hooks + Zustand |
| **Real-time Updates** | Reflex WebSockets | FastAPI WebSockets |

### 1.5 Data Flow

```
Document Upload
      |
      v
+---------------------+
| Frame: Ingest Queue |  (Redis)
+---------------------+
      |
      v
+---------------------+     +---------------------+
| Frame: Splitter     | --> | Frame: OCR Worker   |
| (PDF/DOCX pages)    |     | (PaddleOCR/Qwen-VL) |
+---------------------+     +---------------------+
                                    |
                                    v
                            +---------------------+
                            | Frame: Parser       |
                            | (SpaCy NER)         |
                            +---------------------+
                                    |
                                    v
                            +---------------------+
                            | Frame: Embed        |
                            | (BGE-M3/MiniLM)     |
                            +---------------------+
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
        v                           v                           v
+---------------+           +---------------+           +---------------+
| PostgreSQL    |           | Qdrant        |           | Event Bus     |
| (metadata,    |           | (vectors)     |           | (notify       |
|  entities)    |           |               |           |  shards)      |
+---------------+           +---------------+           +---------------+
        |                           |                           |
        +---------------------------+---------------------------+
                                    |
                                    v
                        +------------------------+
                        | Shards Consume Events: |
                        | - ACH: analyze docs    |
                        | - Search: index ready  |
                        | - Contradict: scan     |
                        +------------------------+
```

### 1.6 Database Schema Architecture

PostgreSQL uses schema isolation for Frame and each Shard:

```sql
-- Frame's schema (managed by Frame)
CREATE SCHEMA arkham_frame;
-- Tables: documents, chunks, entities, canonical_entities,
--         entity_relationships, projects, clusters, page_ocr,
--         minidocs, events

-- Dashboard Shard's schema
CREATE SCHEMA arkham_dashboard;
-- Tables: (minimal - mostly reads Frame data)

-- ACH Shard's schema
CREATE SCHEMA arkham_ach;
-- Tables: ach_analysis, ach_hypotheses, ach_evidence,
--         ach_ratings, ach_milestones, ach_snapshots

-- Contradictions Shard's schema
CREATE SCHEMA arkham_contradictions;
-- Tables: contradictions, contradiction_batches, contradiction_chains

-- Each shard's tables are isolated in their own namespace
-- Shards reference Frame tables by ID only (soft references, no FK constraints)
```

### 1.7 Network Security Model

- **Internal Network**: All containers communicate via `shattered-network` bridge
- **External Access**: Only port 3000 exposed (FastAPI serves frontend + API)
- **Database Isolation**: PostgreSQL, Qdrant, Redis have no external port bindings
- **LLM Connection**: App connects outbound to LM Studio (host machine or remote)
- **Inter-Shard**: Communication via Frame's event bus only (no direct shard-to-shard)

---

## 2. System Requirements

### 2.1 Hardware Requirements

| Resource | Minimum | Recommended | Notes |
|----------|---------|-------------|-------|
| **vCPU** | 2 cores | 4+ cores | Workers are CPU-intensive |
| **RAM** | 8 GB | 16+ GB | BGE-M3 embeddings use ~2.2GB |
| **Storage** | 20 GB | 50+ GB | NVMe/SSD strongly recommended |
| **Network** | 100 Mbps | 1 Gbps | For image pulls and LLM traffic |

### 2.2 Software Requirements

| Software | Version | Notes |
|----------|---------|-------|
| **OS** | Ubuntu 22.04+ / Debian 12+ | Any Linux with Docker support |
| **Docker** | 24.0+ | With Docker Compose V2 |
| **LM Studio** | Latest | Running on host or accessible remotely |

### 2.3 Per-Component Resource Usage

| Component | RAM Usage | Storage |
|-----------|-----------|---------|
| **App Container** | 2-4 GB | ~6 GB (image) |
| **PostgreSQL** | 256-512 MB | Variable (schemas) |
| **Qdrant** | 512 MB - 2 GB | Variable (vectors) |
| **Redis** | 64-256 MB | Minimal |
| **Total Base** | ~4-6 GB | ~8 GB |

### 2.4 Per-Shard Additions

| Shard | Additional RAM | Additional Storage | Dependencies |
|-------|----------------|-------------------|--------------|
| Dashboard | Negligible | Negligible | None |
| ACH | ~50 MB | Minimal | pandas, plotly |
| Search | Negligible | Negligible | Uses Frame vectors |
| Contradictions | ~200 MB | Minimal | Additional NLP |
| Timeline | ~50 MB | Minimal | Date parsing libs |
| Entities | ~100 MB | Minimal | Graph libraries |

---

## 3. Shard Selection

### 3.1 Configuration File

Shard selection is controlled by `shattered.yaml`, a configuration file mounted into the container:

```yaml
# shattered.yaml - Shard Configuration
# Mount this file to /config/shattered.yaml in the container

# Frame version compatibility
frame_version: "1.0.0"

# Enabled shards
# Dashboard is always required and cannot be disabled
shards:
  dashboard: true      # REQUIRED - System status and shard management
  ach: true            # Analysis of Competing Hypotheses
  search: true         # Semantic search interface
  contradictions: true # Contradiction detection and chains
  timeline: false      # Timeline visualization
  entities: false      # Entity graph and influence mapping
  anomalies: false     # Anomaly detection
  red_flags: false     # Suspicious pattern detection
  narrative: false     # Narrative reconstruction
  tables: false        # Table extraction and display
  export: false        # Multi-format export

# Frame configuration
frame:
  # Worker settings
  workers:
    ocr:
      enabled: true
      provider: "paddleocr"
      concurrency: 2
    parser:
      enabled: true
      provider: "spacy"
      model: "en_core_web_sm"
    embed:
      enabled: true
      provider: "bge-m3"
    clustering:
      enabled: true
      min_cluster_size: 5

  # LLM settings (if not using environment variable)
  llm:
    provider: "lm_studio"
    # url set via LM_STUDIO_URL environment variable

  # Logging
  logging:
    level: "INFO"
    format: "structured"
```

### 3.2 Available Shards

#### Core Shards (Included in MVP)

| Shard | Description | Frame Dependency |
|-------|-------------|------------------|
| **dashboard** | System status, health indicators, shard management, metrics | Required |
| **ach** | Heuer's 8-step Analysis of Competing Hypotheses | Frame only |
| **search** | Semantic search with filters and export | Frame vectors |

#### Analysis Shards

| Shard | Description | Optional Enhancements |
|-------|-------------|----------------------|
| **contradictions** | Detect contradictions between documents, build chains | Subscribes to document.processed |
| **timeline** | Timeline visualization and merging | Subscribes to entity.created |
| **anomalies** | Statistical anomaly detection | Subscribes to document.processed |
| **red_flags** | Suspicious pattern detection | Subscribes to entity.created |
| **narrative** | Narrative reconstruction across documents | Uses contradictions events |

#### Visualization Shards

| Shard | Description | Optional Enhancements |
|-------|-------------|----------------------|
| **entities** | Entity graph, influence mapping, pathfinder | Subscribes to entity.merged |
| **tables** | Extracted table display and export | Subscribes to document.processed |

#### Utility Shards

| Shard | Description | Notes |
|-------|-------------|-------|
| **export** | Multi-format export (PDF, CSV, JSON) | Works with any shard data |

### 3.3 Pre-Built Configurations

For convenience, we provide pre-built images with common shard combinations:

| Configuration | Image Tag | Included Shards |
|---------------|-----------|-----------------|
| **Minimal** | `shattered-kandor:minimal` | dashboard |
| **Standard** | `shattered-kandor:standard` | dashboard, ach, search |
| **Analysis** | `shattered-kandor:analysis` | dashboard, ach, search, contradictions, timeline |
| **Full** | `shattered-kandor:full` | All shards |

Users can also build custom configurations from source (see Section 4).

### 3.4 Shard Dependencies

Shards have no hard dependencies on each other. However, some shards provide optional enhancements when others are present:

```
+-------------+                    +----------------+
| ACH Shard   | --subscribes to--> | contradictions |
|             |    (optional)      | .detected      |
+-------------+                    +----------------+
      |
      +--subscribes to--> timeline.event_added (optional)

If the source shard is not installed, the subscriber shard
simply doesn't receive those events. No errors, no crashes.
Graceful degradation is enforced by the Shard protocol.
```

---

## 4. Building the Container

### 4.1 Monorepo Structure

The ArkhamMirror Shattered repository uses a Turborepo monorepo:

```
ArkhamMirror-Shattered/
|-- README.md
|-- pyproject.toml              # Python workspace
|-- package.json                # Root package.json
|-- pnpm-workspace.yaml         # pnpm workspace
|-- turbo.json                  # Turborepo config
|-- Dockerfile                  # Multi-stage build
|-- docker-compose.prod.yml     # Production compose
|-- shattered.yaml.example      # Example shard config
|
|-- packages/
|   |-- arkham-frame/           # The Frame (core)
|   |   |-- pyproject.toml
|   |   |-- arkham_frame/       # Python backend
|   |   |   |-- main.py         # FastAPI app
|   |   |   |-- frame.py        # ArkhamFrame class
|   |   |   |-- api/            # REST endpoints
|   |   |   |-- services/       # Core services
|   |   |   |-- workers/        # Background workers
|   |   |   |-- models/         # SQLAlchemy models
|   |   |   |-- schemas/        # Pydantic schemas
|   |   |   +-- registry/       # Shard management
|   |   +-- migrations/
|   |
|   |-- arkham-shard-dashboard/
|   |   |-- pyproject.toml
|   |   |-- shard.yaml          # Shard manifest
|   |   |-- arkham_shard_dashboard/
|   |   |   |-- shard.py        # ArkhamShard implementation
|   |   |   |-- routes.py       # FastAPI routes
|   |   |   +-- service.py
|   |   +-- frontend/           # React components
|   |       |-- package.json
|   |       +-- src/
|   |
|   |-- arkham-shard-ach/
|   |-- arkham-shard-search/
|   |-- arkham-shard-contradictions/
|   +-- ... (other shards)
|
|-- frontend/                   # React shell
|   |-- package.json
|   |-- src/
|   |   |-- App.tsx             # Main app, routing
|   |   |-- components/         # Shared components
|   |   |   |-- Sidebar.tsx
|   |   |   |-- Layout.tsx
|   |   |   +-- ...
|   |   +-- hooks/
|   |       +-- useFrameState.ts
|   +-- vite.config.ts
|
+-- docker/
    +-- entrypoint.sh
```

### 4.2 Dockerfile (Multi-Stage Build)

```dockerfile
# =============================================================================
# Shattered KANDOR: Multi-Stage Dockerfile
# Builds Frame + All Shards into a single deployable container
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Frontend Build (React + Turborepo)
# -----------------------------------------------------------------------------
FROM node:18-alpine AS frontend-builder

# Install pnpm
RUN corepack enable pnpm

WORKDIR /build

# Copy package files for dependency installation
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml turbo.json ./
COPY frontend/package.json ./frontend/
COPY packages/arkham-shard-*/frontend/package.json ./packages/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source code
COPY frontend/ ./frontend/
COPY packages/*/frontend/ ./packages/

# Build all frontends (Turborepo handles ordering)
RUN pnpm turbo build --filter=frontend...

# -----------------------------------------------------------------------------
# Stage 2: Python Backend Build
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS backend-builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy all Python packages
COPY packages/arkham-frame/pyproject.toml ./packages/arkham-frame/
COPY packages/arkham-frame/arkham_frame/ ./packages/arkham-frame/arkham_frame/
COPY packages/arkham-shard-*/pyproject.toml ./packages/
COPY packages/arkham-shard-*/arkham_shard_*/ ./packages/

# Install Frame
RUN pip install --no-cache-dir --upgrade pip wheel setuptools
RUN pip install --no-cache-dir ./packages/arkham-frame

# Install all Shards (runtime config determines which are enabled)
RUN for shard_dir in ./packages/arkham-shard-*/; do \
      pip install --no-cache-dir "$shard_dir"; \
    done

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# -----------------------------------------------------------------------------
# Stage 3: Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Labels
LABEL org.opencontainers.image.source="https://github.com/mantisfury/ArkhamMirror"
LABEL org.opencontainers.image.description="ArkhamMirror Shattered - Modular AI Investigation Platform"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="Shattered KANDOR"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Copy backend packages (already installed in venv, but need source for migrations)
COPY packages/arkham-frame/ /app/packages/arkham-frame/
COPY packages/arkham-shard-*/ /app/packages/

# Set working directory
WORKDIR /app

# Create directories
RUN mkdir -p /app/DataSilo/documents \
             /app/DataSilo/pages \
             /app/DataSilo/logs \
             /app/DataSilo/temp \
             /app/config

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/api/frame/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

### 4.3 Entrypoint Script

Create `docker/entrypoint.sh`:

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "   Shattered KANDOR Starting"
echo "=========================================="
echo ""

# Configuration file
CONFIG_FILE="${CONFIG_FILE:-/config/shattered.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[WARN] No config file at $CONFIG_FILE, using defaults"
    echo "       Mount a config file for shard selection"
fi

# Wait for PostgreSQL
echo "[1/5] Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST:-postgres} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-arkham} 2>/dev/null; do
    sleep 2
done
echo "      PostgreSQL ready"

# Wait for Qdrant
echo "[2/5] Waiting for Qdrant..."
until curl -sf http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}/health 2>/dev/null; do
    sleep 2
done
echo "      Qdrant ready"

# Wait for Redis
echo "[3/5] Waiting for Redis..."
until redis-cli -h ${REDIS_HOST:-redis} -p ${REDIS_PORT:-6379} ping 2>/dev/null | grep -q PONG; do
    sleep 2
done
echo "      Redis ready"

# Run Frame migrations
echo "[4/5] Running database migrations..."
cd /app/packages/arkham-frame
alembic upgrade head 2>/dev/null || echo "      Frame migrations complete (or already current)"

# Initialize Frame and run shard migrations
echo "[5/5] Initializing Frame and Shards..."
python -c "
from arkham_frame import ArkhamFrame
frame = ArkhamFrame()
frame.initialize()
print('      Frame initialized')
print(f'      Enabled shards: {frame.get_enabled_shards()}')
"

echo ""

# Start workers in background
echo "Starting background workers..."
python -m arkham_frame.workers.runner &
WORKER_PID=$!

# Handle shutdown gracefully
trap "echo 'Shutting down...'; kill $WORKER_PID 2>/dev/null; exit 0" SIGTERM SIGINT

# Start FastAPI server
echo "Starting application server..."
echo ""
echo "=========================================="
echo "   Shattered KANDOR Ready"
echo "   http://0.0.0.0:8000"
echo "=========================================="
echo ""

exec uvicorn arkham_frame.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
```

### 4.4 Docker Compose (Production)

Create `docker-compose.prod.yml`:

```yaml
# =============================================================================
# Shattered KANDOR: Production Docker Compose
# Deploy with: docker compose -f docker-compose.prod.yml up -d
# =============================================================================

name: shattered-kandor

services:
  # ---------------------------------------------------------------------------
  # Main Application (Frame + Shards + Frontend)
  # ---------------------------------------------------------------------------
  app:
    image: ghcr.io/mantisfury/shattered-kandor:latest
    # For local builds:
    # build:
    #   context: .
    #   dockerfile: Dockerfile
    container_name: shattered-app
    restart: unless-stopped
    ports:
      - "${APP_PORT:-3000}:8000"   # External 3000 -> Internal 8000
    environment:
      # Database
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER:-arkham}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-arkhampass}
      - POSTGRES_DB=${POSTGRES_DB:-arkhamdb}
      - DATABASE_URL=postgresql://${POSTGRES_USER:-arkham}:${POSTGRES_PASSWORD:-arkhampass}@postgres:5432/${POSTGRES_DB:-arkhamdb}
      # Vector database
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - QDRANT_URL=http://qdrant:6333
      # Queue
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_URL=redis://redis:6379
      # LLM
      - LM_STUDIO_URL=${LM_STUDIO_URL:-http://host.docker.internal:1234/v1}
      # Config
      - CONFIG_FILE=/config/shattered.yaml
    volumes:
      # Shard configuration
      - ./config/shattered.yaml:/config/shattered.yaml:ro
      # Persistent data
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
  # PostgreSQL - Frame Schema + Shard Schemas
  # ---------------------------------------------------------------------------
  postgres:
    image: postgres:15-alpine
    container_name: shattered-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-arkham}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-arkhampass}
      - POSTGRES_DB=${POSTGRES_DB:-arkhamdb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-arkham} -d ${POSTGRES_DB:-arkhamdb}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - shattered-net
    # Internal only - no ports exposed

  # ---------------------------------------------------------------------------
  # Qdrant - Vector Database
  # ---------------------------------------------------------------------------
  qdrant:
    image: qdrant/qdrant:latest
    container_name: shattered-qdrant
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - shattered-net
    # Internal only - no ports exposed

  # ---------------------------------------------------------------------------
  # Redis - Task Queue
  # ---------------------------------------------------------------------------
  redis:
    image: redis:7-alpine
    container_name: shattered-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s
    networks:
      - shattered-net
    # Internal only - no ports exposed

# -----------------------------------------------------------------------------
# Volumes
# -----------------------------------------------------------------------------
volumes:
  postgres_data:
    name: shattered_postgres_data
  qdrant_data:
    name: shattered_qdrant_data
  redis_data:
    name: shattered_redis_data
  datasilo:
    name: shattered_datasilo

# -----------------------------------------------------------------------------
# Network
# -----------------------------------------------------------------------------
networks:
  shattered-net:
    name: shattered-network
    driver: bridge
```

### 4.5 Build Commands

```bash
# Clone the repository
git clone https://github.com/mantisfury/ArkhamMirror-Shattered.git
cd ArkhamMirror-Shattered

# Build the image locally
docker build -t shattered-kandor:local .

# Or build with specific tag
docker build -t shattered-kandor:$(date +%Y%m%d) .

# Build for multiple platforms (for publishing)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/mantisfury/shattered-kandor:latest \
  --push .
```

### 4.6 Local Development Build

For development, use the Turborepo dev server:

```bash
# Install dependencies
pnpm install

# Start all services in dev mode
pnpm turbo dev

# This runs:
# - FastAPI with hot reload (port 8000)
# - Vite dev server with HMR (port 3000)
# - Watches for changes in all packages
```

---

## 5. Publishing to Container Registries

### 5.1 GitHub Container Registry (Recommended)

```bash
# 1. Create Personal Access Token at https://github.com/settings/tokens
#    Required scopes: read:packages, write:packages, delete:packages

# 2. Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u mantisfury --password-stdin

# 3. Tag and push
docker tag shattered-kandor:local ghcr.io/mantisfury/shattered-kandor:latest
docker tag shattered-kandor:local ghcr.io/mantisfury/shattered-kandor:$(date +%Y%m%d)
docker push ghcr.io/mantisfury/shattered-kandor:latest
docker push ghcr.io/mantisfury/shattered-kandor:$(date +%Y%m%d)

# 4. Make package public (GitHub UI)
#    https://github.com/users/mantisfury/packages/container/shattered-kandor/settings
```

### 5.2 GitHub Actions CI/CD

Create `.github/workflows/shattered-kandor-build.yml`:

```yaml
name: Shattered KANDOR Build and Publish

on:
  push:
    branches: [main, kandor]
    tags: ['v*']
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      configuration:
        description: 'Build configuration (minimal, standard, analysis, full)'
        required: true
        default: 'full'
        type: choice
        options:
          - minimal
          - standard
          - analysis
          - full

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
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=tag
            type=sha,prefix=
            type=raw,value=latest,enable={{is_default_branch}}
            type=raw,value={{date 'YYYYMMDD'}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64

  # Build pre-configured variants
  build-variants:
    runs-on: ubuntu-latest
    needs: build-and-push
    strategy:
      matrix:
        config: [minimal, standard, analysis]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build ${{ matrix.config }} variant
        run: |
          # Copy appropriate config
          cp configs/${{ matrix.config }}.yaml config/shattered.yaml
          docker build -t ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ matrix.config }} .
          docker push ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ matrix.config }}
```

### 5.3 Pre-Built Configuration Files

Create configuration files for common setups in `configs/`:

**configs/minimal.yaml:**
```yaml
frame_version: "1.0.0"
shards:
  dashboard: true
```

**configs/standard.yaml:**
```yaml
frame_version: "1.0.0"
shards:
  dashboard: true
  ach: true
  search: true
```

**configs/analysis.yaml:**
```yaml
frame_version: "1.0.0"
shards:
  dashboard: true
  ach: true
  search: true
  contradictions: true
  timeline: true
  entities: true
```

---

## 6. Deployment Paths

### 6.1 Quick Deploy (Evaluation / Trusted Networks)

**For**: Evaluation, development, personal use on trusted networks

**Security Level**: Basic (relies on network isolation)

**Time**: 10 minutes

```bash
# 1. Install Docker (if needed)
curl -fsSL https://get.docker.com | sh

# 2. Create directory
mkdir -p ~/shattered && cd ~/shattered

# 3. Download compose file and example config
curl -O https://raw.githubusercontent.com/mantisfury/ArkhamMirror-Shattered/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/mantisfury/ArkhamMirror-Shattered/main/shattered.yaml.example
mkdir -p config && mv shattered.yaml.example config/shattered.yaml

# 4. Edit config to select your shards
nano config/shattered.yaml

# 5. Start everything
docker compose -f docker-compose.prod.yml up -d

# 6. Access at http://localhost:3000
```

### 6.2 Production Hardened Deploy

**For**: Journalists, investigators, handling sensitive documents

**Security Level**: High (VPN, firewall, encrypted secrets)

**Time**: 30-60 minutes

```
Step 1: Provision VPS (Section 7)
    |
    v
Step 2: Configure VPN - WireGuard or Tailscale (Section 8.1)
    |
    v
Step 3: Harden Server - UFW, SSH, fail2ban (Section 8.2-8.4)
    |
    v
Step 4: Setup 1Password for Secrets (Section 8.5) [Optional]
    |
    v
Step 5: Configure Shard Selection (config/shattered.yaml)
    |
    v
Step 6: Deploy Shattered KANDOR via Docker Compose
    |
    v
Step 7: Configure Monitoring & Backups (Section 9)
```

### 6.3 Deployment Comparison

| Aspect | Quick Deploy | Production Hardened |
|--------|--------------|---------------------|
| Setup Time | 10 min | 30-60 min |
| VPN Required | No | Yes |
| Firewall Config | No | Yes |
| Secret Management | .env file | 1Password |
| Public Internet Access | Optional | VPN-only |
| Suitable for Sensitive Data | No | Yes |
| Backup Automation | Manual | Automated |
| Shard Selection | Edit YAML | Edit YAML |

---

## 7. VPS Provider Guide

### 7.1 Provider Comparison

| Provider | Plan | vCPU | RAM | Storage | Monthly Cost | Best For |
|----------|------|------|-----|---------|--------------|----------|
| **Hostinger** | KVM 4 | 4 | 16 GB | 200 GB NVMe | $10.49 | Budget-friendly |
| **Hetzner** | CPX31 | 4 | 8 GB | 160 GB | ~$15 | European hosting |
| **Vultr** | Cloud Compute | 4 | 16 GB | 100 GB SSD | $80 | Good performance |
| **DigitalOcean** | General Purpose | 4 | 16 GB | 100 GB | $96 | Developer-friendly |
| **AWS** | t3.xlarge | 4 | 16 GB | EBS | ~$120 | Enterprise features |
| **GCP** | n2-standard-4 | 4 | 16 GB | PD-SSD | ~$130 | Google ecosystem |

### 7.2 Recommended Configuration

For most users: **Hostinger KVM 4** ($10.49/mo) or **Hetzner CPX31** (~$15/mo)

- 4 vCPU handles document processing workloads
- 16 GB RAM (or 8 GB for light use) accommodates embeddings
- NVMe storage for fast I/O

### 7.3 DigitalOcean Deployment

```bash
# Create Droplet via CLI
doctl compute droplet create shattered-kandor \
  --image ubuntu-24-04-x64 \
  --size s-4vcpu-16gb \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header) \
  --tag-names shattered \
  --enable-monitoring \
  --enable-private-networking

# SSH in
ssh root@YOUR_DROPLET_IP

# Run setup script (see Section 7.5)
```

### 7.4 Vultr Deployment

```bash
# Via Vultr API
curl "https://api.vultr.com/v2/instances" \
  -X POST \
  -H "Authorization: Bearer ${VULTR_API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{
    "region": "ewr",
    "plan": "vc2-4c-16gb",
    "label": "shattered-kandor",
    "os_id": 2284,
    "sshkey_id": ["your-ssh-key-id"]
  }'
```

### 7.5 Universal VPS Setup Script

```bash
#!/bin/bash
# shattered-vps-setup.sh
# Run as root on fresh VPS

set -e

echo "=========================================="
echo "   Shattered KANDOR VPS Setup"
echo "=========================================="

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Create user
if ! id "shattered" &>/dev/null; then
    adduser --disabled-password --gecos "" shattered
    usermod -aG sudo shattered
    usermod -aG docker shattered
    echo "shattered ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/shattered
fi

# Copy SSH keys
mkdir -p /home/shattered/.ssh
cp ~/.ssh/authorized_keys /home/shattered/.ssh/
chown -R shattered:shattered /home/shattered/.ssh
chmod 700 /home/shattered/.ssh
chmod 600 /home/shattered/.ssh/authorized_keys

echo ""
echo "Setup complete. Now:"
echo "  1. su - shattered"
echo "  2. Continue with Shattered KANDOR deployment"
```

---

## 8. Security Hardening

### 8.1 VPN Configuration

#### Option A: WireGuard (Best Performance)

**Server Setup:**

```bash
# Install WireGuard
sudo apt install -y wireguard

# Generate keys
wg genkey | sudo tee /etc/wireguard/server_private.key
sudo chmod 600 /etc/wireguard/server_private.key
sudo cat /etc/wireguard/server_private.key | wg pubkey | sudo tee /etc/wireguard/server_public.key

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me)

# Create config
sudo tee /etc/wireguard/wg0.conf << EOF
[Interface]
PrivateKey = $(sudo cat /etc/wireguard/server_private.key)
Address = 10.200.200.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
SaveConfig = true
EOF

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Start WireGuard
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

echo "Server public key: $(sudo cat /etc/wireguard/server_public.key)"
echo "Endpoint: $PUBLIC_IP:51820"
```

**Client Setup:**

```bash
# Generate client keys
wg genkey | tee client_private.key | wg pubkey > client_public.key

# Create client config
cat > shattered.conf << EOF
[Interface]
PrivateKey = $(cat client_private.key)
Address = 10.200.200.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = SERVER_PUBLIC_KEY_HERE
AllowedIPs = 10.200.200.0/24
Endpoint = SERVER_IP:51820
PersistentKeepalive = 25
EOF

# Add client to server
sudo wg set wg0 peer $(cat client_public.key) allowed-ips 10.200.200.2/32

# Connect
sudo wg-quick up ./shattered.conf

# Access: http://10.200.200.1:3000
```

#### Option B: Tailscale (Easiest)

```bash
# On VPS
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh

# Get Tailscale IP
tailscale ip -4  # e.g., 100.x.x.x

# On your machine: Install Tailscale, login with same account
# Access: http://100.x.x.x:3000
```

#### Option C: Cloudflare Tunnel (Zero Trust)

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create shattered

# Configure
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << EOF
tunnel: YOUR_TUNNEL_ID
credentials-file: /home/shattered/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: shattered.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
EOF

# Route DNS and start
cloudflared tunnel route dns shattered shattered.yourdomain.com
sudo cloudflared service install
sudo systemctl start cloudflared
```

### 8.2 Firewall Configuration

```bash
# Reset and configure UFW
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# For WireGuard:
sudo ufw allow 51820/udp comment 'WireGuard'
sudo ufw allow from 10.200.200.0/24 to any port 22 proto tcp comment 'SSH via VPN'
sudo ufw allow from 10.200.200.0/24 to any port 3000 proto tcp comment 'Shattered via VPN'

# For Tailscale:
sudo ufw allow in on tailscale0

# Enable
sudo ufw enable
sudo ufw status verbose
```

### 8.3 SSH Hardening

```bash
sudo tee /etc/ssh/sshd_config.d/hardening.conf << EOF
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
MaxAuthTries 3
MaxSessions 2
AllowUsers shattered
EOF

sudo systemctl restart sshd
```

### 8.4 Fail2Ban

```bash
sudo apt install -y fail2ban

sudo tee /etc/fail2ban/jail.local << EOF
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 8.5 1Password Secrets Management

```bash
# Install 1Password CLI
curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
  sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/amd64 stable main" | \
  sudo tee /etc/apt/sources.list.d/1password.list
sudo apt update && sudo apt install 1password-cli

op signin
```

Create `.env.1password`:

```bash
POSTGRES_USER=op://Shattered/Database/username
POSTGRES_PASSWORD=op://Shattered/Database/password
POSTGRES_DB=op://Shattered/Database/database
```

Start with secrets:

```bash
op run --env-file=.env.1password -- docker compose -f docker-compose.prod.yml up -d
```

### 8.6 Security Checklist

- [ ] SSH key authentication only
- [ ] Root login disabled
- [ ] UFW firewall enabled
- [ ] VPN configured (WireGuard/Tailscale/Cloudflare)
- [ ] Fail2Ban running
- [ ] Database password changed from default
- [ ] All services accessible via VPN only
- [ ] Automatic security updates enabled

---

## 9. Operations & Maintenance

### 9.1 Health Monitoring

Create `health_check.sh`:

```bash
#!/bin/bash

echo "=== Shattered KANDOR Health Check ==="
echo ""

# Check containers
echo "Containers:"
for container in shattered-app shattered-postgres shattered-qdrant shattered-redis; do
    if docker ps --filter "name=$container" --format "{{.Status}}" | grep -q "Up"; then
        echo "  [OK] $container"
    else
        echo "  [FAIL] $container"
    fi
done

echo ""

# Check Frame health endpoint
echo "Application:"
HEALTH=$(curl -sf http://localhost:3000/api/frame/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  [OK] Frame API responding"
    echo "  Enabled shards: $(echo $HEALTH | jq -r '.shards | join(", ")')"
else
    echo "  [FAIL] Frame API not responding"
fi

echo ""

# Resources
echo "Resources:"
DISK=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
MEM=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
echo "  Disk: ${DISK}%"
echo "  Memory: ${MEM}%"
```

### 9.2 Backup & Restore

**Backup Script:**

```bash
#!/bin/bash
# backup_shattered.sh

BACKUP_DIR="/home/shattered/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "Starting Shattered KANDOR backup..."

# Backup PostgreSQL (all schemas)
docker exec shattered-postgres pg_dumpall -U arkham > "$BACKUP_DIR/postgres_$DATE.sql"

# Backup DataSilo
docker run --rm \
  -v shattered_datasilo:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/datasilo_$DATE.tar.gz -C /data .

# Backup config
cp ~/shattered/config/shattered.yaml "$BACKUP_DIR/config_$DATE.yaml"

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup complete: $BACKUP_DIR"
```

**Restore Script:**

```bash
#!/bin/bash
# restore_shattered.sh

BACKUP_DIR="/home/shattered/backups"

echo "Available backups:"
ls -la $BACKUP_DIR/*.sql

read -p "Enter date stamp (e.g., 20241217_030000): " DATE

# Stop app
docker compose -f docker-compose.prod.yml stop app

# Restore PostgreSQL
cat "$BACKUP_DIR/postgres_$DATE.sql" | docker exec -i shattered-postgres psql -U arkham

# Restore DataSilo
docker run --rm \
  -v shattered_datasilo:/data \
  -v $BACKUP_DIR:/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/datasilo_$DATE.tar.gz -C /data"

# Restore config
cp "$BACKUP_DIR/config_$DATE.yaml" ~/shattered/config/shattered.yaml

# Restart
docker compose -f docker-compose.prod.yml start app

echo "Restore complete"
```

### 9.3 Updates

```bash
# Pull latest image
docker compose -f docker-compose.prod.yml pull

# Restart with new image (data preserved)
docker compose -f docker-compose.prod.yml up -d

# Clean old images
docker image prune -f
```

### 9.4 Shard Management Post-Deploy

To change which shards are enabled:

```bash
# 1. Edit configuration
nano ~/shattered/config/shattered.yaml

# 2. Restart app container (migrations run automatically)
docker compose -f docker-compose.prod.yml restart app

# 3. Verify
curl http://localhost:3000/api/frame/health | jq '.shards'
```

### 9.5 Cron Jobs

```bash
crontab -e

# Health check every 5 minutes
*/5 * * * * /home/shattered/scripts/health_check.sh >> /home/shattered/logs/health.log 2>&1

# Daily backup at 3 AM
0 3 * * * /home/shattered/scripts/backup_shattered.sh >> /home/shattered/logs/backup.log 2>&1

# Weekly image update (Sunday 4 AM)
0 4 * * 0 cd /home/shattered && docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d >> /home/shattered/logs/updates.log 2>&1
```

### 9.6 Logs

```bash
# All logs
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f app

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 app

# Export logs
docker compose -f docker-compose.prod.yml logs > shattered_logs_$(date +%Y%m%d).txt
```

---

## 10. Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs app

# Common issues:
# 1. Config file missing - ensure config/shattered.yaml exists
# 2. Memory exhausted - check with: free -h
# 3. Port conflict - check with: netstat -tlnp | grep 3000
```

### Database Connection Failed

```bash
# Check PostgreSQL
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml logs postgres

# Test connection
docker compose -f docker-compose.prod.yml exec postgres psql -U arkham -d arkhamdb -c "SELECT 1;"

# Check schemas exist
docker compose -f docker-compose.prod.yml exec postgres psql -U arkham -d arkhamdb -c "\dn"
```

### Shard Not Loading

```bash
# Check if shard is enabled in config
cat config/shattered.yaml | grep -A20 "shards:"

# Check Frame logs for shard initialization
docker compose -f docker-compose.prod.yml logs app | grep -i "shard"

# Verify shard migrations ran
docker compose -f docker-compose.prod.yml exec postgres psql -U arkham -d arkhamdb -c "\dt arkham_*.*"
```

### LM Studio Connection Failed

```bash
# Check if LM Studio is accessible
curl http://localhost:1234/v1/models

# For Linux Docker, use host IP instead of host.docker.internal
ip route | grep default | awk '{print $3}'

# Update environment
export LM_STUDIO_URL=http://172.17.0.1:1234/v1
docker compose -f docker-compose.prod.yml up -d
```

### Reset Everything

```bash
# Stop and remove everything
docker compose -f docker-compose.prod.yml down -v

# Remove images
docker rmi ghcr.io/mantisfury/shattered-kandor:latest

# Fresh start
docker compose -f docker-compose.prod.yml up -d
```

### Resource Issues

```bash
# Container stats
docker stats

# Disk usage
docker system df
df -h

# Clean up
docker system prune -a --volumes
```

---

## 11. Future Enhancements

### 11.1 LLM Cloud Infrastructure (TODO)

Currently, Shattered KANDOR requires LM Studio running externally. Future options:

- **Ollama sidecar container**: Smaller models, CPU-capable
- **vLLM container**: For GPU-equipped VPS
- **OpenAI/Anthropic fallback**: For users who accept cloud LLM
- **Bundled lightweight model**: Small LLM included in container

### 11.2 Lite Mode Containers

Future variant using SQLite + ChromaDB instead of PostgreSQL + Qdrant:

```yaml
# docker-compose.lite.yml
services:
  app:
    image: ghcr.io/mantisfury/shattered-kandor:lite
    # No external database containers needed
    # SQLite + ChromaDB run inside app container
```

### 11.3 Team Mode

Future variant with remote shared services:

```yaml
# shattered.yaml for Team mode
frame:
  mode: "team"
  database:
    host: "shared-postgres.internal"
  vector:
    host: "shared-qdrant.internal"
  queue:
    host: "shared-redis.internal"
```

### 11.4 GPU Container Variant

```dockerfile
# Dockerfile.gpu
FROM nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04
# GPU-accelerated OCR and embeddings
```

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
docker compose -f docker-compose.prod.yml logs -f

# Shell into container
docker compose -f docker-compose.prod.yml exec app bash

# Update
docker compose -f docker-compose.prod.yml pull && \
docker compose -f docker-compose.prod.yml up -d

# Check enabled shards
curl http://localhost:3000/api/frame/health | jq '.shards'
```

### URLs

| Service | URL |
|---------|-----|
| Application | http://localhost:3000 |
| API | http://localhost:3000/api/ |
| Frame Health | http://localhost:3000/api/frame/health |
| Via WireGuard | http://10.200.200.1:3000 |
| Via Tailscale | http://100.x.x.x:3000 |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `arkham` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `arkhampass` | PostgreSQL password |
| `POSTGRES_DB` | `arkhamdb` | PostgreSQL database |
| `LM_STUDIO_URL` | `http://host.docker.internal:1234/v1` | LLM endpoint |
| `APP_PORT` | `3000` | External port mapping |
| `CONFIG_FILE` | `/config/shattered.yaml` | Shard config path |

### Volumes

| Volume | Purpose |
|--------|---------|
| `shattered_postgres_data` | Frame + Shard schemas |
| `shattered_qdrant_data` | Vector embeddings |
| `shattered_redis_data` | Job queue |
| `shattered_datasilo` | Documents, pages, logs |

---

## 13. Appendices

### Appendix A: Complete shattered.yaml Reference

```yaml
# Shattered KANDOR Configuration Reference
# All options with defaults shown

# Frame compatibility
frame_version: "1.0.0"

# Shard enablement
shards:
  # Core (required)
  dashboard: true         # System status, health, shard management

  # Analysis
  ach: false              # Analysis of Competing Hypotheses
  contradictions: false   # Contradiction detection and chains
  anomalies: false        # Statistical anomaly detection
  red_flags: false        # Suspicious pattern detection
  narrative: false        # Narrative reconstruction

  # Visualization
  search: false           # Semantic search interface
  timeline: false         # Timeline visualization and merge
  entities: false         # Entity graph, influence, pathfinder
  tables: false           # Extracted table display

  # Utility
  export: false           # Multi-format export

# Frame configuration
frame:
  # Worker configuration
  workers:
    ocr:
      enabled: true
      provider: "paddleocr"  # or "qwen_vl" for GPU
      concurrency: 2
    parser:
      enabled: true
      provider: "spacy"
      model: "en_core_web_sm"
    embed:
      enabled: true
      provider: "bge-m3"     # or "minilm" for lighter weight
    clustering:
      enabled: true
      min_cluster_size: 5

  # Event bus
  events:
    persistence: "session"   # Events cleared on restart
    max_retries: 3

  # Logging
  logging:
    level: "INFO"           # DEBUG, INFO, WARNING, ERROR
    format: "structured"    # or "simple"

  # LLM (if not using LM_STUDIO_URL env var)
  llm:
    provider: "lm_studio"
    timeout: 120
```

### Appendix B: Pre-Built Image Tags

| Tag | Contents |
|-----|----------|
| `latest` | Full build with all shards |
| `minimal` | Dashboard only |
| `standard` | Dashboard + ACH + Search |
| `analysis` | Dashboard + ACH + Search + Contradictions + Timeline + Entities |
| `full` | All shards |
| `YYYYMMDD` | Date-stamped builds |
| `vX.Y.Z` | Semantic version releases |

### Appendix C: One-Click Deploy Script

```bash
#!/bin/bash
# Shattered KANDOR One-Click Deploy
# curl -sSL https://get.shattered.arkhammirror.io | bash

set -e

echo ""
echo "  _____ _           _   _                    _ "
echo " / ____| |         | | | |                  | |"
echo "| (___ | |__   __ _| |_| |_ ___ _ __ ___  __| |"
echo " \\___ \\| '_ \\ / _\` | __| __/ _ \\ '__/ _ \\/ _\` |"
echo " ____) | | | | (_| | |_| ||  __/ | |  __/ (_| |"
echo "|_____/|_| |_|\\__,_|\\__|\\__\\___|_|  \\___|\\__,_|"
echo ""
echo "       KANDOR - Cloud Deployment"
echo "=============================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    sudo systemctl enable docker
    sudo systemctl start docker
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "Docker Compose V2 required"
    exit 1
fi

echo "[1/5] Docker ready"

# Create directory
mkdir -p ~/shattered/config && cd ~/shattered
echo "[2/5] Directory created: ~/shattered"

# Download files
curl -sSL -o docker-compose.prod.yml \
    https://raw.githubusercontent.com/mantisfury/ArkhamMirror-Shattered/main/docker-compose.prod.yml
echo "[3/5] Docker Compose downloaded"

# Create default config (standard configuration)
cat > config/shattered.yaml << 'EOF'
frame_version: "1.0.0"
shards:
  dashboard: true
  ach: true
  search: true
  contradictions: false
  timeline: false
  entities: false
EOF
echo "[4/5] Default configuration created"

# Start
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
echo "[5/5] Shattered KANDOR starting..."

# Wait for health
echo ""
echo "Waiting for application to be ready..."
for i in {1..30}; do
    if curl -sf http://localhost:3000/api/frame/health > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ""
echo "=============================================="
echo "   Shattered KANDOR Deployed Successfully"
echo "=============================================="
echo ""
echo "Access: http://localhost:3000"
echo ""
echo "Enabled shards: dashboard, ach, search"
echo "Edit ~/shattered/config/shattered.yaml to change"
echo ""
echo "Commands:"
echo "  Logs:   docker compose -f docker-compose.prod.yml logs -f"
echo "  Stop:   docker compose -f docker-compose.prod.yml down"
echo "  Update: docker compose -f docker-compose.prod.yml pull && up -d"
echo ""
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-18 | Initial draft - Shattered KANDOR integrated plan |

---

**Document Version**: 1.0
**Based On**: KANDOR_PLAN.md v1.0, Voltron_Plan.md v1.3
**Created**: 2025-12-18
**Status**: Planning / Pre-Development
