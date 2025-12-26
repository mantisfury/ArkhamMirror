"""
Ingest Shard - API Tests

Tests for FastAPI endpoints using TestClient.
"""

import pytest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_ingest.api import router, init_api
from arkham_shard_ingest.models import (
    FileCategory,
    FileInfo,
    ImageQuality,
    ImageQualityScore,
    IngestBatch,
    IngestJob,
    JobPriority,
    JobStatus,
)


# === Test Setup ===


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
def sample_image_file_info():
    """Create sample image file info for tests."""
    return FileInfo(
        path=Path("/tmp/scan.png"),
        original_name="scan.png",
        size_bytes=500000,
        mime_type="image/png",
        category=FileCategory.IMAGE,
        extension=".png",
        width=1920,
        height=1080,
        dpi=300,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_quality_score():
    """Create sample image quality score."""
    return ImageQualityScore(
        dpi=300,
        skew_angle=0.5,
        contrast_ratio=0.8,
        is_grayscale=False,
        compression_ratio=0.9,
        has_noise=False,
        layout_complexity="simple",
        analysis_ms=50.0,
    )


@pytest.fixture
def sample_job(sample_file_info):
    """Create sample ingest job."""
    return IngestJob(
        id="job-123",
        file_info=sample_file_info,
        priority=JobPriority.USER,
        status=JobStatus.QUEUED,
        worker_route=["extract", "parse"],
        current_worker="extract",
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_image_job(sample_image_file_info, sample_quality_score):
    """Create sample ingest job for an image."""
    return IngestJob(
        id="job-456",
        file_info=sample_image_file_info,
        priority=JobPriority.USER,
        status=JobStatus.QUEUED,
        worker_route=["image_preprocess", "ocr", "extract"],
        current_worker="image_preprocess",
        quality_score=sample_quality_score,
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


@pytest.fixture
def mock_intake_manager():
    """Create a mock IntakeManager."""
    manager = MagicMock()
    manager.receive_file = AsyncMock()
    manager.receive_batch = AsyncMock()
    manager.receive_path = AsyncMock()
    manager.get_job = MagicMock(return_value=None)
    manager.get_batch = MagicMock(return_value=None)
    manager.get_pending_jobs = MagicMock(return_value=[])
    manager._jobs = {}
    return manager


@pytest.fixture
def mock_job_dispatcher():
    """Create a mock JobDispatcher."""
    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock(return_value=True)
    dispatcher.retry = AsyncMock(return_value=True)
    return dispatcher


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = AsyncMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def app(mock_intake_manager, mock_job_dispatcher, mock_event_bus):
    """Create test FastAPI app with mocked dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)

    init_api(
        intake_manager=mock_intake_manager,
        job_dispatcher=mock_job_dispatcher,
        event_bus=mock_event_bus,
    )

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    with TestClient(app) as c:
        yield c


# === Upload Endpoint Tests ===


class TestUploadEndpoint:
    """Tests for POST /api/ingest/upload"""

    def test_upload_document(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test uploading a document file."""
        mock_intake_manager.receive_file.return_value = sample_job

        file_content = b"PDF content here"
        response = client.post(
            "/api/ingest/upload",
            files={"file": ("test.pdf", BytesIO(file_content), "application/pdf")},
            data={"priority": "user"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["filename"] == "test.pdf"
        assert data["category"] == "document"
        assert data["route"] == ["extract", "parse"]

    def test_upload_image_with_quality(self, client, mock_intake_manager, mock_job_dispatcher, sample_image_job):
        """Test uploading an image file returns quality info."""
        mock_intake_manager.receive_file.return_value = sample_image_job

        file_content = b"PNG content here"
        response = client.post(
            "/api/ingest/upload",
            files={"file": ("scan.png", BytesIO(file_content), "image/png")},
            data={"priority": "user"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-456"
        assert data["category"] == "image"
        assert data["quality"] is not None
        assert data["quality"]["classification"] == "clean"
        assert data["quality"]["dpi"] == 300

    def test_upload_default_priority(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test upload without priority defaults to user."""
        mock_intake_manager.receive_file.return_value = sample_job

        response = client.post(
            "/api/ingest/upload",
            files={"file": ("test.pdf", BytesIO(b"content"), "application/pdf")},
        )

        assert response.status_code == 200
        # Verify receive_file was called with USER priority
        mock_intake_manager.receive_file.assert_called_once()

    def test_upload_invalid_priority_defaults(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test upload with invalid priority defaults to USER."""
        mock_intake_manager.receive_file.return_value = sample_job

        response = client.post(
            "/api/ingest/upload",
            files={"file": ("test.pdf", BytesIO(b"content"), "application/pdf")},
            data={"priority": "invalid_priority"},
        )

        assert response.status_code == 200


# === Batch Upload Endpoint Tests ===


class TestBatchUploadEndpoint:
    """Tests for POST /api/ingest/upload/batch"""

    def test_upload_batch(self, client, mock_intake_manager, mock_job_dispatcher, sample_batch, sample_job):
        """Test uploading multiple files as a batch."""
        sample_batch.jobs = [sample_job]
        mock_intake_manager.receive_batch.return_value = sample_batch

        files = [
            ("files", ("file1.pdf", BytesIO(b"content1"), "application/pdf")),
            ("files", ("file2.pdf", BytesIO(b"content2"), "application/pdf")),
        ]
        response = client.post(
            "/api/ingest/upload/batch",
            files=files,
            data={"priority": "batch"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "batch-789"
        assert data["total_files"] == 1
        assert len(data["jobs"]) == 1

    def test_upload_batch_with_failures(self, client, mock_intake_manager, mock_job_dispatcher, sample_batch):
        """Test batch upload with some failures."""
        sample_batch.failed = 2
        mock_intake_manager.receive_batch.return_value = sample_batch

        files = [
            ("files", ("file1.pdf", BytesIO(b"content"), "application/pdf")),
        ]
        response = client.post(
            "/api/ingest/upload/batch",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["failed"] == 2


# === Ingest Path Endpoint Tests ===


class TestIngestPathEndpoint:
    """Tests for POST /api/ingest/ingest-path"""

    def test_ingest_path(self, client, mock_intake_manager, mock_job_dispatcher, sample_batch, sample_job):
        """Test ingesting from a filesystem path."""
        sample_batch.jobs = [sample_job]
        mock_intake_manager.receive_path.return_value = sample_batch

        with patch("arkham_shard_ingest.api.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            response = client.post(
                "/api/ingest/ingest-path",
                json={
                    "path": "/data/documents",
                    "recursive": True,
                    "priority": "batch",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "batch-789"

    def test_ingest_path_not_found(self, client, mock_intake_manager):
        """Test ingesting from a non-existent path."""
        with patch("arkham_shard_ingest.api.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            response = client.post(
                "/api/ingest/ingest-path",
                json={"path": "/nonexistent/path"},
            )

        assert response.status_code == 404


# === Job Status Endpoint Tests ===


class TestJobStatusEndpoint:
    """Tests for GET /api/ingest/job/{job_id}"""

    def test_get_job_status(self, client, mock_intake_manager, sample_job):
        """Test getting job status."""
        mock_intake_manager.get_job.return_value = sample_job

        response = client.get("/api/ingest/job/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["filename"] == "test.pdf"
        assert data["status"] == "queued"
        assert data["current_worker"] == "extract"
        assert data["route"] == ["extract", "parse"]

    def test_get_job_status_with_quality(self, client, mock_intake_manager, sample_image_job):
        """Test getting job status includes quality for images."""
        mock_intake_manager.get_job.return_value = sample_image_job

        response = client.get("/api/ingest/job/job-456")

        assert response.status_code == 200
        data = response.json()
        assert data["quality"] is not None
        assert data["quality"]["classification"] == "clean"

    def test_get_job_status_not_found(self, client, mock_intake_manager):
        """Test getting status of non-existent job."""
        mock_intake_manager.get_job.return_value = None

        response = client.get("/api/ingest/job/nonexistent")

        assert response.status_code == 404


# === Batch Status Endpoint Tests ===


class TestBatchStatusEndpoint:
    """Tests for GET /api/ingest/batch/{batch_id}"""

    def test_get_batch_status(self, client, mock_intake_manager, sample_batch, sample_job):
        """Test getting batch status."""
        sample_batch.jobs = [sample_job]
        sample_batch.completed = 0
        sample_batch.failed = 0
        mock_intake_manager.get_batch.return_value = sample_batch

        response = client.get("/api/ingest/batch/batch-789")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "batch-789"
        assert data["total_files"] == 1
        assert data["pending"] == 1
        assert len(data["jobs"]) == 1

    def test_get_batch_status_not_found(self, client, mock_intake_manager):
        """Test getting status of non-existent batch."""
        mock_intake_manager.get_batch.return_value = None

        response = client.get("/api/ingest/batch/nonexistent")

        assert response.status_code == 404


# === Retry Endpoint Tests ===


class TestRetryEndpoint:
    """Tests for POST /api/ingest/job/{job_id}/retry"""

    def test_retry_failed_job(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test retrying a failed job."""
        sample_job.status = JobStatus.FAILED
        mock_intake_manager.get_job.return_value = sample_job
        mock_job_dispatcher.retry.return_value = True

        response = client.post("/api/ingest/job/job-123/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "retrying"
        assert data["job_id"] == "job-123"

    def test_retry_dead_job(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test retrying a dead job."""
        sample_job.status = JobStatus.DEAD
        mock_intake_manager.get_job.return_value = sample_job
        mock_job_dispatcher.retry.return_value = True

        response = client.post("/api/ingest/job/job-123/retry")

        assert response.status_code == 200

    def test_retry_non_failed_job(self, client, mock_intake_manager, sample_job):
        """Test retrying a job that isn't failed."""
        sample_job.status = JobStatus.PROCESSING
        mock_intake_manager.get_job.return_value = sample_job

        response = client.post("/api/ingest/job/job-123/retry")

        assert response.status_code == 400
        assert "not in failed state" in response.json()["detail"]

    def test_retry_max_retries_exceeded(self, client, mock_intake_manager, mock_job_dispatcher, sample_job):
        """Test retrying when max retries exceeded."""
        sample_job.status = JobStatus.FAILED
        mock_intake_manager.get_job.return_value = sample_job
        mock_job_dispatcher.retry.return_value = False

        response = client.post("/api/ingest/job/job-123/retry")

        assert response.status_code == 400
        assert "Max retries exceeded" in response.json()["detail"]

    def test_retry_job_not_found(self, client, mock_intake_manager):
        """Test retrying non-existent job."""
        mock_intake_manager.get_job.return_value = None

        response = client.post("/api/ingest/job/nonexistent/retry")

        assert response.status_code == 404


# === Queue Stats Endpoint Tests ===


class TestQueueStatsEndpoint:
    """Tests for GET /api/ingest/queue"""

    def test_get_queue_stats_empty(self, client, mock_intake_manager):
        """Test getting queue stats when empty."""
        mock_intake_manager._jobs = {}

        response = client.get("/api/ingest/queue")

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 0
        assert data["processing"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0

    def test_get_queue_stats_with_jobs(self, client, mock_intake_manager, sample_file_info):
        """Test getting queue stats with various jobs."""
        jobs = {
            "job-1": IngestJob(id="job-1", file_info=sample_file_info, priority=JobPriority.USER, status=JobStatus.PENDING),
            "job-2": IngestJob(id="job-2", file_info=sample_file_info, priority=JobPriority.BATCH, status=JobStatus.PROCESSING),
            "job-3": IngestJob(id="job-3", file_info=sample_file_info, priority=JobPriority.USER, status=JobStatus.COMPLETED),
            "job-4": IngestJob(id="job-4", file_info=sample_file_info, priority=JobPriority.REPROCESS, status=JobStatus.FAILED),
        }
        mock_intake_manager._jobs = jobs

        response = client.get("/api/ingest/queue")

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 1
        assert data["processing"] == 1
        assert data["completed"] == 1
        assert data["failed"] == 1
        assert data["by_priority"]["user"] == 2
        assert data["by_priority"]["batch"] == 1
        assert data["by_priority"]["reprocess"] == 1


# === Pending Jobs Endpoint Tests ===


class TestPendingJobsEndpoint:
    """Tests for GET /api/ingest/pending"""

    def test_get_pending_jobs_empty(self, client, mock_intake_manager):
        """Test getting pending jobs when none exist."""
        mock_intake_manager.get_pending_jobs.return_value = []

        response = client.get("/api/ingest/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["jobs"] == []

    def test_get_pending_jobs_with_jobs(self, client, mock_intake_manager, sample_job):
        """Test getting pending jobs with results."""
        mock_intake_manager.get_pending_jobs.return_value = [sample_job]

        response = client.get("/api/ingest/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["jobs"][0]["job_id"] == "job-123"
        assert data["jobs"][0]["filename"] == "test.pdf"
        assert data["jobs"][0]["category"] == "document"

    def test_get_pending_jobs_with_limit(self, client, mock_intake_manager):
        """Test getting pending jobs with limit parameter."""
        mock_intake_manager.get_pending_jobs.return_value = []

        response = client.get("/api/ingest/pending?limit=10")

        assert response.status_code == 200
        mock_intake_manager.get_pending_jobs.assert_called_with(limit=10)


# === Service Unavailable Tests ===


class TestServiceUnavailable:
    """Tests for service unavailable scenarios."""

    def test_upload_service_unavailable(self, client):
        """Test upload when service not initialized."""
        # Reset API state
        init_api(None, None, None)

        response = client.post(
            "/api/ingest/upload",
            files={"file": ("test.pdf", BytesIO(b"content"), "application/pdf")},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_batch_service_unavailable(self, client):
        """Test batch upload when service not initialized."""
        init_api(None, None, None)

        response = client.post(
            "/api/ingest/upload/batch",
            files=[("files", ("test.pdf", BytesIO(b"content"), "application/pdf"))],
        )

        assert response.status_code == 503

    def test_job_status_service_unavailable(self, client):
        """Test job status when service not initialized."""
        init_api(None, None, None)

        response = client.get("/api/ingest/job/job-123")

        assert response.status_code == 503
