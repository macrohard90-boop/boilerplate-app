"""Marketing admin endpoints — campaigns, email logs, suppressed users, comm types, templates."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.marketing.models.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignStatsResponse,
    CampaignWizardRequest,
    CommunicationTypeCreateRequest,
    CommunicationTypeResponse,
    InsightsSegmentRequest,
    SegmentCreateRequest,
    SegmentPreviewRequest,
    SegmentUpdateRequest,
    TemplateCloneRequest,
    TemplateCreateRequest,
    TemplateListResponse,
    TemplatePreviewRequest,
    TemplateResponse,
    TemplateUpdateRequest,
)
from modules.marketing.services import campaign_service
from modules.marketing.services import template_crud_service
from modules.marketing.services.audience_service import (
    create_communication_type,
    get_eligible_recipients,
    list_communication_types,
    update_communication_type,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-marketing"],
    dependencies=[Depends(require_role("admin"))],
)


# ── Campaigns ──────────────────────────────────────────────


@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List all marketing campaigns (paginated, filterable by status)."""
    return await campaign_service.list_campaigns(
        db, status=status, page=page, per_page=per_page
    )


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create a new draft campaign."""
    result = await campaign_service.create_campaign(
        db,
        name=body.name,
        subject=body.subject,
        template_id=body.template_id,
        template_data=body.template_data,
        created_by=user["user_id"],
        scheduled_at=body.scheduled_at,
    )
    return result


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Send or schedule a draft/scheduled campaign."""
    try:
        return await campaign_service.send_campaign(db, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/campaigns/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Get campaign delivery stats (cached, refreshed from ESP every 5 min)."""
    try:
        return await campaign_service.get_campaign_stats(db, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/campaigns/{campaign_id}")
async def cancel_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Cancel a draft or scheduled campaign."""
    try:
        return await campaign_service.cancel_campaign(db, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Email Logs ─────────────────────────────────────────────


@router.get("/email-logs")
async def list_email_logs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    email_type: str | None = Query(None),
    status: str | None = Query(None),
    user_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Paginated email event audit log from gdpr.email_events."""
    where = "WHERE 1=1"
    params: dict[str, Any] = {"lim": page_size, "off": (page - 1) * page_size}

    if email_type:
        where += " AND email_type = :etype"
        params["etype"] = email_type
    if status:
        where += " AND status = :status"
        params["status"] = status
    if user_id:
        where += " AND user_id = :uid"
        params["uid"] = user_id

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM gdpr.email_events {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, user_id, email_type, template_id, provider, "
                    f"provider_message_id, status, skip_reason, "
                    f"sent_at, delivered_at, created_at "
                    f"FROM gdpr.email_events {where} "
                    f"ORDER BY created_at DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "email_type": r["email_type"],
                "template_id": r["template_id"],
                "provider": r["provider"],
                "provider_message_id": r["provider_message_id"],
                "status": r["status"],
                "skip_reason": r["skip_reason"],
                "sent_at": str(r["sent_at"]) if r["sent_at"] else None,
                "delivered_at": str(r["delivered_at"]) if r["delivered_at"] else None,
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/resend/{event_id}")
async def resend_failed_email(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Resend a failed email by pushing it back to the retry queue."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, user_id, template_id, email_type, status "
                    "FROM gdpr.email_events WHERE id = :eid"
                ),
                {"eid": event_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Email event not found")
    if row["status"] not in ("bounced", "complained", "skipped"):
        raise HTTPException(
            status_code=400, detail=f"Cannot resend email with status '{row['status']}'"
        )

    from modules.gdpr.services.email_send_service import send_email

    try:
        result = await send_email(
            db,
            user_id=str(row["user_id"]),
            template_id=row["template_id"],
            template_data={},
            email_type=row["email_type"],
        )
        return {"status": "resent", "new_event_id": result.get("event_id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resend failed: {e}")


# ── Suppressed Users ──────────────────────────────────────


@router.get("/suppressed")
async def list_suppressed_users(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List users with suppressed email delivery."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM gdpr.email_preferences "
                "WHERE suppressed_at IS NOT NULL"
            )
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    "SELECT ep.user_id, u.email, ep.suppressed_at, ep.suppression_reason "
                    "FROM gdpr.email_preferences ep "
                    "JOIN core.users u ON u.id = ep.user_id "
                    "WHERE ep.suppressed_at IS NOT NULL "
                    "ORDER BY ep.suppressed_at DESC "
                    "LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [
            {
                "user_id": str(r["user_id"]),
                "email": r["email"],
                "suppressed_at": str(r["suppressed_at"]),
                "suppression_reason": r["suppression_reason"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Eligible Recipients (audience preview) ────────────────


@router.get("/audience")
async def preview_audience(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    communication_type_id: str | None = Query(None),
):
    """Preview eligible recipients for a given communication type."""
    recipients = await get_eligible_recipients(db, communication_type_id)
    return {"count": len(recipients), "recipients": recipients}


# ── Communication Types ───────────────────────────────────


@router.get("/communication-types", response_model=list[CommunicationTypeResponse])
async def get_communication_types(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    include_disabled: bool = Query(False),
):
    """List all communication types."""
    return await list_communication_types(db, include_disabled=include_disabled)


@router.post(
    "/communication-types",
    response_model=CommunicationTypeResponse,
    status_code=201,
)
async def create_comm_type(
    body: CommunicationTypeCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create a new communication type."""
    try:
        return await create_communication_type(
            db, name=body.name, description=body.description, enabled=body.enabled
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/communication-types/{type_id}", response_model=CommunicationTypeResponse)
async def update_comm_type(
    type_id: str,
    body: CommunicationTypeCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Update an existing communication type."""
    try:
        return await update_communication_type(
            db,
            type_id,
            name=body.name,
            description=body.description,
            enabled=body.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Email Templates ──────────────────────────────────────


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List all email templates (paginated, filterable by category)."""
    return await template_crud_service.list_templates(
        db, category=category, page=page, per_page=per_page
    )


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create a new email template."""
    try:
        result = await template_crud_service.create_template(
            db,
            name=body.name,
            display_name=body.display_name,
            html_content=body.html_content,
            category=body.category,
            subject=body.subject,
            description=body.description,
            variables=body.variables,
            created_by=user["user_id"],
        )
        # Fetch full template for response
        return await template_crud_service.get_template(db, result["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/preview")
async def preview_template(
    body: TemplatePreviewRequest,
    user: dict = Depends(require_role("admin")),
):
    """Render arbitrary HTML with sample data and return the result."""
    try:
        rendered = await template_crud_service.preview_template(
            body.html_content, body.template_data
        )
        return {"html": rendered}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Render error: {e}")


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Get a single email template with full HTML content."""
    result = await template_crud_service.get_template(db, template_id)
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    body: TemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Update an email template (bumps version)."""
    result = await template_crud_service.update_template(
        db,
        template_id,
        display_name=body.display_name,
        subject=body.subject,
        html_content=body.html_content,
        category=body.category,
        description=body.description,
        variables=body.variables,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    # Fetch full template for response
    return await template_crud_service.get_template(db, template_id)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Delete a template. Built-in templates cannot be deleted."""
    try:
        await template_crud_service.delete_template(db, template_id)
        return {"status": "deleted"}
    except ValueError as e:
        status = 400 if "Cannot delete" in str(e) else 404
        raise HTTPException(status_code=status, detail=str(e))


@router.post(
    "/templates/{template_id}/clone", response_model=TemplateResponse, status_code=201
)
async def clone_template(
    template_id: str,
    body: TemplateCloneRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Clone a template with a new name."""
    try:
        result = await template_crud_service.clone_template(
            db,
            source_id=template_id,
            new_name=body.new_name,
            new_display_name=body.new_display_name,
            created_by=user["user_id"],
        )
        return await template_crud_service.get_template(db, result["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/templates/{template_id}/send-test")
async def send_test_email(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Send a test email using this template to the requesting admin."""
    template = await template_crud_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Look up admin's email
    admin_row = (
        (
            await db.execute(
                text("SELECT email FROM core.users WHERE id = :uid"),
                {"uid": user["user_id"]},
            )
        )
        .mappings()
        .first()
    )

    if not admin_row:
        raise HTTPException(status_code=400, detail="Admin user not found")

    from modules.gdpr.services.email_send_service import send_email

    try:
        # Build sample data from the template's variable definitions
        sample_data: dict[str, str] = {"first_name": "Test User"}
        for var in template.get("variables") or []:
            vname = var.get("name", "")
            if vname and vname not in sample_data:
                sample_data[vname] = f"[{vname}]"

        result = await send_email(
            db,
            user_id=user["user_id"],
            template_id=template["name"],
            template_data=sample_data,
            email_type="transactional_email",
            to_email=admin_row["email"],
            force=True,
        )
        return {
            "status": result.get("status", "sent"),
            "event_id": result.get("event_id"),
            "error": result.get("error"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Send failed: {e}")


# ── Campaign Wizard (A/B Variants) ───────────────────────


@router.post("/campaigns/wizard", status_code=201)
async def create_campaign_wizard(
    body: CampaignWizardRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create a campaign with A/B variants, audience segments, and UTM tracking."""
    try:
        result = await campaign_service.create_campaign_with_variants(
            db,
            name=body.name,
            variants=[v.model_dump() for v in body.variants],
            segment_ids=[s.model_dump() for s in body.segments],
            created_by=user["user_id"],
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            utm_content=body.utm_content,
            scheduled_at=body.scheduled_at,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns/{campaign_id}/variants")
async def get_campaign_variants(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Get all A/B variants for a campaign."""
    variants = await campaign_service.get_campaign_variants(db, campaign_id)
    return {"variants": variants}


@router.get("/campaigns/{campaign_id}/variant-stats")
async def get_campaign_variant_stats(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Get per-variant delivery stats for an A/B campaign."""
    try:
        stats = await campaign_service.get_campaign_variant_stats(db, campaign_id)
        return {"variant_stats": stats}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Audience Segments ─────────────────────────────────────


@router.get("/segments")
async def list_segments(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    include_system: bool = Query(True),
):
    """List all audience segments."""
    from modules.marketing.services import segment_service

    segments = await segment_service.list_segments(db, include_system=include_system)
    return {"segments": segments}


@router.post("/segments", status_code=201)
async def create_segment(
    body: SegmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create a custom audience segment."""
    from modules.marketing.services import segment_service

    try:
        result = await segment_service.create_segment(
            db,
            name=body.name,
            description=body.description,
            filters=body.filters,
            created_by=user["user_id"],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/segments/{segment_id}")
async def update_segment(
    segment_id: str,
    body: SegmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Update a custom audience segment."""
    from modules.marketing.services import segment_service

    try:
        return await segment_service.update_segment(
            db,
            segment_id,
            name=body.name,
            description=body.description,
            filters=body.filters,
        )
    except ValueError as e:
        status = 400 if "Cannot update" in str(e) else 404
        raise HTTPException(status_code=status, detail=str(e))


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Delete a custom segment. System segments cannot be deleted."""
    from modules.marketing.services import segment_service

    try:
        await segment_service.delete_segment(db, segment_id)
        return {"status": "deleted"}
    except ValueError as e:
        status = 400 if "Cannot delete" in str(e) else 404
        raise HTTPException(status_code=status, detail=str(e))


@router.post("/segments/preview")
async def preview_segment(
    body: SegmentPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Preview a segment: count + sample users for given filters."""
    from modules.marketing.services import segment_service

    count = await segment_service.compute_segment_count(db, body.filters)
    sample = await segment_service.compute_segment_users(db, body.filters, limit=10)
    return {"count": count, "sample_users": sample}


# ── Insights ─────────────────────────────────────────────


@router.get("/insights/global")
async def get_global_insights(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Global audience insights for the campaign wizard."""
    from modules.marketing.services import insights_service

    return await insights_service.get_global_insights(db)


@router.post("/insights/segment")
async def get_segment_insights(
    body: InsightsSegmentRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Segment-specific insights for a given filter set."""
    from modules.marketing.services import insights_service

    return await insights_service.get_segment_insights(db, body.filters)


@router.post("/insights/send-time")
async def get_send_time_suggestion(
    body: InsightsSegmentRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Suggested optimal send time based on audience activity patterns."""
    from modules.marketing.services import insights_service

    return await insights_service.get_send_time_suggestion(db, body.filters)
