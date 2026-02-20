"""Integration tests for subscription lifecycle — create, cancel, webhook update.

Full service→DB flow with real PostgreSQL. Only Stripe SDK is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_recurring_product, make_variant, make_discount, make_subscription
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, seed_subscription, seed_stripe_customer, tid

pytestmark = pytest.mark.integration


class TestSubscriptionCreation:
    async def test_creates_subscription_in_db(self, db, mock_user):
        """Create subscription writes to DB and returns client_secret."""
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-si1"), stripe_price_id="price_si1"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_si1")

        mock_prov = MagicMock()
        mock_prov.create_subscription = AsyncMock(return_value=MagicMock(
            provider_subscription_id="sub_si1", status="active",
            client_secret="sec_si1",
            current_period_start=1700000000, current_period_end=1702592000,
        ))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            result = await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-si1"))

        assert result["client_secret"] == "sec_si1"

        # Verify in DB
        row = (await db.execute(text(
            "SELECT stripe_subscription_id, status, user_id "
            "FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_si1'"
        ))).mappings().first()
        assert row is not None
        assert row["status"] == "active"
        assert str(row["user_id"]) == mock_user["user_id"]

    async def test_creates_customer_if_missing(self, db, mock_user):
        """When no stripe_customer row exists, creates one via Stripe."""
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-si2"), stripe_price_id="price_si2"))

        mock_prov = MagicMock()
        mock_prov.create_customer = AsyncMock(return_value=MagicMock(provider_customer_id="cus_auto"))
        mock_prov.create_subscription = AsyncMock(return_value=MagicMock(
            provider_subscription_id="sub_si2", status="active",
            client_secret="sec", current_period_start=None, current_period_end=None,
        ))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-si2"))

        # Verify customer row created
        row = (await db.execute(text(
            "SELECT stripe_customer_id FROM ecommerce.stripe_customers WHERE user_id = :uid"
        ), {"uid": mock_user["user_id"]})).mappings().first()
        assert row["stripe_customer_id"] == "cus_auto"

    async def test_with_discount_code_increments_usage(self, db, mock_user):
        """Discount code usage counter increments after subscription creation."""
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-si3"), stripe_price_id="price_si3"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_si3")
        disc = await seed_discount(db, make_discount(code="SUBUSE", applies_to="recurring", stripe_coupon_id="coup_x"))

        mock_prov = MagicMock()
        mock_prov.create_subscription = AsyncMock(return_value=MagicMock(
            provider_subscription_id="sub_si3", status="active",
            client_secret="s", current_period_start=None, current_period_end=None,
        ))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-si3"), discount_code="SUBUSE")

        row = (await db.execute(text(
            "SELECT uses_count FROM ecommerce.discount_codes WHERE id = :id"
        ), {"id": str(disc["id"])})).mappings().first()
        assert row["uses_count"] == 1


class TestSubscriptionCancellation:
    async def test_cancel_marks_in_db(self, db, mock_user):
        """Cancellation sets cancel_at_period_end and canceled_at."""
        from modules.ecommerce.services.subscription_service import cancel_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc")))
        sub = await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-sc"),
            stripe_subscription_id="sub_cancel", status="active",
        ))

        mock_prov = MagicMock()
        mock_prov.cancel_subscription = AsyncMock()

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            result = await cancel_subscription(db, str(sub["id"]), mock_user["user_id"])

        assert result["cancel_at_period_end"] is True
        assert result["canceled_at"] is not None


class TestSubscriptionWebhookUpdate:
    async def test_webhook_updates_status_and_period(self, db, mock_user):
        """Webhook update changes status and period timestamps in DB."""
        from modules.ecommerce.services.subscription_service import update_subscription_from_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-swh")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-swh"),
            stripe_subscription_id="sub_wh_int", status="active",
        ))

        await update_subscription_from_webhook(db, "sub_wh_int", "past_due", 1700000000, 1702592000)

        row = (await db.execute(text(
            "SELECT status, current_period_start, current_period_end "
            "FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_wh_int'"
        ))).mappings().first()
        assert row["status"] == "past_due"
        assert row["current_period_start"] is not None
        assert row["current_period_end"] is not None


class TestSubscriptionListing:
    async def test_list_user_subscriptions(self, db, mock_user):
        """Lists all subscriptions for a user with product info."""
        from modules.ecommerce.services.subscription_service import list_user_subscriptions

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-ls"), name="Pro Plan"))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-ls"),
            stripe_subscription_id="sub_ls1", status="active",
        ))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-ls"),
            stripe_subscription_id="sub_ls2", status="canceled",
        ))

        result = await list_user_subscriptions(db, mock_user["user_id"])
        assert len(result) == 2
        assert all(r["product_name"] == "Pro Plan" for r in result)
