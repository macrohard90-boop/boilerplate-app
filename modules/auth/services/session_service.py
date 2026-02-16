"""Redis-backed session management with concurrent session limits."""

import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

_SESSION_PREFIX = "session:"
_USER_SESSIONS_PREFIX = "user_sessions:"


async def create_session(
    redis: Redis,
    db: AsyncSession,
    user_id: str,
    role: str,
    device: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    auth_time: int | None = None,
    amr: list[str] | None = None,
) -> str:
    """Create a new session in Redis and PostgreSQL.

    Enforces ``MAX_SESSIONS_PER_USER`` — evicts the oldest session on overflow.
    Returns the new session_id (UUID string).
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    ttl = settings.refresh_token_ttl  # session lives as long as refresh token

    # --- Enforce concurrent session limit ---
    user_sessions_key = f"{_USER_SESSIONS_PREFIX}{user_id}"
    existing = await redis.smembers(user_sessions_key)

    if len(existing) >= settings.max_sessions_per_user:
        # Find and evict the oldest session(s)
        sessions_with_time: list[tuple[str, float]] = []
        for sid in existing:
            data = await redis.hgetall(f"{_SESSION_PREFIX}{sid}")
            created = float(data.get("created_at", 0)) if data else 0
            sessions_with_time.append((sid, created))

        sessions_with_time.sort(key=lambda x: x[1])
        evict_count = len(existing) - settings.max_sessions_per_user + 1
        for sid, _ in sessions_with_time[:evict_count]:
            await invalidate_session(redis, sid, user_id)

    # --- Create Redis session hash ---
    session_key = f"{_SESSION_PREFIX}{session_id}"
    mapping = {
        "user_id": user_id,
        "role": role,
        "device": device or "",
        "ip": ip or "",
        "user_agent": user_agent or "",
        "created_at": str(now.timestamp()),
        "auth_time": str(auth_time or int(now.timestamp())),
        "amr": json.dumps(amr or ["pwd"]),
    }
    await redis.hset(session_key, mapping=mapping)
    await redis.expire(session_key, ttl)

    # Add to user's session set
    await redis.sadd(user_sessions_key, session_id)
    await redis.expire(user_sessions_key, ttl)

    # --- Persist to PostgreSQL ---
    await db.execute(
        text(
            "INSERT INTO core.sessions (id, user_id, device, ip_address, user_agent, expires_at) "
            "VALUES (:id, :user_id, :device, :ip, :ua, NOW() + :ttl * INTERVAL '1 second')"
        ),
        {
            "id": session_id,
            "user_id": user_id,
            "device": device,
            "ip": ip,
            "ua": user_agent,
            "ttl": ttl,
        },
    )
    await db.commit()

    return session_id


async def get_session(redis: Redis, session_id: str) -> dict[str, str] | None:
    """Look up an active session by ID. Returns None if expired/missing."""
    data = await redis.hgetall(f"{_SESSION_PREFIX}{session_id}")
    if not data or "user_id" not in data:
        return None
    return data


async def invalidate_session(
    redis: Redis,
    session_id: str,
    user_id: str,
) -> None:
    """Remove a single session from Redis."""
    await redis.delete(f"{_SESSION_PREFIX}{session_id}")
    await redis.srem(f"{_USER_SESSIONS_PREFIX}{user_id}", session_id)

    # Also revoke any refresh tokens bound to this session
    # (scan is acceptable here — small keyspace per user)
    cursor: int | bytes = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="refresh:*", count=100)
        for key in keys:
            data = await redis.hgetall(key)
            if data.get("session_id") == session_id:
                await redis.delete(key)
        if cursor == 0:
            break


async def invalidate_all_sessions(redis: Redis, user_id: str) -> None:
    """Remove every session and refresh token for a user."""
    user_sessions_key = f"{_USER_SESSIONS_PREFIX}{user_id}"
    session_ids = await redis.smembers(user_sessions_key)
    for sid in session_ids:
        await redis.delete(f"{_SESSION_PREFIX}{sid}")
    await redis.delete(user_sessions_key)

    # Revoke all refresh tokens for this user
    cursor: int | bytes = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="refresh:*", count=100)
        for key in keys:
            data = await redis.hgetall(key)
            if data.get("user_id") == user_id:
                await redis.delete(key)
        if cursor == 0:
            break


async def get_user_session_count(redis: Redis, user_id: str) -> int:
    """Return the number of active sessions for a user."""
    return await redis.scard(f"{_USER_SESSIONS_PREFIX}{user_id}")
