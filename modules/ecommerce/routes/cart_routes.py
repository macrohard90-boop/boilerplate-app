"""Shopping cart endpoints supporting both guest and authenticated users."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import get_current_user, get_optional_user
from backend.core.redis import get_redis
from modules.ecommerce.models.schemas import (
    CartDiscountApply,
    CartItemAdd,
    CartItemUpdate,
    CartResponse,
)
from modules.ecommerce.services import cart_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cart", tags=["cart"])


def _get_session_id(x_session_id: str | None = Header(default=None)) -> str | None:
    return x_session_id


@router.get("", response_model=CartResponse)
async def get_cart(
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    return await cart_service.get_cart(db, redis, user, session_id)


@router.post("/items", response_model=CartResponse)
async def add_item(
    body: CartItemAdd,
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    if not user and not session_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "Provide X-Session-ID header or authenticate",
                "details": None,
            },
        )
    variant_id = str(body.variant_id) if body.variant_id else None
    try:
        result = await cart_service.add_item(
            db,
            redis,
            user,
            session_id,
            str(body.product_id),
            variant_id,
            body.quantity,
        )
        if settings.enable_tracking and not session_id and user:
            _row = (
                (
                    await db.execute(
                        text(
                            "SELECT session_id FROM analytics.analytics_sessions "
                            "WHERE user_id = :uid ORDER BY ended_at DESC NULLS FIRST LIMIT 1"
                        ),
                        {"uid": user["user_id"]},
                    )
                )
                .mappings()
                .first()
            )
            if _row:
                session_id = _row["session_id"]
        if settings.enable_tracking and session_id:
            try:
                from modules.tracking.services.event_service import record_event

                user_id = user["user_id"] if user else None
                await record_event(
                    db,
                    session_id,
                    "add_to_cart",
                    {
                        "product_id": str(body.product_id),
                        "quantity": body.quantity,
                    },
                    user_id=user_id,
                )
            except Exception:
                logger.debug("Failed to record add_to_cart event", exc_info=True)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.put("/items/{product_id}_{variant_id}", response_model=CartResponse)
async def update_item(
    product_id: str,
    variant_id: str,
    body: CartItemUpdate,
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        return await cart_service.update_item(
            db, redis, user, session_id, product_id, variant_id, body.quantity
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.delete("/items/{product_id}_{variant_id}", response_model=CartResponse)
async def remove_item(
    product_id: str,
    variant_id: str,
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        result = await cart_service.remove_item(
            db, redis, user, session_id, product_id, variant_id
        )
        if settings.enable_tracking and not session_id and user:
            _row = (
                (
                    await db.execute(
                        text(
                            "SELECT session_id FROM analytics.analytics_sessions "
                            "WHERE user_id = :uid ORDER BY ended_at DESC NULLS FIRST LIMIT 1"
                        ),
                        {"uid": user["user_id"]},
                    )
                )
                .mappings()
                .first()
            )
            if _row:
                session_id = _row["session_id"]
        if settings.enable_tracking and session_id:
            try:
                from modules.tracking.services.event_service import record_event

                user_id = user["user_id"] if user else None
                await record_event(
                    db,
                    session_id,
                    "remove_from_cart",
                    {
                        "product_id": product_id,
                        "variant_id": variant_id,
                    },
                    user_id=user_id,
                )
            except Exception:
                logger.debug("Failed to record remove_from_cart event", exc_info=True)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.post("/discount", response_model=CartResponse)
async def apply_discount(
    body: CartDiscountApply,
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    if not settings.enable_coupons:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Coupons are not enabled",
                "details": None,
            },
        )
    try:
        return await cart_service.apply_discount(db, redis, user, session_id, body.code)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.delete("/discount", response_model=CartResponse)
async def remove_discount(
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    if not settings.enable_coupons:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Coupons are not enabled",
                "details": None,
            },
        )
    try:
        return await cart_service.remove_discount(db, redis, user, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.delete("", response_model=CartResponse)
async def clear_cart(
    user: dict | None = Depends(get_optional_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        return await cart_service.clear_cart(db, redis, user, session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


@router.post("/merge", response_model=CartResponse)
async def merge_cart(
    user: dict = Depends(get_current_user),
    session_id: str | None = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "X-Session-ID header required for merge",
                "details": None,
            },
        )
    return await cart_service.merge_cart(db, redis, user["user_id"], session_id)
