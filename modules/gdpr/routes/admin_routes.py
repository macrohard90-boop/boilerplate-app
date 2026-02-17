"""Admin GDPR dashboard endpoints."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.gdpr.models.schemas import (
    AuditLogItem,
    AuditLogResponse,
    ConsentStatsResponse,
    ConsentTypeStat,
    DeletionListItem,
    DeletionListResponse,
    ExportListItem,
    ExportListResponse,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-gdpr"],
    dependencies=[Depends(require_role("admin"))],
)


# ── Export Requests ──────────────────────────────────────────

@router.get("/exports", response_model=ExportListResponse)
async def list_exports(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all data export requests (paginated, filterable by status)."""
    where = "WHERE 1=1"
    params: dict[str, Any] = {"lim": page_size, "off": (page - 1) * page_size}
    if status:
        where += " AND status = :status"
        params["status"] = status

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM gdpr.data_export_requests {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                f"SELECT id, user_id, status, requested_at, completed_at, expires_at "
                f"FROM gdpr.data_export_requests {where} "
                f"ORDER BY requested_at DESC LIMIT :lim OFFSET :off"
            ),
            params,
        )
    ).mappings().all()

    return ExportListResponse(
        items=[
            ExportListItem(
                id=str(r["id"]),
                user_id=str(r["user_id"]),
                status=r["status"],
                requested_at=str(r["requested_at"]),
                completed_at=str(r["completed_at"]) if r["completed_at"] else None,
                expires_at=str(r["expires_at"]) if r["expires_at"] else None,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Deletion Requests ────────────────────────────────────────

@router.get("/deletions", response_model=DeletionListResponse)
async def list_deletions(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all deletion requests (paginated, filterable by status)."""
    where = "WHERE 1=1"
    params: dict[str, Any] = {"lim": page_size, "off": (page - 1) * page_size}
    if status:
        where += " AND status = :status"
        params["status"] = status

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM gdpr.deletion_requests {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                f"SELECT id, user_id, status, requested_at, grace_period_ends, completed_at "
                f"FROM gdpr.deletion_requests {where} "
                f"ORDER BY requested_at DESC LIMIT :lim OFFSET :off"
            ),
            params,
        )
    ).mappings().all()

    return DeletionListResponse(
        items=[
            DeletionListItem(
                id=str(r["id"]),
                user_id=str(r["user_id"]),
                status=r["status"],
                requested_at=str(r["requested_at"]),
                grace_period_ends=str(r["grace_period_ends"]) if r["grace_period_ends"] else None,
                completed_at=str(r["completed_at"]) if r["completed_at"] else None,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Consent Stats ────────────────────────────────────────────

@router.get("/consent-stats", response_model=ConsentStatsResponse)
async def get_consent_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Consent grant/revoke rates by type."""
    rows = (
        await db.execute(
            text(
                "SELECT consent_type, "
                "SUM(CASE WHEN granted THEN 1 ELSE 0 END) AS total_grants, "
                "SUM(CASE WHEN NOT granted THEN 1 ELSE 0 END) AS total_revokes "
                "FROM gdpr.consent_records "
                "GROUP BY consent_type ORDER BY consent_type"
            )
        )
    ).mappings().all()

    return ConsentStatsResponse(
        stats=[
            ConsentTypeStat(
                consent_type=r["consent_type"],
                total_grants=r["total_grants"],
                total_revokes=r["total_revokes"],
            )
            for r in rows
        ]
    )


# ── Audit Log ────────────────────────────────────────────────

@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    user_id: str | None = Query(None),
    consent_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Consent audit log (paginated, filterable by user and type)."""
    where = "WHERE 1=1"
    params: dict[str, Any] = {"lim": page_size, "off": (page - 1) * page_size}
    if user_id:
        where += " AND user_id = :uid"
        params["uid"] = user_id
    if consent_type:
        where += " AND consent_type = :ct"
        params["ct"] = consent_type

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM gdpr.consent_audit_log {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                f"SELECT id, user_id, action, consent_type, old_value, new_value, "
                f"ip_address, created_at "
                f"FROM gdpr.consent_audit_log {where} "
                f"ORDER BY created_at DESC LIMIT :lim OFFSET :off"
            ),
            params,
        )
    ).mappings().all()

    return AuditLogResponse(
        items=[
            AuditLogItem(
                id=str(r["id"]),
                user_id=str(r["user_id"]),
                action=r["action"],
                consent_type=r["consent_type"],
                old_value=r["old_value"],
                new_value=r["new_value"],
                ip_address=r["ip_address"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
