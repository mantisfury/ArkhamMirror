"""
Tests for Letters Shard - Data Models
"""

import pytest
from datetime import datetime

from arkham_shard_letters.models import (
    ExportFormat,
    Letter,
    LetterExportResult,
    LetterFilter,
    LetterStatistics,
    LetterStatus,
    LetterTemplate,
    LetterType,
    PlaceholderValue,
)


class TestLetterType:
    """Test LetterType enum."""

    def test_letter_types(self):
        """Test all letter types are defined."""
        assert LetterType.FOIA == "foia"
        assert LetterType.COMPLAINT == "complaint"
        assert LetterType.DEMAND == "demand"
        assert LetterType.NOTICE == "notice"
        assert LetterType.COVER == "cover"
        assert LetterType.INQUIRY == "inquiry"
        assert LetterType.RESPONSE == "response"
        assert LetterType.CUSTOM == "custom"


class TestLetterStatus:
    """Test LetterStatus enum."""

    def test_letter_statuses(self):
        """Test all letter statuses are defined."""
        assert LetterStatus.DRAFT == "draft"
        assert LetterStatus.REVIEW == "review"
        assert LetterStatus.FINALIZED == "finalized"
        assert LetterStatus.SENT == "sent"


class TestExportFormat:
    """Test ExportFormat enum."""

    def test_export_formats(self):
        """Test all export formats are defined."""
        assert ExportFormat.PDF == "pdf"
        assert ExportFormat.DOCX == "docx"
        assert ExportFormat.HTML == "html"
        assert ExportFormat.MARKDOWN == "markdown"
        assert ExportFormat.TXT == "txt"


class TestLetter:
    """Test Letter dataclass."""

    def test_letter_creation(self):
        """Test creating a letter."""
        letter = Letter(
            id="letter-1",
            title="Test Letter",
            letter_type=LetterType.FOIA,
            status=LetterStatus.DRAFT,
            content="This is a test letter.",
        )

        assert letter.id == "letter-1"
        assert letter.title == "Test Letter"
        assert letter.letter_type == LetterType.FOIA
        assert letter.status == LetterStatus.DRAFT
        assert letter.content == "This is a test letter."
        assert letter.template_id is None
        assert letter.metadata == {}

    def test_letter_with_recipients(self):
        """Test letter with recipient information."""
        letter = Letter(
            id="letter-2",
            title="FOIA Request",
            letter_type=LetterType.FOIA,
            recipient_name="FOIA Officer",
            recipient_address="123 Main St",
            recipient_email="foia@agency.gov",
            sender_name="John Doe",
            sender_address="456 Oak Ave",
        )

        assert letter.recipient_name == "FOIA Officer"
        assert letter.recipient_address == "123 Main St"
        assert letter.recipient_email == "foia@agency.gov"
        assert letter.sender_name == "John Doe"
        assert letter.sender_address == "456 Oak Ave"

    def test_letter_with_subject(self):
        """Test letter with subject and reference."""
        letter = Letter(
            id="letter-3",
            title="Complaint Letter",
            letter_type=LetterType.COMPLAINT,
            subject="Service Complaint",
            reference_number="REF-2024-001",
            re_line="Poor Service on 2024-01-15",
        )

        assert letter.subject == "Service Complaint"
        assert letter.reference_number == "REF-2024-001"
        assert letter.re_line == "Poor Service on 2024-01-15"

    def test_letter_timestamps(self):
        """Test letter timestamp fields."""
        now = datetime.utcnow()
        letter = Letter(
            id="letter-4",
            title="Test",
            letter_type=LetterType.CUSTOM,
            created_at=now,
            updated_at=now,
        )

        assert letter.created_at == now
        assert letter.updated_at == now
        assert letter.finalized_at is None
        assert letter.sent_at is None


class TestLetterTemplate:
    """Test LetterTemplate dataclass."""

    def test_template_creation(self):
        """Test creating a template."""
        template = LetterTemplate(
            id="template-1",
            name="FOIA Template",
            letter_type=LetterType.FOIA,
            description="Standard FOIA request template",
            content_template="Dear {{recipient}},\n\nI request {{documents}}.",
        )

        assert template.id == "template-1"
        assert template.name == "FOIA Template"
        assert template.letter_type == LetterType.FOIA
        assert template.description == "Standard FOIA request template"
        assert "{{recipient}}" in template.content_template
        assert "{{documents}}" in template.content_template

    def test_template_with_placeholders(self):
        """Test template with placeholder lists."""
        template = LetterTemplate(
            id="template-2",
            name="Test Template",
            letter_type=LetterType.CUSTOM,
            description="Test",
            content_template="Hello {{name}}",
            placeholders=["name", "date"],
            required_placeholders=["name"],
        )

        assert template.placeholders == ["name", "date"]
        assert template.required_placeholders == ["name"]

    def test_template_with_subject(self):
        """Test template with subject template."""
        template = LetterTemplate(
            id="template-3",
            name="Template with Subject",
            letter_type=LetterType.INQUIRY,
            description="Has subject",
            content_template="Content",
            subject_template="Inquiry - {{case_number}}",
        )

        assert template.subject_template == "Inquiry - {{case_number}}"


class TestPlaceholderValue:
    """Test PlaceholderValue dataclass."""

    def test_placeholder_value(self):
        """Test creating placeholder value."""
        pv = PlaceholderValue(
            key="recipient_name",
            value="John Doe",
            required=True,
        )

        assert pv.key == "recipient_name"
        assert pv.value == "John Doe"
        assert pv.required is True

    def test_placeholder_value_optional(self):
        """Test optional placeholder value."""
        pv = PlaceholderValue(
            key="optional_field",
            value="Some value",
        )

        assert pv.required is False


class TestLetterExportResult:
    """Test LetterExportResult dataclass."""

    def test_export_result_success(self):
        """Test successful export result."""
        result = LetterExportResult(
            letter_id="letter-1",
            success=True,
            export_format=ExportFormat.PDF,
            file_path="/tmp/letter-1.pdf",
            file_size=1024,
            processing_time_ms=150.5,
        )

        assert result.success is True
        assert result.export_format == ExportFormat.PDF
        assert result.file_path == "/tmp/letter-1.pdf"
        assert result.file_size == 1024
        assert result.processing_time_ms == 150.5
        assert result.errors == []
        assert result.warnings == []

    def test_export_result_failure(self):
        """Test failed export result."""
        result = LetterExportResult(
            letter_id="letter-2",
            success=False,
            export_format=ExportFormat.DOCX,
            errors=["File write failed"],
            warnings=["Placeholder not found"],
        )

        assert result.success is False
        assert result.errors == ["File write failed"]
        assert result.warnings == ["Placeholder not found"]


class TestLetterFilter:
    """Test LetterFilter dataclass."""

    def test_filter_by_status(self):
        """Test filter by status."""
        filter = LetterFilter(status=LetterStatus.DRAFT)
        assert filter.status == LetterStatus.DRAFT

    def test_filter_by_type(self):
        """Test filter by letter type."""
        filter = LetterFilter(letter_type=LetterType.FOIA)
        assert filter.letter_type == LetterType.FOIA

    def test_filter_by_search(self):
        """Test filter with search text."""
        filter = LetterFilter(search_text="FOIA request")
        assert filter.search_text == "FOIA request"


class TestLetterStatistics:
    """Test LetterStatistics dataclass."""

    def test_statistics_creation(self):
        """Test creating statistics object."""
        stats = LetterStatistics(
            total_letters=100,
            by_status={"draft": 20, "finalized": 80},
            by_type={"foia": 50, "complaint": 50},
            total_templates=10,
        )

        assert stats.total_letters == 100
        assert stats.by_status["draft"] == 20
        assert stats.by_status["finalized"] == 80
        assert stats.by_type["foia"] == 50
        assert stats.total_templates == 10

    def test_statistics_defaults(self):
        """Test statistics default values."""
        stats = LetterStatistics()

        assert stats.total_letters == 0
        assert stats.by_status == {}
        assert stats.by_type == {}
        assert stats.total_templates == 0
        assert stats.letters_last_24h == 0
        assert stats.total_exports == 0
