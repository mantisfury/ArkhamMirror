# SHATTERED

<div align="center">

![SHATTERED - Intelligence Analysis Platform](docs/Gemini_Generated_Image_4r91tk4r91tk4r91.png)

**A modular, local-first platform for document analysis and investigative research**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-blue.svg)](https://www.typescriptlang.org/)

[Philosophy](#philosophy) | [Architecture](#architecture) | [Use Cases](#use-cases) | [Quick Start](#quick-start) | [Documentation](#documentation)

</div>

---

## Philosophy

SHATTERED isn't a product — it's a **platform**. The shards are the products. Or rather, *bundles* of shards configured for specific use cases.

**Core Principles:**

- **Build domain-agnostic infrastructure** that supports domain-specific applications
- **Lower the bar for contribution** so non-coders can build custom shards
- **Provide utility to people in need**, not just those who can pay
- **Local-first**: data never leaves your machine unless you want it to

---

## The Meta-Pattern

Every workflow follows the same fundamental pattern:

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

---

## Architecture

SHATTERED uses the **Voltron** architectural philosophy: a modular, plug-and-play system where self-contained shards combine into a unified application.

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

### Core Design Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards communicate via events, not imports
3. **Schema Isolation**: Each shard gets its own PostgreSQL schema
4. **Graceful Degradation**: Works with or without AI/GPU capabilities

---

## Use Cases

SHATTERED supports 67 pre-configured bundles across 17 user bases. Here are some examples:

### Journalists & Investigators
| Bundle | Purpose |
|--------|---------|
| **OSINT Kit** | Social media archiving, entity correlation, network mapping |
| **FOIA Tracker** | Request templates, deadline tracking, response analysis |
| **Publication Prep** | Claim extraction, citation tracing, fact-check reports |

### Legal Self-Advocacy
| Bundle | Purpose |
|--------|---------|
| **Tenant Defense** | Violation chronology, housing code matching, evidence packets |
| **Employment Rights** | Incident documentation, labor law elements, EEOC prep |
| **Consumer Protection** | Warranty extraction, demand letters, small claims prep |

### Healthcare Self-Advocacy
| Bundle | Purpose |
|--------|---------|
| **Chronic Illness Manager** | Lab results parsing, symptom tracking, treatment analysis |
| **Insurance Fighter** | Denial tracking, appeal letters, medical necessity docs |
| **Diagnosis Quest** | Test organization, symptom progression, specialist prep |

### Civic Engagement
| Bundle | Purpose |
|--------|---------|
| **Local Government Watch** | Meeting minutes parsing, vote tracking, promise vs action |
| **Campaign Finance** | Donor identification, bundling detection, money flow mapping |

### Financial Analysis
| Bundle | Purpose |
|--------|---------|
| **Fraud Detection** | Benford analysis, transaction anomalies, duplicate detection |
| **Investment Research** | SEC filings, financial statement analysis, news tracking |

See [SHARDS_AND_BUNDLES.md](SHARDS_AND_BUNDLES.md) for the complete list of 67 bundles.

---

## Current Implementation

### Frame Services (16 services)

| Service | Description |
|---------|-------------|
| **ConfigService** | Environment + YAML configuration |
| **ResourceService** | Hardware detection, GPU/CPU management, tier assignment |
| **StorageService** | File/blob storage with categories |
| **DatabaseService** | PostgreSQL with schema isolation |
| **VectorService** | Qdrant vector store for embeddings |
| **LLMService** | OpenAI-compatible LLM integration |
| **ChunkService** | 8 text chunking strategies |
| **EventBus** | Pub/sub for inter-shard communication |
| **WorkerService** | Redis job queues with 14 worker pools |
| **DocumentService** | Document CRUD with content access |
| **EntityService** | Entity extraction and relationships |
| **ProjectService** | Project management |
| **ExportService** | Multi-format export (JSON, CSV, PDF, DOCX) |
| **TemplateService** | Jinja2 template management |
| **NotificationService** | Email/Webhook/Log notifications |
| **SchedulerService** | APScheduler job scheduling |

### Implemented Shards (25 shards)

| Category | Shards |
|----------|--------|
| **System** | Dashboard, Projects, Settings |
| **Data** | Ingest, OCR, Parse, Documents, Entities |
| **Search** | Search, Embed |
| **Analysis** | ACH, Claims, Provenance, Credibility, Contradictions, Patterns, Anomalies, Summary |
| **Visualize** | Graph, Timeline |
| **Export** | Export, Letters, Templates, Reports, Packets |

### Roadmap (58 total shards planned)

See [SHARDS_AND_BUNDLES.md](SHARDS_AND_BUNDLES.md) for the complete shard inventory and build priority.

---

## Tech Stack

### Backend
- **Python 3.10+** with FastAPI
- **PostgreSQL** for document storage
- **Redis** for job queues (14 worker pools)
- **Qdrant** for vector search

### Frontend
- **React** + **TypeScript** with Vite
- **TailwindCSS** for styling

### AI/ML (Optional)
- **LM Studio** / **Ollama** / **vLLM** for LLM inference
- **spaCy** for NER
- **PaddleOCR** + **Qwen-VL** for OCR
- **sentence-transformers** for embeddings

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL
- Redis
- Qdrant (for vector search)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/SHATTERED.git
cd SHATTERED

# Install the Frame
cd packages/arkham-frame
pip install -e .

# Install shards you need
cd ../arkham-shard-ach
pip install -e .

# Install spaCy model
python -m spacy download en_core_web_sm

# Install UI
cd ../arkham-shard-shell
npm install
```

### Running

```bash
# Terminal 1: Start the Frame API
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Terminal 2: Start the UI
cd packages/arkham-shard-shell
npm run dev

# Terminal 3 (optional): Start workers
python -m arkham_frame.workers --pool cpu-light --count 2
```

**Access:**
- UI: http://localhost:3100
- API Docs: http://localhost:8100/docs

### Configuration

```bash
DATABASE_URL=postgresql://user:pass@localhost:5435/shattered
REDIS_URL=redis://localhost:6380
QDRANT_URL=http://localhost:6343
LM_STUDIO_URL=http://localhost:1234/v1  # Optional
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [SHARDS_AND_BUNDLES.md](SHARDS_AND_BUNDLES.md) | Complete shard inventory and use-case bundles |
| [full_frame_plan.md](full_frame_plan.md) | Frame implementation details and service specs |
| [docs/shard_manifest_schema_prod.md](docs/shard_manifest_schema_prod.md) | Production manifest schema for shard development |
| [CLAUDE.md](CLAUDE.md) | Project guidelines and development standards |
| [docs/voltron_plan.md](docs/voltron_plan.md) | Architecture overview |

---

## Project Status

- **25 production-ready shards** implemented
- **16 Frame services** operational
- **1,469+ tests** across all components
- **7 development phases** complete

---

## Support

If you find SHATTERED useful, consider supporting development:

<a href="https://ko-fi.com/arkhammirror">
  <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support on Ko-fi" />
</a>

---

## Contributing

Contributions welcome! See [CLAUDE.md](CLAUDE.md) for project guidelines.

**Creating a new shard:**
1. Use `arkham-shard-ach` as reference implementation
2. Follow the [production manifest schema](docs/shard_manifest_schema_prod.md)
3. No direct shard imports — use events for communication
4. Add comprehensive tests

---

## License

MIT License - Copyright (c) 2024 Justin McHugh

See [LICENSE](LICENSE) for details.

---

<div align="center">

**SHATTERED** — *Break documents into pieces. Reassemble the truth.*

</div>
