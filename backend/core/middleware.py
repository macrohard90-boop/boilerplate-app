"""ASGI middleware: rate limiting."""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.core.config import settings
from backend.core.redis import get_redis


# ---------------------------------------------------------------------------
# Rate-limit configuration per route pattern
# ---------------------------------------------------------------------------

_AUTH_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/forgot-password"}

# Limits: (max_requests, window_seconds)
_AUTH_LIMIT = (10, 60)  # 10 req/min for auth endpoints (brute-force protection)
_GENERAL_LIMIT_IP = (30, 60)  # 30 req/min per IP for unauthenticated
_GENERAL_LIMIT_USER = (60, 60)  # 60 req/min per user for authenticated

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/api/health", "/api/health/db", "/api/health/redis", "/docs", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter backed by Redis."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip exempt paths
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        try:
            redis = await get_redis()
        except Exception:
            return await call_next(request)
        if redis is None:
            # If Redis is unavailable, allow the request (fail open)
            return await call_next(request)

        ip = _get_client_ip(request)
        window = int(time.time() // 60)  # 1-minute windows

        # Determine limit
        if path in _AUTH_PATHS:
            max_req, _ = _AUTH_LIMIT
            key = f"rate:ip:{ip}:auth:{window}"
        else:
            # Check if user is authenticated (JWT in header)
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and len(auth_header) > 20:
                max_req, _ = _GENERAL_LIMIT_USER
                # Use a hash of the token prefix as identifier (don't decode JWT in middleware)
                token_prefix = auth_header[7:27]
                key = f"rate:token:{token_prefix}:{window}"
            else:
                max_req, _ = _GENERAL_LIMIT_IP
                key = f"rate:ip:{ip}:{window}"

        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)  # TTL > window to handle edge cases

            if count > max_req:
                retry_after = 60 - (int(time.time()) % 60)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limited",
                        "message": "Too many requests",
                        "details": {"retry_after": retry_after},
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception:
            # Redis error — fail open
            pass

        return await call_next(request)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
