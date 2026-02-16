"""Core authentication business logic — registration, login, password reset."""

import secrets
from typing import Any

import bcrypt as _bcrypt
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings


# ---------------------------------------------------------------------------
# Password hashing (bcrypt, cost 12)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------


async def get_user_by_email(db: AsyncSession, email: str) -> dict[str, Any] | None:
    """Look up a user by email (case-insensitive). Returns dict or None."""
    result = await db.execute(
        text(
            "SELECT u.id, u.email, u.password_hash, u.first_name, u.last_name, "
            "u.is_verified, u.is_active, u.created_at, u.deleted_at, "
            "r.name AS role "
            "FROM core.users u "
            "JOIN core.roles r ON r.id = u.role_id "
            "WHERE LOWER(u.email) = LOWER(:email)"
        ),
        {"email": email},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_user_by_id(db: AsyncSession, user_id: str) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            "SELECT u.id, u.email, u.password_hash, u.first_name, u.last_name, "
            "u.is_verified, u.is_active, u.created_at, u.deleted_at, "
            "r.name AS role "
            "FROM core.users u "
            "JOIN core.roles r ON r.id = u.role_id "
            "WHERE u.id = :uid"
        ),
        {"uid": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_user_permissions(db: AsyncSession, user_id: str) -> list[str]:
    """Return permissions as ``['resource:action', ...]`` for a user."""
    result = await db.execute(
        text(
            "SELECT p.resource || ':' || p.action AS perm "
            "FROM core.permissions p "
            "JOIN core.users u ON u.role_id = p.role_id "
            "WHERE u.id = :uid"
        ),
        {"uid": user_id},
    )
    return [row[0] for row in result.fetchall()]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_DEFAULT_ROLE = "customer"


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any]:
    """Create a new user with the *customer* role.

    Raises ``ValueError`` if the email is already taken.
    """
    existing = await get_user_by_email(db, email)
    if existing:
        raise ValueError("Email already registered")

    pw_hash = hash_password(password)

    result = await db.execute(
        text(
            "INSERT INTO core.users (email, password_hash, first_name, last_name, role_id) "
            "VALUES (:email, :ph, :fn, :ln, (SELECT id FROM core.roles WHERE name = :role)) "
            "RETURNING id, email, first_name, last_name, is_verified, is_active, created_at"
        ),
        {
            "email": email,
            "ph": pw_hash,
            "fn": first_name,
            "ln": last_name,
            "role": _DEFAULT_ROLE,
        },
    )
    row = result.mappings().first()
    await db.commit()
    return {**dict(row), "role": _DEFAULT_ROLE}  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def authenticate_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    """Validate credentials. Returns user dict or raises ``ValueError``."""
    user = await get_user_by_email(db, email)
    if not user:
        raise ValueError("Invalid email or password")

    if user.get("deleted_at") is not None:
        raise ValueError("Account has been deleted")

    if not user.get("is_active"):
        raise ValueError("Account is deactivated")

    if not user.get("password_hash"):
        raise ValueError("Account uses OAuth login only")

    if not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    return user


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

_RESET_PREFIX = "password_reset:"
_RESET_TTL = 3600  # 1 hour


async def generate_password_reset_token(
    redis: Redis,
    user_id: str,
) -> str:
    """Store an opaque reset token in Redis (1hr TTL). Returns the token."""
    token = secrets.token_urlsafe(48)
    await redis.set(f"{_RESET_PREFIX}{token}", user_id, ex=_RESET_TTL)
    return token


async def validate_reset_token(redis: Redis, token: str) -> str | None:
    """Return user_id if token is valid, else None."""
    user_id = await redis.get(f"{_RESET_PREFIX}{token}")
    return user_id


async def consume_reset_token(redis: Redis, token: str) -> str | None:
    """Validate and delete the reset token. Returns user_id or None."""
    key = f"{_RESET_PREFIX}{token}"
    user_id = await redis.get(key)
    if user_id:
        await redis.delete(key)
    return user_id


async def change_password(db: AsyncSession, user_id: str, new_password: str) -> None:
    """Update a user's password hash."""
    pw_hash = hash_password(new_password)
    await db.execute(
        text("UPDATE core.users SET password_hash = :ph WHERE id = :uid"),
        {"ph": pw_hash, "uid": user_id},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

_VERIFY_PREFIX = "email_verify:"
_VERIFY_TTL = 86400  # 24 hours


async def generate_verification_token(redis: Redis, user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    await redis.set(f"{_VERIFY_PREFIX}{token}", user_id, ex=_VERIFY_TTL)
    return token


async def verify_email(db: AsyncSession, redis: Redis, token: str) -> bool:
    """Verify a user's email. Returns True on success."""
    key = f"{_VERIFY_PREFIX}{token}"
    user_id = await redis.get(key)
    if not user_id:
        return False

    await redis.delete(key)
    await db.execute(
        text("UPDATE core.users SET is_verified = TRUE WHERE id = :uid"),
        {"uid": user_id},
    )
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# CSRF tokens
# ---------------------------------------------------------------------------

_CSRF_PREFIX = "csrf:"
_CSRF_TTL = 3600  # 1 hour


async def create_csrf_token(redis: Redis, session_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await redis.set(f"{_CSRF_PREFIX}{token}", session_id, ex=_CSRF_TTL)
    return token


async def validate_csrf_token(
    redis: Redis,
    token: str,
    session_id: str,
) -> bool:
    stored_session = await redis.get(f"{_CSRF_PREFIX}{token}")
    return stored_session == session_id
