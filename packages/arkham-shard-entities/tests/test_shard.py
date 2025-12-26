"""Tests for EntitiesShard implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from arkham_shard_entities.shard import EntitiesShard


@pytest.fixture
def mock_frame():
    """Create a mock ArkhamFrame for testing."""
    frame = MagicMock()

    # Mock database service
    frame.db = MagicMock()
    frame.db.execute = AsyncMock()

    # Mock event bus
    frame.events = MagicMock()
    frame.events.subscribe = AsyncMock()
    frame.events.unsubscribe = AsyncMock()
    frame.events.emit = AsyncMock()

    # Mock vectors service (optional)
    frame.vectors = MagicMock()

    # Mock entity service (optional)
    frame.entities = MagicMock()

    # Mock get_service method
    def get_service(name):
        services = {
            "database": frame.db,
            "events": frame.events,
            "vectors": frame.vectors,
            "entities": frame.entities,
        }
        return services.get(name)

    frame.get_service = MagicMock(side_effect=get_service)

    return frame


@pytest.fixture
def shard():
    """Create an EntitiesShard instance."""
    return EntitiesShard()


class TestEntitiesShardInit:
    """Test shard initialization."""

    def test_shard_creation(self, shard):
        """Test basic shard creation."""
        assert shard.name == "entities"
        assert shard.version == "0.1.0"
        assert shard.description == "Entity browser with merge/link/edit capabilities for entity resolution workflow"

    def test_shard_initial_state(self, shard):
        """Test shard initial state before initialization."""
        assert shard._frame is None
        assert shard._db is None
        assert shard._event_bus is None
        assert shard._vectors_service is None
        assert shard._entity_service is None


class TestEntitiesShardInitialization:
    """Test shard initialization with Frame."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, shard, mock_frame):
        """Test successful initialization with all services."""
        await shard.initialize(mock_frame)

        # Check frame reference
        assert shard._frame == mock_frame

        # Check required services
        assert shard._db == mock_frame.db
        assert shard._event_bus == mock_frame.events

        # Check optional services
        assert shard._vectors_service == mock_frame.vectors
        assert shard._entity_service == mock_frame.entities

        # Verify get_service was called
        assert mock_frame.get_service.call_count >= 2

    @pytest.mark.asyncio
    async def test_initialize_without_database_fails(self, shard):
        """Test initialization fails without database service."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)

        with pytest.raises(RuntimeError, match="Database service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_without_optional_services(self, shard, mock_frame):
        """Test initialization succeeds without optional services."""
        # Remove optional services
        mock_frame.vectors = None
        mock_frame.entities = None

        def get_service(name):
            if name == "database":
                return mock_frame.db
            elif name == "events":
                return mock_frame.events
            return None

        mock_frame.get_service = MagicMock(side_effect=get_service)

        await shard.initialize(mock_frame)

        # Should initialize successfully
        assert shard._db == mock_frame.db
        assert shard._vectors_service is None
        assert shard._entity_service is None


class TestEntitiesShardShutdown:
    """Test shard shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_services(self, shard, mock_frame):
        """Test shutdown clears service references."""
        # Initialize first
        await shard.initialize(mock_frame)

        # Verify services are set
        assert shard._db is not None
        assert shard._event_bus is not None

        # Shutdown
        await shard.shutdown()

        # Verify services are cleared
        assert shard._db is None
        assert shard._event_bus is None
        assert shard._vectors_service is None
        assert shard._entity_service is None

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize(self, shard):
        """Test shutdown works even without initialization."""
        # Should not raise error
        await shard.shutdown()

        assert shard._db is None
        assert shard._event_bus is None


class TestEntitiesShardRoutes:
    """Test shard routes."""

    def test_get_routes(self, shard):
        """Test get_routes returns router."""
        router = shard.get_routes()
        assert router is not None
        assert hasattr(router, "prefix")
        assert router.prefix == "/api/entities"


class TestEntitiesShardPublicMethods:
    """Test shard public methods."""

    @pytest.mark.asyncio
    async def test_get_entity_not_initialized(self, shard):
        """Test get_entity fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_entity("test-id")

    @pytest.mark.asyncio
    async def test_get_entity_stub(self, shard, mock_frame):
        """Test get_entity stub implementation."""
        await shard.initialize(mock_frame)

        result = await shard.get_entity("test-id")

        # Stub returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_entity_mentions_not_initialized(self, shard):
        """Test get_entity_mentions fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_entity_mentions("test-id")

    @pytest.mark.asyncio
    async def test_get_entity_mentions_stub(self, shard, mock_frame):
        """Test get_entity_mentions stub implementation."""
        await shard.initialize(mock_frame)

        result = await shard.get_entity_mentions("test-id")

        # Stub returns empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_merge_entities_not_initialized(self, shard):
        """Test merge_entities fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.merge_entities(
                entity_ids=["id1", "id2"],
                canonical_id="id1",
            )

    @pytest.mark.asyncio
    async def test_merge_entities_stub(self, shard, mock_frame):
        """Test merge_entities stub implementation."""
        await shard.initialize(mock_frame)

        result = await shard.merge_entities(
            entity_ids=["id1", "id2"],
            canonical_id="id1",
            canonical_name="John Doe",
        )

        # Stub returns empty dict
        assert result == {}

    @pytest.mark.asyncio
    async def test_create_relationship_not_initialized(self, shard):
        """Test create_relationship fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.create_relationship(
                source_id="person-id",
                target_id="org-id",
                relationship_type="WORKS_FOR",
            )

    @pytest.mark.asyncio
    async def test_create_relationship_stub(self, shard, mock_frame):
        """Test create_relationship stub implementation."""
        await shard.initialize(mock_frame)

        result = await shard.create_relationship(
            source_id="person-id",
            target_id="org-id",
            relationship_type="WORKS_FOR",
            confidence=0.9,
            metadata={"position": "Engineer"},
        )

        # Stub returns empty dict
        assert result == {}

    @pytest.mark.asyncio
    async def test_create_relationship_default_params(self, shard, mock_frame):
        """Test create_relationship with default parameters."""
        await shard.initialize(mock_frame)

        result = await shard.create_relationship(
            source_id="person-id",
            target_id="org-id",
            relationship_type="WORKS_FOR",
        )

        # Should work with minimal params
        assert result == {}


class TestEntitiesShardEventHandlers:
    """Test shard event handlers."""

    @pytest.mark.asyncio
    async def test_on_entity_created_handler(self, shard, mock_frame):
        """Test _on_entity_created event handler."""
        await shard.initialize(mock_frame)

        event_data = {
            "entity_id": "test-id",
            "name": "John Doe",
            "entity_type": "PERSON",
        }

        # Should not raise error (stub implementation)
        await shard._on_entity_created(event_data)

    @pytest.mark.asyncio
    async def test_on_entity_updated_handler(self, shard, mock_frame):
        """Test _on_entity_updated event handler."""
        await shard.initialize(mock_frame)

        event_data = {
            "entity_id": "test-id",
            "changes": {"name": "Jane Doe"},
        }

        # Should not raise error (stub implementation)
        await shard._on_entity_updated(event_data)


class TestEntitiesShardSchema:
    """Test database schema creation."""

    @pytest.mark.asyncio
    async def test_create_schema_called_on_init(self, shard, mock_frame):
        """Test _create_schema is called during initialization."""
        with patch.object(shard, "_create_schema", new_callable=AsyncMock) as mock_create:
            await shard.initialize(mock_frame)
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_schema_stub(self, shard, mock_frame):
        """Test _create_schema stub implementation."""
        await shard.initialize(mock_frame)

        # Should not raise error
        await shard._create_schema()


class TestEntitiesShardManifest:
    """Test shard manifest loading."""

    def test_shard_has_manifest(self, shard):
        """Test shard has manifest loaded."""
        # The manifest is auto-loaded in __init__ via super().__init__()
        assert hasattr(shard, "manifest")
        assert shard.manifest is not None

    def test_manifest_metadata(self, shard):
        """Test manifest has expected metadata."""
        assert shard.name == "entities"
        assert shard.version == "0.1.0"
        assert len(shard.description) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
