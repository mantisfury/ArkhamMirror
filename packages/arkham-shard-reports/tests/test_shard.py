"""
Reports Shard - Shard Tests

Tests for ReportsShard class and methods.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from arkham_shard_reports.shard import ReportsShard
from arkham_shard_reports.models import (
    Report,
    ReportFormat,
    ReportStatus,
    ReportTemplate,
    ReportType,
    ReportSchedule,
    ReportFilter,
)


@pytest.fixture
def mock_frame():
    """Create a mock ArkhamFrame."""
    frame = MagicMock()
    frame.database = MagicMock()
    frame.database.execute = AsyncMock()
    frame.database.fetch_one = AsyncMock(return_value=None)
    frame.database.fetch_all = AsyncMock(return_value=[])
    frame.events = MagicMock()
    frame.events.emit = AsyncMock()
    frame.llm = None
    frame.storage = None
    frame.workers = None
    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create and initialize a ReportsShard."""
    shard = ReportsShard()
    await shard.initialize(mock_frame)
    return shard


class TestShardMetadata:
    """Tests for shard metadata."""

    def test_shard_name(self):
        """Verify shard name."""
        shard = ReportsShard()
        assert shard.name == "reports"

    def test_shard_version(self):
        """Verify shard version is semver."""
        shard = ReportsShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard has description."""
        shard = ReportsShard()
        assert "report" in shard.description.lower()


class TestInitialization:
    """Tests for shard initialization."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_frame):
        """Test shard initialization."""
        shard = ReportsShard()
        await shard.initialize(mock_frame)

        assert shard._initialized is True
        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events

    @pytest.mark.asyncio
    async def test_shutdown(self, shard):
        """Test shard shutdown."""
        await shard.shutdown()
        assert shard._initialized is False

    @pytest.mark.asyncio
    async def test_get_routes(self, shard):
        """Test get_routes returns a router."""
        router = shard.get_routes()
        assert router is not None
        assert hasattr(router, "prefix")


class TestReportGeneration:
    """Tests for report generation."""

    @pytest.mark.asyncio
    async def test_generate_report(self, shard):
        """Test generating a report."""
        report = await shard.generate_report(
            report_type=ReportType.SUMMARY,
            title="Test Summary Report",
            parameters={"date_range": "last_7_days"},
            output_format=ReportFormat.HTML,
        )

        assert report is not None
        assert report.report_type == ReportType.SUMMARY
        assert report.title == "Test Summary Report"
        assert report.status == ReportStatus.PENDING
        assert report.parameters["date_range"] == "last_7_days"

    @pytest.mark.asyncio
    async def test_get_report(self, shard):
        """Test getting a report by ID."""
        # Mock database response
        shard._db.fetch_one = AsyncMock(return_value={
            "id": "rep-1",
            "report_type": "summary",
            "title": "Test Report",
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "parameters": "{}",
            "output_format": "html",
            "file_path": "/reports/rep-1.html",
            "file_size": 1024,
            "error": None,
            "metadata": "{}",
        })

        report = await shard.get_report("rep-1")
        assert report is not None
        assert report.id == "rep-1"
        assert report.title == "Test Report"

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, shard):
        """Test getting a non-existent report."""
        shard._db.fetch_one = AsyncMock(return_value=None)
        report = await shard.get_report("nonexistent")
        assert report is None

    @pytest.mark.asyncio
    async def test_list_reports(self, shard):
        """Test listing reports."""
        # Mock database response
        shard._db.fetch_all = AsyncMock(return_value=[
            {
                "id": "rep-1",
                "report_type": "summary",
                "title": "Report 1",
                "status": "completed",
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "parameters": "{}",
                "output_format": "html",
                "file_path": None,
                "file_size": None,
                "error": None,
                "metadata": "{}",
            },
            {
                "id": "rep-2",
                "report_type": "timeline",
                "title": "Report 2",
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "parameters": "{}",
                "output_format": "pdf",
                "file_path": None,
                "file_size": None,
                "error": None,
                "metadata": "{}",
            },
        ])

        reports = await shard.list_reports(limit=10, offset=0)
        assert len(reports) == 2
        assert reports[0].id == "rep-1"
        assert reports[1].id == "rep-2"

    @pytest.mark.asyncio
    async def test_list_reports_with_filter(self, shard):
        """Test listing reports with filter."""
        shard._db.fetch_all = AsyncMock(return_value=[])

        filter = ReportFilter(
            status=ReportStatus.COMPLETED,
            report_type=ReportType.SUMMARY,
        )
        reports = await shard.list_reports(filter=filter, limit=10, offset=0)
        assert len(reports) == 0

    @pytest.mark.asyncio
    async def test_delete_report(self, shard):
        """Test deleting a report."""
        # Mock get_report to return a report
        shard._db.fetch_one = AsyncMock(return_value={
            "id": "rep-1",
            "report_type": "summary",
            "title": "Test Report",
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "parameters": "{}",
            "output_format": "html",
            "file_path": "/reports/rep-1.html",
            "file_size": 1024,
            "error": None,
            "metadata": "{}",
        })

        success = await shard.delete_report("rep-1")
        assert success is True

    @pytest.mark.asyncio
    async def test_get_count(self, shard):
        """Test getting report count."""
        shard._db.fetch_one = AsyncMock(return_value={"count": 42})
        count = await shard.get_count()
        assert count == 42

    @pytest.mark.asyncio
    async def test_get_count_with_status(self, shard):
        """Test getting report count filtered by status."""
        shard._db.fetch_one = AsyncMock(return_value={"count": 15})
        count = await shard.get_count(status="pending")
        assert count == 15


class TestTemplates:
    """Tests for template management."""

    @pytest.mark.asyncio
    async def test_create_template(self, shard):
        """Test creating a template."""
        template = await shard.create_template(
            name="Weekly Summary Template",
            report_type=ReportType.SUMMARY,
            description="Generate weekly summary reports",
            parameters_schema={"type": "object"},
            default_format=ReportFormat.HTML,
        )

        assert template is not None
        assert template.name == "Weekly Summary Template"
        assert template.report_type == ReportType.SUMMARY

    @pytest.mark.asyncio
    async def test_get_template(self, shard):
        """Test getting a template by ID."""
        shard._db.fetch_one = AsyncMock(return_value={
            "id": "tmpl-1",
            "name": "Test Template",
            "report_type": "summary",
            "description": "Test description",
            "parameters_schema": "{}",
            "default_format": "html",
            "template_content": "# {{title}}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": "{}",
        })

        template = await shard.get_template("tmpl-1")
        assert template is not None
        assert template.id == "tmpl-1"
        assert template.name == "Test Template"

    @pytest.mark.asyncio
    async def test_list_templates(self, shard):
        """Test listing templates."""
        shard._db.fetch_all = AsyncMock(return_value=[
            {
                "id": "tmpl-1",
                "name": "Template 1",
                "report_type": "summary",
                "description": "Desc 1",
                "parameters_schema": "{}",
                "default_format": "html",
                "template_content": "",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "metadata": "{}",
            },
        ])

        templates = await shard.list_templates(limit=10, offset=0)
        assert len(templates) == 1
        assert templates[0].id == "tmpl-1"


class TestSchedules:
    """Tests for schedule management."""

    @pytest.mark.asyncio
    async def test_create_schedule(self, shard):
        """Test creating a schedule."""
        schedule = await shard.create_schedule(
            template_id="tmpl-1",
            cron_expression="0 9 * * 1",
            parameters={"include_charts": True},
            output_format=ReportFormat.PDF,
            retention_days=30,
        )

        assert schedule is not None
        assert schedule.template_id == "tmpl-1"
        assert schedule.cron_expression == "0 9 * * 1"
        assert schedule.enabled is True

    @pytest.mark.asyncio
    async def test_list_schedules(self, shard):
        """Test listing schedules."""
        shard._db.fetch_all = AsyncMock(return_value=[
            {
                "id": "sched-1",
                "template_id": "tmpl-1",
                "cron_expression": "0 9 * * 1",
                "enabled": 1,
                "last_run": None,
                "next_run": None,
                "parameters": "{}",
                "output_format": "html",
                "retention_days": 30,
                "email_recipients": "[]",
                "metadata": "{}",
            },
        ])

        schedules = await shard.list_schedules(limit=10, offset=0)
        assert len(schedules) == 1
        assert schedules[0].id == "sched-1"

    @pytest.mark.asyncio
    async def test_delete_schedule(self, shard):
        """Test deleting a schedule."""
        success = await shard.delete_schedule("sched-1")
        assert success is True


class TestStatistics:
    """Tests for statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, shard):
        """Test getting statistics."""
        shard._db.fetch_one = AsyncMock(side_effect=[
            {"count": 100},  # total reports
            {"count": 10},   # templates
            {"count": 5},    # schedules
            {"count": 3},    # active schedules
            {"total": 524288},  # file size
        ])
        shard._db.fetch_all = AsyncMock(side_effect=[
            [{"status": "completed", "count": 80}, {"status": "pending", "count": 20}],
            [{"report_type": "summary", "count": 60}, {"report_type": "timeline", "count": 40}],
            [{"output_format": "html", "count": 70}, {"output_format": "pdf", "count": 30}],
        ])

        stats = await shard.get_statistics()
        assert stats.total_reports == 100
        assert stats.total_templates == 10
        assert stats.total_schedules == 5
