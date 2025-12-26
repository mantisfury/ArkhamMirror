"""
Dashboard Shard - Shard Tests

Tests for the DashboardShard class including initialization,
lifecycle, and service monitoring methods.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from arkham_shard_dashboard.shard import DashboardShard


class TestShardMetadata:
    """Tests for shard metadata and manifest."""

    def test_shard_name(self):
        """Test shard name."""
        shard = DashboardShard()
        assert shard.name == "dashboard"

    def test_shard_version(self):
        """Test shard version."""
        shard = DashboardShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = DashboardShard()
        assert "monitoring" in shard.description.lower() or "control" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.db = MagicMock()
        frame.vectors = MagicMock()
        frame.llm = MagicMock()
        frame.workers = MagicMock()
        frame.events = MagicMock()
        frame.config = MagicMock()
        frame.shards = {}
        return frame

    @pytest.mark.asyncio
    async def test_initialize(self, mock_frame):
        """Test shard initialization."""
        shard = DashboardShard()
        await shard.initialize(mock_frame)

        assert shard.frame == mock_frame

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_frame):
        """Test shard shutdown."""
        shard = DashboardShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        # Should complete without error


class TestShardRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the FastAPI router."""
        shard = DashboardShard()
        routes = shard.get_routes()
        assert routes is not None


class TestServiceHealth:
    """Tests for service health monitoring."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.db = MagicMock()
        shard.frame.vectors = MagicMock()
        shard.frame.vectors.is_available = MagicMock(return_value=True)
        shard.frame.llm = MagicMock()
        shard.frame.llm.is_available = MagicMock(return_value=True)
        shard.frame.llm.get_endpoint = MagicMock(return_value="http://localhost:11434")
        shard.frame.workers = MagicMock()
        shard.frame.workers.is_available = MagicMock(return_value=True)
        shard.frame.workers.get_queue_stats = AsyncMock(return_value={})
        shard.frame.events = MagicMock()
        shard.frame.config = MagicMock()
        shard.frame.config.database_url = "postgresql://localhost:5432/arkham"
        return shard

    @pytest.mark.asyncio
    async def test_get_service_health(self, initialized_shard):
        """Test getting service health."""
        health = await initialized_shard.get_service_health()

        assert "database" in health
        assert "vectors" in health
        assert "llm" in health
        assert "workers" in health
        assert "events" in health

    @pytest.mark.asyncio
    async def test_get_service_health_database_available(self, initialized_shard):
        """Test database health when available."""
        health = await initialized_shard.get_service_health()

        assert health["database"]["available"] is True

    @pytest.mark.asyncio
    async def test_get_service_health_vectors_available(self, initialized_shard):
        """Test vectors health when available."""
        health = await initialized_shard.get_service_health()

        assert health["vectors"]["available"] is True

    @pytest.mark.asyncio
    async def test_get_service_health_llm_available(self, initialized_shard):
        """Test LLM health when available."""
        health = await initialized_shard.get_service_health()

        assert health["llm"]["available"] is True
        assert health["llm"]["info"]["endpoint"] == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_get_service_health_no_services(self):
        """Test health when no services available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.db = None
        shard.frame.vectors = None
        shard.frame.llm = None
        shard.frame.workers = None

        health = await shard.get_service_health()

        assert health["database"]["available"] is False
        assert health["vectors"]["available"] is False
        assert health["llm"]["available"] is False
        assert health["workers"]["available"] is False


class TestLLMConfiguration:
    """Tests for LLM configuration methods."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.config = MagicMock()
        shard.frame.config.llm_endpoint = "http://localhost:11434"
        shard.frame.config.get = MagicMock(return_value="llama2")
        shard.frame.config.set = MagicMock()
        shard.frame.llm = MagicMock()
        shard.frame.llm.is_available = MagicMock(return_value=True)
        shard.frame.llm.shutdown = AsyncMock()
        shard.frame.llm.initialize = AsyncMock()
        shard.frame.llm.chat = AsyncMock(return_value="OK")
        return shard

    @pytest.mark.asyncio
    async def test_get_llm_config(self, initialized_shard):
        """Test getting LLM configuration."""
        config = await initialized_shard.get_llm_config()

        assert config["endpoint"] == "http://localhost:11434"
        assert config["model"] == "llama2"
        assert config["available"] is True

    @pytest.mark.asyncio
    async def test_update_llm_config(self, initialized_shard):
        """Test updating LLM configuration."""
        await initialized_shard.update_llm_config(
            endpoint="http://newhost:11434",
            model="mistral",
        )

        initialized_shard.frame.config.set.assert_any_call("llm_endpoint", "http://newhost:11434")
        initialized_shard.frame.config.set.assert_any_call("llm.model", "mistral")

    @pytest.mark.asyncio
    async def test_test_llm_connection_success(self, initialized_shard):
        """Test successful LLM connection test."""
        result = await initialized_shard.test_llm_connection()

        assert result["success"] is True
        assert result["response"] == "OK"

    @pytest.mark.asyncio
    async def test_test_llm_connection_no_service(self):
        """Test LLM connection when service not available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.llm = None

        result = await shard.test_llm_connection()

        assert result["success"] is False
        assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_test_llm_connection_failure(self, initialized_shard):
        """Test LLM connection failure."""
        initialized_shard.frame.llm.chat = AsyncMock(side_effect=Exception("Connection refused"))

        result = await initialized_shard.test_llm_connection()

        assert result["success"] is False
        assert "Connection refused" in result["error"]


class TestDatabaseControls:
    """Tests for database control methods."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.db = MagicMock()
        shard.frame.config = MagicMock()
        shard.frame.config.database_url = "postgresql://localhost:5432/arkham"
        return shard

    @pytest.mark.asyncio
    async def test_get_database_info(self, initialized_shard):
        """Test getting database info."""
        info = await initialized_shard.get_database_info()

        assert info["available"] is True
        assert "..." in info["url"]  # URL should be truncated

    @pytest.mark.asyncio
    async def test_get_database_info_no_db(self):
        """Test database info when no database."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.db = None

        info = await shard.get_database_info()

        assert info["available"] is False

    @pytest.mark.asyncio
    async def test_run_migrations(self, initialized_shard):
        """Test running migrations."""
        result = await initialized_shard.run_migrations()

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_reset_database_no_confirm(self, initialized_shard):
        """Test reset database without confirmation."""
        result = await initialized_shard.reset_database(confirm=False)

        assert result["success"] is False
        assert "Confirmation required" in result["error"]

    @pytest.mark.asyncio
    async def test_reset_database_with_confirm(self, initialized_shard):
        """Test reset database with confirmation."""
        result = await initialized_shard.reset_database(confirm=True)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_vacuum_database(self, initialized_shard):
        """Test vacuum database."""
        result = await initialized_shard.vacuum_database()

        assert result["success"] is True


class TestWorkerControls:
    """Tests for worker control methods."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.workers = MagicMock()
        shard.frame.workers.get_workers = AsyncMock(return_value=[
            {"id": "w1", "queue": "embeddings", "status": "running"},
        ])
        shard.frame.workers.get_queue_stats = AsyncMock(return_value=[
            {"queue": "embeddings", "pending": 10},
        ])
        shard.frame.workers.scale = AsyncMock(return_value=True)
        shard.frame.workers.start_worker = AsyncMock(return_value={"success": True})
        shard.frame.workers.stop_worker = AsyncMock(return_value={"success": True})
        return shard

    @pytest.mark.asyncio
    async def test_get_workers(self, initialized_shard):
        """Test getting workers."""
        workers = await initialized_shard.get_workers()

        assert len(workers) == 1
        assert workers[0]["id"] == "w1"

    @pytest.mark.asyncio
    async def test_get_workers_no_service(self):
        """Test getting workers when service not available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.workers = None

        workers = await shard.get_workers()

        assert workers == []

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, initialized_shard):
        """Test getting queue stats."""
        stats = await initialized_shard.get_queue_stats()

        assert len(stats) == 1
        assert stats[0]["queue"] == "embeddings"

    @pytest.mark.asyncio
    async def test_scale_workers(self, initialized_shard):
        """Test scaling workers."""
        result = await initialized_shard.scale_workers(queue="embeddings", count=4)

        assert result["success"] is True
        assert result["queue"] == "embeddings"
        assert result["target_count"] == 4

    @pytest.mark.asyncio
    async def test_scale_workers_no_service(self):
        """Test scaling when service not available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.workers = None

        result = await shard.scale_workers(queue="embeddings", count=4)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_start_worker(self, initialized_shard):
        """Test starting a worker."""
        result = await initialized_shard.start_worker(queue="parsing")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_stop_worker(self, initialized_shard):
        """Test stopping a worker."""
        result = await initialized_shard.stop_worker(worker_id="w1")

        assert result["success"] is True


class TestEvents:
    """Tests for event retrieval methods."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = DashboardShard()
        shard.frame = MagicMock()

        # Create mock events
        mock_event = MagicMock()
        mock_event.event_type = "document.ingested"
        mock_event.payload = {"doc_id": "123"}
        mock_event.source = "ingest"
        mock_event.timestamp = MagicMock()
        mock_event.timestamp.isoformat = MagicMock(return_value="2024-01-01T00:00:00")

        mock_error_event = MagicMock()
        mock_error_event.event_type = "parsing.error"
        mock_error_event.payload = {"doc_id": "456"}
        mock_error_event.source = "parse"
        mock_error_event.timestamp = MagicMock()
        mock_error_event.timestamp.isoformat = MagicMock(return_value="2024-01-01T00:01:00")

        shard.frame.events = MagicMock()
        shard.frame.events.get_events = MagicMock(return_value=[mock_event, mock_error_event])
        return shard

    @pytest.mark.asyncio
    async def test_get_events(self, initialized_shard):
        """Test getting events."""
        events = await initialized_shard.get_events(limit=50)

        assert len(events) == 2
        assert events[0]["event_type"] == "document.ingested"

    @pytest.mark.asyncio
    async def test_get_events_no_service(self):
        """Test getting events when service not available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.events = None

        events = await shard.get_events()

        assert events == []

    @pytest.mark.asyncio
    async def test_get_errors(self, initialized_shard):
        """Test getting error events."""
        errors = await initialized_shard.get_errors(limit=50)

        # Should filter to only error events
        assert len(errors) == 1
        assert "error" in errors[0]["event_type"].lower()

    @pytest.mark.asyncio
    async def test_get_errors_no_service(self):
        """Test getting errors when service not available."""
        shard = DashboardShard()
        shard.frame = MagicMock()
        shard.frame.events = None

        errors = await shard.get_errors()

        assert errors == []
