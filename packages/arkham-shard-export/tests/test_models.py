"""
Export Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime, timedelta

from arkham_shard_export.models import (
    # Enums
    ExportFormat,
    ExportStatus,
    ExportTarget,
    # Dataclasses
    ExportOptions,
    ExportJob,
    ExportResult,
    ExportStatistics,
    ExportFilter,
    FormatInfo,
    TargetInfo,
)


class TestExportFormatEnum:
    """Tests for ExportFormat enum."""

    def test_all_values_exist(self):
        """Verify all expected format values exist."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.PDF.value == "pdf"
        assert ExportFormat.DOCX.value == "docx"
        assert ExportFormat.XLSX.value == "xlsx"

    def test_string_inheritance(self):
        """Verify enum values can be used as strings."""
        assert ExportFormat.JSON == "json"
        assert str(ExportFormat.JSON) == "json"

    def test_enum_count(self):
        """Verify total number of formats."""
        assert len(ExportFormat) == 5


class TestExportStatusEnum:
    """Tests for ExportStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert ExportStatus.PENDING.value == "pending"
        assert ExportStatus.PROCESSING.value == "processing"
        assert ExportStatus.COMPLETED.value == "completed"
        assert ExportStatus.FAILED.value == "failed"
        assert ExportStatus.CANCELLED.value == "cancelled"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(ExportStatus) == 5


class TestExportTargetEnum:
    """Tests for ExportTarget enum."""

    def test_all_values_exist(self):
        """Verify all expected target values exist."""
        assert ExportTarget.DOCUMENTS.value == "documents"
        assert ExportTarget.ENTITIES.value == "entities"
        assert ExportTarget.CLAIMS.value == "claims"
        assert ExportTarget.TIMELINE.value == "timeline"
        assert ExportTarget.GRAPH.value == "graph"
        assert ExportTarget.MATRIX.value == "matrix"
        assert ExportTarget.CUSTOM.value == "custom"

    def test_enum_count(self):
        """Verify total number of targets."""
        assert len(ExportTarget) == 7


class TestExportOptionsDataclass:
    """Tests for ExportOptions dataclass."""

    def test_minimal_creation(self):
        """Test creating options with defaults."""
        options = ExportOptions()
        assert options.include_metadata is True
        assert options.include_relationships is True
        assert options.flatten is False
        assert options.date_range_start is None
        assert options.entity_types is None

    def test_full_creation(self):
        """Test creating options with all fields."""
        now = datetime.utcnow()
        options = ExportOptions(
            include_metadata=False,
            include_relationships=False,
            date_range_start=now,
            date_range_end=now + timedelta(days=7),
            entity_types=["person", "organization"],
            flatten=True,
            max_records=100,
            sort_by="created_at",
            sort_order="desc",
        )
        assert options.include_metadata is False
        assert options.flatten is True
        assert len(options.entity_types) == 2
        assert options.max_records == 100
        assert options.sort_order == "desc"


class TestExportJobDataclass:
    """Tests for ExportJob dataclass."""

    def test_minimal_creation(self):
        """Test creating a job with minimal required fields."""
        job = ExportJob(
            id="job-1",
            format=ExportFormat.JSON,
            target=ExportTarget.DOCUMENTS,
        )
        assert job.id == "job-1"
        assert job.format == ExportFormat.JSON
        assert job.target == ExportTarget.DOCUMENTS
        assert job.status == ExportStatus.PENDING
        assert job.record_count == 0

    def test_full_creation(self):
        """Test creating a job with all fields."""
        now = datetime.utcnow()
        options = ExportOptions(flatten=True)
        job = ExportJob(
            id="job-full",
            format=ExportFormat.CSV,
            target=ExportTarget.ENTITIES,
            status=ExportStatus.COMPLETED,
            created_at=now,
            started_at=now,
            completed_at=now + timedelta(seconds=5),
            file_path="/tmp/export.csv",
            file_size=1024,
            download_url="/api/export/jobs/job-full/download",
            expires_at=now + timedelta(hours=24),
            error=None,
            filters={"entity_type": "person"},
            options=options,
            record_count=50,
            processing_time_ms=5000.0,
            created_by="user-123",
            metadata={"version": "1.0"},
        )
        assert job.id == "job-full"
        assert job.format == ExportFormat.CSV
        assert job.status == ExportStatus.COMPLETED
        assert job.file_size == 1024
        assert job.record_count == 50
        assert job.created_by == "user-123"
        assert job.options.flatten is True

    def test_default_values(self):
        """Test that default values are set correctly."""
        job = ExportJob(
            id="test",
            format=ExportFormat.JSON,
            target=ExportTarget.DOCUMENTS,
        )
        assert job.filters == {}
        assert job.metadata == {}
        assert job.processing_time_ms == 0
        assert job.created_by == "system"


class TestExportResultDataclass:
    """Tests for ExportResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful export result."""
        now = datetime.utcnow()
        result = ExportResult(
            job_id="job-1",
            success=True,
            file_path="/tmp/export.json",
            file_size=2048,
            download_url="/api/export/jobs/job-1/download",
            expires_at=now + timedelta(hours=24),
            record_count=100,
            processing_time_ms=1500.0,
        )
        assert result.success is True
        assert result.file_size == 2048
        assert result.record_count == 100
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed export result."""
        result = ExportResult(
            job_id="job-2",
            success=False,
            error="Database connection failed",
            processing_time_ms=500.0,
        )
        assert result.success is False
        assert result.error == "Database connection failed"
        assert result.file_size == 0
        assert result.record_count == 0


class TestExportStatisticsDataclass:
    """Tests for ExportStatistics dataclass."""

    def test_default_values(self):
        """Test default values for statistics."""
        stats = ExportStatistics()
        assert stats.total_jobs == 0
        assert stats.by_status == {}
        assert stats.by_format == {}
        assert stats.by_target == {}
        assert stats.jobs_pending == 0
        assert stats.total_records_exported == 0

    def test_populated_statistics(self):
        """Test statistics with data."""
        now = datetime.utcnow()
        stats = ExportStatistics(
            total_jobs=100,
            by_status={"completed": 80, "pending": 10, "failed": 10},
            by_format={"json": 50, "csv": 40, "pdf": 10},
            by_target={"documents": 60, "entities": 40},
            jobs_pending=10,
            jobs_processing=5,
            jobs_completed=80,
            jobs_failed=5,
            total_records_exported=10000,
            total_file_size_bytes=1024000,
            avg_processing_time_ms=2500.5,
            oldest_pending_job=now - timedelta(hours=2),
        )
        assert stats.total_jobs == 100
        assert stats.by_status["completed"] == 80
        assert stats.total_records_exported == 10000
        assert stats.avg_processing_time_ms == 2500.5


class TestExportFilterDataclass:
    """Tests for ExportFilter dataclass."""

    def test_empty_filter(self):
        """Test empty filter with all None values."""
        filter = ExportFilter()
        assert filter.status is None
        assert filter.format is None
        assert filter.target is None
        assert filter.created_by is None

    def test_populated_filter(self):
        """Test filter with values."""
        now = datetime.utcnow()
        filter = ExportFilter(
            status=ExportStatus.COMPLETED,
            format=ExportFormat.CSV,
            target=ExportTarget.ENTITIES,
            created_after=now - timedelta(days=7),
            created_before=now,
            created_by="user-123",
        )
        assert filter.status == ExportStatus.COMPLETED
        assert filter.format == ExportFormat.CSV
        assert filter.target == ExportTarget.ENTITIES
        assert filter.created_by == "user-123"


class TestFormatInfoDataclass:
    """Tests for FormatInfo dataclass."""

    def test_creation(self):
        """Test creating format info."""
        info = FormatInfo(
            format=ExportFormat.JSON,
            name="JSON",
            description="JavaScript Object Notation",
            file_extension=".json",
            mime_type="application/json",
            supports_metadata=True,
            supports_flatten=False,
            placeholder=False,
        )
        assert info.format == ExportFormat.JSON
        assert info.name == "JSON"
        assert info.file_extension == ".json"
        assert info.supports_metadata is True
        assert info.placeholder is False


class TestTargetInfoDataclass:
    """Tests for TargetInfo dataclass."""

    def test_creation(self):
        """Test creating target info."""
        info = TargetInfo(
            target=ExportTarget.DOCUMENTS,
            name="Documents",
            description="Export document records",
            available_formats=[ExportFormat.JSON, ExportFormat.CSV],
            estimated_record_count=100,
            supports_filters=True,
        )
        assert info.target == ExportTarget.DOCUMENTS
        assert info.name == "Documents"
        assert len(info.available_formats) == 2
        assert ExportFormat.JSON in info.available_formats
        assert info.estimated_record_count == 100
