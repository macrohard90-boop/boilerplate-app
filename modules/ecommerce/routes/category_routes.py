"""Category endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role

logger = logging.getLogger(__name__)
from modules.ecommerce.models.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryTreeResponse,
    CategoryUpdate,
    ProductListResponse,
)
from modules.ecommerce.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryTreeResponse])
async def list_categories(db: AsyncSession = Depends(get_db)) -> Any:
    return await category_service.list_categories_tree(db)


@router.get("/{slug}/products", response_model=ProductListResponse)
async def get_category_products(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    cat = await category_service.get_category_by_slug(db, slug)
    if not cat:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Category not found",
                "details": None,
            },
        )
    return await category_service.get_category_products(
        db, str(cat["id"]), page=page, page_size=page_size
    )


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await category_service.create_category(db, body.model_dump())

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.category_created",
                {
                    "category_id": str(result["id"]),
                    "category_name": result.get("name", ""),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.category_created", exc_info=True)

    return result


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    body: CategoryUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        result = await category_service.update_category(
            db, category_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.category_updated",
                {
                    "category_id": category_id,
                    "category_name": result.get("name", ""),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.category_updated", exc_info=True)

    return result


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await category_service.delete_category(db, category_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": msg, "details": None},
            )
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": msg, "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.category_deleted",
                {"category_id": category_id},
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.category_deleted", exc_info=True)
