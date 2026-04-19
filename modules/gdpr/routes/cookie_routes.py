"""Cookie preference endpoints — works for both authenticated and guest users."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_optional_user
from modules.gdpr.models.schemas import (
    CookiePreferencesResponse,
    CookiePreferencesUpdate,
)
from modules.gdpr.services import cookie_service

router = APIRouter(tags=["gdpr-cookies"])


@router.get("/cookies", response_model=CookiePreferencesResponse)
async def get_cookie_preferences(
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Get current cookie preferences (auth or session-based)."""
    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    prefs = await cookie_service.get_preferences(
        db, user_id=user_id, session_id=session_id
    )

    if prefs:
        return CookiePreferencesResponse(**prefs)

    # No preferences set yet — return defaults
    return CookiePreferencesResponse()


@router.post("/cookies", response_model=CookiePreferencesResponse)
async def update_cookie_preferences(
    data: CookiePreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
    x_session_id: str | None = Header(None),
):
    """Update cookie preferences. `necessary` is always true."""
    user_id = user["user_id"] if user else None
    session_id = user.get("session_id") if user else x_session_id

    result = await cookie_service.update_preferences(
        db,
        analytics=data.analytics,
        marketing=data.marketing,
        preferences=data.preferences,
        user_id=user_id,
        session_id=session_id,
    )

    return CookiePreferencesResponse(**result)
