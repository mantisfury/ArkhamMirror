"""
Settings Shard - Main Implementation

Provides centralized settings management for ArkhamFrame.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from arkham_frame import ArkhamShard

from .models import (
    Setting,
    SettingCategory,
    SettingsBackup,
    SettingsProfile,
    SettingsValidationResult,
    ShardSettings,
)

logger = logging.getLogger(__name__)


class SettingsShard(ArkhamShard):
    """
    Settings and configuration management shard.

    Provides centralized management for system settings,
    user preferences, and shard configurations.
    """

    name = "settings"
    version = "0.1.0"
    description = "Application settings and configuration management - controls system behavior, user preferences, and shard configurations"

    def __init__(self):
        super().__init__()
        self._frame = None
        self._db = None
        self._event_bus = None
        self._storage = None

        # Caches
        self._settings_cache: Dict[str, Setting] = {}
        self._profiles_cache: Dict[str, SettingsProfile] = {}

    async def initialize(self, frame) -> None:
        """Initialize the shard with Frame services."""
        self._frame = frame

        # Get required services
        self._db = frame.get_service("database")
        if not self._db:
            raise RuntimeError("Database service required for Settings shard")

        self._event_bus = frame.get_service("events")
        if not self._event_bus:
            raise RuntimeError("Events service required for Settings shard")

        # Get optional services
        self._storage = frame.get_service("storage")
        if not self._storage:
            logger.info("Storage service not available - backup features limited")

        # Initialize database schema
        await self._create_schema()

        # Load default settings
        await self._load_default_settings()

        # Subscribe to events
        await self._event_bus.subscribe("shard.registered", self._on_shard_registered)
        await self._event_bus.subscribe("shard.unregistered", self._on_shard_unregistered)

        logger.info("Settings shard initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._event_bus:
            try:
                await self._event_bus.unsubscribe("shard.registered", self._on_shard_registered)
                await self._event_bus.unsubscribe("shard.unregistered", self._on_shard_unregistered)
            except Exception as e:
                logger.warning(f"Error unsubscribing from events: {e}")

        # Clear caches
        self._settings_cache.clear()
        self._profiles_cache.clear()

        self._db = None
        self._event_bus = None
        self._storage = None
        self._frame = None

        logger.info("Settings shard shut down")

    def get_routes(self):
        """Return the API router."""
        from .api import router
        return router

    # === Public API ===

    async def get_setting(self, key: str) -> Optional[Setting]:
        """
        Get a setting by key.

        Args:
            key: Setting key (e.g., "appearance.theme")

        Returns:
            Setting object or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Check cache first
        if key in self._settings_cache:
            return self._settings_cache[key]

        # Stub: return None (would query database)
        return None

    async def update_setting(
        self,
        key: str,
        value: Any,
        validate: bool = True
    ) -> Optional[Setting]:
        """
        Update a setting value.

        Args:
            key: Setting key
            value: New value
            validate: Whether to validate before saving

        Returns:
            Updated Setting or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub implementation
        if validate:
            validation = await self.validate_setting(key, value)
            if not validation.is_valid:
                raise ValueError(f"Invalid value: {validation.errors}")

        # Would update database and emit event
        if self._event_bus:
            await self._event_bus.publish("settings.setting.updated", {
                "key": key,
                "value": value,
            })

        return None

    async def reset_setting(self, key: str) -> Optional[Setting]:
        """
        Reset a setting to its default value.

        Args:
            key: Setting key

        Returns:
            Reset Setting or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub implementation
        if self._event_bus:
            await self._event_bus.publish("settings.setting.reset", {"key": key})

        return None

    async def get_category_settings(self, category: str) -> List[Setting]:
        """
        Get all settings in a category.

        Args:
            category: Category name

        Returns:
            List of settings in the category
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub: return empty list
        return []

    async def update_category_settings(
        self,
        category: str,
        settings: Dict[str, Any]
    ) -> List[Setting]:
        """
        Bulk update settings in a category.

        Args:
            category: Category name
            settings: Dict of key-value pairs

        Returns:
            List of updated settings
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub implementation
        if self._event_bus:
            await self._event_bus.publish("settings.category.updated", {
                "category": category,
                "count": len(settings),
            })

        return []

    async def validate_setting(self, key: str, value: Any) -> SettingsValidationResult:
        """
        Validate a setting value.

        Args:
            key: Setting key
            value: Value to validate

        Returns:
            Validation result
        """
        # Stub: always valid
        return SettingsValidationResult(is_valid=True, coerced_value=value)

    # === Profiles ===

    async def list_profiles(self) -> List[SettingsProfile]:
        """Get all settings profiles."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return []

    async def get_profile(self, profile_id: str) -> Optional[SettingsProfile]:
        """Get a profile by ID."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return None

    async def create_profile(
        self,
        name: str,
        description: str = "",
        settings: Optional[Dict[str, Any]] = None
    ) -> SettingsProfile:
        """
        Create a new settings profile.

        Args:
            name: Profile name
            description: Profile description
            settings: Optional settings to include (uses current if None)

        Returns:
            Created profile
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        profile = SettingsProfile(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            settings=settings or {},
        )
        return profile

    async def apply_profile(self, profile_id: str) -> bool:
        """
        Apply a settings profile.

        Args:
            profile_id: Profile ID to apply

        Returns:
            True if successful
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub implementation
        if self._event_bus:
            await self._event_bus.publish("settings.profile.applied", {
                "profile_id": profile_id,
            })

        return True

    async def delete_profile(self, profile_id: str) -> bool:
        """Delete a settings profile."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return True

    # === Shard Settings ===

    async def get_shard_settings(self, shard_name: str) -> Optional[ShardSettings]:
        """Get settings for a specific shard."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return None

    async def update_shard_settings(
        self,
        shard_name: str,
        settings: Dict[str, Any]
    ) -> Optional[ShardSettings]:
        """Update settings for a specific shard."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return None

    async def reset_shard_settings(self, shard_name: str) -> bool:
        """Reset shard settings to defaults."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return True

    # === Backup/Restore ===

    async def create_backup(
        self,
        name: str = "",
        description: str = ""
    ) -> Optional[SettingsBackup]:
        """
        Create a backup of all settings.

        Args:
            name: Backup name
            description: Backup description

        Returns:
            Created backup or None if storage unavailable
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        if not self._storage:
            logger.warning("Cannot create backup: storage service unavailable")
            return None

        # Stub implementation
        if self._event_bus:
            await self._event_bus.publish("settings.backup.created", {"name": name})

        return None

    async def list_backups(self) -> List[SettingsBackup]:
        """List all available backups."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return []

    async def restore_backup(self, backup_id: str) -> bool:
        """
        Restore settings from a backup.

        Args:
            backup_id: Backup ID to restore

        Returns:
            True if successful
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Stub implementation
        if self._event_bus:
            await self._event_bus.publish("settings.backup.restored", {
                "backup_id": backup_id,
            })

        return True

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return True

    # === Private Methods ===

    async def _create_schema(self) -> None:
        """Create database schema for settings."""
        # Stub: would create tables
        # arkham_settings: id, key, value, category, data_type, ...
        # arkham_settings_profiles: id, name, settings, ...
        # arkham_settings_backups: id, name, file_path, ...
        # arkham_settings_changes: id, setting_key, old_value, new_value, ...
        pass

    async def _load_default_settings(self) -> None:
        """Load default settings into cache."""
        # Stub: would load defaults from config
        pass

    async def _on_shard_registered(self, event_data: Dict[str, Any]) -> None:
        """Handle shard registration events."""
        shard_name = event_data.get("shard_name")
        logger.debug(f"Shard registered: {shard_name}")
        # Would initialize settings schema for new shard

    async def _on_shard_unregistered(self, event_data: Dict[str, Any]) -> None:
        """Handle shard unregistration events."""
        shard_name = event_data.get("shard_name")
        logger.debug(f"Shard unregistered: {shard_name}")
        # Would clean up shard settings
