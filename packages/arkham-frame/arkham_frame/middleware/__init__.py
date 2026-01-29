"""Security middleware for ArkhamFrame."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # Disable caching for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"

        return response


from .rate_limit import limiter, rate_limit_handler, upload_rate_limit, auth_rate_limit
from .tenant import TenantContextMiddleware, get_current_tenant_id, set_current_tenant_id
from .logging import WideEventMiddleware

__all__ = [
    "SecurityHeadersMiddleware",
    "limiter",
    "rate_limit_handler",
    "upload_rate_limit",
    "auth_rate_limit",
    "TenantContextMiddleware",
    "get_current_tenant_id",
    "set_current_tenant_id",
    "WideEventMiddleware",
]
