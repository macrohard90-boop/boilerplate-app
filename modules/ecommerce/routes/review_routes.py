"""Product review endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.ecommerce.models.schemas import (
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)
from modules.ecommerce.services import review_service

router = APIRouter(tags=["reviews"])


@router.get("/products/{product_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    product_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await review_service.list_reviews(db, product_id, page=page, page_size=page_size)


@router.post("/products/{product_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    product_id: str,
    body: ReviewCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await review_service.create_review(
            db, product_id, user["user_id"],
            body.rating, body.title, body.body,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": str(e), "details": None})
