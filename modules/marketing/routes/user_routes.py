"""User-facing marketing preferences endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.marketing.models.schemas import UserPreferencesUpdateRequest

router = APIRouter(
    prefix="/preferences",
    tags=["marketing-preferences"],
)


@router.get("")
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get the current user's marketing communication type preferences."""
    user_id = user["user_id"]

    # Check GDPR marketing_email consent
    consent_row = (
        await db.execute(
            text(
                "SELECT marketing_email FROM gdpr.email_preferences "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    marketing_email_consent = bool(consent_row and consent_row["marketing_email"])

    # Get all enabled communication types with user's preference (LEFT JOIN)
    rows = (
        await db.execute(
            text(
                "SELECT ct.id, ct.name, ct.description, "
                "COALESCE(ucp.allowed, FALSE) AS allowed "
                "FROM marketing.communication_types ct "
                "LEFT JOIN marketing.user_communication_preferences ucp "
                "  ON ucp.communication_type_id = ct.id AND ucp.user_id = :uid "
                "WHERE ct.enabled = TRUE "
                "ORDER BY ct.name"
            ),
            {"uid": user_id},
        )
    ).mappings().all()

    return {
        "marketing_email_consent": marketing_email_consent,
        "preferences": [
            {
                "communication_type_id": str(r["id"]),
                "communication_type_name": r["name"],
                "description": r["description"],
                "allowed": r["allowed"],
            }
            for r in rows
        ],
    }


@router.put("")
async def update_preferences(
    body: UserPreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update the current user's marketing communication type preferences."""
    user_id = user["user_id"]

    for pref in body.preferences:
        await db.execute(
            text(
                "INSERT INTO marketing.user_communication_preferences "
                "(user_id, communication_type_id, allowed) "
                "VALUES (:uid, :ctid, :allowed) "
                "ON CONFLICT (user_id, communication_type_id) "
                "DO UPDATE SET allowed = :allowed, updated_at = NOW()"
            ),
            {
                "uid": user_id,
                "ctid": pref.communication_type_id,
                "allowed": pref.allowed,
            },
        )

    await db.commit()

    return {"status": "updated", "count": len(body.preferences)}
