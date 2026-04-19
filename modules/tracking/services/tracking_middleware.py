"""Non-blocking tracking middleware.

Automatically records page views, parses user agents, extracts UTM params,
and manages analytics sessions for every request. All DB writes happen in
background tasks to avoid adding latency.
"""

import asyncio
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.core.config import settings
from backend.core.database import get_session_factory
from backend.core.redis import get_redis

logger = logging.getLogger(__name__)

# Path prefixes to exclude from auto-tracking
_EXCLUDE_PREFIXES: list[str] = []


def _load_excludes() -> None:
    global _EXCLUDE_PREFIXES
    if not _EXCLUDE_PREFIXES:
        _EXCLUDE_PREFIXES = [
            p.strip() for p in settings.tracking_exclude_paths.split(",") if p.strip()
        ]
        # Always exclude tracking endpoints to avoid recursion
        _EXCLUDE_PREFIXES.append("/api/tracking")
        # Exclude all API routes — only frontend pages should be tracked
        _EXCLUDE_PREFIXES.append("/api/")


class TrackingMiddleware(BaseHTTPMiddleware):
    """Auto-track page views and sessions for all requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not settings.enable_tracking:
            return await call_next(request)

        _load_excludes()
        path = request.url.path

        # Skip excluded paths
        if any(path.startswith(prefix) for prefix in _EXCLUDE_PREFIXES):
            return await call_next(request)

        # Get response first (non-blocking — tracking happens after)
        response = await call_next(request)

        # Fire-and-forget tracking in background
        try:
            asyncio.create_task(_track_request(request, path))
        except Exception:
            logger.debug("Failed to schedule tracking task", exc_info=True)

        return response


async def _track_request(request: Request, path: str) -> None:
    """Background task: record pageview, session, user agent, referral, UTM."""
    try:
        from modules.tracking.services import (
            agent_service,
            consent_service,
            pageview_service,
            referral_service,
            session_service,
            utm_service,
        )

        # Get user context if available
        user = getattr(request.state, "user", None)
        user_id = user["user_id"] if user else None
        session_id = (
            user.get("session_id") if user else request.headers.get("x-session-id")
        )

        if not session_id:
            session_id = str(uuid.uuid4())

        # Use a fresh DB session for background work
        async with get_session_factory()() as db:
            # GDPR consent check
            has_consent = await consent_service.has_analytics_consent(
                db, user_id=user_id, session_id=session_id
            )
            if not has_consent:
                return

            # Get Redis connection
            redis = await get_redis()

            # Create/update analytics session
            session_id = await session_service.get_or_create_session(
                db, redis, session_id=session_id, user_id=user_id
            )

            # Record page view
            referrer = request.headers.get("referer")
            await pageview_service.record_pageview(
                db,
                session_id=session_id,
                path=path,
                user_id=user_id,
                referrer=referrer,
            )

            # Parse and store user agent (once per session)
            ua = request.headers.get("user-agent", "")
            if ua:
                await agent_service.store_user_agent(db, session_id, ua)

            # Parse and store referral source (once per session)
            if referrer:
                ref_data = referral_service.parse_referrer(referrer)
                await referral_service.store_referral(db, session_id, ref_data)

            # Extract and store UTM parameters
            url = str(request.url)
            utm_params = utm_service.extract_utm_params(url)
            if utm_service.has_utm_params(utm_params):
                await utm_service.store_utm(db, session_id, utm_params)

    except Exception:
        logger.debug("Tracking middleware error (non-fatal)", exc_info=True)
