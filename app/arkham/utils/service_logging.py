"""
Service layer logging utilities.

Provides decorators for automatic logging of service calls with:
- Request/response logging
- Error handling
- Performance timing
- Structured context
"""

import logging
import functools
import time
from typing import Any, Callable, Optional
import traceback


def logged_service_call(service_name: Optional[str] = None):
    """
    Decorator for service methods that automatically logs:
    - Method calls with arguments
    - Execution time
    - Errors and exceptions
    - Return values (summarized)

    Usage:
        @logged_service_call("SearchService")
        def search_documents(self, query: str) -> List[Document]:
            ...
    """

    def decorator(func: Callable) -> Callable:
        nonlocal service_name
        if service_name is None:
            # Try to infer from class name
            service_name = func.__qualname__.split(".")[0] if "." in func.__qualname__ else "UnknownService"

        logger = logging.getLogger(f"arkham.service.{service_name}")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build context
            func_name = func.__name__
            call_id = f"{service_name}.{func_name}"

            # Log arguments (sanitized)
            args_str = _sanitize_args(args, kwargs)
            logger.info(f"→ {call_id}({args_str})")

            start_time = time.time()
            result = None
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                logger.error(
                    f"✗ {call_id} failed: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )
                raise
            finally:
                elapsed = time.time() - start_time

                if error is None:
                    result_summary = _summarize_result(result)
                    logger.info(f"← {call_id} completed in {elapsed:.3f}s | {result_summary}")
                else:
                    logger.error(f"✗ {call_id} failed in {elapsed:.3f}s")

        return wrapper

    return decorator


def _sanitize_args(args: tuple, kwargs: dict) -> str:
    """Sanitize arguments for logging (hide sensitive data, limit length)."""
    parts = []

    # Skip 'self' argument
    visible_args = args[1:] if args and hasattr(args[0], "__class__") else args

    for arg in visible_args:
        parts.append(_format_value(arg))

    for key, value in kwargs.items():
        # Hide sensitive keys
        if any(secret in key.lower() for secret in ["password", "token", "secret", "key", "credential"]):
            parts.append(f"{key}=***")
        else:
            parts.append(f"{key}={_format_value(value)}")

    return ", ".join(parts)


def _format_value(value: Any, max_length: int = 100) -> str:
    """Format a value for logging."""
    if value is None:
        return "None"
    elif isinstance(value, str):
        if len(value) > max_length:
            return f'"{value[:max_length]}..."'
        return f'"{value}"'
    elif isinstance(value, (list, tuple)):
        return f"{type(value).__name__}[{len(value)}]"
    elif isinstance(value, dict):
        return f"dict[{len(value)}]"
    elif isinstance(value, bytes):
        return f"bytes[{len(value)}]"
    else:
        str_val = str(value)
        if len(str_val) > max_length:
            return f"{str_val[:max_length]}..."
        return str_val


def _summarize_result(result: Any) -> str:
    """Summarize result for logging."""
    if result is None:
        return "None"
    elif isinstance(result, bool):
        return str(result)
    elif isinstance(result, (int, float)):
        return str(result)
    elif isinstance(result, str):
        return f'"{result[:50]}..."' if len(result) > 50 else f'"{result}"'
    elif isinstance(result, (list, tuple)):
        return f"{type(result).__name__}[{len(result)} items]"
    elif isinstance(result, dict):
        return f"dict[{len(result)} keys]"
    elif hasattr(result, "__len__"):
        try:
            return f"{type(result).__name__}[{len(result)}]"
        except:
            pass
    return f"{type(result).__name__}"


def log_database_query(query: str, params: Optional[dict] = None) -> None:
    """Log a database query."""
    logger = logging.getLogger("arkham.database")
    sanitized_query = query.replace("\n", " ").strip()
    if len(sanitized_query) > 200:
        sanitized_query = sanitized_query[:200] + "..."

    if params:
        logger.debug(f"SQL: {sanitized_query} | Params: {params}")
    else:
        logger.debug(f"SQL: {sanitized_query}")


def log_external_api_call(service: str, endpoint: str, method: str = "GET", status: Optional[int] = None) -> None:
    """Log an external API call."""
    logger = logging.getLogger("arkham.external")
    if status:
        logger.info(f"{method} {service}/{endpoint} → {status}")
    else:
        logger.info(f"{method} {service}/{endpoint}")
