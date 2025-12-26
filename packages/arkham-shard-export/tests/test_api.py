"""
Export Shard - API Tests

Tests for FastAPI endpoints using TestClient.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_export.api import router
from arkham_shard_export.models import (
    ExportJob,
    ExportFormat,
    ExportStatus,
    ExportTarget,
    ExportOptions,
    ExportStatistics,
    FormatInfo,
    TargetInfo,
)


# === Test Setup ===


@pytest.fixture
def mock_shard():
    """Create a mock ExportShard."""
    shard = MagicMock()
    shard.name = "export"
    shard._events = AsyncMock()
    shard.get_count = AsyncMock(return_value=5)
    shard.list_jobs = AsyncMock(return_value=[])
    shard.create_export_job = AsyncMock()
    shard.get_job_status = AsyncMock(return_value=None)
    shard.cancel_job = AsyncMock(return_value=None)
    shard.get_download_url = AsyncMock(return_value=None)
    shard.get_statistics = AsyncMock()
    shard.get_supported_formats = MagicMock(return_value=[])
    shard.get_export_targets = MagicMock(return_value=[])
    return shard


@pytest.fixture
def mock_frame(mock_shard):
    """Create a mock Frame that returns the mock shard."""
    frame = MagicMock()
    frame.get_shard = MagicMock(return_value=mock_shard)
    return frame


@pytest.fixture
def app(mock_frame):
    """Create test FastAPI app with mocked dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app, mock_frame):
    """Create test client with patched get_frame."""
    with patch("arkham_shard_export.api.get_frame", return_value=mock_frame):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_job():
    """Create a sample export job for testing."""
    return ExportJob(
        id="job-1",
        format=ExportFormat.JSON,
        target=ExportTarget.DOCUMENTS,
        status=ExportStatus.COMPLETED,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        file_path="/tmp/export.json",
        file_size=2048,
        download_url="/api/export/jobs/job-1/download",
        expires_at=datetime.utcnow() + timedelta(hours=24),
        record_count=100,
        processing_time_ms=1500.0,
        created_by="test-user",
        metadata={"version": "1.0"},
    )


# === Count Endpoint Tests ===


class TestCountEndpoint:
    """Tests for GET /api/export/count"""

    def test_get_count(self, client, mock_shard):
        """Test getting export job count."""
        mock_shard.get_count.return_value = 5

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/count")

        assert response.status_code == 200
        assert response.json()["count"] == 5

    def test_get_count_with_status(self, client, mock_shard):
        """Test getting count with status filter."""
        mock_shard.get_count.return_value = 3

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/count?status=pending")

        assert response.status_code == 200


# === List Jobs Endpoint Tests ===


class TestListJobsEndpoint:
    """Tests for GET /api/export/jobs"""

    def test_list_jobs_empty(self, client, mock_shard):
        """Test listing jobs when empty."""
        mock_shard.list_jobs.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_with_results(self, client, mock_shard, sample_job):
        """Test listing jobs with results."""
        mock_shard.list_jobs.return_value = [sample_job]
        mock_shard.get_count.return_value = 1

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "job-1"

    def test_list_jobs_with_filters(self, client, mock_shard):
        """Test listing jobs with query filters."""
        mock_shard.list_jobs.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get(
                "/api/export/jobs?status=completed&format=json&target=documents"
            )

        assert response.status_code == 200
        mock_shard.list_jobs.assert_called_once()

    def test_list_jobs_pagination(self, client, mock_shard):
        """Test listing jobs with pagination."""
        mock_shard.list_jobs.return_value = []
        mock_shard.get_count.return_value = 100

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs?limit=20&offset=40")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 20
        assert data["offset"] == 40


# === Create Job Endpoint Tests ===


class TestCreateJobEndpoint:
    """Tests for POST /api/export/jobs"""

    def test_create_job_minimal(self, client, mock_shard, sample_job):
        """Test creating a job with minimal fields."""
        mock_shard.create_export_job.return_value = sample_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/export/jobs",
                json={
                    "format": "json",
                    "target": "documents",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["format"] == "json"
        assert data["target"] == "documents"

    def test_create_job_with_options(self, client, mock_shard, sample_job):
        """Test creating a job with export options."""
        mock_shard.create_export_job.return_value = sample_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/export/jobs",
                json={
                    "format": "csv",
                    "target": "entities",
                    "options": {
                        "include_metadata": False,
                        "flatten": True,
                        "max_records": 100,
                    },
                },
            )

        assert response.status_code == 201

    def test_create_job_missing_format(self, client, mock_shard):
        """Test creating a job without format fails."""
        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/export/jobs",
                json={"target": "documents"},
            )

        assert response.status_code == 422  # Validation error


# === Get Job Endpoint Tests ===


class TestGetJobEndpoint:
    """Tests for GET /api/export/jobs/{job_id}"""

    def test_get_job_found(self, client, mock_shard, sample_job):
        """Test getting an existing job."""
        mock_shard.get_job_status.return_value = sample_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs/job-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "job-1"
        assert data["status"] == "completed"

    def test_get_job_not_found(self, client, mock_shard):
        """Test getting a non-existent job."""
        mock_shard.get_job_status.return_value = None

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs/nonexistent")

        assert response.status_code == 404


# === Cancel Job Endpoint Tests ===


class TestCancelJobEndpoint:
    """Tests for DELETE /api/export/jobs/{job_id}"""

    def test_cancel_job(self, client, mock_shard, sample_job):
        """Test cancelling a job."""
        cancelled_job = ExportJob(
            id=sample_job.id,
            format=sample_job.format,
            target=sample_job.target,
            status=ExportStatus.CANCELLED,
            created_at=sample_job.created_at,
        )
        mock_shard.cancel_job.return_value = cancelled_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/export/jobs/job-1")

        assert response.status_code == 204

    def test_cancel_job_not_found(self, client, mock_shard):
        """Test cancelling non-existent job."""
        mock_shard.cancel_job.return_value = None

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/export/jobs/nonexistent")

        assert response.status_code == 404


# === Download Job Endpoint Tests ===


class TestDownloadJobEndpoint:
    """Tests for GET /api/export/jobs/{job_id}/download"""

    def test_download_job_success(self, client, mock_shard, sample_job):
        """Test downloading a completed export."""
        import tempfile
        import os

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write('{"test": "data"}')
            temp_path = f.name

        try:
            sample_job.file_path = temp_path
            sample_job.expires_at = datetime.utcnow() + timedelta(hours=1)
            mock_shard.get_job_status.return_value = sample_job

            with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
                response = client.get("/api/export/jobs/job-1/download")

            assert response.status_code == 200
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_download_job_not_found(self, client, mock_shard):
        """Test downloading non-existent job."""
        mock_shard.get_job_status.return_value = None

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs/nonexistent/download")

        assert response.status_code == 404

    def test_download_job_not_completed(self, client, mock_shard, sample_job):
        """Test downloading a pending job."""
        sample_job.status = ExportStatus.PENDING
        mock_shard.get_job_status.return_value = sample_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs/job-1/download")

        assert response.status_code == 400

    def test_download_job_expired(self, client, mock_shard, sample_job):
        """Test downloading an expired export."""
        sample_job.expires_at = datetime.utcnow() - timedelta(hours=1)
        mock_shard.get_job_status.return_value = sample_job

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/jobs/job-1/download")

        assert response.status_code == 410


# === Formats Endpoint Tests ===


class TestFormatsEndpoint:
    """Tests for GET /api/export/formats"""

    def test_get_formats(self, client, mock_shard):
        """Test getting supported formats."""
        mock_shard.get_supported_formats.return_value = [
            FormatInfo(
                format=ExportFormat.JSON,
                name="JSON",
                description="JSON format",
                file_extension=".json",
                mime_type="application/json",
                supports_metadata=True,
                supports_flatten=False,
                placeholder=False,
            )
        ]

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/formats")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["format"] == "json"
        assert data[0]["name"] == "JSON"


# === Targets Endpoint Tests ===


class TestTargetsEndpoint:
    """Tests for GET /api/export/targets"""

    def test_get_targets(self, client, mock_shard):
        """Test getting export targets."""
        mock_shard.get_export_targets.return_value = [
            TargetInfo(
                target=ExportTarget.DOCUMENTS,
                name="Documents",
                description="Document records",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV],
                estimated_record_count=100,
                supports_filters=True,
            )
        ]

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/targets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target"] == "documents"
        assert data[0]["name"] == "Documents"
        assert len(data[0]["available_formats"]) == 2


# === Preview Endpoint Tests ===


class TestPreviewEndpoint:
    """Tests for POST /api/export/preview"""

    def test_preview_export(self, client, mock_shard):
        """Test previewing an export."""
        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/export/preview",
                json={
                    "format": "json",
                    "target": "documents",
                    "max_preview_records": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert data["target"] == "documents"


# === Statistics Endpoint Tests ===


class TestStatisticsEndpoint:
    """Tests for GET /api/export/stats"""

    def test_get_statistics(self, client, mock_shard):
        """Test getting export statistics."""
        mock_shard.get_statistics.return_value = ExportStatistics(
            total_jobs=100,
            by_status={"completed": 80, "pending": 15, "failed": 5},
            by_format={"json": 60, "csv": 40},
            by_target={"documents": 70, "entities": 30},
            jobs_pending=15,
            jobs_processing=0,
            jobs_completed=80,
            jobs_failed=5,
            total_records_exported=10000,
            total_file_size_bytes=1024000,
            avg_processing_time_ms=2500.0,
        )

        with patch("arkham_shard_export.api._get_shard", return_value=mock_shard):
            response = client.get("/api/export/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 100
        assert data["jobs_completed"] == 80
        assert data["total_records_exported"] == 10000
