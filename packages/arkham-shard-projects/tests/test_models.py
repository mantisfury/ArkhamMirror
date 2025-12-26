"""
Projects Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime

from arkham_shard_projects.models import (
    # Enums
    ProjectStatus,
    ProjectRole,
    # Dataclasses
    Project,
    ProjectMember,
    ProjectDocument,
    ProjectActivity,
    ProjectStatistics,
    ProjectFilter,
)


class TestProjectStatusEnum:
    """Tests for ProjectStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert ProjectStatus.ACTIVE.value == "active"
        assert ProjectStatus.ARCHIVED.value == "archived"
        assert ProjectStatus.COMPLETED.value == "completed"
        assert ProjectStatus.ON_HOLD.value == "on_hold"

    def test_string_inheritance(self):
        """Verify enum values can be used as strings."""
        assert ProjectStatus.ACTIVE == "active"
        assert str(ProjectStatus.ACTIVE) == "active"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(ProjectStatus) == 4


class TestProjectRoleEnum:
    """Tests for ProjectRole enum."""

    def test_all_values_exist(self):
        """Verify all expected role values exist."""
        assert ProjectRole.OWNER.value == "owner"
        assert ProjectRole.ADMIN.value == "admin"
        assert ProjectRole.EDITOR.value == "editor"
        assert ProjectRole.VIEWER.value == "viewer"

    def test_enum_count(self):
        """Verify total number of roles."""
        assert len(ProjectRole) == 4


class TestProjectDataclass:
    """Tests for Project dataclass."""

    def test_minimal_creation(self):
        """Test creating a project with minimal required fields."""
        project = Project(
            id="proj-1",
            name="Test Project",
        )
        assert project.id == "proj-1"
        assert project.name == "Test Project"
        assert project.status == ProjectStatus.ACTIVE
        assert project.owner_id == "system"

    def test_full_creation(self):
        """Test creating a project with all fields."""
        now = datetime.utcnow()
        project = Project(
            id="proj-full",
            name="Full Project",
            description="A complete project",
            status=ProjectStatus.COMPLETED,
            owner_id="user-1",
            created_at=now,
            updated_at=now,
            settings={"color": "blue"},
            metadata={"category": "research"},
            member_count=5,
            document_count=10,
        )
        assert project.id == "proj-full"
        assert project.status == ProjectStatus.COMPLETED
        assert project.owner_id == "user-1"
        assert project.member_count == 5
        assert project.document_count == 10

    def test_default_values(self):
        """Test that default values are set correctly."""
        project = Project(id="test", name="test")
        assert project.description == ""
        assert project.settings == {}
        assert project.metadata == {}
        assert project.member_count == 0
        assert project.document_count == 0


class TestProjectMemberDataclass:
    """Tests for ProjectMember dataclass."""

    def test_minimal_creation(self):
        """Test creating a member with minimal required fields."""
        member = ProjectMember(
            id="mem-1",
            project_id="proj-1",
            user_id="user-1",
        )
        assert member.id == "mem-1"
        assert member.project_id == "proj-1"
        assert member.user_id == "user-1"
        assert member.role == ProjectRole.VIEWER
        assert member.added_by == "system"

    def test_full_creation(self):
        """Test creating a member with all fields."""
        now = datetime.utcnow()
        member = ProjectMember(
            id="mem-full",
            project_id="proj-1",
            user_id="user-1",
            role=ProjectRole.ADMIN,
            added_at=now,
            added_by="owner-1",
        )
        assert member.role == ProjectRole.ADMIN
        assert member.added_by == "owner-1"


class TestProjectDocumentDataclass:
    """Tests for ProjectDocument dataclass."""

    def test_minimal_creation(self):
        """Test creating a document association with minimal fields."""
        doc = ProjectDocument(
            id="doc-1",
            project_id="proj-1",
            document_id="doc-123",
        )
        assert doc.id == "doc-1"
        assert doc.project_id == "proj-1"
        assert doc.document_id == "doc-123"
        assert doc.added_by == "system"

    def test_full_creation(self):
        """Test creating a document association with all fields."""
        now = datetime.utcnow()
        doc = ProjectDocument(
            id="doc-full",
            project_id="proj-1",
            document_id="doc-123",
            added_at=now,
            added_by="user-1",
        )
        assert doc.added_by == "user-1"


class TestProjectActivityDataclass:
    """Tests for ProjectActivity dataclass."""

    def test_minimal_creation(self):
        """Test creating activity with minimal fields."""
        activity = ProjectActivity(
            id="act-1",
            project_id="proj-1",
            action="created",
            actor_id="user-1",
        )
        assert activity.id == "act-1"
        assert activity.action == "created"
        assert activity.target_type == "project"
        assert activity.details == {}

    def test_full_creation(self):
        """Test creating activity with all fields."""
        now = datetime.utcnow()
        activity = ProjectActivity(
            id="act-full",
            project_id="proj-1",
            action="member_added",
            actor_id="owner-1",
            target_type="member",
            target_id="user-2",
            timestamp=now,
            details={"role": "editor"},
        )
        assert activity.action == "member_added"
        assert activity.target_type == "member"
        assert activity.details["role"] == "editor"


class TestProjectStatisticsDataclass:
    """Tests for ProjectStatistics dataclass."""

    def test_default_values(self):
        """Test default values for statistics."""
        stats = ProjectStatistics()
        assert stats.total_projects == 0
        assert stats.by_status == {}
        assert stats.by_owner == {}
        assert stats.total_members == 0
        assert stats.avg_members_per_project == 0.0

    def test_populated_statistics(self):
        """Test statistics with data."""
        stats = ProjectStatistics(
            total_projects=100,
            by_status={"active": 70, "archived": 30},
            by_owner={"user-1": 50, "user-2": 50},
            total_members=200,
            total_documents=500,
            avg_members_per_project=2.0,
            avg_documents_per_project=5.0,
        )
        assert stats.total_projects == 100
        assert stats.by_status["active"] == 70
        assert stats.avg_members_per_project == 2.0


class TestProjectFilterDataclass:
    """Tests for ProjectFilter dataclass."""

    def test_empty_filter(self):
        """Test empty filter with all None values."""
        filter = ProjectFilter()
        assert filter.status is None
        assert filter.owner_id is None
        assert filter.member_id is None
        assert filter.search_text is None

    def test_populated_filter(self):
        """Test filter with values."""
        now = datetime.utcnow()
        filter = ProjectFilter(
            status=ProjectStatus.ACTIVE,
            owner_id="user-1",
            member_id="user-2",
            has_documents=True,
            search_text="research",
            created_after=now,
        )
        assert filter.status == ProjectStatus.ACTIVE
        assert filter.owner_id == "user-1"
        assert filter.has_documents is True
        assert filter.search_text == "research"
