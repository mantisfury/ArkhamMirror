"""
Settings Shard - Default Settings

Defines all default settings for the application.
"""

from .models import Setting, SettingCategory, SettingType


# Default settings organized by category
DEFAULT_SETTINGS: list[Setting] = [
    # === General Settings ===
    Setting(
        key="general.app_name",
        value="SHATTERED",
        default_value="SHATTERED",
        category=SettingCategory.GENERAL,
        data_type=SettingType.STRING,
        label="Application Name",
        description="The display name for the application",
        is_readonly=True,
        order=1,
    ),
    Setting(
        key="general.language",
        value="en",
        default_value="en",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Language",
        description="Interface language",
        options=[
            {"value": "en", "label": "English"},
            {"value": "es", "label": "Spanish"},
            {"value": "fr", "label": "French"},
        ],
        order=2,
    ),
    Setting(
        key="general.timezone",
        value="UTC",
        default_value="UTC",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Timezone",
        description="Default timezone for dates",
        options=[
            {"value": "UTC", "label": "UTC"},
            {"value": "America/New_York", "label": "Eastern Time"},
            {"value": "America/Chicago", "label": "Central Time"},
            {"value": "America/Denver", "label": "Mountain Time"},
            {"value": "America/Los_Angeles", "label": "Pacific Time"},
            {"value": "Europe/London", "label": "London"},
            {"value": "Europe/Paris", "label": "Paris"},
        ],
        order=3,
    ),
    Setting(
        key="general.date_format",
        value="YYYY-MM-DD",
        default_value="YYYY-MM-DD",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Date Format",
        description="How dates are displayed",
        options=[
            {"value": "YYYY-MM-DD", "label": "2024-12-27"},
            {"value": "MM/DD/YYYY", "label": "12/27/2024"},
            {"value": "DD/MM/YYYY", "label": "27/12/2024"},
            {"value": "MMM DD, YYYY", "label": "Dec 27, 2024"},
        ],
        order=4,
    ),

    # === Appearance Settings ===
    Setting(
        key="appearance.theme",
        value="dark",
        default_value="dark",
        category=SettingCategory.APPEARANCE,
        data_type=SettingType.SELECT,
        label="Theme",
        description="Color theme for the interface",
        options=[
            {"value": "dark", "label": "Dark"},
            {"value": "light", "label": "Light"},
            {"value": "system", "label": "System Default"},
        ],
        order=1,
    ),
    Setting(
        key="appearance.sidebar_collapsed",
        value=False,
        default_value=False,
        category=SettingCategory.APPEARANCE,
        data_type=SettingType.BOOLEAN,
        label="Collapse Sidebar",
        description="Start with sidebar collapsed",
        order=2,
    ),
    Setting(
        key="appearance.compact_mode",
        value=False,
        default_value=False,
        category=SettingCategory.APPEARANCE,
        data_type=SettingType.BOOLEAN,
        label="Compact Mode",
        description="Use smaller spacing and fonts",
        order=3,
    ),
    Setting(
        key="appearance.show_badges",
        value=True,
        default_value=True,
        category=SettingCategory.APPEARANCE,
        data_type=SettingType.BOOLEAN,
        label="Show Badges",
        description="Show notification badges in navigation",
        order=4,
    ),
    Setting(
        key="appearance.accent_color",
        value="#e94560",
        default_value="#e94560",
        category=SettingCategory.APPEARANCE,
        data_type=SettingType.COLOR,
        label="Accent Color",
        description="Primary accent color",
        order=5,
    ),

    # === Notification Settings ===
    Setting(
        key="notifications.enabled",
        value=True,
        default_value=True,
        category=SettingCategory.NOTIFICATIONS,
        data_type=SettingType.BOOLEAN,
        label="Enable Notifications",
        description="Show in-app notifications",
        order=1,
    ),
    Setting(
        key="notifications.sound",
        value=False,
        default_value=False,
        category=SettingCategory.NOTIFICATIONS,
        data_type=SettingType.BOOLEAN,
        label="Notification Sounds",
        description="Play sound for notifications",
        order=2,
    ),
    Setting(
        key="notifications.auto_dismiss",
        value=5,
        default_value=5,
        category=SettingCategory.NOTIFICATIONS,
        data_type=SettingType.INTEGER,
        label="Auto-dismiss Time",
        description="Seconds before notifications auto-dismiss (0 = never)",
        validation={"min": 0, "max": 30},
        order=3,
    ),

    # === Performance Settings ===
    Setting(
        key="performance.page_size",
        value=20,
        default_value=20,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.SELECT,
        label="Items Per Page",
        description="Number of items to show in lists",
        options=[
            {"value": 10, "label": "10"},
            {"value": 20, "label": "20"},
            {"value": 50, "label": "50"},
            {"value": 100, "label": "100"},
        ],
        order=1,
    ),
    Setting(
        key="performance.enable_caching",
        value=True,
        default_value=True,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Enable Caching",
        description="Cache data for faster loading",
        order=2,
    ),
    Setting(
        key="performance.lazy_load_images",
        value=True,
        default_value=True,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Lazy Load Images",
        description="Load images only when visible",
        order=3,
    ),

    # === Privacy Settings ===
    Setting(
        key="privacy.analytics_enabled",
        value=False,
        default_value=False,
        category=SettingCategory.PRIVACY,
        data_type=SettingType.BOOLEAN,
        label="Usage Analytics",
        description="Share anonymous usage data to improve the app",
        order=1,
    ),
    Setting(
        key="privacy.save_search_history",
        value=True,
        default_value=True,
        category=SettingCategory.PRIVACY,
        data_type=SettingType.BOOLEAN,
        label="Save Search History",
        description="Remember recent searches",
        order=2,
    ),

    # === Advanced Settings ===
    Setting(
        key="advanced.debug_mode",
        value=False,
        default_value=False,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.BOOLEAN,
        label="Debug Mode",
        description="Enable debug logging and developer tools",
        requires_restart=True,
        order=1,
    ),
    Setting(
        key="advanced.api_timeout",
        value=30,
        default_value=30,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.INTEGER,
        label="API Timeout",
        description="Seconds to wait for API responses",
        validation={"min": 5, "max": 120},
        order=2,
    ),
    Setting(
        key="advanced.max_upload_size",
        value=100,
        default_value=100,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.INTEGER,
        label="Max Upload Size (MB)",
        description="Maximum file size for uploads",
        validation={"min": 1, "max": 1000},
        order=3,
    ),
    Setting(
        key="advanced.experimental_features",
        value=False,
        default_value=False,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.BOOLEAN,
        label="Experimental Features",
        description="Enable features still in development",
        requires_restart=True,
        order=4,
    ),
]


def get_default_settings() -> list[Setting]:
    """Get a copy of all default settings."""
    return [
        Setting(
            key=s.key,
            value=s.default_value,  # Use default as current for fresh install
            default_value=s.default_value,
            category=s.category,
            data_type=s.data_type,
            label=s.label,
            description=s.description,
            validation=s.validation.copy() if s.validation else {},
            options=s.options.copy() if s.options else [],
            requires_restart=s.requires_restart,
            is_hidden=s.is_hidden,
            is_readonly=s.is_readonly,
            order=s.order,
        )
        for s in DEFAULT_SETTINGS
    ]


def get_settings_by_category(category: SettingCategory) -> list[Setting]:
    """Get default settings for a specific category."""
    return [s for s in get_default_settings() if s.category == category]
