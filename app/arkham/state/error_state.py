"""
Error state mixin for Reflex state classes.

Provides standardized error handling, recovery, and logging
for all state classes.
"""

import reflex as rx
from typing import Optional, Callable, Any
from ..utils.error_handler import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    format_error_for_ui,
)


class ErrorStateMixin(rx.State):
    """
    Mixin class providing error handling capabilities to state classes.

    Add this to your state class to get standardized error handling:
        class MyState(ErrorStateMixin, rx.State):
            ...
    """

    # Error tracking
    has_error: bool = False
    error_message: str = ""
    error_id: str = ""
    error_severity: str = "error"  # error, warning, info

    # Loading states
    is_loading: bool = False
    is_retrying: bool = False

    def set_error(
        self,
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[dict] = None,
    ):
        """
        Set error state with proper logging.

        Args:
            error: The exception that occurred
            category: Error category
            error_type: Specific error type
            severity: Error severity
            context: Additional context
        """
        # Merge context with state info
        full_context = context or {}
        full_context["state_class"] = self.__class__.__name__

        # Log and get user message
        error_info = ErrorHandler.handle_error(
            error, category, error_type, severity, full_context
        )

        # Update state
        self.has_error = True
        self.error_message = error_info["message"]
        self.error_id = error_info["error_id"]
        self.error_severity = severity.value
        self.is_loading = False

    def clear_error(self):
        """Clear error state."""
        self.has_error = False
        self.error_message = ""
        self.error_id = ""
        self.error_severity = "error"

    def set_loading(self, loading: bool = True):
        """Set loading state and optionally clear errors."""
        self.is_loading = loading
        if loading:
            self.clear_error()

    def safe_execute(
        self,
        func: Callable,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
        context: Optional[dict] = None,
        clear_error_first: bool = True,
    ) -> bool:
        """
        Safely execute a function with error handling.

        Args:
            func: Function to execute
            category: Error category
            error_type: Specific error type
            context: Additional context
            clear_error_first: Whether to clear existing errors first

        Returns:
            True if successful, False if error occurred
        """
        if clear_error_first:
            self.clear_error()

        try:
            func()
            return True
        except Exception as e:
            self.set_error(e, category, error_type, context=context)
            return False

    async def safe_execute_async(
        self,
        func: Callable,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        error_type: str = "default",
        context: Optional[dict] = None,
        clear_error_first: bool = True,
    ) -> bool:
        """
        Safely execute an async function with error handling.

        Args:
            func: Async function to execute
            category: Error category
            error_type: Specific error type
            context: Additional context
            clear_error_first: Whether to clear existing errors first

        Returns:
            True if successful, False if error occurred
        """
        if clear_error_first:
            self.clear_error()

        try:
            if callable(func):
                result = func()
                # Handle both async and sync functions
                if hasattr(result, '__await__'):
                    await result
                else:
                    # Already executed, just return success
                    pass
            return True
        except Exception as e:
            self.set_error(e, category, error_type, context=context)
            return False

    def retry_operation(
        self,
        operation: Callable,
        max_attempts: int = 3,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
    ):
        """
        Retry a failed operation with exponential backoff.

        Args:
            operation: Function to retry
            max_attempts: Maximum retry attempts
            category: Error category
        """
        from ..utils.error_handler import ErrorRecovery

        self.is_retrying = True
        self.clear_error()

        try:
            result = ErrorRecovery.retry_with_backoff(
                operation, max_attempts=max_attempts, category=category
            )
            self.is_retrying = False
            return result
        except Exception as e:
            self.is_retrying = False
            self.set_error(e, category, context={"retry_attempts": max_attempts})
            raise

    @property
    def formatted_error(self) -> str:
        """Get formatted error message for UI display."""
        if not self.has_error:
            return ""

        return format_error_for_ui(
            {"message": self.error_message, "error_id": self.error_id}
        )


# NOTE: PageErrorState and ValidationErrorState are commented out due to Reflex's
# limitation of only allowing one parent state. If needed in the future, these
# should be converted to use composition instead of multiple inheritance.

# class PageErrorState(ErrorStateMixin, rx.State):
#     """
#     Specialized error state for page-level errors.
#
#     Includes page-specific error tracking and recovery.
#     """
#
#     page_name: str = "Page"
#     is_page_error: bool = False  # Critical errors that break the entire page
#     fallback_message: str = ""
#
#     def set_page_error(
#         self,
#         error: Exception,
#         category: ErrorCategory = ErrorCategory.UNKNOWN,
#         page_name: Optional[str] = None,
#     ):
#         """
#         Set a page-level error (more severe than component errors).
#
#         Args:
#             error: The exception
#             category: Error category
#             page_name: Name of the page (uses self.page_name if None)
#         """
#         if page_name:
#             self.page_name = page_name
#
#         self.set_error(
#             error,
#             category,
#             severity=ErrorSeverity.CRITICAL,
#             context={"page": self.page_name, "level": "page"},
#         )
#         self.is_page_error = True
#         self.fallback_message = f"Unable to load {self.page_name}. Please try refreshing."
#
#     def clear_page_error(self):
#         """Clear page-level error."""
#         self.clear_error()
#         self.is_page_error = False
#         self.fallback_message = ""
#
#
# class ValidationErrorState(ErrorStateMixin, rx.State):
#     """
#     Specialized state for form validation errors.
#     """
#
#     field_errors: dict[str, str] = {}
#     has_validation_errors: bool = False
#
#     def set_field_error(self, field: str, message: str):
#         """
#         Set an error for a specific form field.
#
#         Args:
#             field: Field name
#             message: Error message
#         """
#         self.field_errors[field] = message
#         self.has_validation_errors = True
#
#     def clear_field_error(self, field: str):
#         """Clear error for a specific field."""
#         if field in self.field_errors:
#             del self.field_errors[field]
#
#         if not self.field_errors:
#             self.has_validation_errors = False
#
#     def clear_all_field_errors(self):
#         """Clear all field errors."""
#         self.field_errors = {}
#         self.has_validation_errors = False
#
#     def validate_field(
#         self,
#         field: str,
#         value: Any,
#         validators: list[Callable[[Any], tuple[bool, str]]],
#     ) -> bool:
#         """
#         Validate a field with multiple validators.
#
#         Args:
#             field: Field name
#             value: Field value
#             validators: List of validation functions that return (is_valid, error_message)
#
#         Returns:
#             True if all validations pass
#         """
#         self.clear_field_error(field)
#
#         for validator in validators:
#             is_valid, error_message = validator(value)
#             if not is_valid:
#                 self.set_field_error(field, error_message)
#                 return False
#
#         return True
#
#     def get_field_error(self, field: str) -> str:
#         """Get error message for a field."""
#         return self.field_errors.get(field, "")
