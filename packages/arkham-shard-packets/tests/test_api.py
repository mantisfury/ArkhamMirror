"""
Packets Shard - API Tests

Tests for the FastAPI routes.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from arkham_shard_packets.models import (
    Packet,
    PacketContent,
    PacketShare,
    PacketVersion,
    PacketExportResult,
    PacketImportResult,
    PacketStatistics,
    PacketStatus,
    PacketVisibility,
    ContentType,
    SharePermission,
    ExportFormat,
)


@pytest.fixture
def mock_shard():
    """Create a mock PacketsShard."""
    shard = MagicMock()
    shard.name = "packets"
    shard.version = "0.1.0"

    # Mock async methods
    shard.create_packet = AsyncMock()
    shard.get_packet = AsyncMock()
    shard.list_packets = AsyncMock()
    shard.update_packet = AsyncMock()
    shard.finalize_packet = AsyncMock()
    shard.archive_packet = AsyncMock()
    shard.add_content = AsyncMock()
    shard.get_packet_contents = AsyncMock()
    shard.remove_content = AsyncMock()
    shard.share_packet = AsyncMock()
    shard.get_packet_shares = AsyncMock()
    shard.revoke_share = AsyncMock()
    shard.export_packet = AsyncMock()
    shard.import_packet = AsyncMock()
    shard.get_packet_versions = AsyncMock()
    shard._create_version_snapshot = AsyncMock()
    shard.get_statistics = AsyncMock()
    shard.get_count = AsyncMock()

    return shard


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, mock_shard):
        """Test health check returns shard info."""
        from arkham_shard_packets.api import health_check

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await health_check()

            assert response.status == "healthy"
            assert response.shard == "packets"
            assert response.version == "0.1.0"


class TestCountEndpoint:
    """Tests for count endpoint."""

    @pytest.mark.asyncio
    async def test_get_count(self, mock_shard):
        """Test getting packet count."""
        from arkham_shard_packets.api import get_packets_count

        mock_shard.get_count.return_value = 42

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packets_count()

            assert response.count == 42
            mock_shard.get_count.assert_called_once_with(status=None)

    @pytest.mark.asyncio
    async def test_get_count_with_filter(self, mock_shard):
        """Test getting packet count with status filter."""
        from arkham_shard_packets.api import get_packets_count

        mock_shard.get_count.return_value = 15

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packets_count(status="draft")

            assert response.count == 15
            mock_shard.get_count.assert_called_once_with(status="draft")


class TestPacketCRUDEndpoints:
    """Tests for packet CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_packet(self, mock_shard):
        """Test creating a packet."""
        from arkham_shard_packets.api import create_packet, PacketCreate

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Test Packet",
            description="Test",
            created_at=now,
            updated_at=now,
        )
        mock_shard.create_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = PacketCreate(name="Test Packet", description="Test")
            response = await create_packet(request)

            assert response.id == "test-id"
            assert response.name == "Test Packet"

    @pytest.mark.asyncio
    async def test_get_packet_success(self, mock_shard):
        """Test getting an existing packet."""
        from arkham_shard_packets.api import get_packet

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Test Packet",
            created_at=now,
            updated_at=now,
        )
        mock_shard.get_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packet("test-id")

            assert response.id == "test-id"
            assert response.name == "Test Packet"

    @pytest.mark.asyncio
    async def test_get_packet_not_found(self, mock_shard):
        """Test getting a non-existent packet."""
        from arkham_shard_packets.api import get_packet

        mock_shard.get_packet.return_value = None

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            with pytest.raises(HTTPException) as exc_info:
                await get_packet("nonexistent")

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_packets(self, mock_shard):
        """Test listing packets."""
        from arkham_shard_packets.api import list_packets

        now = datetime.utcnow()
        packets = [
            Packet(id="p1", name="Packet 1", created_at=now, updated_at=now),
            Packet(id="p2", name="Packet 2", created_at=now, updated_at=now),
        ]
        mock_shard.list_packets.return_value = packets
        mock_shard.get_count.return_value = 2

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await list_packets()

            assert len(response.packets) == 2
            assert response.total == 2

    @pytest.mark.asyncio
    async def test_update_packet(self, mock_shard):
        """Test updating a packet."""
        from arkham_shard_packets.api import update_packet, PacketUpdate

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Updated Name",
            created_at=now,
            updated_at=now,
        )
        mock_shard.update_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = PacketUpdate(name="Updated Name")
            response = await update_packet("test-id", request)

            assert response.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_packet(self, mock_shard):
        """Test deleting a packet."""
        from arkham_shard_packets.api import delete_packet

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Test",
            status=PacketStatus.ARCHIVED,
            created_at=now,
            updated_at=now,
        )
        mock_shard.archive_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            await delete_packet("test-id")

            mock_shard.archive_packet.assert_called_once_with("test-id")


class TestPacketStatusEndpoints:
    """Tests for packet status endpoints."""

    @pytest.mark.asyncio
    async def test_finalize_packet(self, mock_shard):
        """Test finalizing a packet."""
        from arkham_shard_packets.api import finalize_packet

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Test",
            status=PacketStatus.FINALIZED,
            created_at=now,
            updated_at=now,
        )
        mock_shard.finalize_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await finalize_packet("test-id")

            assert response.status == "finalized"

    @pytest.mark.asyncio
    async def test_archive_packet(self, mock_shard):
        """Test archiving a packet."""
        from arkham_shard_packets.api import archive_packet

        now = datetime.utcnow()
        packet = Packet(
            id="test-id",
            name="Test",
            status=PacketStatus.ARCHIVED,
            created_at=now,
            updated_at=now,
        )
        mock_shard.archive_packet.return_value = packet

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await archive_packet("test-id")

            assert response.status == "archived"


class TestContentEndpoints:
    """Tests for content management endpoints."""

    @pytest.mark.asyncio
    async def test_get_packet_contents(self, mock_shard):
        """Test getting packet contents."""
        from arkham_shard_packets.api import get_packet_contents

        now = datetime.utcnow()
        packet = Packet(id="p1", name="Test", created_at=now, updated_at=now)
        contents = [
            PacketContent(
                id="c1",
                packet_id="p1",
                content_type=ContentType.DOCUMENT,
                content_id="doc-1",
                content_title="Document 1",
                added_at=now,
            ),
        ]
        mock_shard.get_packet.return_value = packet
        mock_shard.get_packet_contents.return_value = contents

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packet_contents("p1")

            assert len(response) == 1
            assert response[0].content_title == "Document 1"

    @pytest.mark.asyncio
    async def test_add_packet_content(self, mock_shard):
        """Test adding content to packet."""
        from arkham_shard_packets.api import add_packet_content, ContentCreate

        now = datetime.utcnow()
        content = PacketContent(
            id="c1",
            packet_id="p1",
            content_type=ContentType.ENTITY,
            content_id="ent-1",
            content_title="Entity 1",
            added_at=now,
        )
        mock_shard.add_content.return_value = content

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = ContentCreate(
                content_type=ContentType.ENTITY,
                content_id="ent-1",
                content_title="Entity 1",
            )
            response = await add_packet_content("p1", request)

            assert response.content_type == "entity"

    @pytest.mark.asyncio
    async def test_remove_packet_content(self, mock_shard):
        """Test removing content from packet."""
        from arkham_shard_packets.api import remove_packet_content

        mock_shard.remove_content.return_value = True

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            await remove_packet_content("p1", "c1")

            mock_shard.remove_content.assert_called_once_with("p1", "c1")


class TestShareEndpoints:
    """Tests for sharing endpoints."""

    @pytest.mark.asyncio
    async def test_share_packet(self, mock_shard):
        """Test sharing a packet."""
        from arkham_shard_packets.api import share_packet, ShareCreate

        now = datetime.utcnow()
        share = PacketShare(
            id="s1",
            packet_id="p1",
            shared_with="user-123",
            permissions=SharePermission.VIEW,
            shared_at=now,
            access_token="token-abc",
        )
        mock_shard.share_packet.return_value = share

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = ShareCreate(shared_with="user-123")
            response = await share_packet("p1", request)

            assert response.shared_with == "user-123"
            assert response.access_token == "token-abc"

    @pytest.mark.asyncio
    async def test_get_packet_shares(self, mock_shard):
        """Test getting packet shares."""
        from arkham_shard_packets.api import get_packet_shares

        now = datetime.utcnow()
        packet = Packet(id="p1", name="Test", created_at=now, updated_at=now)
        shares = [
            PacketShare(
                id="s1",
                packet_id="p1",
                shared_with="user-1",
                shared_at=now,
                access_token="token-1",
            ),
        ]
        mock_shard.get_packet.return_value = packet
        mock_shard.get_packet_shares.return_value = shares

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packet_shares("p1")

            assert len(response) == 1

    @pytest.mark.asyncio
    async def test_revoke_share(self, mock_shard):
        """Test revoking a share."""
        from arkham_shard_packets.api import revoke_share

        mock_shard.revoke_share.return_value = True

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            await revoke_share("p1", "s1")

            mock_shard.revoke_share.assert_called_once_with("s1")


class TestExportImportEndpoints:
    """Tests for export/import endpoints."""

    @pytest.mark.asyncio
    async def test_export_packet(self, mock_shard):
        """Test exporting a packet."""
        from arkham_shard_packets.api import export_packet, ExportRequest

        now = datetime.utcnow()
        result = PacketExportResult(
            packet_id="p1",
            export_format=ExportFormat.ZIP,
            file_path="/exports/p1.zip",
            file_size_bytes=1024,
            exported_at=now,
            contents_exported=5,
        )
        mock_shard.export_packet.return_value = result

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = ExportRequest(format=ExportFormat.ZIP)
            response = await export_packet("p1", request)

            assert response.export_format == "zip"
            assert response.contents_exported == 5

    @pytest.mark.asyncio
    async def test_import_packet(self, mock_shard):
        """Test importing a packet."""
        from arkham_shard_packets.api import import_packet, ImportRequest

        now = datetime.utcnow()
        result = PacketImportResult(
            packet_id="p-new",
            import_source="/imports/packet.zip",
            imported_at=now,
            contents_imported=10,
            merge_mode="replace",
        )
        mock_shard.import_packet.return_value = result

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            request = ImportRequest(file_path="/imports/packet.zip")
            response = await import_packet(request)

            assert response.packet_id == "p-new"
            assert response.contents_imported == 10


class TestVersionEndpoints:
    """Tests for version endpoints."""

    @pytest.mark.asyncio
    async def test_get_packet_versions(self, mock_shard):
        """Test getting packet versions."""
        from arkham_shard_packets.api import get_packet_versions

        now = datetime.utcnow()
        packet = Packet(id="p1", name="Test", created_at=now, updated_at=now)
        versions = [
            PacketVersion(
                id="v1",
                packet_id="p1",
                version_number=1,
                created_at=now,
                changes_summary="Initial version",
                snapshot_path="/snapshots/p1_v1.json",
            ),
        ]
        mock_shard.get_packet.return_value = packet
        mock_shard.get_packet_versions.return_value = versions

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_packet_versions("p1")

            assert len(response) == 1
            assert response[0].version_number == 1


class TestStatisticsEndpoints:
    """Tests for statistics endpoints."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_shard):
        """Test getting packet statistics."""
        from arkham_shard_packets.api import get_statistics

        stats = PacketStatistics(
            total_packets=100,
            by_status={"draft": 40, "finalized": 50, "shared": 10},
            total_contents=500,
            total_shares=25,
            avg_contents_per_packet=5.0,
        )
        mock_shard.get_statistics.return_value = stats

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await get_statistics()

            assert response.total_packets == 100
            assert response.avg_contents_per_packet == 5.0


class TestFilteredListEndpoints:
    """Tests for filtered list endpoints."""

    @pytest.mark.asyncio
    async def test_list_draft_packets(self, mock_shard):
        """Test listing draft packets."""
        from arkham_shard_packets.api import list_draft_packets

        now = datetime.utcnow()
        packets = [
            Packet(
                id="p1",
                name="Draft 1",
                status=PacketStatus.DRAFT,
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_shard.list_packets.return_value = packets
        mock_shard.get_count.return_value = 1

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await list_draft_packets()

            assert len(response.packets) == 1
            assert response.packets[0].status == "draft"

    @pytest.mark.asyncio
    async def test_list_finalized_packets(self, mock_shard):
        """Test listing finalized packets."""
        from arkham_shard_packets.api import list_finalized_packets

        now = datetime.utcnow()
        packets = [
            Packet(
                id="p1",
                name="Final 1",
                status=PacketStatus.FINALIZED,
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_shard.list_packets.return_value = packets
        mock_shard.get_count.return_value = 1

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await list_finalized_packets()

            assert len(response.packets) == 1

    @pytest.mark.asyncio
    async def test_list_shared_packets(self, mock_shard):
        """Test listing shared packets."""
        from arkham_shard_packets.api import list_shared_packets

        now = datetime.utcnow()
        packets = [
            Packet(
                id="p1",
                name="Shared 1",
                status=PacketStatus.SHARED,
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_shard.list_packets.return_value = packets
        mock_shard.get_count.return_value = 1

        with patch('arkham_shard_packets.api._get_shard', return_value=mock_shard):
            response = await list_shared_packets()

            assert len(response.packets) == 1
