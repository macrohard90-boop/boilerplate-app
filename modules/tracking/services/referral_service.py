"""Referral source parsing from referrer URLs."""

from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Known referral source mappings (domain → source, medium)
_KNOWN_SOURCES: dict[str, tuple[str, str]] = {
    "google.com": ("google", "organic"),
    "google.co": ("google", "organic"),
    "bing.com": ("bing", "organic"),
    "yahoo.com": ("yahoo", "organic"),
    "duckduckgo.com": ("duckduckgo", "organic"),
    "facebook.com": ("facebook", "social"),
    "fb.com": ("facebook", "social"),
    "twitter.com": ("twitter", "social"),
    "x.com": ("twitter", "social"),
    "t.co": ("twitter", "social"),
    "linkedin.com": ("linkedin", "social"),
    "instagram.com": ("instagram", "social"),
    "reddit.com": ("reddit", "social"),
    "youtube.com": ("youtube", "social"),
    "pinterest.com": ("pinterest", "social"),
    "tiktok.com": ("tiktok", "social"),
}


def parse_referrer(referrer: str | None) -> dict[str, str | None]:
    """Parse a referrer URL into source and medium.

    Returns {"source": ..., "medium": ..., "campaign": None}.
    """
    if not referrer:
        return {"source": "direct", "medium": "none", "campaign": None}

    try:
        parsed = urlparse(referrer)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return {"source": "unknown", "medium": "unknown", "campaign": None}

    if not hostname:
        return {"source": "direct", "medium": "none", "campaign": None}

    # Check known sources
    for domain, (source, medium) in _KNOWN_SOURCES.items():
        if hostname.endswith(domain):
            return {"source": source, "medium": medium, "campaign": None}

    # Unknown external referrer
    return {"source": hostname, "medium": "referral", "campaign": None}


async def store_referral(
    db: AsyncSession,
    session_id: str,
    referral: dict[str, str | None],
) -> None:
    """Store referral source for a session."""
    await db.execute(
        text(
            "INSERT INTO analytics.referral_sources "
            "(session_id, source, medium, campaign) "
            "VALUES (:sid, :src, :med, :camp) "
            "ON CONFLICT (session_id) DO NOTHING"
        ),
        {
            "sid": session_id,
            "src": referral.get("source"),
            "med": referral.get("medium"),
            "camp": referral.get("campaign"),
        },
    )
    await db.commit()


async def get_source_stats(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Get traffic source breakdown for admin dashboard."""
    where_clauses = []
    params: dict[str, Any] = {}

    if date_from:
        where_clauses.append(
            "session_id IN (SELECT session_id FROM analytics.analytics_sessions WHERE started_at >= :date_from)"
        )
        params["date_from"] = date_from
    if date_to:
        where_clauses.append(
            "session_id IN (SELECT session_id FROM analytics.analytics_sessions WHERE started_at <= :date_to)"
        )
        params["date_to"] = date_to

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    rows = (
        await db.execute(
            text(
                f"SELECT source, medium, COUNT(*) AS sessions "
                f"FROM analytics.referral_sources WHERE {where} "
                f"GROUP BY source, medium ORDER BY sessions DESC LIMIT 50"
            ),
            params,
        )
    ).mappings().all()

    return {
        "total_sources": len(rows),
        "sources": [
            {"source": r["source"], "medium": r["medium"], "sessions": r["sessions"]}
            for r in rows
        ],
    }
