# arkham-shard-settings

> Application settings and configuration management for ArkhamFrame - controls system behavior, user preferences, and shard configurations.

## Overview

The Settings shard provides a centralized interface for managing application settings, user preferences, and shard configurations. It enables users to customize system behavior while maintaining sensible defaults and supporting multiple configuration profiles.

## Features

### General Settings
- Application name and branding
- Language and timezone configuration
- Date and time format preferences

### Appearance Settings
- Theme selection: Arkham (dark cyberpunk), Newsroom (light parchment), System
- Custom accent color picker with presets
- Real-time theme preview and application

### Notification Settings
- In-app notification preferences
- Email channel configuration (SMTP)
- Webhook channel configuration (Slack, Discord, custom)
- Channel management (add, remove, test)

### Performance Settings
- Pagination defaults
- Cache settings
- Batch processing sizes

### Data Management
- Storage overview (database, vectors, file storage)
- Clear local storage (browser cache)
- Clear temporary files
- Clear vector embeddings
- Clear database (preserves settings)
- Reset all data (complete fresh start)
- Settings export/import

### Shard Management
- View all installed shards grouped by category
- Enable/disable shards (except protected: Dashboard, Settings)
- View shard capabilities and versions

### Advanced Settings
- Debug mode toggle
- Developer options
- Logging configuration

## Installation

```bash
cd packages/arkham-shard-settings
pip install -e .
```

The shard is auto-discovered by ArkhamFrame via entry points.

## API Endpoints

All endpoints are prefixed with `/api/settings`.

### Settings CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all settings (optional: `category`, `search`, `modified_only`) |
| GET | `/{key}` | Get specific setting by key |
| PUT | `/{key}` | Update setting value |
| DELETE | `/{key}` | Reset setting to default |
| GET | `/health` | Health check with settings count |
| GET | `/count` | Get count of modified settings |

### Category Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/category/{category}` | Get all settings in a category |
| PUT | `/category/{category}` | Bulk update category settings |

### Validation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/validate` | Validate a setting value without saving |

### Data Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/data/stats` | Get storage statistics (database, vectors, files) |
| POST | `/data/clear-vectors` | Clear all vector embeddings |
| POST | `/data/clear-database` | Clear database tables (preserves settings) |
| POST | `/data/clear-temp` | Clear temporary files |
| POST | `/data/reset-all` | Reset all data (database, vectors, temp) |

### Profiles

| Method | Path | Description |
|--------|------|-------------|
| GET | `/profiles` | List all settings profiles |
| POST | `/profiles` | Create a new profile |
| GET | `/profiles/{id}` | Get profile by ID |
| PUT | `/profiles/{id}` | Update a profile |
| DELETE | `/profiles/{id}` | Delete a profile |
| POST | `/profiles/{id}/apply` | Apply a profile |

### Shard Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/shards` | List settings for all shards |
| GET | `/shards/{name}` | Get settings for a specific shard |
| PUT | `/shards/{name}` | Update shard settings |
| DELETE | `/shards/{name}` | Reset shard settings to defaults |

### Backup/Restore

| Method | Path | Description |
|--------|------|-------------|
| GET | `/backups` | List all backups |
| POST | `/backup` | Create a settings backup |
| GET | `/backups/{id}` | Get backup details |
| POST | `/restore/{id}` | Restore from backup |
| DELETE | `/backups/{id}` | Delete a backup |

### Export/Import

| Method | Path | Description |
|--------|------|-------------|
| GET | `/export` | Export all settings as JSON |
| POST | `/import` | Import settings from JSON |

### API Examples

```bash
# List all settings
curl http://localhost:8100/api/settings/

# Get settings by category
curl "http://localhost:8100/api/settings/?category=appearance"

# Get a specific setting
curl http://localhost:8100/api/settings/appearance.theme

# Update a setting
curl -X PUT http://localhost:8100/api/settings/appearance.theme \
  -H "Content-Type: application/json" \
  -d '{"value": "newsroom"}'

# Reset a setting to default
curl -X DELETE http://localhost:8100/api/settings/appearance.theme

# Validate a setting value
curl -X POST http://localhost:8100/api/settings/validate \
  -H "Content-Type: application/json" \
  -d '{"key": "performance.page_size", "value": 50}'

# Get storage statistics
curl http://localhost:8100/api/settings/data/stats

# Clear vector embeddings
curl -X POST http://localhost:8100/api/settings/data/clear-vectors

# Export settings
curl http://localhost:8100/api/settings/export > settings-backup.json
```

## Events

### Published Events

| Event | Payload | Description |
|-------|---------|-------------|
| `settings.setting.updated` | `{key, old_value, new_value, requires_restart}` | Setting value changed |
| `settings.setting.reset` | `{key}` | Setting reset to default |
| `settings.category.updated` | `{category, count}` | Bulk category update |
| `settings.profile.applied` | `{profile_id}` | Profile applied |
| `settings.backup.created` | `{name}` | Backup created |
| `settings.backup.restored` | `{backup_id}` | Settings restored |

### Subscribed Events

| Event | Description |
|-------|-------------|
| `shard.registered` | Initialize settings schema for new shard |
| `shard.unregistered` | Clean up shard settings |

## Database Schema

### arkham_settings
```sql
CREATE TABLE arkham_settings (
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
);
```

### arkham_settings_profiles
```sql
CREATE TABLE arkham_settings_profiles (
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
);
```

### arkham_settings_changes
```sql
CREATE TABLE arkham_settings_changes (
    id SERIAL PRIMARY KEY,
    setting_key TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    reason TEXT
);
```

## UI Routes

| Route | Tab | Description |
|-------|-----|-------------|
| `/settings` | General | Language, timezone, date formats |
| `/settings/appearance` | Appearance | Theme, colors, layout |
| `/settings/notifications` | Notifications | Alerts, email, webhooks |
| `/settings/performance` | Performance | Caching, pagination |
| `/settings/data` | Data | Storage management, cleanup |
| `/settings/advanced` | Advanced | Developer options |
| `/settings/shards` | Shards | Enable/disable feature modules |

## Dependencies

### Required Services
- `database` - Settings persistence
- `events` - Change notifications

### Optional Services
- `storage` - Backup file storage

## Setting Categories

| Category | Description |
|----------|-------------|
| `general` | Application name, language, timezone, date format |
| `appearance` | Theme, accent color, layout preferences |
| `notifications` | Alert preferences, delivery channels |
| `performance` | Pagination, caching, batch sizes |
| `data` | Retention policies, cleanup settings |
| `advanced` | Debug mode, developer options |

## Setting Data Types

| Type | Description |
|------|-------------|
| `boolean` | Toggle switch |
| `string` | Text input |
| `integer` | Numeric input (whole numbers) |
| `float` | Numeric input (decimals) |
| `select` | Dropdown with predefined options |
| `multiselect` | Multiple selection |
| `color` | Color picker |

## URL State

The settings page uses URL state strategy with these parameters:

- `category` - Active category tab
- `search` - Search filter for settings

Local storage keys:
- `collapsed_sections` - UI section collapse state
- `show_advanced` - Show advanced settings toggle
- `last_category` - Remember last visited category

## Usage Example

```python
from arkham_shard_settings import SettingsShard

# Get a setting
theme = await shard.get_setting("appearance.theme")
print(f"Current theme: {theme.value}")  # e.g., "arkham"

# Update a setting
await shard.update_setting("appearance.theme", "newsroom")

# Get all settings in a category
appearance = await shard.get_category_settings("appearance")
for setting in appearance:
    print(f"{setting.label}: {setting.value}")

# Validate before saving
result = await shard.validate_setting("performance.page_size", 100)
if result.is_valid:
    await shard.update_setting("performance.page_size", result.coerced_value)
else:
    print(f"Validation errors: {result.errors}")

# Reset to default
await shard.reset_setting("appearance.theme")

# Create a profile from current settings
profile = await shard.create_profile("My Config", "Personal settings")

# Apply a profile
await shard.apply_profile(profile.id)
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run frame with settings
cd ../arkham-frame
python -m uvicorn arkham_frame.main:app --reload

# Access settings UI
# http://localhost:5173/settings (with shell running)
```

## License

MIT License - Part of the SHATTERED project.
