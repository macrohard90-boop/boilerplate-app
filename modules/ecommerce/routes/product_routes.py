"""Product, variant, and image endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, require_role
from modules.ecommerce.models.schemas import (
    ImageCreate,
    ImageResponse,
    ImageUpdate,
    ProductCreate,
    ProductDetailResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)
from modules.ecommerce.services import (
    image_service,
    product_service,
    variant_service,
)

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    category_id: str | None = None,
    search: str | None = None,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await product_service.list_products(
        db, page=page, page_size=page_size, status=status,
        category_id=category_id, search=search, product_type=type,
    )


@router.get("/{slug}", response_model=ProductDetailResponse)
async def get_product(slug: str, db: AsyncSession = Depends(get_db)) -> Any:
    product = await product_service.get_product_by_slug(db, slug)
    if not product:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Product not found", "details": None})

    categories = await product_service.get_product_categories(db, str(product["id"]))
    variants = await variant_service.list_variants(db, str(product["id"]))
    images = await image_service.list_images(db, str(product["id"]))

    return {**product, "categories": categories, "variants": variants, "images": images}


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await product_service.create_product(db, body.model_dump())


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    body: ProductUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        return await product_service.update_product(db, product_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


@router.post("/{product_id}/sync", response_model=ProductResponse)
async def retry_product_sync(
    product_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retry catalog sync for a product and its variants (admin only)."""
    from modules.ecommerce.services import catalog_sync_service

    try:
        return await catalog_sync_service.retry_sync(db, product_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "sync_failed", "message": str(e), "details": None},
        )


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await product_service.delete_product(db, product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


@router.get("/{product_id}/variants", response_model=list[VariantResponse])
async def list_variants(product_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    return await variant_service.list_variants(db, product_id)


@router.get("/{product_id}/variants/{variant_id}", response_model=VariantResponse)
async def get_variant(product_id: str, variant_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    v = await variant_service.get_variant(db, variant_id)
    if not v or str(v["product_id"]) != product_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Variant not found", "details": None})
    return v


@router.post("/{product_id}/variants", response_model=VariantResponse, status_code=201)
async def create_variant(
    product_id: str,
    body: VariantCreate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    product = await product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Product not found", "details": None})
    return await variant_service.create_variant(db, product_id, body.model_dump())


@router.put("/{product_id}/variants/{variant_id}", response_model=VariantResponse)
async def update_variant(
    product_id: str,
    variant_id: str,
    body: VariantUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        v = await variant_service.update_variant(db, variant_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})
    if str(v["product_id"]) != product_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Variant not found", "details": None})
    return v


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
async def delete_variant(
    product_id: str,
    variant_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await variant_service.delete_variant(db, variant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@router.get("/{product_id}/images", response_model=list[ImageResponse])
async def list_images(product_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    return await image_service.list_images(db, product_id)


@router.post("/{product_id}/images", response_model=ImageResponse, status_code=201)
async def create_image(
    product_id: str,
    body: ImageCreate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    product = await product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Product not found", "details": None})
    return await image_service.create_image(db, product_id, body.model_dump())


@router.put("/{product_id}/images/{image_id}", response_model=ImageResponse)
async def update_image(
    product_id: str,
    image_id: str,
    body: ImageUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        img = await image_service.update_image(db, image_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})
    if str(img["product_id"]) != product_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Image not found", "details": None})
    return img


@router.delete("/{product_id}/images/{image_id}", status_code=204)
async def delete_image(
    product_id: str,
    image_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await image_service.delete_image(db, image_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(e), "details": None})
