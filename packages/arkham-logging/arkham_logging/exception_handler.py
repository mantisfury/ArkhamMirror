"""Global exception handling with context managers and decorators."""

import functools
import logging
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from .wide_event import WideEventBuilder, create_wide_event
from .sanitizer import DataSanitizer
from .tracing import get_trace_id

logger = logging.getLogger(__name__)


def format_error_message(
    message: str,
    exc: Optional[Exception] = None,
    *,
    max_context_items: int = 8,
    **context: Any,
) -> str:
    """Build an error message with trace_id and context for easier tracing.

    Use when logging or re-raising so logs and stack traces include context
    (e.g. job_id, document_id) without callers having to remember to pass extra.

    Args:
        message: Primary error message.
        exc: Optional exception (its message is appended).
        max_context_items: Max key=value pairs to include in the message string.
        **context: Key-value context (e.g. job_id=..., document_id=...).

    Returns:
        A single string like:
        "Failed to persist job (job_id=abc document_id=xyz trace_id=trace_123): Original error"
    """
    parts = [message]
    trace_id = get_trace_id()
    if trace_id:
        context = {**context, "trace_id": trace_id}
    if context:
        # Sanitize: short string values only for inline message
        items = []
        for k, v in list(context.items())[:max_context_items]:
            if v is None:
                items.append(f"{k}=None")
            elif isinstance(v, str) and len(v) > 64:
                items.append(f"{k}={v[:61]}...")
            else:
                items.append(f"{k}={v}")
        parts.append(" (" + " ".join(items) + ")")
    if exc is not None and str(exc):
        parts.append(f": {exc}")
    return "".join(parts)


def log_error_with_context(
    log: logging.Logger,
    message: str,
    exc: Optional[Exception] = None,
    *,
    exc_info: bool = True,
    level: int = logging.ERROR,
    **context: Any,
) -> None:
    """Log an error with trace_id and context so errors are traceable.

    Ensures trace_id (from current context) and any passed context (job_id,
    document_id, etc.) are in the log record's extra and, when possible, in
    the message string. Use this for caught exceptions so logs and log
    aggregation can be filtered by trace_id or business IDs.

    Args:
        log: Logger to use (e.g. logger from module).
        message: Primary error message.
        exc: Optional exception (if exc_info True, traceback is logged).
        exc_info: Whether to log exception traceback (default True when exc set).
        level: Log level (default ERROR).
        **context: Context to attach (e.g. job_id=..., document_id=...).
    """
    trace_id = get_trace_id()
    extra: Dict[str, Any] = {**context}
    if trace_id:
        extra["trace_id"] = trace_id
    full_message = format_error_message(message, exc=exc, **context)
    if exc is not None and exc_info:
        log.log(level, full_message, exc_info=True, extra=extra)
    else:
        log.log(level, full_message, extra=extra)


def emit_wide_error(
    event: Optional[WideEventBuilder],
    code: str,
    message: str,
    exc: Optional[Exception] = None,
) -> None:
    """Call event.error with full traceback when exc is provided. No-op if event is None.

    Use so call sites do not need to import traceback or build traceback_str by hand.
    The traceback is derived from the passed exception (safe in async and in helpers).

    Args:
        event: WideEventBuilder from log_operation or create_wide_event; None is a no-op.
        code: Error code (e.g. exception type name or "DocumentCreationFailed").
        message: Error message (e.g. str(e)).
        exc: Optional exception; when set, type and full traceback are added to the wide event.
    """
    if event is None:
        return
    if exc is not None:
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        event.error(code, message, exception=exc, traceback_str=tb_str)
    else:
        event.error(code, message)


T = TypeVar("T")


@contextmanager
def log_operation(
    service: str,
    trace_id: Optional[str] = None,
    **context: Any,
):
    """Context manager for logging operations with automatic exception handling.
    
    Usage:
        with log_operation("process_document", document_id=doc.id) as event:
            event.input(filename=doc.filename)
            result = process_document(doc)
            event.output(page_count=result.pages)
    
    Args:
        service: Service name for the operation
        trace_id: Optional trace ID (uses current context if not provided)
        **context: Additional context to add to the event
        
    Yields:
        WideEventBuilder instance
    """
    # Get trace_id from context if not provided
    if trace_id is None:
        trace_id = get_trace_id()
    
    # Create wide event
    event = create_wide_event(service, trace_id=trace_id)
    
    # Add initial context (automatically sanitized)
    sanitizer = DataSanitizer()
    sanitized_context = sanitizer.sanitize(context)
    event.input(**sanitized_context)
    
    # Add context fields to extra
    for key, value in sanitized_context.items():
        event.context(key, value)
    
    try:
        yield event
        event.success()
    except Exception as e:
        # Log exception with full traceback
        tb_str = traceback.format_exc()
        event.error(
            code=type(e).__name__,
            message=str(e),
            exception=e,
            traceback_str=tb_str,
        )
        
        # Also log to standard logger
        logger.exception(
            f"Operation failed: {service}",
            extra={"context": sanitized_context, "trace_id": trace_id},
        )
        raise


def logged_service_call(service_name: Optional[str] = None):
    """Decorator for service methods that automatically logs using wide event logging.
    
    Usage:
        @logged_service_call("SearchService")
        def search_documents(self, query: str) -> List[Document]:
            ...
    
    Args:
        service_name: Optional service name (inferred from class if not provided)
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        nonlocal service_name
        
        # Infer service name from class if not provided
        if service_name is None:
            if "." in func.__qualname__:
                service_name = func.__qualname__.split(".")[0]
            else:
                service_name = "UnknownService"
        
        func_name = func.__name__
        full_service_name = f"{service_name}.{func_name}"
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get trace_id from context
            trace_id = get_trace_id()
            
            # Create wide event
            event = create_wide_event(full_service_name, trace_id=trace_id)
            
            # Sanitize and log input
            sanitizer = DataSanitizer()
            args_dict = _args_to_dict(args, kwargs)
            sanitized_args = sanitizer.sanitize(args_dict)
            event.input(**sanitized_args)
            
            try:
                result = func(*args, **kwargs)
                # Summarize result
                result_summary = _summarize_result(result)
                event.output(result_summary=result_summary)
                event.success()
                return result
            except Exception as e:
                tb_str = traceback.format_exc()
                event.error(
                    code=type(e).__name__,
                    message=str(e),
                    exception=e,
                    traceback_str=tb_str,
                )
                raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get trace_id from context
            trace_id = get_trace_id()
            
            # Create wide event
            event = create_wide_event(full_service_name, trace_id=trace_id)
            
            # Sanitize and log input
            sanitizer = DataSanitizer()
            args_dict = _args_to_dict(args, kwargs)
            sanitized_args = sanitizer.sanitize(args_dict)
            event.input(**sanitized_args)
            
            try:
                result = await func(*args, **kwargs)
                # Summarize result
                result_summary = _summarize_result(result)
                event.output(result_summary=result_summary)
                event.success()
                return result
            except Exception as e:
                tb_str = traceback.format_exc()
                event.error(
                    code=type(e).__name__,
                    message=str(e),
                    exception=e,
                    traceback_str=tb_str,
                )
                raise
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _args_to_dict(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Convert function arguments to dictionary for logging.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        Dictionary representation of arguments
    """
    result = {}
    
    # Skip 'self' argument
    visible_args = args[1:] if args and hasattr(args[0], "__class__") else args
    
    # Add positional args (limited to first 5)
    for i, arg in enumerate(visible_args[:5]):
        result[f"arg_{i}"] = _format_value(arg)
    
    # Add keyword args
    for key, value in kwargs.items():
        result[key] = _format_value(value)
    
    return result


def _format_value(value: Any, max_length: int = 100) -> str:
    """Format a value for logging.
    
    Args:
        value: Value to format
        max_length: Maximum string length
        
    Returns:
        Formatted string representation
    """
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
    """Summarize result for logging.
    
    Args:
        result: Result value to summarize
        
    Returns:
        Summary string
    """
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
        except Exception:
            pass
    return f"{type(result).__name__}"
