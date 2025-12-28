"""
ConfigService - Configuration management.
"""

import os
from typing import Any, Optional
from pathlib import Path
import yaml


class ConfigService:
    """
    Configuration management service.

    Loads config from environment variables and optional config file.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config = {}
        self._load_env()

        if config_path:
            self._load_yaml(config_path)
        elif os.environ.get("CONFIG_PATH"):
            self._load_yaml(os.environ["CONFIG_PATH"])

    def _load_env(self):
        """Load configuration from environment variables."""
        self._config["database_url"] = os.environ.get(
            "DATABASE_URL",
            "postgresql://anom:anompass@localhost:5435/anomdb"
        )
        self._config["redis_url"] = os.environ.get(
            "REDIS_URL",
            "redis://localhost:6380"
        )
        self._config["qdrant_url"] = os.environ.get(
            "QDRANT_URL",
            "http://localhost:6343"
        )
        self._config["llm_endpoint"] = os.environ.get(
            "LLM_ENDPOINT",
            os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
        )

    def _load_yaml(self, path: str):
        """Load configuration from YAML file."""
        config_file = Path(path)
        if config_file.exists():
            with open(config_file) as f:
                yaml_config = yaml.safe_load(f) or {}
                self._config.update(yaml_config)

    @property
    def database_url(self) -> str:
        return self._config.get("database_url", "")

    @property
    def redis_url(self) -> str:
        return self._config.get("redis_url", "")

    @property
    def qdrant_url(self) -> str:
        return self._config.get("qdrant_url", "")

    @property
    def llm_endpoint(self) -> str:
        return self._config.get("llm_endpoint", "")

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
