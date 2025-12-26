"""Tests for SettingsShard implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from arkham_shard_settings.shard import SettingsShard


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
    frame.events.publish = AsyncMock()

    # Mock storage service (optional)
    frame.storage = MagicMock()

    # Mock get_service method
    def get_service(name):
        services = {
            "database": frame.db,
            "events": frame.events,
            "storage": frame.storage,
        }
        return services.get(name)

    frame.get_service = MagicMock(side_effect=get_service)

    return frame


@pytest.fixture
def shard():
    """Create a SettingsShard instance."""
    return SettingsShard()


class TestSettingsShardInit:
    """Test shard initialization."""

    def test_shard_creation(self, shard):
        """Test basic shard creation."""
        assert shard.name == "settings"
        assert shard.version == "0.1.0"
        assert "settings" in shard.description.lower()

    def test_shard_initial_state(self, shard):
        """Test shard initial state before initialization."""
        assert shard._frame is None
        assert shard._db is None
        assert shard._event_bus is None
        assert shard._storage is None
        assert shard._settings_cache == {}
        assert shard._profiles_cache == {}


class TestSettingsShardInitialization:
    """Test shard initialization with Frame."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, shard, mock_frame):
        """Test successful initialization with all services."""
        await shard.initialize(mock_frame)

        assert shard._frame == mock_frame
        assert shard._db == mock_frame.db
        assert shard._event_bus == mock_frame.events
        assert shard._storage == mock_frame.storage

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, shard, mock_frame):
        """Test that initialization subscribes to events."""
        await shard.initialize(mock_frame)

        # Verify subscriptions
        assert mock_frame.events.subscribe.call_count >= 2
        calls = [call[0][0] for call in mock_frame.events.subscribe.call_args_list]
        assert "shard.registered" in calls
        assert "shard.unregistered" in calls

    @pytest.mark.asyncio
    async def test_initialize_without_database_fails(self, shard):
        """Test initialization fails without database service."""
        frame = MagicMock()
        frame.get_service = MagicMock(return_value=None)

        with pytest.raises(RuntimeError, match="Database service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_without_events_fails(self, shard):
        """Test initialization fails without events service."""
        frame = MagicMock()
        frame.db = MagicMock()

        def get_service(name):
            if name == "database":
                return frame.db
            return None

        frame.get_service = MagicMock(side_effect=get_service)

        with pytest.raises(RuntimeError, match="Events service required"):
            await shard.initialize(frame)

    @pytest.mark.asyncio
    async def test_initialize_without_optional_storage(self, shard, mock_frame):
        """Test initialization succeeds without optional storage."""
        mock_frame.storage = None

        def get_service(name):
            if name == "database":
                return mock_frame.db
            elif name == "events":
                return mock_frame.events
            return None

        mock_frame.get_service = MagicMock(side_effect=get_service)

        await shard.initialize(mock_frame)

        assert shard._db is not None
        assert shard._storage is None


class TestSettingsShardShutdown:
    """Test shard shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_services(self, shard, mock_frame):
        """Test shutdown clears service references."""
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard._db is None
        assert shard._event_bus is None
        assert shard._storage is None
        assert shard._frame is None

    @pytest.mark.asyncio
    async def test_shutdown_clears_caches(self, shard, mock_frame):
        """Test shutdown clears caches."""
        await shard.initialize(mock_frame)

        # Add something to cache
        shard._settings_cache["test"] = "value"
        shard._profiles_cache["test"] = "value"

        await shard.shutdown()

        assert shard._settings_cache == {}
        assert shard._profiles_cache == {}

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize(self, shard):
        """Test shutdown works even without initialization."""
        await shard.shutdown()
        assert shard._db is None


class TestSettingsShardRoutes:
    """Test shard routes."""

    def test_get_routes(self, shard):
        """Test get_routes returns router."""
        router = shard.get_routes()
        assert router is not None
        assert hasattr(router, "prefix")
        assert router.prefix == "/api/settings"


class TestSettingsPublicMethods:
    """Test shard public methods."""

    @pytest.mark.asyncio
    async def test_get_setting_not_initialized(self, shard):
        """Test get_setting fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.get_setting("theme")

    @pytest.mark.asyncio
    async def test_get_setting_stub(self, shard, mock_frame):
        """Test get_setting stub implementation."""
        await shard.initialize(mock_frame)
        result = await shard.get_setting("theme")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_setting_not_initialized(self, shard):
        """Test update_setting fails if shard not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await shard.update_setting("theme", "dark")

    @pytest.mark.asyncio
    async def test_update_setting_publishes_event(self, shard, mock_frame):
        """Test update_setting publishes event."""
        await shard.initialize(mock_frame)
        await shard.update_setting("theme", "dark")

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.setting.updated"

    @pytest.mark.asyncio
    async def test_reset_setting_publishes_event(self, shard, mock_frame):
        """Test reset_setting publishes event."""
        await shard.initialize(mock_frame)
        await shard.reset_setting("theme")

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.setting.reset"

    @pytest.mark.asyncio
    async def test_get_category_settings_stub(self, shard, mock_frame):
        """Test get_category_settings stub."""
        await shard.initialize(mock_frame)
        result = await shard.get_category_settings("appearance")
        assert result == []

    @pytest.mark.asyncio
    async def test_update_category_settings_publishes_event(self, shard, mock_frame):
        """Test update_category_settings publishes event."""
        await shard.initialize(mock_frame)
        await shard.update_category_settings("appearance", {"theme": "dark"})

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.category.updated"

    @pytest.mark.asyncio
    async def test_validate_setting_always_valid(self, shard, mock_frame):
        """Test validate_setting stub returns valid."""
        await shard.initialize(mock_frame)
        result = await shard.validate_setting("theme", "dark")
        assert result.is_valid is True
        assert result.coerced_value == "dark"


class TestProfileMethods:
    """Test profile management methods."""

    @pytest.mark.asyncio
    async def test_list_profiles_stub(self, shard, mock_frame):
        """Test list_profiles stub."""
        await shard.initialize(mock_frame)
        result = await shard.list_profiles()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_profile_stub(self, shard, mock_frame):
        """Test get_profile stub."""
        await shard.initialize(mock_frame)
        result = await shard.get_profile("profile-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_profile(self, shard, mock_frame):
        """Test create_profile."""
        await shard.initialize(mock_frame)
        result = await shard.create_profile(
            name="Test Profile",
            description="A test profile",
            settings={"theme": "dark"},
        )
        assert result.name == "Test Profile"
        assert result.description == "A test profile"
        assert result.settings == {"theme": "dark"}

    @pytest.mark.asyncio
    async def test_apply_profile_publishes_event(self, shard, mock_frame):
        """Test apply_profile publishes event."""
        await shard.initialize(mock_frame)
        result = await shard.apply_profile("profile-1")
        assert result is True

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.profile.applied"

    @pytest.mark.asyncio
    async def test_delete_profile_stub(self, shard, mock_frame):
        """Test delete_profile stub."""
        await shard.initialize(mock_frame)
        result = await shard.delete_profile("profile-1")
        assert result is True


class TestShardSettingsMethods:
    """Test shard settings methods."""

    @pytest.mark.asyncio
    async def test_get_shard_settings_stub(self, shard, mock_frame):
        """Test get_shard_settings stub."""
        await shard.initialize(mock_frame)
        result = await shard.get_shard_settings("search")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_shard_settings_stub(self, shard, mock_frame):
        """Test update_shard_settings stub."""
        await shard.initialize(mock_frame)
        result = await shard.update_shard_settings("search", {"max_results": 100})
        assert result is None

    @pytest.mark.asyncio
    async def test_reset_shard_settings_stub(self, shard, mock_frame):
        """Test reset_shard_settings stub."""
        await shard.initialize(mock_frame)
        result = await shard.reset_shard_settings("search")
        assert result is True


class TestBackupMethods:
    """Test backup/restore methods."""

    @pytest.mark.asyncio
    async def test_create_backup_without_storage(self, shard, mock_frame):
        """Test create_backup returns None without storage."""
        mock_frame.storage = None

        def get_service(name):
            if name == "database":
                return mock_frame.db
            elif name == "events":
                return mock_frame.events
            return None

        mock_frame.get_service = MagicMock(side_effect=get_service)

        await shard.initialize(mock_frame)
        result = await shard.create_backup("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_backup_publishes_event(self, shard, mock_frame):
        """Test create_backup publishes event when storage available."""
        await shard.initialize(mock_frame)
        await shard.create_backup("test")

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.backup.created"

    @pytest.mark.asyncio
    async def test_list_backups_stub(self, shard, mock_frame):
        """Test list_backups stub."""
        await shard.initialize(mock_frame)
        result = await shard.list_backups()
        assert result == []

    @pytest.mark.asyncio
    async def test_restore_backup_publishes_event(self, shard, mock_frame):
        """Test restore_backup publishes event."""
        await shard.initialize(mock_frame)
        result = await shard.restore_backup("backup-1")
        assert result is True

        mock_frame.events.publish.assert_called()
        call_args = mock_frame.events.publish.call_args[0]
        assert call_args[0] == "settings.backup.restored"

    @pytest.mark.asyncio
    async def test_delete_backup_stub(self, shard, mock_frame):
        """Test delete_backup stub."""
        await shard.initialize(mock_frame)
        result = await shard.delete_backup("backup-1")
        assert result is True


class TestEventHandlers:
    """Test event handlers."""

    @pytest.mark.asyncio
    async def test_on_shard_registered(self, shard, mock_frame):
        """Test _on_shard_registered handler."""
        await shard.initialize(mock_frame)
        await shard._on_shard_registered({"shard_name": "test-shard"})
        # Should not raise error

    @pytest.mark.asyncio
    async def test_on_shard_unregistered(self, shard, mock_frame):
        """Test _on_shard_unregistered handler."""
        await shard.initialize(mock_frame)
        await shard._on_shard_unregistered({"shard_name": "test-shard"})
        # Should not raise error


class TestSchemaCreation:
    """Test database schema creation."""

    @pytest.mark.asyncio
    async def test_create_schema_called_on_init(self, shard, mock_frame):
        """Test _create_schema is called during initialization."""
        with patch.object(shard, "_create_schema", new_callable=AsyncMock) as mock_create:
            await shard.initialize(mock_frame)
            mock_create.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
