"""
Packets Shard - Shard Tests

Tests for the PacketsShard implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from arkham_shard_packets.shard import PacketsShard
from arkham_shard_packets.models import (
    PacketStatus,
    PacketVisibility,
    ContentType,
    SharePermission,
    ExportFormat,
)


@pytest.fixture
def mock_frame():
    """Create a mock frame with required services."""
    frame = MagicMock()
    frame.database = MagicMock()
    frame.events = MagicMock()
    frame.storage = None

    # Mock database methods
    frame.database.execute = AsyncMock()
    frame.database.fetch_one = AsyncMock(return_value=None)
    frame.database.fetch_all = AsyncMock(return_value=[])

    # Mock event methods
    frame.events.emit = AsyncMock()

    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create and initialize a PacketsShard instance."""
    shard = PacketsShard()
    await shard.initialize(mock_frame)
    return shard


class TestShardMetadata:
    """Tests for shard metadata and properties."""

    def test_shard_name(self):
        """Verify shard name is correct."""
        shard = PacketsShard()
        assert shard.name == "packets"

    def test_shard_version(self):
        """Verify shard version is set."""
        shard = PacketsShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard has description."""
        shard = PacketsShard()
        assert len(shard.description) > 0
        assert "packet" in shard.description.lower()


class TestShardInitialization:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_sets_services(self, mock_frame):
        """Test that initialize sets frame services."""
        shard = PacketsShard()
        await shard.initialize(mock_frame)

        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events
        assert shard._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_creates_schema(self, mock_frame):
        """Test that initialize creates database schema."""
        shard = PacketsShard()
        await shard.initialize(mock_frame)

        # Should have called execute for table creation
        assert mock_frame.database.execute.called

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self, shard):
        """Test that shutdown cleans up properly."""
        await shard.shutdown()
        assert shard._initialized is False

    def test_get_routes_returns_router(self, shard):
        """Test that get_routes returns a router."""
        router = shard.get_routes()
        assert router is not None


class TestPacketCreation:
    """Tests for packet creation."""

    @pytest.mark.asyncio
    async def test_create_packet_minimal(self, shard):
        """Test creating a packet with minimal fields."""
        packet = await shard.create_packet(name="Test Packet")

        assert packet.id is not None
        assert packet.name == "Test Packet"
        assert packet.status == PacketStatus.DRAFT
        assert packet.visibility == PacketVisibility.PRIVATE

    @pytest.mark.asyncio
    async def test_create_packet_full(self, shard):
        """Test creating a packet with all fields."""
        packet = await shard.create_packet(
            name="Full Packet",
            description="Test description",
            created_by="user-123",
            visibility=PacketVisibility.TEAM,
            metadata={"project": "test"},
        )

        assert packet.name == "Full Packet"
        assert packet.description == "Test description"
        assert packet.created_by == "user-123"
        assert packet.visibility == PacketVisibility.TEAM
        assert packet.metadata["project"] == "test"

    @pytest.mark.asyncio
    async def test_create_packet_emits_event(self, shard, mock_frame):
        """Test that creating a packet emits an event."""
        await shard.create_packet(name="Test")

        mock_frame.events.emit.assert_called()
        call_args = mock_frame.events.emit.call_args
        assert call_args[0][0] == "packets.packet.created"


class TestPacketRetrieval:
    """Tests for retrieving packets."""

    @pytest.mark.asyncio
    async def test_get_packet_not_found(self, shard):
        """Test getting a non-existent packet."""
        packet = await shard.get_packet("nonexistent-id")
        assert packet is None

    @pytest.mark.asyncio
    async def test_list_packets_empty(self, shard):
        """Test listing packets when none exist."""
        packets = await shard.list_packets()
        assert packets == []

    @pytest.mark.asyncio
    async def test_get_count_zero(self, shard):
        """Test getting count when no packets exist."""
        count = await shard.get_count()
        assert count == 0


class TestPacketUpdate:
    """Tests for updating packets."""

    @pytest.mark.asyncio
    async def test_update_packet_not_found(self, shard):
        """Test updating a non-existent packet."""
        result = await shard.update_packet("nonexistent", name="New Name")
        assert result is None


class TestPacketStatus:
    """Tests for packet status transitions."""

    @pytest.mark.asyncio
    async def test_finalize_packet_not_found(self, shard):
        """Test finalizing a non-existent packet."""
        result = await shard.finalize_packet("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_archive_packet_not_found(self, shard):
        """Test archiving a non-existent packet."""
        result = await shard.archive_packet("nonexistent")
        assert result is None


class TestPacketContent:
    """Tests for packet content management."""

    @pytest.mark.asyncio
    async def test_add_content_packet_not_found(self, shard):
        """Test adding content to non-existent packet."""
        with pytest.raises(ValueError):
            await shard.add_content(
                packet_id="nonexistent",
                content_type=ContentType.DOCUMENT,
                content_id="doc-1",
                content_title="Test Doc",
            )

    @pytest.mark.asyncio
    async def test_get_packet_contents_empty(self, shard):
        """Test getting contents for packet with none."""
        contents = await shard.get_packet_contents("packet-1")
        assert contents == []

    @pytest.mark.asyncio
    async def test_remove_content_packet_not_found(self, shard):
        """Test removing content from non-existent packet."""
        result = await shard.remove_content("nonexistent", "content-1")
        assert result is False


class TestPacketSharing:
    """Tests for packet sharing."""

    @pytest.mark.asyncio
    async def test_share_packet_not_found(self, shard):
        """Test sharing a non-existent packet."""
        with pytest.raises(ValueError):
            await shard.share_packet(
                packet_id="nonexistent",
                shared_with="user-123",
            )

    @pytest.mark.asyncio
    async def test_get_packet_shares_empty(self, shard):
        """Test getting shares for packet with none."""
        shares = await shard.get_packet_shares("packet-1")
        assert shares == []

    @pytest.mark.asyncio
    async def test_revoke_share(self, shard):
        """Test revoking a share."""
        result = await shard.revoke_share("share-1")
        # Should return True even if not found (delete succeeds)
        assert isinstance(result, bool)


class TestPacketExport:
    """Tests for packet export."""

    @pytest.mark.asyncio
    async def test_export_packet_not_found(self, shard):
        """Test exporting a non-existent packet."""
        with pytest.raises(ValueError):
            await shard.export_packet("nonexistent")

    @pytest.mark.asyncio
    async def test_import_packet(self, shard):
        """Test importing a packet."""
        result = await shard.import_packet("/path/to/file.zip")

        assert result.packet_id is not None
        assert result.import_source == "/path/to/file.zip"


class TestPacketVersions:
    """Tests for packet versioning."""

    @pytest.mark.asyncio
    async def test_get_packet_versions_empty(self, shard):
        """Test getting versions for packet with none."""
        versions = await shard.get_packet_versions("packet-1")
        assert versions == []


class TestStatistics:
    """Tests for statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, shard):
        """Test getting statistics when no packets exist."""
        stats = await shard.get_statistics()

        assert stats.total_packets == 0
        assert stats.total_contents == 0
        assert stats.total_shares == 0


class TestHelperMethods:
    """Tests for private helper methods."""

    @pytest.mark.asyncio
    async def test_save_packet(self, shard):
        """Test saving a packet."""
        from arkham_shard_packets.models import Packet

        packet = Packet(id="test-id", name="Test")
        await shard._save_packet(packet)

        # Should have called database execute
        assert shard._db.execute.called

    @pytest.mark.asyncio
    async def test_update_packet_counts(self, shard):
        """Test updating packet counts."""
        await shard._update_packet_counts("packet-1")

        # Should have called database methods
        assert shard._db.fetch_one.called
