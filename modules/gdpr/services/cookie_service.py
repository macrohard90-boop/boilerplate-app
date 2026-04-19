"""Cookie preference management for authenticated and guest users."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_preferences(
    db: AsyncSession,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Get current cookie preferences.

    Looks up by user_id first, falls back to session_id for guests.
    Returns None if no preferences found.
    """
    if user_id:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT necessary, analytics, marketing, preferences, updated_at "
                        "FROM gdpr.cookie_preferences "
                        "WHERE user_id = :uid "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if row:
            return {
                "necessary": row["necessary"],
                "analytics": row["analytics"],
                "marketing": row["marketing"],
                "preferences": row["preferences"],
                "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
            }

    if session_id:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT necessary, analytics, marketing, preferences, updated_at "
                        "FROM gdpr.cookie_preferences "
                        "WHERE session_id = :sid "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"sid": session_id},
                )
            )
            .mappings()
            .first()
        )
        if row:
            return {
                "necessary": row["necessary"],
                "analytics": row["analytics"],
                "marketing": row["marketing"],
                "preferences": row["preferences"],
                "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
            }

    return None


async def update_preferences(
    db: AsyncSession,
    analytics: bool = False,
    marketing: bool = False,
    preferences: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Create or update cookie preferences.

    `necessary` is always True and cannot be changed.
    Uses upsert logic: update if exists, insert if not.
    """
    if not user_id and not session_id:
        raise ValueError("Either user_id or session_id is required")

    # Check for existing record
    existing = None
    if user_id:
        existing = (
            (
                await db.execute(
                    text(
                        "SELECT id FROM gdpr.cookie_preferences "
                        "WHERE user_id = :uid LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
    elif session_id:
        existing = (
            (
                await db.execute(
                    text(
                        "SELECT id FROM gdpr.cookie_preferences "
                        "WHERE session_id = :sid AND user_id IS NULL LIMIT 1"
                    ),
                    {"sid": session_id},
                )
            )
            .mappings()
            .first()
        )

    if existing:
        await db.execute(
            text(
                "UPDATE gdpr.cookie_preferences "
                "SET analytics = :analytics, marketing = :marketing, "
                "preferences = :preferences "
                "WHERE id = :id"
            ),
            {
                "id": existing["id"],
                "analytics": analytics,
                "marketing": marketing,
                "preferences": preferences,
            },
        )
    else:
        await db.execute(
            text(
                "INSERT INTO gdpr.cookie_preferences "
                "(user_id, session_id, necessary, analytics, marketing, preferences) "
                "VALUES (:uid, :sid, true, :analytics, :marketing, :preferences)"
            ),
            {
                "uid": user_id,
                "sid": session_id,
                "analytics": analytics,
                "marketing": marketing,
                "preferences": preferences,
            },
        )

    await db.commit()

    return {
        "necessary": True,
        "analytics": analytics,
        "marketing": marketing,
        "preferences": preferences,
    }
