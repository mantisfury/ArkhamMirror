"""
Centralized error handling for ArkhamMirror Reflex application.

Provides consistent error logging, user-friendly error messages,
and error recovery strategies.
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum

# Import config
from config.settings import DEBUG, LOGS_DIR


class ErrorSeverity(Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors for better handling."""

    DATABASE = "database"
    NETWORK = "network"
    FILE_IO = "file_io"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    PROCESSING = "processing"
    UNKNOWN = "unknown"


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{LOGS_DIR}/arkham_mirror.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("ArkhamMirror")


class ErrorHandler:
    """Centralized error handling with logging and user-friendly messages."""

    # User-friendly error messages
    ERROR_MESSAGES = {
        ErrorCategory.DATABASE: {
            "default": "Database connection issue. Please check your connection and try again.",
            "connection": "Could not connect to the database. Is PostgreSQL running?",
            "timeout": "Database query timed out. The operation may be too complex.",
            "not_found": "The requested data was not found in the database.",
        },
        ErrorCategory.NETWORK: {
            "default": "Network error occurred. Please check your connection.",
            "timeout": "Request timed out. The service may be unavailable.",
            "connection": "Could not connect to the service. Is it running?",
        },
        ErrorCategory.FILE_IO: {
            "default": "File operation failed. Please check file permissions.",
            "not_found": "File not found. Please check the path.",
            "permission": "Permission denied. Check file access rights.",
            "disk_full": "Not enough disk space to complete the operation.",
        },
        ErrorCategory.VALIDATION: {
            "default": "Invalid input. Please check your data and try again.",
            "format": "Data format is invalid. Please verify the format.",
            "required": "Required field is missing.",
        },
        ErrorCategory.PROCESSING: {
            "default": "Processing error occurred. Please try again.",
            "ocr_failed": "OCR processing failed. The document may be corrupted.",
            "embedding_failed": "Failed to generate embeddings. Check the embedding service.",
            "parsing_failed": "Document parsing failed. Format may not be supported.",
        },
        ErrorCategory.UNKNOWN: {
            "default": "An unexpected error occurred. Please try again or contact support.",
        },
    }

    @staticmethod
    def log_error(
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log an error with context and return an error ID for tracking.

        Args:
            error: The exception that occurred
            category: Category of the error
            severity: Severity level
            context: Additional context (user action, state, etc.)

        Returns:
            Error ID for tracking
        """
        error_id = f"ERR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        log_message = f"[{error_id}] {category.value.upper()}: {str(error)}"

        if context:
            log_message += f"\nContext: {context}"

        log_message += f"\nTraceback:\n{traceback.format_exc()}"

        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return error_id

    @staticmethod
    def get_user_message(
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
    ) -> str:
        """
        Get a user-friendly error message.

        Args:
            error: The exception
            category: Error category
            error_type: Specific error type within category

        Returns:
            User-friendly error message
        """
        messages = ErrorHandler.ERROR_MESSAGES.get(
            category, ErrorHandler.ERROR_MESSAGES[ErrorCategory.UNKNOWN]
        )

        message = messages.get(error_type, messages.get("default"))

        # Add technical details in development mode
        if DEBUG:
            message += f"\n\nTechnical details: {str(error)}"

        return message

    @staticmethod
    def handle_error(
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Complete error handling: log and get user message.

        Args:
            error: The exception
            category: Error category
            error_type: Specific error type
            severity: Severity level
            context: Additional context

        Returns:
            Dict with error_id and user_message
        """
        error_id = ErrorHandler.log_error(error, category, severity, context)
        user_message = ErrorHandler.get_user_message(error, category, error_type)

        return {"error_id": error_id, "message": user_message}

    @staticmethod
    def safe_execute(
        func: Callable,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
        context: Optional[Dict[str, Any]] = None,
        fallback_value: Any = None,
    ) -> Any:
        """
        Safely execute a function with error handling.

        Args:
            func: Function to execute
            category: Error category
            error_type: Specific error type
            context: Additional context
            fallback_value: Value to return on error

        Returns:
            Function result or fallback_value on error
        """
        try:
            return func()
        except Exception as e:
            ErrorHandler.handle_error(e, category, error_type, context=context)
            return fallback_value


# Convenience functions for common error categories
def handle_database_error(
    error: Exception,
    error_type: str = "default",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Handle database errors."""
    return ErrorHandler.handle_error(
        error, ErrorCategory.DATABASE, error_type, context=context
    )


def handle_network_error(
    error: Exception,
    error_type: str = "default",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Handle network errors."""
    return ErrorHandler.handle_error(
        error, ErrorCategory.NETWORK, error_type, context=context
    )


def handle_file_error(
    error: Exception,
    error_type: str = "default",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Handle file I/O errors."""
    return ErrorHandler.handle_error(
        error, ErrorCategory.FILE_IO, error_type, context=context
    )


def handle_processing_error(
    error: Exception,
    error_type: str = "default",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Handle processing errors."""
    return ErrorHandler.handle_error(
        error, ErrorCategory.PROCESSING, error_type, context=context
    )


# Error message formatter for UI
def format_error_for_ui(error_info: Dict[str, str], show_error_id: bool = True) -> str:
    """
    Format error message for display in UI.

    Args:
        error_info: Dict from handle_error with error_id and message
        show_error_id: Whether to show error ID

    Returns:
        Formatted error message
    """
    message = error_info["message"]

    if show_error_id and "error_id" in error_info:
        message += f"\n\nError ID: {error_info['error_id']}"

    return message


# Error recovery strategies
class ErrorRecovery:
    """Strategies for recovering from errors."""

    @staticmethod
    def retry_with_backoff(
        func: Callable,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
    ) -> Any:
        """
        Retry a function with exponential backoff.

        Args:
            func: Function to retry
            max_attempts: Maximum number of attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for delay after each attempt
            category: Error category for logging

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail
        """
        import time

        last_exception = None
        delay = initial_delay

        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    ErrorHandler.handle_error(
                        e,
                        category,
                        context={"attempts": max_attempts, "function": func.__name__},
                    )

        raise last_exception

    @staticmethod
    def fallback_chain(*functions: Callable) -> Any:
        """
        Try multiple functions in order until one succeeds.

        Args:
            *functions: Functions to try in order

        Returns:
            Result from first successful function

        Raises:
            Exception if all functions fail
        """
        exceptions = []

        for i, func in enumerate(functions):
            try:
                return func()
            except Exception as e:
                exceptions.append((i, func.__name__, e))
                logger.debug(f"Fallback {i + 1}/{len(functions)} failed: {str(e)}")
                continue

        # All failed - log and raise last exception
        error_msg = f"All {len(functions)} fallback options failed"
        logger.error(error_msg)
        for i, name, exc in exceptions:
            logger.error(f"  {i + 1}. {name}: {str(exc)}")

        raise exceptions[-1][2]  # Raise last exception

    @staticmethod
    def circuit_breaker(
        func: Callable,
        failure_threshold: int = 5,
        timeout: float = 60.0,
    ) -> Any:
        """
        Implement circuit breaker pattern.

        Note: This is a simplified version. For production, use a library like pybreaker.

        Args:
            func: Function to protect
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds before attempting to close circuit

        Returns:
            Function result
        """
        # This is a basic implementation - would need state management
        # for production use
        try:
            return func()
        except Exception as e:
            logger.error(f"Circuit breaker caught error: {str(e)}")
            raise


# State recovery helpers
def safe_state_update(
    state_obj, update_func: Callable, error_handler: Optional[Callable] = None
):
    """
    Safely update state with error handling.

    Args:
        state_obj: State object to update
        update_func: Function that updates the state
        error_handler: Optional custom error handler

    Returns:
        True if successful, False otherwise
    """
    try:
        update_func()
        return True
    except Exception as e:
        if error_handler:
            error_handler(e)
        else:
            error_info = ErrorHandler.handle_error(
                e,
                ErrorCategory.UNKNOWN,
                context={"state": state_obj.__class__.__name__},
            )
            logger.error(f"State update failed: {error_info['message']}")
        return False


def validate_and_execute(
    func: Callable,
    validators: list[Callable] = None,
    category: ErrorCategory = ErrorCategory.VALIDATION,
) -> Any:
    """
    Validate inputs before executing a function.

    Args:
        func: Function to execute
        validators: List of validation functions (should raise on invalid)
        category: Error category

    Returns:
        Function result
    """
    try:
        # Run validators
        if validators:
            for validator in validators:
                validator()

        # Execute function
        return func()
    except Exception as e:
        ErrorHandler.handle_error(e, category, context={"function": func.__name__})
        raise
