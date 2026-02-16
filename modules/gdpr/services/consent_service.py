"""Consent management — grant/revoke, state queries, audit logging."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CONSENT_TYPES = [
    "marketing_email",
    "transactional_email",
    "third_party_sharing",
    "analytics",
    "cookies_analytics",
    "cookies_marketing",
]


async def get_consent_state(
    db: AsyncSession, user_id: str
) -> list[dict[str, Any]]:
    """Get current consent state for all 6 types.

    Returns the most recent record for each consent type.
    Types with no record default to granted=False.
    """
    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT ON (consent_type) "
                "consent_type, granted, created_at "
                "FROM gdpr.consent_records "
                "WHERE user_id = :uid "
                "ORDER BY consent_type, created_at DESC"
            ),
            {"uid": user_id},
        )
    ).mappings().all()

    state_map = {r["consent_type"]: r for r in rows}

    result = []
    for ct in CONSENT_TYPES:
        if ct in state_map:
            result.append({
                "consent_type": ct,
                "granted": state_map[ct]["granted"],
                "updated_at": str(state_map[ct]["created_at"]),
            })
        else:
            result.append({
                "consent_type": ct,
                "granted": False,
                "updated_at": None,
            })
    return result


async def update_consent(
    db: AsyncSession,
    user_id: str,
    consent_type: str,
    granted: bool,
    ip_address: str | None = None,
    version: str = "1.0",
) -> None:
    """Grant or revoke a consent type. Creates consent_records + audit_log entries."""
    if consent_type not in CONSENT_TYPES:
        raise ValueError(f"Invalid consent type: {consent_type}")

    # Get current value for audit log
    current = (
        await db.execute(
            text(
                "SELECT granted FROM gdpr.consent_records "
                "WHERE user_id = :uid AND consent_type = :ct "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"uid": user_id, "ct": consent_type},
        )
    ).mappings().first()

    old_value = current["granted"] if current else None

    # Insert consent record
    await db.execute(
        text(
            "INSERT INTO gdpr.consent_records "
            "(user_id, consent_type, granted, version, ip_address) "
            "VALUES (:uid, :ct, :granted, :ver, :ip)"
        ),
        {
            "uid": user_id,
            "ct": consent_type,
            "granted": granted,
            "ver": version,
            "ip": ip_address,
        },
    )

    # Insert audit log entry
    action = "grant" if granted else "revoke"
    await db.execute(
        text(
            "INSERT INTO gdpr.consent_audit_log "
            "(user_id, action, consent_type, old_value, new_value, ip_address) "
            "VALUES (:uid, :action, :ct, :old, :new, :ip)"
        ),
        {
            "uid": user_id,
            "action": action,
            "ct": consent_type,
            "old": old_value,
            "new": granted,
            "ip": ip_address,
        },
    )

    await db.commit()


async def get_consent_history(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Get paginated consent change history for a user."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM gdpr.consent_records WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                "SELECT id, consent_type, granted, version, ip_address, created_at "
                "FROM gdpr.consent_records "
                "WHERE user_id = :uid "
                "ORDER BY created_at DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"uid": user_id, "lim": page_size, "off": offset},
        )
    ).mappings().all()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "consent_type": r["consent_type"],
                "granted": r["granted"],
                "version": r["version"],
                "ip_address": r["ip_address"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def check_marketing_consent(
    db: AsyncSession, user_id: str
) -> bool:
    """Check if user has granted marketing_email consent.

    Used by abandoned cart and other modules before sending marketing emails.
    """
    row = (
        await db.execute(
            text(
                "SELECT granted FROM gdpr.consent_records "
                "WHERE user_id = :uid AND consent_type = 'marketing_email' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    return bool(row["granted"]) if row else False
