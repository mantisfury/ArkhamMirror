"""
Settings Shard - Main Implementation

Provides centralized settings management for ArkhamFrame.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from arkham_frame import ArkhamShard

from .defaults import DEFAULT_SETTINGS, get_default_settings
from .models import (
    Setting,
    SettingCategory,
    SettingsBackup,
    SettingsProfile,
    SettingsValidationResult,
    SettingType,
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

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.settings_shard = self

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

        # Query database - settings can be tenant-specific or global (NULL tenant_id)
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_settings WHERE key = :key AND (tenant_id = :tenant_id OR tenant_id IS NULL)",
                {"key": key, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_settings WHERE key = :key",
                {"key": key}
            )

        if row:
            setting = self._row_to_setting(row)
            self._settings_cache[key] = setting
            return setting

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

        # Get existing setting
        existing = await self.get_setting(key)
        if not existing:
            return None

        # Check if readonly
        if existing.is_readonly:
            raise ValueError(f"Setting {key} is read-only")

        # Validate if requested
        if validate:
            validation = await self.validate_setting(key, value)
            if not validation.is_valid:
                raise ValueError(f"Invalid value: {validation.errors}")
            value = validation.coerced_value

        old_value = existing.value
        tenant_id = self.get_tenant_id_or_none()

        # Update in database
        if tenant_id:
            await self._db.execute(
                """
                UPDATE arkham_settings
                SET value = :value, modified_at = :modified_at
                WHERE key = :key AND (tenant_id = :tenant_id OR tenant_id IS NULL)
                """,
                {
                    "key": key,
                    "value": json.dumps(value),
                    "modified_at": datetime.utcnow(),
                    "tenant_id": str(tenant_id),
                }
            )
        else:
            await self._db.execute(
                """
                UPDATE arkham_settings
                SET value = :value, modified_at = :modified_at
                WHERE key = :key
                """,
                {
                    "key": key,
                    "value": json.dumps(value),
                    "modified_at": datetime.utcnow(),
                }
            )

        # Record change in history
        await self._db.execute(
            """
            INSERT INTO arkham_settings_changes (setting_key, old_value, new_value, tenant_id)
            VALUES (:key, :old_value, :new_value, :tenant_id)
            """,
            {
                "key": key,
                "old_value": json.dumps(old_value),
                "new_value": json.dumps(value),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

        # Invalidate cache
        if key in self._settings_cache:
            del self._settings_cache[key]

        # Refetch updated setting
        updated = await self.get_setting(key)

        # Emit event
        if self._event_bus and updated:
            await self._event_bus.emit("settings.setting.updated", {
                "key": key,
                "old_value": old_value,
                "new_value": value,
                "requires_restart": updated.requires_restart,
            }, "settings")

        return updated

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

        # Get existing setting
        existing = await self.get_setting(key)
        if not existing:
            return None

        if existing.is_readonly:
            raise ValueError(f"Setting {key} is read-only")

        # Reset to default value
        return await self.update_setting(key, existing.default_value, validate=False)

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

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_settings
                WHERE category = :category AND is_hidden = FALSE
                AND (tenant_id = :tenant_id OR tenant_id IS NULL)
                ORDER BY display_order
                """,
                {"category": category, "tenant_id": str(tenant_id)}
            )
        else:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_settings
                WHERE category = :category AND is_hidden = FALSE
                ORDER BY display_order
                """,
                {"category": category}
            )

        settings = [self._row_to_setting(row) for row in rows]

        # Update cache
        for setting in settings:
            self._settings_cache[setting.key] = setting

        return settings

    async def get_all_settings(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        modified_only: bool = False
    ) -> List[Setting]:
        """
        Get all settings with optional filtering.

        Args:
            category: Filter by category
            search: Search in key/label
            modified_only: Only return modified settings

        Returns:
            List of settings
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Build query with filters
        query = "SELECT * FROM arkham_settings WHERE is_hidden = FALSE"
        params: Dict[str, Any] = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND (tenant_id = :tenant_id OR tenant_id IS NULL)"
            params["tenant_id"] = str(tenant_id)

        if category:
            query += " AND category = :category"
            params["category"] = category

        if search:
            query += " AND (key ILIKE :search OR label ILIKE :search)"
            params["search"] = f"%{search}%"

        if modified_only:
            query += " AND value != default_value"

        query += " ORDER BY category, display_order"

        rows = await self._db.fetch_all(query, params)

        settings = [self._row_to_setting(row) for row in rows]

        # Update cache
        for setting in settings:
            self._settings_cache[setting.key] = setting

        return settings

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
            await self._event_bus.emit("settings.category.updated", {
                "category": category,
                "count": len(settings),
            }, "settings")

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
        errors: List[str] = []
        warnings: List[str] = []
        coerced_value = value

        # Get setting metadata
        setting = await self.get_setting(key)
        if not setting:
            return SettingsValidationResult(
                is_valid=False,
                errors=[f"Setting not found: {key}"],
                coerced_value=value
            )

        # Type coercion and validation based on data_type
        data_type = setting.data_type

        if data_type == SettingType.BOOLEAN:
            if isinstance(value, str):
                coerced_value = value.lower() in ("true", "1", "yes")
            elif not isinstance(value, bool):
                errors.append("Value must be a boolean")

        elif data_type == SettingType.INTEGER:
            try:
                coerced_value = int(value)
            except (ValueError, TypeError):
                errors.append("Value must be an integer")

        elif data_type == SettingType.FLOAT:
            try:
                coerced_value = float(value)
            except (ValueError, TypeError):
                errors.append("Value must be a number")

        elif data_type == SettingType.STRING:
            coerced_value = str(value)

        elif data_type in (SettingType.SELECT, SettingType.MULTISELECT):
            # Validate against options
            if setting.options:
                valid_values = [opt.get("value") for opt in setting.options]
                if data_type == SettingType.SELECT:
                    if value not in valid_values:
                        errors.append(f"Value must be one of: {valid_values}")
                else:
                    if not isinstance(value, list):
                        errors.append("Value must be a list")
                    elif not all(v in valid_values for v in value):
                        errors.append(f"All values must be in: {valid_values}")

        # Validation rules from setting.validation
        validation = setting.validation
        if validation:
            if "min" in validation and isinstance(coerced_value, (int, float)):
                if coerced_value < validation["min"]:
                    errors.append(f"Value must be at least {validation['min']}")

            if "max" in validation and isinstance(coerced_value, (int, float)):
                if coerced_value > validation["max"]:
                    errors.append(f"Value must be at most {validation['max']}")

            if "pattern" in validation and isinstance(coerced_value, str):
                import re
                if not re.match(validation["pattern"], coerced_value):
                    errors.append(f"Value must match pattern: {validation['pattern']}")

        return SettingsValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            coerced_value=coerced_value
        )

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
            await self._event_bus.emit("settings.profile.applied", {
                "profile_id": profile_id,
            }, "settings")

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
            await self._event_bus.emit("settings.backup.created", {"name": name}, "settings")

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
            await self._event_bus.emit("settings.backup.restored", {
                "backup_id": backup_id,
            }, "settings")

        return True

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        return True

    # === Private Methods ===

    async def _create_schema(self) -> None:
        """Create database schema for settings."""
        # Create settings table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_settings (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                default_value JSONB NOT NULL,
                category TEXT NOT NULL,
                data_type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT DEFAULT '',
                validation JSONB DEFAULT '{}',
                options JSONB DEFAULT '[]',
                requires_restart BOOLEAN DEFAULT FALSE,
                is_hidden BOOLEAN DEFAULT FALSE,
                is_readonly BOOLEAN DEFAULT FALSE,
                display_order INTEGER DEFAULT 0,
                modified_at TIMESTAMP,
                modified_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create profiles table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_settings_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                settings JSONB DEFAULT '{}',
                is_default BOOLEAN DEFAULT FALSE,
                is_builtin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Create change history table for auditing
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_settings_changes (
                id SERIAL PRIMARY KEY,
                setting_key TEXT NOT NULL,
                old_value JSONB,
                new_value JSONB,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                changed_by TEXT,
                reason TEXT
            )
        """)

        # Create index on category for faster filtering
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_settings_category
            ON arkham_settings(category)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY[
                    'arkham_settings',
                    'arkham_settings_profiles',
                    'arkham_settings_changes'
                ];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_settings_tenant
            ON arkham_settings(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_settings_profiles_tenant
            ON arkham_settings_profiles(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_settings_changes_tenant
            ON arkham_settings_changes(tenant_id)
        """)

        logger.info("Settings database schema created")

    async def _load_default_settings(self) -> None:
        """Load default settings into database if not exists."""
        # Get set of valid setting keys from defaults
        valid_keys = [setting.key for setting in DEFAULT_SETTINGS]

        # Remove orphaned settings that no longer exist in defaults
        # Build placeholders for the IN clause
        if valid_keys:
            try:
                placeholders = ", ".join(f"'{k}'" for k in valid_keys)
                await self._db.execute(
                    f"DELETE FROM arkham_settings WHERE key NOT IN ({placeholders})"
                )
                logger.debug("Cleaned up orphaned settings")
            except Exception as e:
                logger.warning(f"Failed to clean up orphaned settings: {e}")

        for setting in DEFAULT_SETTINGS:
            # Check if setting already exists
            existing = await self._db.fetch_one(
                "SELECT key FROM arkham_settings WHERE key = :key",
                {"key": setting.key}
            )

            if not existing:
                # Insert new setting
                await self._db.execute(
                    """
                    INSERT INTO arkham_settings (
                        key, value, default_value, category, data_type,
                        label, description, validation, options,
                        requires_restart, is_hidden, is_readonly, display_order
                    ) VALUES (
                        :key, :value, :default_value, :category, :data_type,
                        :label, :description, :validation, :options,
                        :requires_restart, :is_hidden, :is_readonly, :display_order
                    )
                    """,
                    {
                        "key": setting.key,
                        "value": json.dumps(setting.value),
                        "default_value": json.dumps(setting.default_value),
                        "category": setting.category.value,
                        "data_type": setting.data_type.value,
                        "label": setting.label,
                        "description": setting.description,
                        "validation": json.dumps(setting.validation),
                        "options": json.dumps(setting.options),
                        "requires_restart": setting.requires_restart,
                        "is_hidden": setting.is_hidden,
                        "is_readonly": setting.is_readonly,
                        "display_order": setting.order,
                    }
                )
                logger.debug(f"Inserted default setting: {setting.key}")

            # Cache the setting
            self._settings_cache[setting.key] = setting

        logger.info(f"Loaded {len(DEFAULT_SETTINGS)} default settings")

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored, e.g., "SHATTERED")
        - String that needs parsing (raw JSON, e.g., '{"key": "value"}')
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                # (e.g., JSONB stored "SHATTERED" comes back as 'SHATTERED')
                return value
        return default

    def _row_to_setting(self, row: Dict[str, Any]) -> Setting:
        """Convert a database row to a Setting object."""
        # Debug log the raw row
        logger.debug(f"Raw row for {row.get('key')}: value={row.get('value')!r} (type={type(row.get('value')).__name__})")

        # Parse JSONB fields - handle both string and already-parsed formats
        value = self._parse_jsonb(row.get("value"))
        default_value = self._parse_jsonb(row.get("default_value"))
        validation = self._parse_jsonb(row.get("validation"), {})
        options = self._parse_jsonb(row.get("options"), [])

        logger.debug(f"Parsed value for {row.get('key')}: {value!r}")

        return Setting(
            key=row["key"],
            value=value,
            default_value=default_value,
            category=SettingCategory(row["category"]),
            data_type=SettingType(row["data_type"]),
            label=row["label"],
            description=row.get("description", ""),
            validation=validation,
            options=options,
            requires_restart=row.get("requires_restart", False),
            is_hidden=row.get("is_hidden", False),
            is_readonly=row.get("is_readonly", False),
            order=row.get("display_order", 0),
            modified_at=row.get("modified_at"),
            modified_by=row.get("modified_by"),
        )

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
