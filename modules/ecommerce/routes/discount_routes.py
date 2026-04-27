"""Admin endpoints for discount/coupon management."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role

logger = logging.getLogger(__name__)
from modules.ecommerce.models.schemas import (
    DiscountCreate,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdate,
)
from modules.ecommerce.services import discount_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/discounts", response_model=DiscountListResponse)
async def admin_list_discounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await discount_service.list_discounts(
        db, page=page, page_size=page_size, status=status
    )


@router.get("/discounts/{discount_id}", response_model=DiscountResponse)
async def admin_get_discount(
    discount_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await discount_service.get_discount_by_id(db, discount_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Discount not found",
                "details": None,
            },
        )
    return result


@router.post("/discounts", response_model=DiscountResponse, status_code=201)
async def admin_create_discount(
    body: DiscountCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await discount_service.create_discount(db, body.model_dump())

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.coupon_created",
                {
                    "coupon_code": result.get("code", ""),
                    "type": result.get("type", ""),
                    "value": result.get("value", 0),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.coupon_created", exc_info=True)

    return result


@router.put("/discounts/{discount_id}", response_model=DiscountResponse)
async def admin_update_discount(
    discount_id: str,
    body: DiscountUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        result = await discount_service.update_discount(
            db, discount_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.coupon_updated",
                {
                    "discount_id": discount_id,
                    "coupon_code": result.get("code", ""),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.coupon_updated", exc_info=True)

    return result


@router.delete("/discounts/{discount_id}", status_code=204)
async def admin_deactivate_discount(
    discount_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Fetch discount info before deactivation for tracking
    discount_info = await discount_service.get_discount_by_id(db, discount_id)

    try:
        await discount_service.deactivate_discount(db, discount_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.coupon_deactivated",
                {
                    "discount_id": discount_id,
                    "coupon_code": (
                        discount_info.get("code", "") if discount_info else ""
                    ),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.coupon_deactivated", exc_info=True)
