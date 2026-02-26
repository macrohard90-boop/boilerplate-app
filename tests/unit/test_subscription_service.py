"""Unit tests for subscription service — create, cancel, list, webhook updates."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import (
    make_recurring_product, make_variant, make_discount,
    make_subscription, make_stripe_customer,
)
from tests.conftest import (
    seed_user, seed_product, seed_variant, seed_discount,
    seed_subscription, seed_stripe_customer, tid,
)

pytestmark = pytest.mark.unit


class TestGetOrCreateStripeCustomer:
    async def test_returns_existing_customer(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import get_or_create_stripe_customer

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_exist")

        result = await get_or_create_stripe_customer(db, mock_user["user_id"], mock_user["email"])
        assert result == "cus_exist"

    async def test_creates_new_customer_when_missing(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import get_or_create_stripe_customer

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        mock_prov = MagicMock()
        mock_prov.create_customer = AsyncMock(return_value=MagicMock(provider_customer_id="cus_new"))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            result = await get_or_create_stripe_customer(db, mock_user["user_id"], mock_user["email"])

        assert result == "cus_new"
        mock_prov.create_customer.assert_called_once_with(mock_user["email"], name=None, metadata={"user_id": mock_user["user_id"]})

        row = (await db.execute(text("SELECT stripe_customer_id FROM ecommerce.stripe_customers WHERE user_id = :uid"), {"uid": mock_user["user_id"]})).mappings().first()
        assert row["stripe_customer_id"] == "cus_new"


class TestCreateSubscription:
    async def test_creates_subscription_record(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-cs1"), stripe_price_id="price_cs1"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_cs1")

        mock_prov = MagicMock()
        mock_sub_result = MagicMock(
            provider_subscription_id="sub_cs1", status="active",
            client_secret="sec_cs1",
            current_period_start=1700000000, current_period_end=1702592000,
        )
        mock_prov.create_subscription = AsyncMock(return_value=mock_sub_result)

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            result = await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs1"))

        assert result["stripe_subscription_id"] == "sub_cs1"
        assert result["status"] == "active"
        assert result["client_secret"] == "sec_cs1"

    async def test_uses_variant_price_when_available(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-cs2"), stripe_price_id="price_prod"))
        await seed_variant(db, make_variant(id=tid("v-cs2"), product_id=tid("p-cs2"), stripe_price_id="price_var"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_cs2")

        mock_prov = MagicMock()
        mock_prov.create_subscription = AsyncMock(return_value=MagicMock(
            provider_subscription_id="sub_cs2", status="active", client_secret="s",
            current_period_start=None, current_period_end=None,
        ))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs2"), variant_id=tid("v-cs2"))

        call_args = mock_prov.create_subscription.call_args
        assert call_args[0][1] == "price_var"

    async def test_non_recurring_product_raises(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription
        from tests.factories import make_synced_product

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-cs3")))

        with pytest.raises(ValueError, match="not a recurring"):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs3"))

    async def test_unsynced_product_raises(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-cs4"), stripe_price_id=None))

        with pytest.raises(ValueError, match="not been synced"):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs4"))

    async def test_product_not_found_raises(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with pytest.raises(ValueError, match="Product not found"):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("nonexistent"))

    async def test_one_time_coupon_rejected(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-cs5"), stripe_price_id="price_5"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_cs5")
        await seed_discount(db, make_discount(code="ONETIME", applies_to="one_time"))

        mock_prov = MagicMock()
        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            with pytest.raises(ValueError, match="recurring subscriptions"):
                await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs5"), discount_code="ONETIME")

    async def test_with_discount_passes_coupon(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import create_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-cs6"), stripe_price_id="price_6"))
        await seed_stripe_customer(db, mock_user["user_id"], "cus_cs6")
        await seed_discount(db, make_discount(code="RECDISC", applies_to="recurring", stripe_coupon_id="coup_rec"))

        mock_prov = MagicMock()
        mock_prov.create_subscription = AsyncMock(return_value=MagicMock(
            provider_subscription_id="sub_cs6", status="active", client_secret="s",
            current_period_start=None, current_period_end=None,
        ))

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            await create_subscription(db, mock_user["user_id"], mock_user["email"], tid("p-cs6"), discount_code="RECDISC")

        assert mock_prov.create_subscription.call_args[1]["coupon_id"] == "coup_rec"


class TestCancelSubscription:
    async def test_cancels_at_period_end(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import cancel_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-can")))
        sub = await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-can"),
            stripe_subscription_id="sub_can", status="active",
        ))

        mock_prov = MagicMock()
        mock_prov.cancel_subscription = AsyncMock()

        with patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_prov):
            result = await cancel_subscription(db, str(sub["id"]), mock_user["user_id"])

        assert result["cancel_at_period_end"] is True
        mock_prov.cancel_subscription.assert_called_once_with("sub_can", at_period_end=True)

    async def test_already_canceled_raises(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import cancel_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-can2")))
        sub = await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-can2"),
            stripe_subscription_id="sub_can2", status="canceled",
        ))

        with pytest.raises(ValueError, match="already canceled"):
            await cancel_subscription(db, str(sub["id"]), mock_user["user_id"])

    async def test_not_found_raises(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import cancel_subscription

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with pytest.raises(ValueError, match="not found"):
            await cancel_subscription(db, tid("nonexistent-id"), mock_user["user_id"])


class TestUpdateSubscriptionFromWebhook:
    async def test_updates_status_and_period(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import update_subscription_from_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-wh")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-wh"),
            stripe_subscription_id="sub_wh", status="active",
        ))

        await update_subscription_from_webhook(db, "sub_wh", "past_due", 1700000000, 1702592000)

        row = (await db.execute(text(
            "SELECT status FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_wh'"
        ))).mappings().first()
        assert row["status"] == "past_due"

    async def test_canceled_sets_canceled_at(self, db, mock_user):
        from modules.ecommerce.services.subscription_service import update_subscription_from_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-wh2")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-wh2"),
            stripe_subscription_id="sub_wh2", status="active",
        ))

        await update_subscription_from_webhook(db, "sub_wh2", "canceled")

        row = (await db.execute(text(
            "SELECT status, canceled_at FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_wh2'"
        ))).mappings().first()
        assert row["status"] == "canceled"
        assert row["canceled_at"] is not None
