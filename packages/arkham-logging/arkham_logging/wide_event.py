"""Wide event logging for comprehensive operation tracking."""

import json
import logging
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from .sampling import get_sampler
from .sanitizer import DataSanitizer
from .tracing import get_trace_id

logger = logging.getLogger(__name__)


@dataclass
class WideEvent:
    """A comprehensive log event for an operation.
    
    Attributes:
        timestamp: ISO format timestamp of the operation.
        operation_id: Unique identifier for this operation.
        trace_id: Trace ID for distributed tracing.
        service: Name of the service handling the operation.
        duration_ms: Duration of the operation in milliseconds.
        outcome: Either "success" or "error".
        status_code: HTTP status code (if applicable).
        error: Error details if outcome is "error".
        user: User context information.
        input: Input summary (non-sensitive).
        output: Output summary.
        dependencies: Dependency timing information.
        extra: Additional context fields.
    """
    
    timestamp: str
    operation_id: str
    trace_id: str
    service: str
    duration_ms: int
    outcome: Literal["success", "error"]
    status_code: Optional[int] = None
    error: Optional[Dict[str, str]] = None
    user: Optional[Dict[str, Any]] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    dependencies: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    # Additional fields for compatibility
    project_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging.
        
        Returns:
            Dictionary representation of the event.
        """
        result = {
            "timestamp": self.timestamp,
            "operation_id": self.operation_id,
            "trace_id": self.trace_id,
            "service": self.service,
            "duration_ms": self.duration_ms,
            "outcome": self.outcome,
        }
        
        if self.status_code is not None:
            result["status_code"] = self.status_code
        
        if self.error:
            result["error"] = self.error
        
        if self.user:
            result["user"] = self.user
        
        if self.input:
            result["input"] = self.input
        
        if self.output:
            result["output"] = self.output
        
        if self.dependencies:
            result["dependencies"] = self.dependencies
        
        if self.project_id:
            result["project_id"] = self.project_id
        
        # Add extra fields
        result.update(self.extra)
        
        return result


class WideEventBuilder:
    """Builder for constructing wide events throughout an operation."""
    
    def __init__(
        self,
        service: str,
        trace_id: Optional[str] = None,
        sampler: Optional[Any] = None,
        sanitizer: Optional[DataSanitizer] = None,
    ) -> None:
        """Initialize the builder.
        
        Args:
            service: Name of the service.
            trace_id: Optional trace ID for distributed tracing.
            sampler: Optional sampling strategy instance.
            sanitizer: Optional data sanitizer instance.
        """
        self._start_time = time.time()
        self._operation_id = f"op_{uuid.uuid4().hex[:12]}"
        self._trace_id = trace_id or get_trace_id() or f"trace_{uuid.uuid4().hex[:12]}"
        self._service = service
        from datetime import timezone
        self._timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._user: Optional[Dict[str, Any]] = None
        self._input: Optional[Dict[str, Any]] = None
        self._output: Optional[Dict[str, Any]] = None
        self._dependencies: Dict[str, Any] = {}
        self._extra: Dict[str, Any] = {}
        self._status_code: Optional[int] = None
        self._sampler = sampler or get_sampler()
        self._sanitizer = sanitizer or DataSanitizer()
    
    def user(self, **kwargs: Any) -> "WideEventBuilder":
        """Add user context (automatically sanitized).
        
        Args:
            **kwargs: User attributes (id, subscription, etc.)
            
        Returns:
            Self for chaining.
        """
        self._user = self._sanitizer.sanitize(kwargs)
        return self
    
    def input(self, **kwargs: Any) -> "WideEventBuilder":
        """Add input summary (automatically sanitized).
        
        Args:
            **kwargs: Input summary attributes.
            
        Returns:
            Self for chaining.
        """
        self._input = self._sanitizer.sanitize(kwargs)
        return self
    
    def output(self, **kwargs: Any) -> "WideEventBuilder":
        """Add output summary (automatically sanitized).
        
        Args:
            **kwargs: Output summary attributes.
            
        Returns:
            Self for chaining.
        """
        self._output = self._sanitizer.sanitize(kwargs)
        return self
    
    def dependency(
        self,
        name: str,
        duration_ms: int,
        **metadata: Any
    ) -> "WideEventBuilder":
        """Add dependency timing.
        
        Args:
            name: Name of the dependency.
            duration_ms: Time taken in milliseconds.
            **metadata: Additional metadata (automatically sanitized).
            
        Returns:
            Self for chaining.
        """
        sanitized_metadata = self._sanitizer.sanitize(metadata)
        self._dependencies[name] = {"duration_ms": duration_ms, **sanitized_metadata}
        return self
    
    def context(self, key: str, value: Any) -> "WideEventBuilder":
        """Add arbitrary context (automatically sanitized).
        
        Args:
            key: Context key.
            value: Context value.
            
        Returns:
            Self for chaining.
        """
        self._extra[key] = self._sanitizer.sanitize(value)
        return self
    
    def status_code(self, code: int) -> "WideEventBuilder":
        """Set HTTP status code.
        
        Args:
            code: HTTP status code.
            
        Returns:
            Self for chaining.
        """
        self._status_code = code
        return self
    
    def success(self) -> WideEvent:
        """Mark as success and emit (with sampling).
        
        Returns:
            The emitted WideEvent.
        """
        duration_ms = int((time.time() - self._start_time) * 1000)
        event = WideEvent(
            timestamp=self._timestamp,
            operation_id=self._operation_id,
            trace_id=self._trace_id,
            service=self._service,
            duration_ms=duration_ms,
            outcome="success",
            status_code=self._status_code,
            user=self._user,
            input=self._input,
            output=self._output,
            dependencies=self._dependencies if self._dependencies else None,
            extra=self._extra,
            project_id=self._extra.get("project_id"),
        )
        self._emit(event)
        return event
    
    def error(
        self,
        code: str,
        message: str,
        exception: Optional[Exception] = None,
        traceback_str: Optional[str] = None,
    ) -> WideEvent:
        """Mark as error and emit (always sampled).
        
        Args:
            code: Error code.
            message: Error message.
            exception: Optional exception object.
            traceback_str: Optional traceback string.
            
        Returns:
            The emitted WideEvent.
        """
        duration_ms = int((time.time() - self._start_time) * 1000)
        
        error_dict: Dict[str, str] = {
            "code": code,
            "message": message,
        }
        
        if exception:
            error_dict["type"] = type(exception).__name__
            if traceback_str:
                error_dict["traceback"] = traceback_str
            elif hasattr(exception, "__traceback__"):
                error_dict["traceback"] = "".join(
                    traceback.format_exception(
                        type(exception),
                        exception,
                        exception.__traceback__,
                    )
                )
        
        event = WideEvent(
            timestamp=self._timestamp,
            operation_id=self._operation_id,
            trace_id=self._trace_id,
            service=self._service,
            duration_ms=duration_ms,
            outcome="error",
            status_code=self._status_code,
            error=error_dict,
            user=self._user,
            input=self._input,
            output=self._output,
            dependencies=self._dependencies if self._dependencies else None,
            extra=self._extra,
            project_id=self._extra.get("project_id"),
        )
        self._emit(event)
        return event
    
    def _emit(self, event: WideEvent) -> None:
        """Emit the event to logging infrastructure (with sampling).
        
        Args:
            event: The wide event to emit.
        """
        # Check sampling strategy
        if self._sampler:
            if not self._sampler.should_sample(event):
                return  # Don't emit if not sampled
        
        # Emit as JSON to logger
        event_dict = event.to_dict()
        logger.info(json.dumps(event_dict))


def create_wide_event(
    service: str,
    trace_id: Optional[str] = None,
    sampler: Optional[Any] = None,
    sanitizer: Optional[DataSanitizer] = None,
) -> WideEventBuilder:
    """Create a new wide event builder.
    
    Args:
        service: Name of the service.
        trace_id: Optional trace ID for distributed tracing.
        sampler: Optional sampling strategy instance.
        sanitizer: Optional data sanitizer instance.
        
    Returns:
        WideEventBuilder instance.
    """
    return WideEventBuilder(service, trace_id, sampler, sanitizer)
