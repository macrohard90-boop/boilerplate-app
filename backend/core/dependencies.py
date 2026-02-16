"""FastAPI dependencies for authentication, authorization, and CSRF."""

from typing import Any, Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.redis import get_redis
from modules.auth.services import auth_service, rbac_service, session_service, token_service

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# get_current_user  — 6-step session isolation pipeline
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Validate JWT, verify Redis session, and return user context.

    The 6-step pipeline from ARCHITECTURE.md §3.2:
    1. Extract JWT from Authorization header (or detect API key)
    2. Validate JWT signature and expiry
    3. Look up active session in Redis
    4. Verify session belongs to requesting user
    5. Attach verified user context to request
    6. Return context (DB queries downstream scope by user_id)
    """
    if not credentials:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Missing authorization", "details": None})

    token = credentials.credentials

    # Detect API key (prefix ba_) vs JWT
    if token.startswith("ba_"):
        return await _validate_api_key(token, db, redis)

    # Step 2: Validate JWT
    try:
        claims = token_service.decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid or expired token", "details": None})

    user_id = claims.get("sub")
    session_id = claims.get("sid")
    role = claims.get("role", "")
    permissions = claims.get("permissions", [])

    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Malformed token", "details": None})

    # Step 3: Redis session lookup
    session = await session_service.get_session(redis, session_id)
    if not session:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Session expired or invalidated", "details": None})

    # Step 4: Verify session belongs to user
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Session mismatch", "details": None})

    # Step 5: Build user context
    context: dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "permissions": permissions,
        "session_id": session_id,
        "auth_type": "jwt",
        "auth_time": claims.get("auth_time"),
        "amr": claims.get("amr", []),
        "jti": claims.get("jti"),
        "consent": claims.get("consent", []),
        "token_type": claims.get("token_type", "access"),
    }

    # Attach to request state for downstream use
    request.state.user = context
    return context


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any] | None:
    """Like get_current_user but returns None instead of 401 for guests."""
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials, db, redis)
    except HTTPException:
        return None


async def _validate_api_key(
    raw_key: str,
    db: AsyncSession,
    redis: Redis,
) -> dict[str, Any]:
    """Validate an API key and return user context with scoped permissions."""
    import hashlib
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    from sqlalchemy import text
    result = await db.execute(
        text(
            "SELECT ak.id, ak.user_id, ak.scopes, ak.rate_limit, ak.is_active, "
            "r.name AS role "
            "FROM core.api_keys ak "
            "JOIN core.users u ON u.id = ak.user_id "
            "JOIN core.roles r ON r.id = u.role_id "
            "WHERE ak.key_hash = :kh"
        ),
        {"kh": key_hash},
    )
    row = result.mappings().first()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid API key", "details": None})

    # Update last_used_at
    await db.execute(
        text("UPDATE core.api_keys SET last_used_at = NOW() WHERE id = :id"),
        {"id": str(row["id"])},
    )
    await db.commit()

    scopes = row["scopes"] if isinstance(row["scopes"], list) else []

    return {
        "user_id": str(row["user_id"]),
        "role": row["role"],
        "permissions": scopes,
        "session_id": None,
        "auth_type": "api_key",
        "api_key_id": str(row["id"]),
        "rate_limit": row["rate_limit"],
    }


# ---------------------------------------------------------------------------
# require_role  — dependency factory
# ---------------------------------------------------------------------------


def require_role(role: str) -> Callable:
    """Return a FastAPI dependency that checks the user has the given role or higher."""

    async def _check(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if not rbac_service.has_role_or_higher(user["role"], role):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"Requires role: {role}", "details": None},
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# require_permission  — dependency factory
# ---------------------------------------------------------------------------


def require_permission(permission: str) -> Callable:
    """Return a FastAPI dependency that checks the user has the specific permission."""

    async def _check(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if not rbac_service.has_permission(user["permissions"], permission):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"Missing permission: {permission}", "details": None},
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# CSRF validation
# ---------------------------------------------------------------------------


async def validate_csrf(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Validate CSRF token on state-changing requests (POST/PUT/DELETE)."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not x_csrf_token:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Missing CSRF token", "details": None})

        session_id = user.get("session_id")
        if not session_id:
            # API key auth doesn't need CSRF
            return user

        valid = await auth_service.validate_csrf_token(redis, x_csrf_token, session_id)
        if not valid:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Invalid CSRF token", "details": None})

    return user
