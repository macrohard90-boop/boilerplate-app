"""Pydantic request/response models for the e-commerce module."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    parent_id: UUID | None
    description: str | None
    sort_order: int
    created_at: datetime


class CategoryTreeResponse(CategoryResponse):
    children: list["CategoryTreeResponse"] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    sku: str | None = Field(default=None, max_length=100)
    base_price: int = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = "draft"
    type: str = "physical"
    category_ids: list[UUID] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("draft", "active", "archived"):
            raise ValueError("status must be draft, active, or archived")
        return v

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in ("physical", "digital"):
            raise ValueError("type must be physical or digital")
        return v


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    sku: str | None = Field(default=None, max_length=100)
    base_price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = None
    type: str | None = None
    category_ids: list[UUID] | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("draft", "active", "archived"):
            raise ValueError("status must be draft, active, or archived")
        return v

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("physical", "digital"):
            raise ValueError("type must be physical or digital")
        return v


class ProductResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    sku: str | None
    base_price: int
    currency: str
    status: str
    type: str
    stripe_product_id: str | None = None
    stripe_price_id: str | None = None
    stripe_sync_status: str = "unsynced"
    stripe_sync_error: str | None = None
    synced_provider: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductDetailResponse(ProductResponse):
    categories: list[CategoryResponse] = Field(default_factory=list)
    variants: list["VariantResponse"] = Field(default_factory=list)
    images: list["ImageResponse"] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Variant
# ---------------------------------------------------------------------------

class VariantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    price_override: int | None = Field(default=None, ge=0)
    stock_quantity: int = Field(default=0, ge=0)
    attributes: dict = Field(default_factory=dict)


class VariantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    price_override: int | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    attributes: dict | None = None


class VariantResponse(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    sku: str | None
    price_override: int | None
    stock_quantity: int
    effective_price: int
    attributes: dict
    stripe_price_id: str | None = None
    stripe_sync_status: str = "unsynced"
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------

class ImageCreate(BaseModel):
    variant_id: UUID | None = None
    url: str = Field(..., min_length=1)
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int = 0
    is_primary: bool = False


class ImageUpdate(BaseModel):
    variant_id: UUID | None = None
    url: str | None = Field(default=None, min_length=1)
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None
    is_primary: bool | None = None


class ImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None
    url: str
    alt_text: str | None
    sort_order: int
    is_primary: bool
    storage_path: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class CartItemAdd(BaseModel):
    product_id: UUID
    variant_id: UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    product_id: UUID
    variant_id: UUID
    quantity: int
    unit_price: int
    total_price: int
    product_name: str
    variant_name: str
    currency: str = "USD"


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    subtotal: int
    discount_amount: int = 0
    discount_code: str | None = None
    total: int
    currency: str = "USD"
    item_count: int


class CartDiscountApply(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    shipping_address: dict | None = None
    billing_address: dict | None = None


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    currency: str
    subtotal: int
    discount_amount: int
    tax_amount: int
    total: int
    shipping_address: dict | None
    billing_address: dict | None
    created_at: datetime
    updated_at: datetime


class OrderItemResponse(BaseModel):
    product_id: UUID
    variant_id: UUID
    quantity: int
    unit_price: int
    total_price: int
    product_snapshot: dict


class OrderDetailResponse(OrderResponse):
    items: list[OrderItemResponse] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        allowed = ("pending", "processing", "accepted", "completed", "rejected", "refunded")
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# Discount
# ---------------------------------------------------------------------------

class DiscountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    type: str
    value: int = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    min_order_amount: int = Field(default=0, ge=0)
    max_uses: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in ("percentage", "fixed", "free_shipping"):
            raise ValueError("type must be percentage, fixed, or free_shipping")
        return v


class DiscountUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    type: str | None = None
    value: int | None = Field(default=None, ge=0)
    min_order_amount: int | None = Field(default=None, ge=0)
    max_uses: int | None = None
    valid_until: datetime | None = None
    active: bool | None = None

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("percentage", "fixed", "free_shipping"):
            raise ValueError("type must be percentage, fixed, or free_shipping")
        return v


class DiscountResponse(BaseModel):
    id: UUID
    code: str
    type: str
    value: int
    currency: str
    min_order_amount: int
    max_uses: int | None
    uses_count: int
    valid_from: datetime
    valid_until: datetime | None
    active: bool
    created_at: datetime


class DiscountListResponse(BaseModel):
    items: list[DiscountResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryAdjust(BaseModel):
    quantity_change: int
    reason: str = Field(..., min_length=1, max_length=100)


class InventoryRecordResponse(BaseModel):
    id: UUID
    variant_id: UUID
    quantity_change: int
    reason: str
    reference_id: UUID | None
    created_at: datetime


class LowStockResponse(BaseModel):
    variant_id: UUID
    product_id: UUID
    product_name: str
    variant_name: str
    stock_quantity: int
    sku: str | None


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

class WishlistCreate(BaseModel):
    name: str = Field(default="My Wishlist", min_length=1, max_length=100)


class WishlistItemAdd(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None


class WishlistResponse(BaseModel):
    id: UUID
    name: str
    is_default: bool
    created_at: datetime
    items: list["WishlistItemResponse"] = Field(default_factory=list)


class WishlistItemResponse(BaseModel):
    product_id: UUID
    variant_id: UUID | None
    added_at: datetime
    product_name: str | None = None
    product_slug: str | None = None
    base_price: int | None = None


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(default=None, max_length=200)
    body: str | None = None


class ReviewResponse(BaseModel):
    id: UUID
    product_id: UUID
    user_id: UUID
    rating: int
    title: str | None
    body: str | None
    status: str
    created_at: datetime


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReviewModerate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("approved", "rejected"):
            raise ValueError("status must be approved or rejected")
        return v


# ---------------------------------------------------------------------------
# Digital Assets
# ---------------------------------------------------------------------------

class DigitalAssetCreate(BaseModel):
    product_id: UUID
    file_url: str = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., ge=0)
    download_limit: int | None = None


class DigitalAssetUpdate(BaseModel):
    file_url: str | None = Field(default=None, min_length=1)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    file_size: int | None = Field(default=None, ge=0)
    download_limit: int | None = None


class DigitalAssetResponse(BaseModel):
    id: UUID
    product_id: UUID
    file_url: str
    file_name: str
    file_size: int
    download_limit: int | None
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in: int


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | list | None = None
