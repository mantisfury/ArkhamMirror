"""
Projects Shard - API Tests

Tests for FastAPI endpoints using TestClient.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_projects.api import router
from arkham_shard_projects.models import (
    Project,
    ProjectMember,
    ProjectDocument,
    ProjectActivity,
    ProjectStatus,
    ProjectRole,
)


# === Test Setup ===


@pytest.fixture
def mock_shard():
    """Create a mock ProjectsShard."""
    shard = MagicMock()
    shard.version = "0.1.0"
    shard.get_count = AsyncMock(return_value=42)
    shard.list_projects = AsyncMock(return_value=[])
    shard.create_project = AsyncMock()
    shard.get_project = AsyncMock(return_value=None)
    shard.update_project = AsyncMock(return_value=None)
    shard.delete_project = AsyncMock(return_value=True)
    shard.add_document = AsyncMock()
    shard.remove_document = AsyncMock(return_value=True)
    shard.add_member = AsyncMock()
    shard.remove_member = AsyncMock(return_value=True)
    shard.get_activity = AsyncMock(return_value=[])
    return shard


@pytest.fixture
def mock_frame(mock_shard):
    """Create a mock Frame that returns the mock shard."""
    frame = MagicMock()
    frame.get_shard = MagicMock(return_value=mock_shard)
    return frame


@pytest.fixture
def app(mock_frame):
    """Create test FastAPI app with mocked dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)

    with patch("arkham_shard_projects.api.get_frame", return_value=mock_frame):
        yield test_app


@pytest.fixture
def client(app, mock_frame):
    """Create test client with patched get_frame."""
    with patch("arkham_shard_projects.api.get_frame", return_value=mock_frame):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project(
        id="proj-1",
        name="Test Project",
        description="A test project",
        status=ProjectStatus.ACTIVE,
        owner_id="user-1",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        settings={"color": "blue"},
        metadata={"category": "research"},
    )


# === Health & Count Endpoint Tests ===


class TestHealthEndpoint:
    """Tests for GET /api/projects/health"""

    def test_health_check(self, client, mock_shard):
        """Test health check endpoint."""
        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestCountEndpoint:
    """Tests for GET /api/projects/count"""

    def test_get_count(self, client, mock_shard):
        """Test getting project count."""
        mock_shard.get_count.return_value = 42

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/count")

        assert response.status_code == 200
        assert response.json()["count"] == 42


# === List Endpoint Tests ===


class TestListEndpoint:
    """Tests for GET /api/projects/"""

    def test_list_projects_empty(self, client, mock_shard):
        """Test listing projects when empty."""
        mock_shard.list_projects.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/")

        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []
        assert data["total"] == 0

    def test_list_projects_with_results(self, client, mock_shard, sample_project):
        """Test listing projects with results."""
        mock_shard.list_projects.return_value = [sample_project]
        mock_shard.get_count.return_value = 1

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["id"] == "proj-1"


# === Create Endpoint Tests ===


class TestCreateEndpoint:
    """Tests for POST /api/projects/"""

    def test_create_project(self, client, mock_shard, sample_project):
        """Test creating a project."""
        mock_shard.create_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/projects/",
                json={
                    "name": "Test Project",
                    "description": "A test project",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"


# === Get Single Project Tests ===


class TestGetProjectEndpoint:
    """Tests for GET /api/projects/{project_id}"""

    def test_get_project_found(self, client, mock_shard, sample_project):
        """Test getting an existing project."""
        mock_shard.get_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/proj-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "proj-1"

    def test_get_project_not_found(self, client, mock_shard):
        """Test getting a non-existent project."""
        mock_shard.get_project.return_value = None

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/nonexistent")

        assert response.status_code == 404


# === Update Endpoint Tests ===


class TestUpdateEndpoint:
    """Tests for PUT /api/projects/{project_id}"""

    def test_update_project(self, client, mock_shard, sample_project):
        """Test updating a project."""
        updated_project = Project(
            id=sample_project.id,
            name="Updated Name",
            description=sample_project.description,
            status=sample_project.status,
            owner_id=sample_project.owner_id,
            created_at=sample_project.created_at,
            updated_at=datetime.utcnow(),
        )
        mock_shard.update_project.return_value = updated_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.put(
                "/api/projects/proj-1",
                json={"name": "Updated Name"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"


# === Delete Endpoint Tests ===


class TestDeleteEndpoint:
    """Tests for DELETE /api/projects/{project_id}"""

    def test_delete_project(self, client, mock_shard):
        """Test deleting a project."""
        mock_shard.delete_project.return_value = True

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/projects/proj-1")

        assert response.status_code == 204


# === Archive/Restore Tests ===


class TestArchiveEndpoints:
    """Tests for archive and restore endpoints."""

    def test_archive_project(self, client, mock_shard, sample_project):
        """Test archiving a project."""
        archived = Project(
            id=sample_project.id,
            name=sample_project.name,
            description=sample_project.description,
            status=ProjectStatus.ARCHIVED,
            owner_id=sample_project.owner_id,
            created_at=sample_project.created_at,
            updated_at=datetime.utcnow(),
        )
        mock_shard.update_project.return_value = archived

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.post("/api/projects/proj-1/archive")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "archived"

    def test_restore_project(self, client, mock_shard, sample_project):
        """Test restoring an archived project."""
        mock_shard.update_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.post("/api/projects/proj-1/restore")

        assert response.status_code == 200


# === Document Endpoint Tests ===


class TestDocumentEndpoints:
    """Tests for document-related endpoints."""

    def test_get_project_documents(self, client, mock_shard, sample_project):
        """Test getting project documents."""
        mock_shard.get_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/proj-1/documents")

        assert response.status_code == 200
        assert response.json() == []

    def test_add_document(self, client, mock_shard, sample_project):
        """Test adding a document to a project."""
        mock_shard.get_project.return_value = sample_project
        doc = ProjectDocument(
            id="doc-1",
            project_id="proj-1",
            document_id="doc-123",
            added_at=datetime.utcnow(),
            added_by="user-1",
        )
        mock_shard.add_document.return_value = doc

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/projects/proj-1/documents",
                json={"document_id": "doc-123", "added_by": "user-1"},
            )

        assert response.status_code == 201


# === Member Endpoint Tests ===


class TestMemberEndpoints:
    """Tests for member-related endpoints."""

    def test_get_project_members(self, client, mock_shard, sample_project):
        """Test getting project members."""
        mock_shard.get_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/proj-1/members")

        assert response.status_code == 200
        assert response.json() == []

    def test_add_member(self, client, mock_shard, sample_project):
        """Test adding a member to a project."""
        mock_shard.get_project.return_value = sample_project
        member = ProjectMember(
            id="mem-1",
            project_id="proj-1",
            user_id="user-2",
            role=ProjectRole.EDITOR,
            added_at=datetime.utcnow(),
        )
        mock_shard.add_member.return_value = member

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/projects/proj-1/members",
                json={"user_id": "user-2", "role": "editor"},
            )

        assert response.status_code == 201


# === Activity Endpoint Tests ===


class TestActivityEndpoint:
    """Tests for GET /api/projects/{project_id}/activity"""

    def test_get_activity(self, client, mock_shard, sample_project):
        """Test getting project activity."""
        mock_shard.get_project.return_value = sample_project

        with patch("arkham_shard_projects.api._get_shard", return_value=mock_shard):
            response = client.get("/api/projects/proj-1/activity")

        assert response.status_code == 200
        assert response.json() == []
