# Ingest Pipeline Optimization Plan

## Overview
Improvements to the ingest → OCR pipeline based on 2025 best practices research.

## Status Legend
- [ ] Not started
- [x] Completed
- [~] In progress
- [SKIP] Deferred (too complex or low ROI)

---

## Phase 1: Quick Wins (Low Effort, High Impact)

### 1.1 Deduplication at Intake
**Status:** [x]
**Files:** `intake.py`
**Effort:** Low
**Impact:** High - skip redundant processing

Added:
- `_checksums: dict[str, str]` tracking hash → job_id
- Duplicate check after checksum calculation
- Returns existing job if duplicate found
- Temp file cleanup on duplicate detection

### 1.2 Early Validation
**Status:** [x]
**Files:** `intake.py`, `shard.py`
**Effort:** Low
**Impact:** Medium - prevent wasted compute

Added `_validate_file()` method:
- Minimum file size check (configurable, default 100 bytes)
- Maximum file size check (configurable, default 100MB)
- PIL.Image.verify() for images
- pypdf page count check for PDFs
- Config keys: `ingest_min_file_size_bytes`, `ingest_max_file_size_mb`, `ingest_enable_validation`

### 1.3 Parallel Page OCR
**Status:** [x]
**Files:** `packages/arkham-shard-ocr/arkham_shard_ocr/shard.py`
**Effort:** Low
**Impact:** High - faster multi-page documents

Changed `ocr_document()` to parallel processing:
- Uses `asyncio.gather()` for concurrent page OCR
- Semaphore-based concurrency control
- Configurable limit via `ocr_parallel_pages` (default: 4)

---

## Phase 2: Accuracy Improvements (Medium Effort, High Impact)

### 2.1 Confidence-Based Escalation
**Status:** [x]
**Files:** `packages/arkham-shard-ocr/arkham_shard_ocr/shard.py`, `paddle_worker.py`
**Effort:** Medium
**Impact:** High - better accuracy on difficult documents

Added:
- Average confidence calculation in PaddleWorker result
- Escalation logic in `ocr_page()` - if confidence < threshold, re-OCR with Qwen
- Emits `ocr.escalation` event for tracking
- Config keys: `ocr_confidence_threshold` (default 0.8), `ocr_enable_escalation` (default True)
- Result includes `escalated`, `original_engine`, `original_confidence` fields

### 2.2 Result Caching
**Status:** [x]
**Files:** `packages/arkham-shard-ocr/arkham_shard_ocr/shard.py`
**Effort:** Medium
**Impact:** High - skip re-processing identical images

Added:
- In-memory TTL cache keyed by `{checksum}:{engine}`
- `_get_file_checksum()`, `_cache_get()`, `_cache_set()` methods
- `get_cache_stats()` and `clear_cache()` public methods
- Config keys: `ocr_enable_cache` (default True), `ocr_cache_ttl_days` (default 7)
- Results include `from_cache` field

---

## Phase 3: Resource Optimization (Low-Medium Effort, Medium Impact)

### 3.1 DPI-Based Downscaling
**Status:** [x]
**Files:** `models.py`, `image_quality.py`, `workers/image_worker.py`
**Effort:** Low
**Impact:** Medium - 60% memory reduction

Added:
- `needs_downscale` and `downscale_factor` properties to `ImageQualityScore`
- Route now prepends `cpu-image:downscale` for images > 200 DPI
- New `_downscale()` operation in ImageWorker
- Reports memory reduction percentage in result

### 3.2 Batch Job Staggering
**Status:** [x]
**Files:** `api.py`
**Effort:** Low
**Impact:** Low - prevents GPU overload on large batches

Added:
- Constants: `BATCH_STAGGER_THRESHOLD=10`, `BATCH_STAGGER_SIZE=10`, `BATCH_STAGGER_DELAY=0.5`
- Stagger logic in `upload_batch()` and `ingest_from_path()`
- Only activates for batches > threshold

---

## Phase 4: Advanced Features (Higher Effort)

### 4.1 Strategic Cropping / ROI Detection
**Status:** [SKIP]
**Reason:** High complexity, requires ML model for border/margin detection
**Impact:** Medium - 30% accuracy improvement per research

Would need:
- Border/margin detection model
- Content region extraction
- Integration into preprocessing pipeline

**Recommendation:** Revisit after core optimizations are stable.

### 4.2 Blank Page Detection
**Status:** [x]
**Files:** `models.py`, `image_quality.py`
**Effort:** Medium
**Impact:** Low-Medium - skip useless pages

Added:
- `is_blank: bool` field to `ImageQualityScore`
- `_detect_blank()` method using variance and edge analysis
- Blank detection integrated into `classify()` method
- `get_ocr_route()` returns empty list for blank pages (skips OCR)

---

## Implementation Order

1. **1.1 Deduplication** - Immediate value, very simple
2. **1.2 Early Validation** - Prevents bad files entering pipeline
3. **1.3 Parallel Page OCR** - Major speedup for PDFs
4. **3.1 DPI Downscaling** - Easy memory savings
5. **2.1 Confidence Escalation** - Accuracy improvement
6. **2.2 Result Caching** - Repeat document optimization
7. **3.2 Batch Staggering** - Polish for large imports
8. **4.2 Blank Page Detection** - Nice to have

---

## Progress Log

| Date | Item | Status | Notes |
|------|------|--------|-------|
| 2025-12-29 | 1.1 Deduplication | Complete | Added _checksums dict, duplicate check in receive_file() |
| 2025-12-29 | 1.2 Early Validation | Complete | ValidationError class, _validate_file() method, config support |
| 2025-12-29 | 1.3 Parallel Page OCR | Complete | asyncio.gather + semaphore in ocr_document() |
| 2025-12-29 | 3.1 DPI Downscaling | Complete | needs_downscale property, cpu-image:downscale route, _downscale() worker |
| 2025-12-29 | 2.1 Confidence Escalation | Complete | avg confidence in PaddleWorker, escalation in ocr_page(), ocr.escalation event |
| 2025-12-29 | 2.2 Result Caching | Complete | TTL cache with checksum keys, get_cache_stats(), clear_cache() |
| 2025-12-29 | 3.2 Batch Staggering | Complete | Stagger constants, asyncio.sleep() in batch dispatch loops |
| 2025-12-29 | 4.2 Blank Page Detection | Complete | is_blank field, _detect_blank() method, skip OCR for blank pages |
| 2025-12-29 | Integration Fixes | Complete | Pool:operation suffix parsing in dispatcher, empty route handling |
| 2025-12-29 | Settings UI | Complete | Settings panel on Ingest page with toggle switches for all optimizations |

---

## Configuration Keys (Implemented)

All toggles default to `True` (enabled). Set to `False` to disable.

```yaml
# Ingest Shard Config (in frame config)
ingest_ocr_mode: "auto"              # auto | paddle_only | qwen_only
ingest_max_file_size_mb: 100         # Max file size in MB
ingest_min_file_size_bytes: 100      # Min file size in bytes
ingest_enable_validation: true       # Validate files before processing
ingest_enable_deduplication: true    # Skip duplicate files (by checksum)
ingest_enable_downscale: true        # Downscale high-DPI images (>200 DPI)
ingest_skip_blank_pages: true        # Skip OCR for blank/near-blank pages

# OCR Shard Config (in frame config)
ocr_default_engine: "paddle"         # Default OCR engine
ocr_parallel_pages: 4                # Max concurrent page OCR
ocr_confidence_threshold: 0.8        # Escalate to Qwen below this
ocr_enable_escalation: true          # Enable confidence-based escalation
ocr_enable_cache: true               # Cache OCR results
ocr_cache_ttl_days: 7                # Cache TTL in days
```
