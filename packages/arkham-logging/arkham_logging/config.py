"""Configuration models for arkham-logging."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
import yaml

from .utils import parse_env_bool, parse_env_float, parse_env_int, get_log_level


class OutputConfig(BaseModel):
    """Configuration for console output."""
    
    enabled: bool = Field(default=True, description="Enable console output")
    level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    format: str = Field(default="standard", description="Format: standard, json, colored")


class FileConfig(BaseModel):
    """Configuration for file output."""
    
    enabled: bool = Field(default=True, description="Enable file output")
    path: str = Field(default="logs/arkham.log", description="Path to log file")
    level: str = Field(default="DEBUG", description="Log level")
    max_bytes: int = Field(default=100_000_000, description="Max bytes per file (100MB)")
    backup_count: int = Field(default=10, description="Number of backup files to keep")
    retention_days: Optional[int] = Field(default=30, description="Days to retain logs (None = forever)")
    queue_size: int = Field(default=1000, description="Queue size for async handler")


class WideEventConfig(BaseModel):
    """Configuration for wide event logging."""
    
    enabled: bool = Field(default=True, description="Enable wide event logging")
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Sampling rate (0.0-1.0)")
    tail_sampling: bool = Field(default=True, description="Use tail sampling (sample after request completes)")
    always_sample_errors: bool = Field(default=True, description="Always sample errors")
    always_sample_slow: bool = Field(default=True, description="Always sample slow requests")
    slow_threshold_ms: int = Field(default=2000, description="Slow request threshold in milliseconds")
    always_sample_users: List[str] = Field(default_factory=list, description="User IDs to always sample")
    always_sample_projects: List[str] = Field(default_factory=list, description="Project IDs to always sample")


class LoggingConfig(BaseModel):
    """Complete logging configuration."""
    
    console: OutputConfig = Field(default_factory=OutputConfig)
    file: FileConfig = Field(default_factory=FileConfig)
    error_file: Optional[FileConfig] = Field(default=None, description="Separate error log file")
    wide_events: WideEventConfig = Field(default_factory=WideEventConfig)
    global_level: str = Field(default="INFO", description="Global log level")
    
    @classmethod
    def from_dict(cls, data: dict) -> "LoggingConfig":
        """Create config from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_yaml(cls, path: str) -> "LoggingConfig":
        """Load config from YAML file."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()  # Return defaults
        
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f) or {}
        
        # Extract logging config from nested structure
        logging_data = yaml_data.get("frame", {}).get("logging", {})
        return cls.from_dict(logging_data)
    
    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load config from environment variables."""
        config = cls()
        
        # Global level
        if os.environ.get("ARKHAM_LOG_LEVEL"):
            config.global_level = os.environ["ARKHAM_LOG_LEVEL"]
        
        # Console config
        if os.environ.get("ARKHAM_LOG_CONSOLE_ENABLED") is not None:
            config.console.enabled = parse_env_bool(os.environ.get("ARKHAM_LOG_CONSOLE_ENABLED"))
        if os.environ.get("ARKHAM_LOG_CONSOLE_LEVEL"):
            config.console.level = os.environ["ARKHAM_LOG_CONSOLE_LEVEL"]
        if os.environ.get("ARKHAM_LOG_CONSOLE_FORMAT"):
            config.console.format = os.environ["ARKHAM_LOG_CONSOLE_FORMAT"]
        
        # File config
        if os.environ.get("ARKHAM_LOG_FILE_ENABLED") is not None:
            config.file.enabled = parse_env_bool(os.environ.get("ARKHAM_LOG_FILE_ENABLED"))
        if os.environ.get("ARKHAM_LOG_FILE_PATH"):
            config.file.path = os.environ["ARKHAM_LOG_FILE_PATH"]
        if os.environ.get("ARKHAM_LOG_FILE_LEVEL"):
            config.file.level = os.environ["ARKHAM_LOG_FILE_LEVEL"]
        if os.environ.get("ARKHAM_LOG_FILE_MAX_BYTES"):
            config.file.max_bytes = parse_env_int(os.environ.get("ARKHAM_LOG_FILE_MAX_BYTES"))
        if os.environ.get("ARKHAM_LOG_FILE_BACKUP_COUNT"):
            config.file.backup_count = parse_env_int(os.environ.get("ARKHAM_LOG_FILE_BACKUP_COUNT"))
        if os.environ.get("ARKHAM_LOG_FILE_RETENTION_DAYS"):
            retention = os.environ.get("ARKHAM_LOG_FILE_RETENTION_DAYS")
            config.file.retention_days = parse_env_int(retention) if retention else None
        
        # Error file config
        if os.environ.get("ARKHAM_LOG_ERROR_FILE_ENABLED") is not None:
            if config.error_file is None:
                config.error_file = FileConfig()
            config.error_file.enabled = parse_env_bool(os.environ.get("ARKHAM_LOG_ERROR_FILE_ENABLED"))
        if os.environ.get("ARKHAM_LOG_ERROR_FILE_PATH"):
            if config.error_file is None:
                config.error_file = FileConfig()
            config.error_file.path = os.environ["ARKHAM_LOG_ERROR_FILE_PATH"]
        
        # Wide events config
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_ENABLED") is not None:
            config.wide_events.enabled = parse_env_bool(os.environ.get("ARKHAM_LOG_WIDE_EVENTS_ENABLED"))
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SAMPLING_RATE"):
            config.wide_events.sampling_rate = parse_env_float(os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SAMPLING_RATE"))
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SLOW_THRESHOLD_MS"):
            config.wide_events.slow_threshold_ms = parse_env_int(os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SLOW_THRESHOLD_MS"))
        
        return config
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "LoggingConfig":
        """Load configuration from multiple sources (priority: env vars > YAML > defaults).
        
        Args:
            config_path: Optional path to YAML config file
            
        Returns:
            LoggingConfig instance
        """
        # Start with defaults
        config = cls()
        
        # Load from YAML if provided
        if config_path:
            try:
                yaml_config = cls.from_yaml(config_path)
                # Merge YAML config (YAML takes precedence over defaults)
                config = yaml_config
            except Exception:
                pass  # Fall back to defaults if YAML fails
        
        # Override with environment variables (env vars take highest precedence)
        env_config = cls.from_env()
        
        # Merge env config into base config
        if env_config.global_level != "INFO":
            config.global_level = env_config.global_level
        
        # When only ARKHAM_LOG_LEVEL is set, apply it to console too (single env var for console level)
        if os.environ.get("ARKHAM_LOG_LEVEL") and not os.environ.get("ARKHAM_LOG_CONSOLE_LEVEL"):
            config.console.level = config.global_level
        
        # Merge console config
        if os.environ.get("ARKHAM_LOG_CONSOLE_ENABLED") is not None:
            config.console.enabled = env_config.console.enabled
        if os.environ.get("ARKHAM_LOG_CONSOLE_LEVEL"):
            config.console.level = env_config.console.level
        if os.environ.get("ARKHAM_LOG_CONSOLE_FORMAT"):
            config.console.format = env_config.console.format
        
        # Merge file config
        if os.environ.get("ARKHAM_LOG_FILE_ENABLED") is not None:
            config.file.enabled = env_config.file.enabled
        if os.environ.get("ARKHAM_LOG_FILE_PATH"):
            config.file.path = env_config.file.path
        if os.environ.get("ARKHAM_LOG_FILE_LEVEL"):
            config.file.level = env_config.file.level
        if os.environ.get("ARKHAM_LOG_FILE_MAX_BYTES"):
            config.file.max_bytes = env_config.file.max_bytes
        if os.environ.get("ARKHAM_LOG_FILE_BACKUP_COUNT"):
            config.file.backup_count = env_config.file.backup_count
        if os.environ.get("ARKHAM_LOG_FILE_RETENTION_DAYS"):
            config.file.retention_days = env_config.file.retention_days
        
        # Merge error file config
        if os.environ.get("ARKHAM_LOG_ERROR_FILE_ENABLED") is not None:
            if config.error_file is None:
                config.error_file = FileConfig()
            config.error_file.enabled = env_config.error_file.enabled if env_config.error_file else True
        if os.environ.get("ARKHAM_LOG_ERROR_FILE_PATH"):
            if config.error_file is None:
                config.error_file = FileConfig()
            config.error_file.path = env_config.error_file.path if env_config.error_file else "logs/errors.log"
        
        # Merge wide events config
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_ENABLED") is not None:
            config.wide_events.enabled = env_config.wide_events.enabled
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SAMPLING_RATE"):
            config.wide_events.sampling_rate = env_config.wide_events.sampling_rate
        if os.environ.get("ARKHAM_LOG_WIDE_EVENTS_SLOW_THRESHOLD_MS"):
            config.wide_events.slow_threshold_ms = env_config.wide_events.slow_threshold_ms
        
        return config


# Convenience function
def load_config(config_path: Optional[str] = None) -> LoggingConfig:
    """Load logging configuration.
    
    Args:
        config_path: Optional path to YAML config file
        
    Returns:
        LoggingConfig instance
    """
    return LoggingConfig.load(config_path)
