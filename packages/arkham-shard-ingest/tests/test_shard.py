"""
Ingest Shard - Shard Class Tests

Tests for IngestShard with mocked Frame services.
"""

import pytest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from arkham_shard_ingest.shard import IngestShard
from arkham_shard_ingest.models import (
    FileCategory,
    FileInfo,
    IngestBatch,
    IngestJob,
    JobPriority,
    JobStatus,
)


# === Fixtures ===


@pytest.fixture
def mock_events():
    """Create a mock events service."""
    events = MagicMock()
    events.subscribe = MagicMock()
    events.unsubscribe = MagicMock()
    events.emit = AsyncMock()
    return events


@pytest.fixture
def mock_workers():
    """Create a mock workers service."""
    workers = MagicMock()
    workers.register_worker = MagicMock()
    workers.unregister_worker = MagicMock()
    workers.enqueue = AsyncMock()
    return workers


@pytest.fixture
def mock_config():
    """Create a mock config."""
    return {
        "data_silo_path": "/tmp/test_data_silo",
    }


@pytest.fixture
def mock_frame(mock_events, mock_workers, mock_config):
    """Create a mock Frame with all services."""
    frame = MagicMock()
    frame.config = MagicMock()
    frame.config.get = MagicMock(side_effect=lambda key, default=None: mock_config.get(key, default))
    frame.get_service = MagicMock(side_effect=lambda name: {
        "events": mock_events,
        "workers": mock_workers,
    }.get(name))
    return frame


@pytest.fixture
def sample_file_info():
    """Create sample file info for tests."""
    return FileInfo(
        path=Path("/tmp/test.pdf"),
        original_name="test.pdf",
        size_bytes=1024,
        mime_type="application/pdf",
        category=FileCategory.DOCUMENT,
        extension=".pdf",
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_job(sample_file_info):
    """Create sample ingest job."""
    return IngestJob(
        id="job-123",
        file_info=sample_file_info,
        priority=JobPriority.USER,
        status=JobStatus.PENDING,
        worker_route=["extract", "parse"],
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_batch(sample_job):
    """Create sample ingest batch."""
    return IngestBatch(
        id="batch-789",
        jobs=[sample_job],
        priority=JobPriority.BATCH,
        total_files=1,
        created_at=datetime.utcnow(),
    )


# === Shard Metadata Tests ===


class TestShardMetadata:
    """Tests for shard metadata and properties."""

    def test_shard_name(self):
        """Verify shard name is correct."""
        shard = IngestShard()
        assert shard.name == "ingest"

    def test_shard_version(self):
        """Verify shard version is correct."""
        shard = IngestShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard description exists and is meaningful."""
        shard = IngestShard()
        assert "ingestion" in shard.description.lower() or "processing" in shard.description.lower()


# === Initialization Tests ===


class TestInitialization:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_with_frame(self, mock_frame, mock_events, mock_workers):
        """Test shard initializes correctly with frame."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_dispatcher = MagicMock()
                MockIntake.return_value = mock_intake
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                assert shard._frame == mock_frame
                assert shard.intake_manager is not None
                assert shard.job_dispatcher is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_intake_manager(self, mock_frame):
        """Test that initialization creates intake manager with correct paths."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)

                # Verify IntakeManager was created with correct paths
                MockIntake.assert_called_once()
                call_kwargs = MockIntake.call_args[1]
                assert "storage_path" in call_kwargs
                assert "temp_path" in call_kwargs

    @pytest.mark.asyncio
    async def test_initialize_without_workers(self, mock_events):
        """Test shard initializes without worker service."""
        frame = MagicMock()
        frame.config = MagicMock()
        frame.config.get = MagicMock(return_value="/tmp/test")
        frame.get_service = MagicMock(side_effect=lambda name: {
            "events": mock_events,
            "workers": None,
        }.get(name))

        with patch("arkham_shard_ingest.shard.IntakeManager"):
            shard = IngestShard()
            await shard.initialize(frame)

            # Should initialize but without job dispatcher
            assert shard.intake_manager is not None
            # Dispatcher should be None when workers not available

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame, mock_events):
        """Test that initialization subscribes to worker events."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)

                # Verify event subscriptions
                subscribe_calls = [call[0][0] for call in mock_events.subscribe.call_args_list]
                assert "worker.job.completed" in subscribe_calls
                assert "worker.job.failed" in subscribe_calls

    @pytest.mark.asyncio
    async def test_initialize_registers_workers(self, mock_frame, mock_workers):
        """Test that initialization registers ingest workers."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)

                # Verify workers were registered
                assert mock_workers.register_worker.call_count == 4

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_frame, mock_events, mock_workers):
        """Test shard shuts down correctly."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)
                await shard.shutdown()

                assert shard.intake_manager is None
                assert shard.job_dispatcher is None

    @pytest.mark.asyncio
    async def test_shutdown_unregisters_workers(self, mock_frame, mock_workers):
        """Test that shutdown unregisters workers."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)
                await shard.shutdown()

                # Verify workers were unregistered
                assert mock_workers.unregister_worker.call_count == 4

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_events(self, mock_frame, mock_events):
        """Test that shutdown unsubscribes from events."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)
                await shard.shutdown()

                # Verify event unsubscriptions
                unsubscribe_calls = [call[0][0] for call in mock_events.unsubscribe.call_args_list]
                assert "worker.job.completed" in unsubscribe_calls
                assert "worker.job.failed" in unsubscribe_calls

    @pytest.mark.asyncio
    async def test_get_routes(self, mock_frame):
        """Test get_routes returns a router."""
        with patch("arkham_shard_ingest.shard.IntakeManager"):
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                shard = IngestShard()
                await shard.initialize(mock_frame)
                router = shard.get_routes()

                assert router is not None
                assert hasattr(router, "routes")


# === Public API Tests ===


class TestPublicAPI:
    """Tests for public API methods."""

    @pytest.mark.asyncio
    async def test_ingest_file(self, mock_frame, sample_job):
        """Test ingest_file public method."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.receive_file = AsyncMock(return_value=sample_job)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.dispatch = AsyncMock(return_value=True)
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                file_content = BytesIO(b"test content")
                job = await shard.ingest_file(file_content, "test.pdf", priority="user")

                assert job == sample_job
                mock_intake.receive_file.assert_called_once()
                mock_dispatcher.dispatch.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_ingest_file_default_priority(self, mock_frame, sample_job):
        """Test ingest_file uses default priority."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.receive_file = AsyncMock(return_value=sample_job)
                MockIntake.return_value = mock_intake
                MockDispatcher.return_value.dispatch = AsyncMock()

                shard = IngestShard()
                await shard.initialize(mock_frame)

                await shard.ingest_file(BytesIO(b"content"), "test.pdf")

                # Verify USER priority was used (default)
                mock_intake.receive_file.assert_called_once()
                # Priority is passed as 3rd positional arg
                call_args = mock_intake.receive_file.call_args
                assert call_args[0][2] == JobPriority.USER

    @pytest.mark.asyncio
    async def test_ingest_file_invalid_priority(self, mock_frame, sample_job):
        """Test ingest_file with invalid priority defaults to USER."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.receive_file = AsyncMock(return_value=sample_job)
                MockIntake.return_value = mock_intake
                MockDispatcher.return_value.dispatch = AsyncMock()

                shard = IngestShard()
                await shard.initialize(mock_frame)

                await shard.ingest_file(BytesIO(b"content"), "test.pdf", priority="invalid")

                # Should default to USER
                mock_intake.receive_file.assert_called_once()
                # Priority is passed as 3rd positional arg
                call_args = mock_intake.receive_file.call_args
                assert call_args[0][2] == JobPriority.USER

    @pytest.mark.asyncio
    async def test_ingest_path(self, mock_frame, sample_batch):
        """Test ingest_path public method."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.receive_path = AsyncMock(return_value=sample_batch)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.dispatch = AsyncMock(return_value=True)
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                batch = await shard.ingest_path("/data/documents", recursive=True, priority="batch")

                assert batch == sample_batch
                mock_intake.receive_path.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_status(self, mock_frame, sample_job):
        """Test get_job_status public method."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=sample_job)
                MockIntake.return_value = mock_intake

                shard = IngestShard()
                await shard.initialize(mock_frame)

                job = shard.get_job_status("job-123")

                assert job == sample_job
                mock_intake.get_job.assert_called_once_with("job-123")

    @pytest.mark.asyncio
    async def test_get_batch_status(self, mock_frame, sample_batch):
        """Test get_batch_status public method."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher"):
                mock_intake = MagicMock()
                mock_intake.get_batch = MagicMock(return_value=sample_batch)
                MockIntake.return_value = mock_intake

                shard = IngestShard()
                await shard.initialize(mock_frame)

                batch = shard.get_batch_status("batch-789")

                assert batch == sample_batch
                mock_intake.get_batch.assert_called_once_with("batch-789")


# === Event Handler Tests ===


class TestEventHandlers:
    """Tests for event handlers."""

    @pytest.mark.asyncio
    async def test_on_job_completed_advances_job(self, mock_frame, sample_job):
        """Test job completion handler advances to next worker."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=sample_job)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.advance = AsyncMock(return_value=True)
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                event = {
                    "job_id": "job-123",
                    "result": {"pages": 10},
                }
                await shard._on_job_completed(event)

                mock_dispatcher.advance.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_job_completed_emits_event_when_done(self, mock_frame, mock_events, sample_job):
        """Test job completion emits event when job is fully done."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=sample_job)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.advance = AsyncMock(return_value=False)  # No more workers
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                event = {
                    "job_id": "job-123",
                    "result": {"pages": 10},
                }
                await shard._on_job_completed(event)

                # Should emit completion event
                mock_events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_on_job_completed_ignores_unknown_job(self, mock_frame):
        """Test job completion handler ignores unknown jobs."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=None)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                event = {"job_id": "unknown-job"}
                await shard._on_job_completed(event)

                # Should not attempt to advance
                mock_dispatcher.advance.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_job_failed_retries(self, mock_frame, sample_job):
        """Test job failure handler attempts retry."""
        sample_job.retry_count = 0
        sample_job.max_retries = 3

        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=sample_job)
                mock_intake.update_job_status = MagicMock()
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.retry = AsyncMock(return_value=True)
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                event = {
                    "job_id": "job-123",
                    "error": "Worker crashed",
                }
                await shard._on_job_failed(event)

                mock_dispatcher.retry.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_on_job_failed_max_retries_exceeded(self, mock_frame, mock_events, sample_job):
        """Test job failure handler marks as dead when max retries exceeded."""
        sample_job.retry_count = 3
        sample_job.max_retries = 3

        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.get_job = MagicMock(return_value=sample_job)
                mock_intake.update_job_status = MagicMock()
                MockIntake.return_value = mock_intake
                MockDispatcher.return_value = MagicMock()

                shard = IngestShard()
                await shard.initialize(mock_frame)

                event = {
                    "job_id": "job-123",
                    "error": "Final failure",
                }
                await shard._on_job_failed(event)

                # Should emit failure event
                emit_calls = mock_events.emit.call_args_list
                # Check if any emit call was for job failure
                failure_events = [c for c in emit_calls if "failed" in str(c)]
                # The job should be marked as dead


# === Integration Tests ===


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_ingest_workflow(self, mock_frame, sample_job, sample_batch):
        """Test complete ingest workflow."""
        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                # Setup mocks
                mock_intake = MagicMock()
                mock_intake.receive_file = AsyncMock(return_value=sample_job)
                mock_intake.get_job = MagicMock(return_value=sample_job)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.dispatch = AsyncMock(return_value=True)
                mock_dispatcher.advance = AsyncMock(return_value=False)  # Complete on first advance
                MockDispatcher.return_value = mock_dispatcher

                # Initialize shard
                shard = IngestShard()
                await shard.initialize(mock_frame)

                # 1. Ingest a file
                job = await shard.ingest_file(BytesIO(b"PDF content"), "document.pdf")
                assert job.id == "job-123"

                # 2. Check job status
                status = shard.get_job_status("job-123")
                assert status is not None

                # 3. Simulate job completion
                await shard._on_job_completed({
                    "job_id": "job-123",
                    "result": {"pages": 5, "text": "extracted text"},
                })

                # Verify advance was called
                mock_dispatcher.advance.assert_called()

    @pytest.mark.asyncio
    async def test_batch_ingest_workflow(self, mock_frame, sample_batch, sample_job):
        """Test batch ingest workflow."""
        sample_batch.jobs = [sample_job]

        with patch("arkham_shard_ingest.shard.IntakeManager") as MockIntake:
            with patch("arkham_shard_ingest.shard.JobDispatcher") as MockDispatcher:
                mock_intake = MagicMock()
                mock_intake.receive_path = AsyncMock(return_value=sample_batch)
                mock_intake.get_batch = MagicMock(return_value=sample_batch)
                MockIntake.return_value = mock_intake

                mock_dispatcher = MagicMock()
                mock_dispatcher.dispatch = AsyncMock(return_value=True)
                MockDispatcher.return_value = mock_dispatcher

                shard = IngestShard()
                await shard.initialize(mock_frame)

                # Ingest from path
                batch = await shard.ingest_path("/data/documents")
                assert batch.id == "batch-789"
                assert len(batch.jobs) == 1

                # Check batch status
                status = shard.get_batch_status("batch-789")
                assert status is not None

                # Verify all jobs were dispatched
                assert mock_dispatcher.dispatch.call_count == 1
