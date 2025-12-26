"""Tests for Summary Shard models."""

import pytest
from datetime import datetime

from arkham_shard_summary.models import (
    Summary,
    SummaryType,
    SummaryStatus,
    SourceType,
    SummaryLength,
    SummaryRequest,
    SummaryResult,
    SummaryFilter,
    SummaryStatistics,
    BatchSummaryRequest,
    BatchSummaryResult,
    KeyPoint,
)


class TestEnums:
    """Test enum definitions."""

    def test_summary_type_enum(self):
        """Test SummaryType enum values."""
        assert SummaryType.BRIEF.value == "brief"
        assert SummaryType.DETAILED.value == "detailed"
        assert SummaryType.EXECUTIVE.value == "executive"
        assert SummaryType.BULLET_POINTS.value == "bullet_points"
        assert SummaryType.ABSTRACT.value == "abstract"

    def test_source_type_enum(self):
        """Test SourceType enum values."""
        assert SourceType.DOCUMENT.value == "document"
        assert SourceType.DOCUMENTS.value == "documents"
        assert SourceType.ENTITY.value == "entity"
        assert SourceType.PROJECT.value == "project"
        assert SourceType.CLAIM_SET.value == "claim_set"
        assert SourceType.TIMELINE.value == "timeline"
        assert SourceType.ANALYSIS.value == "analysis"

    def test_summary_status_enum(self):
        """Test SummaryStatus enum values."""
        assert SummaryStatus.PENDING.value == "pending"
        assert SummaryStatus.GENERATING.value == "generating"
        assert SummaryStatus.COMPLETED.value == "completed"
        assert SummaryStatus.FAILED.value == "failed"
        assert SummaryStatus.STALE.value == "stale"

    def test_summary_length_enum(self):
        """Test SummaryLength enum values."""
        assert SummaryLength.VERY_SHORT.value == "very_short"
        assert SummaryLength.SHORT.value == "short"
        assert SummaryLength.MEDIUM.value == "medium"
        assert SummaryLength.LONG.value == "long"
        assert SummaryLength.VERY_LONG.value == "very_long"


class TestSummary:
    """Test Summary dataclass."""

    def test_create_summary(self):
        """Test creating a Summary object."""
        summary = Summary(
            id="sum-123",
            summary_type=SummaryType.DETAILED,
            status=SummaryStatus.COMPLETED,
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-456"],
            content="This is a test summary.",
            key_points=["Point 1", "Point 2"],
            title="Test Summary",
            word_count=5,
            token_count=7,
        )

        assert summary.id == "sum-123"
        assert summary.summary_type == SummaryType.DETAILED
        assert summary.status == SummaryStatus.COMPLETED
        assert summary.source_type == SourceType.DOCUMENT
        assert summary.source_ids == ["doc-456"]
        assert summary.content == "This is a test summary."
        assert summary.key_points == ["Point 1", "Point 2"]
        assert summary.title == "Test Summary"
        assert summary.word_count == 5
        assert summary.token_count == 7

    def test_summary_defaults(self):
        """Test Summary default values."""
        summary = Summary(id="sum-123")

        assert summary.summary_type == SummaryType.DETAILED
        assert summary.status == SummaryStatus.COMPLETED
        assert summary.source_type == SourceType.DOCUMENT
        assert summary.source_ids == []
        assert summary.content == ""
        assert summary.key_points == []
        assert summary.title is None
        assert summary.confidence == 1.0
        assert summary.completeness == 1.0
        assert summary.target_length == SummaryLength.MEDIUM
        assert summary.focus_areas == []
        assert summary.exclude_topics == []
        assert isinstance(summary.created_at, datetime)
        assert isinstance(summary.updated_at, datetime)

    def test_summary_with_metadata(self):
        """Test Summary with metadata and tags."""
        summary = Summary(
            id="sum-123",
            metadata={"custom_field": "value"},
            tags=["important", "review"],
        )

        assert summary.metadata == {"custom_field": "value"}
        assert summary.tags == ["important", "review"]


class TestSummaryRequest:
    """Test SummaryRequest dataclass."""

    def test_create_request(self):
        """Test creating a SummaryRequest."""
        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-123"],
            summary_type=SummaryType.BRIEF,
            target_length=SummaryLength.SHORT,
            focus_areas=["key findings"],
            exclude_topics=["acknowledgments"],
        )

        assert request.source_type == SourceType.DOCUMENT
        assert request.source_ids == ["doc-123"]
        assert request.summary_type == SummaryType.BRIEF
        assert request.target_length == SummaryLength.SHORT
        assert request.focus_areas == ["key findings"]
        assert request.exclude_topics == ["acknowledgments"]

    def test_request_defaults(self):
        """Test SummaryRequest default values."""
        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-123"],
        )

        assert request.summary_type == SummaryType.DETAILED
        assert request.target_length == SummaryLength.MEDIUM
        assert request.focus_areas == []
        assert request.exclude_topics == []
        assert request.include_key_points is True
        assert request.include_title is True
        assert request.tags == []


class TestSummaryResult:
    """Test SummaryResult dataclass."""

    def test_create_result(self):
        """Test creating a SummaryResult."""
        result = SummaryResult(
            summary_id="sum-123",
            status=SummaryStatus.COMPLETED,
            content="This is a summary.",
            key_points=["Point 1", "Point 2"],
            title="Test Title",
            token_count=100,
            word_count=80,
            processing_time_ms=1234.5,
            confidence=0.95,
        )

        assert result.summary_id == "sum-123"
        assert result.status == SummaryStatus.COMPLETED
        assert result.content == "This is a summary."
        assert result.key_points == ["Point 1", "Point 2"]
        assert result.title == "Test Title"
        assert result.token_count == 100
        assert result.word_count == 80
        assert result.processing_time_ms == 1234.5
        assert result.confidence == 0.95

    def test_result_with_error(self):
        """Test SummaryResult with error."""
        result = SummaryResult(
            summary_id="sum-123",
            status=SummaryStatus.FAILED,
            error_message="LLM service unavailable",
            warnings=["Falling back to extractive summarization"],
        )

        assert result.status == SummaryStatus.FAILED
        assert result.error_message == "LLM service unavailable"
        assert result.warnings == ["Falling back to extractive summarization"]


class TestBatchSummaryRequest:
    """Test BatchSummaryRequest dataclass."""

    def test_create_batch_request(self):
        """Test creating a BatchSummaryRequest."""
        req1 = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-1"],
        )
        req2 = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-2"],
        )

        batch_request = BatchSummaryRequest(
            requests=[req1, req2],
            parallel=True,
            stop_on_error=False,
        )

        assert len(batch_request.requests) == 2
        assert batch_request.parallel is True
        assert batch_request.stop_on_error is False


class TestBatchSummaryResult:
    """Test BatchSummaryResult dataclass."""

    def test_create_batch_result(self):
        """Test creating a BatchSummaryResult."""
        result1 = SummaryResult(summary_id="sum-1", status=SummaryStatus.COMPLETED)
        result2 = SummaryResult(summary_id="sum-2", status=SummaryStatus.COMPLETED)

        batch_result = BatchSummaryResult(
            total=2,
            successful=2,
            failed=0,
            summaries=[result1, result2],
            errors=[],
            total_processing_time_ms=2500.0,
        )

        assert batch_result.total == 2
        assert batch_result.successful == 2
        assert batch_result.failed == 0
        assert len(batch_result.summaries) == 2
        assert batch_result.errors == []
        assert batch_result.total_processing_time_ms == 2500.0


class TestSummaryFilter:
    """Test SummaryFilter dataclass."""

    def test_create_filter(self):
        """Test creating a SummaryFilter."""
        filter = SummaryFilter(
            summary_type=SummaryType.DETAILED,
            source_type=SourceType.DOCUMENT,
            source_id="doc-123",
            status=SummaryStatus.COMPLETED,
            min_confidence=0.8,
        )

        assert filter.summary_type == SummaryType.DETAILED
        assert filter.source_type == SourceType.DOCUMENT
        assert filter.source_id == "doc-123"
        assert filter.status == SummaryStatus.COMPLETED
        assert filter.min_confidence == 0.8

    def test_filter_defaults(self):
        """Test SummaryFilter default values."""
        filter = SummaryFilter()

        assert filter.summary_type is None
        assert filter.source_type is None
        assert filter.source_id is None
        assert filter.status is None
        assert filter.min_confidence is None
        assert filter.tags is None
        assert filter.search_text is None


class TestSummaryStatistics:
    """Test SummaryStatistics dataclass."""

    def test_create_statistics(self):
        """Test creating SummaryStatistics."""
        stats = SummaryStatistics(
            total_summaries=42,
            by_type={"detailed": 20, "brief": 15, "executive": 7},
            by_source_type={"document": 30, "documents": 10, "project": 2},
            by_status={"completed": 40, "pending": 2},
            avg_confidence=0.95,
            avg_word_count=234.5,
            avg_processing_time_ms=1234.5,
            generated_last_24h=10,
        )

        assert stats.total_summaries == 42
        assert stats.by_type["detailed"] == 20
        assert stats.by_source_type["document"] == 30
        assert stats.by_status["completed"] == 40
        assert stats.avg_confidence == 0.95
        assert stats.avg_word_count == 234.5
        assert stats.avg_processing_time_ms == 1234.5
        assert stats.generated_last_24h == 10

    def test_statistics_defaults(self):
        """Test SummaryStatistics default values."""
        stats = SummaryStatistics()

        assert stats.total_summaries == 0
        assert stats.by_type == {}
        assert stats.by_source_type == {}
        assert stats.by_status == {}
        assert stats.avg_confidence == 0.0
        assert stats.avg_word_count == 0.0
        assert stats.avg_processing_time_ms == 0.0
        assert stats.generated_last_24h == 0


class TestKeyPoint:
    """Test KeyPoint dataclass."""

    def test_create_key_point(self):
        """Test creating a KeyPoint."""
        point = KeyPoint(
            text="This is a key finding",
            importance=0.9,
            source_reference="doc-123",
            page_number=5,
            section="Results",
        )

        assert point.text == "This is a key finding"
        assert point.importance == 0.9
        assert point.source_reference == "doc-123"
        assert point.page_number == 5
        assert point.section == "Results"

    def test_key_point_defaults(self):
        """Test KeyPoint default values."""
        point = KeyPoint(text="Key finding")

        assert point.text == "Key finding"
        assert point.importance == 1.0
        assert point.source_reference is None
        assert point.page_number is None
        assert point.section is None
