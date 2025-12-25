# Resource Detection & Scaling

ArkhamFrame must adapt to available hardware, not assume a specific configuration.

---

## Design Principles

1. **Detect, Don't Assume** - Probe hardware at startup
2. **Degrade Gracefully** - Disable features if resources unavailable
3. **Inform the User** - Clear messaging about what's available/disabled
4. **Conservative Defaults** - Better to underutilize than crash

---

## Resource Detection

### Startup Probe

```python
@dataclass
class SystemResources:
    """Detected system resources."""

    # GPU
    gpu_available: bool
    gpu_name: str | None
    gpu_vram_mb: int
    gpu_compute_capability: tuple[int, int] | None
    cuda_version: str | None

    # CPU
    cpu_cores_physical: int
    cpu_cores_logical: int
    cpu_model: str

    # Memory
    ram_total_mb: int
    ram_available_mb: int

    # Disk
    disk_free_mb: int
    data_silo_path: str

    # Services
    redis_available: bool
    postgres_available: bool
    qdrant_available: bool
    lm_studio_available: bool


async def detect_resources() -> SystemResources:
    """
    Probe system resources at startup.
    """
    resources = SystemResources(...)

    # GPU detection
    try:
        import torch
        if torch.cuda.is_available():
            resources.gpu_available = True
            resources.gpu_name = torch.cuda.get_device_name(0)
            resources.gpu_vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024*1024)
            resources.gpu_compute_capability = torch.cuda.get_device_capability(0)
            resources.cuda_version = torch.version.cuda
        else:
            resources.gpu_available = False
    except ImportError:
        resources.gpu_available = False

    # CPU detection
    import psutil
    resources.cpu_cores_physical = psutil.cpu_count(logical=False)
    resources.cpu_cores_logical = psutil.cpu_count(logical=True)

    # Memory
    mem = psutil.virtual_memory()
    resources.ram_total_mb = mem.total // (1024*1024)
    resources.ram_available_mb = mem.available // (1024*1024)

    # etc...

    return resources
```

---

## Resource Tiers

Based on detected resources, assign a tier:

| Tier | GPU VRAM | RAM | CPU Cores | Description |
|------|----------|-----|-----------|-------------|
| **minimal** | None | < 8GB | 2-4 | CPU-only, limited concurrency |
| **standard** | < 6GB | 8-16GB | 4-8 | Basic GPU, moderate workers |
| **recommended** | 6-12GB | 16-32GB | 8-16 | Full GPU features |
| **power** | > 12GB | > 32GB | > 16 | Multiple GPU workers, high concurrency |

```python
def determine_tier(resources: SystemResources) -> str:
    if not resources.gpu_available:
        return "minimal"

    if resources.gpu_vram_mb < 6000:
        return "standard"

    if resources.gpu_vram_mb < 12000:
        return "recommended"

    return "power"
```

---

## Worker Pool Scaling

### Per-Tier Defaults

```yaml
# config/tiers/minimal.yaml
tier: minimal
description: "CPU-only mode. GPU features disabled."

disabled_pools:
  - gpu-paddle
  - gpu-qwen
  - gpu-whisper
  - gpu-embed  # Will use CPU fallback

pool_limits:
  cpu-light: { max: 8 }
  cpu-heavy: { max: 2 }
  cpu-ner: { max: 2 }
  cpu-extract: { max: 2 }
  io-file: { max: 10 }
  io-db: { max: 5 }

fallbacks:
  gpu-embed: cpu-embed  # Use CPU embeddings (slower but works)
  gpu-paddle: disabled  # No OCR without GPU
  gpu-qwen: disabled

warnings:
  - "GPU not detected. OCR features disabled."
  - "Use PaddleOCR CPU mode or external OCR service."
```

```yaml
# config/tiers/standard.yaml
tier: standard
description: "Limited GPU. Some features restricted."

disabled_pools:
  - gpu-qwen      # Too much VRAM
  - gpu-whisper   # Too much VRAM

pool_limits:
  gpu-paddle: { max: 1 }
  gpu-embed: { max: 1 }
  cpu-light: { max: 16 }
  cpu-heavy: { max: 4 }

exclusive_groups:
  # Can't run paddle and embed simultaneously
  gpu_shared: [gpu-paddle, gpu-embed]

warnings:
  - "Limited GPU memory. Vision OCR (Qwen) disabled."
  - "Audio transcription (Whisper) disabled."
```

```yaml
# config/tiers/recommended.yaml
tier: recommended
description: "Full features with managed GPU sharing."

disabled_pools: []

pool_limits:
  gpu-paddle: { max: 1 }
  gpu-qwen: { max: 1 }
  gpu-whisper: { max: 1 }
  gpu-embed: { max: 1 }
  cpu-light: { max: 32 }
  cpu-heavy: { max: 6 }

exclusive_groups:
  heavy_gpu: [gpu-qwen, gpu-whisper]
```

```yaml
# config/tiers/power.yaml
tier: power
description: "High-resource mode. Parallel GPU operations."

disabled_pools: []

pool_limits:
  gpu-paddle: { max: 2 }
  gpu-qwen: { max: 1 }
  gpu-whisper: { max: 1 }
  gpu-embed: { max: 2 }
  cpu-light: { max: 50 }
  cpu-heavy: { max: 8 }

exclusive_groups: {}  # Can run everything in parallel
```

---

## Dynamic Scaling

### Memory-Aware Scheduling

```python
class GPUMemoryManager:
    """
    Track GPU memory and prevent OOM.
    """

    def __init__(self, total_vram_mb: int, reserve_mb: int = 500):
        self.total = total_vram_mb
        self.reserve = reserve_mb
        self.available = total_vram_mb - reserve_mb
        self.allocations: dict[str, int] = {}

    # Model memory requirements (approximate)
    MODEL_MEMORY = {
        "paddle": 2000,      # 2GB
        "qwen": 8000,        # 8GB
        "whisper-large": 4000,  # 4GB
        "whisper-medium": 2000,
        "bge-m3": 2000,
    }

    async def can_load(self, model: str) -> bool:
        """Check if model can be loaded."""
        required = self.MODEL_MEMORY.get(model, 0)
        current_used = sum(self.allocations.values())
        return (current_used + required) <= self.available

    async def allocate(self, model: str) -> bool:
        """Allocate memory for model."""
        if not await self.can_load(model):
            return False
        self.allocations[model] = self.MODEL_MEMORY.get(model, 0)
        return True

    async def release(self, model: str):
        """Release model memory."""
        self.allocations.pop(model, None)

    async def wait_for_memory(self, model: str, timeout: float = 60):
        """Wait until memory is available."""
        start = time.time()
        while not await self.can_load(model):
            if time.time() - start > timeout:
                raise ResourceError(f"Timeout waiting for GPU memory for {model}")
            await asyncio.sleep(1)
        return await self.allocate(model)
```

### CPU Throttling

```python
class CPUManager:
    """
    Manage CPU worker count based on load.
    """

    def __init__(self, cores: int, max_utilization: float = 0.8):
        self.cores = cores
        self.max_threads = int(cores * max_utilization)
        self.current_threads = 0

    def available_threads(self) -> int:
        return max(0, self.max_threads - self.current_threads)

    async def acquire(self, threads: int) -> bool:
        if threads > self.available_threads():
            return False
        self.current_threads += threads
        return True

    async def release(self, threads: int):
        self.current_threads = max(0, self.current_threads - threads)
```

---

## User Messaging

### Startup Report

```
================================================================================
                         ArkhamFrame Resource Detection
================================================================================

System:
  CPU: AMD Ryzen 7 5800X (8 cores / 16 threads)
  RAM: 32 GB (28 GB available)
  GPU: NVIDIA RTX 3060 (12 GB VRAM)

Tier: RECOMMENDED

Worker Pools:
  [OK] cpu-light      (max: 32 workers)
  [OK] cpu-heavy      (max: 6 workers)
  [OK] cpu-ner        (max: 8 workers)
  [OK] gpu-paddle     (max: 1 worker, 2GB reserved)
  [OK] gpu-qwen       (max: 1 worker, 8GB reserved)
  [OK] gpu-embed      (max: 1 worker, 2GB reserved)
  [--] gpu-whisper    (disabled - would exceed VRAM with Qwen)

GPU Scheduling:
  Exclusive: gpu-qwen OR gpu-whisper (not both)
  Shared: gpu-paddle + gpu-embed can run together

Services:
  [OK] PostgreSQL (localhost:5435)
  [OK] Redis (localhost:6380)
  [OK] Qdrant (localhost:6343)
  [OK] LM Studio (localhost:1234)

================================================================================
```

### Dashboard Display

The Dashboard UI should show:
- Current resource tier
- Per-pool status (enabled/disabled/why)
- Real-time GPU memory usage
- CPU utilization
- Warnings for disabled features

---

## CPU-Only Fallbacks

For systems without GPU:

| Feature | GPU Version | CPU Fallback | Notes |
|---------|-------------|--------------|-------|
| OCR | PaddleOCR GPU | PaddleOCR CPU | 5-10x slower |
| OCR (vision) | Qwen-VL | Tesseract | Much lower quality |
| Embeddings | BGE-M3 GPU | BGE-M3 CPU | 3-5x slower |
| Transcription | Whisper GPU | Whisper CPU | 10-20x slower |

```python
FALLBACK_MAP = {
    "gpu-paddle": "cpu-paddle",
    "gpu-embed": "cpu-embed",
    "gpu-whisper": "cpu-whisper",
    "gpu-qwen": None,  # No good CPU fallback
}

def get_worker_pool(preferred: str, resources: SystemResources) -> str | None:
    """Get best available worker pool."""
    if preferred in resources.enabled_pools:
        return preferred

    fallback = FALLBACK_MAP.get(preferred)
    if fallback and fallback in resources.enabled_pools:
        logger.warning(f"{preferred} unavailable, using {fallback}")
        return fallback

    logger.error(f"{preferred} unavailable, no fallback")
    return None
```

---

## Configuration Override

Users can override detected settings:

```yaml
# config/resources.yaml (user override)

# Force a specific tier (ignores detection)
force_tier: standard

# Manually disable pools
disabled_pools:
  - gpu-whisper  # Don't need audio

# Override limits
pool_overrides:
  cpu-heavy:
    max: 2  # Limit CPU usage

# GPU memory override (if detection is wrong)
gpu_vram_override_mb: 8000
```

---

*Last Updated: 2025-12-20*
