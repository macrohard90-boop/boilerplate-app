"""Pydantic request/response models for payment processing."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Checkout ─────────────────────────────────────────────

class AddressSchema(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str | None = None
    postal_code: str
    country: str = "US"


class CheckoutRequest(BaseModel):
    shipping_address: AddressSchema
    billing_address: AddressSchema | None = None
    discount_code: str | None = None


class CheckoutResponse(BaseModel):
    order_id: str
    order_number: str
    client_secret: str
    subtotal: int
    discount_amount: int = 0
    tax_amount: int = 0
    total: int
    currency: str = "USD"


# ── Payment Status ───────────────────────────────────────

class PaymentStatusResponse(BaseModel):
    order_id: str
    order_status: str
    payment_status: str | None = None
    provider: str | None = None
    provider_payment_id: str | None = None
    client_secret: str | None = None
    amount: int = 0
    currency: str = "USD"
    created_at: datetime | None = None


# ── Refund ───────────────────────────────────────────────

class RefundRequest(BaseModel):
    amount: int | None = Field(None, description="Partial refund amount in cents. Null for full refund.")
    reason: str | None = None


class RefundResponse(BaseModel):
    order_id: str
    refund_id: str
    status: str
    amount: int
    currency: str = "USD"


# ── Merchant Onboarding ─────────────────────────────────

class MerchantOnboardRequest(BaseModel):
    business_name: str | None = None
    business_type: str = "individual"
    country: str = "US"


class MerchantOnboardResponse(BaseModel):
    account_id: str
    onboarding_url: str
    status: str = "onboarding"


class MerchantStatusResponse(BaseModel):
    account_id: str
    status: str
    charges_enabled: bool = False
    payouts_enabled: bool = False
    business_name: str | None = None


class MerchantDashboardResponse(BaseModel):
    dashboard_url: str


# ── Generic ──────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Any = None
