"""User agent parsing and storage."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tracking.adapters.default_agent_parser import get_agent_parser


async def store_user_agent(
    db: AsyncSession,
    session_id: str,
    user_agent: str,
) -> None:
    """Parse and store user agent info for a session.

    Only stores once per session (checks for existing record).
    """
    # Check if already stored for this session
    existing = (
        (
            await db.execute(
                text(
                    "SELECT id FROM analytics.user_agents WHERE session_id = :sid LIMIT 1"
                ),
                {"sid": session_id},
            )
        )
        .mappings()
        .first()
    )

    if existing:
        return

    parser = get_agent_parser()
    info = parser.parse(user_agent)

    await db.execute(
        text(
            "INSERT INTO analytics.user_agents "
            "(session_id, raw, browser, browser_version, os, device_type) "
            "VALUES (:sid, :raw, :browser, :bver, :os, :dtype)"
        ),
        {
            "sid": session_id,
            "raw": info.raw[:2000],  # Truncate extremely long UA strings
            "browser": info.browser,
            "bver": info.browser_version,
            "os": info.os,
            "dtype": info.device_type,
        },
    )
    await db.commit()
