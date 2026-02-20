"""Unit tests for subscription checkout session creation."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_recurring_product, make_variant, make_discount, make_stripe_customer
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, seed_cart_with_items, seed_stripe_customer, tid

pytestmark = pytest.mark.unit

M = "modules.payments.services.subscription_checkout_service"


class TestCreateSubscriptionCheckoutSession:
    async def test_builds_line_items_from_variant_price(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc1"), stripe_price_id="price_prod"))
        await seed_variant(db, make_variant(id=tid("v-sc1"), product_id=tid("p-sc1"), stripe_price_id="price_var"))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc1"), "variant_id": tid("v-sc1"), "quantity": 2}])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_sc1")

        mock_prov = MagicMock()
        mock_prov.create_checkout_session = AsyncMock(return_value={"session_id": "cs_1", "url": "https://stripe.com/pay"})

        with patch(f"{M}.get_payment_provider", return_value=mock_prov):
            result = await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

        kw = mock_prov.create_checkout_session.call_args[1]
        assert kw["line_items"] == [{"price": "price_var", "quantity": 2}]
        assert result["session_url"] == "https://stripe.com/pay"

    async def test_falls_back_to_product_price(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc2"), stripe_price_id="price_prod_only"))
        await seed_variant(db, make_variant(id=tid("v-sc2"), product_id=tid("p-sc2"), stripe_price_id=None))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc2"), "variant_id": tid("v-sc2"), "quantity": 1}])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_sc2")

        mock_prov = MagicMock()
        mock_prov.create_checkout_session = AsyncMock(return_value={"session_id": "cs_2", "url": "url"})

        with patch(f"{M}.get_payment_provider", return_value=mock_prov):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

        assert mock_prov.create_checkout_session.call_args[1]["line_items"] == [{"price": "price_prod_only", "quantity": 1}]

    async def test_creates_customer_if_missing(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc3"), stripe_price_id="price_3"))
        await seed_variant(db, make_variant(id=tid("v-sc3"), product_id=tid("p-sc3"), stripe_price_id="price_v3"))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc3"), "variant_id": tid("v-sc3"), "quantity": 1}])

        mock_main = MagicMock()
        mock_main.create_checkout_session = AsyncMock(return_value={"session_id": "cs_3", "url": "u"})
        mock_cust = MagicMock()
        mock_cust.create_customer = AsyncMock(return_value=MagicMock(provider_customer_id="cus_new"))

        with patch(f"{M}.get_payment_provider", return_value=mock_main), \
             patch("modules.ecommerce.services.subscription_service.get_payment_provider", return_value=mock_cust):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

        mock_cust.create_customer.assert_called_once()

    async def test_empty_cart_raises(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await db.execute(text("INSERT INTO ecommerce.cart (user_id, status) VALUES (:uid, 'active')"), {"uid": mock_user["user_id"]})
        await db.flush()

        with pytest.raises(ValueError, match="Cart is empty"):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

    async def test_no_cart_raises(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with pytest.raises(ValueError, match="No active cart"):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

    async def test_unsynced_product_raises(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc-ns"), stripe_price_id=None, stripe_sync_status="unsynced"))
        await seed_variant(db, make_variant(id=tid("v-sc-ns"), product_id=tid("p-sc-ns"), stripe_price_id=None))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc-ns"), "variant_id": tid("v-sc-ns"), "quantity": 1}])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_ns")

        with pytest.raises(ValueError, match="not synced to Stripe"):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

    async def test_discount_passes_coupon_to_session(self, db, mock_user):
        """Bug B4 fix: coupon is now forwarded to Stripe Checkout Session."""
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc-dc"), stripe_price_id="price_dc"))
        await seed_variant(db, make_variant(id=tid("v-sc-dc"), product_id=tid("p-sc-dc"), stripe_price_id="price_vdc"))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc-dc"), "variant_id": tid("v-sc-dc"), "quantity": 1}])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_dc")
        await seed_discount(db, make_discount(code="SUBDISC", stripe_coupon_id="coup_stripe_1"))

        mock_prov = MagicMock()
        mock_prov.create_checkout_session = AsyncMock(return_value={"session_id": "cs_dc", "url": "u"})

        with patch(f"{M}.get_payment_provider", return_value=mock_prov):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"], discount_code="SUBDISC")

        assert mock_prov.create_checkout_session.call_args[1]["discounts"] == [{"coupon": "coup_stripe_1"}]

    async def test_sets_correct_urls(self, db, mock_user):
        from modules.payments.services.subscription_checkout_service import create_subscription_checkout_session

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-sc-url"), stripe_price_id="price_url"))
        await seed_variant(db, make_variant(id=tid("v-sc-url"), product_id=tid("p-sc-url"), stripe_price_id="price_vurl"))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-sc-url"), "variant_id": tid("v-sc-url"), "quantity": 1}])
        await seed_stripe_customer(db, mock_user["user_id"], "cus_url")

        mock_prov = MagicMock()
        mock_prov.create_checkout_session = AsyncMock(return_value={"session_id": "cs_u", "url": "u"})

        with patch(f"{M}.get_payment_provider", return_value=mock_prov):
            await create_subscription_checkout_session(db, mock_user["user_id"], mock_user["email"])

        kw = mock_prov.create_checkout_session.call_args[1]
        assert "checkout=success" in kw["success_url"]
        assert "canceled=1" in kw["cancel_url"]
