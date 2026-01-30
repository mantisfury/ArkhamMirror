"""Logging filters for arkham-logging."""

import logging
from typing import Optional


class TraceIdFilter(logging.Filter):
    """
    Capture trace_id from the current context and attach it to the log record.

    Must run in the same thread/context as the log call (e.g. the request task).
    That way when handlers format the record in another thread (e.g. AsyncFileHandler's
    worker thread), trace_id is already on the record and ContextVar is not needed.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from .tracing import get_trace_id
            trace_id = get_trace_id()
            record.trace_id = trace_id  # type: ignore[attr-defined]
        except Exception:
            record.trace_id = None  # type: ignore[attr-defined]
        return True
