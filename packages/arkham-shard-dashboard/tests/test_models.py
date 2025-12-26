"""
Dashboard Shard - Model Tests

Tests for all Pydantic models and enums.
"""

import pytest
from datetime import datetime

from arkham_shard_dashboard.models import (
    ServiceStatus,
    ServiceHealth,
    SystemHealth,
    LLMConfig,
    UpdateLLMRequest,
    LLMTestResult,
    DatabaseInfo,
    MigrationResult,
    ResetDatabaseRequest,
    VacuumResult,
    WorkerInfo,
    QueueStats,
    ScaleWorkersRequest,
    ScaleWorkersResult,
    StartWorkerRequest,
    StartWorkerResult,
    StopWorkerRequest,
    StopWorkerResult,
    EventInfo,
    EventListResponse,
    ErrorInfo,
    ErrorListResponse,
    ShardInfo,
    SystemInfo,
    DashboardStats,
)


class TestServiceStatusEnum:
    """Tests for ServiceStatus enum."""

    def test_available_value(self):
        """Test AVAILABLE status value."""
        assert ServiceStatus.AVAILABLE.value == "available"

    def test_unavailable_value(self):
        """Test UNAVAILABLE status value."""
        assert ServiceStatus.UNAVAILABLE.value == "unavailable"

    def test_degraded_value(self):
        """Test DEGRADED status value."""
        assert ServiceStatus.DEGRADED.value == "degraded"

    def test_initializing_value(self):
        """Test INITIALIZING status value."""
        assert ServiceStatus.INITIALIZING.value == "initializing"


class TestServiceHealthModel:
    """Tests for ServiceHealth Pydantic model."""

    def test_default_initialization(self):
        """Test ServiceHealth with defaults."""
        health = ServiceHealth()
        assert health.available is False
        assert health.status == ServiceStatus.UNAVAILABLE
        assert health.info is None

    def test_available_service(self):
        """Test ServiceHealth for available service."""
        health = ServiceHealth(
            available=True,
            status=ServiceStatus.AVAILABLE,
            info={"endpoint": "http://localhost:8080"},
        )
        assert health.available is True
        assert health.status == ServiceStatus.AVAILABLE
        assert health.info["endpoint"] == "http://localhost:8080"


class TestSystemHealthModel:
    """Tests for SystemHealth Pydantic model."""

    def test_default_initialization(self):
        """Test SystemHealth with defaults."""
        health = SystemHealth()
        assert health.database.available is False
        assert health.vectors.available is False
        assert health.llm.available is False
        assert health.workers.available is False
        assert health.events.available is False
        assert health.storage.available is False


class TestLLMConfigModel:
    """Tests for LLMConfig Pydantic model."""

    def test_default_initialization(self):
        """Test LLMConfig with defaults."""
        config = LLMConfig()
        assert config.endpoint is None
        assert config.model is None
        assert config.available is False
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_custom_initialization(self):
        """Test LLMConfig with custom values."""
        config = LLMConfig(
            endpoint="http://localhost:11434",
            model="llama2",
            available=True,
            max_tokens=8192,
            temperature=0.5,
        )
        assert config.endpoint == "http://localhost:11434"
        assert config.model == "llama2"
        assert config.available is True
        assert config.max_tokens == 8192
        assert config.temperature == 0.5


class TestUpdateLLMRequestModel:
    """Tests for UpdateLLMRequest Pydantic model."""

    def test_partial_update(self):
        """Test partial LLM config update."""
        request = UpdateLLMRequest(endpoint="http://newhost:11434")
        assert request.endpoint == "http://newhost:11434"
        assert request.model is None

    def test_full_update(self):
        """Test full LLM config update."""
        request = UpdateLLMRequest(
            endpoint="http://newhost:11434",
            model="mistral",
            max_tokens=4096,
            temperature=0.8,
        )
        assert request.endpoint == "http://newhost:11434"
        assert request.model == "mistral"


class TestLLMTestResultModel:
    """Tests for LLMTestResult Pydantic model."""

    def test_success_result(self):
        """Test successful LLM test result."""
        result = LLMTestResult(
            success=True,
            response="OK",
            latency_ms=150.5,
        )
        assert result.success is True
        assert result.response == "OK"
        assert result.error is None

    def test_failure_result(self):
        """Test failed LLM test result."""
        result = LLMTestResult(
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"
        assert result.response is None


class TestDatabaseInfoModel:
    """Tests for DatabaseInfo Pydantic model."""

    def test_default_initialization(self):
        """Test DatabaseInfo with defaults."""
        info = DatabaseInfo()
        assert info.available is False
        assert info.url is None
        assert info.schemas == []

    def test_available_database(self):
        """Test DatabaseInfo for available database."""
        info = DatabaseInfo(
            available=True,
            url="postgresql://localhost/...",
            schemas=["public", "arkham"],
            size_mb=150.5,
            table_count=25,
        )
        assert info.available is True
        assert info.size_mb == 150.5
        assert info.table_count == 25


class TestMigrationResultModel:
    """Tests for MigrationResult Pydantic model."""

    def test_success_result(self):
        """Test successful migration result."""
        result = MigrationResult(
            success=True,
            message="3 migrations applied",
            migrations_applied=3,
        )
        assert result.success is True
        assert result.migrations_applied == 3
        assert result.errors == []

    def test_failure_result(self):
        """Test failed migration result."""
        result = MigrationResult(
            success=False,
            message="Migration failed",
            errors=["Column already exists"],
        )
        assert result.success is False
        assert len(result.errors) == 1


class TestResetDatabaseRequestModel:
    """Tests for ResetDatabaseRequest Pydantic model."""

    def test_default_no_confirm(self):
        """Test default is no confirmation."""
        request = ResetDatabaseRequest()
        assert request.confirm is False

    def test_with_confirmation(self):
        """Test with confirmation."""
        request = ResetDatabaseRequest(confirm=True)
        assert request.confirm is True


class TestVacuumResultModel:
    """Tests for VacuumResult Pydantic model."""

    def test_success_result(self):
        """Test successful vacuum result."""
        result = VacuumResult(
            success=True,
            message="VACUUM completed",
            space_reclaimed_mb=25.5,
        )
        assert result.success is True
        assert result.space_reclaimed_mb == 25.5


class TestWorkerInfoModel:
    """Tests for WorkerInfo Pydantic model."""

    def test_initialization(self):
        """Test WorkerInfo initialization."""
        worker = WorkerInfo(
            id="worker-123",
            queue="embeddings",
            status="running",
            jobs_processed=150,
            current_job="job-456",
        )
        assert worker.id == "worker-123"
        assert worker.queue == "embeddings"
        assert worker.jobs_processed == 150


class TestQueueStatsModel:
    """Tests for QueueStats Pydantic model."""

    def test_default_initialization(self):
        """Test QueueStats with defaults."""
        stats = QueueStats(queue="embeddings")
        assert stats.queue == "embeddings"
        assert stats.pending == 0
        assert stats.processing == 0
        assert stats.completed == 0

    def test_populated_stats(self):
        """Test QueueStats with data."""
        stats = QueueStats(
            queue="parsing",
            pending=10,
            processing=2,
            completed=100,
            failed=5,
            workers_active=2,
            workers_max=4,
        )
        assert stats.pending == 10
        assert stats.workers_active == 2


class TestScaleWorkersRequestModel:
    """Tests for ScaleWorkersRequest Pydantic model."""

    def test_initialization(self):
        """Test ScaleWorkersRequest initialization."""
        request = ScaleWorkersRequest(queue="embeddings", count=4)
        assert request.queue == "embeddings"
        assert request.count == 4


class TestScaleWorkersResultModel:
    """Tests for ScaleWorkersResult Pydantic model."""

    def test_success_result(self):
        """Test successful scale result."""
        result = ScaleWorkersResult(
            success=True,
            queue="embeddings",
            target_count=4,
            current_count=4,
        )
        assert result.success is True
        assert result.target_count == 4


class TestStartWorkerRequestModel:
    """Tests for StartWorkerRequest Pydantic model."""

    def test_initialization(self):
        """Test StartWorkerRequest initialization."""
        request = StartWorkerRequest(queue="parsing")
        assert request.queue == "parsing"


class TestStartWorkerResultModel:
    """Tests for StartWorkerResult Pydantic model."""

    def test_success_result(self):
        """Test successful start result."""
        result = StartWorkerResult(
            success=True,
            worker_id="worker-new-123",
            queue="parsing",
        )
        assert result.success is True
        assert result.worker_id == "worker-new-123"


class TestStopWorkerRequestModel:
    """Tests for StopWorkerRequest Pydantic model."""

    def test_initialization(self):
        """Test StopWorkerRequest initialization."""
        request = StopWorkerRequest(worker_id="worker-123")
        assert request.worker_id == "worker-123"


class TestStopWorkerResultModel:
    """Tests for StopWorkerResult Pydantic model."""

    def test_success_result(self):
        """Test successful stop result."""
        result = StopWorkerResult(
            success=True,
            worker_id="worker-123",
        )
        assert result.success is True
        assert result.error is None


class TestEventInfoModel:
    """Tests for EventInfo Pydantic model."""

    def test_initialization(self):
        """Test EventInfo initialization."""
        event = EventInfo(
            event_type="document.ingested",
            payload={"doc_id": "doc-123"},
            source="ingest-shard",
        )
        assert event.event_type == "document.ingested"
        assert event.source == "ingest-shard"


class TestEventListResponseModel:
    """Tests for EventListResponse Pydantic model."""

    def test_initialization(self):
        """Test EventListResponse initialization."""
        event = EventInfo(
            event_type="test.event",
            payload={},
            source="test",
        )
        response = EventListResponse(events=[event], total=1)
        assert len(response.events) == 1
        assert response.total == 1


class TestErrorInfoModel:
    """Tests for ErrorInfo Pydantic model."""

    def test_initialization(self):
        """Test ErrorInfo initialization."""
        error = ErrorInfo(
            event_type="parsing.error",
            payload={"doc_id": "doc-123"},
            source="parse-shard",
            error_message="Failed to parse PDF",
        )
        assert error.event_type == "parsing.error"
        assert error.error_message == "Failed to parse PDF"


class TestErrorListResponseModel:
    """Tests for ErrorListResponse Pydantic model."""

    def test_initialization(self):
        """Test ErrorListResponse initialization."""
        error = ErrorInfo(
            event_type="error",
            payload={},
            source="test",
        )
        response = ErrorListResponse(errors=[error], total=1)
        assert len(response.errors) == 1


class TestShardInfoModel:
    """Tests for ShardInfo Pydantic model."""

    def test_initialization(self):
        """Test ShardInfo initialization."""
        shard = ShardInfo(
            name="search",
            version="0.1.0",
            description="Search functionality",
            api_prefix="/api/search",
            category="Search",
        )
        assert shard.name == "search"
        assert shard.status == "active"


class TestSystemInfoModel:
    """Tests for SystemInfo Pydantic model."""

    def test_default_initialization(self):
        """Test SystemInfo with defaults."""
        info = SystemInfo()
        assert info.frame_version == "0.1.0"
        assert info.shards_loaded == 0
        assert info.shards == []

    def test_populated_info(self):
        """Test SystemInfo with data."""
        shard = ShardInfo(
            name="search",
            version="0.1.0",
            description="Search",
            api_prefix="/api/search",
            category="Search",
        )
        info = SystemInfo(
            shards_loaded=1,
            shards=[shard],
            uptime_seconds=3600.0,
        )
        assert info.shards_loaded == 1
        assert info.uptime_seconds == 3600.0


class TestDashboardStatsModel:
    """Tests for DashboardStats Pydantic model."""

    def test_default_initialization(self):
        """Test DashboardStats with defaults."""
        stats = DashboardStats()
        assert stats.total_documents == 0
        assert stats.total_entities == 0
        assert stats.services_healthy == 0
        assert stats.services_total == 6

    def test_populated_stats(self):
        """Test DashboardStats with data."""
        stats = DashboardStats(
            total_documents=1000,
            total_entities=5000,
            total_projects=10,
            jobs_pending=5,
            jobs_processing=2,
            errors_last_hour=3,
            services_healthy=5,
        )
        assert stats.total_documents == 1000
        assert stats.services_healthy == 5
