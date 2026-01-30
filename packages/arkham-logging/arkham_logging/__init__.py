"""
Arkham Logging - Comprehensive logging system for SHATTERED.

Provides structured logging, wide event logging, distributed tracing,
automatic data sanitization, and configurable sampling.
"""

__version__ = "0.1.0"

from .manager import LoggingManager, get_logger, initialize
from .wide_event import WideEvent, WideEventBuilder, create_wide_event
from .exception_handler import (
    log_operation,
    log_error_with_context,
    format_error_message,
    emit_wide_error,
)
from .tracing import TracingContext, get_trace_id, set_trace_id, generate_trace_id
from .sanitizer import DataSanitizer
from .config import LoggingConfig, load_config

__all__ = [
    "LoggingManager",
    "get_logger",
    "initialize",
    "WideEvent",
    "WideEventBuilder",
    "create_wide_event",
    "log_operation",
    "log_error_with_context",
    "format_error_message",
    "emit_wide_error",
    "TracingContext",
    "get_trace_id",
    "set_trace_id",
    "generate_trace_id",
    "DataSanitizer",
    "LoggingConfig",
    "load_config",
]
