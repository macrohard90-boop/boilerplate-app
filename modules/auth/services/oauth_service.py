"""OAuth orchestration: provider factory, state tokens, account linking."""

import logging
import secrets
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.interfaces.auth_provider import AuthProvider, OAuthUserInfo

logger = logging.getLogger(__name__)

_STATE_PREFIX = "oauth_state:"
_STATE_TTL = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_providers: dict[str, AuthProvider] = {}


def register_provider(provider: AuthProvider) -> None:
    _providers[provider.name] = provider


def get_provider(name: str) -> AuthProvider | None:
    return _providers.get(name)


def list_providers() -> list[str]:
    return list(_providers.keys())


def init_providers() -> None:
    """Initialize all configured OAuth providers."""
    import os

    if os.environ.get("GOOGLE_CLIENT_ID"):
        from modules.auth.adapters.google import GoogleAuthProvider
        register_provider(GoogleAuthProvider())

    if os.environ.get("GITHUB_CLIENT_ID"):
        from modules.auth.adapters.github_oauth import GitHubAuthProvider
        register_provider(GitHubAuthProvider())

    if os.environ.get("MICROSOFT_CLIENT_ID"):
        from modules.auth.adapters.microsoft import MicrosoftAuthProvider
        register_provider(MicrosoftAuthProvider())

    if os.environ.get("APPLE_CLIENT_ID"):
        from modules.auth.adapters.apple import AppleAuthProvider
        register_provider(AppleAuthProvider())

    if os.environ.get("OIDC_ISSUER_URL"):
        from modules.auth.adapters.oidc import OIDCAuthProvider
        register_provider(OIDCAuthProvider())

    logger.info("OAuth providers initialized: %s", list_providers())


# ---------------------------------------------------------------------------
# State token management
# ---------------------------------------------------------------------------


async def create_state_token(redis: Redis, *, return_to: str = "/") -> str:
    """Generate and store a CSRF state token for OAuth flow."""
    state = secrets.token_urlsafe(32)
    await redis.set(f"{_STATE_PREFIX}{state}", return_to or "/", ex=_STATE_TTL)
    return state


async def validate_state_token(redis: Redis, state: str) -> str | None:
    """Validate and consume an OAuth state token. Returns returnTo path or None."""
    key = f"{_STATE_PREFIX}{state}"
    val = await redis.get(key)
    if val:
        await redis.delete(key)
        return val
    return None


# ---------------------------------------------------------------------------
# Account linking
# ---------------------------------------------------------------------------


async def _ensure_stripe_customer(db: AsyncSession, user: dict[str, Any]) -> None:
    """Sync OAuth user to Stripe as a customer if not already synced."""
    try:
        from modules.ecommerce.services.subscription_service import get_or_create_stripe_customer
        full_name = f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or None
        await get_or_create_stripe_customer(db, str(user["id"]), user["email"], name=full_name)
    except Exception as e:
        logger.warning("Failed to sync Stripe customer for OAuth user %s: %s", user["id"], e)


async def _backfill_name(
    db: AsyncSession, user: dict[str, Any], info: OAuthUserInfo
) -> None:
    """Fill in first/last name from OAuth provider if the user record is missing them."""
    updates: dict[str, Any] = {}
    if not user.get("first_name") and info.first_name:
        updates["fn"] = info.first_name
    if not user.get("last_name") and info.last_name:
        updates["ln"] = info.last_name
    if not updates:
        return
    set_parts = []
    if "fn" in updates:
        set_parts.append("first_name = :fn")
        user["first_name"] = updates["fn"]
    if "ln" in updates:
        set_parts.append("last_name = :ln")
        user["last_name"] = updates["ln"]
    await db.execute(
        text(f"UPDATE core.users SET {', '.join(set_parts)} WHERE id = :uid"),
        {**updates, "uid": str(user["id"])},
    )


async def find_or_create_user(
    db: AsyncSession,
    info: OAuthUserInfo,
) -> dict[str, Any]:
    """Find existing user by OAuth identity or email, or create new user.

    Account linking rules:
    1. Existing oauth_identity → return linked user
    2. Verified email match → link OAuth identity to existing user
    3. No match → create new user + OAuth identity
    """
    # 1. Check existing OAuth identity
    result = await db.execute(
        text(
            "SELECT u.id, u.email, u.first_name, u.last_name, u.is_verified, "
            "u.is_active, u.created_at, r.name AS role "
            "FROM core.oauth_identities oi "
            "JOIN core.users u ON u.id = oi.user_id "
            "JOIN core.roles r ON r.id = u.role_id "
            "WHERE oi.provider = :provider AND oi.provider_user_id = :pid"
        ),
        {"provider": info.provider, "pid": info.provider_user_id},
    )
    row = result.mappings().first()
    if row:
        user = dict(row)
        await _backfill_name(db, user, info)
        await _ensure_stripe_customer(db, user)
        return user

    # 2. Check verified email match
    if info.email:
        result = await db.execute(
            text(
                "SELECT u.id, u.email, u.first_name, u.last_name, u.is_verified, "
                "u.is_active, u.created_at, r.name AS role "
                "FROM core.users u "
                "JOIN core.roles r ON r.id = u.role_id "
                "WHERE LOWER(u.email) = LOWER(:email) AND u.is_verified = TRUE"
            ),
            {"email": info.email},
        )
        row = result.mappings().first()
        if row:
            # Link OAuth identity
            await db.execute(
                text(
                    "INSERT INTO core.oauth_identities (user_id, provider, provider_user_id) "
                    "VALUES (:uid, :provider, :pid) ON CONFLICT DO NOTHING"
                ),
                {"uid": str(row["id"]), "provider": info.provider, "pid": info.provider_user_id},
            )
            user = dict(row)
            await _backfill_name(db, user, info)
            await db.commit()
            await _ensure_stripe_customer(db, user)
            return user

    # 3. Create new user
    result = await db.execute(
        text(
            "INSERT INTO core.users (email, first_name, last_name, role_id, is_verified) "
            "VALUES (:email, :fn, :ln, "
            "(SELECT id FROM core.roles WHERE name = 'customer'), :verified) "
            "RETURNING id, email, first_name, last_name, is_verified, is_active, created_at"
        ),
        {
            "email": info.email,
            "fn": info.first_name,
            "ln": info.last_name,
            "verified": info.email_verified,
        },
    )
    new_user = result.mappings().first()
    user_id = str(new_user["id"])  # type: ignore[index]

    # Link OAuth identity
    await db.execute(
        text(
            "INSERT INTO core.oauth_identities (user_id, provider, provider_user_id) "
            "VALUES (:uid, :provider, :pid)"
        ),
        {"uid": user_id, "provider": info.provider, "pid": info.provider_user_id},
    )
    await db.commit()
    user = {**dict(new_user), "role": "customer"}  # type: ignore[union-attr]
    await _ensure_stripe_customer(db, user)
    return user
