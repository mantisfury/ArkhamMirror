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
        key="general.start_page",
        value="/dashboard",
        default_value="/dashboard",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Start Page",
        description="Page to show when opening the application",
        options=[
            {"value": "/dashboard", "label": "Dashboard"},
            {"value": "/documents", "label": "Documents"},
            {"value": "/ingest", "label": "Ingest"},
            {"value": "/search", "label": "Search"},
            {"value": "/entities", "label": "Entities"},
            {"value": "/timeline", "label": "Timeline"},
            {"value": "/projects", "label": "Projects"},
        ],
        order=2,
    ),
    Setting(
        key="general.default_project",
        value="",
        default_value="",
        category=SettingCategory.GENERAL,
        data_type=SettingType.STRING,
        label="Default Project",
        description="Project to load on startup (leave empty for none). Set via Projects page.",
        is_readonly=True,
        order=3,
    ),
    Setting(
        key="general.recent_items_count",
        value=10,
        default_value=10,
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Recent Items",
        description="Number of recent items to show in lists and menus",
        options=[
            {"value": 5, "label": "5"},
            {"value": 10, "label": "10"},
            {"value": 15, "label": "15"},
            {"value": 20, "label": "20"},
        ],
        order=4,
    ),
    Setting(
        key="general.timezone",
        value="UTC",
        default_value="UTC",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Timezone",
        description="Timezone for displaying dates and timestamps",
        options=[
            {"value": "UTC", "label": "UTC"},
            {"value": "America/New_York", "label": "Eastern Time (US)"},
            {"value": "America/Chicago", "label": "Central Time (US)"},
            {"value": "America/Denver", "label": "Mountain Time (US)"},
            {"value": "America/Los_Angeles", "label": "Pacific Time (US)"},
            {"value": "Europe/London", "label": "London (UK)"},
            {"value": "Europe/Paris", "label": "Paris (EU)"},
            {"value": "Europe/Berlin", "label": "Berlin (EU)"},
            {"value": "Asia/Tokyo", "label": "Tokyo (Japan)"},
            {"value": "Asia/Shanghai", "label": "Shanghai (China)"},
            {"value": "Australia/Sydney", "label": "Sydney (Australia)"},
        ],
        order=5,
    ),
    Setting(
        key="general.date_format",
        value="YYYY-MM-DD",
        default_value="YYYY-MM-DD",
        category=SettingCategory.GENERAL,
        data_type=SettingType.SELECT,
        label="Date Format",
        description="How dates are displayed throughout the application",
        options=[
            {"value": "YYYY-MM-DD", "label": "2024-12-27 (ISO)"},
            {"value": "MM/DD/YYYY", "label": "12/27/2024 (US)"},
            {"value": "DD/MM/YYYY", "label": "27/12/2024 (EU)"},
            {"value": "MMM DD, YYYY", "label": "Dec 27, 2024"},
            {"value": "DD MMM YYYY", "label": "27 Dec 2024"},
        ],
        order=6,
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
        key="performance.table_virtualization",
        value=True,
        default_value=True,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Table Virtualization",
        description="Only render visible rows for large datasets (improves performance)",
        order=2,
    ),
    Setting(
        key="performance.reduce_motion",
        value=False,
        default_value=False,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Reduce Motion",
        description="Minimize animations and transitions",
        order=3,
    ),
    Setting(
        key="performance.enable_caching",
        value=True,
        default_value=True,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Enable Caching",
        description="Cache data for faster loading (placeholder - future feature)",
        order=4,
    ),
    Setting(
        key="performance.lazy_load_images",
        value=True,
        default_value=True,
        category=SettingCategory.PERFORMANCE,
        data_type=SettingType.BOOLEAN,
        label="Lazy Load Images",
        description="Load images only when visible (placeholder - future feature)",
        order=5,
    ),

    # === Data Management Settings ===
    # Note: These are informational settings. The actual actions (clear, reset, export)
    # are performed via the custom Data Management UI, not by changing these values.
    Setting(
        key="data.retention_days",
        value=0,
        default_value=0,
        category=SettingCategory.DATA,
        data_type=SettingType.SELECT,
        label="Auto-Delete Old Data",
        description="Automatically remove data older than this (0 = never)",
        options=[
            {"value": 0, "label": "Never"},
            {"value": 30, "label": "30 days"},
            {"value": 90, "label": "90 days"},
            {"value": 180, "label": "6 months"},
            {"value": 365, "label": "1 year"},
        ],
        order=1,
    ),
    Setting(
        key="data.confirm_destructive",
        value=True,
        default_value=True,
        category=SettingCategory.DATA,
        data_type=SettingType.BOOLEAN,
        label="Confirm Destructive Actions",
        description="Show confirmation dialog before clearing or deleting data",
        order=2,
    ),

    # === Advanced Settings ===
    # --- Timeouts ---
    Setting(
        key="advanced.api_timeout",
        value=30,
        default_value=30,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="API Request Timeout",
        description="Seconds to wait for API responses before timing out",
        options=[
            {"value": 15, "label": "15 seconds - Fast timeout"},
            {"value": 30, "label": "30 seconds - Default"},
            {"value": 60, "label": "60 seconds - Slow connections"},
            {"value": 120, "label": "2 minutes - Very slow"},
        ],
        order=1,
    ),
    Setting(
        key="advanced.llm_timeout",
        value=120,
        default_value=120,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="LLM Request Timeout",
        description="Seconds to wait for AI model responses (analysis, enrichment)",
        options=[
            {"value": 60, "label": "1 minute - Quick responses"},
            {"value": 120, "label": "2 minutes - Default"},
            {"value": 180, "label": "3 minutes - Complex analysis"},
            {"value": 300, "label": "5 minutes - Very complex"},
        ],
        order=2,
    ),
    Setting(
        key="advanced.worker_timeout",
        value=300,
        default_value=300,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Worker Job Timeout",
        description="Maximum seconds for background jobs (parsing, embedding, OCR)",
        options=[
            {"value": 120, "label": "2 minutes - Fast jobs only"},
            {"value": 300, "label": "5 minutes - Default"},
            {"value": 600, "label": "10 minutes - Large documents"},
            {"value": 900, "label": "15 minutes - Very large files"},
        ],
        order=3,
    ),

    # --- Storage ---
    Setting(
        key="storage.max_file_size_mb",
        value=100,
        default_value=100,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Max Upload Size",
        description="Maximum file size for document uploads",
        options=[
            {"value": 50, "label": "50 MB"},
            {"value": 100, "label": "100 MB"},
            {"value": 250, "label": "250 MB"},
            {"value": 500, "label": "500 MB"},
            {"value": 1000, "label": "1 GB"},
        ],
        order=4,
    ),
    Setting(
        key="storage.cleanup_temp_after_hours",
        value=24,
        default_value=24,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Temp File Cleanup",
        description="Hours before temporary files are automatically deleted",
        options=[
            {"value": 1, "label": "1 hour"},
            {"value": 6, "label": "6 hours"},
            {"value": 24, "label": "24 hours"},
            {"value": 72, "label": "3 days"},
            {"value": 168, "label": "1 week"},
        ],
        order=5,
    ),

    # --- Resources ---
    Setting(
        key="advanced.enable_gpu",
        value=True,
        default_value=True,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.BOOLEAN,
        label="Enable GPU Acceleration",
        description="Use GPU for OCR, embeddings, and transcription when available",
        requires_restart=True,
        order=6,
    ),
    Setting(
        key="advanced.worker_profile",
        value="balanced",
        default_value="balanced",
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Worker Resource Profile",
        description="How many concurrent workers to run (affects memory and CPU usage)",
        options=[
            {"value": "minimal", "label": "Minimal - Low resource usage, slower processing"},
            {"value": "balanced", "label": "Balanced - Default for most systems"},
            {"value": "performance", "label": "Performance - Higher resource usage, faster processing"},
        ],
        requires_restart=True,
        order=7,
    ),
    Setting(
        key="advanced.max_concurrent_llm",
        value=4,
        default_value=4,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Max Concurrent LLM Requests",
        description="Maximum parallel AI model requests (higher uses more API quota)",
        options=[
            {"value": 1, "label": "1 - Sequential, lowest cost"},
            {"value": 2, "label": "2 - Light parallelism"},
            {"value": 4, "label": "4 - Default"},
            {"value": 8, "label": "8 - Fast processing, higher cost"},
        ],
        order=8,
    ),

    # --- Developer ---
    Setting(
        key="advanced.log_level",
        value="info",
        default_value="info",
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Log Level",
        description="Verbosity of console and file logging",
        options=[
            {"value": "error", "label": "Error - Errors only"},
            {"value": "warn", "label": "Warning - Warnings and errors"},
            {"value": "info", "label": "Info - Normal operation"},
            {"value": "debug", "label": "Debug - Verbose debugging"},
        ],
        requires_restart=True,
        order=9,
    ),
    Setting(
        key="advanced.show_dev_tools",
        value=False,
        default_value=False,
        category=SettingCategory.ADVANCED,
        data_type=SettingType.BOOLEAN,
        label="Show Developer Tools",
        description="Display additional debugging information in the UI",
        order=10,
    ),

    # --- Embedding Model ---
    Setting(
        key="advanced.embedding_model",
        value="BAAI/bge-m3",
        default_value="BAAI/bge-m3",
        category=SettingCategory.ADVANCED,
        data_type=SettingType.SELECT,
        label="Embedding Model",
        description=(
            "Model for semantic text embeddings (vector search). "
            "WARNING: Changing models after storing vectors requires rebuilding vector collections!"
        ),
        options=[
            {"value": "BAAI/bge-m3", "label": "BGE-M3 (1024-dim, multilingual) - Default"},
            {"value": "BAAI/bge-large-en-v1.5", "label": "BGE-Large-EN (1024-dim, English)"},
            {"value": "BAAI/bge-base-en-v1.5", "label": "BGE-Base-EN (768-dim)"},
            {"value": "sentence-transformers/all-MiniLM-L6-v2", "label": "MiniLM-L6 (384-dim, fast, lightweight)"},
            {"value": "sentence-transformers/all-mpnet-base-v2", "label": "MPNet-Base (768-dim, balanced)"},
        ],
        requires_restart=True,
        order=11,
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
