"""Machine-to-Machine API key management."""

import hashlib
import secrets
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_KEY_PREFIX = "ba_"


def generate_raw_key() -> str:
    """Generate a new raw API key with prefix."""
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(48)}"


def hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key (stored in DB)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    db: AsyncSession,
    *,
    user_id: str,
    name: str,
    scopes: list[str],
    rate_limit: int = 100,
) -> tuple[dict[str, Any], str]:
    """Create an API key. Returns (key_record, raw_key).

    The raw key is only available at creation time.
    """
    import json

    raw_key = generate_raw_key()
    key_hash = hash_key(raw_key)

    result = await db.execute(
        text(
            "INSERT INTO core.api_keys (user_id, key_hash, name, scopes, rate_limit) "
            "VALUES (:uid, :kh, :name, CAST(:scopes AS jsonb), :rl) "
            "RETURNING id, user_id, name, scopes, rate_limit, is_active, last_used_at, created_at"
        ),
        {
            "uid": user_id,
            "kh": key_hash,
            "name": name,
            "scopes": json.dumps(scopes),
            "rl": rate_limit,
        },
    )
    row = result.mappings().first()
    await db.commit()
    return dict(row), raw_key  # type: ignore[union-attr]


async def list_api_keys(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    """List all active API keys for a user (no raw keys returned)."""
    result = await db.execute(
        text(
            "SELECT id, name, scopes, rate_limit, is_active, last_used_at, created_at "
            "FROM core.api_keys WHERE user_id = :uid AND is_active = TRUE "
            "ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    return [dict(row) for row in result.mappings().fetchall()]


async def revoke_api_key(db: AsyncSession, key_id: str, user_id: str) -> bool:
    """Deactivate an API key. Returns True if found and deactivated."""
    result = await db.execute(
        text(
            "UPDATE core.api_keys SET is_active = FALSE "
            "WHERE id = :kid AND user_id = :uid AND is_active = TRUE"
        ),
        {"kid": key_id, "uid": user_id},
    )
    await db.commit()
    return result.rowcount > 0
