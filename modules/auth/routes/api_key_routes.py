"""API key management endpoints for M2M authentication."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.auth.models.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    MessageResponse,
)
from modules.auth.services import api_key_service, audit_service

router = APIRouter()


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    record, raw_key = await api_key_service.create_api_key(
        db,
        user_id=user["user_id"],
        name=body.name,
        scopes=body.scopes,
        rate_limit=body.rate_limit,
    )

    await audit_service.log_audit(
        db,
        user_id=user["user_id"],
        action="api_key.create",
        resource="api_key",
        resource_id=str(record["id"]),
    )

    scopes = record["scopes"] if isinstance(record["scopes"], list) else []

    return ApiKeyCreatedResponse(
        id=record["id"],
        name=record["name"],
        scopes=scopes,
        rate_limit=record["rate_limit"],
        is_active=record["is_active"],
        last_used_at=record.get("last_used_at"),
        created_at=record["created_at"],
        raw_key=raw_key,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    keys = await api_key_service.list_api_keys(db, user["user_id"])
    result = []
    for k in keys:
        scopes = k["scopes"] if isinstance(k["scopes"], list) else []
        result.append(
            ApiKeyResponse(
                id=k["id"],
                name=k["name"],
                scopes=scopes,
                rate_limit=k["rate_limit"],
                is_active=k["is_active"],
                last_used_at=k.get("last_used_at"),
                created_at=k["created_at"],
            )
        )
    return result


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    ok = await api_key_service.revoke_api_key(db, key_id, user["user_id"])
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "API key not found", "details": None},
        )

    await audit_service.log_audit(
        db,
        user_id=user["user_id"],
        action="api_key.revoke",
        resource="api_key",
        resource_id=key_id,
    )

    return MessageResponse(message="API key revoked")
