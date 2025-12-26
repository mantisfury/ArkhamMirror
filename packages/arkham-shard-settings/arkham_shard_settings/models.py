"""
Settings Shard - Data Models

Pydantic models and dataclasses for settings management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# === Enums ===

class SettingCategory(str, Enum):
    """Categories for organizing settings."""
    GENERAL = "general"           # Language, timezone, formats
    APPEARANCE = "appearance"     # Theme, layout, fonts
    NOTIFICATIONS = "notifications"  # Alerts, emails
    PRIVACY = "privacy"           # Data sharing, analytics
    PERFORMANCE = "performance"   # Caching, batch sizes
    ADVANCED = "advanced"         # Developer options
    SHARD = "shard"              # Shard-specific settings


class SettingType(str, Enum):
    """Data types for setting values."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    SELECT = "select"             # Single selection from options
    MULTISELECT = "multiselect"   # Multiple selections
    COLOR = "color"               # Color picker
    JSON = "json"                 # Complex JSON value
    SECRET = "secret"             # Password/API key (masked)


class ValidationRule(str, Enum):
    """Types of validation rules for settings."""
    REQUIRED = "required"
    MIN = "min"
    MAX = "max"
    PATTERN = "pattern"
    OPTIONS = "options"


# === Dataclasses ===

@dataclass
class SettingValue:
    """
    A setting's current and default values.
    """
    current: Any
    default: Any
    is_modified: bool = False
    modified_at: Optional[datetime] = None
    modified_by: Optional[str] = None


@dataclass
class Setting:
    """
    A configurable setting with metadata.
    """
    key: str                                  # Unique key (e.g., "appearance.theme")
    value: Any                                # Current value
    default_value: Any                        # Factory default
    category: SettingCategory                 # Grouping category
    data_type: SettingType                    # Value type
    label: str                                # Display label
    description: str = ""                     # Help text

    # Validation
    validation: Dict[str, Any] = field(default_factory=dict)
    options: List[Dict[str, Any]] = field(default_factory=list)  # For SELECT types

    # Metadata
    requires_restart: bool = False            # Needs app restart
    is_hidden: bool = False                   # Hidden from UI
    is_readonly: bool = False                 # Cannot be modified
    order: int = 0                            # Display order within category

    # Tracking
    modified_at: Optional[datetime] = None
    modified_by: Optional[str] = None

    @property
    def is_modified(self) -> bool:
        """Check if setting differs from default."""
        return self.value != self.default_value

    @property
    def full_key(self) -> str:
        """Full setting key including category."""
        return f"{self.category.value}.{self.key}" if "." not in self.key else self.key


@dataclass
class SettingsProfile:
    """
    A saved collection of settings for quick application.
    """
    id: str
    name: str
    description: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)  # Key-value pairs

    is_default: bool = False                  # Default profile
    is_builtin: bool = False                  # System-provided profile

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingsBackup:
    """
    A backup of all settings for restore.
    """
    id: str
    name: str
    description: str = ""

    settings_count: int = 0
    file_path: Optional[str] = None
    file_size: int = 0
    checksum: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    # What's included
    includes_system: bool = True
    includes_user: bool = True
    includes_shards: bool = True

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShardSettings:
    """
    Settings configuration for a specific shard.
    """
    shard_name: str
    shard_version: str

    settings: Dict[str, Setting] = field(default_factory=dict)
    schema: Dict[str, Any] = field(default_factory=dict)  # JSON Schema for validation

    is_enabled: bool = True
    last_modified: Optional[datetime] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingChange:
    """
    Record of a setting change for audit.
    """
    id: str
    setting_key: str
    old_value: Any
    new_value: Any
    changed_at: datetime = field(default_factory=datetime.utcnow)
    changed_by: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class SettingsValidationResult:
    """
    Result of validating a settings value.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    coerced_value: Any = None  # Value after type coercion


@dataclass
class SettingsExport:
    """
    Exported settings data for transfer.
    """
    version: str = "1.0"
    exported_at: datetime = field(default_factory=datetime.utcnow)
    exported_by: Optional[str] = None

    settings: Dict[str, Any] = field(default_factory=dict)
    profiles: List[SettingsProfile] = field(default_factory=list)

    app_version: Optional[str] = None
    checksum: Optional[str] = None
