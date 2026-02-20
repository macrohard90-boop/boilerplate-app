"""Unit tests for merchant onboarding service."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_merchant_account, make_stripe_account, make_stripe_account_link, make_stripe_login_link
from tests.conftest import seed_user, seed_merchant

pytestmark = pytest.mark.unit

MODULE = "modules.payments.services.merchant_service"


class TestOnboardMerchant:
    async def test_new_merchant_creates_account(self, db, mock_merchant):
        from modules.payments.services.merchant_service import onboard_merchant
        from modules.payments.interfaces.payment_provider import MerchantAccount

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")

        mock_provider = MagicMock()
        mock_provider.create_merchant = AsyncMock(return_value=MerchantAccount(
            provider_account_id="acct_new_123",
            onboarding_url="https://connect.stripe.com/setup/e/new",
            status="onboarding",
        ))

        with patch(f"{MODULE}.get_payment_provider", return_value=mock_provider):
            result = await onboard_merchant(db, mock_merchant["user_id"], "Test Biz", "individual", "US")

        assert result["account_id"] == "acct_new_123"
        assert result["onboarding_url"] == "https://connect.stripe.com/setup/e/new"
        assert result["status"] == "onboarding"

        # Verify stored in DB
        row = (await db.execute(
            text("SELECT stripe_account_id FROM ecommerce.merchant_accounts WHERE user_id = :uid"),
            {"uid": mock_merchant["user_id"]},
        )).mappings().first()
        assert row["stripe_account_id"] == "acct_new_123"

    async def test_existing_merchant_returns_fresh_link(self, db, mock_merchant):
        from modules.payments.services.merchant_service import onboard_merchant

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"],
            stripe_account_id="acct_existing",
            status="restricted",
        ))

        mock_provider = MagicMock()
        mock_provider.create_account_link = AsyncMock(return_value="https://connect.stripe.com/setup/e/refresh")

        with patch(f"{MODULE}.get_payment_provider", return_value=mock_provider):
            result = await onboard_merchant(db, mock_merchant["user_id"])

        assert result["account_id"] == "acct_existing"
        assert result["onboarding_url"] == "https://connect.stripe.com/setup/e/refresh"
        mock_provider.create_account_link.assert_called_once()


class TestGetMerchantStatus:
    async def test_returns_account_info(self, db, mock_merchant):
        from modules.payments.services.merchant_service import get_merchant_status

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"],
            stripe_account_id="acct_status",
            status="active",
            charges_enabled=True,
            payouts_enabled=True,
        ))

        result = await get_merchant_status(db, mock_merchant["user_id"])
        assert result["account_id"] == "acct_status"
        assert result["status"] == "active"
        assert result["charges_enabled"] is True

    async def test_no_account_returns_none(self, db, mock_merchant):
        from modules.payments.services.merchant_service import get_merchant_status

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        result = await get_merchant_status(db, mock_merchant["user_id"])
        assert result is None


class TestGetDashboardLink:
    async def test_active_merchant_gets_link(self, db, mock_merchant):
        from modules.payments.services.merchant_service import get_dashboard_link

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"],
            stripe_account_id="acct_dash",
            status="active",
        ))

        mock_provider = MagicMock()
        mock_provider.create_login_link = AsyncMock(return_value="https://connect.stripe.com/express/login")

        with patch(f"{MODULE}.get_payment_provider", return_value=mock_provider):
            result = await get_dashboard_link(db, mock_merchant["user_id"])

        assert result == "https://connect.stripe.com/express/login"

    async def test_no_account_returns_none(self, db, mock_merchant):
        from modules.payments.services.merchant_service import get_dashboard_link

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        result = await get_dashboard_link(db, mock_merchant["user_id"])
        assert result is None

    async def test_onboarding_status_returns_none(self, db, mock_merchant):
        """Merchants still in onboarding can't get dashboard links."""
        from modules.payments.services.merchant_service import get_dashboard_link

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"],
            stripe_account_id="acct_onboard",
            status="onboarding",
        ))

        result = await get_dashboard_link(db, mock_merchant["user_id"])
        assert result is None  # status not in ('active', 'restricted')
