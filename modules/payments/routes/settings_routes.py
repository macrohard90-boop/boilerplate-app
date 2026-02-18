"""Admin-only payment settings routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from modules.auth.services.auth_service import require_role
from modules.payments.services import payment_settings_service
from modules.payments.services.payment_settings_service import SUPPORTED_METHODS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["payments-settings"])


class PaymentMethodsUpdate(BaseModel):
    """Request body for updating payment method toggles."""

    methods: dict[str, bool]


@router.get("/payment-methods")
async def get_payment_methods(
    _user: dict[str, Any] = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get current payment method toggle states."""
    stored = await payment_settings_service.get_setting(db, "payment_methods")

    # Build response: default all to True (automatic) if no customization
    methods: dict[str, bool] = {}
    for method in SUPPORTED_METHODS:
        if stored is not None:
            methods[method] = bool(stored.get(method, False))
        else:
            methods[method] = True  # Default: all enabled (automatic mode)

    return {"methods": methods, "customized": stored is not None}


@router.put("/payment-methods")
async def update_payment_methods(
    body: PaymentMethodsUpdate,
    _user: dict[str, Any] = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update payment method toggles. Only known methods are stored."""
    # Filter to only supported methods
    cleaned: dict[str, bool] = {}
    for method in SUPPORTED_METHODS:
        if method in body.methods:
            cleaned[method] = bool(body.methods[method])

    if not cleaned:
        raise HTTPException(status_code=400, detail="No valid payment methods provided")

    await payment_settings_service.upsert_setting(db, "payment_methods", cleaned)

    return {"methods": cleaned, "customized": True}
