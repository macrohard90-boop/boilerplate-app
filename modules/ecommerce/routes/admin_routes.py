"""Admin endpoints: orders, inventory, reviews, digital assets, fee tiers."""

import json as _json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
from redis.asyncio import Redis

from backend.core.redis import get_redis

logger = logging.getLogger(__name__)
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


@router.get("/orders/{order_id}/full-detail")
async def admin_get_order_full_detail(
    order_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Aggregated order detail with payment, customer, and attribution data."""

    def _ts(v: Any) -> str | None:
        return v.isoformat() if v else None

    # 1. Order basics
    o = (
        (
            await db.execute(
                text(
                    "SELECT id, user_id, order_number, status, currency, "
                    "subtotal, discount_amount, tax_amount, total, "
                    "shipping_address, billing_address, created_at, updated_at "
                    "FROM ecommerce.orders WHERE id = :oid"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .first()
    )
    if not o:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Order not found",
                "details": None,
            },
        )

    user_id = str(o["user_id"])
    order_time = o["created_at"]
    # Pre-compute time window for attribution/UTM lookups
    from datetime import timedelta

    ot_before = order_time - timedelta(minutes=5)
    ot_after = order_time + timedelta(minutes=5)
    ot_hour_before = order_time - timedelta(hours=1)
    ot_hour_after = order_time + timedelta(hours=1)

    # 2. Order items
    items_rows = (
        (
            await db.execute(
                text(
                    "SELECT product_id, variant_id, quantity, unit_price, "
                    "total_price, product_snapshot "
                    "FROM ecommerce.order_items WHERE order_id = :oid"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .all()
    )

    # 3. Customer info
    cu = (
        (
            await db.execute(
                text(
                    "SELECT u.id, u.email, u.first_name, u.last_name, "
                    "cm.rfm_segment, cm.order_count, cm.total_spent, "
                    "cm.default_currency "
                    "FROM core.users u "
                    "LEFT JOIN ecommerce.customer_metrics cm ON cm.user_id = u.id "
                    "WHERE u.id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 4. Payment record (most recent for this order)
    pr = (
        (
            await db.execute(
                text(
                    "SELECT provider, method, status, amount, currency, "
                    "provider_payment_id, charge_id, created_at "
                    "FROM ecommerce.payment_records "
                    "WHERE order_id = :oid ORDER BY created_at DESC LIMIT 1"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .first()
    )

    # 5. Campaign attribution (only if marketing enabled)
    attr = None
    if settings.enable_marketing:
        attr_row = (
            (
                await db.execute(
                    text(
                        "SELECT ca.campaign_id, c.name AS campaign_name, "
                        "ca.channel, ca.conversion_event, ca.conversion_value, "
                        "ca.converted_at, ca.touch_sequence "
                        "FROM marketing.campaign_attributions ca "
                        "JOIN marketing.campaigns c ON c.id = ca.campaign_id "
                        "WHERE ca.user_id = :uid "
                        "AND ca.converted_at >= :ot_before "
                        "AND ca.converted_at <= :ot_after "
                        "ORDER BY ca.converted_at DESC LIMIT 1"
                    ),
                    {"uid": user_id, "ot_before": ot_before, "ot_after": ot_after},
                )
            )
            .mappings()
            .first()
        )

        # UTM params from user's session around order time
        utm = None
        utm_row = (
            (
                await db.execute(
                    text(
                        "SELECT ut.utm_source, ut.utm_medium, ut.utm_campaign, "
                        "ut.utm_content, ut.utm_term "
                        "FROM analytics.utm_tracking ut "
                        "JOIN analytics.analytics_sessions s "
                        "  ON s.session_id = ut.session_id "
                        "WHERE s.user_id = :uid "
                        "AND s.started_at <= :ot "
                        "AND (s.ended_at IS NULL "
                        "  OR s.ended_at >= :ot_hour_before) "
                        "ORDER BY s.started_at DESC LIMIT 1"
                    ),
                    {
                        "uid": user_id,
                        "ot": order_time,
                        "ot_hour_before": ot_hour_before,
                    },
                )
            )
            .mappings()
            .first()
        )
        if utm_row:
            utm = {
                "source": utm_row["utm_source"],
                "medium": utm_row["utm_medium"],
                "campaign": utm_row["utm_campaign"],
                "content": utm_row["utm_content"],
                "term": utm_row["utm_term"],
            }

        if attr_row:
            touch_seq = attr_row["touch_sequence"]
            if isinstance(touch_seq, str):
                touch_seq = _json.loads(touch_seq)

            # Enrich touch_sequence with campaign names
            enriched_touches = []
            campaign_name_cache: dict[str, str] = {
                str(attr_row["campaign_id"]): attr_row["campaign_name"]
            }
            for touch in touch_seq or []:
                t = dict(touch)
                cid = t.get("campaign_id")
                if cid and cid not in campaign_name_cache:
                    cname = (
                        await db.execute(
                            text(
                                "SELECT name FROM marketing.campaigns WHERE id = :cid"
                            ),
                            {"cid": cid},
                        )
                    ).scalar()
                    campaign_name_cache[cid] = cname or "Unknown"
                t["campaign_name"] = campaign_name_cache.get(cid, "Unknown")
                enriched_touches.append(t)

            attr = {
                "campaign_id": str(attr_row["campaign_id"]),
                "campaign_name": attr_row["campaign_name"],
                "channel": attr_row["channel"],
                "conversion_event": attr_row["conversion_event"],
                "conversion_value": (
                    float(attr_row["conversion_value"])
                    if attr_row["conversion_value"]
                    else 0
                ),
                "converted_at": _ts(attr_row["converted_at"]),
                "touch_sequence": enriched_touches,
                "utm": utm,
            }
        elif utm:
            # No attribution record but UTM params exist
            attr = {
                "campaign_id": None,
                "campaign_name": None,
                "channel": None,
                "conversion_event": None,
                "conversion_value": 0,
                "converted_at": None,
                "touch_sequence": [],
                "utm": utm,
            }

    # 6. Automation flow (only if marketing enabled)
    automation = None
    if settings.enable_marketing:
        flow_row = (
            (
                await db.execute(
                    text(
                        "SELECT af.id AS flow_id, af.name AS flow_name, "
                        "af.trigger_event, fe.status "
                        "FROM marketing.flow_enrollments fe "
                        "JOIN marketing.automation_flows af ON af.id = fe.flow_id "
                        "WHERE fe.user_id = :uid "
                        "AND fe.enrolled_at <= :ot_hour_after "
                        "ORDER BY fe.enrolled_at DESC LIMIT 1"
                    ),
                    {"uid": user_id, "ot_hour_after": ot_hour_after},
                )
            )
            .mappings()
            .first()
        )
        if flow_row:
            automation = {
                "flow_id": str(flow_row["flow_id"]),
                "flow_name": flow_row["flow_name"],
                "trigger_event": flow_row["trigger_event"],
                "status": flow_row["status"],
            }

    return {
        "order": {
            "id": str(o["id"]),
            "order_number": o["order_number"],
            "status": o["status"],
            "currency": o["currency"],
            "subtotal": o["subtotal"],
            "discount_amount": o["discount_amount"],
            "tax_amount": o["tax_amount"],
            "total": o["total"],
            "shipping_address": o["shipping_address"],
            "billing_address": o["billing_address"],
            "created_at": _ts(o["created_at"]),
            "updated_at": _ts(o["updated_at"]),
        },
        "items": [
            {
                "product_id": str(i["product_id"]),
                "variant_id": str(i["variant_id"]),
                "quantity": i["quantity"],
                "unit_price": i["unit_price"],
                "total_price": i["total_price"],
                "product_snapshot": (
                    i["product_snapshot"]
                    if isinstance(i["product_snapshot"], dict)
                    else {}
                ),
            }
            for i in items_rows
        ],
        "customer": (
            {
                "id": str(cu["id"]),
                "email": cu["email"],
                "first_name": cu["first_name"],
                "last_name": cu["last_name"],
                "rfm_segment": cu["rfm_segment"],
                "order_count": cu["order_count"] or 0,
                "total_spent": cu["total_spent"] or 0,
                "currency": cu["default_currency"] or "USD",
            }
            if cu
            else None
        ),
        "payment": (
            {
                "provider": pr["provider"],
                "method": pr["method"],
                "status": pr["status"],
                "amount": pr["amount"],
                "currency": pr["currency"],
                "provider_payment_id": pr["provider_payment_id"],
                "charge_id": pr["charge_id"],
                "created_at": _ts(pr["created_at"]),
            }
            if pr
            else None
        ),
        "attribution": attr,
        "automation": automation,
    }


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
