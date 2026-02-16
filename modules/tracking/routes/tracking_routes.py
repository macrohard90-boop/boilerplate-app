"""Tracking collection endpoints — page views and events."""

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import get_optional_user
from backend.core.redis import get_redis
from modules.tracking.models.schemas import (
    ErrorResponse,
    EventBatch,
    EventCreate,
    PageViewBatch,
    PageViewCreate,
    TrackingResponse,
)
from modules.tracking.services import (
    consent_service,
    event_service,
    pageview_service,
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
    )

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
