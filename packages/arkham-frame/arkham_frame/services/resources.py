"""
ResourceService - System resource detection and management.

Detects available hardware (GPU, CPU, RAM) and assigns resource tiers.
Manages GPU memory allocation and CPU thread allocation for workers.
"""

import asyncio
import logging
import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ResourceTier(Enum):
    """System resource tiers based on available hardware."""
    MINIMAL = "minimal"      # CPU-only, limited concurrency
    STANDARD = "standard"    # < 6GB GPU VRAM
    RECOMMENDED = "recommended"  # 6-12GB GPU VRAM
    POWER = "power"          # > 12GB VRAM with high concurrency


class ResourceError(Exception):
    """Base exception for resource errors."""
    pass


class GPUMemoryError(ResourceError):
    """GPU memory allocation failed."""
    pass


class CPUAllocationError(ResourceError):
    """CPU thread allocation failed."""
    pass


@dataclass
class SystemResources:
    """Detected system resources."""
    # GPU
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    gpu_vram_mb: int = 0
    gpu_compute_capability: Optional[Tuple[int, int]] = None
    cuda_version: Optional[str] = None

    # CPU
    cpu_cores_physical: int = 1
    cpu_cores_logical: int = 1
    cpu_model: str = "Unknown"

    # Memory
    ram_total_mb: int = 0
    ram_available_mb: int = 0

    # Disk
    disk_free_mb: int = 0
    data_silo_path: str = ""

    # Services (detected at runtime)
    redis_available: bool = False
    postgres_available: bool = False
    qdrant_available: bool = False
    lm_studio_available: bool = False


@dataclass
class PoolConfig:
    """Configuration for a worker pool."""
    max_workers: int
    min_workers: int = 0
    threads_per_worker: int = 1
    gpu_memory_mb: int = 0
    enabled: bool = True
    fallback: Optional[str] = None


# Model memory requirements (approximate MB)
MODEL_MEMORY_MB = {
    "paddle": 2000,
    "qwen": 8000,
    "whisper-large": 4000,
    "whisper-medium": 2000,
    "bge-m3": 2000,
    "bge-small": 500,
}

# Default pool configurations per tier
TIER_POOL_CONFIGS = {
    ResourceTier.MINIMAL: {
        "io-file": PoolConfig(max_workers=10),
        "io-db": PoolConfig(max_workers=5),
        "cpu-light": PoolConfig(max_workers=8),
        "cpu-heavy": PoolConfig(max_workers=2, threads_per_worker=4),
        "cpu-ner": PoolConfig(max_workers=2),
        "cpu-extract": PoolConfig(max_workers=2),
        "cpu-image": PoolConfig(max_workers=2),
        "cpu-archive": PoolConfig(max_workers=1),
        "cpu-paddle": PoolConfig(max_workers=2, threads_per_worker=2),  # CPU fallback for OCR
        "cpu-embed": PoolConfig(max_workers=2, threads_per_worker=2),   # CPU fallback for embeddings
        "cpu-whisper": PoolConfig(max_workers=1, threads_per_worker=4), # CPU fallback for transcription
        "gpu-paddle": PoolConfig(max_workers=0, enabled=False, fallback="cpu-paddle"),
        "gpu-qwen": PoolConfig(max_workers=0, enabled=False),
        "gpu-whisper": PoolConfig(max_workers=0, enabled=False, fallback="cpu-whisper"),
        "gpu-embed": PoolConfig(max_workers=0, enabled=False, fallback="cpu-embed"),
        "llm-enrich": PoolConfig(max_workers=2),
        "llm-analysis": PoolConfig(max_workers=1),
    },
    ResourceTier.STANDARD: {
        "io-file": PoolConfig(max_workers=20),
        "io-db": PoolConfig(max_workers=10),
        "cpu-light": PoolConfig(max_workers=16),
        "cpu-heavy": PoolConfig(max_workers=4, threads_per_worker=4),
        "cpu-ner": PoolConfig(max_workers=4),
        "cpu-extract": PoolConfig(max_workers=4),
        "cpu-image": PoolConfig(max_workers=4),
        "cpu-archive": PoolConfig(max_workers=2),
        "cpu-paddle": PoolConfig(max_workers=2, threads_per_worker=2),
        "cpu-embed": PoolConfig(max_workers=2, threads_per_worker=2),
        "cpu-whisper": PoolConfig(max_workers=1, threads_per_worker=4),
        "gpu-paddle": PoolConfig(max_workers=1, gpu_memory_mb=2000),
        "gpu-qwen": PoolConfig(max_workers=0, enabled=False),  # Too much VRAM
        "gpu-whisper": PoolConfig(max_workers=0, enabled=False, fallback="cpu-whisper"),  # Too much VRAM
        "gpu-embed": PoolConfig(max_workers=1, gpu_memory_mb=2000),
        "llm-enrich": PoolConfig(max_workers=4),
        "llm-analysis": PoolConfig(max_workers=2),
    },
    ResourceTier.RECOMMENDED: {
        "io-file": PoolConfig(max_workers=30),
        "io-db": PoolConfig(max_workers=15),
        "cpu-light": PoolConfig(max_workers=32),
        "cpu-heavy": PoolConfig(max_workers=6, threads_per_worker=4),
        "cpu-ner": PoolConfig(max_workers=8),
        "cpu-extract": PoolConfig(max_workers=4),
        "cpu-image": PoolConfig(max_workers=4),
        "cpu-archive": PoolConfig(max_workers=2),
        "cpu-paddle": PoolConfig(max_workers=2, threads_per_worker=2),
        "cpu-embed": PoolConfig(max_workers=2, threads_per_worker=2),
        "cpu-whisper": PoolConfig(max_workers=1, threads_per_worker=4),
        "gpu-paddle": PoolConfig(max_workers=1, gpu_memory_mb=2000),
        "gpu-qwen": PoolConfig(max_workers=1, gpu_memory_mb=8000),
        "gpu-whisper": PoolConfig(max_workers=1, gpu_memory_mb=4000),
        "gpu-embed": PoolConfig(max_workers=1, gpu_memory_mb=2000),
        "llm-enrich": PoolConfig(max_workers=4),
        "llm-analysis": PoolConfig(max_workers=2),
    },
    ResourceTier.POWER: {
        "io-file": PoolConfig(max_workers=50),
        "io-db": PoolConfig(max_workers=20),
        "cpu-light": PoolConfig(max_workers=50),
        "cpu-heavy": PoolConfig(max_workers=8, threads_per_worker=4),
        "cpu-ner": PoolConfig(max_workers=16),
        "cpu-extract": PoolConfig(max_workers=8),
        "cpu-image": PoolConfig(max_workers=8),
        "cpu-archive": PoolConfig(max_workers=4),
        "cpu-paddle": PoolConfig(max_workers=4, threads_per_worker=2),
        "cpu-embed": PoolConfig(max_workers=4, threads_per_worker=2),
        "cpu-whisper": PoolConfig(max_workers=2, threads_per_worker=4),
        "gpu-paddle": PoolConfig(max_workers=2, gpu_memory_mb=2000),
        "gpu-qwen": PoolConfig(max_workers=1, gpu_memory_mb=8000),
        "gpu-whisper": PoolConfig(max_workers=1, gpu_memory_mb=4000),
        "gpu-embed": PoolConfig(max_workers=2, gpu_memory_mb=2000),
        "llm-enrich": PoolConfig(max_workers=4),
        "llm-analysis": PoolConfig(max_workers=2),
    },
}

# Exclusive GPU groups - models that cannot run simultaneously
EXCLUSIVE_GPU_GROUPS = {
    "heavy_gpu": ["gpu-qwen", "gpu-whisper"],
}

# Fallback mappings for CPU alternatives
FALLBACK_MAP = {
    "gpu-paddle": "cpu-paddle",
    "gpu-embed": "cpu-embed",
    "gpu-whisper": "cpu-whisper",
    "gpu-qwen": None,  # No good CPU fallback
}


class ResourceService:
    """
    System resource detection and management service.

    Detects available hardware at startup, assigns a resource tier,
    and manages GPU memory and CPU thread allocations for workers.
    """

    def __init__(self, config=None):
        self.config = config
        self.resources: Optional[SystemResources] = None
        self.tier: ResourceTier = ResourceTier.MINIMAL
        self._pool_configs: Dict[str, PoolConfig] = {}

        # GPU memory tracking
        self._gpu_allocations: Dict[str, int] = {}
        self._gpu_reserve_mb: int = 500  # Reserve 500MB for system

        # CPU thread tracking
        self._cpu_allocated: int = 0
        self._cpu_max_utilization: float = 0.8

        # Lock for thread-safe allocations
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the resource service by detecting system resources."""
        logger.info("Detecting system resources...")

        self.resources = await self._detect_resources()
        self.tier = self._determine_tier(self.resources)
        self._pool_configs = dict(TIER_POOL_CONFIGS[self.tier])

        # Apply any config overrides
        if self.config:
            self._apply_config_overrides()

        logger.info(f"Resource detection complete. Tier: {self.tier.value}")
        self._log_startup_report()

    async def shutdown(self) -> None:
        """Shutdown the resource service."""
        logger.info("ResourceService shutting down")
        self._gpu_allocations.clear()
        self._cpu_allocated = 0

    async def _detect_resources(self) -> SystemResources:
        """Probe system resources."""
        resources = SystemResources()

        # Detect GPU using PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                resources.gpu_available = True
                resources.gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                resources.gpu_vram_mb = props.total_memory // (1024 * 1024)
                resources.gpu_compute_capability = (props.major, props.minor)
                resources.cuda_version = torch.version.cuda
                logger.info(f"GPU detected: {resources.gpu_name} ({resources.gpu_vram_mb}MB VRAM)")
            else:
                logger.info("No CUDA GPU detected")
        except ImportError:
            logger.warning("PyTorch not installed, GPU detection skipped")
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")

        # Detect CPU
        try:
            import psutil
            resources.cpu_cores_physical = psutil.cpu_count(logical=False) or 1
            resources.cpu_cores_logical = psutil.cpu_count(logical=True) or 1
            resources.cpu_model = platform.processor() or "Unknown"
            logger.info(f"CPU: {resources.cpu_cores_physical} cores / {resources.cpu_cores_logical} threads")
        except ImportError:
            logger.warning("psutil not installed, using defaults")
            resources.cpu_cores_logical = os.cpu_count() or 1
            resources.cpu_cores_physical = resources.cpu_cores_logical // 2 or 1

        # Detect memory
        try:
            import psutil
            mem = psutil.virtual_memory()
            resources.ram_total_mb = mem.total // (1024 * 1024)
            resources.ram_available_mb = mem.available // (1024 * 1024)
            logger.info(f"RAM: {resources.ram_total_mb}MB total, {resources.ram_available_mb}MB available")
        except ImportError:
            pass

        # Detect disk space for DataSilo
        try:
            import psutil
            # Use relative path from frame package
            frame_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_silo = os.path.join(frame_dir, "DataSilo")

            if not os.path.exists(data_silo):
                os.makedirs(data_silo, exist_ok=True)

            resources.data_silo_path = data_silo
            disk = psutil.disk_usage(data_silo)
            resources.disk_free_mb = disk.free // (1024 * 1024)
            logger.info(f"DataSilo: {data_silo} ({resources.disk_free_mb}MB free)")
        except Exception as e:
            logger.warning(f"Disk detection failed: {e}")

        # Check service availability (non-blocking quick checks)
        resources.redis_available = await self._check_redis()
        resources.postgres_available = await self._check_postgres()
        resources.qdrant_available = await self._check_qdrant()
        resources.lm_studio_available = await self._check_lm_studio()

        return resources

    async def _check_redis(self) -> bool:
        """Quick check if Redis is available."""
        try:
            import redis.asyncio as redis
            url = self.config.redis_url if self.config else "redis://localhost:6380"
            client = redis.from_url(url, socket_connect_timeout=1)
            await asyncio.wait_for(client.ping(), timeout=2)
            await client.close()
            return True
        except Exception:
            return False

    async def _check_postgres(self) -> bool:
        """Quick check if PostgreSQL is available."""
        try:
            import asyncpg
            url = self.config.database_url if self.config else "postgresql://localhost:5435/anomdb"
            # Parse URL for asyncpg
            conn = await asyncio.wait_for(
                asyncpg.connect(url, timeout=2),
                timeout=3
            )
            await conn.close()
            return True
        except Exception:
            return False

    async def _check_qdrant(self) -> bool:
        """Quick check if Qdrant is available."""
        try:
            import httpx
            url = self.config.qdrant_url if self.config else "http://localhost:6343"
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{url}/collections")
                return resp.status_code == 200
        except Exception:
            return False

    async def _check_lm_studio(self) -> bool:
        """Quick check if LM Studio is available."""
        try:
            import httpx
            url = self.config.llm_endpoint if self.config else "http://localhost:1234/v1"
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def _determine_tier(self, resources: SystemResources) -> ResourceTier:
        """Determine resource tier based on detected hardware."""
        if not resources.gpu_available:
            return ResourceTier.MINIMAL

        if resources.gpu_vram_mb < 6000:
            return ResourceTier.STANDARD

        if resources.gpu_vram_mb < 12000:
            return ResourceTier.RECOMMENDED

        return ResourceTier.POWER

    def _apply_config_overrides(self) -> None:
        """Apply configuration overrides to pool configs."""
        if not self.config:
            return

        # Check for force_tier
        force_tier = self.config.get("resources.force_tier")
        if force_tier:
            try:
                self.tier = ResourceTier(force_tier)
                self._pool_configs = dict(TIER_POOL_CONFIGS[self.tier])
                logger.info(f"Forced tier: {self.tier.value}")
            except ValueError:
                logger.warning(f"Invalid force_tier: {force_tier}")

        # Check for disabled pools
        disabled = self.config.get("resources.disabled_pools", [])
        for pool in disabled:
            if pool in self._pool_configs:
                self._pool_configs[pool].enabled = False
                logger.info(f"Pool disabled by config: {pool}")

        # Check for pool overrides
        overrides = self.config.get("resources.pool_overrides", {})
        for pool, settings in overrides.items():
            if pool in self._pool_configs:
                for key, value in settings.items():
                    if hasattr(self._pool_configs[pool], key):
                        setattr(self._pool_configs[pool], key, value)
                        logger.info(f"Pool override: {pool}.{key} = {value}")

        # Check for GPU VRAM override
        vram_override = self.config.get("resources.gpu_vram_override_mb")
        if vram_override and self.resources:
            self.resources.gpu_vram_mb = vram_override
            # Recalculate tier with override
            self.tier = self._determine_tier(self.resources)
            self._pool_configs = dict(TIER_POOL_CONFIGS[self.tier])
            logger.info(f"GPU VRAM override: {vram_override}MB, new tier: {self.tier.value}")

    def _log_startup_report(self) -> None:
        """Log a startup report showing detected resources."""
        if not self.resources:
            return

        lines = [
            "=" * 80,
            "                         ArkhamFrame Resource Detection",
            "=" * 80,
            "",
            "System:",
        ]

        lines.append(f"  CPU: {self.resources.cpu_model}")
        lines.append(f"       ({self.resources.cpu_cores_physical} cores / {self.resources.cpu_cores_logical} threads)")
        lines.append(f"  RAM: {self.resources.ram_total_mb} MB ({self.resources.ram_available_mb} MB available)")

        if self.resources.gpu_available:
            lines.append(f"  GPU: {self.resources.gpu_name} ({self.resources.gpu_vram_mb} MB VRAM)")
            if self.resources.cuda_version:
                lines.append(f"       CUDA {self.resources.cuda_version}")
        else:
            lines.append("  GPU: Not available")

        lines.append("")
        lines.append(f"Tier: {self.tier.value.upper()}")
        lines.append("")
        lines.append("Worker Pools:")

        for pool, config in sorted(self._pool_configs.items()):
            if config.enabled:
                status = f"[OK] {pool:<16} (max: {config.max_workers} workers)"
                if config.gpu_memory_mb:
                    status += f" ({config.gpu_memory_mb}MB GPU)"
            else:
                fallback = config.fallback or "disabled"
                status = f"[--] {pool:<16} (disabled -> {fallback})"
            lines.append(f"  {status}")

        lines.append("")
        lines.append("Services:")
        lines.append(f"  [{'OK' if self.resources.postgres_available else '--'}] PostgreSQL")
        lines.append(f"  [{'OK' if self.resources.redis_available else '--'}] Redis")
        lines.append(f"  [{'OK' if self.resources.qdrant_available else '--'}] Qdrant")
        lines.append(f"  [{'OK' if self.resources.lm_studio_available else '--'}] LM Studio")

        lines.append("")
        lines.append("=" * 80)

        for line in lines:
            logger.info(line)

    # --- GPU Memory Management ---

    def gpu_available(self) -> bool:
        """Check if GPU is available."""
        return self.resources.gpu_available if self.resources else False

    def get_gpu_vram_mb(self) -> int:
        """Get total GPU VRAM in MB."""
        return self.resources.gpu_vram_mb if self.resources else 0

    def get_gpu_available_mb(self) -> int:
        """Get available GPU VRAM (total - allocated - reserve)."""
        if not self.resources or not self.resources.gpu_available:
            return 0

        allocated = sum(self._gpu_allocations.values())
        return self.resources.gpu_vram_mb - allocated - self._gpu_reserve_mb

    async def gpu_can_load(self, model: str) -> bool:
        """Check if a model can be loaded into GPU memory."""
        required = MODEL_MEMORY_MB.get(model, 0)
        return required <= self.get_gpu_available_mb()

    async def gpu_allocate(self, model: str) -> bool:
        """
        Allocate GPU memory for a model.

        Returns True if allocation succeeded, False otherwise.
        """
        async with self._lock:
            if not await self.gpu_can_load(model):
                return False

            required = MODEL_MEMORY_MB.get(model, 0)
            self._gpu_allocations[model] = required
            logger.debug(f"GPU allocated {required}MB for {model}")
            return True

    async def gpu_release(self, model: str) -> None:
        """Release GPU memory for a model."""
        async with self._lock:
            if model in self._gpu_allocations:
                released = self._gpu_allocations.pop(model)
                logger.debug(f"GPU released {released}MB from {model}")

    async def gpu_wait_for_memory(self, model: str, timeout: float = 60) -> bool:
        """
        Wait until GPU memory is available for a model.

        Returns True if memory became available, raises GPUMemoryError on timeout.
        """
        import time
        start = time.time()

        while not await self.gpu_can_load(model):
            if time.time() - start > timeout:
                raise GPUMemoryError(f"Timeout waiting for GPU memory for {model}")
            await asyncio.sleep(1)

        return await self.gpu_allocate(model)

    # --- CPU Management ---

    def get_max_cpu_threads(self) -> int:
        """Get maximum CPU threads that can be allocated (based on utilization cap)."""
        if not self.resources:
            return 1
        return int(self.resources.cpu_cores_logical * self._cpu_max_utilization)

    def get_available_cpu_threads(self) -> int:
        """Get currently available CPU threads."""
        return max(0, self.get_max_cpu_threads() - self._cpu_allocated)

    async def cpu_acquire(self, threads: int) -> bool:
        """
        Acquire CPU threads for a worker.

        Returns True if threads were acquired, False if not enough available.
        """
        async with self._lock:
            if threads > self.get_available_cpu_threads():
                return False

            self._cpu_allocated += threads
            logger.debug(f"CPU acquired {threads} threads ({self._cpu_allocated}/{self.get_max_cpu_threads()})")
            return True

    async def cpu_release(self, threads: int) -> None:
        """Release CPU threads."""
        async with self._lock:
            self._cpu_allocated = max(0, self._cpu_allocated - threads)
            logger.debug(f"CPU released {threads} threads ({self._cpu_allocated}/{self.get_max_cpu_threads()})")

    # --- Pool Configuration ---

    def get_pool_config(self, pool: str) -> Optional[PoolConfig]:
        """Get configuration for a worker pool."""
        return self._pool_configs.get(pool)

    def get_pool_limits(self) -> Dict[str, PoolConfig]:
        """Get all pool configurations."""
        return dict(self._pool_configs)

    def get_disabled_pools(self) -> List[str]:
        """Get list of disabled pool names."""
        return [name for name, config in self._pool_configs.items() if not config.enabled]

    def get_enabled_pools(self) -> List[str]:
        """Get list of enabled pool names."""
        return [name for name, config in self._pool_configs.items() if config.enabled]

    def get_fallback_pool(self, pool: str) -> Optional[str]:
        """Get fallback pool for a disabled pool."""
        config = self._pool_configs.get(pool)
        if config and not config.enabled:
            return config.fallback or FALLBACK_MAP.get(pool)
        return None

    def get_best_pool(self, preferred: str) -> Optional[str]:
        """
        Get the best available pool (preferred or fallback).

        Returns the pool name to use, or None if no option is available.
        """
        config = self._pool_configs.get(preferred)
        if config and config.enabled:
            return preferred

        fallback = self.get_fallback_pool(preferred)
        if fallback:
            fallback_config = self._pool_configs.get(fallback)
            if fallback_config and fallback_config.enabled:
                logger.warning(f"{preferred} unavailable, using {fallback}")
                return fallback

        logger.error(f"{preferred} unavailable, no fallback")
        return None

    # --- Tier Information ---

    def get_tier(self) -> ResourceTier:
        """Get the current resource tier."""
        return self.tier

    def get_tier_name(self) -> str:
        """Get the current resource tier name."""
        return self.tier.value

    def get_resources(self) -> Optional[SystemResources]:
        """Get detected system resources."""
        return self.resources

    def get_state(self) -> Dict[str, Any]:
        """Get current resource state for API."""
        if not self.resources:
            return {"initialized": False}

        return {
            "initialized": True,
            "tier": self.tier.value,
            "gpu": {
                "available": self.resources.gpu_available,
                "name": self.resources.gpu_name,
                "vram_mb": self.resources.gpu_vram_mb,
                "vram_available_mb": self.get_gpu_available_mb(),
                "allocations": dict(self._gpu_allocations),
            },
            "cpu": {
                "cores_physical": self.resources.cpu_cores_physical,
                "cores_logical": self.resources.cpu_cores_logical,
                "max_threads": self.get_max_cpu_threads(),
                "allocated_threads": self._cpu_allocated,
                "available_threads": self.get_available_cpu_threads(),
            },
            "memory": {
                "ram_total_mb": self.resources.ram_total_mb,
                "ram_available_mb": self.resources.ram_available_mb,
            },
            "services": {
                "redis": self.resources.redis_available,
                "postgres": self.resources.postgres_available,
                "qdrant": self.resources.qdrant_available,
                "lm_studio": self.resources.lm_studio_available,
            },
            "pools": {
                name: {
                    "enabled": config.enabled,
                    "max_workers": config.max_workers,
                    "gpu_memory_mb": config.gpu_memory_mb,
                    "fallback": config.fallback,
                }
                for name, config in self._pool_configs.items()
            },
        }
