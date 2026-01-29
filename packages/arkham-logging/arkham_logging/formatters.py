"""Log formatters for different output formats."""

import json
import logging
import re
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape codes from a string.
    
    Args:
        text: String that may contain ANSI codes
        
    Returns:
        String with ANSI codes removed
    """
    # ANSI escape sequence pattern: \x1b[ or \u001b[ followed by codes and ending with m
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\u001b\[[0-9;]*m')
    return ansi_escape.sub('', text)


class ColoredFormatter(logging.Formatter):
    """Formatter with ANSI color coding for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """Initialize colored formatter.
        
        Args:
            fmt: Format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"
        
        super().__init__(fmt, datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted string with ANSI colors
        """
        # Add color to level name
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record.levelname = f"{color}{levelname}{self.RESET}"
        
        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs JSON for structured logging."""
    
    def __init__(self):
        """Initialize structured formatter."""
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string
        """
        from datetime import timezone
        # Strip ANSI codes from levelname (in case ColoredFormatter modified it)
        clean_levelname = strip_ansi_codes(record.levelname)
        
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": clean_levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        # Add any additional fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs", "message",
                "pathname", "process", "processName", "relativeCreated", "thread",
                "threadName", "exc_info", "exc_text", "stack_info", "extra_data",
            }:
                if not key.startswith("_"):
                    log_data[key] = value
        
        return json.dumps(log_data)


class StandardFormatter(logging.Formatter):
    """Standard human-readable formatter with context."""
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """Initialize standard formatter.
        
        Args:
            fmt: Format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"
        
        super().__init__(fmt, datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted string
        """
        return super().format(record)
