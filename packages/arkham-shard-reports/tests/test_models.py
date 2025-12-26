"""
Reports Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime

from arkham_shard_reports.models import (
    # Enums
    ReportType,
    ReportStatus,
    ReportFormat,
    # Dataclasses
    Report,
    ReportTemplate,
    ReportSchedule,
    GeneratedSection,
    ReportGenerationResult,
    ReportStatistics,
    ReportFilter,
)


class TestReportTypeEnum:
    """Tests for ReportType enum."""

    def test_all_values_exist(self):
        """Verify all expected type values exist."""
        assert ReportType.SUMMARY.value == "summary"
        assert ReportType.ENTITY_PROFILE.value == "entity_profile"
        assert ReportType.TIMELINE.value == "timeline"
        assert ReportType.CONTRADICTION.value == "contradiction"
        assert ReportType.ACH_ANALYSIS.value == "ach_analysis"
        assert ReportType.CUSTOM.value == "custom"

    def test_string_inheritance(self):
        """Verify enum values can be used as strings."""
        assert ReportType.SUMMARY == "summary"
        assert str(ReportType.SUMMARY) == "summary"

    def test_enum_count(self):
        """Verify total number of types."""
        assert len(ReportType) == 6


class TestReportStatusEnum:
    """Tests for ReportStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert ReportStatus.PENDING.value == "pending"
        assert ReportStatus.GENERATING.value == "generating"
        assert ReportStatus.COMPLETED.value == "completed"
        assert ReportStatus.FAILED.value == "failed"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(ReportStatus) == 4


class TestReportFormatEnum:
    """Tests for ReportFormat enum."""

    def test_all_values_exist(self):
        """Verify all expected format values exist."""
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.MARKDOWN.value == "markdown"
        assert ReportFormat.JSON.value == "json"

    def test_enum_count(self):
        """Verify total number of formats."""
        assert len(ReportFormat) == 4


class TestReportDataclass:
    """Tests for Report dataclass."""

    def test_minimal_creation(self):
        """Test creating a report with minimal required fields."""
        report = Report(
            id="test-id",
            report_type=ReportType.SUMMARY,
            title="Test Report",
        )
        assert report.id == "test-id"
        assert report.report_type == ReportType.SUMMARY
        assert report.title == "Test Report"
        assert report.status == ReportStatus.PENDING
        assert report.output_format == ReportFormat.HTML

    def test_full_creation(self):
        """Test creating a report with all fields."""
        now = datetime.utcnow()
        report = Report(
            id="full-id",
            report_type=ReportType.ENTITY_PROFILE,
            title="Entity Profile Report",
            status=ReportStatus.COMPLETED,
            created_at=now,
            completed_at=now,
            parameters={"entity_id": "ent-123"},
            output_format=ReportFormat.PDF,
            file_path="/reports/entity_profile.pdf",
            file_size=102400,
            error=None,
            metadata={"generated_by": "system"},
        )
        assert report.id == "full-id"
        assert report.report_type == ReportType.ENTITY_PROFILE
        assert report.status == ReportStatus.COMPLETED
        assert report.file_path == "/reports/entity_profile.pdf"
        assert report.file_size == 102400

    def test_default_values(self):
        """Test that default values are set correctly."""
        report = Report(
            id="test",
            report_type=ReportType.SUMMARY,
            title="test report",
        )
        assert report.status == ReportStatus.PENDING
        assert report.parameters == {}
        assert report.output_format == ReportFormat.HTML
        assert report.metadata == {}
        assert report.completed_at is None
        assert report.error is None


class TestReportTemplateDataclass:
    """Tests for ReportTemplate dataclass."""

    def test_minimal_creation(self):
        """Test creating a template with minimal required fields."""
        template = ReportTemplate(
            id="tmpl-1",
            name="Summary Template",
            report_type=ReportType.SUMMARY,
            description="Weekly summary report",
        )
        assert template.id == "tmpl-1"
        assert template.name == "Summary Template"
        assert template.report_type == ReportType.SUMMARY
        assert template.default_format == ReportFormat.HTML

    def test_full_creation(self):
        """Test creating a template with all fields."""
        now = datetime.utcnow()
        template = ReportTemplate(
            id="tmpl-full",
            name="Custom Template",
            report_type=ReportType.CUSTOM,
            description="Custom report template",
            parameters_schema={"type": "object", "properties": {}},
            default_format=ReportFormat.MARKDOWN,
            template_content="# {{title}}\n\n{{content}}",
            created_at=now,
            updated_at=now,
            metadata={"author": "user-1"},
        )
        assert template.name == "Custom Template"
        assert template.default_format == ReportFormat.MARKDOWN
        assert "{{title}}" in template.template_content


class TestReportScheduleDataclass:
    """Tests for ReportSchedule dataclass."""

    def test_minimal_creation(self):
        """Test creating a schedule with minimal required fields."""
        schedule = ReportSchedule(
            id="sched-1",
            template_id="tmpl-1",
            cron_expression="0 9 * * 1",
        )
        assert schedule.id == "sched-1"
        assert schedule.template_id == "tmpl-1"
        assert schedule.cron_expression == "0 9 * * 1"
        assert schedule.enabled is True
        assert schedule.retention_days == 30

    def test_full_creation(self):
        """Test creating a schedule with all fields."""
        now = datetime.utcnow()
        schedule = ReportSchedule(
            id="sched-full",
            template_id="tmpl-1",
            cron_expression="0 0 * * *",
            enabled=False,
            last_run=now,
            next_run=now,
            parameters={"include_charts": True},
            output_format=ReportFormat.PDF,
            retention_days=90,
            email_recipients=["user@example.com"],
            metadata={"created_by": "admin"},
        )
        assert schedule.enabled is False
        assert schedule.retention_days == 90
        assert len(schedule.email_recipients) == 1


class TestGeneratedSectionDataclass:
    """Tests for GeneratedSection dataclass."""

    def test_minimal_creation(self):
        """Test creating a section with minimal fields."""
        section = GeneratedSection(title="Executive Summary")
        assert section.title == "Executive Summary"
        assert section.content == ""
        assert section.charts == []
        assert section.tables == []
        assert section.subsections == []

    def test_full_creation(self):
        """Test creating a section with all fields."""
        subsection = GeneratedSection(title="Subsection", content="Subsection content")
        section = GeneratedSection(
            title="Main Section",
            content="Main content",
            charts=[{"type": "bar", "data": [1, 2, 3]}],
            tables=[{"headers": ["A", "B"], "rows": [[1, 2]]}],
            subsections=[subsection],
            metadata={"importance": "high"},
        )
        assert section.title == "Main Section"
        assert len(section.charts) == 1
        assert len(section.tables) == 1
        assert len(section.subsections) == 1


class TestReportGenerationResultDataclass:
    """Tests for ReportGenerationResult dataclass."""

    def test_successful_result(self):
        """Test successful generation result."""
        result = ReportGenerationResult(
            report_id="rep-1",
            success=True,
            file_path="/reports/rep-1.html",
            file_size=51200,
            processing_time_ms=1500.0,
        )
        assert result.success is True
        assert result.file_path == "/reports/rep-1.html"
        assert result.errors == []

    def test_failed_result(self):
        """Test failed generation result."""
        result = ReportGenerationResult(
            report_id="rep-2",
            success=False,
            errors=["Database unavailable", "Timeout"],
            warnings=["Large dataset"],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestReportStatisticsDataclass:
    """Tests for ReportStatistics dataclass."""

    def test_default_values(self):
        """Test default values for statistics."""
        stats = ReportStatistics()
        assert stats.total_reports == 0
        assert stats.by_status == {}
        assert stats.by_type == {}
        assert stats.total_templates == 0
        assert stats.total_file_size_bytes == 0

    def test_populated_statistics(self):
        """Test statistics with data."""
        stats = ReportStatistics(
            total_reports=150,
            by_status={"completed": 120, "pending": 20, "failed": 10},
            by_type={"summary": 80, "entity_profile": 50, "timeline": 20},
            by_format={"html": 100, "pdf": 40, "markdown": 10},
            total_templates=15,
            total_schedules=8,
            active_schedules=6,
            total_file_size_bytes=52428800,
            avg_generation_time_ms=2500.0,
            reports_last_24h=5,
            reports_last_7d=25,
            reports_last_30d=100,
        )
        assert stats.total_reports == 150
        assert stats.by_status["completed"] == 120
        assert stats.active_schedules == 6
        assert stats.reports_last_30d == 100


class TestReportFilterDataclass:
    """Tests for ReportFilter dataclass."""

    def test_empty_filter(self):
        """Test empty filter with all None values."""
        filter = ReportFilter()
        assert filter.status is None
        assert filter.report_type is None
        assert filter.output_format is None
        assert filter.search_text is None

    def test_populated_filter(self):
        """Test filter with values."""
        now = datetime.utcnow()
        filter = ReportFilter(
            status=ReportStatus.COMPLETED,
            report_type=ReportType.SUMMARY,
            output_format=ReportFormat.PDF,
            created_after=now,
            created_before=now,
            search_text="weekly",
        )
        assert filter.status == ReportStatus.COMPLETED
        assert filter.report_type == ReportType.SUMMARY
        assert filter.output_format == ReportFormat.PDF
        assert filter.search_text == "weekly"
