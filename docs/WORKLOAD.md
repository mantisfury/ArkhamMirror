# Shattered Workload Reference

Comprehensive list of work items for Project Shattered.

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Frame (core) | DONE | Services, API, shard loading |
| Dashboard Shard | DONE | Health, LLM config, queue stats |
| Ingest Shard | DONE | Upload, classify, dispatch |
| ACH Shard | DONE | 17+ endpoints, LLM integration complete |
| Search Shard | DONE | 6 endpoints, semantic/keyword/hybrid |
| Parse Shard | DONE | 7 endpoints, NER/dates/locations |
| Embed Shard | DONE | 10 endpoints, vector operations |
| Contradictions Shard | DONE | 16 endpoints, multi-stage detection |
| Anomalies Shard | DONE | 9 endpoints, 6 detection strategies |
| Timeline Shard | DONE | 8 endpoints, date extraction/merging |
| Graph Shard | DONE | 10 endpoints, centrality/communities |
| Worker Pools | DONE | ALL 14 pools implemented |
| Job Queuing | DONE | Redis-backed priority queues |
| Worker Infrastructure | DONE | BaseWorker, Runner, Registry, CLI |
| Worker Tests | DONE | 12 tests passing |

### Summary

- **10 Shards** implemented
- **14 Workers** implemented (13 production + 1 test)
- **~25,000+ lines** of code across shards and workers

---

## 1. Worker Implementations (COMPLETE)

All 14 worker pools are now implemented.

### IO Workers (2/2 COMPLETE)

| Worker | Pool | Purpose | Status |
|--------|------|---------|--------|
| FileWorker | io-file | File read/write, move, copy, stat | DONE |
| DBWorker | io-db | Async PostgreSQL, connection pooling | DONE |

### CPU Workers (6/6 COMPLETE)

| Worker | Pool | Purpose | Status |
|--------|------|---------|--------|
| LightWorker | cpu-light | Text normalization, language detection, quality | DONE |
| SlowWorker | cpu-heavy | Test/example worker | DONE |
| NERWorker | cpu-ner | Entity extraction (spaCy) | DONE |
| ExtractWorker | cpu-extract | PDF/DOCX/XLSX/TXT/EML extraction | DONE |
| ImageWorker | cpu-image | Deskew, enhance, denoise, resize, binarize | DONE |
| ArchiveWorker | cpu-archive | ZIP/TAR/7z/RAR extraction, zip bomb protection | DONE |

### GPU Workers (4/4 COMPLETE)

| Worker | Pool | Purpose | Status |
|--------|------|---------|--------|
| PaddleWorker | gpu-paddle | PaddleOCR with bounding boxes | DONE |
| QwenWorker | gpu-qwen | VLM OCR (LM Studio/Ollama/vLLM) | DONE |
| WhisperWorker | gpu-whisper | Audio transcription (faster-whisper) | DONE |
| EmbedWorker | gpu-embed | BGE-M3/MiniLM embeddings | DONE |

### LLM Workers (2/2 COMPLETE)

| Worker | Pool | Purpose | Status |
|--------|------|---------|--------|
| EnrichWorker | llm-enrich | Summarize, keywords, metadata, classify | DONE |
| AnalysisWorker | llm-analysis | Contradictions, fact-check, speculation, credibility | DONE |

### Worker Infrastructure (COMPLETE)

| Task | Description | Status |
|------|-------------|--------|
| Worker Base Class | Common lifecycle, health checks, metrics | DONE |
| Worker Runner | Process manager, spawn/kill workers | DONE |
| Worker Registry | Track active workers per pool | DONE |
| CLI Entry Point | `python -m arkham_frame.workers` | DONE |
| Test Suite | 12 tests covering all scenarios | DONE |
| Health Monitor | Detect stuck workers, restart | DONE |

---

## 2. Shards Implementation Status

### Core Shards (6/6 COMPLETE)

| Shard | Purpose | Endpoints | Status |
|-------|---------|-----------|--------|
| **Dashboard** | Monitoring, health, config | 7 | DONE |
| **Ingest** | File upload, classify, dispatch | 9 | DONE |
| **Parse** | Entity extraction, NER, linking | 7 | DONE |
| **Search** | Semantic + keyword + hybrid search | 6 | DONE |
| **Embed** | Generate embeddings, vector ops | 10 | DONE |
| **ACH** | Analysis of Competing Hypotheses | 17+ | DONE |

### Analysis Shards (3/6)

| Shard | Purpose | Endpoints | Status |
|-------|---------|-----------|--------|
| **Contradictions** | Find conflicting statements | 16 | DONE |
| **Anomalies** | Detect outliers, unusual patterns | 9 | DONE |
| **Timeline** | Timeline extraction and merging | 8 | DONE |
| RedFlags | Suspicious pattern detection | - | TODO |
| FactCheck | Cross-document fact comparison | - | TODO |
| Narrative | Narrative reconstruction | - | TODO |

### Visualization Shards (1/3)

| Shard | Purpose | Endpoints | Status |
|-------|---------|-----------|--------|
| **Graph** | Entity relationship visualization | 10 | DONE |
| Map | Geospatial visualization | - | TODO |
| Influence | Entity influence mapping | - | TODO |

### Utility Shards (0/5)

| Shard | Purpose | Status |
|-------|---------|--------|
| Export | Export data in various formats | TODO |
| Audio | Audio file transcription | TODO |
| Regex | Pattern search across documents | TODO |
| Duplicates | Find duplicate documents | TODO |
| Metadata | File metadata forensics | TODO |

---

## 3. Package Structure

```
packages/
├── arkham-frame/                    # Core infrastructure (DONE)
│   ├── arkham_frame/
│   │   ├── frame.py                 # Main orchestrator
│   │   ├── shard_interface.py       # ArkhamShard ABC
│   │   ├── main.py                  # FastAPI entry
│   │   ├── services/                # Core services
│   │   ├── workers/                 # 14 workers
│   │   ├── pipeline/                # Document pipeline
│   │   └── api/                     # REST routes
│
├── arkham-shard-dashboard/          # Monitoring (DONE)
├── arkham-shard-ingest/             # File intake (DONE)
├── arkham-shard-parse/              # NER/parsing (DONE)
├── arkham-shard-search/             # Search engines (DONE)
├── arkham-shard-ach/                # ACH analysis (DONE)
├── arkham-shard-embed/              # Embeddings (DONE)
├── arkham-shard-contradictions/     # Contradictions (DONE)
├── arkham-shard-anomalies/          # Anomalies (DONE)
├── arkham-shard-timeline/           # Timeline (DONE)
└── arkham-shard-graph/              # Graph (DONE)
```

---

## 4. Implementation Order

### Phase 1-2: Core Infrastructure - COMPLETE

```
├── Frame core (services, API, shard loading) ✓
├── Dashboard Shard ✓
├── Ingest Shard ✓
└── Shard discovery via entry_points ✓
```

### Phase 3: Workers - COMPLETE

```
├── Worker Infrastructure ✓
│   ├── BaseWorker, Runner, Registry, CLI ✓
│   └── 12 tests passing ✓
├── IO Workers (io-file, io-db) ✓
├── CPU Workers (light, extract, ner, image, archive) ✓
├── GPU Workers (paddle, qwen, whisper, embed) ✓
└── LLM Workers (enrich, analysis) ✓
```

### Phase 4: Core Shards - COMPLETE

```
├── Parse Shard (NER, dates, locations) ✓
├── Search Shard (semantic, keyword, hybrid) ✓
├── ACH Shard (17 endpoints, LLM integration) ✓
└── Embed Shard (embeddings, vector ops) ✓
```

### Phase 5: Analysis Shards - IN PROGRESS

```
├── Contradictions Shard ✓
├── Anomalies Shard ✓
├── Timeline Shard ✓
├── Graph Shard ✓
└── RedFlags Shard - TODO
```

### Phase 6: Polish - TODO

```
├── Remaining shards (Export, Audio, Regex, etc.)
├── Integration testing across shards
├── Performance optimization
├── Documentation
└── UI components
```

---

## 5. Dependency Graph (Updated)

```
                    ┌─────────────┐
                    │   Ingest    │ ✓ DONE
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Extract  │    │   OCR    │    │  Audio   │
    │    ✓     │    │    ✓     │    │    ✓     │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
                  ┌──────────┐
                  │  Parse   │ ✓ DONE
                  │  (NER)   │
                  └────┬─────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  Embed   │  │ Timeline │  │  Graph   │
  │    ✓     │  │    ✓     │  │    ✓     │
  └────┬─────┘  └──────────┘  └──────────┘
       │
       ▼
┌──────────┐
│  Search  │ ✓ DONE
└────┬─────┘
     │
     ├──────────────┬──────────────┐
     ▼              ▼              ▼
┌─────────┐  ┌─────────────┐  ┌──────────┐
│   ACH   │  │Contradictions│  │ Anomalies│
│    ✓    │  │      ✓      │  │    ✓     │
└─────────┘  └─────────────┘  └──────────┘
```

---

## 6. Quick Reference

### Start Workers

```bash
# List available pools (all 14 implemented)
python -m arkham_frame.workers --list-pools

# Start workers for a specific pool
python -m arkham_frame.workers --pool cpu-ner --count 2

# Start all workers based on resource tier
python -m arkham_frame.workers --tier recommended

# Run tests
cd packages/arkham-frame
python tests/test_workers.py           # Smoke test
pytest tests/test_workers.py -v        # Full suite
```

### Start Frame

```bash
cd packages/arkham-frame
pip install -e .
python -m uvicorn arkham_frame.main:app --port 8105
```

### Install a Shard

```bash
pip install -e packages/arkham-shard-embed
# Auto-discovered on next Frame startup
```

### Check Status

```bash
curl http://localhost:8105/health
# Shows all loaded shards and services
```

---

## 7. Next Priority

1. **RedFlags Shard** - Suspicious pattern detection
2. **Map Shard** - Geospatial visualization
3. **Integration Testing** - Cross-shard workflows
4. **UI Components** - React/Vite frontend for shards

---

*Last Updated: 2025-12-21 (All workers complete, 10 shards implemented)*
