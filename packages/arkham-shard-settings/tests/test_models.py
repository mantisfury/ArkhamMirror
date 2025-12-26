"""Tests for settings shard data models."""

import pytest
from datetime import datetime
from arkham_shard_settings.models import (
    SettingCategory,
    SettingType,
    ValidationRule,
    Setting,
    SettingValue,
    SettingsProfile,
    SettingsBackup,
    ShardSettings,
    SettingChange,
    SettingsValidationResult,
    SettingsExport,
)


class TestSettingCategory:
    """Test SettingCategory enum."""

    def test_setting_category_values(self):
        """Test all setting category values."""
        assert SettingCategory.GENERAL.value == "general"
        assert SettingCategory.APPEARANCE.value == "appearance"
        assert SettingCategory.NOTIFICATIONS.value == "notifications"
        assert SettingCategory.PRIVACY.value == "privacy"
        assert SettingCategory.PERFORMANCE.value == "performance"
        assert SettingCategory.ADVANCED.value == "advanced"
        assert SettingCategory.SHARD.value == "shard"

    def test_setting_category_count(self):
        """Test we have all expected categories."""
        assert len(SettingCategory) == 7


class TestSettingType:
    """Test SettingType enum."""

    def test_setting_type_values(self):
        """Test all setting type values."""
        assert SettingType.STRING.value == "string"
        assert SettingType.INTEGER.value == "integer"
        assert SettingType.FLOAT.value == "float"
        assert SettingType.BOOLEAN.value == "boolean"
        assert SettingType.SELECT.value == "select"
        assert SettingType.MULTISELECT.value == "multiselect"
        assert SettingType.COLOR.value == "color"
        assert SettingType.JSON.value == "json"
        assert SettingType.SECRET.value == "secret"

    def test_setting_type_count(self):
        """Test we have all expected types."""
        assert len(SettingType) == 9


class TestValidationRule:
    """Test ValidationRule enum."""

    def test_validation_rule_values(self):
        """Test all validation rule values."""
        assert ValidationRule.REQUIRED.value == "required"
        assert ValidationRule.MIN.value == "min"
        assert ValidationRule.MAX.value == "max"
        assert ValidationRule.PATTERN.value == "pattern"
        assert ValidationRule.OPTIONS.value == "options"

    def test_validation_rule_count(self):
        """Test we have all expected rules."""
        assert len(ValidationRule) == 5


class TestSettingValue:
    """Test SettingValue dataclass."""

    def test_setting_value_creation(self):
        """Test basic setting value creation."""
        sv = SettingValue(
            current="dark",
            default="light",
        )
        assert sv.current == "dark"
        assert sv.default == "light"
        assert sv.is_modified is False
        assert sv.modified_at is None
        assert sv.modified_by is None

    def test_setting_value_with_modification(self):
        """Test setting value with modification info."""
        now = datetime.utcnow()
        sv = SettingValue(
            current="dark",
            default="light",
            is_modified=True,
            modified_at=now,
            modified_by="user-123",
        )
        assert sv.is_modified is True
        assert sv.modified_at == now
        assert sv.modified_by == "user-123"


class TestSetting:
    """Test Setting dataclass."""

    def test_setting_creation_minimal(self):
        """Test minimal setting creation."""
        setting = Setting(
            key="theme",
            value="dark",
            default_value="light",
            category=SettingCategory.APPEARANCE,
            data_type=SettingType.SELECT,
            label="Theme",
        )
        assert setting.key == "theme"
        assert setting.value == "dark"
        assert setting.default_value == "light"
        assert setting.category == SettingCategory.APPEARANCE
        assert setting.data_type == SettingType.SELECT
        assert setting.label == "Theme"
        assert setting.description == ""
        assert setting.requires_restart is False
        assert setting.is_hidden is False
        assert setting.is_readonly is False
        assert setting.order == 0

    def test_setting_creation_full(self):
        """Test setting creation with all fields."""
        now = datetime.utcnow()
        setting = Setting(
            key="max_workers",
            value=8,
            default_value=4,
            category=SettingCategory.PERFORMANCE,
            data_type=SettingType.INTEGER,
            label="Max Workers",
            description="Maximum number of worker threads",
            validation={"min": 1, "max": 32},
            options=[],
            requires_restart=True,
            is_hidden=False,
            is_readonly=False,
            order=10,
            modified_at=now,
            modified_by="admin",
        )
        assert setting.requires_restart is True
        assert setting.validation == {"min": 1, "max": 32}
        assert setting.modified_at == now
        assert setting.modified_by == "admin"

    def test_setting_is_modified_property(self):
        """Test is_modified property."""
        # Modified
        modified = Setting(
            key="theme",
            value="dark",
            default_value="light",
            category=SettingCategory.APPEARANCE,
            data_type=SettingType.SELECT,
            label="Theme",
        )
        assert modified.is_modified is True

        # Not modified
        unmodified = Setting(
            key="theme",
            value="light",
            default_value="light",
            category=SettingCategory.APPEARANCE,
            data_type=SettingType.SELECT,
            label="Theme",
        )
        assert unmodified.is_modified is False

    def test_setting_full_key_property(self):
        """Test full_key property."""
        # Without category prefix
        setting1 = Setting(
            key="theme",
            value="dark",
            default_value="light",
            category=SettingCategory.APPEARANCE,
            data_type=SettingType.SELECT,
            label="Theme",
        )
        assert setting1.full_key == "appearance.theme"

        # With category prefix already
        setting2 = Setting(
            key="appearance.theme",
            value="dark",
            default_value="light",
            category=SettingCategory.APPEARANCE,
            data_type=SettingType.SELECT,
            label="Theme",
        )
        assert setting2.full_key == "appearance.theme"

    def test_setting_with_options(self):
        """Test setting with select options."""
        setting = Setting(
            key="language",
            value="en",
            default_value="en",
            category=SettingCategory.GENERAL,
            data_type=SettingType.SELECT,
            label="Language",
            options=[
                {"value": "en", "label": "English"},
                {"value": "es", "label": "Spanish"},
                {"value": "fr", "label": "French"},
            ],
        )
        assert len(setting.options) == 3
        assert setting.options[0]["value"] == "en"


class TestSettingsProfile:
    """Test SettingsProfile dataclass."""

    def test_profile_creation_minimal(self):
        """Test minimal profile creation."""
        profile = SettingsProfile(
            id="profile-1",
            name="Dark Mode",
        )
        assert profile.id == "profile-1"
        assert profile.name == "Dark Mode"
        assert profile.description == ""
        assert profile.settings == {}
        assert profile.is_default is False
        assert profile.is_builtin is False
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)
        assert profile.created_by is None

    def test_profile_creation_full(self):
        """Test profile creation with all fields."""
        now = datetime.utcnow()
        profile = SettingsProfile(
            id="profile-2",
            name="Minimal UI",
            description="A minimal interface with fewer elements",
            settings={
                "appearance.theme": "light",
                "appearance.sidebar": "collapsed",
            },
            is_default=True,
            is_builtin=True,
            created_at=now,
            updated_at=now,
            created_by="system",
            metadata={"version": "1.0"},
        )
        assert profile.description == "A minimal interface with fewer elements"
        assert len(profile.settings) == 2
        assert profile.is_default is True
        assert profile.is_builtin is True
        assert profile.metadata == {"version": "1.0"}


class TestSettingsBackup:
    """Test SettingsBackup dataclass."""

    def test_backup_creation_minimal(self):
        """Test minimal backup creation."""
        backup = SettingsBackup(
            id="backup-1",
            name="Daily Backup",
        )
        assert backup.id == "backup-1"
        assert backup.name == "Daily Backup"
        assert backup.settings_count == 0
        assert backup.file_path is None
        assert backup.includes_system is True
        assert backup.includes_user is True
        assert backup.includes_shards is True

    def test_backup_creation_full(self):
        """Test backup creation with all fields."""
        now = datetime.utcnow()
        backup = SettingsBackup(
            id="backup-2",
            name="Full Backup",
            description="Complete settings backup before upgrade",
            settings_count=150,
            file_path="/backups/settings_20241225.json",
            file_size=32768,
            checksum="abc123",
            created_at=now,
            created_by="admin",
            includes_system=True,
            includes_user=True,
            includes_shards=True,
            metadata={"reason": "pre-upgrade"},
        )
        assert backup.settings_count == 150
        assert backup.file_size == 32768
        assert backup.checksum == "abc123"


class TestShardSettings:
    """Test ShardSettings dataclass."""

    def test_shard_settings_creation(self):
        """Test shard settings creation."""
        settings = ShardSettings(
            shard_name="search",
            shard_version="0.1.0",
        )
        assert settings.shard_name == "search"
        assert settings.shard_version == "0.1.0"
        assert settings.settings == {}
        assert settings.schema == {}
        assert settings.is_enabled is True
        assert settings.last_modified is None

    def test_shard_settings_with_config(self):
        """Test shard settings with configuration."""
        setting = Setting(
            key="max_results",
            value=100,
            default_value=50,
            category=SettingCategory.SHARD,
            data_type=SettingType.INTEGER,
            label="Max Results",
        )
        shard_settings = ShardSettings(
            shard_name="search",
            shard_version="0.1.0",
            settings={"max_results": setting},
            is_enabled=True,
        )
        assert "max_results" in shard_settings.settings


class TestSettingChange:
    """Test SettingChange dataclass."""

    def test_setting_change_creation(self):
        """Test setting change creation."""
        change = SettingChange(
            id="change-1",
            setting_key="appearance.theme",
            old_value="light",
            new_value="dark",
        )
        assert change.id == "change-1"
        assert change.setting_key == "appearance.theme"
        assert change.old_value == "light"
        assert change.new_value == "dark"
        assert isinstance(change.changed_at, datetime)
        assert change.changed_by is None
        assert change.reason is None

    def test_setting_change_with_audit(self):
        """Test setting change with audit info."""
        now = datetime.utcnow()
        change = SettingChange(
            id="change-2",
            setting_key="performance.cache_size",
            old_value=1024,
            new_value=2048,
            changed_at=now,
            changed_by="admin",
            reason="Increase cache for better performance",
        )
        assert change.changed_by == "admin"
        assert change.reason == "Increase cache for better performance"


class TestSettingsValidationResult:
    """Test SettingsValidationResult dataclass."""

    def test_validation_result_valid(self):
        """Test valid validation result."""
        result = SettingsValidationResult(
            is_valid=True,
            coerced_value=42,
        )
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.coerced_value == 42

    def test_validation_result_invalid(self):
        """Test invalid validation result."""
        result = SettingsValidationResult(
            is_valid=False,
            errors=["Value must be between 1 and 100"],
            warnings=["Value is near maximum"],
            coerced_value=None,
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


class TestSettingsExport:
    """Test SettingsExport dataclass."""

    def test_settings_export_creation(self):
        """Test settings export creation."""
        export = SettingsExport()
        assert export.version == "1.0"
        assert isinstance(export.exported_at, datetime)
        assert export.settings == {}
        assert export.profiles == []

    def test_settings_export_with_data(self):
        """Test settings export with data."""
        profile = SettingsProfile(id="p1", name="Test")
        export = SettingsExport(
            version="1.0",
            exported_by="user-1",
            settings={"theme": "dark"},
            profiles=[profile],
            app_version="2.0.0",
            checksum="xyz789",
        )
        assert export.exported_by == "user-1"
        assert export.settings == {"theme": "dark"}
        assert len(export.profiles) == 1
        assert export.app_version == "2.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
