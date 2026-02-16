"""Data export (Right of Access) endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.gdpr.models.schemas import ExportStatusResponse, MessageResponse
from modules.gdpr.services import export_service

router = APIRouter(tags=["gdpr-export"])


@router.post("/export", response_model=ExportStatusResponse)
async def request_export(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Request a data export. Rate limited to 1 per 24 hours."""
    try:
        result = await export_service.request_export(db, user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=429, detail={
            "error": "rate_limited",
            "message": str(e),
            "details": None,
        })

    return ExportStatusResponse(**result)


@router.get("/export/{export_id}", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Check export status and download data if completed."""
    try:
        result = await export_service.get_export_status(
            db, user["user_id"], export_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail={
            "error": "not_found",
            "message": str(e),
            "details": None,
        })

    return ExportStatusResponse(**result)
