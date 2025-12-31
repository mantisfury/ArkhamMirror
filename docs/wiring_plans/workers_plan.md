# Workers & Ports Fix Plan

This document tracks two related issues:
1. **Workers need DATA_SILO_PATH support** - For Docker/portable deployments
2. **Old port numbers** - Legacy ports causing connection failures

**Status: COMPLETED** (2024-12-29)

---

## Part 1: Worker Path Resolution Fixes

### Background
Workers receive `file_path` in job payloads. Previously we used absolute paths which break in Docker
(host: `C:\GitHub\SHATTERED\DataSilo\...` vs container: `/app/DataSilo/...`).

### Solution Pattern
Each worker now has a `_resolve_path()` method:
```python
def _resolve_path(self, file_path: str) -> Path:
    """Resolve file path using DATA_SILO_PATH for Docker/portable deployments."""
    if not os.path.isabs(file_path):
        data_silo = os.environ.get("DATA_SILO_PATH", ".")
        return Path(data_silo) / file_path
    return Path(file_path)
```

### Workers Updated

#### Frame Workers (packages/arkham-frame/arkham_frame/workers/)
| Worker | File | Pool | Status | Notes |
|--------|------|------|--------|-------|
| LightWorker | light_worker.py | cpu-light | DONE | Has inline path resolution |
| DBWorker | db_worker.py | io-db | N/A | Database operations, no file paths |
| EnrichWorker | enrich_worker.py | llm-enrich | N/A | Text-only, no file paths |
| WhisperWorker | whisper_worker.py | gpu-whisper | PENDING | Audio file paths - needs review |
| AnalysisWorker | analysis_worker.py | llm-analysis | N/A | Text-only, no file paths |
| EchoWorker | examples.py | test | N/A | Test worker, no file paths |

#### Ingest Shard Workers (packages/arkham-shard-ingest/arkham_shard_ingest/workers/)
| Worker | File | Pool | Status | Notes |
|--------|------|------|--------|-------|
| ExtractWorker | extract_worker.py | cpu-extract | DONE | Added _resolve_path() |
| FileWorker | file_worker.py | io-file | DONE | Added _resolve_path() for all ops |
| ArchiveWorker | archive_worker.py | cpu-archive | DONE | Added _resolve_path() |
| ImageWorker | image_worker.py | cpu-image | DONE | Added _resolve_path() |

#### OCR Shard Workers (packages/arkham-shard-ocr/arkham_shard_ocr/workers/)
| Worker | File | Pool | Status | Notes |
|--------|------|------|--------|-------|
| PaddleWorker | paddle_worker.py | gpu-paddle | DONE | Added _resolve_path() |
| QwenWorker | qwen_worker.py | gpu-qwen | DONE | Added _resolve_path() |

---

## Part 2: Port Number Fixes

### Port Mapping
| Service | OLD Port | NEW Port | Status |
|---------|----------|----------|--------|
| PostgreSQL | 5435 | 5432 | DONE |
| Redis | 6380 | 6379 | DONE |
| Qdrant | 6343 | 6333 | DONE |

### Files Updated

#### Production Code (COMPLETED)
- `packages/arkham-frame/arkham_frame/services/resources.py` - 3 port fixes
- `packages/arkham-frame/arkham_frame/workers/base.py` - 1 port fix
- `packages/arkham-frame/arkham_frame/workers/examples.py` - 1 port fix
- `packages/arkham-frame/arkham_frame/workers/runner.py` - 1 port fix
- `packages/arkham-frame/arkham_frame/workers/registry.py` - 1 port fix

#### Test Files (COMPLETED)
- `packages/arkham-frame/tests/test_workers.py` - 2 port fixes
- `packages/arkham-frame/tests/test_integration.py` - 2 port fixes
- `packages/arkham-frame/tests/test_e2e_pipeline.py` - 1 port fix

#### Documentation (LOW PRIORITY - NOT UPDATED)
- README.md
- docs/frame_spec.md
- docs/voltron_plan.md
- docs/RESOURCE_DETECTION.md
- packages/arkham-frame/FRAME_SPEC.md

---

## Testing Plan

1. **Port fixes**: Restart services and verify connections
2. **Worker path fixes**:
   - Upload file via ingest API
   - Verify worker processes file correctly
   - Test in Docker environment with different mount paths

---

## Notes

- The `DATA_SILO_PATH` env var is set by `WorkerService._spawn_worker_process()` before spawning
- Workers inherit environment variables from parent process
- For Docker, ensure DATA_SILO_PATH matches the container mount point (`/app/DataSilo`)

## Remaining Work

- WhisperWorker may need DATA_SILO_PATH support if it processes audio files via paths
- NERWorker and EmbedWorker appear to only receive text, not file paths
- Documentation files still have old port numbers (low priority)
