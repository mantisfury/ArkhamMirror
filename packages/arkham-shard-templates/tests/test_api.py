"""
Tests for Templates Shard API Routes
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from arkham_shard_templates import TemplatesShard
from arkham_shard_templates.api import router, set_shard
from arkham_shard_templates.models import (
    Template,
    TemplateCreate,
    TemplateType,
    TemplatePlaceholder,
    TemplateRenderRequest,
    OutputFormat,
)


@pytest.fixture
def mock_frame():
    """Create a mock ArkhamFrame."""
    frame = MagicMock()
    frame.get_service = MagicMock(side_effect=lambda name: {
        "database": MagicMock(),
        "events": AsyncMock(),
        "storage": None,
    }.get(name))
    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create and initialize a Templates shard."""
    shard = TemplatesShard()
    await shard.initialize(mock_frame)
    set_shard(shard)
    return shard


@pytest.fixture
def client(shard):
    """Create a test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and status endpoints."""

    def test_health(self, client):
        """Test health check endpoint."""
        response = client.get("/api/templates/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "templates"

    def test_count(self, client, shard):
        """Test count endpoint."""
        response = client.get("/api/templates/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_stats(self, client):
        """Test statistics endpoint."""
        response = client.get("/api/templates/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_templates" in data
        assert "active_templates" in data
        assert "by_type" in data


class TestTemplateCRUDEndpoints:
    """Test template CRUD endpoints."""

    def test_list_templates_empty(self, client):
        """Test listing templates when none exist."""
        response = client.get("/api/templates/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1

    def test_create_template(self, client):
        """Test creating a template."""
        template_data = {
            "name": "Test Template",
            "template_type": "LETTER",
            "description": "A test template",
            "content": "Dear {{ name }},\n\nHello!",
            "placeholders": [
                {
                    "name": "name",
                    "description": "Recipient name",
                    "data_type": "string",
                    "required": True
                }
            ],
            "is_active": True,
        }
        response = client.post("/api/templates/", json=template_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["template_type"] == "LETTER"
        assert "id" in data

    def test_create_template_invalid_syntax(self, client):
        """Test creating template with invalid syntax."""
        template_data = {
            "name": "Invalid Template",
            "template_type": "REPORT",
            "content": "Dear {{ name },\n\nMissing closing brace!",
        }
        response = client.post("/api/templates/", json=template_data)
        assert response.status_code == 400

    def test_get_template(self, client):
        """Test getting a template by ID."""
        # Create template
        template_data = {
            "name": "Get Test",
            "template_type": "REPORT",
            "content": "Test content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Get template
        response = client.get(f"/api/templates/{template_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == template_id
        assert data["name"] == "Get Test"

    def test_get_template_not_found(self, client):
        """Test getting non-existent template."""
        response = client.get("/api/templates/nonexistent_id")
        assert response.status_code == 404

    def test_update_template(self, client):
        """Test updating a template."""
        # Create template
        template_data = {
            "name": "Original Name",
            "template_type": "LETTER",
            "content": "Original content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Update template
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
        }
        response = client.put(f"/api/templates/{template_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"

    def test_update_template_not_found(self, client):
        """Test updating non-existent template."""
        update_data = {"name": "New Name"}
        response = client.put("/api/templates/nonexistent_id", json=update_data)
        assert response.status_code == 404

    def test_delete_template(self, client):
        """Test deleting a template."""
        # Create template
        template_data = {
            "name": "To Delete",
            "template_type": "REPORT",
            "content": "Content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Delete template
        response = client.delete(f"/api/templates/{template_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

        # Verify deleted
        get_response = client.get(f"/api/templates/{template_id}")
        assert get_response.status_code == 404

    def test_activate_template(self, client):
        """Test activating a template."""
        # Create inactive template
        template_data = {
            "name": "Inactive",
            "template_type": "LETTER",
            "content": "Content",
            "is_active": False,
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Activate
        response = client.post(f"/api/templates/{template_id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_deactivate_template(self, client):
        """Test deactivating a template."""
        # Create active template
        template_data = {
            "name": "Active",
            "template_type": "LETTER",
            "content": "Content",
            "is_active": True,
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Deactivate
        response = client.post(f"/api/templates/{template_id}/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False


class TestVersioningEndpoints:
    """Test versioning endpoints."""

    def test_get_versions(self, client):
        """Test getting template versions."""
        # Create template
        template_data = {
            "name": "Version Test",
            "template_type": "REPORT",
            "content": "Initial content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Get versions
        response = client.get(f"/api/templates/{template_id}/versions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["version_number"] == 1

    def test_create_version(self, client):
        """Test creating a new version."""
        # Create template
        template_data = {
            "name": "Version Test",
            "template_type": "REPORT",
            "content": "Initial content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Create version
        version_data = {"changes": "Updated for testing"}
        response = client.post(
            f"/api/templates/{template_id}/versions",
            json=version_data
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version_number"] == 2
        assert data["changes"] == "Updated for testing"

    def test_restore_version(self, client):
        """Test restoring a previous version."""
        # Create template
        template_data = {
            "name": "Restore Test",
            "template_type": "LETTER",
            "content": "Version 1 content",
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Get version 1 ID
        versions_response = client.get(f"/api/templates/{template_id}/versions")
        version1_id = versions_response.json()[0]["id"]

        # Update to version 2
        update_data = {"content": "Version 2 content"}
        client.put(f"/api/templates/{template_id}", json=update_data)

        # Restore version 1
        response = client.post(
            f"/api/templates/{template_id}/restore/{version1_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Version 1 content"


class TestRenderingEndpoints:
    """Test rendering endpoints."""

    def test_render_template(self, client):
        """Test rendering a template."""
        # Create template
        template_data = {
            "name": "Render Test",
            "template_type": "LETTER",
            "content": "Hello {{ name }}!",
            "placeholders": [
                {"name": "name", "required": True}
            ],
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Render template
        render_data = {
            "data": {"name": "World"},
            "output_format": "text",
        }
        response = client.post(
            f"/api/templates/{template_id}/render",
            json=render_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "Hello World!" in data["rendered_content"]
        assert "name" in data["placeholders_used"]

    def test_render_template_not_found(self, client):
        """Test rendering non-existent template."""
        render_data = {
            "data": {"name": "Test"},
            "output_format": "text",
        }
        response = client.post(
            "/api/templates/nonexistent_id/render",
            json=render_data
        )
        assert response.status_code == 404

    def test_preview_template(self, client):
        """Test previewing a template."""
        # Create template
        template_data = {
            "name": "Preview Test",
            "template_type": "LETTER",
            "content": "Hello {{ name }}!",
            "placeholders": [
                {
                    "name": "name",
                    "example": "Example User"
                }
            ],
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Preview template
        response = client.post(f"/api/templates/{template_id}/preview")
        assert response.status_code == 200
        data = response.json()
        assert "Example User" in data["rendered_content"]

    def test_validate_template_data(self, client):
        """Test validating placeholder data."""
        # Create template
        template_data = {
            "name": "Validate Test",
            "template_type": "LETTER",
            "content": "Hello {{ name }}!",
            "placeholders": [
                {"name": "name", "required": True}
            ],
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Validate with missing required field
        validation_data = {}
        response = client.post(
            f"/api/templates/{template_id}/validate",
            json=validation_data
        )
        assert response.status_code == 200
        warnings = response.json()
        assert len(warnings) > 0
        assert any("required" in w["message"].lower() for w in warnings)


class TestMetadataEndpoints:
    """Test metadata endpoints."""

    def test_get_template_types(self, client):
        """Test getting template types."""
        response = client.get("/api/templates/types")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert any(t["type"] == "REPORT" for t in data)
        assert any(t["type"] == "LETTER" for t in data)

    def test_get_template_placeholders(self, client):
        """Test getting template placeholders."""
        # Create template
        template_data = {
            "name": "Placeholder Test",
            "template_type": "LETTER",
            "content": "Hello {{ name }}!",
            "placeholders": [
                {
                    "name": "name",
                    "description": "Recipient name",
                    "data_type": "string",
                    "required": True
                }
            ],
        }
        create_response = client.post("/api/templates/", json=template_data)
        template_id = create_response.json()["id"]

        # Get placeholders
        response = client.get(f"/api/templates/{template_id}/placeholders")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "name"
        assert data[0]["required"] is True


class TestBulkActions:
    """Test bulk action endpoints."""

    def test_bulk_activate(self, client):
        """Test bulk activating templates."""
        # Create inactive templates
        template_ids = []
        for i in range(3):
            template_data = {
                "name": f"Template {i}",
                "template_type": "REPORT",
                "content": "Content",
                "is_active": False,
            }
            response = client.post("/api/templates/", json=template_data)
            template_ids.append(response.json()["id"])

        # Bulk activate
        bulk_data = {"template_ids": template_ids}
        response = client.post("/api/templates/batch/activate", json=bulk_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed"] == 3
        assert data["failed"] == 0

    def test_bulk_deactivate(self, client):
        """Test bulk deactivating templates."""
        # Create active templates
        template_ids = []
        for i in range(3):
            template_data = {
                "name": f"Template {i}",
                "template_type": "REPORT",
                "content": "Content",
                "is_active": True,
            }
            response = client.post("/api/templates/", json=template_data)
            template_ids.append(response.json()["id"])

        # Bulk deactivate
        bulk_data = {"template_ids": template_ids}
        response = client.post("/api/templates/batch/deactivate", json=bulk_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed"] == 3

    def test_bulk_delete(self, client):
        """Test bulk deleting templates."""
        # Create templates
        template_ids = []
        for i in range(3):
            template_data = {
                "name": f"Template {i}",
                "template_type": "REPORT",
                "content": "Content",
            }
            response = client.post("/api/templates/", json=template_data)
            template_ids.append(response.json()["id"])

        # Bulk delete
        bulk_data = {"template_ids": template_ids}
        response = client.post("/api/templates/batch/delete", json=bulk_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed"] == 3

        # Verify deleted
        for template_id in template_ids:
            get_response = client.get(f"/api/templates/{template_id}")
            assert get_response.status_code == 404


class TestPaginationAndFiltering:
    """Test pagination and filtering."""

    def test_pagination(self, client):
        """Test template pagination."""
        # Create 10 templates
        for i in range(10):
            template_data = {
                "name": f"Template {i}",
                "template_type": "REPORT",
                "content": f"Content {i}",
            }
            client.post("/api/templates/", json=template_data)

        # Get page 1
        response = client.get("/api/templates/?page=1&page_size=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10
        assert data["page"] == 1

        # Get page 2
        response = client.get("/api/templates/?page=2&page_size=3")
        data = response.json()
        assert len(data["items"]) == 3
        assert data["page"] == 2

    def test_filter_by_type(self, client):
        """Test filtering by template type."""
        # Create templates of different types
        client.post("/api/templates/", json={
            "name": "Report 1",
            "template_type": "REPORT",
            "content": "Content",
        })
        client.post("/api/templates/", json={
            "name": "Letter 1",
            "template_type": "LETTER",
            "content": "Content",
        })

        # Filter by REPORT
        response = client.get("/api/templates/?template_type=REPORT")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["template_type"] == "REPORT"

    def test_filter_by_active_status(self, client):
        """Test filtering by active status."""
        # Create active and inactive templates
        client.post("/api/templates/", json={
            "name": "Active",
            "template_type": "REPORT",
            "content": "Content",
            "is_active": True,
        })
        client.post("/api/templates/", json={
            "name": "Inactive",
            "template_type": "REPORT",
            "content": "Content",
            "is_active": False,
        })

        # Filter by active
        response = client.get("/api/templates/?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["is_active"] is True

    def test_search_by_name(self, client):
        """Test searching by name."""
        # Create templates
        client.post("/api/templates/", json={
            "name": "FOIA Request Letter",
            "template_type": "LETTER",
            "content": "Content",
        })
        client.post("/api/templates/", json={
            "name": "Report Template",
            "template_type": "REPORT",
            "content": "Content",
        })

        # Search for "FOIA"
        response = client.get("/api/templates/?name_contains=FOIA")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "FOIA" in data["items"][0]["name"]
