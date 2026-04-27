"""Order endpoints for authenticated users."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, validate_csrf
from modules.ecommerce.models.schemas import (
    OrderCreate,
    OrderDetailResponse,
    OrderListResponse,
    OrderResponse,
)
from modules.ecommerce.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    body: OrderCreate,
    user: dict = Depends(validate_csrf),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        order = await order_service.create_order_from_cart(
            db, user["user_id"], session_id=user.get("session_id")
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )

    # Update addresses if provided
    if body.shipping_address or body.billing_address:
        from sqlalchemy import text

        updates = []
        params: dict[str, Any] = {"oid": str(order["id"])}
        if body.shipping_address:
            import json

            updates.append("shipping_address = CAST(:ship AS jsonb)")
            params["ship"] = json.dumps(body.shipping_address)
        if body.billing_address:
            import json

            updates.append("billing_address = CAST(:bill AS jsonb)")
            params["bill"] = json.dumps(body.billing_address)
        if updates:
            await db.execute(
                text(
                    f"UPDATE ecommerce.orders SET {', '.join(updates)} WHERE id = :oid"
                ),
                params,
            )
            await db.commit()
            order = await order_service.get_order(db, str(order["id"]))

    return order


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await order_service.list_orders(
        db, user["user_id"], page=page, page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    order = await order_service.get_order(db, order_id, user["user_id"])
    if not order:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Order not found",
                "details": None,
            },
        )
    return order
