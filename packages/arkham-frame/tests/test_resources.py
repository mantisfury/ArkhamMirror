"""
Integration tests for ResourceService - system resource detection and management.

Tests hardware detection, tier assignment, pool configuration, GPU memory management,
and CPU thread management.

Run with:
    cd packages/arkham-frame
    pytest tests/test_resources.py -v -s
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Optional

from arkham_frame.services.resources import (
    ResourceService,
    ResourceTier,
    SystemResources,
    PoolConfig,
    GPUMemoryError,
    CPUAllocationError,
)


# =============================================================================
# Test 1: Hardware Detection
# =============================================================================

class TestHardwareDetection:
    """Test system hardware detection capabilities."""

    @pytest.mark.asyncio
    async def test_cpu_detection_with_psutil(self):
        """Should detect CPU cores using psutil."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(side_effect=lambda logical: 8 if logical else 4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(
            total=16 * 1024 * 1024 * 1024,
            available=8 * 1024 * 1024 * 1024
        ))
        mock_psutil.disk_usage = Mock(return_value=Mock(
            free=100 * 1024 * 1024 * 1024
        ))

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            service = ResourceService()
            await service.initialize()

            assert service.resources.cpu_cores_physical == 4
            assert service.resources.cpu_cores_logical == 8
            assert service.resources.ram_total_mb == 16384
            assert service.resources.ram_available_mb == 8192

    @pytest.mark.asyncio
    async def test_cpu_detection_without_psutil(self):
        """Should fall back to os.cpu_count when psutil unavailable."""
        with patch.dict('sys.modules', {'psutil': None}):
            with patch('os.cpu_count', return_value=4):
                service = ResourceService()
                await service.initialize()

                assert service.resources.cpu_cores_logical == 4
                assert service.resources.cpu_cores_physical == 2  # Half of logical

    @pytest.mark.asyncio
    async def test_ram_detection(self):
        """Should detect RAM using psutil."""
        mock_memory = Mock()
        mock_memory.total = 32 * 1024 * 1024 * 1024  # 32GB
        mock_memory.available = 16 * 1024 * 1024 * 1024  # 16GB

        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=mock_memory)
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100 * 1024 * 1024 * 1024))

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            service = ResourceService()
            await service.initialize()

            assert service.resources.ram_total_mb == 32768
            assert service.resources.ram_available_mb == 16384

    @pytest.mark.asyncio
    async def test_gpu_detection_with_cuda(self):
        """Should detect GPU when CUDA is available."""
        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="NVIDIA RTX 4090")

        mock_props = Mock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024  # 24GB
        mock_props.major = 8
        mock_props.minor = 9
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.1"

        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        with patch.dict('sys.modules', {'torch': mock_torch, 'psutil': mock_psutil}):
            service = ResourceService()
            await service.initialize()

            assert service.resources.gpu_available is True
            assert service.resources.gpu_name == "NVIDIA RTX 4090"
            assert service.resources.gpu_vram_mb == 24576
            assert service.resources.gpu_compute_capability == (8, 9)
            assert service.resources.cuda_version == "12.1"

    @pytest.mark.asyncio
    async def test_gpu_detection_without_cuda(self):
        """Should handle no GPU when CUDA not available."""
        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        with patch.dict('sys.modules', {'torch': mock_torch, 'psutil': mock_psutil}):
            service = ResourceService()
            await service.initialize()

            assert service.resources.gpu_available is False
            assert service.resources.gpu_name is None
            assert service.resources.gpu_vram_mb == 0

    @pytest.mark.asyncio
    async def test_gpu_detection_without_torch(self):
        """Should handle when PyTorch is not installed."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        # Simulate ImportError for torch
        def mock_import(name, *args, **kwargs):
            if name == 'torch':
                raise ImportError("No module named 'torch'")
            return __import__(name, *args, **kwargs)

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            with patch('builtins.__import__', side_effect=mock_import):
                service = ResourceService()
                await service.initialize()

                assert service.resources.gpu_available is False


# =============================================================================
# Test 2: Tier Assignment
# =============================================================================

class TestTierAssignment:
    """Test resource tier assignment based on detected hardware."""

    @pytest.mark.asyncio
    async def test_minimal_tier_no_gpu(self):
        """Should assign MINIMAL tier when no GPU available."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=8*1024**3, available=4*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            assert service.tier == ResourceTier.MINIMAL

    @pytest.mark.asyncio
    async def test_standard_tier_small_gpu(self):
        """Should assign STANDARD tier with < 6GB VRAM."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="GTX 1660 Ti")
        mock_props = Mock()
        mock_props.total_memory = 4 * 1024 * 1024 * 1024  # 4GB VRAM
        mock_props.major = 7
        mock_props.minor = 5
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "11.8"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            assert service.tier == ResourceTier.STANDARD
            assert service.resources.gpu_vram_mb == 4096

    @pytest.mark.asyncio
    async def test_recommended_tier_medium_gpu(self):
        """Should assign RECOMMENDED tier with 6-12GB VRAM."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=12)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=32*1024**3, available=16*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=500*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_props = Mock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024  # 8GB VRAM
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            assert service.tier == ResourceTier.RECOMMENDED
            assert service.resources.gpu_vram_mb == 8192

    @pytest.mark.asyncio
    async def test_power_tier_large_gpu(self):
        """Should assign POWER tier with > 12GB VRAM."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=16)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=64*1024**3, available=32*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=1000*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 4090")
        mock_props = Mock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024  # 24GB VRAM
        mock_props.major = 8
        mock_props.minor = 9
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.1"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            assert service.tier == ResourceTier.POWER
            assert service.resources.gpu_vram_mb == 24576

    @pytest.mark.asyncio
    async def test_force_tier_override(self):
        """Should allow forcing a specific tier via config."""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "resources.force_tier": "recommended"
        }.get(key, default))

        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=8*1024**3, available=4*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService(config=mock_config)
            await service.initialize()

            # Despite no GPU (would normally be MINIMAL), should be RECOMMENDED
            assert service.tier == ResourceTier.RECOMMENDED


# =============================================================================
# Test 3: Pool Configuration
# =============================================================================

class TestPoolConfiguration:
    """Test worker pool configuration based on tier."""

    @pytest.mark.asyncio
    async def test_get_pool_limits_minimal(self):
        """Should return pool configs for MINIMAL tier."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=8*1024**3, available=4*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            pools = service.get_pool_limits()

            assert "io-file" in pools
            assert pools["io-file"].max_workers == 10
            assert "gpu-paddle" in pools
            assert pools["gpu-paddle"].enabled is False
            assert pools["gpu-paddle"].fallback == "cpu-paddle"

    @pytest.mark.asyncio
    async def test_get_pool_limits_power(self):
        """Should return pool configs for POWER tier."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=16)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=64*1024**3, available=32*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=1000*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 4090")
        mock_props = Mock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024
        mock_props.major = 8
        mock_props.minor = 9
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.1"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            pools = service.get_pool_limits()

            assert pools["io-file"].max_workers == 50
            assert pools["cpu-light"].max_workers == 50
            assert pools["gpu-paddle"].enabled is True
            assert pools["gpu-paddle"].max_workers == 2
            assert pools["gpu-paddle"].gpu_memory_mb == 2000

    @pytest.mark.asyncio
    async def test_disabled_pools_handling(self):
        """Should handle disabled pools correctly."""
        mock_config = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "resources.disabled_pools": ["gpu-embed", "llm-analysis"]
        }.get(key, default))

        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_props = Mock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService(config=mock_config)
            await service.initialize()

            disabled = service.get_disabled_pools()
            assert "gpu-embed" in disabled
            assert "llm-analysis" in disabled

            enabled = service.get_enabled_pools()
            assert "gpu-embed" not in enabled
            assert "llm-analysis" not in enabled

    @pytest.mark.asyncio
    async def test_fallback_pool_mapping(self):
        """Should correctly map disabled GPU pools to CPU fallbacks."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=8*1024**3, available=4*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # In MINIMAL tier, GPU pools are disabled
            assert service.get_fallback_pool("gpu-paddle") == "cpu-paddle"
            assert service.get_fallback_pool("gpu-embed") == "cpu-embed"
            assert service.get_fallback_pool("gpu-whisper") == "cpu-whisper"

    @pytest.mark.asyncio
    async def test_get_best_pool_with_fallback(self):
        """Should return best available pool (preferred or fallback)."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=8*1024**3, available=4*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # GPU pools disabled in MINIMAL, should get CPU fallback
            best = service.get_best_pool("gpu-embed")
            assert best == "cpu-embed"

            # Enabled pool should return itself
            best = service.get_best_pool("cpu-light")
            assert best == "cpu-light"


# =============================================================================
# Test 4: GPU Memory Management
# =============================================================================

class TestGPUMemoryManagement:
    """Test GPU memory allocation and tracking."""

    @pytest.mark.asyncio
    async def test_gpu_allocate_memory(self):
        """Should allocate GPU memory for models."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_props = Mock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024  # 8GB
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Allocate memory for paddle (2000MB)
            success = await service.gpu_allocate("paddle")
            assert success is True

            # Check allocation tracked
            state = service.get_state()
            assert "paddle" in state["gpu"]["allocations"]
            assert state["gpu"]["allocations"]["paddle"] == 2000

    @pytest.mark.asyncio
    async def test_gpu_release_memory(self):
        """Should release GPU memory."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_props = Mock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            await service.gpu_allocate("paddle")
            await service.gpu_release("paddle")

            state = service.get_state()
            assert "paddle" not in state["gpu"]["allocations"]

    @pytest.mark.asyncio
    async def test_gpu_wait_for_memory_success(self):
        """Should wait and allocate when memory becomes available."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_props = Mock()
        mock_props.total_memory = 4 * 1024 * 1024 * 1024  # Small GPU
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Allocate most of the memory
            await service.gpu_allocate("paddle")

            # Schedule release after a delay
            async def release_later():
                await asyncio.sleep(0.5)
                await service.gpu_release("paddle")

            asyncio.create_task(release_later())

            # Wait for memory (should succeed after release)
            success = await service.gpu_wait_for_memory("bge-m3", timeout=2)
            assert success is True

    @pytest.mark.asyncio
    async def test_gpu_wait_for_memory_timeout(self):
        """Should raise GPUMemoryError on timeout."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 3060")
        mock_props = Mock()
        mock_props.total_memory = 2 * 1024 * 1024 * 1024  # Very small GPU
        mock_props.major = 8
        mock_props.minor = 6
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.0"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Try to allocate more than available
            with pytest.raises(GPUMemoryError):
                await service.gpu_wait_for_memory("qwen", timeout=1)

    @pytest.mark.asyncio
    async def test_gpu_allocation_tracking(self):
        """Should track multiple GPU allocations."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(return_value=16)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=64*1024**3, available=32*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=1000*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=True)
        mock_torch.cuda.get_device_name = Mock(return_value="RTX 4090")
        mock_props = Mock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024
        mock_props.major = 8
        mock_props.minor = 9
        mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
        mock_torch.version.cuda = "12.1"

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Allocate multiple models
            await service.gpu_allocate("paddle")
            await service.gpu_allocate("bge-m3")

            state = service.get_state()
            assert len(state["gpu"]["allocations"]) == 2
            assert state["gpu"]["allocations"]["paddle"] == 2000
            assert state["gpu"]["allocations"]["bge-m3"] == 2000


# =============================================================================
# Test 5: CPU Thread Management
# =============================================================================

class TestCPUThreadManagement:
    """Test CPU thread allocation and tracking."""

    @pytest.mark.asyncio
    async def test_cpu_acquire_threads(self):
        """Should acquire CPU threads."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(side_effect=lambda logical: 8 if logical else 4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Max threads = 8 * 0.8 = 6 (with 80% utilization cap)
            max_threads = service.get_max_cpu_threads()
            assert max_threads == 6

            # Acquire 4 threads
            success = await service.cpu_acquire(4)
            assert success is True

            available = service.get_available_cpu_threads()
            assert available == 2

    @pytest.mark.asyncio
    async def test_cpu_release_threads(self):
        """Should release CPU threads."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(side_effect=lambda logical: 8 if logical else 4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            await service.cpu_acquire(4)
            await service.cpu_release(4)

            available = service.get_available_cpu_threads()
            assert available == 6  # Back to max

    @pytest.mark.asyncio
    async def test_cpu_thread_limit_enforcement(self):
        """Should enforce CPU thread limits."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(side_effect=lambda logical: 8 if logical else 4)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=16*1024**3, available=8*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=100*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Try to acquire more than max (6)
            success = await service.cpu_acquire(10)
            assert success is False

            # Available should still be max
            available = service.get_available_cpu_threads()
            assert available == 6

    @pytest.mark.asyncio
    async def test_cpu_thread_state_tracking(self):
        """Should track CPU thread allocation state."""
        mock_psutil = Mock()
        mock_psutil.cpu_count = Mock(side_effect=lambda logical: 16 if logical else 8)
        mock_psutil.virtual_memory = Mock(return_value=Mock(total=32*1024**3, available=16*1024**3))
        mock_psutil.disk_usage = Mock(return_value=Mock(free=500*1024**3))

        mock_torch = Mock()
        mock_torch.cuda.is_available = Mock(return_value=False)

        with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
            service = ResourceService()
            await service.initialize()

            # Max = 16 * 0.8 = 12
            await service.cpu_acquire(5)

            state = service.get_state()
            assert state["cpu"]["max_threads"] == 12
            assert state["cpu"]["allocated_threads"] == 5
            assert state["cpu"]["available_threads"] == 7


# =============================================================================
# Smoke Test (can run directly)
# =============================================================================

async def smoke_test():
    """Quick smoke test for ResourceService."""
    print("=" * 60)
    print("ResourceService Smoke Test")
    print("=" * 60)

    mock_psutil = Mock()
    mock_psutil.cpu_count = Mock(side_effect=lambda logical: 8 if logical else 4)
    mock_psutil.virtual_memory = Mock(return_value=Mock(
        total=16 * 1024 * 1024 * 1024,
        available=8 * 1024 * 1024 * 1024
    ))
    mock_psutil.disk_usage = Mock(return_value=Mock(free=100 * 1024 * 1024 * 1024))

    mock_torch = Mock()
    mock_torch.cuda.is_available = Mock(return_value=True)
    mock_torch.cuda.get_device_name = Mock(return_value="Test GPU")
    mock_props = Mock()
    mock_props.total_memory = 8 * 1024 * 1024 * 1024
    mock_props.major = 8
    mock_props.minor = 6
    mock_torch.cuda.get_device_properties = Mock(return_value=mock_props)
    mock_torch.version.cuda = "12.0"

    with patch.dict('sys.modules', {'psutil': mock_psutil, 'torch': mock_torch}):
        print("\n1. Testing initialization...")
        service = ResourceService()
        await service.initialize()
        print("   OK - Service initialized")

        print("\n2. Testing resource detection...")
        assert service.resources.cpu_cores_logical == 8
        assert service.resources.gpu_available is True
        print("   OK - Resources detected")

        print("\n3. Testing tier assignment...")
        assert service.tier == ResourceTier.RECOMMENDED
        print(f"   OK - Tier: {service.tier.value}")

        print("\n4. Testing GPU allocation...")
        success = await service.gpu_allocate("paddle")
        assert success is True
        await service.gpu_release("paddle")
        print("   OK - GPU memory management works")

        print("\n5. Testing CPU allocation...")
        success = await service.cpu_acquire(4)
        assert success is True
        await service.cpu_release(4)
        print("   OK - CPU thread management works")

        await service.shutdown()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(smoke_test())
    exit(0 if result else 1)
