"""
ConfigService - Configuration management.
"""

import os
from typing import Any, Optional
from pathlib import Path
import yaml


def is_running_in_docker() -> bool:
    """Detect if we're running inside a Docker container."""
    # Check for .dockerenv file (most reliable)
    if Path("/.dockerenv").exists():
        return True
    # Check cgroup (Linux containers)
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except (FileNotFoundError, PermissionError):
        pass
    # Check environment variable (explicit override)
    return os.environ.get("RUNNING_IN_DOCKER", "").lower() in ("true", "1", "yes")


def transform_localhost_for_docker(url: str) -> str:
    """Transform localhost URLs to host.docker.internal when in Docker."""
    if not is_running_in_docker():
        return url
    # Replace localhost and 127.0.0.1 with host.docker.internal
    return url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")


class ConfigService:
    """
    Configuration management service.

    Loads config from environment variables and optional config file.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config = {}
        self._is_docker = is_running_in_docker()
        self._load_env()

        if config_path:
            self._load_yaml(config_path)
        elif os.environ.get("CONFIG_PATH"):
            self._load_yaml(os.environ["CONFIG_PATH"])

    def _load_env(self):
        """Load configuration from environment variables."""
        # PostgreSQL database (includes pgvector for vectors and job queue)
        self._config["database_url"] = os.environ.get(
            "DATABASE_URL",
            "postgresql://arkham:arkhampass@localhost:5432/arkhamdb"
        )
        # LLM endpoint (LM Studio, Ollama, OpenAI-compatible)
        self._config["llm_endpoint"] = os.environ.get(
            "LLM_ENDPOINT",
            os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
        )
        # VLM endpoint for vision tasks (OCR)
        self._config["vlm_endpoint"] = os.environ.get("VLM_ENDPOINT", "")
        # Embedding model name
        self._config["embed_model"] = os.environ.get("EMBED_MODEL", "")

        # Air-gap / offline mode - prevents auto-downloading ML models
        self._config["offline_mode"] = os.environ.get(
            "ARKHAM_OFFLINE_MODE", ""
        ).lower() in ("true", "1", "yes")

        # Model cache path (for pre-cached models in air-gap deployments)
        self._config["model_cache_path"] = os.environ.get(
            "ARKHAM_MODEL_CACHE",
            os.environ.get("HF_HOME", "")
        )

    def _load_yaml(self, path: str):
        """Load configuration from YAML file."""
        config_file = Path(path)
        if config_file.exists():
            with open(config_file) as f:
                yaml_config = yaml.safe_load(f) or {}
                self._config.update(yaml_config)

    @property
    def is_docker(self) -> bool:
        """Return whether we're running inside Docker."""
        return self._is_docker

    @property
    def database_url(self) -> str:
        return self._config.get("database_url", "")

    @property
    def llm_endpoint(self) -> str:
        return self._config.get("llm_endpoint", "")

    @property
    def vlm_endpoint(self) -> str:
        return self._config.get("vlm_endpoint", "")

    @property
    def embed_model(self) -> str:
        return self._config.get("embed_model", "")

    @property
    def offline_mode(self) -> bool:
        """Return whether offline/air-gap mode is enabled."""
        return self._config.get("offline_mode", False)

    @property
    def model_cache_path(self) -> str:
        """Return the model cache path for pre-cached ML models."""
        return self._config.get("model_cache_path", "")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-notation key."""
        parts = key.split(".")
        value = self._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value."""
        parts = key.split(".")
        config = self._config

        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]

        config[parts[-1]] = value

    def get_local_llm_default(self) -> str:
        """Get the appropriate default LLM endpoint for local providers."""
        if self._is_docker:
            return "http://host.docker.internal:1234/v1"
        return "http://localhost:1234/v1"

    def get_local_ollama_default(self) -> str:
        """Get the appropriate default Ollama endpoint."""
        if self._is_docker:
            return "http://host.docker.internal:11434/v1"
        return "http://localhost:11434/v1"
