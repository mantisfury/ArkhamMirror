"""FastAPI middleware for automatic wide event logging per request."""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from arkham_frame import LOGGING_AVAILABLE


class WideEventMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic wide event logging of HTTP requests.
    
    Automatically creates wide events for each request with:
    - Request method, path, and headers
    - User and project context (from request.state)
    - Response status code
    - Request duration
    - Automatic trace_id extraction/generation
    - Automatic data sanitization
    """
    
    def __init__(self, app, frame=None):
        """Initialize middleware.
        
        Args:
            app: FastAPI application
            frame: Optional ArkhamFrame instance
        """
        super().__init__(app)
        self.frame = frame
        
        # Initialize tracing and sanitizer if logging is available
        if LOGGING_AVAILABLE:
            try:
                from arkham_logging.tracing import TracingContext
                from arkham_logging.sanitizer import DataSanitizer
                self.tracing = TracingContext()
                self.sanitizer = DataSanitizer()
            except ImportError:
                self.tracing = None
                self.sanitizer = None
        else:
            self.tracing = None
            self.sanitizer = None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and create wide event.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Get frame from app state (set during lifespan)
        frame = getattr(request.app.state, "frame", None) or self.frame
        
        # Skip if logging not available or frame not initialized
        if not LOGGING_AVAILABLE or not frame or not hasattr(frame, "create_wide_event") or not frame.create_wide_event:
            return await call_next(request)
        
        # Extract or generate trace_id
        trace_id = self._extract_trace_id(request)
        if self.tracing:
            self.tracing.set_trace_id(trace_id)
        
        # Create wide event
        event = frame.create_wide_event("api_request", trace_id=trace_id)
        
        # Sanitize and add input data
        input_data = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
        }
        
        # Add user/project context if available
        if hasattr(request.state, "user_id"):
            input_data["user_id"] = request.state.user_id
        if hasattr(request.state, "project_id"):
            input_data["project_id"] = request.state.project_id
        
        # Sanitize input
        if self.sanitizer:
            sanitized_input = self.sanitizer.sanitize(input_data)
        else:
            sanitized_input = input_data
        
        event.input(**sanitized_input)
        
        # Add context fields
        for key, value in sanitized_input.items():
            event.context(key, value)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Add response data
            event.status_code(response.status_code)
            event.output(status_code=response.status_code)
            
            # Mark as success
            event.success()
            
            return response
        except Exception as e:
            # Log error
            import traceback
            tb_str = traceback.format_exc()
            event.error(
                code=type(e).__name__,
                message=str(e),
                exception=e,
                traceback_str=tb_str,
            )
            raise
    
    def _extract_trace_id(self, request: Request) -> str:
        """Extract trace_id from headers or generate new one.
        
        Args:
            request: FastAPI request
            
        Returns:
            Trace ID string
        """
        if self.tracing:
            # Try to extract from headers
            headers_dict = dict(request.headers)
            trace_id = self.tracing.extract_from_headers(headers_dict)
            if trace_id:
                return trace_id
        
        # Generate new trace_id
        return f"trace_{uuid.uuid4().hex[:12]}"
