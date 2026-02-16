"""JWT access token and opaque refresh token management."""

import secrets
from datetime import datetime, timezone
from typing import Any

from jose import JWTError, jwt
from redis.asyncio import Redis

from backend.core.config import settings


# ---------------------------------------------------------------------------
# Access tokens (JWT)
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: str,
    role: str,
    session_id: str,
    permissions: list[str],
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "session_id": session_id,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + settings.jwt_expiry,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises ``JWTError`` on invalid/expired tokens.
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require_exp": True, "require_sub": True},
    )


# ---------------------------------------------------------------------------
# Refresh tokens (opaque, stored in Redis)
# ---------------------------------------------------------------------------

_REFRESH_PREFIX = "refresh:"


async def create_refresh_token(
    redis: Redis,
    user_id: str,
    session_id: str,
) -> str:
    """Generate an opaque refresh token and store it in Redis."""
    token = secrets.token_urlsafe(48)
    key = f"{_REFRESH_PREFIX}{token}"
    await redis.hset(key, mapping={"user_id": user_id, "session_id": session_id})
    await redis.expire(key, settings.refresh_token_ttl)
    return token


async def validate_refresh_token(
    redis: Redis,
    token: str,
) -> dict[str, str] | None:
    """Return ``{user_id, session_id}`` if the refresh token is valid, else None."""
    key = f"{_REFRESH_PREFIX}{token}"
    data = await redis.hgetall(key)
    if not data or "user_id" not in data:
        return None
    return {"user_id": data["user_id"], "session_id": data["session_id"]}


async def revoke_refresh_token(redis: Redis, token: str) -> None:
    """Delete a refresh token from Redis."""
    await redis.delete(f"{_REFRESH_PREFIX}{token}")
