"""Rate limiting for ArkhamFrame."""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.

    Uses X-Forwarded-For header if present (for proxy/load balancer setups),
    otherwise falls back to direct client IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs; take the first (client)
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Rate limit defaults (configurable via environment variables)
DEFAULT_LIMIT = os.environ.get("RATE_LIMIT_DEFAULT", "100/minute")
UPLOAD_LIMIT = os.environ.get("RATE_LIMIT_UPLOAD", "20/minute")
AUTH_LIMIT = os.environ.get("RATE_LIMIT_AUTH", "10/minute")

# Create limiter instance
# Uses Redis if available, otherwise in-memory storage
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[DEFAULT_LIMIT],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": str(exc.detail),
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )


# Decorator shortcuts for common endpoints
def upload_rate_limit():
    """Rate limit decorator for upload endpoints."""
    return limiter.limit(UPLOAD_LIMIT)


def auth_rate_limit():
    """Rate limit decorator for auth endpoints."""
    return limiter.limit(AUTH_LIMIT)
