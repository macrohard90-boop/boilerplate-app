"""Wishlist endpoints for authenticated users."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from modules.ecommerce.models.schemas import (
    WishlistCreate,
    WishlistItemAdd,
    WishlistResponse,
)
from modules.ecommerce.services import wishlist_service

router = APIRouter(prefix="/wishlists", tags=["wishlists"])


@router.get("", response_model=list[WishlistResponse])
async def list_wishlists(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await wishlist_service.list_wishlists(db, user["user_id"])


@router.post("", response_model=WishlistResponse, status_code=201)
async def create_wishlist(
    body: WishlistCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await wishlist_service.create_wishlist(db, user["user_id"], body.name)


@router.post("/{wishlist_id}/items", response_model=WishlistResponse)
async def add_item(
    wishlist_id: str,
    body: WishlistItemAdd,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await wishlist_service.add_item(
            db,
            user["user_id"],
            wishlist_id,
            str(body.product_id),
            str(body.variant_id) if body.variant_id else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


@router.delete("/{wishlist_id}/items/{product_id}", status_code=204)
async def remove_item(
    wishlist_id: str,
    product_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await wishlist_service.remove_item(db, user["user_id"], wishlist_id, product_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


@router.delete("/{wishlist_id}", status_code=204)
async def delete_wishlist(
    wishlist_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await wishlist_service.delete_wishlist(db, user["user_id"], wishlist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": str(e), "details": None},
        )
