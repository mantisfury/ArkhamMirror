"""
Rate limiting for ArkhamFrame using PostgreSQL.

Replaces Redis-based slowapi with PostgreSQL rate limiting.
Uses the arkham_frame.check_rate_limit() function from the migration.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Callable, Optional
from functools import wraps

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limit defaults (configurable via environment variables)
DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT_DEFAULT", "100"))
DEFAULT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))  # seconds
UPLOAD_LIMIT = int(os.environ.get("RATE_LIMIT_UPLOAD", "20"))
AUTH_LIMIT = int(os.environ.get("RATE_LIMIT_AUTH", "10"))

# Global reference to database pool (set by ArkhamFrame)
_db_pool = None


def set_db_pool(pool) -> None:
    """Set the database pool for rate limiting."""
    global _db_pool
    _db_pool = pool


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
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    key: str,
    limit: int = DEFAULT_LIMIT,
    window_seconds: int = DEFAULT_WINDOW,
) -> tuple[bool, int, datetime]:
    """
    Check rate limit using PostgreSQL.

    Args:
        key: Rate limit key (e.g., IP address, user ID)
        limit: Maximum requests allowed in window
        window_seconds: Window size in seconds

    Returns:
        Tuple of (allowed, current_count, reset_at)
    """
    global _db_pool

    if _db_pool is None:
        # No database, allow request (fail open)
        logger.warning("Rate limiter: no database pool, allowing request")
        return True, 0, datetime.utcnow()

    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM arkham_frame.check_rate_limit($1, $2, $3)
            """, key, limit, window_seconds)

            return row['allowed'], row['current_count'], row['reset_at']

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Fail open - allow request if database error
        return True, 0, datetime.utcnow()


async def rate_limit_middleware(
    request: Request,
    call_next,
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW,
):
    """
    ASGI middleware for rate limiting.

    Usage:
        @app.middleware("http")
        async def rate_limit(request, call_next):
            return await rate_limit_middleware(request, call_next)
    """
    key = get_rate_limit_key(request)
    endpoint_key = f"{key}:{request.url.path}"

    allowed, count, reset_at = await check_rate_limit(endpoint_key, limit, window)

    if not allowed:
        retry_after = max(1, int((reset_at - datetime.utcnow()).total_seconds()))
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "detail": f"Rate limit exceeded. {count}/{limit} requests in {window}s window.",
                "retry_after": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": reset_at.isoformat(),
            },
        )

    response = await call_next(request)

    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
    response.headers["X-RateLimit-Reset"] = reset_at.isoformat()

    return response


def rate_limit(
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW,
    key_func: Optional[Callable[[Request], str]] = None,
):
    """
    Decorator for rate limiting specific endpoints.

    Args:
        limit: Maximum requests allowed in window
        window: Window size in seconds
        key_func: Optional function to generate rate limit key

    Usage:
        @app.get("/api/data")
        @rate_limit(limit=10, window=60)
        async def get_data():
            return {"data": "value"}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request in args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get('request')

            if request:
                key = key_func(request) if key_func else get_rate_limit_key(request)
                endpoint_key = f"{key}:{request.url.path}"

                allowed, count, reset_at = await check_rate_limit(endpoint_key, limit, window)

                if not allowed:
                    retry_after = max(1, int((reset_at - datetime.utcnow()).total_seconds()))
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "detail": f"Rate limit exceeded. {count}/{limit} requests.",
                            "retry_after": retry_after,
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0",
                        },
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience decorators for common endpoints
def upload_rate_limit():
    """Rate limit decorator for upload endpoints."""
    return rate_limit(limit=UPLOAD_LIMIT, window=DEFAULT_WINDOW)


def auth_rate_limit():
    """Rate limit decorator for auth endpoints."""
    return rate_limit(limit=AUTH_LIMIT, window=DEFAULT_WINDOW)


class RateLimiter:
    """
    Rate limiter class for more complex use cases.

    Provides the same interface as slowapi's Limiter for compatibility.
    """

    def __init__(
        self,
        key_func: Callable[[Request], str] = get_rate_limit_key,
        default_limits: list[str] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            key_func: Function to extract rate limit key from request
            default_limits: Default limits (format: "N/period", e.g., "100/minute")
        """
        self.key_func = key_func
        self.default_limit = DEFAULT_LIMIT
        self.default_window = DEFAULT_WINDOW

        if default_limits:
            # Parse first default limit
            self._parse_limit(default_limits[0])

    def _parse_limit(self, limit_str: str) -> tuple[int, int]:
        """Parse limit string like '100/minute' into (limit, window_seconds)."""
        parts = limit_str.split("/")
        if len(parts) != 2:
            return self.default_limit, self.default_window

        try:
            limit = int(parts[0])
        except ValueError:
            limit = self.default_limit

        period = parts[1].lower()
        window_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }
        window = window_map.get(period, 60)

        self.default_limit = limit
        self.default_window = window
        return limit, window

    def limit(self, limit_str: str):
        """
        Create a rate limit decorator.

        Args:
            limit_str: Limit string (format: "N/period")

        Returns:
            Decorator function
        """
        limit, window = self._parse_limit(limit_str)
        return rate_limit(limit=limit, window=window, key_func=self.key_func)


# Default limiter instance for compatibility
limiter = RateLimiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{DEFAULT_LIMIT}/minute"],
)


async def rate_limit_handler(request: Request, exc) -> JSONResponse:
    """Handle rate limit exceeded errors (compatibility with slowapi)."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else "Rate limit exceeded",
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )
