"""Unit tests for discount service — validation, calculation, Stripe sync, admin CRUD."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_discount, make_synced_product, make_variant
from tests.conftest import seed_user, seed_product, seed_variant, seed_discount, tid

pytestmark = pytest.mark.unit


class TestValidateDiscount:
    async def test_valid_code_returns_discount(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="VALID10", min_order_amount=1000))

        result = await validate_discount(db, "VALID10", 5000)
        assert result["code"] == "VALID10"

    async def test_case_insensitive_lookup(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="UPPER"))

        result = await validate_discount(db, "upper", 5000)
        assert result["code"] == "UPPER"

    async def test_invalid_code_raises(self, db):
        from modules.ecommerce.services.discount_service import validate_discount

        with pytest.raises(ValueError, match="Invalid discount code"):
            await validate_discount(db, "NONEXISTENT", 5000)

    async def test_inactive_code_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="INACTIVE"))
        await db.execute(text("UPDATE ecommerce.discount_codes SET active = FALSE WHERE id = :id"), {"id": str(disc["id"])})
        await db.flush()

        with pytest.raises(ValueError, match="no longer active"):
            await validate_discount(db, "INACTIVE", 5000)

    async def test_expired_code_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount
        from datetime import datetime, timezone, timedelta

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await seed_discount(db, make_discount(code="EXPIRED", valid_until=past))

        with pytest.raises(ValueError, match="expired"):
            await validate_discount(db, "EXPIRED", 5000)

    async def test_max_uses_exceeded_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="MAXED", max_uses=1))
        await db.execute(text("UPDATE ecommerce.discount_codes SET uses_count = 1 WHERE id = :id"), {"id": str(disc["id"])})
        await db.flush()

        with pytest.raises(ValueError, match="maximum uses"):
            await validate_discount(db, "MAXED", 5000)

    async def test_min_order_not_met_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="MINORD", min_order_amount=10000))

        with pytest.raises(ValueError, match="Minimum order amount"):
            await validate_discount(db, "MINORD", 5000)


class TestCalculateDiscount:
    def test_percentage_discount(self):
        from modules.ecommerce.services.discount_service import calculate_discount

        result = calculate_discount({"type": "percentage", "value": 10}, 10000)
        assert result == 1000

    def test_fixed_discount(self):
        from modules.ecommerce.services.discount_service import calculate_discount

        result = calculate_discount({"type": "fixed", "value": 500}, 10000)
        assert result == 500

    def test_fixed_discount_capped_at_subtotal(self):
        from modules.ecommerce.services.discount_service import calculate_discount

        result = calculate_discount({"type": "fixed", "value": 15000}, 10000)
        assert result == 10000

    def test_free_shipping_returns_zero(self):
        from modules.ecommerce.services.discount_service import calculate_discount

        result = calculate_discount({"type": "free_shipping", "value": 0}, 10000)
        assert result == 0

    def test_unknown_type_returns_zero(self):
        from modules.ecommerce.services.discount_service import calculate_discount

        result = calculate_discount({"type": "bogus", "value": 100}, 10000)
        assert result == 0


class TestSyncCouponToStripe:
    async def test_syncs_percentage_coupon(self, db, mock_user):
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="SYNC10", type="percentage", value=10))

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_sync"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_sync"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await _sync_coupon_to_stripe(db, dict(disc))

        assert result["stripe_coupon_id"] == "coup_sync"
        assert result["stripe_promotion_code_id"] == "promo_sync"
        mock_prov.create_coupon.assert_called_once()

    async def test_skips_free_shipping(self, db, mock_user):
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="FREESHIP", type="free_shipping", value=0))

        result = await _sync_coupon_to_stripe(db, dict(disc))
        assert result.get("stripe_coupon_id") is None

    async def test_handles_stripe_error_gracefully(self, db, mock_user):
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="SYNCFAIL", type="percentage", value=10))

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(side_effect=Exception("Stripe error"))

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await _sync_coupon_to_stripe(db, dict(disc))

        # Should not raise, just log the error
        assert result.get("stripe_coupon_id") is None


class TestDeleteStripeCoupon:
    async def test_deletes_existing_coupon(self):
        from modules.ecommerce.services.discount_service import _delete_stripe_coupon

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock()

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            await _delete_stripe_coupon({"stripe_coupon_id": "coup_del"})

        mock_prov.delete_coupon.assert_called_once_with("coup_del")

    async def test_skips_when_no_coupon_id(self):
        from modules.ecommerce.services.discount_service import _delete_stripe_coupon

        await _delete_stripe_coupon({})  # should not raise

    async def test_handles_stripe_error_gracefully(self):
        from modules.ecommerce.services.discount_service import _delete_stripe_coupon

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock(side_effect=Exception("Stripe down"))

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            await _delete_stripe_coupon({"stripe_coupon_id": "coup_err"})
        # Should not raise


class TestAdminCRUD:
    async def test_create_discount_syncs_to_stripe(self, db, mock_user):
        from modules.ecommerce.services.discount_service import create_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_new"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_new"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await create_discount(db, {
                "code": "newdisc",
                "type": "percentage",
                "value": 15,
            })

        assert result["code"] == "NEWDISC"  # uppercased
        assert result["stripe_coupon_id"] == "coup_new"

    async def test_deactivate_deletes_stripe_coupon(self, db, mock_user):
        from modules.ecommerce.services.discount_service import deactivate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="DEACT", stripe_coupon_id="coup_deact"))

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock()

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            await deactivate_discount(db, str(disc["id"]))

        row = (await db.execute(text("SELECT active FROM ecommerce.discount_codes WHERE id = :id"), {"id": str(disc["id"])})).mappings().first()
        assert row["active"] is False
        mock_prov.delete_coupon.assert_called_once_with("coup_deact")

    async def test_deactivate_nonexistent_raises(self, db):
        from modules.ecommerce.services.discount_service import deactivate_discount

        with pytest.raises(ValueError, match="not found"):
            await deactivate_discount(db, tid("nonexistent-id"))

    async def test_increment_uses(self, db, mock_user):
        from modules.ecommerce.services.discount_service import increment_uses

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="INCR"))

        await increment_uses(db, str(disc["id"]))

        row = (await db.execute(text("SELECT uses_count FROM ecommerce.discount_codes WHERE id = :id"), {"id": str(disc["id"])})).mappings().first()
        assert row["uses_count"] == 1
