"""Unit tests for checkout orchestration — cart to order to payment."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from tests.factories import make_order, make_synced_product, make_variant, make_discount
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, seed_cart_with_items, tid

pytestmark = pytest.mark.unit

M = "modules.payments.services.checkout_service"


class TestCheckout:
    async def test_happy_path_creates_order_and_payment(self, db, mock_user):
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        fake_order = make_order(user_id=mock_user["user_id"], total=2999)
        pi = PaymentResult(provider_payment_id="pi_h", client_secret="sec_h", amount=2999)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with patch(f"{M}.order_service.create_order_from_cart", new_callable=AsyncMock, return_value=fake_order), \
             patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None), \
             patch(f"{M}.payment_service.create_payment_record", new_callable=AsyncMock), \
             patch(f"{M}.order_service.update_order_status", new_callable=AsyncMock):
            result = await checkout(db, mock_user["user_id"], {"line1": "123 Main", "city": "NY", "postal_code": "10001", "country": "US"})

        assert result["client_secret"] == "sec_h"
        assert result["total"] == 2999
        mock_prov.create_payment.assert_called_once()

    async def test_zero_cost_skips_payment(self, db, mock_user):
        from modules.payments.services.checkout_service import checkout

        fake_order = make_order(user_id=mock_user["user_id"], total=0, subtotal=2999, discount_amount=2999)
        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with patch(f"{M}.order_service.create_order_from_cart", new_callable=AsyncMock, return_value=fake_order), \
             patch(f"{M}.order_service.update_order_status", new_callable=AsyncMock) as mock_st:
            result = await checkout(db, mock_user["user_id"], {"line1": "1", "city": "X", "postal_code": "1", "country": "US"})

        assert result["client_secret"] is None
        assert result["total"] == 0
        mock_st.assert_called_once_with(db, str(fake_order["id"]), "completed")

    async def test_stripe_failure_releases_inventory(self, db, mock_user):
        from modules.payments.services.checkout_service import checkout

        fake_order = make_order(user_id=mock_user["user_id"], total=2999)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(side_effect=Exception("Stripe down"))
        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with patch(f"{M}.order_service.create_order_from_cart", new_callable=AsyncMock, return_value=fake_order), \
             patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None), \
             patch(f"{M}._release_order_inventory", new_callable=AsyncMock) as mock_rel, \
             patch(f"{M}.order_service.update_order_status", new_callable=AsyncMock) as mock_st:
            with pytest.raises(ValueError, match="Payment creation failed"):
                await checkout(db, mock_user["user_id"], {"line1": "1", "city": "X", "postal_code": "1", "country": "US"})

        mock_rel.assert_called_once()
        mock_st.assert_called_once_with(db, str(fake_order["id"]), "rejected")

    async def test_explicit_payment_methods_passed(self, db, mock_user):
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        fake_order = make_order(user_id=mock_user["user_id"], total=2999)
        pi = PaymentResult(provider_payment_id="pi_m", client_secret="s", amount=2999)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)
        await seed_user(db, mock_user["user_id"], mock_user["email"])

        with patch(f"{M}.order_service.create_order_from_cart", new_callable=AsyncMock, return_value=fake_order), \
             patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=["card", "klarna"]), \
             patch(f"{M}.payment_service.create_payment_record", new_callable=AsyncMock), \
             patch(f"{M}.order_service.update_order_status", new_callable=AsyncMock):
            await checkout(db, mock_user["user_id"], {"line1": "1", "city": "X", "postal_code": "1", "country": "US"})

        assert mock_prov.create_payment.call_args[1]["payment_method_types"] == ["card", "klarna"]

    async def test_billing_defaults_to_shipping(self, db, mock_user):
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        fake_order = make_order(user_id=mock_user["user_id"], total=2999)
        pi = PaymentResult(provider_payment_id="pi_a", client_secret="s", amount=2999)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)
        await seed_user(db, mock_user["user_id"], mock_user["email"])

        ship = {"line1": "123 Main", "city": "NY", "postal_code": "10001", "country": "US"}
        with patch(f"{M}.order_service.create_order_from_cart", new_callable=AsyncMock, return_value=fake_order), \
             patch(f"{M}.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None), \
             patch(f"{M}.payment_service.create_payment_record", new_callable=AsyncMock), \
             patch(f"{M}.order_service.update_order_status", new_callable=AsyncMock):
            result = await checkout(db, mock_user["user_id"], ship, billing_address=None)
        # Should succeed without error (billing defaults to shipping internally)
        assert result["client_secret"] is not None


class TestApplyDiscountToCart:
    async def test_valid_discount_applied(self, db, mock_user):
        from modules.payments.services.checkout_service import _apply_discount_to_cart
        from sqlalchemy import text

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-d1"), base_price=5000))
        var = await seed_variant(db, make_variant(id=tid("v-d1"), product_id=tid("p-d1")))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-d1"), "variant_id": tid("v-d1"), "quantity": 1}])
        await seed_discount(db, make_discount(code="SAVE10", min_order_amount=1000))

        await _apply_discount_to_cart(db, mock_user["user_id"], "SAVE10")

        cart = (await db.execute(text("SELECT discount_code_id FROM ecommerce.cart WHERE user_id = :uid AND status = 'active'"), {"uid": mock_user["user_id"]})).mappings().first()
        assert cart["discount_code_id"] is not None

    async def test_min_order_not_met_raises(self, db, mock_user):
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-d2"), base_price=500))
        var = await seed_variant(db, make_variant(id=tid("v-d2"), product_id=tid("p-d2")))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-d2"), "variant_id": tid("v-d2"), "quantity": 1}])
        await seed_discount(db, make_discount(code="BIGMIN", min_order_amount=10000))

        with pytest.raises(ValueError, match="Minimum order amount"):
            await _apply_discount_to_cart(db, mock_user["user_id"], "BIGMIN")

    async def test_invalid_code_raises(self, db, mock_user):
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-d3"), base_price=5000))
        var = await seed_variant(db, make_variant(id=tid("v-d3"), product_id=tid("p-d3")))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-d3"), "variant_id": tid("v-d3"), "quantity": 1}])

        with pytest.raises(ValueError, match="Invalid discount code"):
            await _apply_discount_to_cart(db, mock_user["user_id"], "NONEXISTENT")

    async def test_recurring_only_coupon_rejected(self, db, mock_user):
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-d4"), base_price=5000))
        var = await seed_variant(db, make_variant(id=tid("v-d4"), product_id=tid("p-d4")))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-d4"), "variant_id": tid("v-d4"), "quantity": 1}])
        await seed_discount(db, make_discount(code="RECONLY", applies_to="recurring"))

        with pytest.raises(ValueError, match="recurring subscriptions"):
            await _apply_discount_to_cart(db, mock_user["user_id"], "RECONLY")
