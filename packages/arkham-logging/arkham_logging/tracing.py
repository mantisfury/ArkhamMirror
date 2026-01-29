"""Distributed tracing support for cross-service correlation."""

import uuid
from contextvars import ContextVar
from typing import Dict, Optional

# Context variable for storing trace_id in async operations
_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class TracingContext:
    """Manages trace_id for distributed tracing across services.
    
    Generates and propagates trace_id across service boundaries,
    extracts from HTTP headers, injects into outgoing requests,
    and stores in contextvars for async operations.
    """
    
    def __init__(self):
        """Initialize tracing context."""
        self._local_trace_id: Optional[str] = None
    
    def get_trace_id(self) -> Optional[str]:
        """Get current trace_id from context.
        
        Checks contextvars first (for async), then local storage.
        
        Returns:
            Current trace_id or None
        """
        # Check contextvars (for async operations)
        ctx_trace_id = _trace_id.get()
        if ctx_trace_id:
            return ctx_trace_id
        
        # Check local storage (for sync operations)
        return self._local_trace_id
    
    def set_trace_id(self, trace_id: Optional[str]) -> None:
        """Set trace_id in context.
        
        Args:
            trace_id: Trace ID to set (or None to clear)
        """
        self._local_trace_id = trace_id
        _trace_id.set(trace_id)
    
    def generate_trace_id(self) -> str:
        """Generate a new trace_id.
        
        Returns:
            New trace_id string
        """
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        self.set_trace_id(trace_id)
        return trace_id
    
    def extract_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """Extract trace_id from HTTP headers.
        
        Supports:
        - X-Trace-ID (custom header)
        - traceparent (W3C Trace Context standard)
        
        Args:
            headers: Dictionary of HTTP headers
            
        Returns:
            Extracted trace_id or None
        """
        # Check X-Trace-ID header
        trace_id = headers.get("X-Trace-ID") or headers.get("x-trace-id")
        if trace_id:
            return trace_id.strip()
        
        # Check traceparent header (W3C Trace Context)
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        if traceparent:
            # traceparent format: version-trace_id-parent_id-flags
            # Extract trace_id (second field)
            parts = traceparent.split("-")
            if len(parts) >= 2:
                return parts[1]  # Return trace_id portion
        
        return None
    
    def propagate_to_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Generate headers for HTTP propagation.
        
        Args:
            headers: Optional existing headers dict to update
            
        Returns:
            Dictionary with trace headers
        """
        if headers is None:
            headers = {}
        
        trace_id = self.get_trace_id()
        if trace_id:
            headers["X-Trace-ID"] = trace_id
            # Also set traceparent for W3C compatibility
            # Format: 00-{trace_id}-{parent_id}-01
            # We use trace_id as parent_id for simplicity
            headers["traceparent"] = f"00-{trace_id}-{trace_id[:16]}-01"
        
        return headers
    
    def clear(self) -> None:
        """Clear current trace_id from context."""
        self.set_trace_id(None)


# Global instance for convenience
_default_tracing = TracingContext()


def get_trace_id() -> Optional[str]:
    """Get current trace_id from default tracing context.
    
    Returns:
        Current trace_id or None
    """
    return _default_tracing.get_trace_id()


def set_trace_id(trace_id: Optional[str]) -> None:
    """Set trace_id in default tracing context.
    
    Args:
        trace_id: Trace ID to set
    """
    _default_tracing.set_trace_id(trace_id)


def generate_trace_id() -> str:
    """Generate and set a new trace_id in default context.
    
    Returns:
        New trace_id string
    """
    return _default_tracing.generate_trace_id()
