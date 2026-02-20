"""Integration tests for full checkout flow — cart → order → payment intent.

Tests the complete checkout pipeline with real DB operations.
Only the Stripe SDK is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_synced_product, make_variant, make_discount
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, seed_cart_with_items, tid

pytestmark = pytest.mark.integration

M = "modules.payments.services.checkout_service"


class TestFullCheckoutFlow:
    async def test_cart_to_order_to_payment(self, db, mock_user):
        """End-to-end: seed cart → checkout → order created + PI created."""
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-int1"), base_price=2999))
        await seed_variant(db, make_variant(id=tid("v-int1"), product_id=tid("p-int1")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-int1"), "variant_id": tid("v-int1"), "quantity": 2},
        ])

        pi = PaymentResult(provider_payment_id="pi_int1", client_secret="sec_int1", amount=5998)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        with patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            result = await checkout(
                db, mock_user["user_id"],
                {"line1": "123 Main", "city": "NY", "postal_code": "10001", "country": "US"},
            )

        assert result["client_secret"] == "sec_int1"
        assert result["order_id"] is not None

        # Verify order exists in DB
        order = (await db.execute(text(
            "SELECT status, total FROM ecommerce.orders WHERE id = :oid"
        ), {"oid": result["order_id"]})).mappings().first()
        assert order["status"] == "processing"

        # Verify payment record created
        pay = (await db.execute(text(
            "SELECT provider_payment_id, status FROM ecommerce.payment_records WHERE order_id = :oid"
        ), {"oid": result["order_id"]})).mappings().first()
        assert pay["provider_payment_id"] == "pi_int1"
        assert pay["status"] == "pending"

        # Verify cart is converted
        cart = (await db.execute(text(
            "SELECT status FROM ecommerce.cart WHERE user_id = :uid"
        ), {"uid": mock_user["user_id"]})).mappings().first()
        assert cart["status"] == "converted"

    async def test_checkout_with_discount_code(self, db, mock_user):
        """Checkout with a valid discount code applies it to the cart."""
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-int2"), base_price=5000))
        await seed_variant(db, make_variant(id=tid("v-int2"), product_id=tid("p-int2")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-int2"), "variant_id": tid("v-int2"), "quantity": 1},
        ])
        await seed_discount(db, make_discount(code="INT10", type="percentage", value=10, min_order_amount=1000))

        pi = PaymentResult(provider_payment_id="pi_int2", client_secret="sec_int2", amount=4500)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        with patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            result = await checkout(
                db, mock_user["user_id"],
                {"line1": "1 St", "city": "X", "postal_code": "1", "country": "US"},
                discount_code="INT10",
            )

        assert result["order_id"] is not None

    async def test_checkout_stores_addresses(self, db, mock_user):
        """Shipping and billing addresses stored on the order."""
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-int3"), base_price=2000))
        await seed_variant(db, make_variant(id=tid("v-int3"), product_id=tid("p-int3")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-int3"), "variant_id": tid("v-int3"), "quantity": 1},
        ])

        pi = PaymentResult(provider_payment_id="pi_int3", client_secret="sec", amount=2000)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        ship = {"line1": "456 Oak", "city": "LA", "postal_code": "90001", "country": "US"}
        bill = {"line1": "789 Elm", "city": "SF", "postal_code": "94102", "country": "US"}

        with patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            result = await checkout(db, mock_user["user_id"], ship, billing_address=bill)

        order = (await db.execute(text(
            "SELECT shipping_address, billing_address FROM ecommerce.orders WHERE id = :oid"
        ), {"oid": result["order_id"]})).mappings().first()
        assert order["shipping_address"]["line1"] == "456 Oak"
        assert order["billing_address"]["line1"] == "789 Elm"

    async def test_stripe_failure_rolls_back_order(self, db, mock_user):
        """When Stripe fails, order is rejected and inventory released."""
        from modules.payments.services.checkout_service import checkout

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-int4"), base_price=3000))
        await seed_variant(db, make_variant(id=tid("v-int4"), product_id=tid("p-int4")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-int4"), "variant_id": tid("v-int4"), "quantity": 1},
        ])

        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(side_effect=Exception("Stripe down"))

        with patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="Payment creation failed"):
                await checkout(
                    db, mock_user["user_id"],
                    {"line1": "1", "city": "X", "postal_code": "1", "country": "US"},
                )

        # Order should exist but be rejected
        orders = (await db.execute(text(
            "SELECT status FROM ecommerce.orders WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"
        ), {"uid": mock_user["user_id"]})).mappings().all()
        assert len(orders) >= 1
        assert orders[0]["status"] == "rejected"


class TestCheckoutWithPaymentMethods:
    async def test_enabled_methods_forwarded(self, db, mock_user):
        """Admin-configured payment methods passed through to Stripe."""
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult
        from modules.payments.services import payment_settings_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-pm"), base_price=1500))
        await seed_variant(db, make_variant(id=tid("v-pm"), product_id=tid("p-pm")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-pm"), "variant_id": tid("v-pm"), "quantity": 1},
        ])

        # Set up payment method toggles
        await payment_settings_service.upsert_setting(db, "payment_methods", {"card": True, "klarna": True, "paypal": False})

        pi = PaymentResult(provider_payment_id="pi_pm", client_secret="sec_pm", amount=1500)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        with patch(f"{M}.get_payment_provider", return_value=mock_prov):
            await checkout(
                db, mock_user["user_id"],
                {"line1": "1", "city": "X", "postal_code": "1", "country": "US"},
            )

        assert sorted(mock_prov.create_payment.call_args[1]["payment_method_types"]) == ["card", "klarna"]
