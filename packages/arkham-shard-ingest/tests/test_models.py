"""
Ingest Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime
from pathlib import Path

from arkham_shard_ingest.models import (
    # Enums
    FileCategory,
    ImageQuality,
    JobPriority,
    JobStatus,
    # Dataclasses
    FileInfo,
    ImageQualityScore,
    IngestJob,
    IngestBatch,
)


class TestFileCategoryEnum:
    """Tests for FileCategory enum."""

    def test_all_values_exist(self):
        """Verify all expected category values exist."""
        assert FileCategory.DOCUMENT.value == "document"
        assert FileCategory.IMAGE.value == "image"
        assert FileCategory.AUDIO.value == "audio"
        assert FileCategory.ARCHIVE.value == "archive"
        assert FileCategory.UNKNOWN.value == "unknown"

    def test_enum_count(self):
        """Verify total number of categories."""
        assert len(FileCategory) == 5


class TestImageQualityEnum:
    """Tests for ImageQuality enum."""

    def test_all_values_exist(self):
        """Verify all expected quality values exist."""
        assert ImageQuality.CLEAN.value == "clean"
        assert ImageQuality.FIXABLE.value == "fixable"
        assert ImageQuality.MESSY.value == "messy"

    def test_enum_count(self):
        """Verify total number of quality levels."""
        assert len(ImageQuality) == 3


class TestJobPriorityEnum:
    """Tests for JobPriority enum."""

    def test_all_values_exist(self):
        """Verify all expected priority values exist."""
        assert JobPriority.USER.value == 1
        assert JobPriority.BATCH.value == 2
        assert JobPriority.REPROCESS.value == 3

    def test_priority_ordering(self):
        """Verify USER has highest priority (lowest value)."""
        assert JobPriority.USER.value < JobPriority.BATCH.value
        assert JobPriority.BATCH.value < JobPriority.REPROCESS.value

    def test_enum_count(self):
        """Verify total number of priorities."""
        assert len(JobPriority) == 3


class TestJobStatusEnum:
    """Tests for JobStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.DEAD.value == "dead"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(JobStatus) == 6


class TestFileInfoDataclass:
    """Tests for FileInfo dataclass."""

    def test_minimal_creation(self):
        """Test creating file info with minimal required fields."""
        file_info = FileInfo(
            path=Path("/tmp/test.pdf"),
            original_name="test.pdf",
            size_bytes=1024,
            mime_type="application/pdf",
            category=FileCategory.DOCUMENT,
            extension=".pdf",
        )
        assert file_info.path == Path("/tmp/test.pdf")
        assert file_info.original_name == "test.pdf"
        assert file_info.size_bytes == 1024
        assert file_info.mime_type == "application/pdf"
        assert file_info.category == FileCategory.DOCUMENT
        assert file_info.extension == ".pdf"

    def test_full_creation_document(self):
        """Test creating file info with all document fields."""
        now = datetime.utcnow()
        file_info = FileInfo(
            path=Path("/tmp/test.pdf"),
            original_name="test.pdf",
            size_bytes=2048000,
            mime_type="application/pdf",
            category=FileCategory.DOCUMENT,
            extension=".pdf",
            created_at=now,
            checksum="abc123hash",
            page_count=42,
        )
        assert file_info.checksum == "abc123hash"
        assert file_info.page_count == 42

    def test_full_creation_image(self):
        """Test creating file info with all image fields."""
        file_info = FileInfo(
            path=Path("/tmp/scan.png"),
            original_name="scan.png",
            size_bytes=500000,
            mime_type="image/png",
            category=FileCategory.IMAGE,
            extension=".png",
            width=1920,
            height=1080,
            dpi=300,
        )
        assert file_info.width == 1920
        assert file_info.height == 1080
        assert file_info.dpi == 300

    def test_default_values(self):
        """Test that default values are set correctly."""
        file_info = FileInfo(
            path=Path("/tmp/test.pdf"),
            original_name="test.pdf",
            size_bytes=1024,
            mime_type="application/pdf",
            category=FileCategory.DOCUMENT,
            extension=".pdf",
        )
        assert file_info.checksum is None
        assert file_info.width is None
        assert file_info.height is None
        assert file_info.dpi is None
        assert file_info.page_count is None
        assert file_info.created_at is not None


class TestImageQualityScoreDataclass:
    """Tests for ImageQualityScore dataclass."""

    def test_clean_image(self):
        """Test classification of a clean image."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=0.5,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
        )
        assert score.classification == ImageQuality.CLEAN
        assert len(score.issues) == 0

    def test_fixable_image(self):
        """Test classification of a fixable image."""
        score = ImageQualityScore(
            dpi=150,
            skew_angle=3.0,
            contrast_ratio=0.6,
            is_grayscale=True,
            compression_ratio=0.7,
            has_noise=False,
            layout_complexity="table",
        )
        # Issues: skew > 2.0
        assert score.classification == ImageQuality.FIXABLE

    def test_messy_image_multiple_issues(self):
        """Test classification of a messy image with multiple issues."""
        score = ImageQualityScore(
            dpi=100,
            skew_angle=5.0,
            contrast_ratio=0.3,
            is_grayscale=True,
            compression_ratio=0.5,
            has_noise=True,
            layout_complexity="complex",
        )
        # Issues: low_dpi, skewed, low_contrast, noisy
        assert score.classification == ImageQuality.MESSY
        assert len(score.issues) >= 4

    def test_messy_image_complex_layout(self):
        """Test that complex layout can lead to messy classification."""
        score = ImageQualityScore(
            dpi=200,
            skew_angle=3.0,
            contrast_ratio=0.6,
            is_grayscale=False,
            compression_ratio=0.8,
            has_noise=True,
            layout_complexity="complex",
        )
        # Issues: skew + noise + complex layout
        assert score.classification == ImageQuality.MESSY

    def test_issues_low_dpi(self):
        """Test that low DPI is detected as an issue."""
        score = ImageQualityScore(
            dpi=100,
            skew_angle=0.0,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
        )
        assert "low_dpi:100" in score.issues

    def test_issues_skewed(self):
        """Test that skew is detected as an issue."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=5.5,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
        )
        assert any("skewed" in issue for issue in score.issues)

    def test_issues_low_contrast(self):
        """Test that low contrast is detected as an issue."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=0.0,
            contrast_ratio=0.3,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
        )
        assert any("low_contrast" in issue for issue in score.issues)

    def test_issues_noisy(self):
        """Test that noise is detected as an issue."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=0.0,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=True,
            layout_complexity="simple",
        )
        assert "noisy" in score.issues

    def test_issues_complex_layout(self):
        """Test that complex layout is detected as an issue."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=0.0,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="mixed",
        )
        assert any("complex_layout" in issue for issue in score.issues)

    def test_analysis_time(self):
        """Test that analysis time is tracked."""
        score = ImageQualityScore(
            dpi=300,
            skew_angle=0.0,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
            analysis_ms=150.5,
        )
        assert score.analysis_ms == 150.5


class TestIngestJobDataclass:
    """Tests for IngestJob dataclass."""

    @pytest.fixture
    def sample_file_info(self):
        """Create sample file info for tests."""
        return FileInfo(
            path=Path("/tmp/test.pdf"),
            original_name="test.pdf",
            size_bytes=1024,
            mime_type="application/pdf",
            category=FileCategory.DOCUMENT,
            extension=".pdf",
        )

    def test_minimal_creation(self, sample_file_info):
        """Test creating a job with minimal required fields."""
        job = IngestJob(
            id="job-123",
            file_info=sample_file_info,
            priority=JobPriority.USER,
        )
        assert job.id == "job-123"
        assert job.file_info == sample_file_info
        assert job.priority == JobPriority.USER
        assert job.status == JobStatus.PENDING
        assert job.worker_route == []

    def test_full_creation(self, sample_file_info):
        """Test creating a job with all fields."""
        now = datetime.utcnow()
        quality = ImageQualityScore(
            dpi=300,
            skew_angle=0.0,
            contrast_ratio=0.8,
            is_grayscale=False,
            compression_ratio=0.9,
            has_noise=False,
            layout_complexity="simple",
        )
        job = IngestJob(
            id="job-full",
            file_info=sample_file_info,
            priority=JobPriority.BATCH,
            status=JobStatus.PROCESSING,
            worker_route=["extract", "parse", "embed"],
            current_worker="parse",
            quality_score=quality,
            created_at=now,
            started_at=now,
            result={"pages": 10},
            retry_count=1,
            max_retries=5,
        )
        assert job.worker_route == ["extract", "parse", "embed"]
        assert job.current_worker == "parse"
        assert job.quality_score == quality
        assert job.result == {"pages": 10}
        assert job.retry_count == 1
        assert job.max_retries == 5

    def test_can_retry_true(self, sample_file_info):
        """Test can_retry when retries available."""
        job = IngestJob(
            id="job-1",
            file_info=sample_file_info,
            priority=JobPriority.USER,
            retry_count=1,
            max_retries=3,
        )
        assert job.can_retry is True

    def test_can_retry_false(self, sample_file_info):
        """Test can_retry when max retries reached."""
        job = IngestJob(
            id="job-1",
            file_info=sample_file_info,
            priority=JobPriority.USER,
            retry_count=3,
            max_retries=3,
        )
        assert job.can_retry is False

    def test_can_retry_exceeded(self, sample_file_info):
        """Test can_retry when retries exceeded."""
        job = IngestJob(
            id="job-1",
            file_info=sample_file_info,
            priority=JobPriority.USER,
            retry_count=5,
            max_retries=3,
        )
        assert job.can_retry is False

    def test_default_values(self, sample_file_info):
        """Test that default values are set correctly."""
        job = IngestJob(
            id="job-1",
            file_info=sample_file_info,
            priority=JobPriority.USER,
        )
        assert job.status == JobStatus.PENDING
        assert job.worker_route == []
        assert job.current_worker is None
        assert job.quality_score is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.result is None
        assert job.error is None
        assert job.retry_count == 0
        assert job.max_retries == 3


class TestIngestBatchDataclass:
    """Tests for IngestBatch dataclass."""

    @pytest.fixture
    def sample_jobs(self):
        """Create sample jobs for batch tests."""
        file_info = FileInfo(
            path=Path("/tmp/test.pdf"),
            original_name="test.pdf",
            size_bytes=1024,
            mime_type="application/pdf",
            category=FileCategory.DOCUMENT,
            extension=".pdf",
        )
        return [
            IngestJob(id=f"job-{i}", file_info=file_info, priority=JobPriority.BATCH)
            for i in range(5)
        ]

    def test_minimal_creation(self):
        """Test creating a batch with minimal fields."""
        batch = IngestBatch(id="batch-1")
        assert batch.id == "batch-1"
        assert batch.jobs == []
        assert batch.priority == JobPriority.BATCH
        assert batch.total_files == 0

    def test_full_creation(self, sample_jobs):
        """Test creating a batch with all fields."""
        now = datetime.utcnow()
        batch = IngestBatch(
            id="batch-full",
            jobs=sample_jobs,
            priority=JobPriority.USER,
            total_files=5,
            completed=2,
            failed=1,
            created_at=now,
        )
        assert len(batch.jobs) == 5
        assert batch.priority == JobPriority.USER
        assert batch.total_files == 5
        assert batch.completed == 2
        assert batch.failed == 1

    def test_pending_property(self):
        """Test pending calculation."""
        batch = IngestBatch(
            id="batch-1",
            total_files=10,
            completed=4,
            failed=2,
        )
        assert batch.pending == 4  # 10 - 4 - 2

    def test_pending_all_completed(self):
        """Test pending when all completed."""
        batch = IngestBatch(
            id="batch-1",
            total_files=10,
            completed=10,
            failed=0,
        )
        assert batch.pending == 0

    def test_is_complete_true(self):
        """Test is_complete when batch is done."""
        batch = IngestBatch(
            id="batch-1",
            total_files=10,
            completed=8,
            failed=2,
        )
        assert batch.is_complete is True

    def test_is_complete_false(self):
        """Test is_complete when batch still has pending jobs."""
        batch = IngestBatch(
            id="batch-1",
            total_files=10,
            completed=5,
            failed=2,
        )
        assert batch.is_complete is False

    def test_default_values(self):
        """Test that default values are set correctly."""
        batch = IngestBatch(id="batch-1")
        assert batch.jobs == []
        assert batch.priority == JobPriority.BATCH
        assert batch.total_files == 0
        assert batch.completed == 0
        assert batch.failed == 0
        assert batch.completed_at is None
