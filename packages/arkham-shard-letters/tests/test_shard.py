"""
Tests for Letters Shard - Shard Implementation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from arkham_shard_letters.shard import LettersShard
from arkham_shard_letters.models import (
    ExportFormat,
    Letter,
    LetterStatus,
    LetterTemplate,
    LetterType,
    PlaceholderValue,
)


@pytest.fixture
def mock_frame():
    """Create a mock frame for testing."""
    frame = MagicMock()
    frame.database = AsyncMock()
    frame.events = AsyncMock()
    frame.llm = None
    frame.storage = None
    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create a letters shard instance."""
    shard = LettersShard()
    await shard.initialize(mock_frame)
    return shard


class TestShardInitialization:
    """Test shard initialization."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_frame):
        """Test shard initialization."""
        shard = LettersShard()
        assert shard.name == "letters"
        assert shard.version == "0.1.0"
        assert not shard._initialized

        await shard.initialize(mock_frame)

        assert shard._initialized
        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events

    @pytest.mark.asyncio
    async def test_shutdown(self, shard):
        """Test shard shutdown."""
        assert shard._initialized

        await shard.shutdown()

        assert not shard._initialized

    def test_get_routes(self, shard):
        """Test getting routes."""
        router = shard.get_routes()
        assert router is not None
        assert router.prefix == "/api/letters"


class TestPlaceholderExtraction:
    """Test placeholder extraction from templates."""

    def test_extract_placeholders(self, shard):
        """Test extracting placeholders."""
        template = "Dear {{name}}, I request {{documents}} from {{department}}."
        placeholders = shard._extract_placeholders(template)

        assert "name" in placeholders
        assert "documents" in placeholders
        assert "department" in placeholders
        assert len(placeholders) == 3

    def test_extract_no_placeholders(self, shard):
        """Test template with no placeholders."""
        template = "This is a plain text template."
        placeholders = shard._extract_placeholders(template)

        assert len(placeholders) == 0

    def test_extract_duplicate_placeholders(self, shard):
        """Test template with duplicate placeholders."""
        template = "Hello {{name}}, welcome {{name}}!"
        placeholders = shard._extract_placeholders(template)

        # Should only have one instance
        assert len(placeholders) == 1
        assert "name" in placeholders


class TestTemplateRendering:
    """Test template rendering with placeholders."""

    def test_render_template(self, shard):
        """Test rendering template with placeholders."""
        template = "Dear {{name}}, your request for {{item}} is approved."
        placeholder_map = {
            "name": "John Doe",
            "item": "documents",
        }

        result = shard._render_template(template, placeholder_map)

        assert result == "Dear John Doe, your request for documents is approved."

    def test_render_template_partial(self, shard):
        """Test rendering with partial placeholders."""
        template = "Hello {{name}}, you requested {{item}}."
        placeholder_map = {"name": "Jane"}

        result = shard._render_template(template, placeholder_map)

        # Unfilled placeholder remains
        assert "Hello Jane" in result
        assert "{{item}}" in result

    def test_render_template_empty(self, shard):
        """Test rendering with no placeholder values."""
        template = "Static {{content}} here."
        placeholder_map = {}

        result = shard._render_template(template, placeholder_map)

        assert result == template


class TestLetterCreation:
    """Test letter CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_letter(self, shard, mock_frame):
        """Test creating a letter."""
        # Mock database
        mock_frame.database.execute = AsyncMock()

        letter = await shard.create_letter(
            title="Test Letter",
            letter_type=LetterType.FOIA,
            content="Test content",
        )

        assert letter.title == "Test Letter"
        assert letter.letter_type == LetterType.FOIA
        assert letter.content == "Test content"
        assert letter.status == LetterStatus.DRAFT
        assert letter.id is not None

        # Verify database was called
        assert mock_frame.database.execute.called

        # Verify event was emitted
        assert mock_frame.events.emit.called

    @pytest.mark.asyncio
    async def test_create_letter_with_recipient(self, shard, mock_frame):
        """Test creating letter with recipient."""
        mock_frame.database.execute = AsyncMock()

        letter = await shard.create_letter(
            title="FOIA Request",
            letter_type=LetterType.FOIA,
            recipient_name="FOIA Officer",
            recipient_address="123 Main St",
        )

        assert letter.recipient_name == "FOIA Officer"
        assert letter.recipient_address == "123 Main St"


class TestTemplateCreation:
    """Test template CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_template(self, shard, mock_frame):
        """Test creating a template."""
        mock_frame.database.execute = AsyncMock()

        template = await shard.create_template(
            name="FOIA Template",
            letter_type=LetterType.FOIA,
            description="Standard FOIA request",
            content_template="Dear {{recipient}}, I request {{documents}}.",
        )

        assert template.name == "FOIA Template"
        assert template.letter_type == LetterType.FOIA
        assert template.description == "Standard FOIA request"
        assert "recipient" in template.placeholders
        assert "documents" in template.placeholders
        assert template.id is not None

        # Verify database was called
        assert mock_frame.database.execute.called

        # Verify event was emitted
        assert mock_frame.events.emit.called

    @pytest.mark.asyncio
    async def test_create_template_with_subject(self, shard, mock_frame):
        """Test creating template with subject."""
        mock_frame.database.execute = AsyncMock()

        template = await shard.create_template(
            name="Template with Subject",
            letter_type=LetterType.INQUIRY,
            description="Test",
            content_template="Content {{field}}",
            subject_template="Subject {{field}}",
        )

        # Both content and subject placeholders extracted
        assert "field" in template.placeholders
        assert template.subject_template == "Subject {{field}}"


class TestTemplateApplication:
    """Test applying templates to create letters."""

    @pytest.mark.asyncio
    async def test_apply_template(self, shard, mock_frame):
        """Test applying template to create letter."""
        # Setup mock template
        mock_template = LetterTemplate(
            id="template-1",
            name="Test Template",
            letter_type=LetterType.FOIA,
            description="Test",
            content_template="Dear {{name}}, I request {{item}}.",
            placeholders=["name", "item"],
            required_placeholders=[],
        )

        # Mock get_template
        shard.get_template = AsyncMock(return_value=mock_template)
        mock_frame.database.execute = AsyncMock()

        # Apply template
        placeholder_values = [
            PlaceholderValue(key="name", value="FOIA Officer"),
            PlaceholderValue(key="item", value="documents"),
        ]

        letter = await shard.apply_template(
            template_id="template-1",
            title="My FOIA Request",
            placeholder_values=placeholder_values,
        )

        assert letter.title == "My FOIA Request"
        assert letter.letter_type == LetterType.FOIA
        assert "FOIA Officer" in letter.content
        assert "documents" in letter.content
        assert letter.template_id == "template-1"
        assert letter.metadata["from_template"] == "template-1"

    @pytest.mark.asyncio
    async def test_apply_template_not_found(self, shard):
        """Test applying non-existent template."""
        shard.get_template = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Template .* not found"):
            await shard.apply_template(
                template_id="nonexistent",
                title="Test",
                placeholder_values=[],
            )


class TestLetterExport:
    """Test letter export functionality."""

    @pytest.mark.asyncio
    async def test_export_letter_txt(self, shard, mock_frame):
        """Test exporting letter to TXT format."""
        # Create a test letter
        test_letter = Letter(
            id="letter-1",
            title="Test Letter",
            letter_type=LetterType.CUSTOM,
            content="This is the letter body.",
            sender_name="John Doe",
            sender_address="123 Oak St",
            recipient_name="Jane Smith",
        )

        shard.get_letter = AsyncMock(return_value=test_letter)
        mock_frame.database.execute = AsyncMock()

        result = await shard.export_letter(
            letter_id="letter-1",
            export_format=ExportFormat.TXT,
        )

        assert result.success is True
        assert result.export_format == ExportFormat.TXT
        assert result.file_path is not None
        assert result.file_size > 0
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_export_letter_not_found(self, shard):
        """Test exporting non-existent letter."""
        shard.get_letter = AsyncMock(return_value=None)

        result = await shard.export_letter(
            letter_id="nonexistent",
            export_format=ExportFormat.PDF,
        )

        assert result.success is False
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()


class TestStatistics:
    """Test statistics gathering."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, shard, mock_frame):
        """Test getting statistics."""
        # Mock database responses
        mock_frame.database.fetch_one = AsyncMock(return_value={"count": 42})
        mock_frame.database.fetch_all = AsyncMock(return_value=[])

        stats = await shard.get_statistics()

        assert stats.total_letters == 42
        assert isinstance(stats.by_status, dict)
        assert isinstance(stats.by_type, dict)
