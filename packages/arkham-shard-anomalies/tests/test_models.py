"""
Anomalies Shard - Model Tests

Tests for all dataclasses and enums in the models module.
"""

import pytest
from datetime import datetime

from arkham_shard_anomalies.models import (
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    Anomaly,
    AnomalyPattern,
    OutlierResult,
    DetectionConfig,
    DetectRequest,
    PatternRequest,
    AnomalyResult,
    AnomalyList,
    AnomalyStats,
    StatusUpdate,
    AnalystNote,
)


class TestAnomalyTypeEnum:
    """Tests for AnomalyType enum."""

    def test_content_type(self):
        """Test CONTENT type value."""
        assert AnomalyType.CONTENT.value == "content"

    def test_metadata_type(self):
        """Test METADATA type value."""
        assert AnomalyType.METADATA.value == "metadata"

    def test_temporal_type(self):
        """Test TEMPORAL type value."""
        assert AnomalyType.TEMPORAL.value == "temporal"

    def test_structural_type(self):
        """Test STRUCTURAL type value."""
        assert AnomalyType.STRUCTURAL.value == "structural"

    def test_statistical_type(self):
        """Test STATISTICAL type value."""
        assert AnomalyType.STATISTICAL.value == "statistical"

    def test_red_flag_type(self):
        """Test RED_FLAG type value."""
        assert AnomalyType.RED_FLAG.value == "red_flag"

    def test_all_types_exist(self):
        """Test all expected types exist."""
        types = [t.value for t in AnomalyType]
        assert len(types) == 6


class TestAnomalyStatusEnum:
    """Tests for AnomalyStatus enum."""

    def test_detected_status(self):
        """Test DETECTED status value."""
        assert AnomalyStatus.DETECTED.value == "detected"

    def test_confirmed_status(self):
        """Test CONFIRMED status value."""
        assert AnomalyStatus.CONFIRMED.value == "confirmed"

    def test_dismissed_status(self):
        """Test DISMISSED status value."""
        assert AnomalyStatus.DISMISSED.value == "dismissed"

    def test_false_positive_status(self):
        """Test FALSE_POSITIVE status value."""
        assert AnomalyStatus.FALSE_POSITIVE.value == "false_positive"


class TestSeverityLevelEnum:
    """Tests for SeverityLevel enum."""

    def test_critical_severity(self):
        """Test CRITICAL severity value."""
        assert SeverityLevel.CRITICAL.value == "critical"

    def test_high_severity(self):
        """Test HIGH severity value."""
        assert SeverityLevel.HIGH.value == "high"

    def test_medium_severity(self):
        """Test MEDIUM severity value."""
        assert SeverityLevel.MEDIUM.value == "medium"

    def test_low_severity(self):
        """Test LOW severity value."""
        assert SeverityLevel.LOW.value == "low"


class TestAnomalyDataclass:
    """Tests for Anomaly dataclass."""

    def test_minimal_initialization(self):
        """Test Anomaly with required fields only."""
        anomaly = Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.CONTENT,
        )
        assert anomaly.id == "anom-123"
        assert anomaly.doc_id == "doc-456"
        assert anomaly.anomaly_type == AnomalyType.CONTENT
        assert anomaly.status == AnomalyStatus.DETECTED
        assert anomaly.score == 0.0
        assert anomaly.severity == SeverityLevel.MEDIUM
        assert anomaly.confidence == 1.0
        assert anomaly.explanation == ""
        assert anomaly.details == {}

    def test_full_initialization(self):
        """Test Anomaly with all fields."""
        detected = datetime(2024, 6, 15, 10, 0, 0)
        updated = datetime(2024, 6, 15, 11, 0, 0)
        reviewed = datetime(2024, 6, 15, 12, 0, 0)

        anomaly = Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.RED_FLAG,
            status=AnomalyStatus.CONFIRMED,
            score=4.5,
            severity=SeverityLevel.HIGH,
            confidence=0.95,
            explanation="Contains sensitive keywords",
            details={"keywords": ["confidential", "secret"]},
            field_name="content",
            expected_range="normal",
            actual_value="sensitive",
            detected_at=detected,
            updated_at=updated,
            reviewed_by="analyst@example.com",
            reviewed_at=reviewed,
            notes="This is a real issue",
            tags=["sensitive", "legal"],
        )
        assert anomaly.status == AnomalyStatus.CONFIRMED
        assert anomaly.score == 4.5
        assert anomaly.severity == SeverityLevel.HIGH
        assert anomaly.confidence == 0.95
        assert anomaly.reviewed_by == "analyst@example.com"
        assert anomaly.reviewed_at == reviewed
        assert "confidential" in anomaly.details["keywords"]
        assert "sensitive" in anomaly.tags


class TestAnomalyPatternDataclass:
    """Tests for AnomalyPattern dataclass."""

    def test_minimal_initialization(self):
        """Test AnomalyPattern with required fields only."""
        pattern = AnomalyPattern(
            id="pat-123",
            pattern_type="recurring_money",
            description="Multiple documents with excessive money references",
        )
        assert pattern.id == "pat-123"
        assert pattern.pattern_type == "recurring_money"
        assert pattern.anomaly_ids == []
        assert pattern.doc_ids == []
        assert pattern.frequency == 0
        assert pattern.confidence == 1.0

    def test_full_initialization(self):
        """Test AnomalyPattern with all fields."""
        pattern = AnomalyPattern(
            id="pat-123",
            pattern_type="sensitive_cluster",
            description="Cluster of documents with sensitive keywords",
            anomaly_ids=["anom-1", "anom-2", "anom-3"],
            doc_ids=["doc-1", "doc-2", "doc-3"],
            frequency=3,
            confidence=0.85,
            notes="Found in legal documents",
        )
        assert len(pattern.anomaly_ids) == 3
        assert len(pattern.doc_ids) == 3
        assert pattern.frequency == 3
        assert pattern.confidence == 0.85


class TestOutlierResultDataclass:
    """Tests for OutlierResult dataclass."""

    def test_initialization(self):
        """Test OutlierResult initialization."""
        result = OutlierResult(
            doc_id="doc-123",
            is_outlier=True,
            distance_from_centroid=0.85,
            z_score=3.5,
            cluster_id="cluster-1",
            nearest_neighbors=["doc-124", "doc-125"],
        )
        assert result.doc_id == "doc-123"
        assert result.is_outlier is True
        assert result.distance_from_centroid == 0.85
        assert result.z_score == 3.5
        assert result.cluster_id == "cluster-1"
        assert len(result.nearest_neighbors) == 2

    def test_non_outlier(self):
        """Test OutlierResult for non-outlier."""
        result = OutlierResult(
            doc_id="doc-456",
            is_outlier=False,
            z_score=1.2,
        )
        assert result.is_outlier is False
        assert result.z_score == 1.2


class TestDetectionConfigDataclass:
    """Tests for DetectionConfig dataclass."""

    def test_default_initialization(self):
        """Test DetectionConfig with defaults."""
        config = DetectionConfig()
        assert config.z_score_threshold == 3.0
        assert config.min_cluster_distance == 0.7
        assert config.detect_content is True
        assert config.detect_metadata is True
        assert config.detect_temporal is True
        assert config.detect_structural is True
        assert config.detect_statistical is True
        assert config.detect_red_flags is True
        assert config.money_patterns is True
        assert config.date_patterns is True
        assert config.name_patterns is True
        assert config.sensitive_keywords is True
        assert config.batch_size == 100
        assert config.min_confidence == 0.5

    def test_custom_initialization(self):
        """Test DetectionConfig with custom values."""
        config = DetectionConfig(
            z_score_threshold=2.5,
            detect_content=False,
            detect_red_flags=True,
            batch_size=50,
        )
        assert config.z_score_threshold == 2.5
        assert config.detect_content is False
        assert config.batch_size == 50


class TestDetectRequestDataclass:
    """Tests for DetectRequest dataclass."""

    def test_default_initialization(self):
        """Test DetectRequest with defaults."""
        request = DetectRequest()
        assert request.project_id is None
        assert request.doc_ids == []
        assert isinstance(request.config, DetectionConfig)

    def test_with_project(self):
        """Test DetectRequest with project ID."""
        request = DetectRequest(project_id="proj-123")
        assert request.project_id == "proj-123"

    def test_with_doc_ids(self):
        """Test DetectRequest with specific documents."""
        request = DetectRequest(doc_ids=["doc-1", "doc-2", "doc-3"])
        assert len(request.doc_ids) == 3


class TestPatternRequestDataclass:
    """Tests for PatternRequest dataclass."""

    def test_default_initialization(self):
        """Test PatternRequest with defaults."""
        request = PatternRequest()
        assert request.anomaly_ids == []
        assert request.min_frequency == 2
        assert request.pattern_types == []

    def test_custom_initialization(self):
        """Test PatternRequest with custom values."""
        request = PatternRequest(
            anomaly_ids=["anom-1", "anom-2"],
            min_frequency=3,
            pattern_types=["money", "dates"],
        )
        assert len(request.anomaly_ids) == 2
        assert request.min_frequency == 3
        assert "money" in request.pattern_types


class TestAnomalyResultDataclass:
    """Tests for AnomalyResult dataclass."""

    def test_minimal_initialization(self):
        """Test AnomalyResult with required fields."""
        result = AnomalyResult(anomalies_detected=5)
        assert result.anomalies_detected == 5
        assert result.anomalies == []
        assert result.duration_ms == 0.0
        assert result.config_used is None

    def test_with_anomalies(self):
        """Test AnomalyResult with anomaly list."""
        anomaly = Anomaly(
            id="anom-1",
            doc_id="doc-1",
            anomaly_type=AnomalyType.CONTENT,
        )
        result = AnomalyResult(
            anomalies_detected=1,
            anomalies=[anomaly],
            duration_ms=150.5,
        )
        assert len(result.anomalies) == 1
        assert result.duration_ms == 150.5


class TestAnomalyListDataclass:
    """Tests for AnomalyList dataclass."""

    def test_default_initialization(self):
        """Test AnomalyList with required fields."""
        lst = AnomalyList(total=100)
        assert lst.total == 100
        assert lst.items == []
        assert lst.offset == 0
        assert lst.limit == 20
        assert lst.has_more is False
        assert lst.facets == {}

    def test_with_pagination(self):
        """Test AnomalyList with pagination."""
        lst = AnomalyList(
            total=100,
            offset=20,
            limit=20,
            has_more=True,
        )
        assert lst.has_more is True


class TestAnomalyStatsDataclass:
    """Tests for AnomalyStats dataclass."""

    def test_default_initialization(self):
        """Test AnomalyStats with defaults."""
        stats = AnomalyStats()
        assert stats.total_anomalies == 0
        assert stats.by_type == {}
        assert stats.by_status == {}
        assert stats.by_severity == {}
        assert stats.detected_last_24h == 0
        assert stats.confirmed_last_24h == 0
        assert stats.dismissed_last_24h == 0
        assert stats.false_positive_rate == 0.0
        assert stats.avg_confidence == 0.0

    def test_full_initialization(self):
        """Test AnomalyStats with all data."""
        stats = AnomalyStats(
            total_anomalies=50,
            by_type={"content": 20, "red_flag": 30},
            by_status={"detected": 40, "confirmed": 10},
            by_severity={"high": 15, "medium": 35},
            detected_last_24h=5,
            confirmed_last_24h=2,
            false_positive_rate=0.1,
            avg_confidence=0.85,
        )
        assert stats.total_anomalies == 50
        assert stats.by_type["content"] == 20
        assert stats.false_positive_rate == 0.1


class TestStatusUpdateDataclass:
    """Tests for StatusUpdate dataclass."""

    def test_minimal_initialization(self):
        """Test StatusUpdate with required fields."""
        update = StatusUpdate(status=AnomalyStatus.CONFIRMED)
        assert update.status == AnomalyStatus.CONFIRMED
        assert update.notes == ""
        assert update.reviewed_by is None

    def test_full_initialization(self):
        """Test StatusUpdate with all fields."""
        update = StatusUpdate(
            status=AnomalyStatus.DISMISSED,
            notes="Normal behavior for this document type",
            reviewed_by="analyst@example.com",
        )
        assert update.notes == "Normal behavior for this document type"
        assert update.reviewed_by == "analyst@example.com"


class TestAnalystNoteDataclass:
    """Tests for AnalystNote dataclass."""

    def test_initialization(self):
        """Test AnalystNote initialization."""
        note = AnalystNote(
            id="note-123",
            anomaly_id="anom-456",
            author="analyst@example.com",
            content="This needs further investigation.",
        )
        assert note.id == "note-123"
        assert note.anomaly_id == "anom-456"
        assert note.author == "analyst@example.com"
        assert note.content == "This needs further investigation."
        assert isinstance(note.created_at, datetime)
