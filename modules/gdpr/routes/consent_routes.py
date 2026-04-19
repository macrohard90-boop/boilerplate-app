"""Consent management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.gdpr.models.schemas import (
    ConsentHistoryResponse,
    ConsentState,
    ConsentTypeState,
    ConsentUpdate,
    MessageResponse,
)
from modules.gdpr.services import consent_service

router = APIRouter(tags=["gdpr-consent"])


@router.get("/consent", response_model=ConsentState)
async def get_consent(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get current consent state for all consent types."""
    state = await consent_service.get_consent_state(db, user["user_id"])
    return ConsentState(consents=[ConsentTypeState(**s) for s in state])


@router.post("/consent", response_model=MessageResponse)
async def update_consent(
    data: ConsentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Grant or revoke a specific consent type."""
    ip = request.client.host if request.client else None
    try:
        await consent_service.update_consent(
            db,
            user_id=user["user_id"],
            consent_type=data.consent_type,
            granted=data.granted,
            ip_address=ip,
            version=data.version,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": str(e),
                "details": None,
            },
        )

    action = "granted" if data.granted else "revoked"
    return MessageResponse(message=f"Consent {data.consent_type} {action}")


@router.get("/consent/history", response_model=ConsentHistoryResponse)
async def get_consent_history(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get paginated consent change history."""
    result = await consent_service.get_consent_history(
        db, user["user_id"], page=page, page_size=page_size
    )
    return ConsentHistoryResponse(**result)
