"""Admin user management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
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
    import logging

    from backend.core.config import settings
    from sqlalchemy import text

    logger = logging.getLogger(__name__)

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
