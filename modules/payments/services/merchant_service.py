"""Merchant onboarding via Stripe Connect Express."""

import logging
from typing import Any

from backend.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.adapters import get_payment_provider

logger = logging.getLogger(__name__)


async def onboard_merchant(
    db: AsyncSession,
    user_id: str,
    business_name: str | None = None,
    business_type: str = "individual",
    country: str = "US",
) -> dict[str, Any]:
    """Create a Stripe Connect Express account and return the onboarding URL.

    If merchant already has an account, generate a new onboarding link.
    """
    # Check for existing merchant account
    existing = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.merchant_accounts "
                "WHERE user_id = :uid LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if existing:
        acct = dict(existing)
        # Generate a fresh onboarding link for existing account
        provider = get_payment_provider()
        onboarding_url = await provider.create_account_link(
            account_id=acct["stripe_account_id"],
            refresh_url=f"{settings.frontend_url}/merchant/onboard",
            return_url=f"{settings.frontend_url}/merchant/dashboard",
        )
        return {
            "account_id": acct["stripe_account_id"],
            "onboarding_url": onboarding_url,
            "status": acct["status"],
        }

    # Get user email
    user_row = (
        await db.execute(
            text("SELECT email FROM core.users WHERE id = :uid"),
            {"uid": user_id},
        )
    ).mappings().first()
    email = user_row["email"] if user_row else None

    # Create via provider
    provider = get_payment_provider()
    result = await provider.create_merchant({
        "email": email,
        "business_type": business_type,
        "country": country,
    })

    # Store in DB
    await db.execute(
        text(
            "INSERT INTO ecommerce.merchant_accounts "
            "(user_id, stripe_account_id, status, business_name) "
            "VALUES (:uid, :aid, :status, :bname)"
        ),
        {
            "uid": user_id,
            "aid": result.provider_account_id,
            "status": result.status,
            "bname": business_name,
        },
    )
    await db.commit()

    return {
        "account_id": result.provider_account_id,
        "onboarding_url": result.onboarding_url,
        "status": result.status,
    }


async def get_merchant_status(
    db: AsyncSession, user_id: str
) -> dict[str, Any] | None:
    """Get merchant account status."""
    row = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.merchant_accounts "
                "WHERE user_id = :uid LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if not row:
        return None

    acct = dict(row)
    return {
        "account_id": acct["stripe_account_id"],
        "status": acct["status"],
        "charges_enabled": acct["charges_enabled"],
        "payouts_enabled": acct["payouts_enabled"],
        "business_name": acct.get("business_name"),
    }


async def get_dashboard_link(
    db: AsyncSession, user_id: str
) -> str | None:
    """Generate a Stripe Express dashboard login link for the merchant."""
    row = (
        await db.execute(
            text(
                "SELECT stripe_account_id FROM ecommerce.merchant_accounts "
                "WHERE user_id = :uid AND status IN ('active', 'restricted') LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if not row:
        return None

    provider = get_payment_provider()
    return await provider.create_login_link(row["stripe_account_id"])
