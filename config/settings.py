"""
Central configuration for ArkhamMirror.

This module is the SINGLE SOURCE OF TRUTH for all environment configuration.
All other modules should import from here instead of using os.getenv() directly.

Standard Values (from docker-compose.yml):
- PostgreSQL: External 5435 -> Internal 5432, user=anom, pass=anompass, db=anomdb
- Qdrant: External 6343 (HTTP) -> Internal 6333
- Redis: External 6380 -> Internal 6379
- LM Studio: http://localhost:1234/v1
- Backend: port 8000
- Frontend: port 3000
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# PATH RESOLUTION
# =============================================================================


def _find_project_root() -> Path:
    """
    Find the project root by looking for marker files.

    Searches upward from this file's location for CLAUDE.md, GEMINI.md, or .git.
    This works correctly in git worktrees and different directory structures.
    """
    current = Path(__file__).resolve()

    # Walk up looking for marker files
    for parent in [current] + list(current.parents):
        if (
            (parent / "CLAUDE.md").exists()
            or (parent / "GEMINI.md").exists()
            or (parent / ".git").exists()
        ):
            return parent

    # Fallback: assume standard structure (config is in project_root/config/)
    return Path(__file__).parent.parent


PROJECT_ROOT = _find_project_root()

# New consolidated paths (Phase 2 migration)
APP_PATH = PROJECT_ROOT / "app"
DOCKER_PATH = PROJECT_ROOT / "docker"

# Legacy paths (kept for reference but no longer needed for runtime)
# DEPRECATED: These directories have been archived
ARKHAM_MIRROR_PATH = PROJECT_ROOT / "arkham_mirror"  # Archived
ARKHAM_REFLEX_PATH = PROJECT_ROOT / "arkham_reflex"  # Archived

# =============================================================================
# .ENV LOADING
# =============================================================================


def _load_env_files():
    """
    Load .env files in priority order.

    Priority (first found wins):
    1. arkham_reflex/.env (current active frontend)
    2. PROJECT_ROOT/.env (recommended canonical location)

    Note: arkham_mirror/.env is NOT loaded as that's the deprecated Streamlit path.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning(
            "python-dotenv not installed. Environment variables must be set externally."
        )
        return

    env_locations = [
        APP_PATH / ".env",  # New consolidated location
        ARKHAM_REFLEX_PATH / ".env",  # Legacy
        PROJECT_ROOT / ".env",
    ]

    loaded = False
    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from: {env_path}")
            loaded = True
            break

    if not loaded:
        logger.debug(
            "No .env file found. Using defaults (this is OK if env vars are set externally)."
        )


_load_env_files()

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# PostgreSQL - matches docker-compose.yml (external port 5435 -> internal 5432)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5435")
POSTGRES_USER = os.getenv("POSTGRES_USER", "anom")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "anompass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "anomdb")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# Qdrant - matches docker-compose.yml (external 6343 -> internal 6333)
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", "6343")
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")

# Redis - matches docker-compose.yml (external 6380 -> internal 6379)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6380")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}")

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

# Unified LLM URL - consolidate LM_STUDIO_URL and LLM_BASE_URL into one
# Check LM_STUDIO_URL first (preferred), then LLM_BASE_URL (legacy), then default
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL") or os.getenv(
    "LLM_BASE_URL", "http://localhost:1234/v1"
)

# =============================================================================
# APPLICATION PORTS
# =============================================================================

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# =============================================================================
# DATA SILO (Privacy-First Storage)
# =============================================================================
# All user data is consolidated here for easy backup, wipe, and privacy control.
# See onboard.md for design rationale.

DATA_SILO_PATH = PROJECT_ROOT / "DataSilo"
DOCUMENTS_DIR = DATA_SILO_PATH / "documents"
PAGES_DIR = DATA_SILO_PATH / "pages"

# =============================================================================
# PYTHON ENVIRONMENT
# =============================================================================


def get_python_executable() -> str:
    """
    Get the Python executable, preferring venv if available.

    Search order:
    1. arkham_mirror/venv (Windows with .exe)
    2. arkham_mirror/venv (Windows without .exe - edge case)
    3. project_root/venv (Windows with .exe)
    4. project_root/venv (Windows without .exe)
    5. arkham_mirror/venv (Unix)
    6. project_root/venv (Unix)
    7. Current Python interpreter (sys.executable)
    """
    # Windows paths to check
    windows_paths = [
        ARKHAM_MIRROR_PATH / "venv" / "Scripts" / "python.exe",
        ARKHAM_MIRROR_PATH / "venv" / "Scripts" / "python",  # Edge case
        PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / "venv" / "Scripts" / "python",  # Edge case
    ]

    # Unix paths to check
    unix_paths = [
        ARKHAM_MIRROR_PATH / "venv" / "bin" / "python",
        PROJECT_ROOT / "venv" / "bin" / "python",
    ]

    # Try all paths
    for venv_python in windows_paths + unix_paths:
        if venv_python.exists():
            return str(venv_python)

    # Fall back to current Python
    return sys.executable


PYTHON_EXECUTABLE = get_python_executable()

# =============================================================================
# DERIVED PATHS
# =============================================================================

CONFIG_YAML_PATH = APP_PATH / "config.yaml"  # Consolidated location

# DataSilo directories (consolidated user data)
LOGS_DIR = DATA_SILO_PATH / "logs"
TEMP_DIR = DATA_SILO_PATH / "temp"

# Ensure all DataSilo directories exist (safe to do on import)
for _dir in [DATA_SILO_PATH, DOCUMENTS_DIR, PAGES_DIR, LOGS_DIR, TEMP_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# =============================================================================
# VALIDATION
# =============================================================================


def validate_config() -> list[str]:
    """
    Validate configuration and return list of warnings.

    This does NOT raise exceptions - it just returns warnings.
    Connection failures will occur at runtime when actually trying to connect.
    """
    warnings = []

    if not CONFIG_YAML_PATH.exists():
        warnings.append(f"config.yaml not found: {CONFIG_YAML_PATH}")

    # No longer warn about legacy ARKHAM_MIRROR_PATH - it's been archived

    return warnings


# Run validation on import (log warnings only)
_warnings = validate_config()
for w in _warnings:
    logger.warning(w)

# =============================================================================
# DEBUG INFO
# =============================================================================


def get_config_summary() -> dict:
    """
    Return a summary of current configuration for debugging.

    Use this in startup logs or diagnostic endpoints.
    Password is masked for security.
    """
    return {
        "PROJECT_ROOT": str(PROJECT_ROOT),
        "APP_PATH": str(APP_PATH),
        "DOCKER_PATH": str(DOCKER_PATH),
        "ARKHAM_MIRROR_PATH": str(ARKHAM_MIRROR_PATH),
        "ARKHAM_REFLEX_PATH": str(ARKHAM_REFLEX_PATH),
        "DATA_SILO_PATH": str(DATA_SILO_PATH),
        "DOCUMENTS_DIR": str(DOCUMENTS_DIR),
        "PAGES_DIR": str(PAGES_DIR),
        "DATABASE_URL": DATABASE_URL.replace(POSTGRES_PASSWORD, "***"),
        "QDRANT_URL": QDRANT_URL,
        "REDIS_URL": REDIS_URL,
        "LM_STUDIO_URL": LM_STUDIO_URL,
        "PYTHON_EXECUTABLE": PYTHON_EXECUTABLE,
        "BACKEND_PORT": BACKEND_PORT,
        "FRONTEND_PORT": FRONTEND_PORT,
        "CONFIG_YAML_PATH": str(CONFIG_YAML_PATH),
        "LOGS_DIR": str(LOGS_DIR),
        "TEMP_DIR": str(TEMP_DIR),
    }


# =============================================================================
# DOCKER UTILITIES
# =============================================================================


def get_postgres_container_name() -> Optional[str]:
    """
    Get the PostgreSQL container name dynamically.

    This avoids hardcoding 'arkham_mirror-postgres-1' which can change.
    Returns None if Docker is not available or container not found.
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=postgres:15",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Return first matching container
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
