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
# ArkhamMirror does NOT bundle an LLM. You provide your own inference.
#
# Supported providers (all use OpenAI-compatible API format):
#   - 'local'      : Local inference (LM Studio, Ollama, or vLLM) - default
#   - 'openai'     : OpenAI API (GPT-4o, etc.)
#   - 'openrouter' : OpenRouter (500+ models, single API)
#   - 'together'   : Together AI
#   - 'groq'       : Groq (fast inference)
#   - 'azure'      : Azure OpenAI
#
# For local inference, also set LLM_LOCAL_BACKEND:
#   - 'lm_studio'  : LM Studio (default, port 1234)
#   - 'ollama'     : Ollama (port 11434)
#   - 'vllm'       : vLLM (port 8001) - if you run it yourself
# =============================================================================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local").lower()

# Local backend selection (only used when LLM_PROVIDER='local')
LLM_LOCAL_BACKEND = os.getenv("LLM_LOCAL_BACKEND", "lm_studio").lower()

# -----------------------------------------------------------------------------
# Local LLM Endpoints
# -----------------------------------------------------------------------------
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001/v1")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")

# -----------------------------------------------------------------------------
# Cloud Provider API Keys (set in .env file)
# -----------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")

# -----------------------------------------------------------------------------
# Model Selection (provider-specific defaults)
# -----------------------------------------------------------------------------
LLM_MODEL = os.getenv("LLM_MODEL", "")  # Empty = use provider default

# Default models per provider (used when LLM_MODEL is not set)
LLM_DEFAULT_MODELS = {
    "local": "auto",  # Use whatever model is loaded
    "openai": "gpt-4o",
    "openrouter": "qwen/qwen3-4b",
    "together": "Qwen/Qwen3-4B",
    "groq": "llama-3.3-70b-versatile",
    "azure": "",  # Must be configured per deployment
}

# -----------------------------------------------------------------------------
# Unified LLM Configuration
# -----------------------------------------------------------------------------

def _get_llm_config() -> dict:
    """
    Build LLM configuration based on provider settings.
    Returns dict with: base_url, api_key, model, headers
    """
    provider = LLM_PROVIDER
    model = LLM_MODEL or LLM_DEFAULT_MODELS.get(provider, "")

    if provider == "local":
        # Route to appropriate local backend
        backend = LLM_LOCAL_BACKEND
        if backend == "vllm":
            base_url = VLLM_URL
        elif backend == "ollama":
            base_url = OLLAMA_URL
        else:
            base_url = LM_STUDIO_URL  # Default: LM Studio
        return {
            "base_url": base_url,
            "api_key": "not-needed",  # Local doesn't need API key
            "model": model,
            "headers": {},
        }

    elif provider == "openai":
        return {
            "base_url": "https://api.openai.com/v1",
            "api_key": OPENAI_API_KEY,
            "model": model,
            "headers": {},
        }

    elif provider == "openrouter":
        return {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": OPENROUTER_API_KEY,
            "model": model,
            "headers": {"HTTP-Referer": "https://github.com/your-repo"},  # Required by OpenRouter
        }

    elif provider == "together":
        return {
            "base_url": "https://api.together.xyz/v1",
            "api_key": TOGETHER_API_KEY,
            "model": model,
            "headers": {},
        }

    elif provider == "groq":
        return {
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": GROQ_API_KEY,
            "model": model,
            "headers": {},
        }

    elif provider == "azure":
        return {
            "base_url": AZURE_OPENAI_ENDPOINT,
            "api_key": AZURE_OPENAI_API_KEY,
            "model": model,
            "headers": {},
        }

    else:
        # Unknown provider - fall back to local LM Studio
        logger.warning(f"Unknown LLM_PROVIDER '{provider}', falling back to local")
        return {
            "base_url": LM_STUDIO_URL,
            "api_key": "not-needed",
            "model": model,
            "headers": {},
        }


# Build config on import
_LLM_CONFIG = _get_llm_config()

# Exported values for use by llm_service.py
LLM_BASE_URL = _LLM_CONFIG["base_url"]
LLM_API_KEY = _LLM_CONFIG["api_key"]
LLM_MODEL_NAME = _LLM_CONFIG["model"]
LLM_HEADERS = _LLM_CONFIG["headers"]

# Legacy compatibility (some code still uses LM_STUDIO_URL directly)
# This ensures old code continues to work
if LLM_PROVIDER == "local" and LLM_LOCAL_BACKEND != "lm_studio":
    # Update LM_STUDIO_URL to point to actual backend for legacy code
    pass  # Keep original LM_STUDIO_URL for reference

# =============================================================================
# APPLICATION PORTS
# =============================================================================

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))

# Security: Default to localhost binding (prevents LAN exposure)
# Set BACKEND_HOST=0.0.0.0 for "Team Mode" if you want LAN access on trusted networks
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")

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
        # LLM Configuration
        "LLM_PROVIDER": LLM_PROVIDER,
        "LLM_LOCAL_BACKEND": LLM_LOCAL_BACKEND,
        "LLM_BASE_URL": LLM_BASE_URL,
        "LLM_MODEL_NAME": LLM_MODEL_NAME,
        "LLM_API_KEY": "***" if LLM_API_KEY else "(not set)",
        # Local endpoints (for reference)
        "LM_STUDIO_URL": LM_STUDIO_URL,
        "VLLM_URL": VLLM_URL,
        "OLLAMA_URL": OLLAMA_URL,
        # Other
        "PYTHON_EXECUTABLE": PYTHON_EXECUTABLE,
        "BACKEND_HOST": BACKEND_HOST,
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
