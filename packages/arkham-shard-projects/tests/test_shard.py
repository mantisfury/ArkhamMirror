"""
Projects Shard - Shard Class Tests

Tests for ProjectsShard with mocked Frame services.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from arkham_shard_projects.shard import ProjectsShard
from arkham_shard_projects.models import (
    ProjectStatus,
    ProjectRole,
    ProjectFilter,
)


# === Fixtures ===


@pytest.fixture
def mock_db():
    """Create a mock database service."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_events():
    """Create a mock events service."""
    events = AsyncMock()
    events.emit = AsyncMock()
    events.subscribe = AsyncMock()
    events.unsubscribe = AsyncMock()
    return events


@pytest.fixture
def mock_frame(mock_db, mock_events):
    """Create a mock Frame with all services."""
    frame = MagicMock()
    frame.database = mock_db
    frame.db = mock_db
    frame.events = mock_events
    return frame


@pytest.fixture
async def initialized_shard(mock_frame):
    """Create an initialized ProjectsShard."""
    shard = ProjectsShard()
    await shard.initialize(mock_frame)
    return shard


# === Shard Metadata Tests ===


class TestShardMetadata:
    """Tests for shard metadata and properties."""

    def test_shard_name(self):
        """Verify shard name is correct."""
        shard = ProjectsShard()
        assert shard.name == "projects"

    def test_shard_version(self):
        """Verify shard version is correct."""
        shard = ProjectsShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard description exists."""
        shard = ProjectsShard()
        assert "project" in shard.description.lower()


# === Initialization Tests ===


class TestInitialization:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_with_frame(self, mock_frame):
        """Test shard initializes correctly with frame."""
        shard = ProjectsShard()
        await shard.initialize(mock_frame)

        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events
        assert shard._initialized is True

    @pytest.mark.asyncio
    async def test_schema_creation(self, mock_frame):
        """Test database schema is created on initialization."""
        shard = ProjectsShard()
        await shard.initialize(mock_frame)

        # Verify execute was called for table creation
        assert mock_frame.database.execute.called
        calls = [str(call) for call in mock_frame.database.execute.call_args_list]
        # Check for table creation calls
        assert any("arkham_projects" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_shard, mock_frame):
        """Test shard shuts down correctly."""
        await initialized_shard.shutdown()

        # Verify unsubscribe was called
        assert mock_frame.events.unsubscribe.called
        assert initialized_shard._initialized is False

    @pytest.mark.asyncio
    async def test_get_routes(self, initialized_shard):
        """Test get_routes returns a router."""
        router = initialized_shard.get_routes()
        assert router is not None
        assert hasattr(router, "routes")


# === Project CRUD Tests ===


class TestProjectCRUD:
    """Tests for project create, read, update, delete operations."""

    @pytest.mark.asyncio
    async def test_create_project_minimal(self, initialized_shard, mock_frame):
        """Test creating a project with minimal fields."""
        project = await initialized_shard.create_project(
            name="Test Project",
        )

        assert project is not None
        assert project.name == "Test Project"
        assert project.status == ProjectStatus.ACTIVE

        # Verify event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_create_project_full(self, initialized_shard, mock_frame):
        """Test creating a project with all fields."""
        project = await initialized_shard.create_project(
            name="Full Project",
            description="A complete test project",
            owner_id="user-1",
            status=ProjectStatus.ACTIVE,
            settings={"color": "blue"},
            metadata={"category": "research"},
        )

        assert project.name == "Full Project"
        assert project.owner_id == "user-1"
        assert project.settings["color"] == "blue"

    @pytest.mark.asyncio
    async def test_get_project_found(self, initialized_shard, mock_frame):
        """Test getting an existing project."""
        mock_frame.database.fetch_one.return_value = {
            "id": "proj-1",
            "name": "Test Project",
            "description": "",
            "status": "active",
            "owner_id": "system",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "settings": "{}",
            "metadata": "{}",
            "member_count": 0,
            "document_count": 0,
        }

        project = await initialized_shard.get_project("proj-1")
        assert project is not None
        assert project.id == "proj-1"
        assert project.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, initialized_shard, mock_frame):
        """Test getting a non-existent project."""
        mock_frame.database.fetch_one.return_value = None

        project = await initialized_shard.get_project("nonexistent")
        assert project is None

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, initialized_shard, mock_frame):
        """Test listing projects when none exist."""
        mock_frame.database.fetch_all.return_value = []

        projects = await initialized_shard.list_projects()
        assert projects == []

    @pytest.mark.asyncio
    async def test_update_project(self, initialized_shard, mock_frame):
        """Test updating a project."""
        mock_frame.database.fetch_one.return_value = {
            "id": "proj-1",
            "name": "Old Name",
            "description": "",
            "status": "active",
            "owner_id": "system",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "settings": "{}",
            "metadata": "{}",
            "member_count": 0,
            "document_count": 0,
        }

        project = await initialized_shard.update_project(
            "proj-1",
            name="New Name",
            status=ProjectStatus.COMPLETED,
        )

        assert project is not None
        assert project.name == "New Name"
        assert project.status == ProjectStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_delete_project(self, initialized_shard, mock_frame):
        """Test deleting a project."""
        success = await initialized_shard.delete_project("proj-1")

        assert success is True
        mock_frame.events.emit.assert_called()


# === Document Management Tests ===


class TestDocumentManagement:
    """Tests for document association."""

    @pytest.mark.asyncio
    async def test_add_document(self, initialized_shard, mock_frame):
        """Test adding a document to a project."""
        doc = await initialized_shard.add_document(
            project_id="proj-1",
            document_id="doc-123",
            added_by="user-1",
        )

        assert doc is not None
        assert doc.project_id == "proj-1"
        assert doc.document_id == "doc-123"
        assert doc.added_by == "user-1"

        # Verify event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_remove_document(self, initialized_shard, mock_frame):
        """Test removing a document from a project."""
        success = await initialized_shard.remove_document(
            project_id="proj-1",
            document_id="doc-123",
        )

        assert success is True
        mock_frame.events.emit.assert_called()


# === Member Management Tests ===


class TestMemberManagement:
    """Tests for member management."""

    @pytest.mark.asyncio
    async def test_add_member(self, initialized_shard, mock_frame):
        """Test adding a member to a project."""
        member = await initialized_shard.add_member(
            project_id="proj-1",
            user_id="user-1",
            role=ProjectRole.EDITOR,
            added_by="owner-1",
        )

        assert member is not None
        assert member.project_id == "proj-1"
        assert member.user_id == "user-1"
        assert member.role == ProjectRole.EDITOR

        # Verify event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_remove_member(self, initialized_shard, mock_frame):
        """Test removing a member from a project."""
        success = await initialized_shard.remove_member(
            project_id="proj-1",
            user_id="user-1",
        )

        assert success is True
        mock_frame.events.emit.assert_called()


# === Activity Tests ===


class TestActivity:
    """Tests for activity tracking."""

    @pytest.mark.asyncio
    async def test_get_activity(self, initialized_shard, mock_frame):
        """Test getting activity log."""
        mock_frame.database.fetch_all.return_value = []

        activities = await initialized_shard.get_activity("proj-1")
        assert activities == []


# === Statistics Tests ===


class TestStatistics:
    """Tests for statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, initialized_shard):
        """Test getting project statistics."""
        stats = await initialized_shard.get_statistics()

        assert stats.total_projects == 0

    @pytest.mark.asyncio
    async def test_get_count(self, initialized_shard, mock_frame):
        """Test getting project count."""
        mock_frame.database.fetch_one.return_value = {"count": 42}

        count = await initialized_shard.get_count()
        assert count == 42
