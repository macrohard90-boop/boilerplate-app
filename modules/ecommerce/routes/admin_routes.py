"""Admin endpoints: orders, inventory, reviews, digital assets, fee tiers."""

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
    FeeTierCreate,
    FeeTierResponse,
    FeeTierUpdate,
    InventoryAdjust,
    InventoryRecordResponse,
    LowStockResponse,
    MerchantFeeOverrideRequest,
    MerchantFeeOverrideResponse,
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
    fee_tier_service,
    inventory_service,
    order_service,
    review_service,
    subscription_service,
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
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Order not found",
                "details": None,
            },
        )
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
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


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
    return await inventory_service.adjust_stock(
        db, variant_id, body.quantity_change, body.reason
    )


@router.get("/inventory/low-stock", response_model=list[LowStockResponse])
async def admin_low_stock(
    threshold: int = Query(default=10, ge=0),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await inventory_service.get_low_stock(db, threshold)


# ---------------------------------------------------------------------------
# Admin Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions")
async def admin_list_subscriptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await subscription_service.list_all_subscriptions(
        db, page=page, page_size=page_size, status=status
    )


@router.post("/subscriptions/{subscription_id}/cancel")
async def admin_cancel_subscription(
    subscription_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await subscription_service.admin_cancel_subscription(db, subscription_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )


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
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


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
        return await digital_asset_service.update_asset(
            db, asset_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


@router.delete("/digital-assets/{asset_id}", status_code=204)
async def admin_delete_asset(
    asset_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await digital_asset_service.delete_asset(db, asset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


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
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Invalid or expired download link",
                "details": None,
            },
        )

    asset = await digital_asset_service.get_asset(db, data["asset_id"])
    if not asset:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Asset not found",
                "details": None,
            },
        )

    allowed = await digital_asset_service.check_download_limit(
        redis,
        data["asset_id"],
        data["user_id"],
        asset.get("download_limit"),
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "too_many_requests",
                "message": "Download limit reached",
                "details": None,
            },
        )

    await digital_asset_service.increment_download_count(
        redis, data["asset_id"], data["user_id"]
    )

    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=asset["file_url"])


# ---------------------------------------------------------------------------
# Admin Fee Tiers
# ---------------------------------------------------------------------------


@router.get("/fee-tiers", response_model=list[FeeTierResponse])
async def admin_list_fee_tiers(
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await fee_tier_service.list_default_tiers(db)


@router.post("/fee-tiers", response_model=FeeTierResponse, status_code=201)
async def admin_create_fee_tier(
    body: FeeTierCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await fee_tier_service.create_tier(db, body.model_dump())


@router.put("/fee-tiers/{tier_id}", response_model=FeeTierResponse)
async def admin_update_fee_tier(
    tier_id: str,
    body: FeeTierUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await fee_tier_service.update_tier(
            db, tier_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


@router.delete("/fee-tiers/{tier_id}", status_code=204)
async def admin_delete_fee_tier(
    tier_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await fee_tier_service.delete_tier(db, tier_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


# ---------------------------------------------------------------------------
# Merchant Fee Overrides
# ---------------------------------------------------------------------------


@router.get(
    "/merchants/{merchant_id}/fee-overrides",
    response_model=list[MerchantFeeOverrideResponse],
)
async def admin_get_merchant_fee_overrides(
    merchant_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await fee_tier_service.get_merchant_overrides(db, merchant_id)


@router.put(
    "/merchants/{merchant_id}/fee-overrides",
    response_model=list[MerchantFeeOverrideResponse],
)
async def admin_set_merchant_fee_overrides(
    merchant_id: str,
    body: MerchantFeeOverrideRequest,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await fee_tier_service.set_merchant_overrides(
        db, merchant_id, [t.model_dump() for t in body.tiers]
    )


@router.delete("/merchants/{merchant_id}/fee-overrides", status_code=204)
async def admin_clear_merchant_fee_overrides(
    merchant_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await fee_tier_service.clear_merchant_overrides(db, merchant_id)
