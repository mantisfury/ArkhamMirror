# SHATTERED

<div align="center">

![SHATTERED - Intelligence Analysis Platform](docs/Gemini_Generated_Image_4r91tk4r91tk4r91.png)

**A modular, local-first platform for document analysis and investigative research**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)](https://www.typescriptlang.org/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)

[Philosophy](#philosophy) | [Architecture](#architecture) | [Features](#features) | [Quick Start](#quick-start) | [Security](#authentication--security) | [Production](#production-deployment) | [Shards](#implemented-shards) | [Documentation](#documentation)

</div>

<details>
<summary><strong>Screenshots</strong> (click to expand)</summary>

<br>

### Dashboard & LLM Configuration
Configure local or cloud LLM providers with one-click switching between LM Studio, Ollama, OpenAI, Groq, and custom endpoints.

![Dashboard](docs/Screens/Dashboard.png)

### ACH Analysis with AI Assistant
Full Analysis of Competing Hypotheses implementation with AI-powered observations, recommendations, and devil's advocate mode.

![ACH Matrix with AI](docs/Screens/ACHmatrixAIassist.png)

### Graph Visualization
Interactive network analysis with 10+ visualization modes including force-directed layouts and geospatial mapping.

| Force-Directed | Geospatial |
|----------------|------------|
| ![Force Graph](docs/Screens/graphforce.png) | ![Geospatial](docs/Screens/geospatialgraph.png) |

### Timeline Analysis
Temporal event extraction with AI-powered analysis, conflict detection, and phase management.

![Timeline](docs/Screens/timeline.png)

### Pattern Detection
Automated pattern recognition across documents with statistical analysis and AI interpretation.

![Patterns](docs/Screens/patterns.png)

### Credibility Assessment
Source reliability scoring with deception detection checklists (MOM, POP, MOSES, EVE).

![Credibility](docs/Screens/credibility.png)

### Search with Regex Presets
Hybrid semantic/keyword search with built-in regex patterns for PII, financial data, and technical indicators.

![Search](docs/Screens/regex.png)

### Media Forensics
Image authenticity analysis with EXIF extraction, Error Level Analysis (ELA), perceptual hashing, and reverse image search integration.

![Media Forensics](docs/Screens/mediaforensics.png)

</details>

---

## Philosophy

SHATTERED isn't a product - it's a **platform**. The shards are the products. Or rather, *bundles* of shards configured for specific use cases.

**Core Principles:**

- **Build domain-agnostic infrastructure** that supports domain-specific applications
- **Lower the bar for contribution** so non-coders can build custom shards
- **Provide utility to people in need**, not just those who can pay
- **Local-first**: Your data never leaves your machine unless you want it to
- **Privacy-preserving**: No telemetry, no cloud dependencies, full data sovereignty

---

## The Meta-Pattern

Every investigative workflow follows the same fundamental pattern:

```
INGEST --> EXTRACT --> ORGANIZE --> ANALYZE --> ACT
  |          |           |            |          |
  |          |           |            |          +-- Export, Generate, Notify
  |          |           |            +-- ACH, Contradictions, Patterns, Anomalies
  |          |           +-- Timeline, Graph, Matrix, Provenance
  |          +-- Entities, Claims, Events, Relationships
  +-- Documents, Data, Communications, Records
```

- **Core shards** handle INGEST and EXTRACT
- **Domain shards** handle ORGANIZE and ANALYZE
- **Output shards** handle ACT

---

## Architecture

SHATTERED uses the **Voltron** architectural philosophy: a modular, plug-and-play system where self-contained shards combine into a unified application.

```
                    +------------------+
                    |   ArkhamFrame    |    <-- THE FRAME (immutable core)
                    |   (17 Services)  |
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
   |Dashboard| | ACH | |  Search   | |Graph| |Timeline|  <-- SHARDS (26)
   +---------+ +-----+ +-----------+ +-----+ +--------+
```

### Core Design Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards communicate via events, not imports
3. **Schema Isolation**: Each shard gets its own PostgreSQL schema
4. **Graceful Degradation**: Works with or without AI/GPU capabilities
5. **Event-Driven Architecture**: Loose coupling through pub/sub messaging

---

## Features

### AI-Powered Analysis

| Feature | Description |
|---------|-------------|
| **AI Junior Analyst** | LLM-powered analysis across all shards - anomaly detection, contradiction finding, pattern recognition, credibility assessment, and insight synthesis |
| **LLM Summarization** | Automatic document and corpus summarization with multiple formats (brief, standard, detailed, executive, key points) |
| **Deception Detection** | AI-assisted credibility assessment using MOM, POP, MOSES, and EVE checklists |
| **Query Expansion** | Semantic search enhancement via LLM |
| **Devil's Advocate** | AI-generated counter-arguments for ACH analysis |

### Structured Analytic Techniques

| Technique | Capabilities |
|-----------|-------------|
| **ACH (Analysis of Competing Hypotheses)** | Full matrix analysis, evidence scoring, premortem analysis, cone of plausibility, corpus search integration, scenario planning, devil's advocate mode |
| **Contradiction Detection** | Automated identification of conflicting claims across documents with severity scoring and resolution tracking |
| **Pattern Recognition** | Recurring patterns, behavioral patterns, temporal patterns, correlation analysis with statistical significance |
| **Anomaly Detection** | Statistical anomalies, contextual anomalies, collective anomalies with LLM-powered analysis |
| **Credibility Assessment** | Source reliability scoring, bias indicators, deception detection checklists |
| **Provenance Tracking** | Evidence chains, data lineage, audit trails, artifact verification |

### Advanced Visualization

**Graph Analysis** - 10+ visualization modes:

| Mode | Description |
|------|-------------|
| Force-Directed | Interactive network layout with physics simulation |
| Hierarchical | Tree-based layouts (top-down, bottom-up, radial) |
| Circular | Entities arranged in circular patterns |
| Sankey | Flow diagrams showing relationships and quantities |
| Matrix | Adjacency matrix for dense relationship analysis |
| Geographic | Map overlays with Leaflet integration |
| Causal | Cause-and-effect relationship visualization |
| Argumentation | ACH integration showing evidence-hypothesis relationships |
| Link Analysis | i2 Analyst Notebook-style investigation graphs |
| Temporal | Time-based graph evolution |

**Graph Analytics:**
- Centrality measures (degree, betweenness, closeness, eigenvector, PageRank)
- Community detection algorithms
- Path finding (shortest path, all paths, critical paths)
- Cycle detection
- Component analysis

**Timeline Analysis:**
- Temporal event extraction and visualization
- Date normalization across formats
- Conflict detection for overlapping events
- Phase/period management
- Gap analysis
- Event clustering

### Document Processing Pipeline

| Stage | Capabilities |
|-------|-------------|
| **Ingest** | Multi-format support (PDF, DOCX, images, HTML, TXT), batch processing, duplicate detection, job queue management |
| **OCR** | PaddleOCR for standard OCR, Vision LLM for complex documents (supports local Qwen-VL or cloud APIs like GPT-4o), language detection, confidence scoring |
| **Parse** | 8 chunking strategies, metadata extraction, relations extraction, table detection |
| **Embed** | Multiple embedding models, batch processing, incremental updates |
| **Entity Extraction** | spaCy-powered NER (PERSON, ORG, GPE, DATE, etc.), relationship detection, duplicate merging |
| **Claim Extraction** | Factual claim identification, source attribution, verification status tracking |

### Search Capabilities

| Type | Description |
|------|-------------|
| **Semantic Search** | Vector similarity using pgvector embeddings |
| **Keyword Search** | PostgreSQL full-text search with BM25 ranking |
| **Hybrid Search** | Combined semantic + keyword with configurable weights |
| **Similarity Search** | Find documents similar to a reference document |
| **Faceted Search** | Filter by project, document type, date range, entities |

### Export & Reporting

| Feature | Formats |
|---------|---------|
| **Data Export** | JSON, CSV, PDF, DOCX |
| **Analytical Reports** | Investigation summaries, entity profiles, timeline reports, ACH reports |
| **Letters** | FOIA requests, complaints, legal correspondence with templates |
| **Packets** | Complete investigation bundles with versioning and sharing |
| **Templates** | Jinja2-based template system with placeholder validation |

---

## Frame Services

The Frame provides 17 core services available to all shards:

| Service | Description |
|---------|-------------|
| **ConfigService** | Environment + YAML configuration management |
| **ResourceService** | Hardware detection, GPU/CPU management, tier assignment |
| **StorageService** | File/blob storage with categories and lifecycle |
| **DatabaseService** | PostgreSQL with per-shard schema isolation |
| **VectorService** | pgvector-based vector storage for embeddings and similarity search |
| **LLMService** | OpenAI-compatible LLM integration (LM Studio, Ollama, vLLM) |
| **ChunkService** | 8 text chunking strategies (semantic, sentence, fixed, etc.) |
| **EventBus** | Pub/sub messaging for inter-shard communication |
| **WorkerService** | PostgreSQL-based job queues (SKIP LOCKED) with specialized worker pools |
| **DocumentService** | Document CRUD with content and metadata access |
| **EntityService** | Entity extraction, relationships, and deduplication |
| **ProjectService** | Project organization and management |
| **ExportService** | Multi-format export (JSON, CSV, PDF, DOCX) |
| **TemplateService** | Jinja2 template rendering and management |
| **NotificationService** | Email, webhook, and log notifications |
| **SchedulerService** | APScheduler-based job scheduling |
| **AIJuniorAnalystService** | LLM-powered cross-shard analysis |

---

## Implemented Shards

### System (3 shards)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **Dashboard** | System monitoring and administration | Service health, database stats, worker management, event log, LLM configuration |
| **Projects** | Project organization | Project CRUD, document organization, bulk operations |
| **Settings** | Application configuration | 7 setting categories, import/export, reset capabilities |

### Data Pipeline (6 shards)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **Ingest** | Document ingestion | Multi-format support, batch processing, job queue, duplicate detection |
| **Documents** | Document management | CRUD operations, content access, metadata, batch operations |
| **Parse** | Document parsing | 8 chunking strategies, relations extraction, table detection |
| **Embed** | Vector embeddings | Multiple models, batch processing, incremental updates |
| **OCR** | Text extraction | PaddleOCR, Vision LLM (local or cloud), language detection, confidence scoring |
| **Entities** | Entity management | NER extraction, relationships, deduplication, type management |

### Search (1 shard)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **Search** | Document search | Semantic, keyword, hybrid search, facets, suggestions |

### Analysis (9 shards)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **ACH** | Analysis of Competing Hypotheses | Matrix analysis, premortem, cone of plausibility, corpus search, scenarios |
| **Claims** | Claim extraction | Document extraction, verification status, source attribution |
| **Credibility** | Source assessment | Reliability scoring, bias detection, deception checklists (MOM/POP/MOSES/EVE) |
| **Contradictions** | Conflict detection | Cross-document analysis, severity scoring, resolution tracking |
| **Anomalies** | Anomaly detection | Statistical, contextual, collective anomalies, LLM analysis |
| **Patterns** | Pattern recognition | Recurring, behavioral, temporal, correlation patterns |
| **Provenance** | Evidence chains | Data lineage, audit trails, artifact verification |
| **Summary** | Auto-summarization | Multiple summary types, batch processing, auto-summarize on ingest |
| **Media Forensics** | Image authenticity analysis | EXIF extraction, ELA analysis, perceptual hashing, C2PA verification, reverse image search |

### Visualization (2 shards)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **Graph** | Network visualization | 10+ layout modes, analytics, cross-shard integration |
| **Timeline** | Temporal visualization | Event extraction, date normalization, phases, gap detection |

### Export (5 shards)

| Shard | Description | Key Features |
|-------|-------------|--------------|
| **Export** | Data export | JSON, CSV, PDF, DOCX, job management |
| **Reports** | Report generation | Multiple report types, templates, scheduling |
| **Letters** | Letter generation | FOIA, complaints, legal templates |
| **Packets** | Investigation bundles | Versioning, sharing, access control |
| **Templates** | Template management | Jinja2 syntax, versioning, validation |

---

## Tech Stack

### Backend

| Component | Technology |
|-----------|------------|
| **Runtime** | Python 3.10+ |
| **API Framework** | FastAPI with async/await |
| **Database** | PostgreSQL 14+ with pgvector extension |
| **Job Queue** | PostgreSQL (SKIP LOCKED pattern) |
| **Vector Store** | pgvector (PostgreSQL extension) |

### Frontend

| Component | Technology |
|-----------|------------|
| **Framework** | React 18 + TypeScript 5 |
| **Build Tool** | Vite |
| **Styling** | TailwindCSS + shadcn/ui |
| **Icons** | Lucide React |
| **State** | URL state + local storage |
| **Charts** | Recharts |
| **Maps** | Leaflet |

### AI/ML (Optional)

| Component | Options |
|-----------|---------|
| **LLM Inference** | LM Studio, Ollama, vLLM, OpenAI API |
| **NER** | spaCy (en_core_web_sm/lg/trf) |
| **OCR** | PaddleOCR, Vision LLM (Qwen-VL local, or cloud GPT-4o/Claude) |
| **Embeddings** | sentence-transformers, OpenAI |
| **Reverse Image Search** | TinEye, Google Vision, SerpAPI (optional APIs for Media Forensics) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for local UI development only)
- PostgreSQL 14+ with pgvector extension

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/SHATTERED.git
cd SHATTERED

# Install the Frame
cd packages/arkham-frame
pip install -e .

# Install all shards (or select specific ones)
for dir in ../arkham-shard-*/; do
  pip install -e "$dir"
done

# Install spaCy model
python -m spacy download en_core_web_sm

# Install UI dependencies
cd ../arkham-shard-shell
npm install
```

### Configuration

Create a `.env` file or set environment variables:

```bash
# Required - PostgreSQL with pgvector extension
DATABASE_URL=postgresql://user:pass@localhost:5432/shattered

# Optional - LLM Integration (OpenAI-compatible endpoint)
LLM_ENDPOINT=http://localhost:1234/v1
LLM_API_KEY=your-api-key

# Optional - Embedding Model (default: all-MiniLM-L6-v2)
EMBED_MODEL=all-MiniLM-L6-v2

# Optional - Vision LLM for OCR
VLM_ENDPOINT=http://localhost:1234/v1

# Optional - Auth (required for production)
AUTH_SECRET_KEY=generate-with-openssl-rand-hex-32
```

### Running

```bash
# Terminal 1: Start the Frame API (auto-discovers installed shards)
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Terminal 2 (optional): Start the UI for development
cd packages/arkham-shard-shell
npm run dev

# Workers start automatically with the Frame
# Background jobs use PostgreSQL SKIP LOCKED pattern
```

### Access Points

| Interface | URL |
|-----------|-----|
| **Web UI** | http://localhost:8100 (served by Frame) |
| **API Documentation** | http://localhost:8100/docs |
| **OpenAPI Spec** | http://localhost:8100/openapi.json |
| **Health Check** | http://localhost:8100/api/health |

### Docker Deployment (Recommended)

```bash
# Copy environment template
cp .env.example .env

# Generate a secure auth key
python -c "import secrets; print('AUTH_SECRET_KEY=' + secrets.token_urlsafe(32))"
# Add the output to your .env file

# Start all services (PostgreSQL + App)
docker compose up -d

# Access the application
open http://localhost:8100
```

The Docker setup includes:
- PostgreSQL 14 with pgvector extension pre-installed
- All shards and the UI bundled in a single container
- Automatic database migrations on startup
- No external dependencies (Redis, Qdrant not required)

**First-time Setup**: When you first access the application, you'll be prompted to create an admin account. This sets up your tenant and initial credentials.

---

## Authentication & Security

SHATTERED includes built-in authentication and multi-tenant support.

### Initial Setup

1. **Start the application** using Docker or manual installation
2. **Navigate to the app** - you'll be redirected to the setup wizard
3. **Create your tenant** - enter organization name and admin credentials
4. **Log in** with your new admin account

### User Roles

| Role | Capabilities |
|------|--------------|
| **Admin** | Full access: user management, settings, audit logs |
| **Analyst** | Read/write access to all analysis features |
| **Viewer** | Read-only access to documents and analyses |

### Environment Variables

Add these to your `.env` file:

```env
# REQUIRED: Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
AUTH_SECRET_KEY=your-secure-random-key

# Optional: JWT token lifetime (default: 3600 seconds = 1 hour)
JWT_LIFETIME_SECONDS=3600

# Optional: Rate limiting
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_UPLOAD=20/minute
RATE_LIMIT_AUTH=10/minute

# Optional: CORS origins (comma-separated, defaults to localhost)
CORS_ORIGINS=https://your-domain.com
```

### Managing Users

Admins can manage users at **Settings → Users**:
- Create new users with email, password, and role
- Edit user roles and display names
- Deactivate/reactivate accounts
- View user activity

### Audit Logging

All security-relevant actions are logged:
- User creation, updates, deletion
- Role changes
- Login attempts (coming soon)

View the audit log at **Settings → Audit Log** (admin only).

---

## Production Deployment

For production deployments with HTTPS, SHATTERED includes Traefik integration.

### Prerequisites

1. A domain name pointing to your server
2. Ports 80 and 443 open for Let's Encrypt verification
3. Docker and Docker Compose installed

### Setup

```bash
# 1. Configure environment
cp .env.example .env

# Edit .env and set:
# - AUTH_SECRET_KEY (generate a secure key)
# - DOMAIN=your-domain.com
# - ACME_EMAIL=admin@your-domain.com

# 2. Create certificate storage
mkdir -p traefik
touch traefik/acme.json
chmod 600 traefik/acme.json

# 3. Start with HTTPS
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

### What Traefik Provides

- **Automatic HTTPS** via Let's Encrypt (auto-renewing)
- **HTTP → HTTPS redirect** for all traffic
- **Security headers** (HSTS, CSP, X-Frame-Options)
- **Modern TLS** (TLS 1.2+ only, strong ciphers)

### Verify Deployment

```bash
# Check HTTPS is working
curl -I https://your-domain.com

# Check HTTP redirects
curl -I http://your-domain.com
# Should return 301 redirect to HTTPS

# Check security headers
curl -I https://your-domain.com | grep -i "strict-transport"
```

### Traefik Dashboard (Optional)

To enable the Traefik dashboard:

```bash
# Generate password hash
htpasswd -nb admin your-password

# Add to .env
TRAEFIK_DASHBOARD=true
TRAEFIK_DASHBOARD_AUTH=admin:$apr1$...  # output from htpasswd

# Access at https://traefik.your-domain.com
```

---

## Air-Gap Deployment

SHATTERED is **100% air-gap capable** when configured correctly. Deploy in isolated networks with no internet access.

### Requirements

- PostgreSQL 14+ with pgvector extension
- Local LLM server (LM Studio, Ollama, or vLLM)
- Pre-cached embedding models

### Setup Steps

#### 1. Pre-cache Embedding Models

On a **connected machine**:

```bash
# Start the application
docker compose up -d

# Navigate to Settings → ML Models
# Download desired embedding models using the UI

# Models are cached in: ~/.cache/huggingface/hub
```

Copy the cache directory to your air-gapped system.

#### 2. Configure Environment

```bash
# .env for air-gapped deployment
DATABASE_URL=postgresql://user:pass@localhost:5432/shattered

# Enable offline mode (prevents model download attempts)
ARKHAM_OFFLINE_MODE=true

# Custom model cache location (if different from default)
ARKHAM_MODEL_CACHE=/path/to/huggingface/hub

# Local LLM endpoint
LLM_ENDPOINT=http://localhost:1234/v1

# Vision LLM for OCR (optional)
VLM_ENDPOINT=http://localhost:1234/v1
```

#### 3. Local LLM Options

| Server | Default Endpoint | Notes |
|--------|-----------------|-------|
| LM Studio | `http://localhost:1234/v1` | GUI-based, easy setup |
| Ollama | `http://localhost:11434/v1` | CLI-based, many models |
| vLLM | `http://localhost:8000/v1` | High-performance serving |

#### 4. Feature Availability

| Feature | Air-Gap Status | Notes |
|---------|----------------|-------|
| Document Processing | Full | PDF, DOCX, images, etc. |
| OCR | Full | PaddleOCR works offline |
| Vision LLM OCR | Full | Requires local VLM (e.g., Qwen-VL) |
| Embeddings | Full | Pre-cache models first |
| Semantic Search | Full | pgvector is fully local |
| Entity Extraction | Full | spaCy models are local |
| LLM Analysis | Full | Requires local LLM server |
| **Geo View** | **Limited** | Requires internet for map tiles* |

*The **Geo View** tab in the Graph page fetches map tiles from OpenStreetMap. For full air-gap operation:
- Avoid using the Geo View tab (all other graph views work offline)
- For advanced users: set up a local tile server with offline OpenStreetMap data

### Air-Gap Verification

After deployment, verify no external connections:

```bash
# Monitor network traffic (Linux)
ss -tuln | grep ESTAB

# Or use netstat
netstat -an | grep ESTABLISHED

# The only connections should be to:
# - localhost (PostgreSQL, LLM server)
# - Your local network (if applicable)
```

---

## Use Cases

SHATTERED supports diverse investigative workflows:

### Journalism & OSINT

- **Social Media Analysis**: Archive posts, extract entities, map networks
- **FOIA Tracking**: Request templates, deadline tracking, response analysis
- **Source Verification**: Credibility assessment, claim verification, contradiction detection
- **Publication Prep**: Claim extraction, citation tracing, fact-check reports

### Legal Self-Advocacy

- **Tenant Defense**: Violation chronology, housing code matching, evidence packets
- **Employment Rights**: Incident documentation, labor law elements, EEOC prep
- **Consumer Protection**: Warranty extraction, demand letters, small claims prep
- **Case Building**: Timeline construction, evidence organization, pattern identification

### Healthcare Self-Advocacy

- **Chronic Illness Management**: Lab results parsing, symptom tracking, treatment analysis
- **Insurance Appeals**: Denial tracking, appeal letters, medical necessity documentation
- **Diagnosis Research**: Test organization, symptom progression, specialist prep

### Civic Engagement

- **Government Oversight**: Meeting minutes parsing, vote tracking, promise vs action analysis
- **Campaign Finance**: Donor identification, bundling detection, money flow mapping
- **Policy Analysis**: Document comparison, stakeholder mapping, impact assessment

### Financial Analysis

- **Fraud Detection**: Benford analysis, transaction anomalies, duplicate detection
- **Investment Research**: SEC filings analysis, financial statement parsing, news tracking
- **Audit Support**: Evidence chains, provenance tracking, documentation verification

### Intelligence Analysis

- **Structured Analysis**: ACH matrices, alternative hypotheses, scenario planning
- **Link Analysis**: Entity relationships, network mapping, path analysis
- **Temporal Analysis**: Event timelines, pattern detection, prediction support

---

## Development

### Creating a New Shard

1. Use `arkham-shard-ach` as reference implementation
2. Follow the manifest schema in `docs/shard_manifest_schema_prod.md`
3. Implement the `ArkhamShard` interface from the Frame
4. No direct shard imports - use events for inter-shard communication
5. Add comprehensive tests

### Shard Structure

```
packages/arkham-shard-{name}/
+-- pyproject.toml          # Package definition with entry point
+-- shard.yaml              # Manifest (navigation, events, capabilities)
+-- README.md               # Documentation
+-- arkham_shard_{name}/
    +-- __init__.py         # Exports {Name}Shard class
    +-- shard.py            # Shard implementation
    +-- api.py              # FastAPI routes
    +-- models.py           # Pydantic models (optional)
    +-- services/           # Business logic (optional)
```

### Testing

```bash
# Run all tests
pytest

# Run specific shard tests
pytest packages/arkham-shard-ach/tests/

# Type checking
mypy packages/arkham-frame/
mypy packages/arkham-shard-ach/

# Linting
ruff check packages/
```

### API Development

All shards expose REST APIs that are auto-documented via FastAPI:

```python
from fastapi import APIRouter, Depends
from arkham_frame import get_frame

router = APIRouter(prefix="/api/myshard", tags=["myshard"])

@router.get("/items")
async def list_items(frame=Depends(get_frame)):
    # Access frame services
    db = frame.db
    events = frame.events
    llm = frame.llm  # Optional service
    return {"items": [...]}
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [SECURITY.md](SECURITY.md) | Security best practices and deployment guide |
| [CLAUDE.md](CLAUDE.md) | Project guidelines and development standards |
| [docs/voltron_plan.md](docs/voltron_plan.md) | Architecture deep-dive |
| [docs/shard_manifest_schema_prod.md](docs/shard_manifest_schema_prod.md) | Production manifest schema |
| [packages/arkham-frame/README.md](packages/arkham-frame/README.md) | Frame services documentation |
| [packages/arkham-shard-shell/README.md](packages/arkham-shard-shell/README.md) | UI shell documentation |

Each shard has its own README with API documentation, events, and usage examples.

---

## Project Status

| Metric | Value |
|--------|-------|
| **Lines of Code** | ~217,000 |
| **Total Packages** | 27 (26 shards + shell) |
| **Frame Services** | 17 |
| **API Endpoints** | 400+ |
| **Graph Visualization Modes** | 10+ |
| **Chunking Strategies** | 8 |
| **Infrastructure** | PostgreSQL-only (pgvector + SKIP LOCKED) |

### Recent Major Features

- **PostgreSQL-only architecture** - Eliminated Redis and Qdrant dependencies
- **pgvector integration** - Native PostgreSQL vector search
- AI Junior Analyst integration across all analysis shards
- Full ACH implementation with premortem, cone of plausibility, corpus search
- Link Analysis mode (i2-style) for graph visualization
- Deception detection with MOM/POP/MOSES/EVE checklists
- Evidence chain provenance tracking
- Shared template system for exports

---

## Support

If you find SHATTERED useful, consider supporting development:

<a href="https://ko-fi.com/arkhammirror">
  <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support on Ko-fi" />
</a>

---

## Contributing

Contributions welcome! See [CLAUDE.md](CLAUDE.md) for project guidelines.

**Ways to contribute:**

1. **Bug Reports**: Open issues with reproduction steps
2. **Feature Requests**: Describe your use case
3. **Code**: Follow the shard development guidelines
4. **Documentation**: Help improve guides and examples
5. **Bundles**: Create pre-configured shard bundles for specific use cases

---

## License

MIT License - Copyright (c) 2025-2026 Justin McHugh

See [LICENSE](LICENSE) for details.

---

<div align="center">

**SHATTERED** - *Break documents into pieces. Reassemble the truth.*

Built for journalists, investigators, advocates, and anyone seeking truth in documents.

</div>
