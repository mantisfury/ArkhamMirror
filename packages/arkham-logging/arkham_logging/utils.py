"""Utility functions for arkham-logging."""

import os
from pathlib import Path
from typing import Optional


def ensure_log_directory(log_path: str) -> Path:
    """Ensure the log directory exists.
    
    Args:
        log_path: Path to log file (may be relative or absolute)
        
    Returns:
        Path object for the log file
    """
    log_file = Path(log_path)
    log_dir = log_file.parent
    
    # Create directory if it doesn't exist
    if log_dir and not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    
    return log_file


def get_log_level(level_str: str) -> int:
    """Convert log level string to logging constant.
    
    Args:
        level_str: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Logging level constant
    """
    import logging
    
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    return level_map.get(level_str.upper(), logging.INFO)


def parse_env_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse boolean from environment variable.
    
    Args:
        value: Environment variable value
        default: Default value if not set
        
    Returns:
        Boolean value
    """
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def parse_env_float(value: Optional[str], default: float = 0.0) -> float:
    """Parse float from environment variable.
    
    Args:
        value: Environment variable value
        default: Default value if not set
        
    Returns:
        Float value
    """
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_env_int(value: Optional[str], default: int = 0) -> int:
    """Parse int from environment variable.
    
    Args:
        value: Environment variable value
        default: Default value if not set
        
    Returns:
        Integer value
    """
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
