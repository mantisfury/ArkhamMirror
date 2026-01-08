"""Tenant context for multi-tenancy."""

import contextvars
from typing import Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable to store current tenant ID
_current_tenant_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


def get_current_tenant_id() -> Optional[UUID]:
    """Get the current tenant ID from context."""
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[UUID]) -> None:
    """Set the current tenant ID in context."""
    _current_tenant_id.set(tenant_id)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract tenant from authenticated user and set in context.

    This middleware runs after authentication and extracts the tenant_id
    from the authenticated user, making it available via get_current_tenant_id()
    for tenant-scoped database queries.
    """

    # Paths that don't require tenant context
    EXEMPT_PATHS = {
        "/api/auth/",
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant context for exempt paths
        if any(path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)

        # Extract tenant_id from authenticated user if present
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "tenant_id"):
            set_current_tenant_id(user.tenant_id)

        try:
            response = await call_next(request)
        finally:
            # Always clear tenant context after request
            set_current_tenant_id(None)

        return response
