# SHATTERED

<div align="center">

![SHATTERED - Intelligence Analysis Platform](docs/Gemini_Generated_Image_4r91tk4r91tk4r91.png)

**A modular intelligence analysis and investigative journalism platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-blue.svg)](https://www.typescriptlang.org/)

[Features](#features) | [Architecture](#architecture) | [Quick Start](#quick-start) | [Documentation](#documentation) | [Support](#support)

</div>

---

## Overview

SHATTERED is a production-ready platform for analysts, journalists, and researchers who need to process large document collections, extract structured information, detect patterns and contradictions, and generate professional reports.

Built on the **Voltron** architectural philosophy, SHATTERED uses a modular "distro-style" design where **shards** (feature modules) plug into a **frame** (core infrastructure). Add only the capabilities you need, or use the full suite for comprehensive intelligence analysis.

### Key Use Cases

- **Investigative Journalism**: Process leaked documents, track entities across sources, detect contradictions in official statements
- **Intelligence Analysis**: Apply proven methodologies like ACH (Analysis of Competing Hypotheses) to evaluate competing theories
- **Legal Discovery**: Ingest large document sets, extract entities and relationships, generate evidence packets
- **Research**: Organize source materials, track claims and provenance, build knowledge graphs

---

## Features

### Document Processing Pipeline
- **Multi-format Ingestion**: PDFs, images, audio files, archives (ZIP, TAR)
- **Intelligent OCR**: PaddleOCR for speed, Qwen-VL for complex layouts
- **Entity Extraction**: Named Entity Recognition with spaCy, relationship detection
- **Vector Embeddings**: Semantic search with BGE models and Qdrant

### Intelligence Analysis Tools
- **ACH Matrices**: Analysis of Competing Hypotheses with evidence rating
- **Contradiction Detection**: Multi-stage analysis (claim extraction, semantic matching, LLM verification)
- **Anomaly Detection**: Identify outliers and unusual patterns
- **Provenance Tracking**: Complete audit trails and evidence chains
- **Credibility Scoring**: Assess source reliability

### Visualization & Discovery
- **Entity Graphs**: Network visualization with PageRank, centrality metrics, community detection
- **Timelines**: Temporal event extraction with conflict detection
- **Hybrid Search**: Semantic + keyword search with Reciprocal Rank Fusion

### Export & Collaboration
- **Professional Reports**: Multiple templates (summary, entity, timeline, ACH)
- **Evidence Packets**: Bundled investigations for archiving and sharing
- **Multi-format Export**: JSON, CSV, PDF, DOCX, Markdown
- **Letter Generation**: FOIA requests, formal complaints

---

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

### Core Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards communicate via events, not imports
3. **Schema Isolation**: Each shard gets its own PostgreSQL schema
4. **Graceful Degradation**: Works with or without AI/GPU capabilities

### Available Shards (25 modules)

| Category | Shards |
|----------|--------|
| **System** | Dashboard, Projects, Settings |
| **Data** | Ingest, OCR, Parse, Documents, Entities |
| **Search** | Search, Embed |
| **Analysis** | ACH, Claims, Provenance, Credibility, Contradictions, Patterns, Anomalies, Summary |
| **Visualize** | Graph, Timeline |
| **Export** | Export, Letters, Templates, Reports, Packets |

---

## Tech Stack

### Backend
- **Python 3.10+** with FastAPI
- **PostgreSQL** for document storage (schema isolation per shard)
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

# Install shards (example: ACH shard)
cd ../arkham-shard-ach
pip install -e .

# Install spaCy model for entity extraction
python -m spacy download en_core_web_sm

# Install UI dependencies
cd ../arkham-shard-shell
npm install
```

### Running

```bash
# Terminal 1: Start the Frame API (auto-discovers installed shards)
cd packages/arkham-frame
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# Terminal 2: Start the UI
cd packages/arkham-shard-shell
npm run dev

# Terminal 3 (optional): Start workers
python -m arkham_frame.workers --pool cpu-light --count 2
```

Access the application:
- **UI**: http://localhost:3100
- **API Docs**: http://localhost:8100/docs

### Configuration

Set environment variables or create a `.env` file:

```bash
DATABASE_URL=postgresql://user:pass@localhost:5435/shattered
REDIS_URL=redis://localhost:6380
QDRANT_URL=http://localhost:6343
LM_STUDIO_URL=http://localhost:1234/v1  # Optional: for AI features
```

Default ports:
| Service | Port |
|---------|------|
| PostgreSQL | 5435 |
| Redis | 6380 |
| Qdrant | 6343 |
| Frame API | 8100 |
| Shell UI | 3100 |

---

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Project guidelines and shard standards |
| [docs/voltron_plan.md](docs/voltron_plan.md) | Architecture overview and implementation status |
| [docs/frame_spec.md](docs/frame_spec.md) | Frame service specifications |
| [docs/WORKER_ARCHITECTURE.md](docs/WORKER_ARCHITECTURE.md) | Worker pool design |
| [docs/SHARD_MANIFEST_SCHEMA_v5.md](docs/SHARD_MANIFEST_SCHEMA_v5.md) | Shard manifest specification |

Each shard includes its own README with API documentation.

---

## Project Status

SHATTERED has completed 7 development phases and is production-ready:

- **1,469+ tests** across all shards
- **25 shards** fully implemented and compliant
- **16 Frame services** operational
- **14 worker pools** for background processing

---

## Support

If you find SHATTERED useful, consider supporting development:

<a href="https://ko-fi.com/arkhammirror">
  <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support on Ko-fi" />
</a>

---

## Contributing

Contributions are welcome! Please read the [CLAUDE.md](CLAUDE.md) file for project guidelines and shard development standards.

When creating a new shard:
1. Use `arkham-shard-ach` as the reference implementation
2. Follow the v5 manifest schema
3. Ensure schema isolation (no direct shard imports)
4. Add comprehensive tests

---

## License

MIT License

Copyright (c) 2024 Justin McHugh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

<div align="center">

**SHATTERED** - *Break documents into pieces. Reassemble the truth.*

</div>
