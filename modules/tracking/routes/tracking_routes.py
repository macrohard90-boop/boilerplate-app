"""Tracking collection endpoints — page views and events."""

import logging
import time

from fastapi import APIRouter, Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import get_optional_user
from backend.core.redis import get_redis
from modules.tracking.models.schemas import (
    EventBatch,
    EventCreate,
    HeartbeatCreate,
    PageViewBatch,
    PageViewCreate,
    TrackingResponse,
)
from modules.tracking.services import (
    agent_service,
    consent_service,
    event_service,
    pageview_service,
    referral_service,
    session_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tracking"])


def _get_session_id(
    request: Request,
    x_session_id: str | None = Header(None),
) -> str | None:
    """Extract session ID from header or generate one."""
    return x_session_id


@router.post(
    "/pageview",
    response_model=TrackingResponse,
    responses={200: {"model": TrackingResponse}},
)
async def record_pageview(
    data: PageViewCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Record a single page view."""
    if not settings.enable_tracking:
        return TrackingResponse(recorded=0, session_id=x_session_id or "")

    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    # GDPR consent check
    has_consent = await consent_service.has_analytics_consent(
        db, user_id=user_id, session_id=session_id
    )
    if not has_consent:
        return TrackingResponse(recorded=0, session_id=session_id or "")

    # Get or create analytics session
    session_id = await session_service.get_or_create_session(
        db, redis, session_id=session_id, user_id=user_id
    )

    # Record in background
    await pageview_service.record_pageview(
        db,
        session_id=session_id,
        path=data.path,
        user_id=user_id,
        referrer=data.referrer,
        duration_ms=data.duration_ms,
        trigger=data.trigger,
    )

    # Parse and store user agent (once per session)
    ua = request.headers.get("user-agent", "")
    if ua:
        await agent_service.store_user_agent(db, session_id, ua)

    # Parse and store referral source (once per session, ON CONFLICT ignores duplicates)
    if data.referrer is not None:
        ref_data = referral_service.parse_referrer(data.referrer or None)
        await referral_service.store_referral(db, session_id, ref_data)

    return TrackingResponse(recorded=1, session_id=session_id)


@router.post(
    "/pageviews/batch",
    response_model=TrackingResponse,
)
async def record_pageviews_batch(
    data: PageViewBatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Record multiple page views in a single request."""
    if not settings.enable_tracking:
        return TrackingResponse(recorded=0, session_id=x_session_id or "")

    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    has_consent = await consent_service.has_analytics_consent(
        db, user_id=user_id, session_id=session_id
    )
    if not has_consent:
        return TrackingResponse(recorded=0, session_id=session_id or "")

    session_id = await session_service.get_or_create_session(
        db, redis, session_id=session_id, user_id=user_id
    )

    items = [item.model_dump() for item in data.items]
    count = await pageview_service.record_pageviews_batch(
        db, session_id=session_id, items=items, user_id=user_id
    )

    return TrackingResponse(recorded=count, session_id=session_id)


@router.post(
    "/events",
    response_model=TrackingResponse,
)
async def record_event(
    data: EventCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Record a single custom event."""
    if not settings.enable_tracking:
        return TrackingResponse(recorded=0, session_id=x_session_id or "")

    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    has_consent = await consent_service.has_analytics_consent(
        db, user_id=user_id, session_id=session_id
    )
    if not has_consent:
        return TrackingResponse(recorded=0, session_id=session_id or "")

    session_id = await session_service.get_or_create_session(
        db, redis, session_id=session_id, user_id=user_id
    )

    await event_service.record_event(
        db,
        session_id=session_id,
        event_type=data.event_type,
        event_data=data.event_data,
        user_id=user_id,
    )

    return TrackingResponse(recorded=1, session_id=session_id)


@router.post(
    "/events/batch",
    response_model=TrackingResponse,
)
async def record_events_batch(
    data: EventBatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Record multiple events in a single request."""
    if not settings.enable_tracking:
        return TrackingResponse(recorded=0, session_id=x_session_id or "")

    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    has_consent = await consent_service.has_analytics_consent(
        db, user_id=user_id, session_id=session_id
    )
    if not has_consent:
        return TrackingResponse(recorded=0, session_id=session_id or "")

    session_id = await session_service.get_or_create_session(
        db, redis, session_id=session_id, user_id=user_id
    )

    items = [item.model_dump() for item in data.items]
    count = await event_service.record_events_batch(
        db, session_id=session_id, items=items, user_id=user_id
    )

    return TrackingResponse(recorded=count, session_id=session_id)


@router.post(
    "/heartbeat",
    response_model=TrackingResponse,
    responses={200: {"model": TrackingResponse}},
)
async def record_heartbeat(
    data: HeartbeatCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Record a presence heartbeat. Redis-only, no DB writes."""
    if not settings.enable_tracking:
        return TrackingResponse(recorded=0, session_id=x_session_id or "")

    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    # GDPR consent check
    has_consent = await consent_service.has_analytics_consent(
        db, user_id=user_id, session_id=session_id
    )
    if not has_consent:
        return TrackingResponse(recorded=0, session_id=session_id or "")

    if not session_id:
        return TrackingResponse(recorded=0, session_id="")

    # Check if session exists in Redis — refresh TTL if so, else create it
    session_key = f"analytics:session:{session_id}"
    timeout = settings.tracking_session_timeout * 60
    exists = await redis.exists(session_key)
    if exists:
        await redis.expire(session_key, timeout)
    else:
        # Session not in Redis — ensure it exists via normal flow
        session_id = await session_service.get_or_create_session(
            db, redis, session_id=session_id, user_id=user_id
        )

    # Write presence hash (Redis-only, 90s TTL = 3x heartbeat interval)
    now_ms = int(time.time() * 1000)
    presence_key = f"analytics:presence:{session_id}"

    # Check if path changed or key is new
    raw_presence = await redis.hgetall(presence_key)
    # Normalize keys/values — Redis may return str or bytes depending on config
    old_presence: dict[str, str] = (
        {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw_presence.items()
        }
        if raw_presence
        else {}
    )
    old_path = old_presence.get("path", "")

    presence_data: dict[str, str] = {
        "path": data.path,
        "status": data.status,
        "last_heartbeat": str(now_ms),
    }

    # Set page_entered_at only when path changes or key is new
    if not old_presence or old_path != data.path:
        presence_data["page_entered_at"] = str(now_ms)
    # Set idle_since
    if data.status == "idle":
        # Only set idle_since when transitioning to idle
        old_status = old_presence.get("status", "")
        if old_status != "idle":
            presence_data["idle_since"] = str(now_ms)
    else:
        presence_data["idle_since"] = "0"

    # Track when the current active segment started
    if data.status == "active":
        old_status = old_presence.get("status", "")
        if not old_presence or old_path != data.path or old_status != "active":
            presence_data["active_since"] = str(now_ms)
    # Don't clear active_since when idle — keep for gap computation

    # Idle presence persists for the full session timeout (user walked away).
    # Active presence uses short TTL (3x heartbeat) for quick "gone" detection.
    presence_ttl = timeout if data.status == "idle" else 90

    pipe = redis.pipeline()
    pipe.hset(presence_key, mapping=presence_data)
    pipe.expire(presence_key, presence_ttl)
    await pipe.execute()

    return TrackingResponse(recorded=1, session_id=session_id)
