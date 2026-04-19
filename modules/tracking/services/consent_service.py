"""GDPR consent checking for analytics tracking.

Checks whether the user (authenticated or anonymous) has granted
consent for analytics data collection. Opt-in model: no consent = no tracking.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def has_analytics_consent(
    db: AsyncSession,
    user_id: str | None = None,
    session_id: str | None = None,
) -> bool:
    """Check if analytics tracking is consented.

    - Authenticated: check gdpr.consent_records for consent_type='analytics'
    - Anonymous: check gdpr.cookie_preferences for analytics=true
    - No record found: default to False (opt-in)
    """
    if user_id:
        # Check explicit consent records first
        row = (
            (
                await db.execute(
                    text(
                        "SELECT granted FROM gdpr.consent_records "
                        "WHERE user_id = :uid AND consent_type = 'analytics' "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if row:
            return bool(row["granted"])

        # Fall back to cookie preferences stored by user_id
        row = (
            (
                await db.execute(
                    text(
                        "SELECT analytics FROM gdpr.cookie_preferences "
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
            return bool(row["analytics"])

    if session_id:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT analytics FROM gdpr.cookie_preferences "
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
            return bool(row["analytics"])

    return False
