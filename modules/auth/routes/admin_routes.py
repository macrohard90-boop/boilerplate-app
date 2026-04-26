"""Admin user management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role
from backend.core.redis import get_redis
from modules.auth.models.schemas import (
    AdminUserDetail,
    AdminUserListResponse,
    MessageResponse,
    UpdateRoleRequest,
    UpdateStatusRequest,
)
from modules.auth.services import admin_user_service, auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-users"])


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await admin_user_service.list_users(
        db, page=page, page_size=page_size, search=search, role=role, status=status
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    detail = await admin_user_service.get_user_detail(db, user_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found", "details": None},
        )
    return detail


@router.get("/users/{user_id}/full-profile")
async def get_user_full_profile(
    user_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Aggregated user profile with data from all modules."""

    # 1. User profile with role name
    u = (
        (
            await db.execute(
                text(
                    "SELECT u.id, u.email, u.first_name, u.last_name, "
                    "r.name AS role, u.is_verified, u.is_active, "
                    "u.created_at, u.phone, u.whatsapp_number, u.deleted_at "
                    "FROM core.users u "
                    "JOIN core.roles r ON r.id = u.role_id "
                    "WHERE u.id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    if not u:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found", "details": None},
        )

    # 2. Customer metrics
    cm = (
        (
            await db.execute(
                text(
                    "SELECT order_count, total_spent, default_currency, "
                    "rfm_segment, last_purchase_at "
                    "FROM ecommerce.customer_metrics WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 3. Engagement — computed from sessions & page views (last 90d)
    eng = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(DISTINCT s.session_id) AS sessions_90d, "
                    "  COALESCE(SUM(s.page_count), 0) AS pages_90d, "
                    "  MAX(s.started_at) AS last_visit "
                    "FROM analytics.analytics_sessions s "
                    "WHERE s.user_id = :uid "
                    "  AND s.started_at >= NOW() - INTERVAL '90 days'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 4. Recent orders (last 10)
    orders = (
        (
            await db.execute(
                text(
                    "SELECT id, order_number, status, total, currency, created_at "
                    "FROM ecommerce.orders "
                    "WHERE user_id = :uid "
                    "ORDER BY created_at DESC LIMIT 10"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    # 5. Recent sessions with user agent info (last 10)
    sessions = (
        (
            await db.execute(
                text(
                    "SELECT s.session_id, s.started_at, s.ended_at, s.page_count, "
                    "ua.browser, ua.os, ua.device_type "
                    "FROM analytics.analytics_sessions s "
                    "LEFT JOIN analytics.user_agents ua ON ua.session_id = s.session_id "
                    "WHERE s.user_id = :uid "
                    "ORDER BY s.started_at DESC LIMIT 10"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    # 6. Top pages by view count (last 90d, top 5)
    pages = (
        (
            await db.execute(
                text(
                    "SELECT path, COUNT(*) AS views "
                    "FROM analytics.page_views "
                    "WHERE user_id = :uid "
                    "  AND created_at >= NOW() - INTERVAL '90 days' "
                    "GROUP BY path ORDER BY views DESC LIMIT 5"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    # 7. Email preferences
    ep = (
        (
            await db.execute(
                text(
                    "SELECT marketing_email, transactional_email, suppressed_at "
                    "FROM gdpr.email_preferences WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 8. Cart summary (active carts + total items)
    cart = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(DISTINCT c.id) AS active_carts, "
                    "COALESCE(SUM(ci.quantity), 0) AS total_items "
                    "FROM ecommerce.cart c "
                    "LEFT JOIN ecommerce.cart_items ci ON ci.cart_id = c.id "
                    "WHERE c.user_id = :uid AND c.status = 'active'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 9. Stripe customer ID
    sc = (
        (
            await db.execute(
                text(
                    "SELECT stripe_customer_id FROM ecommerce.stripe_customers "
                    "WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    # 10. Wishlist summary
    wl = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(DISTINCT w.id) AS wishlists, "
                    "COUNT(wi.product_id) AS total_items "
                    "FROM ecommerce.wishlists w "
                    "LEFT JOIN ecommerce.wishlist_items wi ON wi.wishlist_id = w.id "
                    "WHERE w.user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    def _ts(v: Any) -> str | None:
        return v.isoformat() if v else None

    return {
        "user": {
            "id": str(u["id"]),
            "email": u["email"],
            "first_name": u["first_name"],
            "last_name": u["last_name"],
            "role": u["role"],
            "is_verified": u["is_verified"],
            "is_active": u["is_active"],
            "created_at": _ts(u["created_at"]),
            "phone": u["phone"],
            "whatsapp_number": u["whatsapp_number"],
            "deleted_at": _ts(u["deleted_at"]),
        },
        "customer_metrics": (
            {
                "order_count": cm["order_count"],
                "total_spent": cm["total_spent"],
                "currency": cm["default_currency"],
                "rfm_segment": cm["rfm_segment"],
                "last_purchase_at": _ts(cm["last_purchase_at"]),
            }
            if cm
            else None
        ),
        "engagement": {
            "sessions_90d": eng["sessions_90d"] if eng else 0,
            "pages_90d": eng["pages_90d"] if eng else 0,
            "last_visit": _ts(eng["last_visit"]) if eng else None,
        },
        "recent_orders": [
            {
                "id": str(o["id"]),
                "order_number": o["order_number"],
                "status": o["status"],
                "total": o["total"],
                "currency": o["currency"],
                "created_at": _ts(o["created_at"]),
            }
            for o in orders
        ],
        "recent_sessions": [
            {
                "session_id": s["session_id"],
                "started_at": _ts(s["started_at"]),
                "ended_at": _ts(s["ended_at"]),
                "page_count": s["page_count"],
                "browser": s["browser"],
                "os": s["os"],
                "device_type": s["device_type"],
            }
            for s in sessions
        ],
        "top_pages": [{"path": p["path"], "views": p["views"]} for p in pages],
        "email_preferences": (
            {
                "marketing_email": ep["marketing_email"],
                "transactional_email": ep["transactional_email"],
                "suppressed_at": _ts(ep["suppressed_at"]),
            }
            if ep
            else None
        ),
        "cart_summary": {
            "active_carts": cart["active_carts"] if cart else 0,
            "total_items": int(cart["total_items"]) if cart else 0,
        },
        "wishlist_summary": {
            "wishlists": wl["wishlists"] if wl else 0,
            "total_items": int(wl["total_items"]) if wl else 0,
        },
        "stripe_customer_id": sc["stripe_customer_id"] if sc else None,
    }


@router.put("/users/{user_id}/role", response_model=MessageResponse)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        await admin_user_service.update_user_role(
            db, redis, user_id, body.role, admin_user_id=user["user_id"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )
    return {"message": f"Role updated to {body.role}"}


@router.put("/users/{user_id}/status", response_model=MessageResponse)
async def update_user_status(
    user_id: str,
    body: UpdateStatusRequest,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        await admin_user_service.toggle_user_active(
            db, redis, user_id, body.is_active, admin_user_id=user["user_id"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )
    action = "activated" if body.is_active else "deactivated"
    return {"message": f"User {action}"}


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        await admin_user_service.soft_delete_user(
            db, redis, user_id, admin_user_id=user["user_id"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )
    return {"message": "User deleted"}


@router.post("/users/{user_id}/resend-verification", response_model=MessageResponse)
async def resend_verification(
    user_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    """Resend email verification to a user (admin action)."""
    from backend.core.config import settings

    # Fetch user email + verification status
    row = (
        (
            await db.execute(
                text(
                    "SELECT email, first_name, is_verified FROM core.users WHERE id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found", "details": None},
        )

    if row["is_verified"]:
        return {"message": "User is already verified"}

    # Generate new verification token and send welcome email
    verify_token = await auth_service.generate_verification_token(redis, user_id)
    try:
        from modules.gdpr.services.email_send_service import send_email_fire_and_forget

        await send_email_fire_and_forget(
            user_id,
            "welcome",
            {
                "verify_url": f"{settings.frontend_url}/verify-email?token={verify_token}",
                "first_name": row["first_name"] or "there",
            },
            email_type="transactional_email",
            to_email=row["email"],
            force=True,
        )
    except Exception:
        logger.exception("Failed to resend verification email to %s", row["email"])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "send_failed",
                "message": "Failed to send verification email",
                "details": None,
            },
        )

    return {"message": f"Verification email sent to {row['email']}"}
