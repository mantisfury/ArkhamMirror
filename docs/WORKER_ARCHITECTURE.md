# Worker Architecture

Design document for Shattered's distributed worker system.

---

## Design Principles

1. **LLM is Optional** - CPU/GPU processing must complete without LLM. LLM enrichment is always async/extra.
2. **No Zombie Workers** - Workers must timeout, expire, and clean up gracefully.
3. **Resource Isolation** - GPU workers don't block CPU work. IO doesn't block compute.
4. **Burst & Scale** - Workers spin up on demand, scale down when idle.
5. **Fast Path First** - Text files skip OCR. Simple docs skip LLM. Always take the fastest valid path.

---

## Worker Pools (13 Total)

### IO Workers
| Pool | Concurrency | Timeout | Description |
|------|-------------|---------|-------------|
| `io-file` | 10-50 | 30s | File read/write, temp file management |
| `io-db` | 5-20 | 10s | PostgreSQL operations |
| `io-vector` | 5-20 | 30s | Qdrant vector store operations |

### CPU Workers
| Pool | Concurrency | Timeout | Description |
|------|-------------|---------|-------------|
| `cpu-light` | 10-50 | 10s | Hashing, validation, metadata, chunking |
| `cpu-heavy` | 2-8 | 120s | PDF rendering, format conversion (poppler, pandoc) |
| `cpu-extract` | 4-16 | 60s | Text extraction from docx/xlsx/pptx |
| `cpu-ner` | 4-16 | 30s | spaCy NER, regex patterns |
| `cpu-image` | 2-8 | 30s | Image preprocessing (deskew, contrast, resize) |
| `cpu-archive` | 2-4 | 120s | ZIP/tar extraction, nested archives |
| `cpu-dedup` | 2-8 | 30s | Hash dedup, near-duplicate detection |

### GPU Workers
| Pool | Concurrency | Timeout | Description |
|------|-------------|---------|-------------|
| `gpu-paddle` | 1-2 | 60s | PaddleOCR (standard documents) |
| `gpu-qwen` | 1 | 180s | Qwen-VL vision OCR (complex/handwritten) |
| `gpu-whisper` | 1 | 300s | Whisper audio transcription |
| `gpu-embed` | 1-2 | 60s | BGE-M3 embedding generation |

### LLM Workers (Optional/Async)
| Pool | Concurrency | Timeout | Description |
|------|-------------|---------|-------------|
| `llm-enrich` | 1-4 | 120s | Entity enrichment, relationship extraction |
| `llm-analysis` | 1-2 | 180s | Summarization, contradiction detection |

---

## Worker Lifecycle

### Startup Modes

```yaml
worker_modes:
  persistent:
    # Always running, for critical paths
    pools: [io-db, cpu-light, gpu-embed]
    min_workers: 1

  on_demand:
    # Spin up when queue has work
    pools: [cpu-heavy, gpu-paddle, gpu-qwen, gpu-whisper]
    min_workers: 0
    startup_delay: 500ms

  burst:
    # Scale up rapidly under load
    pools: [cpu-ner, cpu-extract, io-file]
    min_workers: 1
    max_workers: 50
    scale_threshold: 10  # queue depth triggers scale
```

### Expiration Rules

```yaml
worker_expiration:
  idle_timeout: 60s        # No work for 60s = shutdown
  max_lifetime: 3600s      # Force restart after 1 hour (memory leaks)
  stuck_timeout: 300s      # Task running > 5 min = kill + requeue
  heartbeat_interval: 10s  # Workers must heartbeat or considered dead
```

### Graceful Shutdown

```python
class WorkerLifecycle:
    """
    Worker shutdown sequence:
    1. Stop accepting new jobs
    2. Finish current job (up to timeout)
    3. Requeue if timeout exceeded
    4. Release resources (GPU memory, file handles)
    5. Deregister from pool
    6. Exit
    """

    async def shutdown(self, timeout: int = 30):
        self.accepting_jobs = False

        if self.current_job:
            try:
                await asyncio.wait_for(
                    self.current_job,
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                await self.requeue_current_job()

        await self.release_resources()
        await self.deregister()
```

---

## Queue Routing

### File Type Router

```python
FILE_ROUTING = {
    # Text files - skip OCR entirely
    "fast_path": {
        "extensions": [".txt", ".md", ".json", ".csv", ".xml", ".html"],
        "pipeline": ["cpu-extract", "cpu-ner", "gpu-embed", "io-db"],
    },

    # Office docs - extract text, skip OCR if text layer exists
    "office_path": {
        "extensions": [".docx", ".xlsx", ".pptx", ".odt"],
        "pipeline": ["cpu-extract", "cpu-ner", "gpu-embed", "io-db"],
    },

    # PDF - check for text layer first
    "pdf_path": {
        "extensions": [".pdf"],
        "pipeline": ["cpu-heavy:pdf_check", "BRANCH"],
        "branch_has_text": ["cpu-extract", "cpu-ner", "gpu-embed", "io-db"],
        "branch_needs_ocr": ["cpu-image", "gpu-paddle", "cpu-ner", "gpu-embed", "io-db"],
    },

    # Images - always need OCR
    "image_path": {
        "extensions": [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"],
        "pipeline": ["cpu-image", "gpu-paddle", "cpu-ner", "gpu-embed", "io-db"],
    },

    # Complex images - use vision LLM
    "vision_path": {
        "extensions": [".png", ".jpg"],  # User-selected or auto-detected
        "conditions": ["handwritten", "complex_layout", "low_quality"],
        "pipeline": ["cpu-image", "gpu-qwen", "cpu-ner", "gpu-embed", "io-db"],
    },

    # Audio - transcription
    "audio_path": {
        "extensions": [".mp3", ".wav", ".m4a", ".flac", ".ogg"],
        "pipeline": ["gpu-whisper", "cpu-ner", "gpu-embed", "io-db"],
    },

    # Archives - extract then route contents
    "archive_path": {
        "extensions": [".zip", ".tar", ".gz", ".7z", ".rar"],
        "pipeline": ["cpu-archive", "RECURSE"],
    },
}
```

### Image Quality Classification (Fast Path)

**Principle:** Don't preprocess everything. Classify first, preprocess only what needs it.

```
Image Input
    │
    ▼
┌─────────────────────────────────┐
│  CPU-light: Quick Quality Check │  (< 5ms per image)
│  - DPI check                    │
│  - Skew angle detection         │
│  - Contrast ratio               │
│  - Color depth analysis         │
│  - File size vs dimensions      │
└─────────────────┬───────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
  CLEAN        FIXABLE       MESSY
    │             │             │
    ▼             ▼             ▼
GPU-paddle    CPU-image     CPU-image
    │             │             │
    │             ▼             ▼
    │        GPU-paddle     GPU-qwen
    │             │             │
    └─────────────┴─────────────┘
                  │
                  ▼
              CPU-ner
```

```python
@dataclass
class ImageQualityScore:
    dpi: int
    skew_angle: float      # degrees
    contrast_ratio: float  # 0.0 - 1.0
    is_grayscale: bool
    compression_ratio: float
    has_noise: bool
    layout_complexity: str  # simple | table | mixed | complex

    @property
    def classification(self) -> str:
        """CLEAN, FIXABLE, or MESSY"""
        issues = 0

        if self.dpi < 150:
            issues += 1
        if abs(self.skew_angle) > 2.0:
            issues += 1
        if self.contrast_ratio < 0.4:
            issues += 1
        if self.has_noise:
            issues += 1

        if issues == 0:
            return "CLEAN"
        elif issues <= 2 and self.layout_complexity in ("simple", "table"):
            return "FIXABLE"
        else:
            return "MESSY"


def route_image(quality: ImageQualityScore, user_settings: dict) -> List[str]:
    """
    Route image through appropriate workers.
    Returns list of worker pools in order.
    """
    # User override
    if user_settings.get("ocr_mode") == "qwen_only":
        return ["cpu-image", "gpu-qwen"]
    if user_settings.get("ocr_mode") == "paddle_only":
        if quality.classification == "CLEAN":
            return ["gpu-paddle"]
        return ["cpu-image", "gpu-paddle"]

    # Auto routing
    classification = quality.classification

    if classification == "CLEAN":
        return ["gpu-paddle"]

    elif classification == "FIXABLE":
        return ["cpu-image", "gpu-paddle"]

    else:  # MESSY
        # Complex layout or severe quality issues -> Qwen
        if quality.layout_complexity in ("mixed", "complex"):
            return ["cpu-image", "gpu-qwen"]
        # Try preprocessing + paddle first, escalate if needed
        return ["cpu-image", "gpu-paddle"]  # Will escalate on low confidence
```

### Quality Check Thresholds

| Check | Threshold | Issue |
|-------|-----------|-------|
| DPI | < 150 | Low-res, needs upscaling |
| Skew | > 2 degrees | Crooked, needs deskew |
| Contrast | < 0.4 | Faded, needs enhancement |
| Compression | size/(w*h) < threshold | Over-compressed, may need denoising |
| Color depth | - | Grayscale conversion might help |

These checks are **cheap** (< 5ms per image) and run in `cpu-light`.

### OCR Retry Strategy

```python
async def ocr_with_retry(image_path: str, quality: ImageQualityScore) -> OCRResult:
    """
    Smart retry logic for OCR.
    """
    # First attempt based on routing
    route = route_image(quality, user_settings)

    result = await run_ocr(image_path, route)

    if result.confidence >= CONFIDENCE_THRESHOLD:
        return result

    # Low confidence - try preprocessing if we haven't
    if "cpu-image" not in route:
        preprocessed = await preprocess_image(image_path)
        result = await run_ocr(preprocessed, ["gpu-paddle"])

        if result.confidence >= CONFIDENCE_THRESHOLD:
            return result

    # Still low - escalate to Qwen (if auto mode)
    if user_settings.get("ocr_mode") == "auto":
        result = await run_ocr(image_path, ["gpu-qwen"])

    return result  # Best effort
```

---

## Resource Allocation

### GPU Memory Management

```yaml
gpu_allocation:
  # Assume 12GB VRAM (RTX 4070 Super)
  # Only one heavy model loaded at a time

  exclusive_models:
    # These cannot run simultaneously
    - gpu-qwen      # ~8GB VRAM
    - gpu-whisper   # ~4GB VRAM (large-v3)

  shared_models:
    # These can coexist
    - gpu-paddle    # ~2GB VRAM
    - gpu-embed     # ~2GB VRAM

  model_loading:
    strategy: lazy           # Load on first use
    unload_after: 300s       # Unload if unused for 5 min
    preload: [gpu-embed]     # Always keep embeddings ready
```

### CPU Core Allocation

```yaml
cpu_allocation:
  # Assume 8 cores / 16 threads

  pools:
    cpu-heavy: 4 threads     # PDF rendering is memory-bound anyway
    cpu-extract: 4 threads
    cpu-ner: 4 threads       # spaCy uses threading
    cpu-light: 8 threads     # IO-bound, can oversubscribe
    cpu-image: 2 threads
    cpu-archive: 2 threads

  # Never exceed 80% total CPU to leave headroom
  max_total_threads: 12
```

---

## Shard-to-Worker Mapping

### Ingest Shard
```yaml
ingest_shard:
  owns_queues:
    - cpu-archive
    - cpu-heavy
    - cpu-extract
    - cpu-image
    - io-file

  routes_to:
    - gpu-paddle    # Owned by OCR shard
    - gpu-qwen      # Owned by OCR shard
    - gpu-whisper   # Owned by Audio shard
```

### OCR Shard
```yaml
ocr_shard:
  owns_queues:
    - gpu-paddle
    - gpu-qwen

  routes_to:
    - cpu-ner       # Owned by Parse shard
```

### Audio Shard
```yaml
audio_shard:
  owns_queues:
    - gpu-whisper

  routes_to:
    - cpu-ner       # Owned by Parse shard
```

### Parse Shard
```yaml
parse_shard:
  owns_queues:
    - cpu-ner
    - cpu-dedup

  routes_to:
    - gpu-embed     # Owned by Embed shard
    - llm-enrich    # Optional, owned by LLM shard
```

### Embed Shard
```yaml
embed_shard:
  owns_queues:
    - gpu-embed

  routes_to:
    - io-db
    - io-vector
```

### LLM Shard (Optional)
```yaml
llm_shard:
  owns_queues:
    - llm-enrich
    - llm-analysis

  # Never blocks main pipeline
  # Always async enrichment
  triggered_by:
    - document.parsed        # Enrich entities
    - document.embedded      # Generate summaries
    - user.request           # On-demand analysis
```

---

## Worker Manager API

### Dashboard Controls

```python
class WorkerManagerAPI:
    """
    Exposed via Dashboard shard.
    """

    async def get_pools(self) -> List[PoolStatus]:
        """List all worker pools with status."""

    async def get_pool_workers(self, pool: str) -> List[WorkerStatus]:
        """List workers in a specific pool."""

    async def scale_pool(self, pool: str, count: int) -> bool:
        """Set target worker count for pool."""

    async def kill_worker(self, worker_id: str) -> bool:
        """Force-kill a specific worker."""

    async def drain_pool(self, pool: str) -> bool:
        """Stop accepting jobs, let current work finish, shutdown."""

    async def pause_pool(self, pool: str) -> bool:
        """Stop processing, keep workers alive."""

    async def resume_pool(self, pool: str) -> bool:
        """Resume paused pool."""

    async def get_stuck_jobs(self, threshold_seconds: int = 300) -> List[Job]:
        """Find jobs running longer than threshold."""

    async def requeue_stuck(self, job_id: str) -> bool:
        """Kill stuck job and requeue."""
```

### CLI Commands

```bash
# Pool management
shattered workers list                    # All pools
shattered workers status gpu-paddle       # Specific pool
shattered workers scale gpu-paddle 2      # Scale to 2 workers
shattered workers drain gpu-qwen          # Graceful shutdown
shattered workers kill worker-abc123      # Force kill

# Job management
shattered jobs stuck --threshold 300      # Find stuck jobs
shattered jobs requeue job-xyz789         # Requeue specific job
shattered jobs cancel job-xyz789          # Cancel without requeue

# Monitoring
shattered workers watch                   # Live dashboard
shattered workers metrics                 # Prometheus export
```

---

## Configuration File

```yaml
# config/workers.yaml

defaults:
  heartbeat_interval: 10s
  idle_timeout: 60s
  max_lifetime: 3600s
  stuck_timeout: 300s

pools:
  io-file:
    min_workers: 1
    max_workers: 50
    mode: burst
    timeout: 30s

  io-db:
    min_workers: 1
    max_workers: 20
    mode: persistent
    timeout: 10s

  cpu-light:
    min_workers: 2
    max_workers: 50
    mode: burst
    timeout: 10s

  cpu-heavy:
    min_workers: 0
    max_workers: 4
    mode: on_demand
    timeout: 120s
    threads_per_worker: 4

  cpu-ner:
    min_workers: 1
    max_workers: 8
    mode: burst
    timeout: 30s

  gpu-paddle:
    min_workers: 0
    max_workers: 2
    mode: on_demand
    timeout: 60s
    gpu_memory: 2GB
    exclusive_group: null  # Can coexist with embed

  gpu-qwen:
    min_workers: 0
    max_workers: 1
    mode: on_demand
    timeout: 180s
    gpu_memory: 8GB
    exclusive_group: heavy_gpu  # Cannot run with whisper
    model_unload_after: 300s

  gpu-whisper:
    min_workers: 0
    max_workers: 1
    mode: on_demand
    timeout: 300s
    gpu_memory: 4GB
    exclusive_group: heavy_gpu  # Cannot run with qwen
    model_unload_after: 300s

  gpu-embed:
    min_workers: 0
    max_workers: 2
    mode: on_demand
    timeout: 60s
    gpu_memory: 2GB
    preload: true  # Keep model in memory

  llm-enrich:
    min_workers: 0
    max_workers: 4
    mode: on_demand
    timeout: 120s
    optional: true  # Never blocks pipeline
    priority: low

  llm-analysis:
    min_workers: 0
    max_workers: 2
    mode: on_demand
    timeout: 180s
    optional: true
    priority: low

routing:
  paddle_confidence_threshold: 0.7
  auto_escalate_to_qwen: true
  skip_ocr_for_text_pdfs: true

gpu:
  max_memory_percent: 90
  model_cache_dir: ${DATA_SILO}/models
  exclusive_groups:
    heavy_gpu: [gpu-qwen, gpu-whisper]
```

---

## Monitoring & Alerts

### Metrics (Prometheus)

```
# Worker pool health
shattered_workers_active{pool="gpu-paddle"} 1
shattered_workers_idle{pool="gpu-paddle"} 0
shattered_workers_stuck{pool="gpu-paddle"} 0

# Queue depth
shattered_queue_depth{pool="gpu-paddle"} 15
shattered_queue_oldest_seconds{pool="gpu-paddle"} 45

# Processing rates
shattered_jobs_completed_total{pool="gpu-paddle"} 1523
shattered_jobs_failed_total{pool="gpu-paddle"} 12
shattered_job_duration_seconds{pool="gpu-paddle",quantile="0.95"} 8.5

# Resource usage
shattered_gpu_memory_used_bytes{device="0"} 8589934592
shattered_cpu_percent{pool="cpu-heavy"} 75
```

### Alerts

```yaml
alerts:
  - name: WorkerStuck
    condition: shattered_workers_stuck > 0
    for: 5m
    action: kill_and_requeue

  - name: QueueBacklog
    condition: shattered_queue_depth > 100
    for: 10m
    action: scale_up

  - name: HighFailureRate
    condition: rate(shattered_jobs_failed_total[5m]) > 0.1
    action: notify

  - name: GPUMemoryExhausted
    condition: shattered_gpu_memory_used_bytes > 11GB
    action: drain_heavy_gpu_pools
```

---

## Implementation Order

1. **Phase 1: Worker Framework**
   - Worker base class with lifecycle
   - Pool manager with scaling
   - Redis queue integration
   - Basic monitoring

2. **Phase 2: CPU Workers**
   - cpu-light, cpu-heavy, cpu-extract, cpu-ner
   - File routing logic
   - Text extraction pipeline

3. **Phase 3: GPU Workers**
   - gpu-paddle, gpu-embed
   - GPU memory management
   - Model loading/unloading

4. **Phase 4: Advanced GPU**
   - gpu-qwen (vision OCR)
   - gpu-whisper (audio)
   - Exclusive group management

5. **Phase 5: LLM Workers**
   - llm-enrich, llm-analysis
   - Async enrichment pipeline
   - Optional integration

---

## Decisions

1. **Job Priority** - User uploads always have priority over batch imports.
2. **Retry Strategy** - 3 retries with exponential backoff. User gets message on each failure.
3. **Failed Jobs** - Keep in dead letter queue. User can re-queue with upgraded worker assignment.
4. **Cross-Machine** - Design for single-machine now. Multi-machine is a future goal but untested.
5. **Cost Tracking** - Track GPU-seconds per document for resource planning.

---

## OCR Mode Configuration

Users can control OCR routing:

```yaml
ocr_settings:
  mode: auto | paddle_only | qwen_only

  # Only applies when mode=auto
  auto_settings:
    confidence_threshold: 0.7    # Below this, escalate to Qwen
    always_try_paddle_first: true
    preprocess_before_retry: true  # If Paddle fails, preprocess then retry before Qwen
```

Dashboard UI provides:
- Toggle: Auto / Paddle Only / Qwen Only
- Confidence slider (0.5 - 0.9) for auto mode
- Per-document override option

---

*Last Updated: 2025-12-20*
