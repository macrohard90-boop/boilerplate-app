"""Product, variant, and image endpoints."""

import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    File,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
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
    catalog_sync_service,
    image_service,
    product_service,
    variant_service,
)

logger = logging.getLogger(__name__)

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
    pricing_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await product_service.list_products(
        db,
        page=page,
        page_size=page_size,
        status=status,
        category_id=category_id,
        search=search,
        product_type=type,
        pricing_type=pricing_type,
    )


@router.get("/{slug}", response_model=ProductDetailResponse)
async def get_product(
    slug: str, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    product = await product_service.get_product_by_slug(db, slug)
    if not product:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Product not found",
                "details": None,
            },
        )

    categories = await product_service.get_product_categories(db, str(product["id"]))
    variants = await variant_service.list_variants(db, str(product["id"]))
    images = await image_service.list_images(db, str(product["id"]))

    # Fire product_viewed event
    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            user = getattr(request.state, "user", None)
            user_id = user["user_id"] if user else None
            session_id = (
                user.get("session_id") if user else request.headers.get("x-session-id")
            )
            if session_id:
                await record_event(
                    db,
                    session_id,
                    "product_viewed",
                    {
                        "product_id": str(product["id"]),
                        "product_slug": slug,
                        "product_name": product.get("name", ""),
                    },
                    user_id=user_id,
                )
        except Exception:
            logger.debug("Failed to record product_viewed event", exc_info=True)

    return {**product, "categories": categories, "variants": variants, "images": images}


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        result = await product_service.create_product(db, body.model_dump())
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": str(e), "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.product_created",
                {
                    "product_id": str(result["id"]),
                    "product_name": result.get("name", ""),
                    "status": result.get("status", ""),
                    "base_price": result.get("base_price", 0),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.product_created", exc_info=True)

    return result


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    body: ProductUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        result = await product_service.update_product(
            db, product_id, body.model_dump(exclude_unset=True)
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
                "admin.product_updated",
                {
                    "product_id": str(result["id"]),
                    "product_name": result.get("name", ""),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.product_updated", exc_info=True)

    return result


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
        msg = str(e)
        if "Cannot delete" in msg:
            raise HTTPException(
                status_code=409,
                detail={"error": "conflict", "message": msg, "details": None},
            )
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": msg, "details": None},
        )

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.product_deleted",
                {"product_id": product_id},
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.product_deleted", exc_info=True)


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


@router.get("/{product_id}/variants", response_model=list[VariantResponse])
async def list_variants(product_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    return await variant_service.list_variants(db, product_id)


@router.get("/{product_id}/variants/{variant_id}", response_model=VariantResponse)
async def get_variant(
    product_id: str, variant_id: str, db: AsyncSession = Depends(get_db)
) -> Any:
    v = await variant_service.get_variant(db, variant_id)
    if not v or str(v["product_id"]) != product_id:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Variant not found",
                "details": None,
            },
        )
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
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Product not found",
                "details": None,
            },
        )
    result = await variant_service.create_variant(db, product_id, body.model_dump())

    if settings.enable_tracking:
        try:
            from modules.tracking.services.event_service import record_event

            await record_event(
                db,
                user["session_id"],
                "admin.variant_created",
                {
                    "product_id": product_id,
                    "variant_name": result.get("name", ""),
                    "stock_quantity": result.get("stock_quantity", 0),
                },
                user_id=user["user_id"],
            )
        except Exception:
            logger.debug("Failed to track admin.variant_created", exc_info=True)

    return result


@router.put("/{product_id}/variants/{variant_id}", response_model=VariantResponse)
async def update_variant(
    product_id: str,
    variant_id: str,
    body: VariantUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        v = await variant_service.update_variant(
            db, variant_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )
    if str(v["product_id"]) != product_id:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Variant not found",
                "details": None,
            },
        )
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
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )


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
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Product not found",
                "details": None,
            },
        )
    result = await image_service.create_image(db, product_id, body.model_dump())
    await catalog_sync_service.sync_product_images_to_catalog(db, product_id)
    return result


@router.put("/{product_id}/images/{image_id}", response_model=ImageResponse)
async def update_image(
    product_id: str,
    image_id: str,
    body: ImageUpdate,
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        img = await image_service.update_image(
            db, image_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )
    if str(img["product_id"]) != product_id:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Image not found",
                "details": None,
            },
        )
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
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e), "details": None},
        )
    await catalog_sync_service.sync_product_images_to_catalog(db, product_id)


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/{product_id}/images/upload", response_model=ImageResponse, status_code=201
)
async def upload_image(
    product_id: str,
    file: UploadFile = File(...),
    variant_id: str | None = Form(None),
    user: dict = Depends(require_role("merchant")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Upload an image file for a product (optionally linked to a variant)."""
    product = await product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Product not found",
                "details": None,
            },
        )

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": f"File type {file.content_type} not allowed. Use JPEG, PNG, WebP, or GIF.",
                "details": None,
            },
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "file_too_large",
                "message": "File exceeds 5 MB limit.",
                "details": None,
            },
        )

    from modules.ecommerce.adapters import get_storage_provider

    storage = get_storage_provider()
    result = await storage.upload(
        file_bytes, file.filename or "image.jpg", file.content_type
    )

    img = await image_service.create_image(
        db,
        product_id,
        {
            "url": result.public_url,
            "storage_path": result.storage_path,
            "alt_text": file.filename,
            "is_primary": False,
            "variant_id": variant_id,
        },
    )
    await catalog_sync_service.sync_product_images_to_catalog(db, product_id)
    return img
