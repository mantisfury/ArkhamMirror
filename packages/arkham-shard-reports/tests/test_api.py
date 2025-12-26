"""
Reports Shard - API Tests

Tests for FastAPI routes and endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from arkham_shard_reports.api import router
from arkham_shard_reports.models import (
    Report,
    ReportFormat,
    ReportStatus,
    ReportTemplate,
    ReportType,
    ReportSchedule,
    ReportStatistics,
)


@pytest.fixture
def mock_shard():
    """Create a mock ReportsShard."""
    shard = MagicMock()
    shard.version = "0.1.0"
    shard._db = MagicMock()
    shard._events = MagicMock()
    shard._llm = None
    shard._storage = None
    shard._workers = None

    # Mock async methods
    shard.generate_report = AsyncMock()
    shard.get_report = AsyncMock()
    shard.list_reports = AsyncMock()
    shard.delete_report = AsyncMock()
    shard.get_count = AsyncMock()
    shard.create_template = AsyncMock()
    shard.get_template = AsyncMock()
    shard.list_templates = AsyncMock()
    shard.create_schedule = AsyncMock()
    shard.list_schedules = AsyncMock()
    shard.delete_schedule = AsyncMock()
    shard.get_statistics = AsyncMock()

    return shard


@pytest.fixture
def client(mock_shard):
    """Create a test client with mocked shard."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    with patch("arkham_shard_reports.api._get_shard", return_value=mock_shard):
        yield TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/reports/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "services" in data


class TestCountEndpoints:
    """Tests for count endpoints."""

    def test_get_reports_count(self, client, mock_shard):
        """Test getting total report count."""
        mock_shard.get_count.return_value = 42
        response = client.get("/api/reports/count")
        assert response.status_code == 200
        assert response.json()["count"] == 42

    def test_get_pending_count(self, client, mock_shard):
        """Test getting pending report count (badge endpoint)."""
        mock_shard.get_count.return_value = 15
        response = client.get("/api/reports/pending/count")
        assert response.status_code == 200
        assert response.json()["count"] == 15


class TestReportsCRUD:
    """Tests for report CRUD endpoints."""

    def test_list_reports(self, client, mock_shard):
        """Test listing reports."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Test Report",
            status=ReportStatus.COMPLETED,
        )
        mock_shard.list_reports.return_value = [mock_report]
        mock_shard.get_count.return_value = 1

        response = client.get("/api/reports/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["reports"]) == 1
        assert data["reports"][0]["id"] == "rep-1"

    def test_create_report(self, client, mock_shard):
        """Test creating a report."""
        mock_report = Report(
            id="rep-new",
            report_type=ReportType.SUMMARY,
            title="New Report",
            status=ReportStatus.PENDING,
        )
        mock_shard.generate_report.return_value = mock_report

        response = client.post(
            "/api/reports/",
            json={
                "report_type": "summary",
                "title": "New Report",
                "output_format": "html",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "rep-new"
        assert data["title"] == "New Report"

    def test_get_report(self, client, mock_shard):
        """Test getting a specific report."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Test Report",
            status=ReportStatus.COMPLETED,
        )
        mock_shard.get_report.return_value = mock_report

        response = client.get("/api/reports/rep-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "rep-1"
        assert data["title"] == "Test Report"

    def test_get_report_not_found(self, client, mock_shard):
        """Test getting a non-existent report."""
        mock_shard.get_report.return_value = None

        response = client.get("/api/reports/nonexistent")
        assert response.status_code == 404

    def test_delete_report(self, client, mock_shard):
        """Test deleting a report."""
        mock_shard.delete_report.return_value = True

        response = client.delete("/api/reports/rep-1")
        assert response.status_code == 204

    def test_delete_report_not_found(self, client, mock_shard):
        """Test deleting a non-existent report."""
        mock_shard.delete_report.return_value = False

        response = client.delete("/api/reports/nonexistent")
        assert response.status_code == 404

    def test_download_report(self, client, mock_shard):
        """Test downloading a report."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Test Report",
            status=ReportStatus.COMPLETED,
            file_path="/reports/rep-1.html",
            file_size=1024,
        )
        mock_shard.get_report.return_value = mock_report

        response = client.get("/api/reports/rep-1/download")
        assert response.status_code == 200


class TestTemplates:
    """Tests for template endpoints."""

    def test_list_templates(self, client, mock_shard):
        """Test listing templates."""
        mock_template = ReportTemplate(
            id="tmpl-1",
            name="Summary Template",
            report_type=ReportType.SUMMARY,
            description="Weekly summary",
        )
        mock_shard.list_templates.return_value = [mock_template]

        response = client.get("/api/reports/templates")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "tmpl-1"

    def test_get_template(self, client, mock_shard):
        """Test getting a specific template."""
        mock_template = ReportTemplate(
            id="tmpl-1",
            name="Summary Template",
            report_type=ReportType.SUMMARY,
            description="Weekly summary",
        )
        mock_shard.get_template.return_value = mock_template

        response = client.get("/api/reports/templates/tmpl-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "tmpl-1"
        assert data["name"] == "Summary Template"

    def test_get_template_not_found(self, client, mock_shard):
        """Test getting a non-existent template."""
        mock_shard.get_template.return_value = None

        response = client.get("/api/reports/templates/nonexistent")
        assert response.status_code == 404

    def test_create_template(self, client, mock_shard):
        """Test creating a template."""
        mock_template = ReportTemplate(
            id="tmpl-new",
            name="New Template",
            report_type=ReportType.SUMMARY,
            description="New template",
        )
        mock_shard.create_template.return_value = mock_template

        response = client.post(
            "/api/reports/templates",
            json={
                "name": "New Template",
                "report_type": "summary",
                "description": "New template",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "tmpl-new"
        assert data["name"] == "New Template"


class TestSchedules:
    """Tests for schedule endpoints."""

    def test_list_schedules(self, client, mock_shard):
        """Test listing schedules."""
        mock_schedule = ReportSchedule(
            id="sched-1",
            template_id="tmpl-1",
            cron_expression="0 9 * * 1",
        )
        mock_shard.list_schedules.return_value = [mock_schedule]

        response = client.get("/api/reports/schedules")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "sched-1"

    def test_create_schedule(self, client, mock_shard):
        """Test creating a schedule."""
        mock_template = ReportTemplate(
            id="tmpl-1",
            name="Test Template",
            report_type=ReportType.SUMMARY,
            description="Test",
        )
        mock_schedule = ReportSchedule(
            id="sched-new",
            template_id="tmpl-1",
            cron_expression="0 9 * * 1",
        )
        mock_shard.get_template.return_value = mock_template
        mock_shard.create_schedule.return_value = mock_schedule

        response = client.post(
            "/api/reports/schedules",
            json={
                "template_id": "tmpl-1",
                "cron_expression": "0 9 * * 1",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "sched-new"

    def test_create_schedule_template_not_found(self, client, mock_shard):
        """Test creating a schedule with non-existent template."""
        mock_shard.get_template.return_value = None

        response = client.post(
            "/api/reports/schedules",
            json={
                "template_id": "nonexistent",
                "cron_expression": "0 9 * * 1",
            },
        )
        assert response.status_code == 404

    def test_delete_schedule(self, client, mock_shard):
        """Test deleting a schedule."""
        mock_shard.delete_schedule.return_value = True

        response = client.delete("/api/reports/schedules/sched-1")
        assert response.status_code == 204

    def test_delete_schedule_not_found(self, client, mock_shard):
        """Test deleting a non-existent schedule."""
        mock_shard.delete_schedule.return_value = False

        response = client.delete("/api/reports/schedules/nonexistent")
        assert response.status_code == 404


class TestPreview:
    """Tests for preview endpoint."""

    def test_preview_report(self, client, mock_shard):
        """Test previewing a report."""
        response = client.post(
            "/api/reports/preview",
            json={
                "report_type": "summary",
                "title": "Preview Report",
                "output_format": "html",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "preview_content" in data
        assert data["estimated_size"] > 0


class TestStatistics:
    """Tests for statistics endpoint."""

    def test_get_statistics(self, client, mock_shard):
        """Test getting statistics."""
        mock_stats = ReportStatistics(
            total_reports=100,
            by_status={"completed": 80, "pending": 20},
            by_type={"summary": 60, "timeline": 40},
            by_format={"html": 70, "pdf": 30},
            total_templates=10,
            total_schedules=5,
            active_schedules=3,
        )
        mock_shard.get_statistics.return_value = mock_stats

        response = client.get("/api/reports/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_reports"] == 100
        assert data["total_templates"] == 10


class TestFilteredLists:
    """Tests for filtered list endpoints."""

    def test_list_pending_reports(self, client, mock_shard):
        """Test listing pending reports."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Pending Report",
            status=ReportStatus.PENDING,
        )
        mock_shard.list_reports.return_value = [mock_report]
        mock_shard.get_count.return_value = 1

        response = client.get("/api/reports/pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["status"] == "pending"

    def test_list_completed_reports(self, client, mock_shard):
        """Test listing completed reports."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Completed Report",
            status=ReportStatus.COMPLETED,
        )
        mock_shard.list_reports.return_value = [mock_report]
        mock_shard.get_count.return_value = 1

        response = client.get("/api/reports/completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["reports"]) == 1

    def test_list_failed_reports(self, client, mock_shard):
        """Test listing failed reports."""
        mock_report = Report(
            id="rep-1",
            report_type=ReportType.SUMMARY,
            title="Failed Report",
            status=ReportStatus.FAILED,
            error="Generation error",
        )
        mock_shard.list_reports.return_value = [mock_report]
        mock_shard.get_count.return_value = 1

        response = client.get("/api/reports/failed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["error"] is not None
