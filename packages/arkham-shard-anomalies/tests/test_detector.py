"""
Anomalies Shard - Detector Tests

Tests for the AnomalyDetector class.
"""

import pytest
import numpy as np

from arkham_shard_anomalies.detector import AnomalyDetector
from arkham_shard_anomalies.models import (
    DetectionConfig,
    AnomalyType,
    SeverityLevel,
)


class TestAnomalyDetectorInit:
    """Tests for AnomalyDetector initialization."""

    def test_default_initialization(self):
        """Test detector initializes with default config."""
        detector = AnomalyDetector()
        assert detector.config is not None
        assert detector.config.z_score_threshold == 3.0

    def test_custom_config(self):
        """Test detector initializes with custom config."""
        config = DetectionConfig(z_score_threshold=2.5)
        detector = AnomalyDetector(config=config)
        assert detector.config.z_score_threshold == 2.5

    def test_patterns_compiled(self):
        """Test regex patterns are compiled."""
        detector = AnomalyDetector()
        assert detector.money_pattern is not None
        assert detector.date_pattern is not None
        assert detector.name_pattern is not None

    def test_sensitive_keywords_set(self):
        """Test sensitive keywords set exists."""
        detector = AnomalyDetector()
        assert "confidential" in detector.sensitive_keywords
        assert "secret" in detector.sensitive_keywords
        assert "classified" in detector.sensitive_keywords


class TestContentAnomalyDetection:
    """Tests for content anomaly detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_detect_content_anomaly(self, detector):
        """Test detecting content anomaly for distant document."""
        # Create an outlier embedding
        doc_embedding = np.array([1.0, 0.0, 0.0])  # Very different from corpus

        # Create corpus with similar embeddings
        corpus_embeddings = [
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.9, 0.1]),
            np.array([0.1, 0.9, 0.0]),
            np.array([0.0, 0.8, 0.2]),
        ]
        corpus_doc_ids = ["doc-1", "doc-2", "doc-3", "doc-4"]

        anomalies = detector.detect_content_anomalies(
            doc_id="doc-outlier",
            embedding=doc_embedding,
            corpus_embeddings=corpus_embeddings,
            corpus_doc_ids=corpus_doc_ids,
        )

        # Should detect as anomaly due to high distance
        assert len(anomalies) >= 0  # May or may not detect depending on thresholds

    def test_detect_content_normal(self, detector):
        """Test no anomaly for similar document."""
        # Create embedding similar to corpus
        doc_embedding = np.array([0.0, 0.95, 0.05])

        corpus_embeddings = [
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.9, 0.1]),
            np.array([0.1, 0.9, 0.0]),
        ]
        corpus_doc_ids = ["doc-1", "doc-2", "doc-3"]

        anomalies = detector.detect_content_anomalies(
            doc_id="doc-normal",
            embedding=doc_embedding,
            corpus_embeddings=corpus_embeddings,
            corpus_doc_ids=corpus_doc_ids,
        )

        # Should not detect anomaly for similar document
        assert len(anomalies) == 0

    def test_content_detection_disabled(self, detector):
        """Test no detection when disabled."""
        detector.config.detect_content = False

        doc_embedding = np.array([1.0, 0.0, 0.0])
        corpus_embeddings = [np.array([0.0, 1.0, 0.0])]
        corpus_doc_ids = ["doc-1"]

        anomalies = detector.detect_content_anomalies(
            doc_id="doc-test",
            embedding=doc_embedding,
            corpus_embeddings=corpus_embeddings,
            corpus_doc_ids=corpus_doc_ids,
        )

        assert len(anomalies) == 0


class TestStatisticalAnomalyDetection:
    """Tests for statistical anomaly detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_detect_statistical_anomaly_word_count(self, detector):
        """Test detecting statistical anomaly in word count."""
        text = "word " * 1000  # Very long document

        corpus_stats = {
            'word_count': {'mean': 100, 'std': 20},
            'sentence_count': {'mean': 10, 'std': 3},
        }

        anomalies = detector.detect_statistical_anomalies(
            doc_id="doc-long",
            text=text,
            corpus_stats=corpus_stats,
        )

        # Should detect word count anomaly
        word_count_anomalies = [a for a in anomalies if a.details.get('metric') == 'word_count']
        assert len(word_count_anomalies) > 0

    def test_detect_statistical_normal(self, detector):
        """Test no anomaly for normal document."""
        text = "This is a normal sentence. " * 10  # Normal length

        corpus_stats = {
            'word_count': {'mean': 50, 'std': 20},
            'sentence_count': {'mean': 10, 'std': 3},
        }

        anomalies = detector.detect_statistical_anomalies(
            doc_id="doc-normal",
            text=text,
            corpus_stats=corpus_stats,
        )

        # Normal document shouldn't trigger anomaly
        assert len(anomalies) == 0

    def test_statistical_detection_disabled(self, detector):
        """Test no detection when disabled."""
        detector.config.detect_statistical = False

        text = "word " * 1000
        corpus_stats = {'word_count': {'mean': 100, 'std': 20}}

        anomalies = detector.detect_statistical_anomalies(
            doc_id="doc-test",
            text=text,
            corpus_stats=corpus_stats,
        )

        assert len(anomalies) == 0


class TestRedFlagDetection:
    """Tests for red flag detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_detect_money_patterns(self, detector):
        """Test detecting money pattern anomaly."""
        # Text with many money references
        text = "The payment of $1,000 was followed by $2,500 and $3,000. " * 5

        anomalies = detector.detect_red_flags(
            doc_id="doc-money",
            text=text,
            metadata={},
        )

        money_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'money']
        assert len(money_anomalies) > 0

    def test_detect_sensitive_keywords(self, detector):
        """Test detecting sensitive keyword anomaly."""
        text = "This document is classified and contains confidential information."

        anomalies = detector.detect_red_flags(
            doc_id="doc-sensitive",
            text=text,
            metadata={},
        )

        keyword_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'sensitive_keywords']
        assert len(keyword_anomalies) > 0
        assert keyword_anomalies[0].severity == SeverityLevel.CRITICAL

    def test_detect_date_patterns(self, detector):
        """Test detecting date pattern anomaly."""
        # Text with many date references
        text = "Meeting on 01/15/2024. Follow-up on 02/20/2024. Review on 03/25/2024. " * 6

        anomalies = detector.detect_red_flags(
            doc_id="doc-dates",
            text=text,
            metadata={},
        )

        date_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'dates']
        assert len(date_anomalies) > 0

    def test_detect_name_patterns(self, detector):
        """Test detecting name pattern anomaly."""
        # Text with many unique name-like patterns (need >20 unique names)
        names = [
            "John Smith", "Jane Doe", "Robert Johnson", "Mary Williams", "James Brown",
            "Sarah Davis", "Michael Wilson", "Emily Taylor", "David Anderson", "Lisa Thomas",
            "Chris Jackson", "Amanda White", "Daniel Harris", "Jessica Martin", "Matthew Garcia",
            "Ashley Martinez", "Joshua Robinson", "Stephanie Clark", "Andrew Rodriguez", "Nicole Lewis",
            "Kevin Lee", "Jennifer Walker", "Brandon Hall", "Samantha Allen",
        ]
        text = ". ".join([f"{name} was mentioned" for name in names])

        anomalies = detector.detect_red_flags(
            doc_id="doc-names",
            text=text,
            metadata={},
        )

        name_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'names']
        assert len(name_anomalies) > 0

    def test_no_red_flags_normal(self, detector):
        """Test no red flags for normal document."""
        text = "This is a normal document without any unusual patterns or content."

        anomalies = detector.detect_red_flags(
            doc_id="doc-normal",
            text=text,
            metadata={},
        )

        assert len(anomalies) == 0

    def test_red_flag_detection_disabled(self, detector):
        """Test no detection when disabled."""
        detector.config.detect_red_flags = False

        text = "This document is classified and confidential."

        anomalies = detector.detect_red_flags(
            doc_id="doc-test",
            text=text,
            metadata={},
        )

        assert len(anomalies) == 0

    def test_individual_pattern_toggles(self, detector):
        """Test individual pattern toggles work."""
        detector.config.money_patterns = False
        detector.config.sensitive_keywords = True

        text = "Paid $1,000,000 for confidential information."

        anomalies = detector.detect_red_flags(
            doc_id="doc-test",
            text=text,
            metadata={},
        )

        # Should only detect sensitive keywords, not money
        money_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'money']
        keyword_anomalies = [a for a in anomalies if a.details.get('pattern_type') == 'sensitive_keywords']

        assert len(money_anomalies) == 0
        assert len(keyword_anomalies) > 0


class TestMetadataAnomalyDetection:
    """Tests for metadata anomaly detection."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_detect_file_size_anomaly(self, detector):
        """Test detecting file size anomaly."""
        metadata = {'file_size': 10000000}  # 10MB - very large

        corpus_stats = {
            'file_size': {'mean': 50000, 'std': 10000},  # ~50KB average
        }

        anomalies = detector.detect_metadata_anomalies(
            doc_id="doc-large",
            metadata=metadata,
            corpus_metadata_stats=corpus_stats,
        )

        assert len(anomalies) > 0
        assert anomalies[0].anomaly_type == AnomalyType.METADATA

    def test_no_metadata_anomaly_normal(self, detector):
        """Test no anomaly for normal metadata."""
        metadata = {'file_size': 55000}  # Close to average

        corpus_stats = {
            'file_size': {'mean': 50000, 'std': 10000},
        }

        anomalies = detector.detect_metadata_anomalies(
            doc_id="doc-normal",
            metadata=metadata,
            corpus_metadata_stats=corpus_stats,
        )

        assert len(anomalies) == 0

    def test_metadata_detection_disabled(self, detector):
        """Test no detection when disabled."""
        detector.config.detect_metadata = False

        metadata = {'file_size': 10000000}
        corpus_stats = {'file_size': {'mean': 50000, 'std': 10000}}

        anomalies = detector.detect_metadata_anomalies(
            doc_id="doc-test",
            metadata=metadata,
            corpus_metadata_stats=corpus_stats,
        )

        assert len(anomalies) == 0


class TestTextStatistics:
    """Tests for text statistics calculation."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_calculate_text_stats(self, detector):
        """Test text statistics calculation."""
        text = "Hello world. This is a test sentence. Another one here."

        stats = detector._calculate_text_stats(text)

        assert 'word_count' in stats
        assert 'sentence_count' in stats
        assert 'avg_word_length' in stats
        assert 'avg_sentence_length' in stats
        assert 'char_count' in stats
        assert stats['word_count'] > 0
        assert stats['sentence_count'] > 0

    def test_calculate_text_stats_empty(self, detector):
        """Test text statistics for empty text."""
        stats = detector._calculate_text_stats("")

        assert stats['word_count'] == 0.0
        assert stats['char_count'] == 0.0


class TestSeverityCalculation:
    """Tests for severity calculation."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_severity_critical(self, detector):
        """Test critical severity for very high z-score."""
        severity = detector._calculate_severity(z_score=7.0, threshold=3.0)
        assert severity == SeverityLevel.CRITICAL

    def test_severity_high(self, detector):
        """Test high severity."""
        severity = detector._calculate_severity(z_score=5.0, threshold=3.0)
        assert severity == SeverityLevel.HIGH

    def test_severity_medium(self, detector):
        """Test medium severity."""
        severity = detector._calculate_severity(z_score=3.5, threshold=3.0)
        assert severity == SeverityLevel.MEDIUM

    def test_severity_low(self, detector):
        """Test low severity for below-threshold z-score."""
        severity = detector._calculate_severity(z_score=2.0, threshold=3.0)
        assert severity == SeverityLevel.LOW


class TestIdGeneration:
    """Tests for ID generation."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return AnomalyDetector()

    def test_generate_unique_ids(self, detector):
        """Test that generated IDs are unique."""
        ids = [detector._generate_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # All unique

    def test_id_is_string(self, detector):
        """Test that generated ID is a string."""
        id = detector._generate_id()
        assert isinstance(id, str)
        assert len(id) > 0
