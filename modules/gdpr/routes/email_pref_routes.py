"""Email preference management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.gdpr.models.schemas import (
    EmailPreferencesResponse,
    EmailPreferencesUpdate,
    MessageResponse,
    UnsubscribeRequest,
)
from modules.gdpr.services import email_pref_service

router = APIRouter(tags=["gdpr-email"])


@router.get("/email-preferences", response_model=EmailPreferencesResponse)
async def get_email_preferences(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get current email preferences."""
    prefs = await email_pref_service.get_preferences(db, user["user_id"])

    if prefs:
        return EmailPreferencesResponse(**prefs)

    # No preferences yet — return defaults
    return EmailPreferencesResponse(
        marketing_email=False,
        transactional_email=True,
    )


@router.put("/email-preferences", response_model=EmailPreferencesResponse)
async def update_email_preferences(
    data: EmailPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update email preferences."""
    result = await email_pref_service.update_preferences(
        db,
        user_id=user["user_id"],
        marketing_email=data.marketing_email,
        transactional_email=data.transactional_email,
    )
    return EmailPreferencesResponse(**result)


@router.post("/email-preferences/unsubscribe", response_model=MessageResponse)
async def one_click_unsubscribe(
    data: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """One-click unsubscribe from marketing emails. No auth required (token-based)."""
    try:
        result = await email_pref_service.unsubscribe_by_token(db, data.token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={
            "error": "bad_request",
            "message": str(e),
            "details": None,
        })

    return MessageResponse(**result)
