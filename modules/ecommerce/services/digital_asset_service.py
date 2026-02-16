"""Digital asset management: HMAC-signed download URLs, download tracking."""

import hashlib
import hmac
import math
import time
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

_DOWNLOAD_PREFIX = "download_count:"
_DEFAULT_URL_TTL = 3600  # 1 hour


async def list_assets(
    db: AsyncSession,
    product_id: str | None = None,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    where = "1=1"
    params: dict[str, Any] = {}
    if product_id:
        where = "product_id = :pid"
        params["pid"] = product_id

    total = (
        await db.execute(text(f"SELECT COUNT(*) FROM ecommerce.digital_assets WHERE {where}"), params)
    ).scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = (
        await db.execute(
            text(
                f"SELECT * FROM ecommerce.digital_assets WHERE {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def get_asset(db: AsyncSession, asset_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.digital_assets WHERE id = :id"),
            {"id": asset_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def create_asset(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.digital_assets "
                "(product_id, file_url, file_name, file_size, download_limit) "
                "VALUES (:pid, :url, :name, :size, :limit) "
                "RETURNING *"
            ),
            {
                "pid": str(data["product_id"]),
                "url": data["file_url"],
                "name": data["file_name"],
                "size": data["file_size"],
                "limit": data.get("download_limit"),
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def update_asset(db: AsyncSession, asset_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = await get_asset(db, asset_id)
    if not existing:
        raise ValueError("Digital asset not found")

    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        return existing

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = asset_id
    row = (
        await db.execute(
            text(f"UPDATE ecommerce.digital_assets SET {set_clause} WHERE id = :id RETURNING *"),
            fields,
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def delete_asset(db: AsyncSession, asset_id: str) -> None:
    result = await db.execute(
        text("DELETE FROM ecommerce.digital_assets WHERE id = :id"),
        {"id": asset_id},
    )
    if result.rowcount == 0:
        raise ValueError("Digital asset not found")
    await db.commit()


def generate_download_url(asset_id: str, user_id: str, ttl: int = _DEFAULT_URL_TTL) -> dict[str, Any]:
    """Generate an HMAC-signed download token."""
    expires = int(time.time()) + ttl
    message = f"{asset_id}:{user_id}:{expires}"
    signature = hmac.new(
        settings.secret_key.encode(), message.encode(), hashlib.sha256,
    ).hexdigest()
    token = f"{asset_id}.{user_id}.{expires}.{signature}"
    return {"url": f"/api/ecommerce/downloads/{token}", "expires_in": ttl}


def verify_download_token(token: str) -> dict[str, str] | None:
    """Verify an HMAC-signed download token. Returns {asset_id, user_id} or None."""
    parts = token.split(".")
    if len(parts) != 4:
        return None

    asset_id, user_id, expires_str, signature = parts
    try:
        expires = int(expires_str)
    except ValueError:
        return None

    if time.time() > expires:
        return None

    message = f"{asset_id}:{user_id}:{expires}"
    expected = hmac.new(
        settings.secret_key.encode(), message.encode(), hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return None

    return {"asset_id": asset_id, "user_id": user_id}


async def check_download_limit(
    redis: Redis, asset_id: str, user_id: str, limit: int | None,
) -> bool:
    """Check if user is within download limit. Returns True if allowed."""
    if limit is None:
        return True
    key = f"{_DOWNLOAD_PREFIX}{asset_id}:{user_id}"
    count = await redis.get(key)
    return int(count or 0) < limit


async def increment_download_count(redis: Redis, asset_id: str, user_id: str) -> None:
    key = f"{_DOWNLOAD_PREFIX}{asset_id}:{user_id}"
    await redis.incr(key)
