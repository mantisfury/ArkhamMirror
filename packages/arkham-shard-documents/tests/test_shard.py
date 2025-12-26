"""
Tests for Documents Shard implementation.

Tests shard lifecycle, initialization, and integration with Frame services.

Run with:
    cd packages/arkham-shard-documents
    pytest tests/test_shard.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path

from arkham_shard_documents.shard import DocumentsShard
from arkham_shard_documents.models import DocumentStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_database():
    """Mock database service."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_one = AsyncMock()
    db.fetch_all = AsyncMock()
    return db


@pytest.fixture
def mock_events():
    """Mock event bus service."""
    events = AsyncMock()
    events.publish = AsyncMock()
    events.subscribe = AsyncMock()
    events.unsubscribe = AsyncMock()
    return events


@pytest.fixture
def mock_storage():
    """Mock storage service."""
    storage = AsyncMock()
    storage.read = AsyncMock()
    storage.write = AsyncMock()
    storage.exists = AsyncMock(return_value=True)
    return storage


@pytest.fixture
def mock_document_service():
    """Mock document service."""
    doc_service = AsyncMock()
    doc_service.get = AsyncMock()
    doc_service.list = AsyncMock()
    doc_service.create = AsyncMock()
    doc_service.update = AsyncMock()
    doc_service.delete = AsyncMock()
    return doc_service


@pytest.fixture
def mock_frame(mock_database, mock_events, mock_storage, mock_document_service):
    """Mock ArkhamFrame instance."""
    frame = Mock()
    frame.get_service = Mock(side_effect=lambda name: {
        "database": mock_database,
        "events": mock_events,
        "storage": mock_storage,
        "documents": mock_document_service,
    }.get(name))
    return frame


@pytest_asyncio.fixture
async def shard():
    """Create a fresh DocumentsShard instance."""
    return DocumentsShard()


# =============================================================================
# Shard Metadata Tests
# =============================================================================


class TestShardMetadata:
    """Test shard metadata and manifest loading."""

    def test_shard_name(self, shard):
        """Test shard has correct name."""
        assert shard.name == "documents"

    def test_shard_version(self, shard):
        """Test shard has version."""
        assert shard.version == "0.1.0"

    def test_shard_description(self, shard):
        """Test shard has description."""
        assert shard.description is not None
        assert len(shard.description) > 0
        assert "document" in shard.description.lower()

    def test_shard_manifest_loaded(self, shard):
        """Test shard manifest is loaded."""
        # Manifest should be loaded from shard.yaml
        assert hasattr(shard, "manifest")
        assert shard.manifest is not None

    def test_shard_manifest_name_matches(self, shard):
        """Test manifest name matches shard name."""
        if shard.manifest:
            assert shard.manifest.name == shard.name

    def test_shard_initial_state(self, shard):
        """Test shard starts in uninitialized state."""
        assert shard._frame is None
        assert shard._db is None
        assert shard._events is None
        assert shard._storage is None
        assert shard._document_service is None


# =============================================================================
# Shard Initialization Tests
# =============================================================================


class TestShardInitialization:
    """Test shard initialization with Frame services."""

    @pytest.mark.asyncio
    async def test_initialize_with_all_services(self, shard, mock_frame):
        """Test successful initialization with all services."""
        await shard.initialize(mock_frame)

        # Verify frame is stored
        assert shard._frame is mock_frame

        # Verify services are retrieved
        assert shard._db is not None
        assert shard._events is not None
        assert shard._storage is not None
        assert shard._document_service is not None

    @pytest.mark.asyncio
    async def test_initialize_without_optional_services(self, shard):
        """Test initialization without optional services."""
        frame = Mock()
        frame.get_service = Mock(side_effect=lambda name: {
            "database": AsyncMock(),
            "events": AsyncMock(),
            "storage": None,  # Optional
            "documents": None,  # Optional
        }.get(name))

        await shard.initialize(frame)

        # Required services should be present
        assert shard._db is not None
        assert shard._events is not None

        # Optional services can be None
        assert shard._storage is None
        assert shard._document_service is None

    @pytest.mark.asyncio
    async def test_initialize_fails_without_database(self, shard):
        """Test initialization fails without database service."""
        frame = Mock()
        frame.get_service = Mock(return_value=None)

        with pytest.raises(RuntimeError, match="Database service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_calls_create_schema(self, shard, mock_frame):
        """Test initialization calls schema creation."""
        with patch.object(shard, "_create_schema", new_callable=AsyncMock) as mock_create:
            await shard.initialize(mock_frame)
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_logs_warnings_for_missing_optional(self, shard, caplog):
        """Test initialization logs warnings for missing optional services."""
        frame = Mock()
        frame.get_service = Mock(side_effect=lambda name: {
            "database": AsyncMock(),
            "events": AsyncMock(),
            "storage": None,
            "documents": None,
        }.get(name))

        await shard.initialize(frame)

        # Should log warnings about missing optional services
        assert any("Storage service not available" in record.message for record in caplog.records)
        assert any("Document service not available" in record.message for record in caplog.records)


# =============================================================================
# Shard Shutdown Tests
# =============================================================================


class TestShardShutdown:
    """Test shard shutdown and cleanup."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_references(self, shard, mock_frame):
        """Test shutdown clears service references."""
        # Initialize first
        await shard.initialize(mock_frame)

        # Verify services are set
        assert shard._db is not None
        assert shard._events is not None

        # Shutdown
        await shard.shutdown()

        # Verify references are cleared
        assert shard._db is None
        assert shard._events is None
        assert shard._storage is None
        assert shard._document_service is None

    @pytest.mark.asyncio
    async def test_shutdown_without_initialization(self, shard):
        """Test shutdown can be called without initialization."""
        # Should not raise an error
        await shard.shutdown()

        # References should still be None
        assert shard._db is None
        assert shard._events is None


# =============================================================================
# Route Tests
# =============================================================================


class TestShardRoutes:
    """Test shard route provision."""

    def test_get_routes_returns_router(self, shard):
        """Test get_routes returns a FastAPI router."""
        router = shard.get_routes()

        assert router is not None
        assert hasattr(router, "routes")

    def test_router_has_correct_prefix(self, shard):
        """Test router has correct API prefix."""
        router = shard.get_routes()

        # Check router prefix
        assert router.prefix == "/api/documents"

    def test_router_has_expected_routes(self, shard):
        """Test router has expected endpoints."""
        router = shard.get_routes()

        # Get route paths
        paths = [route.path for route in router.routes]

        # Key endpoints should exist
        assert "/api/documents/health" in paths
        assert "/api/documents/items" in paths
        assert "/api/documents/count" in paths
        assert "/api/documents/stats" in paths


# =============================================================================
# Schema Creation Tests
# =============================================================================


class TestSchemaCreation:
    """Test database schema creation."""

    @pytest.mark.asyncio
    async def test_create_schema_with_database(self, shard, mock_database):
        """Test schema creation when database is available."""
        shard._db = mock_database

        # Should not raise an error
        await shard._create_schema()

        # In current implementation, this is a stub
        # Future implementation would verify DB calls

    @pytest.mark.asyncio
    async def test_create_schema_without_database(self, shard):
        """Test schema creation without database (no-op)."""
        shard._db = None

        # Should not raise an error
        await shard._create_schema()


# =============================================================================
# Event Handler Tests
# =============================================================================


class TestEventHandlers:
    """Test event handler methods."""

    @pytest.mark.asyncio
    async def test_on_document_processed(self, shard, mock_frame):
        """Test document.processed event handler."""
        await shard.initialize(mock_frame)

        event = {
            "document_id": "doc-123",
            "status": "processed",
        }

        # Should not raise an error (currently a stub)
        await shard._on_document_processed(event)

    @pytest.mark.asyncio
    async def test_on_document_deleted(self, shard, mock_frame):
        """Test document.deleted event handler."""
        await shard.initialize(mock_frame)

        event = {
            "document_id": "doc-456",
        }

        # Should not raise an error (currently a stub)
        await shard._on_document_deleted(event)


# =============================================================================
# Public API Tests
# =============================================================================


class TestPublicAPIMethods:
    """Test public API methods that other shards can use."""

    @pytest.mark.asyncio
    async def test_get_document_view_count(self, shard, mock_frame):
        """Test getting document view count."""
        await shard.initialize(mock_frame)

        count = await shard.get_document_view_count("doc-123")

        # Currently returns 0 (stub implementation)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_recently_viewed(self, shard, mock_frame):
        """Test getting recently viewed documents."""
        await shard.initialize(mock_frame)

        recent = await shard.get_recently_viewed(user_id="user-1", limit=5)

        # Currently returns empty list (stub implementation)
        assert isinstance(recent, list)

    @pytest.mark.asyncio
    async def test_get_recently_viewed_without_user(self, shard, mock_frame):
        """Test getting recently viewed documents without user filter."""
        await shard.initialize(mock_frame)

        recent = await shard.get_recently_viewed(limit=10)

        assert isinstance(recent, list)

    @pytest.mark.asyncio
    async def test_mark_document_viewed(self, shard, mock_frame):
        """Test marking a document as viewed."""
        await shard.initialize(mock_frame)

        # Should not raise an error (currently a stub)
        await shard.mark_document_viewed("doc-123", user_id="user-1")

    @pytest.mark.asyncio
    async def test_mark_document_viewed_without_user(self, shard, mock_frame):
        """Test marking a document as viewed without user."""
        await shard.initialize(mock_frame)

        # Should not raise an error
        await shard.mark_document_viewed("doc-123")


# =============================================================================
# Integration Tests
# =============================================================================


class TestShardIntegration:
    """Test shard integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, shard, mock_frame):
        """Test complete shard lifecycle."""
        # Initialize
        await shard.initialize(mock_frame)
        assert shard._frame is not None

        # Get routes
        router = shard.get_routes()
        assert router is not None

        # Call public methods
        count = await shard.get_document_view_count("doc-123")
        assert isinstance(count, int)

        recent = await shard.get_recently_viewed(limit=5)
        assert isinstance(recent, list)

        await shard.mark_document_viewed("doc-123")

        # Shutdown
        await shard.shutdown()
        assert shard._frame is None

    @pytest.mark.asyncio
    async def test_initialize_twice(self, shard, mock_frame):
        """Test initializing shard twice (should handle gracefully)."""
        await shard.initialize(mock_frame)
        first_db = shard._db

        # Initialize again
        await shard.initialize(mock_frame)
        second_db = shard._db

        # Should have replaced references
        assert first_db is second_db

    @pytest.mark.asyncio
    async def test_shutdown_twice(self, shard, mock_frame):
        """Test shutting down shard twice (should handle gracefully)."""
        await shard.initialize(mock_frame)
        await shard.shutdown()

        # Shutdown again should not raise
        await shard.shutdown()

        assert shard._db is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in shard methods."""

    @pytest.mark.asyncio
    async def test_public_methods_before_initialization(self, shard):
        """Test calling public methods before initialization."""
        # These should handle being called before initialization
        # (may return empty results or raise appropriate errors)

        count = await shard.get_document_view_count("doc-123")
        assert count == 0

        recent = await shard.get_recently_viewed()
        assert recent == []

        # mark_document_viewed should not raise
        await shard.mark_document_viewed("doc-123")

    @pytest.mark.asyncio
    async def test_initialization_with_invalid_frame(self, shard):
        """Test initialization with invalid frame object."""
        invalid_frame = Mock()
        invalid_frame.get_service = Mock(return_value=None)

        with pytest.raises(RuntimeError):
            await shard.initialize(invalid_frame)


# =============================================================================
# Manifest Tests
# =============================================================================


class TestManifestLoading:
    """Test shard manifest loading and validation."""

    def test_manifest_exists(self):
        """Test that shard.yaml manifest file exists."""
        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"
        assert manifest_path.exists(), "shard.yaml file not found"

    def test_manifest_can_be_parsed(self):
        """Test that manifest can be parsed as YAML."""
        import yaml

        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"

        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f)

        assert manifest_data is not None
        assert isinstance(manifest_data, dict)

    def test_manifest_required_fields(self):
        """Test that manifest contains required fields."""
        import yaml

        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"

        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        # Required fields
        assert "name" in manifest
        assert "version" in manifest
        assert "description" in manifest
        assert "entry_point" in manifest
        assert "api_prefix" in manifest
        assert "requires_frame" in manifest

        # Verify values
        assert manifest["name"] == "documents"
        assert manifest["entry_point"] == "arkham_shard_documents:DocumentsShard"
        assert manifest["api_prefix"] == "/api/documents"

    def test_manifest_navigation_config(self):
        """Test that manifest has valid navigation configuration."""
        import yaml

        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"

        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        assert "navigation" in manifest
        nav = manifest["navigation"]

        # Required navigation fields
        assert "category" in nav
        assert "order" in nav
        assert "icon" in nav
        assert "label" in nav
        assert "route" in nav

        # Verify category is valid
        assert nav["category"] in ["System", "Data", "Search", "Analysis", "Visualize", "Export"]

        # Verify order is in range
        assert 0 <= nav["order"] <= 99

        # Verify route starts with /
        assert nav["route"].startswith("/")

    def test_manifest_dependencies(self):
        """Test that manifest has valid dependencies."""
        import yaml

        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"

        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        assert "dependencies" in manifest
        deps = manifest["dependencies"]

        # Should have shards key (must be empty)
        assert "shards" in deps
        assert deps["shards"] == []

    def test_manifest_events(self):
        """Test that manifest has event configuration."""
        import yaml

        shard_dir = Path(__file__).parent.parent
        manifest_path = shard_dir / "shard.yaml"

        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        assert "events" in manifest
        events = manifest["events"]

        # Should have publishes and subscribes
        assert "publishes" in events
        assert "subscribes" in events

        # Both should be lists
        assert isinstance(events["publishes"], list)
        assert isinstance(events["subscribes"], list)

        # Published events should follow naming convention
        for event in events["publishes"]:
            assert event.startswith("documents.")
            parts = event.split(".")
            assert len(parts) == 3  # shard.entity.action
