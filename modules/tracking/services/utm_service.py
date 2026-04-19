"""UTM parameter extraction and storage."""

from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def extract_utm_params(url: str) -> dict[str, str | None]:
    """Extract UTM parameters from a URL query string."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return {
            "utm_source": qs.get("utm_source", [None])[0],
            "utm_medium": qs.get("utm_medium", [None])[0],
            "utm_campaign": qs.get("utm_campaign", [None])[0],
            "utm_content": qs.get("utm_content", [None])[0],
            "utm_term": qs.get("utm_term", [None])[0],
        }
    except Exception:
        return {}


def has_utm_params(params: dict[str, str | None]) -> bool:
    """Check if any UTM parameters are present."""
    return any(v for v in params.values())


async def store_utm(
    db: AsyncSession,
    session_id: str,
    params: dict[str, str | None],
) -> None:
    """Store UTM parameters for a session."""
    if not has_utm_params(params):
        return

    await db.execute(
        text(
            "INSERT INTO analytics.utm_tracking "
            "(session_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term) "
            "VALUES (:sid, :src, :med, :camp, :cont, :term)"
        ),
        {
            "sid": session_id,
            "src": params.get("utm_source"),
            "med": params.get("utm_medium"),
            "camp": params.get("utm_campaign"),
            "cont": params.get("utm_content"),
            "term": params.get("utm_term"),
        },
    )
    await db.commit()


async def get_utm_stats(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Get UTM campaign performance stats."""
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
        (
            await db.execute(
                text(
                    f"SELECT utm_source, utm_medium, utm_campaign, COUNT(*) AS sessions "
                    f"FROM analytics.utm_tracking WHERE {where} "
                    f"GROUP BY utm_source, utm_medium, utm_campaign "
                    f"ORDER BY sessions DESC LIMIT 50"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "total_campaigns": len(rows),
        "campaigns": [
            {
                "utm_source": r["utm_source"],
                "utm_medium": r["utm_medium"],
                "utm_campaign": r["utm_campaign"],
                "sessions": r["sessions"],
            }
            for r in rows
        ],
    }
