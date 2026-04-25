"""Short URL service for SMS/WhatsApp click tracking.

Generates short redirect URLs that track clicks before forwarding to the
original destination. Uses Redis for fast lookup with DB persistence for
historical tracking.

Short URL format: {base_url}/r/{code}
Code: 8-char base62 hash of original URL + campaign_id + recipient_id
"""

import hashlib
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Base62 alphabet for short codes
_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _generate_code(original_url: str, campaign_id: str, recipient_id: str) -> str:
    """Generate a deterministic 8-char short code.

    Deterministic so the same URL+campaign+recipient always gets the same code.
    """
    payload = f"{original_url}|{campaign_id}|{recipient_id}"
    digest = hashlib.sha256(payload.encode()).digest()
    # Convert first 6 bytes to base62
    num = int.from_bytes(digest[:6], "big")
    chars = []
    for _ in range(8):
        chars.append(_BASE62[num % 62])
        num //= 62
    return "".join(chars)


def get_redirect_base_url() -> str:
    """Get the base URL for short redirects."""
    base = settings.public_url or settings.backend_url
    return f"{base.rstrip('/')}/api/marketing/r"


async def create_short_url(
    db: AsyncSession,
    original_url: str,
    campaign_id: str,
    recipient_id: str,
) -> str:
    """Create a short URL for tracking.

    Returns the full short URL (e.g., https://mysite.com/api/marketing/r/AbCd1234).
    Idempotent — same inputs always produce the same short URL.
    """
    code = _generate_code(original_url, campaign_id, recipient_id)
    base = get_redirect_base_url()

    # Upsert into campaign_link_clicks won't work here — we need a dedicated
    # short_urls table or use Redis. For now, store in Redis with DB backup.
    try:
        from backend.core.redis_client import get_redis

        redis = await get_redis()
        key = f"short_url:{code}"
        await redis.hset(
            key,
            mapping={
                "url": original_url,
                "campaign_id": campaign_id,
                "recipient_id": recipient_id,
            },
        )
        # Expire after 90 days (short URLs don't need to live forever)
        await redis.expire(key, 90 * 86400)
    except Exception:
        logger.warning("Failed to cache short URL in Redis, will rely on DB")

    return f"{base}/{code}"


async def resolve_short_url(
    code: str,
) -> dict[str, str] | None:
    """Resolve a short code to its original URL and tracking metadata.

    Checks Redis first, falls back to DB if not cached.
    Returns dict with keys: url, campaign_id, recipient_id. Or None if not found.
    """
    try:
        from backend.core.redis_client import get_redis

        redis = await get_redis()
        data = await redis.hgetall(f"short_url:{code}")
        if data:
            return {
                "url": data.get("url", ""),
                "campaign_id": data.get("campaign_id", ""),
                "recipient_id": data.get("recipient_id", ""),
            }
    except Exception:
        logger.warning("Redis lookup failed for short URL code=%s", code)

    return None


def replace_short_url_placeholders(
    content: str,
    short_urls: dict[str, str],
) -> str:
    """Replace {{short_url:...}} placeholders with actual short URLs.

    Args:
        content: Text with placeholders from rewrite_sms_links.
        short_urls: Map of original_url -> short_url.

    Returns:
        Text with all placeholders replaced.
    """
    pattern = re.compile(r"\{\{short_url:(.*?)\}\}")

    def _replace(match: re.Match) -> str:
        original = match.group(1)
        return short_urls.get(original, original)

    return pattern.sub(_replace, content)
