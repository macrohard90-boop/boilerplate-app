"""OAuth redirect and callback endpoints."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.redis import get_redis
from modules.auth.routes.auth_routes import _get_user_consent
from modules.auth.services import (
    auth_service,
    audit_service,
    oauth_service,
    session_service,
    token_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/oauth/providers")
async def list_oauth_providers() -> Any:
    """List configured OAuth providers."""
    return {"providers": oauth_service.list_providers()}


@router.get("/oauth/{provider}")
async def oauth_redirect(
    provider: str,
    request: Request,
    redis: Redis = Depends(get_redis),
) -> Any:
    """Redirect user to OAuth provider for consent."""
    prov = oauth_service.get_provider(provider)
    if not prov:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"OAuth provider '{provider}' not configured", "details": None},
        )

    # Capture returnTo from query params (default to /)
    return_to = request.query_params.get("returnTo", "/")
    if return_to.startswith("/auth"):
        return_to = "/"

    state = await oauth_service.create_state_token(redis, return_to=return_to)

    # Build callback URL
    callback_url = f"{settings.backend_url}/api/auth/oauth/{provider}/callback"

    auth_url = prov.get_authorization_url(state=state, redirect_uri=callback_url)
    return RedirectResponse(url=auth_url)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    """Handle OAuth callback: exchange code, create/link user, issue tokens."""
    # Validate state and retrieve returnTo
    return_to = await oauth_service.validate_state_token(redis, state)
    if return_to is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "Invalid or expired OAuth state", "details": None},
        )

    prov = oauth_service.get_provider(provider)
    if not prov:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider not found", "details": None})

    callback_url = f"{settings.backend_url}/api/auth/oauth/{provider}/callback"

    # Exchange code for tokens
    try:
        tokens = await prov.exchange_code(code, redirect_uri=callback_url)
    except Exception as e:
        logger.error("OAuth code exchange failed for %s: %s", provider, e)
        raise HTTPException(status_code=400, detail={"error": "oauth_error", "message": "Failed to exchange authorization code", "details": None})

    # Get user info
    try:
        user_info = await prov.get_user_info(tokens["access_token"])
    except Exception as e:
        logger.error("OAuth user info failed for %s: %s", provider, e)
        raise HTTPException(status_code=400, detail={"error": "oauth_error", "message": "Failed to get user info from provider", "details": None})

    # Find or create user
    user = await oauth_service.find_or_create_user(db, user_info)
    user_id = str(user["id"])

    # Create session and tokens
    permissions = await auth_service.get_user_permissions(db, user_id)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    device = request.headers.get("user-agent", "")[:255]

    now_ts = int(datetime.now(timezone.utc).timestamp())
    consent = await _get_user_consent(db, user_id)
    session_id = await session_service.create_session(
        redis, db, user_id, user["role"], device=device, ip=ip, user_agent=device,
        auth_time=now_ts, amr=["oauth"],
    )

    access = token_service.create_access_token(
        user_id, user["role"], session_id, permissions,
        auth_time=now_ts, amr=["oauth"], consent=consent, token_type="access",
    )
    refresh = await token_service.create_refresh_token(redis, user_id, session_id)

    await audit_service.log_audit(
        db, user_id=user_id, action="oauth.login", resource="user",
        resource_id=user_id, ip_address=ip, payload={"provider": provider},
    )

    # Redirect to frontend with access token
    # Refresh token is set as httpOnly cookie
    frontend_url = settings.frontend_url
    redirect_path = return_to if return_to and return_to.startswith("/") else "/"
    response = RedirectResponse(url=f"{frontend_url}{redirect_path}?token={access}")

    secure = settings.frontend_url.startswith("https://")
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/auth",
        max_age=settings.refresh_token_ttl,
    )

    return response
