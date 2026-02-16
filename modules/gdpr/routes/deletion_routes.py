"""Data deletion (Right to Erasure) endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.core.redis import get_redis
from modules.gdpr.models.schemas import DeletionStatusResponse, MessageResponse
from modules.gdpr.services import deletion_service

router = APIRouter(tags=["gdpr-deletion"])


@router.post("/deletion", response_model=DeletionStatusResponse)
async def request_deletion(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict = Depends(get_current_user),
):
    """Request account deletion. Immediately revokes all sessions."""
    try:
        result = await deletion_service.request_deletion(
            db, redis, user["user_id"]
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail={
            "error": "conflict",
            "message": str(e),
            "details": None,
        })

    return DeletionStatusResponse(**result)


@router.get("/deletion/{deletion_id}", response_model=DeletionStatusResponse)
async def get_deletion_status(
    deletion_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Check deletion request status."""
    try:
        result = await deletion_service.get_deletion_status(
            db, user["user_id"], deletion_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail={
            "error": "not_found",
            "message": str(e),
            "details": None,
        })

    return DeletionStatusResponse(**result)


@router.post("/deletion/{deletion_id}/cancel", response_model=MessageResponse)
async def cancel_deletion(
    deletion_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Cancel a deletion request during the grace period."""
    try:
        await deletion_service.cancel_deletion(
            db, user["user_id"], deletion_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={
            "error": "bad_request",
            "message": str(e),
            "details": None,
        })

    return MessageResponse(message="Deletion request cancelled")
