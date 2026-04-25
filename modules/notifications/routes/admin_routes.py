"""Notifications admin routes — test sends, message log, automation rules, guardrails config.

All endpoints require admin role. Individual channel endpoints are gated by
enable_sms / enable_whatsapp settings.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role

router = APIRouter(prefix="/admin", tags=["notifications-admin"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TestSmsRequest(BaseModel):
    to_number: str
    content: str
    sender: str | None = None


class TestWhatsAppRequest(BaseModel):
    to_number: str
    template_name: str | None = None
    text_content: str | None = None
    language: str = "en"
    parameters: dict[str, Any] | None = None


class AutomationRuleUpdate(BaseModel):
    enabled: bool | None = None
    template_id: str | None = None
    delay_seconds: int | None = None


class GuardrailsConfigUpdate(BaseModel):
    freq_cap_marketing_per_day: int | None = None
    freq_cap_marketing_per_week: int | None = None
    freq_cap_marketing_per_month: int | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    sunset_inactivity_days: int | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Test Sends
# ---------------------------------------------------------------------------


@router.post("/test-sms")
async def test_send_sms(
    body: TestSmsRequest,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test SMS. Requires ENABLE_SMS=true."""
    if not settings.enable_sms:
        raise HTTPException(status_code=400, detail="SMS is not enabled")

    from modules.notifications.services.sms_send_service import send_sms

    result = await send_sms(
        db,
        user_id=user.get("id"),
        to_number=body.to_number,
        content=body.content,
        sender=body.sender,
    )
    return result


@router.post("/test-whatsapp")
async def test_send_whatsapp(
    body: TestWhatsAppRequest,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test WhatsApp message. Requires ENABLE_WHATSAPP=true."""
    if not settings.enable_whatsapp:
        raise HTTPException(status_code=400, detail="WhatsApp is not enabled")

    if body.template_name:
        from modules.notifications.services.whatsapp_send_service import (
            send_whatsapp_template,
        )

        result = await send_whatsapp_template(
            db,
            user_id=user.get("id"),
            to_number=body.to_number,
            template_name=body.template_name,
            language=body.language,
            parameters=body.parameters,
        )
    elif body.text_content:
        from modules.notifications.services.whatsapp_send_service import (
            send_whatsapp_text,
        )

        result = await send_whatsapp_text(
            db,
            user_id=user.get("id"),
            to_number=body.to_number,
            text_content=body.text_content,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either template_name or text_content",
        )

    return result


# ---------------------------------------------------------------------------
# Message Log
# ---------------------------------------------------------------------------


@router.get("/message-log")
async def list_message_log(
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    channel: str | None = Query(None, description="Filter by channel: sms, whatsapp"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List recent notification messages (SMS + WhatsApp)."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"lim": limit, "off": offset}

    if channel:
        where_parts.append("ml.channel = :channel")
        params["channel"] = channel
    if status:
        where_parts.append("ml.status = :status")
        params["status"] = status

    where = " AND ".join(where_parts)

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT ml.id, ml.user_id, ml.channel, ml.provider, "
                    f"  ml.provider_message_id, ml.to_number, ml.template_id, "
                    f"  ml.body_preview, ml.status, ml.error_message, "
                    f"  ml.sent_at, ml.created_at "
                    f"FROM notifications.message_log ml "
                    f"WHERE {where} "
                    f"ORDER BY ml.created_at DESC "
                    f"LIMIT :lim OFFSET :off"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    count_row = (
        (
            await db.execute(
                text(
                    f"SELECT COUNT(*) as total "
                    f"FROM notifications.message_log ml "
                    f"WHERE {where}"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    return {
        "items": [
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "channel": r["channel"],
                "provider": r["provider"],
                "provider_message_id": r["provider_message_id"],
                "to_number": r["to_number"],
                "template_id": r["template_id"],
                "body_preview": r["body_preview"],
                "status": r["status"],
                "error_message": r["error_message"],
                "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "total": count_row["total"] if count_row else 0,
    }


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------


@router.get("/automation-rules")
async def list_automation_rules(
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all notification automation rules."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, event_name, channel, template_id, "
                    "  delay_seconds, enabled, created_at, updated_at "
                    "FROM notifications.automation_rules "
                    "ORDER BY event_name, channel"
                )
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "id": str(r["id"]),
            "event_name": r["event_name"],
            "channel": r["channel"],
            "template_id": r["template_id"],
            "delay_seconds": r["delay_seconds"],
            "enabled": r["enabled"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


@router.put("/automation-rules/{rule_id}")
async def update_automation_rule(
    rule_id: str,
    body: AutomationRuleUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enable/disable or update an automation rule."""
    set_parts = []
    params: dict[str, Any] = {"rid": rule_id}

    if body.enabled is not None:
        set_parts.append("enabled = :enabled")
        params["enabled"] = body.enabled
    if body.template_id is not None:
        set_parts.append("template_id = :template_id")
        params["template_id"] = body.template_id
    if body.delay_seconds is not None:
        set_parts.append("delay_seconds = :delay_seconds")
        params["delay_seconds"] = body.delay_seconds

    if not set_parts:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_parts.append("updated_at = NOW()")

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE notifications.automation_rules "
                    f"SET {', '.join(set_parts)} "
                    f"WHERE id = :rid "
                    f"RETURNING id, event_name, channel, template_id, "
                    f"  delay_seconds, enabled, updated_at"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.commit()

    return {
        "id": str(row["id"]),
        "event_name": row["event_name"],
        "channel": row["channel"],
        "template_id": row["template_id"],
        "delay_seconds": row["delay_seconds"],
        "enabled": row["enabled"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


# ---------------------------------------------------------------------------
# Guardrails Config
# ---------------------------------------------------------------------------


@router.get("/guardrails")
async def get_guardrails_config(
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all channel guardrails configuration."""
    from modules.marketing.services.guardrails_service import (
        get_guardrails_config as _get_config,
    )

    return await _get_config(db)


@router.put("/guardrails/{channel}")
async def update_guardrails_config(
    channel: str,
    body: GuardrailsConfigUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update guardrails config for a channel."""
    from modules.marketing.services.guardrails_service import (
        update_guardrails_config as _update_config,
    )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await _update_config(db, channel, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Channel config not found")

    return result


# ---------------------------------------------------------------------------
# Message Pressure Dashboard
# ---------------------------------------------------------------------------


@router.get("/message-pressure")
async def get_message_pressure(
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=90),
) -> dict:
    """Message pressure overview — sends per day and channel over time."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT DATE(sent_at) as date, channel, "
                    "  COUNT(*) as count, message_type "
                    "FROM marketing.message_pressure_log "
                    "WHERE sent_at > NOW() - INTERVAL '1 day' * :days "
                    "GROUP BY DATE(sent_at), channel, message_type "
                    "ORDER BY date DESC, channel"
                ),
                {"days": days},
            )
        )
        .mappings()
        .all()
    )

    # Summary: totals per channel
    summary_rows = (
        (
            await db.execute(
                text(
                    "SELECT channel, message_type, "
                    "  COUNT(*) as total, "
                    "  COUNT(*) FILTER (WHERE sent_at > NOW() - INTERVAL '1 day') as today, "
                    "  COUNT(*) FILTER (WHERE sent_at > NOW() - INTERVAL '7 days') as week "
                    "FROM marketing.message_pressure_log "
                    "WHERE sent_at > NOW() - INTERVAL '1 day' * :days "
                    "GROUP BY channel, message_type "
                    "ORDER BY channel, message_type"
                ),
                {"days": days},
            )
        )
        .mappings()
        .all()
    )

    return {
        "daily": [
            {
                "date": r["date"].isoformat() if r["date"] else None,
                "channel": r["channel"],
                "message_type": r["message_type"],
                "count": r["count"],
            }
            for r in rows
        ],
        "summary": [
            {
                "channel": r["channel"],
                "message_type": r["message_type"],
                "total": r["total"],
                "today": r["today"],
                "week": r["week"],
            }
            for r in summary_rows
        ],
    }
