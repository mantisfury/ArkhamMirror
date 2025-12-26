"""
Tests for Patterns Shard Models
"""

import pytest
from datetime import datetime

from arkham_shard_patterns.models import (
    Pattern,
    PatternCreate,
    PatternUpdate,
    PatternMatch,
    PatternMatchCreate,
    PatternFilter,
    PatternCriteria,
    PatternStatistics,
    PatternAnalysisRequest,
    PatternAnalysisResult,
    CorrelationRequest,
    Correlation,
    CorrelationResult,
    PatternType,
    PatternStatus,
    DetectionMethod,
    SourceType,
)


class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_types_exist(self):
        """Test that all expected pattern types exist."""
        assert PatternType.RECURRING_THEME == "recurring_theme"
        assert PatternType.BEHAVIORAL == "behavioral"
        assert PatternType.TEMPORAL == "temporal"
        assert PatternType.CORRELATION == "correlation"
        assert PatternType.LINGUISTIC == "linguistic"
        assert PatternType.STRUCTURAL == "structural"
        assert PatternType.CUSTOM == "custom"

    def test_pattern_type_values(self):
        """Test pattern type string values."""
        assert len(PatternType) == 7


class TestPatternStatus:
    """Tests for PatternStatus enum."""

    def test_status_values(self):
        """Test that all expected statuses exist."""
        assert PatternStatus.DETECTED == "detected"
        assert PatternStatus.CONFIRMED == "confirmed"
        assert PatternStatus.DISMISSED == "dismissed"
        assert PatternStatus.ARCHIVED == "archived"


class TestDetectionMethod:
    """Tests for DetectionMethod enum."""

    def test_detection_methods(self):
        """Test detection method values."""
        assert DetectionMethod.MANUAL == "manual"
        assert DetectionMethod.AUTOMATED == "automated"
        assert DetectionMethod.LLM == "llm"
        assert DetectionMethod.HYBRID == "hybrid"


class TestSourceType:
    """Tests for SourceType enum."""

    def test_source_types(self):
        """Test source type values."""
        assert SourceType.DOCUMENT == "document"
        assert SourceType.ENTITY == "entity"
        assert SourceType.CLAIM == "claim"
        assert SourceType.EVENT == "event"
        assert SourceType.CHUNK == "chunk"


class TestPatternCriteria:
    """Tests for PatternCriteria model."""

    def test_default_criteria(self):
        """Test default criteria values."""
        criteria = PatternCriteria()
        assert criteria.keywords == []
        assert criteria.regex_patterns == []
        assert criteria.entity_types == []
        assert criteria.entity_ids == []
        assert criteria.min_occurrences == 2
        assert criteria.time_window_days is None
        assert criteria.similarity_threshold == 0.8
        assert criteria.custom_rules == {}

    def test_criteria_with_values(self):
        """Test criteria with custom values."""
        criteria = PatternCriteria(
            keywords=["fraud", "embezzlement"],
            min_occurrences=5,
            similarity_threshold=0.9,
        )
        assert criteria.keywords == ["fraud", "embezzlement"]
        assert criteria.min_occurrences == 5
        assert criteria.similarity_threshold == 0.9


class TestPattern:
    """Tests for Pattern model."""

    def test_pattern_creation(self):
        """Test creating a pattern."""
        pattern = Pattern(
            id="test-pattern-1",
            name="Financial Discrepancy",
            description="Recurring financial discrepancies",
            pattern_type=PatternType.RECURRING_THEME,
        )

        assert pattern.id == "test-pattern-1"
        assert pattern.name == "Financial Discrepancy"
        assert pattern.pattern_type == PatternType.RECURRING_THEME
        assert pattern.status == PatternStatus.DETECTED
        assert pattern.confidence == 0.5
        assert pattern.match_count == 0

    def test_pattern_defaults(self):
        """Test pattern default values."""
        pattern = Pattern(
            id="test-pattern-2",
            name="Test Pattern",
            description="A test pattern",
            pattern_type=PatternType.BEHAVIORAL,
        )

        assert pattern.status == PatternStatus.DETECTED
        assert pattern.confidence == 0.5
        assert pattern.match_count == 0
        assert pattern.document_count == 0
        assert pattern.entity_count == 0
        assert pattern.detection_method == DetectionMethod.MANUAL
        assert pattern.metadata == {}

    def test_pattern_with_criteria(self):
        """Test pattern with criteria."""
        criteria = PatternCriteria(
            keywords=["suspicious", "irregular"],
            min_occurrences=3,
        )
        pattern = Pattern(
            id="test-pattern-3",
            name="Suspicious Activity",
            description="Pattern of suspicious activities",
            pattern_type=PatternType.BEHAVIORAL,
            criteria=criteria,
        )

        assert pattern.criteria.keywords == ["suspicious", "irregular"]
        assert pattern.criteria.min_occurrences == 3

    def test_pattern_confidence_bounds(self):
        """Test confidence value bounds."""
        # Valid confidence
        pattern = Pattern(
            id="test",
            name="Test",
            description="Test",
            pattern_type=PatternType.CUSTOM,
            confidence=0.75,
        )
        assert pattern.confidence == 0.75

        # Edge cases
        pattern_min = Pattern(
            id="test-min",
            name="Test",
            description="Test",
            pattern_type=PatternType.CUSTOM,
            confidence=0.0,
        )
        assert pattern_min.confidence == 0.0

        pattern_max = Pattern(
            id="test-max",
            name="Test",
            description="Test",
            pattern_type=PatternType.CUSTOM,
            confidence=1.0,
        )
        assert pattern_max.confidence == 1.0


class TestPatternCreate:
    """Tests for PatternCreate model."""

    def test_pattern_create_minimal(self):
        """Test minimal pattern creation request."""
        request = PatternCreate(
            name="New Pattern",
            description="A new pattern to track",
            pattern_type=PatternType.RECURRING_THEME,
        )

        assert request.name == "New Pattern"
        assert request.pattern_type == PatternType.RECURRING_THEME
        assert request.confidence == 0.5
        assert request.criteria is None

    def test_pattern_create_full(self):
        """Test full pattern creation request."""
        request = PatternCreate(
            name="Full Pattern",
            description="Complete pattern definition",
            pattern_type=PatternType.TEMPORAL,
            criteria=PatternCriteria(keywords=["monthly", "quarterly"]),
            confidence=0.8,
            metadata={"source": "analysis"},
        )

        assert request.confidence == 0.8
        assert request.criteria.keywords == ["monthly", "quarterly"]
        assert request.metadata["source"] == "analysis"


class TestPatternUpdate:
    """Tests for PatternUpdate model."""

    def test_pattern_update_partial(self):
        """Test partial update request."""
        update = PatternUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.description is None
        assert update.status is None

    def test_pattern_update_status(self):
        """Test status update."""
        update = PatternUpdate(status=PatternStatus.CONFIRMED)
        assert update.status == PatternStatus.CONFIRMED


class TestPatternMatch:
    """Tests for PatternMatch model."""

    def test_match_creation(self):
        """Test creating a pattern match."""
        match = PatternMatch(
            id="match-1",
            pattern_id="pattern-1",
            source_type=SourceType.DOCUMENT,
            source_id="doc-123",
            match_score=0.85,
            excerpt="This is the matching text...",
        )

        assert match.id == "match-1"
        assert match.pattern_id == "pattern-1"
        assert match.source_type == SourceType.DOCUMENT
        assert match.match_score == 0.85

    def test_match_with_position(self):
        """Test match with character positions."""
        match = PatternMatch(
            id="match-2",
            pattern_id="pattern-1",
            source_type=SourceType.CHUNK,
            source_id="chunk-456",
            start_char=100,
            end_char=150,
        )

        assert match.start_char == 100
        assert match.end_char == 150


class TestPatternMatchCreate:
    """Tests for PatternMatchCreate model."""

    def test_match_create_minimal(self):
        """Test minimal match creation."""
        request = PatternMatchCreate(
            source_type=SourceType.DOCUMENT,
            source_id="doc-789",
        )

        assert request.source_type == SourceType.DOCUMENT
        assert request.source_id == "doc-789"
        assert request.match_score == 1.0  # Default

    def test_match_create_full(self):
        """Test full match creation."""
        request = PatternMatchCreate(
            source_type=SourceType.ENTITY,
            source_id="entity-123",
            source_title="John Smith",
            match_score=0.9,
            excerpt="John Smith was mentioned...",
            context="Full paragraph context...",
            start_char=50,
            end_char=60,
            metadata={"confidence": "high"},
        )

        assert request.source_title == "John Smith"
        assert request.match_score == 0.9
        assert request.metadata["confidence"] == "high"


class TestPatternFilter:
    """Tests for PatternFilter model."""

    def test_empty_filter(self):
        """Test empty filter."""
        filter_obj = PatternFilter()
        assert filter_obj.pattern_type is None
        assert filter_obj.status is None

    def test_filter_with_values(self):
        """Test filter with values."""
        filter_obj = PatternFilter(
            pattern_type=PatternType.BEHAVIORAL,
            status=PatternStatus.CONFIRMED,
            min_confidence=0.7,
            min_matches=5,
            search_text="financial",
        )

        assert filter_obj.pattern_type == PatternType.BEHAVIORAL
        assert filter_obj.status == PatternStatus.CONFIRMED
        assert filter_obj.min_confidence == 0.7
        assert filter_obj.min_matches == 5
        assert filter_obj.search_text == "financial"


class TestPatternAnalysisRequest:
    """Tests for PatternAnalysisRequest model."""

    def test_analysis_request_documents(self):
        """Test analysis request with document IDs."""
        request = PatternAnalysisRequest(
            document_ids=["doc-1", "doc-2", "doc-3"],
            pattern_types=[PatternType.RECURRING_THEME],
        )

        assert len(request.document_ids) == 3
        assert request.min_confidence == 0.5  # Default

    def test_analysis_request_text(self):
        """Test analysis request with text."""
        request = PatternAnalysisRequest(
            text="Sample text to analyze for patterns...",
            max_patterns=10,
        )

        assert request.text is not None
        assert request.max_patterns == 10


class TestPatternAnalysisResult:
    """Tests for PatternAnalysisResult model."""

    def test_empty_result(self):
        """Test empty analysis result."""
        result = PatternAnalysisResult()

        assert result.patterns_detected == []
        assert result.matches_found == []
        assert result.documents_analyzed == 0
        assert result.processing_time_ms == 0.0
        assert result.errors == []


class TestCorrelation:
    """Tests for Correlation model."""

    def test_correlation_creation(self):
        """Test creating a correlation."""
        correlation = Correlation(
            entity_id_1="entity-1",
            entity_id_2="entity-2",
            correlation_score=0.85,
            co_occurrence_count=15,
            document_ids=["doc-1", "doc-2"],
            correlation_type="co_occurrence",
            description="Entities frequently appear together",
        )

        assert correlation.entity_id_1 == "entity-1"
        assert correlation.correlation_score == 0.85
        assert correlation.co_occurrence_count == 15
        assert len(correlation.document_ids) == 2


class TestCorrelationRequest:
    """Tests for CorrelationRequest model."""

    def test_correlation_request(self):
        """Test correlation request."""
        request = CorrelationRequest(
            entity_ids=["entity-1", "entity-2", "entity-3"],
            time_window_days=60,
            min_occurrences=5,
        )

        assert len(request.entity_ids) == 3
        assert request.time_window_days == 60
        assert request.min_occurrences == 5


class TestPatternStatistics:
    """Tests for PatternStatistics model."""

    def test_default_statistics(self):
        """Test default statistics."""
        stats = PatternStatistics()

        assert stats.total_patterns == 0
        assert stats.by_type == {}
        assert stats.by_status == {}
        assert stats.total_matches == 0
        assert stats.avg_confidence == 0.0

    def test_statistics_with_data(self):
        """Test statistics with data."""
        stats = PatternStatistics(
            total_patterns=50,
            by_type={"recurring_theme": 30, "behavioral": 20},
            by_status={"confirmed": 25, "detected": 20, "dismissed": 5},
            total_matches=150,
            avg_confidence=0.75,
            patterns_confirmed=25,
            patterns_dismissed=5,
            patterns_pending_review=20,
        )

        assert stats.total_patterns == 50
        assert stats.by_type["recurring_theme"] == 30
        assert stats.patterns_confirmed == 25
