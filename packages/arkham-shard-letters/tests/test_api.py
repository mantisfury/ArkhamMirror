"""
Tests for Letters Shard - API Endpoints
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from arkham_shard_letters.api import router
from arkham_shard_letters.models import (
    ExportFormat,
    Letter,
    LetterExportResult,
    LetterStatistics,
    LetterStatus,
    LetterTemplate,
    LetterType,
)


@pytest.fixture
def mock_shard():
    """Create a mock shard for API testing."""
    shard = MagicMock()
    shard.version = "0.1.0"
    shard._db = MagicMock()
    shard._events = MagicMock()
    shard._llm = None
    shard._storage = None
    return shard


@pytest.fixture
def client():
    """Create a test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client, mock_shard):
        """Test GET /api/letters/health."""
        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["version"] == "0.1.0"
            assert "services" in data


class TestCountEndpoint:
    """Test count endpoint."""

    def test_get_count(self, client, mock_shard):
        """Test GET /api/letters/count."""
        mock_shard.get_count = AsyncMock(return_value=42)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/count")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 42

    def test_get_count_filtered(self, client, mock_shard):
        """Test GET /api/letters/count with status filter."""
        mock_shard.get_count = AsyncMock(return_value=10)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/count?status=draft")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 10


class TestLettersCRUD:
    """Test letter CRUD endpoints."""

    def test_list_letters(self, client, mock_shard):
        """Test GET /api/letters/."""
        mock_letter = Letter(
            id="letter-1",
            title="Test Letter",
            letter_type=LetterType.FOIA,
            status=LetterStatus.DRAFT,
            content="Test content",
        )

        mock_shard.list_letters = AsyncMock(return_value=[mock_letter])
        mock_shard.get_count = AsyncMock(return_value=1)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["letters"]) == 1
            assert data["letters"][0]["id"] == "letter-1"
            assert data["letters"][0]["title"] == "Test Letter"

    def test_create_letter(self, client, mock_shard):
        """Test POST /api/letters/."""
        created_letter = Letter(
            id="new-letter",
            title="New Letter",
            letter_type=LetterType.COMPLAINT,
            status=LetterStatus.DRAFT,
            content="New content",
        )

        mock_shard.create_letter = AsyncMock(return_value=created_letter)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/letters/",
                json={
                    "title": "New Letter",
                    "letter_type": "complaint",
                    "content": "New content",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "new-letter"
            assert data["title"] == "New Letter"
            assert data["letter_type"] == "complaint"

    def test_get_letter(self, client, mock_shard):
        """Test GET /api/letters/{id}."""
        mock_letter = Letter(
            id="letter-1",
            title="Test Letter",
            letter_type=LetterType.FOIA,
            status=LetterStatus.DRAFT,
            content="Test content",
        )

        mock_shard.get_letter = AsyncMock(return_value=mock_letter)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/letter-1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "letter-1"
            assert data["title"] == "Test Letter"

    def test_get_letter_not_found(self, client, mock_shard):
        """Test GET /api/letters/{id} with non-existent letter."""
        mock_shard.get_letter = AsyncMock(return_value=None)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/nonexistent")

            assert response.status_code == 404

    def test_update_letter(self, client, mock_shard):
        """Test PUT /api/letters/{id}."""
        updated_letter = Letter(
            id="letter-1",
            title="Updated Title",
            letter_type=LetterType.FOIA,
            status=LetterStatus.REVIEW,
            content="Updated content",
        )

        mock_shard.update_letter = AsyncMock(return_value=updated_letter)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.put(
                "/api/letters/letter-1",
                json={
                    "title": "Updated Title",
                    "status": "review",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Updated Title"
            assert data["status"] == "review"

    def test_delete_letter(self, client, mock_shard):
        """Test DELETE /api/letters/{id}."""
        mock_shard.delete_letter = AsyncMock(return_value=True)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/letters/letter-1")

            assert response.status_code == 204


class TestLetterExport:
    """Test letter export endpoints."""

    def test_export_letter(self, client, mock_shard):
        """Test POST /api/letters/{id}/export."""
        export_result = LetterExportResult(
            letter_id="letter-1",
            success=True,
            export_format=ExportFormat.PDF,
            file_path="/tmp/letter-1.pdf",
            file_size=2048,
            processing_time_ms=123.45,
        )

        mock_shard.export_letter = AsyncMock(return_value=export_result)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/letters/letter-1/export",
                json={"export_format": "pdf"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["export_format"] == "pdf"
            assert data["file_path"] == "/tmp/letter-1.pdf"
            assert data["file_size"] == 2048

    def test_download_letter(self, client, mock_shard):
        """Test GET /api/letters/{id}/download."""
        mock_letter = Letter(
            id="letter-1",
            title="Test",
            letter_type=LetterType.FOIA,
            last_export_path="/tmp/letter-1.pdf",
            last_export_format=ExportFormat.PDF,
        )

        mock_shard.get_letter = AsyncMock(return_value=mock_letter)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/letter-1/download")

            assert response.status_code == 200
            data = response.json()
            assert "file_path" in data


class TestTemplates:
    """Test template endpoints."""

    def test_list_templates(self, client, mock_shard):
        """Test GET /api/letters/templates."""
        mock_template = LetterTemplate(
            id="template-1",
            name="FOIA Template",
            letter_type=LetterType.FOIA,
            description="Standard FOIA request",
            content_template="Dear {{recipient}}",
            placeholders=["recipient"],
            required_placeholders=[],
        )

        mock_shard.list_templates = AsyncMock(return_value=[mock_template])

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/templates")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "template-1"
            assert data[0]["name"] == "FOIA Template"

    def test_create_template(self, client, mock_shard):
        """Test POST /api/letters/templates."""
        created_template = LetterTemplate(
            id="new-template",
            name="New Template",
            letter_type=LetterType.COMPLAINT,
            description="Test template",
            content_template="Template {{field}}",
            placeholders=["field"],
            required_placeholders=[],
        )

        mock_shard.create_template = AsyncMock(return_value=created_template)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/letters/templates",
                json={
                    "name": "New Template",
                    "letter_type": "complaint",
                    "description": "Test template",
                    "content_template": "Template {{field}}",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "new-template"
            assert data["name"] == "New Template"

    def test_get_template(self, client, mock_shard):
        """Test GET /api/letters/templates/{id}."""
        mock_template = LetterTemplate(
            id="template-1",
            name="Test Template",
            letter_type=LetterType.FOIA,
            description="Test",
            content_template="Content",
            placeholders=[],
            required_placeholders=[],
        )

        mock_shard.get_template = AsyncMock(return_value=mock_template)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/templates/template-1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "template-1"


class TestTemplateApplication:
    """Test template application endpoints."""

    def test_apply_template(self, client, mock_shard):
        """Test POST /api/letters/apply-template."""
        created_letter = Letter(
            id="new-letter",
            title="Letter from Template",
            letter_type=LetterType.FOIA,
            status=LetterStatus.DRAFT,
            content="Rendered content",
            template_id="template-1",
        )

        mock_shard.apply_template = AsyncMock(return_value=created_letter)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/letters/apply-template",
                json={
                    "template_id": "template-1",
                    "title": "Letter from Template",
                    "placeholder_values": [
                        {"key": "name", "value": "John Doe"},
                    ],
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "new-letter"
            assert data["template_id"] == "template-1"


class TestStatistics:
    """Test statistics endpoint."""

    def test_get_statistics(self, client, mock_shard):
        """Test GET /api/letters/stats."""
        mock_stats = LetterStatistics(
            total_letters=100,
            by_status={"draft": 20, "finalized": 80},
            by_type={"foia": 50, "complaint": 50},
            total_templates=10,
        )

        mock_shard.get_statistics = AsyncMock(return_value=mock_stats)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_letters"] == 100
            assert data["by_status"]["draft"] == 20
            assert data["total_templates"] == 10


class TestFilteredLists:
    """Test filtered list endpoints."""

    def test_list_drafts(self, client, mock_shard):
        """Test GET /api/letters/drafts."""
        mock_letter = Letter(
            id="draft-1",
            title="Draft Letter",
            letter_type=LetterType.FOIA,
            status=LetterStatus.DRAFT,
        )

        mock_shard.list_letters = AsyncMock(return_value=[mock_letter])
        mock_shard.get_count = AsyncMock(return_value=1)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/drafts")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["letters"]) == 1

    def test_list_finalized(self, client, mock_shard):
        """Test GET /api/letters/finalized."""
        mock_shard.list_letters = AsyncMock(return_value=[])
        mock_shard.get_count = AsyncMock(return_value=0)

        with patch("arkham_shard_letters.api._get_shard", return_value=mock_shard):
            response = client.get("/api/letters/finalized")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
