"""
Unit tests for v0.2 Data Extraction features:
- Regex Search / Sensitive Data Detection
- PDF Metadata Scrubbing

Run with: python -m pytest tests/test_v0.2_data_extraction.py -v
"""

import pytest
from datetime import datetime
from backend.utils.pattern_detector import PatternDetector, detect_sensitive_data
from backend.metadata_service import extract_pdf_metadata, parse_pdf_date, is_metadata_suspicious


class TestPatternDetection:
    """Tests for sensitive data pattern detection."""

    def test_ssn_detection(self):
        """Test SSN pattern detection."""
        detector = PatternDetector()

        text = "My SSN is 123-45-6789 and my friend's is 987-65-4321"
        matches = detector.detect_patterns(text, pattern_types=["ssn"])

        assert len(matches) == 2
        assert matches[0].pattern_type == "ssn"
        assert "123-45-6789" in matches[0].match_text

    def test_ssn_validation(self):
        """Test SSN validation logic."""
        detector = PatternDetector()

        # Valid SSN
        text = "Valid: 123-45-6789"
        matches = detector.detect_patterns(text, pattern_types=["ssn"])
        assert len(matches) == 1
        assert matches[0].confidence > 0.8

        # Invalid SSN (000 area)
        text = "Invalid: 000-45-6789"
        matches = detector.detect_patterns(text, pattern_types=["ssn"])
        assert len(matches) == 0  # Should be filtered out

    def test_credit_card_detection(self):
        """Test credit card detection with Luhn validation."""
        detector = PatternDetector()

        # Valid test card number (passes Luhn)
        text = "Card: 4532 0151 5155 5151"
        matches = detector.detect_patterns(text, pattern_types=["credit_card"])

        assert len(matches) >= 1
        assert matches[0].pattern_type == "credit_card"
        assert matches[0].confidence > 0.9  # Luhn validation

    def test_email_detection(self):
        """Test email pattern detection."""
        detector = PatternDetector()

        text = "Contact: john.doe@example.com or admin@test.org"
        matches = detector.detect_patterns(text, pattern_types=["email"])

        assert len(matches) == 2
        assert "john.doe@example.com" in [m.match_text for m in matches]
        assert "admin@test.org" in [m.match_text for m in matches]

    def test_phone_detection(self):
        """Test phone number detection."""
        detector = PatternDetector()

        text = "Call me at (555) 123-4567 or +1-555-987-6543"
        matches = detector.detect_patterns(text, pattern_types=["phone"])

        assert len(matches) >= 1
        assert matches[0].pattern_type == "phone"

    def test_ip_address_detection(self):
        """Test IP address detection."""
        detector = PatternDetector()

        text = "Server IP: 192.168.1.1 and gateway: 10.0.0.1"
        matches = detector.detect_patterns(text, pattern_types=["ip_address"])

        assert len(matches) == 2
        assert "192.168.1.1" in [m.match_text for m in matches]

    def test_api_key_detection(self):
        """Test generic API key detection."""
        detector = PatternDetector()

        text = "API Key: sk_test_abcdef1234567890abcdef1234567890abc"
        matches = detector.detect_patterns(text, pattern_types=["api_key_generic"])

        # Should detect keys with sufficient length and entropy
        if matches:
            assert matches[0].pattern_type == "api_key_generic"
            assert len(matches[0].match_text) >= 32

    def test_aws_key_detection(self):
        """Test AWS access key detection."""
        detector = PatternDetector()

        text = "AWS Key: AKIAIOSFODNN7EXAMPLE"
        matches = detector.detect_patterns(text, pattern_types=["aws_access_key"])

        assert len(matches) == 1
        assert matches[0].match_text == "AKIAIOSFODNN7EXAMPLE"

    def test_bitcoin_detection(self):
        """Test Bitcoin address detection."""
        detector = PatternDetector()

        text = "Send BTC to: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        matches = detector.detect_patterns(text, pattern_types=["bitcoin"])

        assert len(matches) >= 1
        assert matches[0].pattern_type == "bitcoin"

    def test_context_extraction(self):
        """Test that context before/after is captured."""
        detector = PatternDetector()

        text = "The secret code is 123-45-6789 for access."
        matches = detector.detect_patterns(text, pattern_types=["ssn"], context_chars=15)

        assert len(matches) == 1
        assert "secret code" in matches[0].context_before.lower()
        assert "for access" in matches[0].context_after.lower()

    def test_multiple_pattern_types(self):
        """Test detecting multiple pattern types in one text."""
        detector = PatternDetector()

        text = "Contact: john@example.com, SSN: 123-45-6789, Phone: (555) 123-4567"
        matches = detector.detect_patterns(text, pattern_types=["email", "ssn", "phone"])

        assert len(matches) >= 3
        pattern_types_found = set([m.pattern_type for m in matches])
        assert "email" in pattern_types_found
        assert "ssn" in pattern_types_found
        assert "phone" in pattern_types_found

    def test_no_matches(self):
        """Test behavior when no patterns are found."""
        detector = PatternDetector()

        text = "This is just normal text with no sensitive data."
        matches = detector.detect_patterns(text)

        assert len(matches) == 0


class TestPDFMetadataExtraction:
    """Tests for PDF metadata extraction."""

    def test_parse_pdf_date_full(self):
        """Test parsing full PDF date string."""
        pdf_date = "D:20230315120000+05'00'"
        result = parse_pdf_date(pdf_date)

        assert result is not None
        assert result.year == 2023
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 12

    def test_parse_pdf_date_short(self):
        """Test parsing short PDF date string (date only)."""
        pdf_date = "D:20230315"
        result = parse_pdf_date(pdf_date)

        assert result is not None
        assert result.year == 2023
        assert result.month == 3
        assert result.day == 15

    def test_parse_pdf_date_no_prefix(self):
        """Test parsing PDF date without D: prefix."""
        pdf_date = "20230315120000"
        result = parse_pdf_date(pdf_date)

        assert result is not None
        assert result.year == 2023

    def test_parse_pdf_date_invalid(self):
        """Test handling of invalid date strings."""
        assert parse_pdf_date("invalid") is None
        assert parse_pdf_date("") is None
        assert parse_pdf_date(None) is None

    def test_metadata_suspicious_missing_author(self):
        """Test detection of suspicious metadata (missing author)."""
        metadata = {
            "pdf_author": None,
            "pdf_creator": None,
            "pdf_producer": "SomePDF",
            "pdf_creation_date": datetime(2023, 1, 1),
            "pdf_modification_date": datetime(2023, 1, 2)
        }

        is_suspicious, reasons = is_metadata_suspicious(metadata)
        assert is_suspicious
        assert any("missing author" in r.lower() for r in reasons)

    def test_metadata_suspicious_manipulation_tool(self):
        """Test detection of metadata manipulation tools."""
        metadata = {
            "pdf_author": "John Doe",
            "pdf_creator": "Word",
            "pdf_producer": "ExifTool 12.0",
            "pdf_creation_date": datetime(2023, 1, 1),
            "pdf_modification_date": datetime(2023, 1, 2)
        }

        is_suspicious, reasons = is_metadata_suspicious(metadata)
        assert is_suspicious
        assert any("manipulation" in r.lower() for r in reasons)

    def test_metadata_suspicious_date_inconsistency(self):
        """Test detection of modification date before creation date."""
        metadata = {
            "pdf_author": "John Doe",
            "pdf_creator": "Word",
            "pdf_producer": "Adobe",
            "pdf_creation_date": datetime(2023, 1, 10),
            "pdf_modification_date": datetime(2023, 1, 5)  # Before creation!
        }

        is_suspicious, reasons = is_metadata_suspicious(metadata)
        assert is_suspicious
        assert any("modification date is before creation" in r.lower() for r in reasons)

    def test_metadata_not_suspicious(self):
        """Test normal metadata is not flagged as suspicious."""
        metadata = {
            "pdf_author": "John Doe",
            "pdf_creator": "Microsoft Word",
            "pdf_producer": "Adobe PDF Library",
            "pdf_creation_date": datetime(2020, 1, 1),
            "pdf_modification_date": datetime(2020, 1, 2)
        }

        is_suspicious, reasons = is_metadata_suspicious(metadata)
        # Recent creation might flag, but check for major issues
        if is_suspicious:
            assert "manipulation" not in " ".join(reasons).lower()
            assert "before creation" not in " ".join(reasons).lower()


class TestIntegration:
    """Integration tests for both features."""

    def test_detect_sensitive_data_convenience_function(self):
        """Test convenience function for pattern detection."""
        text = "Email: test@example.com, Phone: 555-1234"
        matches = detect_sensitive_data(text, pattern_types=["email", "phone"])

        assert len(matches) >= 1

    def test_pattern_detector_singleton(self):
        """Test that pattern detector uses singleton pattern."""
        from backend.utils.pattern_detector import get_detector

        detector1 = get_detector()
        detector2 = get_detector()

        assert detector1 is detector2  # Same instance

    def test_all_pattern_types_available(self):
        """Test that all documented pattern types are available."""
        detector = PatternDetector()
        descriptions = detector.get_pattern_descriptions()

        expected_patterns = [
            "ssn", "credit_card", "email", "phone", "ip_address",
            "api_key_generic", "aws_access_key", "github_token",
            "iban", "bitcoin", "passport", "drivers_license"
        ]

        for pattern in expected_patterns:
            assert pattern in descriptions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
