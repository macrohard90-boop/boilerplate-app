"""Admin user management — list, detail, role change, activate/deactivate, soft delete."""

from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.services.session_service import invalidate_all_sessions


# ---------------------------------------------------------------------------
# List users (paginated, searchable, filterable)
# ---------------------------------------------------------------------------


async def list_users(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Return a paginated list of users with optional filters.

    Filters:
        search — ILIKE on email, first_name, last_name
        role   — exact match on role name (admin, merchant, customer)
        status — 'active', 'inactive', or 'deleted'
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if search:
        conditions.append(
            "(u.email ILIKE :search OR u.first_name ILIKE :search OR u.last_name ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if role:
        conditions.append("r.name = :role")
        params["role"] = role

    if status == "active":
        conditions.append("u.is_active = true AND u.deleted_at IS NULL")
    elif status == "inactive":
        conditions.append("u.is_active = false AND u.deleted_at IS NULL")
    elif status == "deleted":
        conditions.append("u.deleted_at IS NOT NULL")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count query
    count_sql = f"""
        SELECT COUNT(*) FROM core.users u
        JOIN core.roles r ON r.id = u.role_id
        {where}
    """
    total = (await db.execute(text(count_sql), params)).scalar() or 0

    # Data query
    offset = (page - 1) * page_size
    data_sql = f"""
        SELECT u.id, u.email, u.first_name, u.last_name, r.name AS role,
               u.is_verified, u.is_active, u.deleted_at, u.created_at
        FROM core.users u
        JOIN core.roles r ON r.id = u.role_id
        {where}
        ORDER BY u.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = page_size
    params["offset"] = offset

    rows = (await db.execute(text(data_sql), params)).mappings().all()

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# User detail (includes merchant check)
# ---------------------------------------------------------------------------


async def get_user_detail(db: AsyncSession, user_id: str) -> dict[str, Any] | None:
    """Return a single user with is_merchant flag."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT u.id, u.email, u.first_name, u.last_name, r.name AS role, "
                    "u.is_verified, u.is_active, u.deleted_at, u.created_at "
                    "FROM core.users u "
                    "JOIN core.roles r ON r.id = u.role_id "
                    "WHERE u.id = :user_id"
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        return None

    user = dict(row)

    # Check merchant account
    merchant = (
        await db.execute(
            text("SELECT 1 FROM ecommerce.merchant_accounts WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).scalar()
    user["is_merchant"] = merchant is not None

    return user


# ---------------------------------------------------------------------------
# Update role
# ---------------------------------------------------------------------------


async def update_user_role(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    new_role: str,
    admin_user_id: str,
) -> None:
    """Change a user's role. Guards: no self-demotion, no merchant role change."""
    if user_id == admin_user_id:
        raise ValueError("Cannot change your own role")

    # Check merchant account
    merchant = (
        await db.execute(
            text("SELECT 1 FROM ecommerce.merchant_accounts WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).scalar()
    if merchant is not None:
        raise ValueError("Cannot change role for merchant accounts")

    # Validate role exists
    role_row = (
        await db.execute(
            text("SELECT id FROM core.roles WHERE name = :name"),
            {"name": new_role},
        )
    ).scalar()
    if role_row is None:
        raise ValueError(f"Role '{new_role}' does not exist")

    await db.execute(
        text(
            "UPDATE core.users SET role_id = :role_id, updated_at = NOW() WHERE id = :uid"
        ),
        {"role_id": role_row, "uid": user_id},
    )
    await db.commit()

    # Revoke all sessions so new role takes effect
    await invalidate_all_sessions(redis, user_id)


# ---------------------------------------------------------------------------
# Toggle active status
# ---------------------------------------------------------------------------


async def toggle_user_active(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    active: bool,
    admin_user_id: str,
) -> None:
    """Activate or deactivate a user. Revokes sessions on deactivation."""
    if user_id == admin_user_id:
        raise ValueError("Cannot change your own status")

    await db.execute(
        text(
            "UPDATE core.users SET is_active = :active, updated_at = NOW() WHERE id = :uid"
        ),
        {"active": active, "uid": user_id},
    )
    await db.commit()

    if not active:
        await invalidate_all_sessions(redis, user_id)


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


async def soft_delete_user(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    admin_user_id: str,
) -> None:
    """Soft-delete a user: set deleted_at, is_active=false, revoke sessions."""
    if user_id == admin_user_id:
        raise ValueError("Cannot delete yourself")

    # Check not already deleted
    deleted = (
        await db.execute(
            text("SELECT deleted_at FROM core.users WHERE id = :uid"),
            {"uid": user_id},
        )
    ).scalar()
    if deleted is not None:
        raise ValueError("User is already deleted")

    await db.execute(
        text(
            "UPDATE core.users SET deleted_at = NOW(), is_active = false, updated_at = NOW() "
            "WHERE id = :uid"
        ),
        {"uid": user_id},
    )
    await db.commit()

    await invalidate_all_sessions(redis, user_id)
