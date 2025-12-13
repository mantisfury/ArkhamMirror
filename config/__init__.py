"""
Central Configuration Package for ArkhamMirror.

This is the SINGLE SOURCE OF TRUTH for all environment configuration.
All modules should import from here instead of using os.getenv() directly.

Usage:
    from config import DATABASE_URL, QDRANT_URL, REDIS_URL
    from config import get_config_summary  # For debugging
"""

from .settings import (
    # Paths
    PROJECT_ROOT,
    APP_PATH,
    DOCKER_PATH,
    ARKHAM_MIRROR_PATH,
    ARKHAM_REFLEX_PATH,
    CONFIG_YAML_PATH,
    # DataSilo paths (privacy-first storage)
    DATA_SILO_PATH,
    DOCUMENTS_DIR,
    PAGES_DIR,
    LOGS_DIR,
    TEMP_DIR,
    # Database URLs
    DATABASE_URL,
    QDRANT_URL,
    REDIS_URL,
    # Individual DB settings (for when you need components)
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
    QDRANT_HOST,
    QDRANT_PORT,
    REDIS_HOST,
    REDIS_PORT,
    # LLM
    LM_STUDIO_URL,
    # Application
    BACKEND_PORT,
    FRONTEND_PORT,
    DEBUG,
    PYTHON_EXECUTABLE,
    # Functions
    get_python_executable,
    get_config_summary,
    validate_config,
)

__all__ = [
    # Paths
    "PROJECT_ROOT",
    "APP_PATH",
    "DOCKER_PATH",
    "ARKHAM_MIRROR_PATH",
    "ARKHAM_REFLEX_PATH",
    "CONFIG_YAML_PATH",
    # DataSilo paths (privacy-first storage)
    "DATA_SILO_PATH",
    "DOCUMENTS_DIR",
    "PAGES_DIR",
    "LOGS_DIR",
    "TEMP_DIR",
    # Database URLs
    "DATABASE_URL",
    "QDRANT_URL",
    "REDIS_URL",
    # Individual DB settings
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "QDRANT_HOST",
    "QDRANT_PORT",
    "REDIS_HOST",
    "REDIS_PORT",
    # LLM
    "LM_STUDIO_URL",
    # Application
    "BACKEND_PORT",
    "FRONTEND_PORT",
    "DEBUG",
    "PYTHON_EXECUTABLE",
    # Functions
    "get_python_executable",
    "get_config_summary",
    "validate_config",
]
