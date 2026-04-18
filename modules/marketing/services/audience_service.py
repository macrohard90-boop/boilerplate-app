"""Audience & communication type management for marketing module."""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_default_types(db: AsyncSession) -> list[dict[str, Any]]:
    """Ensure default communication types exist (idempotent)."""
    rows = (
        await db.execute(
            text(
                "SELECT id, name, description, enabled "
                "FROM marketing.communication_types ORDER BY name"
            )
        )
    ).mappings().all()

    if rows:
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "enabled": r["enabled"],
            }
            for r in rows
        ]

    # Seed defaults (should already exist from migration 024)
    defaults = [
        ("newsletters", "Regular updates and news about our products and services"),
        ("promotions", "Special offers, discounts, and promotional campaigns"),
        ("product_updates", "New product announcements and feature updates"),
    ]
    for name, desc in defaults:
        await db.execute(
            text(
                "INSERT INTO marketing.communication_types (name, description) "
                "VALUES (:name, :desc) ON CONFLICT (name) DO NOTHING"
            ),
            {"name": name, "desc": desc},
        )
    await db.commit()

    rows = (
        await db.execute(
            text(
                "SELECT id, name, description, enabled "
                "FROM marketing.communication_types ORDER BY name"
            )
        )
    ).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "enabled": r["enabled"],
        }
        for r in rows
    ]


async def list_communication_types(
    db: AsyncSession, include_disabled: bool = False
) -> list[dict[str, Any]]:
    """List communication types (optionally including disabled ones)."""
    where = "" if include_disabled else "WHERE enabled = TRUE"
    rows = (
        await db.execute(
            text(
                f"SELECT id, name, description, enabled, created_at "
                f"FROM marketing.communication_types {where} ORDER BY name"
            )
        )
    ).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "enabled": r["enabled"],
        }
        for r in rows
    ]


async def create_communication_type(
    db: AsyncSession, name: str, description: str | None = None, enabled: bool = True
) -> dict[str, Any]:
    """Create a new communication type."""
    row = (
        await db.execute(
            text(
                "INSERT INTO marketing.communication_types (name, description, enabled) "
                "VALUES (:name, :desc, :enabled) RETURNING id, name, description, enabled"
            ),
            {"name": name, "desc": description, "enabled": enabled},
        )
    ).mappings().first()

    await db.commit()
    logger.info("Communication type created: %s (%s)", row["id"], name)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "enabled": row["enabled"],
    }


async def update_communication_type(
    db: AsyncSession,
    type_id: str,
    name: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Update a communication type."""
    sets: list[str] = []
    params: dict[str, Any] = {"tid": type_id}

    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = description
    if enabled is not None:
        sets.append("enabled = :enabled")
        params["enabled"] = enabled

    if not sets:
        raise ValueError("No fields to update")

    row = (
        await db.execute(
            text(
                f"UPDATE marketing.communication_types SET {', '.join(sets)} "
                f"WHERE id = :tid RETURNING id, name, description, enabled"
            ),
            params,
        )
    ).mappings().first()

    if not row:
        raise ValueError("Communication type not found")

    await db.commit()
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "enabled": row["enabled"],
    }


async def get_eligible_recipients(
    db: AsyncSession, communication_type_id: str | None = None
) -> list[dict[str, Any]]:
    """Get users eligible for marketing emails.

    Filters:
    1. User has marketing_email consent (gdpr.email_preferences.marketing_email = true)
    2. User is not suppressed (gdpr.email_preferences.suppressed_at IS NULL)
    3. If communication_type_id is given, user has allowed that specific type
       (marketing.user_communication_preferences.allowed = true)
    """
    if communication_type_id:
        rows = (
            await db.execute(
                text(
                    "SELECT u.id AS user_id, u.email "
                    "FROM core.users u "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "JOIN marketing.user_communication_preferences ucp "
                    "  ON ucp.user_id = u.id AND ucp.communication_type_id = :ctid "
                    "WHERE ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL "
                    "  AND ucp.allowed = TRUE"
                ),
                {"ctid": communication_type_id},
            )
        ).mappings().all()
    else:
        rows = (
            await db.execute(
                text(
                    "SELECT u.id AS user_id, u.email "
                    "FROM core.users u "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "WHERE ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL"
                )
            )
        ).mappings().all()

    return [{"user_id": str(r["user_id"]), "email": r["email"]} for r in rows]
