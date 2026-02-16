"""Admin endpoints: orders, inventory, discounts, reviews, digital assets."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role
from redis.asyncio import Redis

from backend.core.redis import get_redis
from modules.ecommerce.models.schemas import (
    DigitalAssetCreate,
    DigitalAssetResponse,
    DigitalAssetUpdate,
    DiscountCreate,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdate,
    DownloadUrlResponse,
    InventoryAdjust,
    InventoryRecordResponse,
    LowStockResponse,
    OrderDetailResponse,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
    ReviewModerate,
    ReviewResponse,
)
from backend.core.dependencies import get_current_user
from modules.ecommerce.services import (
    digital_asset_service,
    discount_service,
    inventory_service,
    order_service,
    review_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Admin Orders
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=OrderListResponse)
async def admin_list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await order_service.list_orders(db, page=page, page_size=page_size)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def admin_get_order(
    order_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Order not found", "details": None})
    return order


@router.put("/orders/{order_id}/status", response_model=OrderResponse)
async def admin_update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await order_service.update_order_status(db, order_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Admin Inventory
# ---------------------------------------------------------------------------


@router.post("/inventory/{variant_id}/adjust", response_model=InventoryRecordResponse)
async def admin_adjust_inventory(
    variant_id: str,
    body: InventoryAdjust,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await inventory_service.adjust_stock(db, variant_id, body.quantity_change, body.reason)


@router.get("/inventory/low-stock", response_model=list[LowStockResponse])
async def admin_low_stock(
    threshold: int = Query(default=10, ge=0),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await inventory_service.get_low_stock(db, threshold)


# ---------------------------------------------------------------------------
# Admin Discounts
# ---------------------------------------------------------------------------


@router.get("/discounts", response_model=DiscountListResponse)
async def admin_list_discounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await discount_service.list_discounts(db, page=page, page_size=page_size)


@router.post("/discounts", response_model=DiscountResponse, status_code=201)
async def admin_create_discount(
    body: DiscountCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await discount_service.create_discount(db, body.model_dump())


@router.put("/discounts/{discount_id}", response_model=DiscountResponse)
async def admin_update_discount(
    discount_id: str,
    body: DiscountUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await discount_service.update_discount(db, discount_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


@router.delete("/discounts/{discount_id}", status_code=204)
async def admin_deactivate_discount(
    discount_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await discount_service.deactivate_discount(db, discount_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Admin Reviews
# ---------------------------------------------------------------------------


@router.put("/reviews/{review_id}/moderate", response_model=ReviewResponse)
async def admin_moderate_review(
    review_id: str,
    body: ReviewModerate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await review_service.moderate_review(db, review_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Admin Digital Assets
# ---------------------------------------------------------------------------


@router.post("/digital-assets", response_model=DigitalAssetResponse, status_code=201)
async def admin_create_asset(
    body: DigitalAssetCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await digital_asset_service.create_asset(db, body.model_dump())


@router.put("/digital-assets/{asset_id}", response_model=DigitalAssetResponse)
async def admin_update_asset(
    asset_id: str,
    body: DigitalAssetUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await digital_asset_service.update_asset(db, asset_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


@router.delete("/digital-assets/{asset_id}", status_code=204)
async def admin_delete_asset(
    asset_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await digital_asset_service.delete_asset(db, asset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Download endpoint (authenticated users)
# ---------------------------------------------------------------------------


@router.get("/downloads/{token}")
async def download_file(
    token: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    data = digital_asset_service.verify_download_token(token)
    if not data or data["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Invalid or expired download link", "details": None})

    asset = await digital_asset_service.get_asset(db, data["asset_id"])
    if not asset:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Asset not found", "details": None})

    allowed = await digital_asset_service.check_download_limit(
        redis, data["asset_id"], data["user_id"], asset.get("download_limit"),
    )
    if not allowed:
        raise HTTPException(status_code=429, detail={"error": "too_many_requests", "message": "Download limit reached", "details": None})

    await digital_asset_service.increment_download_count(redis, data["asset_id"], data["user_id"])

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=asset["file_url"])
