"""Authentication endpoints: register, login, refresh, logout, password reset, email verify."""

import logging
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import get_current_user, require_role, require_permission
from backend.core.redis import get_redis
from modules.auth.models.schemas import (
    ErrorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserContextResponse,
    UserResponse,
    SessionResponse,
    VerifyEmailRequest,
)
from modules.auth.services import auth_service, audit_service, session_service, token_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token as an httpOnly cookie."""
    secure = settings.app_env != "development"
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/auth",
        max_age=settings.refresh_token_ttl,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        path="/api/auth",
    )


# -----------------------------------------------------------------------
# POST /register
# -----------------------------------------------------------------------
@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        user = await auth_service.register_user(
            db,
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": str(e), "details": None})

    user_id = str(user["id"])
    permissions = await auth_service.get_user_permissions(db, user_id)

    ip = _client_ip(request)
    device = request.headers.get("user-agent", "")[:255]
    session_id = await session_service.create_session(
        redis, db, user_id, user["role"], device=device, ip=ip, user_agent=device,
    )

    access = token_service.create_access_token(user_id, user["role"], session_id, permissions)
    refresh = await token_service.create_refresh_token(redis, user_id, session_id)
    csrf = await auth_service.create_csrf_token(redis, session_id)

    _set_refresh_cookie(response, refresh)

    # Generate email verification token (logged to console — no email provider yet)
    verify_token = await auth_service.generate_verification_token(redis, user_id)
    logger.info("Email verification token for %s: %s", body.email, verify_token)

    await audit_service.log_audit(
        db, user_id=user_id, action="user.register", resource="user",
        resource_id=user_id, ip_address=ip,
    )

    return TokenResponse(access_token=access, expires_in=settings.jwt_expiry, csrf_token=csrf)


# -----------------------------------------------------------------------
# POST /login
# -----------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    try:
        user = await auth_service.authenticate_user(db, email=body.email, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": str(e), "details": None})

    user_id = str(user["id"])
    permissions = await auth_service.get_user_permissions(db, user_id)

    ip = _client_ip(request)
    device = request.headers.get("user-agent", "")[:255]
    session_id = await session_service.create_session(
        redis, db, user_id, user["role"], device=device, ip=ip, user_agent=device,
    )

    access = token_service.create_access_token(user_id, user["role"], session_id, permissions)
    refresh = await token_service.create_refresh_token(redis, user_id, session_id)
    csrf = await auth_service.create_csrf_token(redis, session_id)

    _set_refresh_cookie(response, refresh)

    await audit_service.log_audit(
        db, user_id=user_id, action="user.login", resource="user",
        resource_id=user_id, ip_address=ip,
    )

    return TokenResponse(access_token=access, expires_in=settings.jwt_expiry, csrf_token=csrf)


# -----------------------------------------------------------------------
# POST /refresh
# -----------------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None),
) -> Any:
    if not refresh_token:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "No refresh token", "details": None})

    data = await token_service.validate_refresh_token(redis, refresh_token)
    if not data:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid or expired refresh token", "details": None})

    user_id = data["user_id"]
    session_id = data["session_id"]

    # Verify session still exists in Redis
    session = await session_service.get_session(redis, session_id)
    if not session:
        await token_service.revoke_refresh_token(redis, refresh_token)
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Session expired", "details": None})

    # Rotate: revoke old refresh, issue new pair
    await token_service.revoke_refresh_token(redis, refresh_token)

    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "User not found", "details": None})

    permissions = await auth_service.get_user_permissions(db, user_id)
    access = token_service.create_access_token(user_id, user["role"], session_id, permissions)
    new_refresh = await token_service.create_refresh_token(redis, user_id, session_id)
    csrf = await auth_service.create_csrf_token(redis, session_id)

    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in=settings.jwt_expiry, csrf_token=csrf)


# -----------------------------------------------------------------------
# POST /logout
# -----------------------------------------------------------------------
@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None),
) -> Any:
    if refresh_token:
        data = await token_service.validate_refresh_token(redis, refresh_token)
        if data:
            await session_service.invalidate_session(redis, data["session_id"], data["user_id"])
        await token_service.revoke_refresh_token(redis, refresh_token)

    _clear_refresh_cookie(response)

    return MessageResponse(message="Logged out successfully")


# -----------------------------------------------------------------------
# POST /forgot-password
# -----------------------------------------------------------------------
@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    # Always return success (prevent email enumeration)
    user = await auth_service.get_user_by_email(db, body.email)
    if user and user.get("is_active") and user.get("deleted_at") is None:
        token = await auth_service.generate_password_reset_token(redis, str(user["id"]))
        logger.info("Password reset token for %s: %s", body.email, token)

    return MessageResponse(message="If an account exists, a reset link has been sent")


# -----------------------------------------------------------------------
# POST /reset-password
# -----------------------------------------------------------------------
@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    user_id = await auth_service.consume_reset_token(redis, body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid or expired reset token", "details": None})

    await auth_service.change_password(db, user_id, body.new_password)
    await session_service.invalidate_all_sessions(redis, user_id)

    ip = _client_ip(request)
    await audit_service.log_audit(
        db, user_id=user_id, action="user.password_reset", resource="user",
        resource_id=user_id, ip_address=ip,
    )

    return MessageResponse(message="Password reset successfully")


# -----------------------------------------------------------------------
# POST /verify-email
# -----------------------------------------------------------------------
@router.post("/verify-email", response_model=MessageResponse)
async def verify_email_endpoint(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    ok = await auth_service.verify_email(db, redis, body.token)
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid or expired verification token", "details": None})

    return MessageResponse(message="Email verified successfully")


# -----------------------------------------------------------------------
# GET /me  — returns authenticated user context
# -----------------------------------------------------------------------
@router.get("/me", response_model=UserContextResponse)
async def get_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Any:
    full_user = await auth_service.get_user_by_id(db, user["user_id"])
    if not full_user:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found", "details": None})

    session_count = await session_service.get_user_session_count(redis, user["user_id"])

    session_resp = None
    if user.get("session_id"):
        session_data = await session_service.get_session(redis, user["session_id"])
        if session_data:
            from datetime import datetime, timezone
            session_created = datetime.fromtimestamp(
                float(session_data.get("created_at", 0)), tz=timezone.utc
            )
            session_resp = SessionResponse(
                session_id=user["session_id"],
                device=session_data.get("device"),
                ip_address=session_data.get("ip"),
                created_at=session_created,
            )

    return UserContextResponse(
        user=UserResponse(
            id=full_user["id"],
            email=full_user["email"],
            first_name=full_user.get("first_name"),
            last_name=full_user.get("last_name"),
            role=full_user["role"],
            is_verified=full_user["is_verified"],
            permissions=user["permissions"],
            created_at=full_user["created_at"],
        ),
        session=session_resp,
        active_sessions_count=session_count,
        auth_type=user.get("auth_type", "jwt"),
    )
