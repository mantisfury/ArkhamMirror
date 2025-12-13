"""Utility modules for ArkhamMirror."""

from .error_handler import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    handle_database_error,
    handle_network_error,
    handle_file_error,
    handle_processing_error,
    format_error_for_ui,
)

from .debounce import (
    debounced_handler,
    DebouncedInput,
    DebouncedState,
    create_search_debouncer,
    DEBOUNCE_FAST,
    DEBOUNCE_NORMAL,
    DEBOUNCE_SLOW,
    DEBOUNCE_VERY_SLOW,
)

__all__ = [
    # Error handling
    "ErrorHandler",
    "ErrorCategory",
    "ErrorSeverity",
    "handle_database_error",
    "handle_network_error",
    "handle_file_error",
    "handle_processing_error",
    "format_error_for_ui",
    # Debouncing
    "debounced_handler",
    "DebouncedInput",
    "DebouncedState",
    "create_search_debouncer",
    "DEBOUNCE_FAST",
    "DEBOUNCE_NORMAL",
    "DEBOUNCE_SLOW",
    "DEBOUNCE_VERY_SLOW",
]
