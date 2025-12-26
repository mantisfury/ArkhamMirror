"""
Packets Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime

from arkham_shard_packets.models import (
    # Enums
    PacketStatus,
    PacketVisibility,
    ContentType,
    SharePermission,
    ExportFormat,
    # Dataclasses
    Packet,
    PacketContent,
    PacketShare,
    PacketVersion,
    PacketExportResult,
    PacketImportResult,
    PacketStatistics,
    PacketFilter,
)


class TestPacketStatusEnum:
    """Tests for PacketStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert PacketStatus.DRAFT.value == "draft"
        assert PacketStatus.FINALIZED.value == "finalized"
        assert PacketStatus.SHARED.value == "shared"
        assert PacketStatus.ARCHIVED.value == "archived"

    def test_string_inheritance(self):
        """Verify enum values can be used as strings."""
        assert PacketStatus.DRAFT == "draft"
        assert str(PacketStatus.DRAFT) == "draft"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(PacketStatus) == 4


class TestPacketVisibilityEnum:
    """Tests for PacketVisibility enum."""

    def test_all_values_exist(self):
        """Verify all expected visibility values exist."""
        assert PacketVisibility.PRIVATE.value == "private"
        assert PacketVisibility.TEAM.value == "team"
        assert PacketVisibility.PUBLIC.value == "public"

    def test_enum_count(self):
        """Verify total number of visibility levels."""
        assert len(PacketVisibility) == 3


class TestContentTypeEnum:
    """Tests for ContentType enum."""

    def test_all_values_exist(self):
        """Verify all expected content type values exist."""
        assert ContentType.DOCUMENT.value == "document"
        assert ContentType.ENTITY.value == "entity"
        assert ContentType.CLAIM.value == "claim"
        assert ContentType.EVIDENCE_CHAIN.value == "evidence_chain"
        assert ContentType.MATRIX.value == "matrix"
        assert ContentType.TIMELINE.value == "timeline"
        assert ContentType.REPORT.value == "report"

    def test_enum_count(self):
        """Verify total number of content types."""
        assert len(ContentType) == 7


class TestSharePermissionEnum:
    """Tests for SharePermission enum."""

    def test_all_values_exist(self):
        """Verify all expected permission values exist."""
        assert SharePermission.VIEW.value == "view"
        assert SharePermission.COMMENT.value == "comment"
        assert SharePermission.EDIT.value == "edit"

    def test_enum_count(self):
        """Verify total number of permissions."""
        assert len(SharePermission) == 3


class TestExportFormatEnum:
    """Tests for ExportFormat enum."""

    def test_all_values_exist(self):
        """Verify all expected format values exist."""
        assert ExportFormat.ZIP.value == "zip"
        assert ExportFormat.TAR_GZ.value == "tar.gz"
        assert ExportFormat.JSON.value == "json"

    def test_enum_count(self):
        """Verify total number of formats."""
        assert len(ExportFormat) == 3


class TestPacketDataclass:
    """Tests for Packet dataclass."""

    def test_minimal_creation(self):
        """Test creating a packet with minimal required fields."""
        packet = Packet(
            id="test-id",
            name="Test Packet",
        )
        assert packet.id == "test-id"
        assert packet.name == "Test Packet"
        assert packet.status == PacketStatus.DRAFT
        assert packet.visibility == PacketVisibility.PRIVATE
        assert packet.version == 1

    def test_full_creation(self):
        """Test creating a packet with all fields."""
        now = datetime.utcnow()
        packet = Packet(
            id="full-id",
            name="Full Packet",
            description="A complete test packet",
            status=PacketStatus.FINALIZED,
            visibility=PacketVisibility.TEAM,
            created_by="user-123",
            created_at=now,
            updated_at=now,
            version=2,
            contents_count=5,
            size_bytes=1024000,
            checksum="abc123",
            metadata={"project": "test"},
        )
        assert packet.id == "full-id"
        assert packet.status == PacketStatus.FINALIZED
        assert packet.visibility == PacketVisibility.TEAM
        assert packet.version == 2
        assert packet.contents_count == 5
        assert packet.checksum == "abc123"

    def test_default_values(self):
        """Test that default values are set correctly."""
        packet = Packet(id="test", name="test packet")
        assert packet.description == ""
        assert packet.contents_count == 0
        assert packet.size_bytes == 0
        assert packet.metadata == {}
        assert packet.checksum is None


class TestPacketContentDataclass:
    """Tests for PacketContent dataclass."""

    def test_minimal_creation(self):
        """Test creating content with minimal required fields."""
        content = PacketContent(
            id="content-1",
            packet_id="packet-1",
            content_type=ContentType.DOCUMENT,
            content_id="doc-123",
            content_title="Document Title",
        )
        assert content.id == "content-1"
        assert content.packet_id == "packet-1"
        assert content.content_type == ContentType.DOCUMENT
        assert content.added_by == "system"
        assert content.order == 0

    def test_full_creation(self):
        """Test creating content with all fields."""
        now = datetime.utcnow()
        content = PacketContent(
            id="content-full",
            packet_id="packet-1",
            content_type=ContentType.CLAIM,
            content_id="claim-456",
            content_title="Important Claim",
            added_at=now,
            added_by="analyst-1",
            order=5,
        )
        assert content.content_type == ContentType.CLAIM
        assert content.added_by == "analyst-1"
        assert content.order == 5


class TestPacketShareDataclass:
    """Tests for PacketShare dataclass."""

    def test_minimal_creation(self):
        """Test creating share with minimal required fields."""
        share = PacketShare(
            id="share-1",
            packet_id="packet-1",
            shared_with="user-123",
        )
        assert share.id == "share-1"
        assert share.packet_id == "packet-1"
        assert share.shared_with == "user-123"
        assert share.permissions == SharePermission.VIEW
        assert share.expires_at is None

    def test_full_creation(self):
        """Test creating share with all fields."""
        now = datetime.utcnow()
        expires = datetime(2025, 12, 31)
        share = PacketShare(
            id="share-full",
            packet_id="packet-1",
            shared_with="public",
            permissions=SharePermission.COMMENT,
            shared_at=now,
            expires_at=expires,
            access_token="token-abc-123",
        )
        assert share.permissions == SharePermission.COMMENT
        assert share.expires_at == expires
        assert share.access_token == "token-abc-123"


class TestPacketVersionDataclass:
    """Tests for PacketVersion dataclass."""

    def test_creation(self):
        """Test creating a version."""
        version = PacketVersion(
            id="ver-1",
            packet_id="packet-1",
            version_number=2,
            changes_summary="Added new documents",
            snapshot_path="/snapshots/packet-1_v2.json",
        )
        assert version.id == "ver-1"
        assert version.packet_id == "packet-1"
        assert version.version_number == 2
        assert version.changes_summary == "Added new documents"


class TestPacketExportResultDataclass:
    """Tests for PacketExportResult dataclass."""

    def test_successful_export(self):
        """Test creating a successful export result."""
        result = PacketExportResult(
            packet_id="packet-1",
            export_format=ExportFormat.ZIP,
            file_path="/exports/packet-1.zip",
            file_size_bytes=2048000,
            contents_exported=10,
        )
        assert result.packet_id == "packet-1"
        assert result.export_format == ExportFormat.ZIP
        assert result.file_size_bytes == 2048000
        assert result.contents_exported == 10
        assert result.errors == []

    def test_export_with_errors(self):
        """Test export result with errors."""
        result = PacketExportResult(
            packet_id="packet-1",
            export_format=ExportFormat.JSON,
            file_path="",
            file_size_bytes=0,
            errors=["Storage unavailable", "Permission denied"],
        )
        assert len(result.errors) == 2


class TestPacketImportResultDataclass:
    """Tests for PacketImportResult dataclass."""

    def test_successful_import(self):
        """Test creating a successful import result."""
        result = PacketImportResult(
            packet_id="packet-new",
            import_source="/imports/packet.zip",
            contents_imported=15,
            merge_mode="replace",
        )
        assert result.packet_id == "packet-new"
        assert result.contents_imported == 15
        assert result.merge_mode == "replace"
        assert result.errors == []


class TestPacketStatisticsDataclass:
    """Tests for PacketStatistics dataclass."""

    def test_default_values(self):
        """Test default values for statistics."""
        stats = PacketStatistics()
        assert stats.total_packets == 0
        assert stats.by_status == {}
        assert stats.total_contents == 0
        assert stats.total_shares == 0
        assert stats.avg_contents_per_packet == 0.0

    def test_populated_statistics(self):
        """Test statistics with data."""
        stats = PacketStatistics(
            total_packets=50,
            by_status={"draft": 20, "finalized": 25, "shared": 5},
            by_visibility={"private": 30, "team": 15, "public": 5},
            total_contents=250,
            by_content_type={"document": 100, "entity": 80, "claim": 70},
            total_shares=15,
            active_shares=12,
            expired_shares=3,
            total_versions=75,
            avg_contents_per_packet=5.0,
            avg_size_bytes=512000.0,
        )
        assert stats.total_packets == 50
        assert stats.by_status["finalized"] == 25
        assert stats.avg_contents_per_packet == 5.0


class TestPacketFilterDataclass:
    """Tests for PacketFilter dataclass."""

    def test_empty_filter(self):
        """Test empty filter with all None values."""
        filter = PacketFilter()
        assert filter.status is None
        assert filter.visibility is None
        assert filter.created_by is None
        assert filter.search_text is None

    def test_populated_filter(self):
        """Test filter with values."""
        now = datetime.utcnow()
        filter = PacketFilter(
            status=PacketStatus.FINALIZED,
            visibility=PacketVisibility.TEAM,
            created_by="user-123",
            search_text="investigation",
            has_contents=True,
            min_version=2,
            created_after=now,
        )
        assert filter.status == PacketStatus.FINALIZED
        assert filter.visibility == PacketVisibility.TEAM
        assert filter.has_contents is True
        assert filter.min_version == 2
