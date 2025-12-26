"""Tests for ProvenanceShard class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from arkham_shard_provenance.shard import ProvenanceShard


class MockEventBus:
    """Mock event bus for testing."""

    def __init__(self):
        self.subscriptions = {}
        self.published_events = []

    async def subscribe(self, pattern, handler):
        """Mock subscribe."""
        if pattern not in self.subscriptions:
            self.subscriptions[pattern] = []
        self.subscriptions[pattern].append(handler)

    async def unsubscribe(self, pattern, handler):
        """Mock unsubscribe."""
        if pattern in self.subscriptions:
            self.subscriptions[pattern].remove(handler)

    async def publish(self, event_name, payload):
        """Mock publish."""
        self.published_events.append((event_name, payload))


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.executed_sql = []

    async def execute(self, sql):
        """Mock execute."""
        self.executed_sql.append(sql)


class MockStorage:
    """Mock storage for testing."""

    def __init__(self):
        self.files = {}

    async def save(self, path, content):
        """Mock save."""
        self.files[path] = content

    async def load(self, path):
        """Mock load."""
        return self.files.get(path)


class MockFrame:
    """Mock ArkhamFrame for testing."""

    def __init__(self):
        self.db = MockDatabase()
        self.events = MockEventBus()
        self.storage = MockStorage()

    def get_service(self, name):
        """Mock get_service."""
        if name == "database":
            return self.db
        elif name == "events":
            return self.events
        elif name == "storage":
            return self.storage
        return None


@pytest.fixture
def mock_frame():
    """Fixture providing a mock frame."""
    return MockFrame()


@pytest.fixture
async def initialized_shard(mock_frame):
    """Fixture providing an initialized shard."""
    shard = ProvenanceShard()
    await shard.initialize(mock_frame)
    return shard


class TestShardInitialization:
    """Test shard initialization."""

    def test_shard_creation(self):
        """Test creating a shard instance."""
        shard = ProvenanceShard()

        assert shard.name == "provenance"
        assert shard.version == "0.1.0"
        assert shard.description == "Track evidence chains and data lineage for legal and journalism analysis"
        assert shard._frame is None
        assert shard._db is None
        assert shard._event_bus is None

    @pytest.mark.asyncio
    async def test_initialize_with_services(self, mock_frame):
        """Test initialization with all services."""
        shard = ProvenanceShard()
        await shard.initialize(mock_frame)

        assert shard._frame is mock_frame
        assert shard._db is mock_frame.db
        assert shard._event_bus is mock_frame.events
        assert shard._storage is mock_frame.storage

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame):
        """Test that initialization subscribes to events."""
        shard = ProvenanceShard()
        await shard.initialize(mock_frame)

        # Check event subscriptions
        assert "*.*.created" in mock_frame.events.subscriptions
        assert "*.*.completed" in mock_frame.events.subscriptions
        assert "document.processed" in mock_frame.events.subscriptions

    @pytest.mark.asyncio
    async def test_initialize_without_database(self):
        """Test initialization failure without database."""
        frame = MockFrame()
        frame.db = None

        shard = ProvenanceShard()
        with pytest.raises(RuntimeError, match="Database service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_without_events(self):
        """Test initialization failure without event bus."""
        frame = MockFrame()
        frame.events = None

        shard = ProvenanceShard()
        with pytest.raises(RuntimeError, match="Event bus service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_without_storage(self, mock_frame):
        """Test initialization succeeds without storage (optional)."""
        mock_frame.storage = None

        shard = ProvenanceShard()
        await shard.initialize(mock_frame)

        assert shard._storage is None


class TestShardShutdown:
    """Test shard shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_events(self, initialized_shard, mock_frame):
        """Test that shutdown unsubscribes from events."""
        # Verify subscriptions exist
        assert len(mock_frame.events.subscriptions) > 0

        await initialized_shard.shutdown()

        # After shutdown, subscriptions should be removed
        for pattern in ["*.*.created", "*.*.completed", "document.processed"]:
            if pattern in mock_frame.events.subscriptions:
                assert len(mock_frame.events.subscriptions[pattern]) == 0

    @pytest.mark.asyncio
    async def test_shutdown_clears_managers(self, initialized_shard):
        """Test that shutdown clears component managers."""
        await initialized_shard.shutdown()

        assert initialized_shard._chain_manager is None
        assert initialized_shard._lineage_tracker is None
        assert initialized_shard._audit_logger is None


class TestEventHandlers:
    """Test event handler methods."""

    @pytest.mark.asyncio
    async def test_on_entity_created_handler(self, initialized_shard):
        """Test entity creation event handler."""
        event_data = {
            "entity_id": "ent-123",
            "entity_type": "document",
            "shard_name": "ingest",
        }

        # Should not raise exception
        await initialized_shard._on_entity_created(event_data)

    @pytest.mark.asyncio
    async def test_on_process_completed_handler(self, initialized_shard):
        """Test process completion event handler."""
        event_data = {
            "process_id": "proc-456",
            "process_type": "extraction",
            "result": "success",
        }

        # Should not raise exception
        await initialized_shard._on_process_completed(event_data)

    @pytest.mark.asyncio
    async def test_on_document_processed_handler(self, initialized_shard):
        """Test document processing event handler."""
        event_data = {
            "document_id": "doc-789",
            "status": "processed",
        }

        # Should not raise exception
        await initialized_shard._on_document_processed(event_data)


class TestPublicAPI:
    """Test public API methods."""

    @pytest.mark.asyncio
    async def test_create_chain(self, initialized_shard):
        """Test creating an evidence chain."""
        result = await initialized_shard.create_chain(
            title="Test Chain",
            description="Test description",
            created_by="user-1",
            project_id="proj-1",
        )

        assert "id" in result
        assert result["title"] == "Test Chain"

    @pytest.mark.asyncio
    async def test_add_link(self, initialized_shard):
        """Test adding a link to a chain."""
        result = await initialized_shard.add_link(
            chain_id="chain-1",
            source_id="src-1",
            target_id="tgt-1",
            link_type="derived_from",
            confidence=0.95,
        )

        assert "id" in result
        assert result["chain_id"] == "chain-1"

    @pytest.mark.asyncio
    async def test_get_lineage(self, initialized_shard):
        """Test getting artifact lineage."""
        result = await initialized_shard.get_lineage(
            artifact_id="art-1",
            direction="both",
        )

        assert result["artifact_id"] == "art-1"
        assert "nodes" in result
        assert "edges" in result

    @pytest.mark.asyncio
    async def test_verify_chain(self, initialized_shard):
        """Test verifying chain integrity."""
        result = await initialized_shard.verify_chain(chain_id="chain-1")

        assert result["chain_id"] == "chain-1"
        assert "verified" in result
        assert "issues" in result


class TestRoutes:
    """Test route registration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the API router."""
        shard = ProvenanceShard()
        router = shard.get_routes()

        assert router is not None
        assert hasattr(router, "routes")


class TestSchemaCreation:
    """Test database schema creation."""

    @pytest.mark.asyncio
    async def test_schema_creation_called(self, mock_frame):
        """Test that schema creation is called during initialization."""
        shard = ProvenanceShard()

        # Mock the _create_schema method to track calls
        with patch.object(shard, '_create_schema', new_callable=AsyncMock) as mock_create:
            await shard.initialize(mock_frame)
            mock_create.assert_called_once()


class TestManifestLoading:
    """Test manifest loading."""

    def test_manifest_loaded(self):
        """Test that manifest is loaded from shard.yaml."""
        shard = ProvenanceShard()

        # The manifest should be auto-loaded from shard.yaml
        assert shard.manifest is not None
        assert shard.manifest.name == "provenance"
        assert shard.manifest.version == "0.1.0"
        assert shard.manifest.api_prefix == "/api/provenance"


class TestServiceIntegration:
    """Test integration with frame services."""

    @pytest.mark.asyncio
    async def test_database_service_access(self, initialized_shard, mock_frame):
        """Test accessing database service."""
        assert initialized_shard._db is not None
        assert initialized_shard._db is mock_frame.db

    @pytest.mark.asyncio
    async def test_event_bus_service_access(self, initialized_shard, mock_frame):
        """Test accessing event bus service."""
        assert initialized_shard._event_bus is not None
        assert initialized_shard._event_bus is mock_frame.events

    @pytest.mark.asyncio
    async def test_storage_service_access(self, initialized_shard, mock_frame):
        """Test accessing storage service."""
        assert initialized_shard._storage is not None
        assert initialized_shard._storage is mock_frame.storage


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_initialize_handles_missing_required_service(self):
        """Test that initialization fails gracefully with missing required services."""
        frame = MockFrame()
        frame.db = None

        shard = ProvenanceShard()

        with pytest.raises(RuntimeError):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_shutdown_handles_no_event_bus(self):
        """Test that shutdown handles missing event bus."""
        shard = ProvenanceShard()
        shard._event_bus = None

        # Should not raise exception
        await shard.shutdown()
