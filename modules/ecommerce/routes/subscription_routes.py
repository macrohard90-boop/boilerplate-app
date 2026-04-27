"""Customer-facing subscription endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.ecommerce.models.schemas import SubscriptionCreate, SubscriptionResponse
from modules.ecommerce.services import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    body: SubscriptionCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a subscription for a recurring product."""
    try:
        return await subscription_service.create_subscription(
            db,
            user_id=str(user["user_id"]),
            email=user.get("email", ""),
            product_id=str(body.product_id),
            variant_id=str(body.variant_id) if body.variant_id else None,
            discount_code=body.discount_code,
            session_id=user.get("session_id"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.get("", response_model=list[SubscriptionResponse])
async def list_my_subscriptions(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List the current user's subscriptions."""
    return await subscription_service.list_user_subscriptions(db, str(user["user_id"]))


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Cancel a subscription at period end."""
    try:
        return await subscription_service.cancel_subscription(
            db, subscription_id, str(user["user_id"])
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )
