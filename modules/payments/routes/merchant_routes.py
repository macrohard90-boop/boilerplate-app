"""Merchant onboarding endpoints (Stripe Connect Express)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, require_role
from modules.payments.models.schemas import (
    ErrorResponse,
    MerchantDashboardResponse,
    MerchantOnboardRequest,
    MerchantOnboardResponse,
    MerchantStatusResponse,
)
from modules.payments.services import merchant_service

router = APIRouter(prefix="/merchants", tags=["payments-merchants"])


@router.post(
    "/onboard",
    response_model=MerchantOnboardResponse,
    responses={400: {"model": ErrorResponse}},
)
async def onboard_merchant(
    data: MerchantOnboardRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("merchant")),
):
    """Generate Stripe Connect onboarding link for merchant."""
    try:
        result = await merchant_service.onboard_merchant(
            db,
            user_id=str(user["user_id"]),
            business_name=data.business_name,
            business_type=data.business_type,
            country=data.country,
        )
        return MerchantOnboardResponse(
            account_id=result["account_id"],
            onboarding_url=result["onboarding_url"],
            status=result["status"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "onboard_failed", "message": str(e), "details": None},
        )


@router.get(
    "/status",
    response_model=MerchantStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_merchant_status(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("merchant")),
):
    """Check merchant onboarding status."""
    result = await merchant_service.get_merchant_status(db, str(user["user_id"]))
    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "No merchant account found. Start onboarding first.",
                "details": None,
            },
        )
    return MerchantStatusResponse(**result)


@router.get(
    "/dashboard-link",
    response_model=MerchantDashboardResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_dashboard_link(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("merchant")),
):
    """Generate Stripe Express dashboard login link."""
    url = await merchant_service.get_dashboard_link(db, str(user["user_id"]))
    if not url:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "No active merchant account found",
                "details": None,
            },
        )
    return MerchantDashboardResponse(dashboard_url=url)
