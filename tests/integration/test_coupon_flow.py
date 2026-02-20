"""Integration tests for coupon/discount lifecycle — create, validate, sync, deactivate.

Full service→DB flow with real PostgreSQL. Stripe SDK is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_discount, make_synced_product, make_variant
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, seed_cart_with_items, tid

pytestmark = pytest.mark.integration


class TestCouponCreateAndSync:
    async def test_create_discount_syncs_to_stripe(self, db):
        """Admin creates discount → Stripe coupon + promotion code created."""
        from modules.ecommerce.services.discount_service import create_discount

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_int"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_int"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await create_discount(db, {
                "code": "inttest",
                "type": "percentage",
                "value": 20,
            })

        assert result["code"] == "INTTEST"
        assert result["stripe_coupon_id"] == "coup_int"
        assert result["stripe_promotion_code_id"] == "promo_int"

        # Verify in DB
        row = (await db.execute(text(
            "SELECT stripe_coupon_id, stripe_promotion_code_id "
            "FROM ecommerce.discount_codes WHERE code = 'INTTEST'"
        ))).mappings().first()
        assert row["stripe_coupon_id"] == "coup_int"

    async def test_free_shipping_skips_stripe_sync(self, db):
        """Free shipping discounts don't sync to Stripe."""
        from modules.ecommerce.services.discount_service import create_discount

        result = await create_discount(db, {
            "code": "FREESHIP",
            "type": "free_shipping",
            "value": 0,
        })

        assert result["stripe_coupon_id"] is None


class TestCouponValidation:
    async def test_validate_with_real_cart_subtotal(self, db, mock_user):
        """Bug B3 fix: discount validation uses actual cart subtotal."""
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-cv"), base_price=5000))
        await seed_variant(db, make_variant(id=tid("v-cv"), product_id=tid("p-cv")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-cv"), "variant_id": tid("v-cv"), "quantity": 2},
        ])
        await seed_discount(db, make_discount(code="VALID", min_order_amount=5000))

        # Cart total is 10000 (2 × 5000) — above min of 5000
        await _apply_discount_to_cart(db, mock_user["user_id"], "VALID")

        cart = (await db.execute(text(
            "SELECT discount_code_id FROM ecommerce.cart WHERE user_id = :uid AND status = 'active'"
        ), {"uid": mock_user["user_id"]})).mappings().first()
        assert cart["discount_code_id"] is not None

    async def test_min_order_not_met_with_real_subtotal(self, db, mock_user):
        """Cart subtotal below min_order_amount correctly rejects."""
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-cv2"), base_price=500))
        await seed_variant(db, make_variant(id=tid("v-cv2"), product_id=tid("p-cv2")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-cv2"), "variant_id": tid("v-cv2"), "quantity": 1},
        ])
        await seed_discount(db, make_discount(code="BIGMIN2", min_order_amount=10000))

        with pytest.raises(ValueError, match="Minimum order amount"):
            await _apply_discount_to_cart(db, mock_user["user_id"], "BIGMIN2")

    async def test_recurring_only_coupon_rejected_at_checkout(self, db, mock_user):
        """Recurring-only coupons blocked during one-time checkout."""
        from modules.payments.services.checkout_service import _apply_discount_to_cart

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-cv3"), base_price=5000))
        await seed_variant(db, make_variant(id=tid("v-cv3"), product_id=tid("p-cv3")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-cv3"), "variant_id": tid("v-cv3"), "quantity": 1},
        ])
        await seed_discount(db, make_discount(code="RECURR", applies_to="recurring"))

        with pytest.raises(ValueError, match="recurring subscriptions"):
            await _apply_discount_to_cart(db, mock_user["user_id"], "RECURR")


class TestCouponDeactivation:
    async def test_deactivate_deletes_stripe_coupon(self, db):
        """Deactivating a discount deletes the Stripe coupon."""
        from modules.ecommerce.services.discount_service import deactivate_discount

        disc = await seed_discount(db, make_discount(code="DEACT_INT", stripe_coupon_id="coup_deact_int"))

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock()

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            await deactivate_discount(db, str(disc["id"]))

        row = (await db.execute(text(
            "SELECT active FROM ecommerce.discount_codes WHERE id = :id"
        ), {"id": str(disc["id"])})).mappings().first()
        assert row["active"] is False
        mock_prov.delete_coupon.assert_called_once_with("coup_deact_int")


class TestCouponUpdate:
    async def test_value_change_recreates_stripe_coupon(self, db):
        """Changing discount value deletes old coupon and creates new one."""
        from modules.ecommerce.services.discount_service import update_discount

        disc = await seed_discount(db, make_discount(
            code="UPD_INT", type="percentage", value=10, stripe_coupon_id="coup_old",
        ))

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_new_int"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_new_int"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await update_discount(db, str(disc["id"]), {"value": 25})

        assert result["value"] == 25
        mock_prov.delete_coupon.assert_called_once_with("coup_old")
        mock_prov.create_coupon.assert_called_once()
