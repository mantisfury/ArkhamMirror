"""
Tests for Templates Shard Models
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from arkham_shard_templates.models import (
    Template,
    TemplateCreate,
    TemplateType,
    TemplatePlaceholder,
    PlaceholderDataType,
    TemplateRenderRequest,
    OutputFormat,
    TemplateStatistics,
)


class TestTemplatePlaceholder:
    """Test TemplatePlaceholder model."""

    def test_create_placeholder(self):
        """Test creating a valid placeholder."""
        placeholder = TemplatePlaceholder(
            name="recipient_name",
            description="Name of the recipient",
            data_type=PlaceholderDataType.STRING,
            required=True,
        )
        assert placeholder.name == "recipient_name"
        assert placeholder.data_type == PlaceholderDataType.STRING
        assert placeholder.required is True

    def test_placeholder_name_validation(self):
        """Test placeholder name validation."""
        # Valid names
        valid_names = ["name", "first_name", "email_address", "value123"]
        for name in valid_names:
            placeholder = TemplatePlaceholder(name=name)
            assert placeholder.name == name

        # Invalid names (should raise ValidationError)
        invalid_names = ["first-name", "email.address", "name with spaces", "name!"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                TemplatePlaceholder(name=name)

    def test_placeholder_defaults(self):
        """Test placeholder default values."""
        placeholder = TemplatePlaceholder(name="test")
        assert placeholder.description == ""
        assert placeholder.data_type == PlaceholderDataType.STRING
        assert placeholder.default_value is None
        assert placeholder.required is False
        assert placeholder.example is None


class TestTemplate:
    """Test Template model."""

    def test_create_template(self):
        """Test creating a valid template."""
        template = Template(
            id="tpl_abc123",
            name="Test Template",
            template_type=TemplateType.LETTER,
            description="A test template",
            content="Dear {{ name }},\n\nHello!",
            placeholders=[
                TemplatePlaceholder(name="name", required=True)
            ],
        )
        assert template.id == "tpl_abc123"
        assert template.name == "Test Template"
        assert template.template_type == TemplateType.LETTER
        assert template.version == 1
        assert template.is_active is True
        assert len(template.placeholders) == 1

    def test_template_defaults(self):
        """Test template default values."""
        template = Template(
            id="tpl_test",
            name="Test",
            template_type=TemplateType.CUSTOM,
            content="Content",
        )
        assert template.description == ""
        assert template.placeholders == []
        assert template.version == 1
        assert template.is_active is True
        assert template.metadata == {}
        assert isinstance(template.created_at, datetime)
        assert isinstance(template.updated_at, datetime)

    def test_template_name_length(self):
        """Test template name length validation."""
        # Empty name should fail
        with pytest.raises(ValidationError):
            Template(
                id="tpl_test",
                name="",
                template_type=TemplateType.REPORT,
                content="Content",
            )

        # Name too long should fail (>255 chars)
        with pytest.raises(ValidationError):
            Template(
                id="tpl_test",
                name="x" * 256,
                template_type=TemplateType.REPORT,
                content="Content",
            )


class TestTemplateCreate:
    """Test TemplateCreate model."""

    def test_create_template_request(self):
        """Test creating a template creation request."""
        request = TemplateCreate(
            name="FOIA Request",
            template_type=TemplateType.LETTER,
            description="Template for FOIA requests",
            content="Dear {{ agency }},\n\nI request {{ records }}.",
            placeholders=[
                TemplatePlaceholder(name="agency", required=True),
                TemplatePlaceholder(name="records", required=True),
            ],
        )
        assert request.name == "FOIA Request"
        assert request.template_type == TemplateType.LETTER
        assert len(request.placeholders) == 2

    def test_create_template_defaults(self):
        """Test TemplateCreate default values."""
        request = TemplateCreate(
            name="Test",
            template_type=TemplateType.REPORT,
            content="Content",
        )
        assert request.description == ""
        assert request.placeholders == []
        assert request.is_active is True
        assert request.metadata == {}


class TestTemplateRenderRequest:
    """Test TemplateRenderRequest model."""

    def test_render_request(self):
        """Test creating a render request."""
        request = TemplateRenderRequest(
            data={"name": "John", "age": 30},
            output_format=OutputFormat.HTML,
            strict=True,
        )
        assert request.data == {"name": "John", "age": 30}
        assert request.output_format == OutputFormat.HTML
        assert request.strict is True

    def test_render_request_defaults(self):
        """Test render request default values."""
        request = TemplateRenderRequest()
        assert request.data == {}
        assert request.output_format == OutputFormat.TEXT
        assert request.strict is True


class TestTemplateStatistics:
    """Test TemplateStatistics model."""

    def test_statistics_creation(self):
        """Test creating statistics."""
        stats = TemplateStatistics(
            total_templates=25,
            active_templates=20,
            inactive_templates=5,
            by_type={"REPORT": 10, "LETTER": 8, "EXPORT": 7},
            total_versions=50,
            total_renders=200,
        )
        assert stats.total_templates == 25
        assert stats.active_templates == 20
        assert stats.inactive_templates == 5
        assert stats.by_type["REPORT"] == 10
        assert stats.total_versions == 50
        assert stats.total_renders == 200

    def test_statistics_defaults(self):
        """Test statistics default values."""
        stats = TemplateStatistics()
        assert stats.total_templates == 0
        assert stats.active_templates == 0
        assert stats.inactive_templates == 0
        assert stats.by_type == {}
        assert stats.total_versions == 0
        assert stats.total_renders == 0
        assert stats.recent_templates == []


class TestTemplateTypes:
    """Test template type enumeration."""

    def test_all_types_exist(self):
        """Test that all expected types exist."""
        expected_types = {"REPORT", "LETTER", "EXPORT", "EMAIL", "CUSTOM"}
        actual_types = {t.value for t in TemplateType}
        assert actual_types == expected_types

    def test_type_values(self):
        """Test template type values."""
        assert TemplateType.REPORT.value == "REPORT"
        assert TemplateType.LETTER.value == "LETTER"
        assert TemplateType.EXPORT.value == "EXPORT"
        assert TemplateType.EMAIL.value == "EMAIL"
        assert TemplateType.CUSTOM.value == "CUSTOM"
