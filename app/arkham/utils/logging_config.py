"""
Comprehensive logging configuration for ArkhamMirror Reflex.

Provides structured logging with:
- File rotation (100MB max per file, keep 10 backups)
- Console output with color coding
- Separate error log
- Request/response logging
- Performance timing
- Structured JSON format option
"""

import logging
import logging.handlers
import sys
import os

from datetime import datetime
import json
import traceback
from typing import Any, Dict, Optional
import functools
import time

# Add project root to path for central config
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)
from config import LOGS_DIR

# Create logs directory
LOGS_DIR.mkdir(exist_ok=True)

# Log files
MAIN_LOG = LOGS_DIR / "arkham_mirror.log"
ERROR_LOG = LOGS_DIR / "errors.log"
REQUESTS_LOG = LOGS_DIR / "requests.log"
PERFORMANCE_LOG = LOGS_DIR / "performance.log"


class ColoredFormatter(logging.Formatter):
    """Formatter with color coding for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Formatter that outputs JSON for structured logging."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    enable_console: bool = True,
    enable_json: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to output to console
        enable_json: Whether to use JSON format for file logs
    """
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Standard format
    standard_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console handler with colors
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(standard_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Main log file (rotating)
    main_handler = logging.handlers.RotatingFileHandler(
        MAIN_LOG,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=10,
        encoding="utf-8",
    )
    main_handler.setLevel(logging.DEBUG)

    if enable_json:
        main_formatter = JSONFormatter()
    else:
        main_formatter = logging.Formatter(standard_format, datefmt=date_format)

    main_handler.setFormatter(main_formatter)
    root_logger.addHandler(main_handler)

    # Error log file (errors only, rotating)
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(standard_format, datefmt=date_format))
    root_logger.addHandler(error_handler)

    # Log startup
    logging.info("=" * 80)
    logging.info("ArkhamMirror Reflex Logging System Initialized")
    logging.info(f"Log Level: {level}")
    logging.info(f"Main Log: {MAIN_LOG}")
    logging.info(f"Error Log: {ERROR_LOG}")
    logging.info("=" * 80)


def get_request_logger() -> logging.Logger:
    """Get a logger for HTTP requests."""
    logger = logging.getLogger("arkham.requests")

    # Add dedicated request log handler if not already added
    if not any(
        h.baseFilename == str(REQUESTS_LOG)
        for h in logger.handlers
        if hasattr(h, "baseFilename")
    ):
        request_handler = logging.handlers.RotatingFileHandler(
            REQUESTS_LOG,
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        request_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(request_handler)

    return logger


def get_performance_logger() -> logging.Logger:
    """Get a logger for performance metrics."""
    logger = logging.getLogger("arkham.performance")

    # Add dedicated performance log handler if not already added
    if not any(
        h.baseFilename == str(PERFORMANCE_LOG)
        for h in logger.handlers
        if hasattr(h, "baseFilename")
    ):
        perf_handler = logging.handlers.RotatingFileHandler(
            PERFORMANCE_LOG,
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        perf_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(perf_handler)

    return logger


def log_exception(
    logger: logging.Logger, exc: Exception, context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with full traceback and context.

    Args:
        logger: Logger instance
        exc: Exception to log
        context: Additional context information
    """
    logger.error(
        f"Exception occurred: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={"extra_data": context} if context else None,
    )


def timed(func):
    """Decorator to log function execution time."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        perf_logger = get_performance_logger()
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.time() - start_time
            perf_logger.info(
                f"{func.__module__}.{func.__name__} completed in {elapsed:.3f}s"
            )

    return wrapper


def log_state_event(
    state_class: str, event: str, data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a Reflex state event.

    Args:
        state_class: Name of the state class
        event: Event name
        data: Event data
    """
    logger = logging.getLogger("arkham.state")
    msg = f"State Event: {state_class}.{event}"
    if data:
        msg += f" | Data: {data}"
    logger.debug(msg)


def log_service_call(
    service: str,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    result: str = "success",
) -> None:
    """
    Log a service layer call.

    Args:
        service: Service name
        method: Method name
        params: Call parameters
        result: Call result (success/failure)
    """
    logger = logging.getLogger("arkham.service")
    msg = f"Service Call: {service}.{method} | Result: {result}"
    if params:
        msg += f" | Params: {params}"
    logger.info(msg)


# Initialize on module import
setup_logging()
