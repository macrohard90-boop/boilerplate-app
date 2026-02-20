"""Integration tests for merchant onboarding — Connect Express lifecycle.

Full service→DB flow with real PostgreSQL. Stripe SDK is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_merchant_account
from tests.conftest import seed_user, seed_merchant

pytestmark = pytest.mark.integration


class TestMerchantOnboarding:
    async def test_new_merchant_creates_account(self, db, mock_merchant):
        """First-time onboarding creates Stripe Connect account + DB row."""
        from modules.payments.services.merchant_service import onboard_merchant

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")

        mock_prov = MagicMock()
        mock_prov.create_merchant = AsyncMock(return_value=MagicMock(
            provider_account_id="acct_new_int",
            status="onboarding",
            onboarding_url="https://connect.stripe.com/setup",
        ))

        with patch("modules.payments.services.merchant_service.get_payment_provider", return_value=mock_prov):
            result = await onboard_merchant(db, mock_merchant["user_id"], business_name="Test Shop")

        assert result["account_id"] == "acct_new_int"
        assert result["status"] == "onboarding"
        assert "stripe.com" in result["onboarding_url"]

        # Verify DB row
        row = (await db.execute(text(
            "SELECT stripe_account_id, status, business_name "
            "FROM ecommerce.merchant_accounts WHERE user_id = :uid"
        ), {"uid": mock_merchant["user_id"]})).mappings().first()
        assert row["stripe_account_id"] == "acct_new_int"
        assert row["business_name"] == "Test Shop"

    async def test_existing_merchant_gets_new_link(self, db, mock_merchant):
        """Re-onboarding generates a fresh link for existing account."""
        from modules.payments.services.merchant_service import onboard_merchant

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"], stripe_account_id="acct_exist_int",
        ))

        mock_prov = MagicMock()
        mock_prov.create_account_link = AsyncMock(return_value="https://connect.stripe.com/refresh")

        with patch("modules.payments.services.merchant_service.get_payment_provider", return_value=mock_prov):
            result = await onboard_merchant(db, mock_merchant["user_id"])

        assert result["account_id"] == "acct_exist_int"
        mock_prov.create_account_link.assert_called_once()


class TestMerchantStatus:
    async def test_returns_status(self, db, mock_merchant):
        """get_merchant_status returns account info from DB."""
        from modules.payments.services.merchant_service import get_merchant_status

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"], stripe_account_id="acct_st_int", status="active",
        ))

        result = await get_merchant_status(db, mock_merchant["user_id"])
        assert result["account_id"] == "acct_st_int"
        assert result["status"] == "active"

    async def test_no_account_returns_none(self, db, mock_merchant):
        from modules.payments.services.merchant_service import get_merchant_status

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        result = await get_merchant_status(db, mock_merchant["user_id"])
        assert result is None


class TestMerchantDashboard:
    async def test_dashboard_link_for_active_merchant(self, db, mock_merchant):
        """Active merchant gets a Stripe dashboard login link."""
        from modules.payments.services.merchant_service import get_dashboard_link

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"], stripe_account_id="acct_dash_int", status="active",
        ))

        mock_prov = MagicMock()
        mock_prov.create_login_link = AsyncMock(return_value="https://connect.stripe.com/login")

        with patch("modules.payments.services.merchant_service.get_payment_provider", return_value=mock_prov):
            result = await get_dashboard_link(db, mock_merchant["user_id"])

        assert result == "https://connect.stripe.com/login"

    async def test_no_dashboard_for_onboarding(self, db, mock_merchant):
        """Onboarding merchants can't access dashboard."""
        from modules.payments.services.merchant_service import get_dashboard_link

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"], stripe_account_id="acct_onb_int", status="onboarding",
        ))

        result = await get_dashboard_link(db, mock_merchant["user_id"])
        assert result is None


class TestWebhookAccountUpdate:
    async def test_account_updated_webhook_changes_status(self, db, mock_merchant):
        """account.updated webhook → merchant status updated in DB."""
        from modules.payments.services.webhook_service import _handle_account_updated

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(
            user_id=mock_merchant["user_id"], stripe_account_id="acct_wh_int", status="onboarding",
        ))

        await _handle_account_updated(db, {
            "id": "acct_wh_int",
            "charges_enabled": True,
            "payouts_enabled": True,
            "requirements": {},
        })

        row = (await db.execute(text(
            "SELECT status, charges_enabled, payouts_enabled "
            "FROM ecommerce.merchant_accounts WHERE stripe_account_id = 'acct_wh_int'"
        ))).mappings().first()
        assert row["status"] == "active"
        assert row["charges_enabled"] is True
        assert row["payouts_enabled"] is True
