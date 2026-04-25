"""Campaign attribution middleware and store.

Captures _cid (campaign_id) and _rid (recipient_id) from inbound links,
stores attribution data in Redis (keyed by user_id), and sets a cookie
for anonymous users. All DB/Redis writes are fire-and-forget background
tasks — zero added latency on the request path.

Attribution cookie: _mattr = JSON {campaign_id, recipient_id, medium, touches: [...]}
Redis key: attr:{user_id} = JSON {campaign_id, recipient_id, medium, first_touch_at, last_touch_at, touches}
TTL: attribution_window_days from campaign (default 7 days)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Redis key prefix for attribution data
_ATTR_PREFIX = "attr:"
# Default attribution window (days) if campaign doesn't specify
_DEFAULT_WINDOW_DAYS = 7
# Cookie name for attribution
_COOKIE_NAME = "_mattr"
# Cookie max age — 30 days (covers longest attribution window)
_COOKIE_MAX_AGE = 30 * 24 * 3600


class AttributionMiddleware(BaseHTTPMiddleware):
    """Capture campaign attribution params from inbound links.

    Fires on all non-API requests. Checks for _cid/_rid query params,
    stores attribution in Redis (for logged-in users) and cookie (for all).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not settings.enable_marketing:
            return await call_next(request)

        # Only check for attribution params on GET requests (landing pages)
        if request.method != "GET":
            return await call_next(request)

        # Skip API routes
        path = request.url.path
        if path.startswith("/api/"):
            return await call_next(request)

        response = await call_next(request)

        # Check for attribution params in background
        url = str(request.url)
        qs = parse_qs(urlparse(url).query)
        cid = qs.get("_cid", [None])[0]

        if cid:
            rid = qs.get("_rid", [None])[0]
            medium = qs.get("utm_medium", [None])[0] or "email"

            # Get user context
            user = getattr(request.state, "user", None)
            user_id = user["user_id"] if user else None

            # Read existing cookie
            existing_cookie = request.cookies.get(_COOKIE_NAME)

            # Fire-and-forget: store attribution
            try:
                asyncio.create_task(
                    _store_attribution(user_id, cid, rid, medium, existing_cookie)
                )
            except Exception:
                logger.debug("Failed to schedule attribution task", exc_info=True)

            # Set/update cookie on response
            cookie_data = _build_cookie_data(cid, rid, medium, existing_cookie)
            response.set_cookie(
                key=_COOKIE_NAME,
                value=json.dumps(cookie_data),
                max_age=_COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=settings.app_env != "development",
                path="/",
            )

        return response


async def _store_attribution(
    user_id: str | None,
    campaign_id: str,
    recipient_id: str | None,
    medium: str,
    existing_cookie: str | None,
) -> None:
    """Store attribution data in Redis for the user.

    If user is anonymous (no user_id), we rely on the cookie.
    When they log in, merge_anonymous_attribution() should be called.
    """
    if not user_id:
        return

    try:
        from backend.core.redis import get_redis

        redis = await get_redis()
        key = f"{_ATTR_PREFIX}{user_id}"
        now = datetime.now(timezone.utc).isoformat()

        # Read existing attribution data
        existing = await redis.get(key)
        if existing:
            data = json.loads(existing)
            touches = data.get("touches", [])
        else:
            touches = []

        # Add new touch
        touch = {
            "campaign_id": campaign_id,
            "recipient_id": recipient_id,
            "medium": medium,
            "ts": now,
        }
        touches.append(touch)

        # Build attribution record
        attr_data = {
            "campaign_id": campaign_id,
            "recipient_id": recipient_id,
            "medium": medium,
            "first_touch_at": touches[0]["ts"],
            "last_touch_at": now,
            "touches": touches[-20:],  # Keep last 20 touches
        }

        # Store with TTL = attribution window
        ttl = _DEFAULT_WINDOW_DAYS * 86400
        await redis.setex(key, ttl, json.dumps(attr_data))

        logger.debug(
            "Attribution stored: user=%s campaign=%s touches=%d",
            user_id,
            campaign_id,
            len(attr_data["touches"]),
        )

    except Exception:
        logger.debug("Attribution store error (non-fatal)", exc_info=True)


def _build_cookie_data(
    campaign_id: str,
    recipient_id: str | None,
    medium: str,
    existing_cookie: str | None,
) -> dict:
    """Build attribution cookie data, merging with existing touches."""
    now = datetime.now(timezone.utc).isoformat()

    touches = []
    if existing_cookie:
        try:
            existing = json.loads(existing_cookie)
            touches = existing.get("touches", [])
        except (json.JSONDecodeError, TypeError):
            pass

    touches.append(
        {
            "campaign_id": campaign_id,
            "recipient_id": recipient_id,
            "medium": medium,
            "ts": now,
        }
    )

    return {
        "campaign_id": campaign_id,
        "recipient_id": recipient_id,
        "medium": medium,
        "first_touch_at": touches[0]["ts"],
        "last_touch_at": now,
        "touches": touches[-20:],
    }


async def get_attribution(user_id: str) -> dict | None:
    """Get current attribution data for a user from Redis.

    Returns the attribution dict or None if no attribution exists.
    Called by conversion_service at conversion time.
    """
    try:
        from backend.core.redis import get_redis

        redis = await get_redis()
        data = await redis.get(f"{_ATTR_PREFIX}{user_id}")
        if data:
            return json.loads(data)
    except Exception:
        logger.debug("Failed to read attribution for user=%s", user_id, exc_info=True)
    return None


async def get_attribution_from_cookie(cookie_value: str) -> dict | None:
    """Parse attribution data from cookie string."""
    try:
        return json.loads(cookie_value)
    except (json.JSONDecodeError, TypeError):
        return None


async def merge_anonymous_attribution(user_id: str, cookie_value: str) -> None:
    """Merge anonymous cookie attribution into Redis when user logs in.

    Called from auth routes after successful login/registration.
    """
    cookie_data = await get_attribution_from_cookie(cookie_value)
    if not cookie_data or not cookie_data.get("campaign_id"):
        return

    try:
        from backend.core.redis import get_redis

        redis = await get_redis()
        key = f"{_ATTR_PREFIX}{user_id}"

        existing = await redis.get(key)
        if existing:
            data = json.loads(existing)
            # Merge touches — cookie touches come first (they're older)
            cookie_touches = cookie_data.get("touches", [])
            redis_touches = data.get("touches", [])
            merged = cookie_touches + redis_touches
            data["touches"] = merged[-20:]
            data["first_touch_at"] = (
                merged[0]["ts"] if merged else data.get("first_touch_at")
            )
        else:
            data = cookie_data

        ttl = _DEFAULT_WINDOW_DAYS * 86400
        await redis.setex(key, ttl, json.dumps(data))

        logger.debug("Merged anonymous attribution for user=%s", user_id)

    except Exception:
        logger.debug("Attribution merge error (non-fatal)", exc_info=True)


async def clear_attribution(user_id: str) -> None:
    """Clear attribution data after conversion is recorded."""
    try:
        from backend.core.redis import get_redis

        redis = await get_redis()
        await redis.delete(f"{_ATTR_PREFIX}{user_id}")
    except Exception:
        pass
