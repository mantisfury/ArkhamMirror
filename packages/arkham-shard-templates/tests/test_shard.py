"""
Tests for Templates Shard Implementation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from arkham_shard_templates import TemplatesShard
from arkham_shard_templates.models import (
    Template,
    TemplateCreate,
    TemplateType,
    TemplatePlaceholder,
    TemplateRenderRequest,
    OutputFormat,
    PlaceholderDataType,
)


@pytest.fixture
def mock_frame():
    """Create a mock ArkhamFrame."""
    frame = MagicMock()
    frame.get_service = MagicMock(side_effect=lambda name: {
        "database": MagicMock(),
        "events": AsyncMock(),
        "storage": None,  # Optional
    }.get(name))
    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create and initialize a Templates shard."""
    shard = TemplatesShard()
    await shard.initialize(mock_frame)
    return shard


class TestShardInitialization:
    """Test shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_frame):
        """Test successful shard initialization."""
        shard = TemplatesShard()
        await shard.initialize(mock_frame)

        assert shard._frame is not None
        assert shard._db is not None
        assert shard._event_bus is not None
        assert shard._jinja_env is not None

    @pytest.mark.asyncio
    async def test_initialize_missing_database(self):
        """Test initialization fails without database."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)

        shard = TemplatesShard()
        with pytest.raises(RuntimeError, match="Database service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_shutdown(self, shard):
        """Test shard shutdown."""
        await shard.shutdown()

        assert shard._db is None
        assert shard._event_bus is None
        assert shard._frame is None


class TestTemplateCRUD:
    """Test template CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_template(self, shard):
        """Test creating a template."""
        template_data = TemplateCreate(
            name="Test Template",
            template_type=TemplateType.LETTER,
            description="A test template",
            content="Dear {{ name }},\n\nHello!",
            placeholders=[
                TemplatePlaceholder(name="name", required=True)
            ],
        )

        template = await shard.create_template(template_data)

        assert template.name == "Test Template"
        assert template.template_type == TemplateType.LETTER
        assert template.version == 1
        assert template.is_active is True
        assert len(template.placeholders) == 1

    @pytest.mark.asyncio
    async def test_create_template_invalid_syntax(self, shard):
        """Test creating template with invalid Jinja2 syntax."""
        template_data = TemplateCreate(
            name="Invalid Template",
            template_type=TemplateType.REPORT,
            content="Dear {{ name },\n\nMissing closing brace!",
        )

        with pytest.raises(ValueError, match="Invalid template syntax"):
            await shard.create_template(template_data)

    @pytest.mark.asyncio
    async def test_create_template_auto_detect_placeholders(self, shard):
        """Test auto-detection of placeholders."""
        template_data = TemplateCreate(
            name="Auto Detect",
            template_type=TemplateType.LETTER,
            content="Hello {{ name }}, your email is {{ email }}.",
        )

        template = await shard.create_template(template_data)

        # Should have auto-detected placeholders
        assert len(template.placeholders) == 2
        placeholder_names = {p.name for p in template.placeholders}
        assert "name" in placeholder_names
        assert "email" in placeholder_names

    @pytest.mark.asyncio
    async def test_get_template(self, shard):
        """Test getting a template by ID."""
        # Create a template
        template_data = TemplateCreate(
            name="Get Test",
            template_type=TemplateType.REPORT,
            content="Test content",
        )
        created = await shard.create_template(template_data)

        # Get the template
        retrieved = await shard.get_template(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, shard):
        """Test getting non-existent template."""
        result = await shard.get_template("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_templates(self, shard):
        """Test listing templates."""
        # Create multiple templates
        for i in range(5):
            await shard.create_template(TemplateCreate(
                name=f"Template {i}",
                template_type=TemplateType.REPORT,
                content=f"Content {i}",
            ))

        # List templates
        templates, total = await shard.list_templates(page=1, page_size=10)

        assert total == 5
        assert len(templates) == 5

    @pytest.mark.asyncio
    async def test_list_templates_pagination(self, shard):
        """Test template pagination."""
        # Create 10 templates
        for i in range(10):
            await shard.create_template(TemplateCreate(
                name=f"Template {i}",
                template_type=TemplateType.REPORT,
                content=f"Content {i}",
            ))

        # Get page 1
        page1, total = await shard.list_templates(page=1, page_size=3)
        assert len(page1) == 3
        assert total == 10

        # Get page 2
        page2, total = await shard.list_templates(page=2, page_size=3)
        assert len(page2) == 3

        # Ensure different results
        page1_ids = {t.id for t in page1}
        page2_ids = {t.id for t in page2}
        assert page1_ids != page2_ids

    @pytest.mark.asyncio
    async def test_update_template(self, shard):
        """Test updating a template."""
        # Create template
        template_data = TemplateCreate(
            name="Original Name",
            template_type=TemplateType.LETTER,
            content="Original content",
        )
        template = await shard.create_template(template_data)

        # Update template
        from arkham_shard_templates.models import TemplateUpdate
        update_data = TemplateUpdate(
            name="Updated Name",
            description="Updated description",
        )
        updated = await shard.update_template(template.id, update_data)

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_template(self, shard):
        """Test deleting a template."""
        # Create template
        template_data = TemplateCreate(
            name="To Delete",
            template_type=TemplateType.REPORT,
            content="Content",
        )
        template = await shard.create_template(template_data)

        # Delete template
        success = await shard.delete_template(template.id)
        assert success is True

        # Verify deleted
        retrieved = await shard.get_template(template.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_activate_deactivate_template(self, shard):
        """Test activating and deactivating templates."""
        # Create template
        template_data = TemplateCreate(
            name="Active Test",
            template_type=TemplateType.LETTER,
            content="Content",
            is_active=False,
        )
        template = await shard.create_template(template_data)
        assert template.is_active is False

        # Activate
        activated = await shard.activate_template(template.id)
        assert activated.is_active is True

        # Deactivate
        deactivated = await shard.deactivate_template(template.id)
        assert deactivated.is_active is False


class TestTemplateVersioning:
    """Test template versioning."""

    @pytest.mark.asyncio
    async def test_version_created_on_creation(self, shard):
        """Test that initial version is created."""
        template_data = TemplateCreate(
            name="Version Test",
            template_type=TemplateType.REPORT,
            content="Initial content",
        )
        template = await shard.create_template(template_data)

        # Check versions
        versions = await shard.get_versions(template.id)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].changes == "Initial version"

    @pytest.mark.asyncio
    async def test_version_created_on_update(self, shard):
        """Test that version is created on content update."""
        # Create template
        template_data = TemplateCreate(
            name="Version Test",
            template_type=TemplateType.REPORT,
            content="Initial content",
        )
        template = await shard.create_template(template_data)

        # Update content
        from arkham_shard_templates.models import TemplateUpdate
        update_data = TemplateUpdate(content="Updated content")
        await shard.update_template(template.id, update_data, create_version=True)

        # Check versions
        versions = await shard.get_versions(template.id)
        assert len(versions) == 2
        assert versions[0].version_number == 2  # Newest first

    @pytest.mark.asyncio
    async def test_restore_version(self, shard):
        """Test restoring a previous version."""
        # Create template
        template_data = TemplateCreate(
            name="Restore Test",
            template_type=TemplateType.LETTER,
            content="Version 1 content",
        )
        template = await shard.create_template(template_data)
        version1_id = (await shard.get_versions(template.id))[0].id

        # Update to version 2
        from arkham_shard_templates.models import TemplateUpdate
        await shard.update_template(
            template.id,
            TemplateUpdate(content="Version 2 content")
        )

        # Restore version 1
        restored = await shard.restore_version(template.id, version1_id)
        assert restored.content == "Version 1 content"
        assert restored.version == 3  # New version created


class TestTemplateRendering:
    """Test template rendering."""

    @pytest.mark.asyncio
    async def test_render_simple_template(self, shard):
        """Test rendering a simple template."""
        # Create template
        template_data = TemplateCreate(
            name="Render Test",
            template_type=TemplateType.LETTER,
            content="Hello {{ name }}!",
            placeholders=[
                TemplatePlaceholder(name="name", required=True)
            ],
        )
        template = await shard.create_template(template_data)

        # Render template
        request = TemplateRenderRequest(
            data={"name": "World"},
            output_format=OutputFormat.TEXT,
        )
        result = await shard.render_template(template.id, request)

        assert result is not None
        assert "Hello World!" in result.rendered_content
        assert "name" in result.placeholders_used

    @pytest.mark.asyncio
    async def test_render_with_missing_required(self, shard):
        """Test rendering fails with missing required placeholder."""
        # Create template
        template_data = TemplateCreate(
            name="Required Test",
            template_type=TemplateType.LETTER,
            content="Hello {{ name }}!",
            placeholders=[
                TemplatePlaceholder(name="name", required=True)
            ],
        )
        template = await shard.create_template(template_data)

        # Render without required data (strict mode)
        request = TemplateRenderRequest(
            data={},
            strict=True,
        )
        result = await shard.render_template(template.id, request)

        # Should have error warnings
        assert len(result.warnings) > 0
        error_warnings = [w for w in result.warnings if w.severity == "error"]
        assert len(error_warnings) > 0

    @pytest.mark.asyncio
    async def test_render_with_default_values(self, shard):
        """Test rendering applies default values."""
        # Create template with default
        template_data = TemplateCreate(
            name="Default Test",
            template_type=TemplateType.LETTER,
            content="Hello {{ name }}!",
            placeholders=[
                TemplatePlaceholder(
                    name="name",
                    default_value="User",
                    required=False
                )
            ],
        )
        template = await shard.create_template(template_data)

        # Render without providing value
        request = TemplateRenderRequest(data={})
        result = await shard.render_template(template.id, request)

        assert "Hello User!" in result.rendered_content

    @pytest.mark.asyncio
    async def test_preview_template(self, shard):
        """Test previewing a template."""
        # Create template
        template_data = TemplateCreate(
            name="Preview Test",
            template_type=TemplateType.LETTER,
            content="Hello {{ name }}!",
            placeholders=[
                TemplatePlaceholder(
                    name="name",
                    example="Example User"
                )
            ],
        )
        template = await shard.create_template(template_data)

        # Preview template
        result = await shard.preview_template(template.id)

        assert result is not None
        assert "Example User" in result.rendered_content


class TestTemplateStatistics:
    """Test template statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, shard):
        """Test getting template statistics."""
        # Create various templates
        await shard.create_template(TemplateCreate(
            name="Report 1",
            template_type=TemplateType.REPORT,
            content="Content",
        ))
        await shard.create_template(TemplateCreate(
            name="Letter 1",
            template_type=TemplateType.LETTER,
            content="Content",
        ))
        await shard.create_template(TemplateCreate(
            name="Inactive",
            template_type=TemplateType.EXPORT,
            content="Content",
            is_active=False,
        ))

        # Get statistics
        stats = await shard.get_statistics()

        assert stats.total_templates == 3
        assert stats.active_templates == 2
        assert stats.inactive_templates == 1
        assert stats.by_type["REPORT"] == 1
        assert stats.by_type["LETTER"] == 1
        assert stats.by_type["EXPORT"] == 1

    @pytest.mark.asyncio
    async def test_get_count(self, shard):
        """Test getting template count."""
        # Create templates
        await shard.create_template(TemplateCreate(
            name="Active",
            template_type=TemplateType.REPORT,
            content="Content",
            is_active=True,
        ))
        await shard.create_template(TemplateCreate(
            name="Inactive",
            template_type=TemplateType.LETTER,
            content="Content",
            is_active=False,
        ))

        # Get total count
        total = await shard.get_count(active_only=False)
        assert total == 2

        # Get active count
        active = await shard.get_count(active_only=True)
        assert active == 1
