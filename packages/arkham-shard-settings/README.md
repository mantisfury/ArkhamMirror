# Settings Shard

> Application settings and configuration management for ArkhamFrame

## Overview

The Settings Shard provides a centralized interface for managing application settings, user preferences, and shard configurations. It enables users to customize system behavior while maintaining sensible defaults.

## Features

- **System Settings**: Configure system-wide behavior (language, timezone, defaults)
- **User Preferences**: Personal settings (theme, layout, notifications)
- **Shard Configuration**: Configure individual shard settings
- **Settings Profiles**: Save and apply settings profiles
- **Backup/Restore**: Export and import settings

## Installation

```bash
cd packages/arkham-shard-settings
pip install -e .
```

## API Endpoints

### Settings Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/` | List all settings |
| GET | `/api/settings/{key}` | Get specific setting |
| PUT | `/api/settings/{key}` | Update setting value |
| DELETE | `/api/settings/{key}` | Reset setting to default |
| GET | `/api/settings/category/{category}` | Get settings by category |
| PUT | `/api/settings/category/{category}` | Bulk update category |

### Shard Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/shards` | List all shard settings |
| GET | `/api/settings/shards/{shard}` | Get shard settings |
| PUT | `/api/settings/shards/{shard}` | Update shard settings |
| DELETE | `/api/settings/shards/{shard}` | Reset shard settings |

### Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/profiles` | List profiles |
| POST | `/api/settings/profiles` | Create profile |
| PUT | `/api/settings/profiles/{id}` | Update profile |
| DELETE | `/api/settings/profiles/{id}` | Delete profile |
| POST | `/api/settings/profiles/{id}/apply` | Apply profile |

### Backup/Restore

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/settings/backup` | Create backup |
| GET | `/api/settings/backups` | List backups |
| POST | `/api/settings/restore` | Restore from backup |

## Data Models

### Setting
```python
@dataclass
class Setting:
    key: str                    # Unique setting key
    value: Any                  # Current value
    default_value: Any          # Default value
    category: SettingCategory   # Setting category
    data_type: SettingType      # Value type
    label: str                  # Display label
    description: str            # Help text
    validation: dict            # Validation rules
    requires_restart: bool      # Needs restart to apply
```

### SettingsProfile
```python
@dataclass
class SettingsProfile:
    id: str
    name: str
    description: str
    settings: Dict[str, Any]    # Key-value pairs
    is_default: bool
    created_at: datetime
    updated_at: datetime
```

## Events

### Published
- `settings.setting.updated` - Setting value changed
- `settings.setting.reset` - Setting reset to default
- `settings.category.updated` - Bulk category update
- `settings.profile.applied` - Profile applied
- `settings.backup.created` - Backup created
- `settings.backup.restored` - Settings restored

### Subscribed
- `shard.registered` - Update shard config options
- `shard.unregistered` - Clean up shard settings

## Setting Categories

| Category | Description |
|----------|-------------|
| General | Language, timezone, date format |
| Appearance | Theme, layout, font size |
| Notifications | Email, in-app alerts |
| Privacy | Data sharing, analytics |
| Performance | Caching, batch sizes |
| Advanced | Developer options |

## Usage Example

```python
from arkham_shard_settings import SettingsShard

# Get a setting
theme = await shard.get_setting("appearance.theme")

# Update a setting
await shard.update_setting("appearance.theme", "dark")

# Get all settings in a category
appearance = await shard.get_category_settings("appearance")

# Apply a profile
await shard.apply_profile("minimal")

# Create a backup
backup_id = await shard.create_backup()
```

## Dependencies

- **Required**: database, events
- **Optional**: storage (for backup files)

## License

Part of the SHATTERED project.
