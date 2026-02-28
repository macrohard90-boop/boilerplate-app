"""Unit tests for discount service — validation, calculation, Stripe sync, admin CRUD."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_discount, make_synced_product, make_variant, make_order
from tests.conftest import (
    seed_user, seed_product, seed_variant, seed_discount,
    seed_discount_product_restriction, tid,
)

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
        assert result["stripe_sync_status"] == "synced"
        assert result["stripe_sync_error"] is None
        mock_prov.create_coupon.assert_called_once()

    async def test_skips_free_shipping(self, db, mock_user):
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="FREESHIP", type="free_shipping", value=0))

        result = await _sync_coupon_to_stripe(db, dict(disc))
        assert result.get("stripe_coupon_id") is None
        assert result["stripe_sync_status"] == "synced"

    async def test_handles_stripe_error_gracefully(self, db, mock_user):
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="SYNCFAIL", type="percentage", value=10))

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(side_effect=Exception("Stripe error"))

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await _sync_coupon_to_stripe(db, dict(disc))

        # Should not raise, records error in sync status
        assert result.get("stripe_coupon_id") is None
        assert result["stripe_sync_status"] == "error"
        assert "Stripe error" in result["stripe_sync_error"]

    async def test_orphan_cleanup_on_promo_code_failure(self, db, mock_user):
        """If coupon creates OK but promo code fails, orphaned coupon is deleted."""
        from modules.ecommerce.services.discount_service import _sync_coupon_to_stripe

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="ORPHAN", type="percentage", value=10))

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_orphan"})
        mock_prov.create_promotion_code = AsyncMock(side_effect=Exception("Promo failed"))
        mock_prov.delete_coupon = AsyncMock()

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await _sync_coupon_to_stripe(db, dict(disc))

        assert result["stripe_sync_status"] == "error"
        assert "Promo failed" in result["stripe_sync_error"]
        # Orphaned coupon should be cleaned up
        mock_prov.delete_coupon.assert_called_once_with("coup_orphan")


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
        assert result["stripe_sync_status"] == "synced"

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

    async def test_update_retries_sync_on_error_state(self, db, mock_user):
        """Updating a coupon with stripe_sync_status='error' retries the sync."""
        from modules.ecommerce.services.discount_service import update_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(
            code="RETRY", type="percentage", value=10,
            stripe_sync_status="error", stripe_sync_error="Previous failure",
        ))

        mock_prov = MagicMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_retry"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_retry"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await update_discount(db, str(disc["id"]), {"active": True})

        assert result["stripe_sync_status"] == "synced"
        assert result["stripe_coupon_id"] == "coup_retry"
        mock_prov.create_coupon.assert_called_once()

    async def test_removing_restriction_triggers_stripe_recreate(self, db, mock_user):
        """Clearing restricted_to_customer_id (set to None) must recreate Stripe coupon."""
        from modules.ecommerce.services.discount_service import update_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(
            code="RMCUST", type="percentage", value=10,
            stripe_coupon_id="coup_rmcust", stripe_promotion_code_id="promo_rmcust",
            stripe_sync_status="synced",
            restricted_to_customer_id=mock_user["user_id"],
        ))

        mock_prov = MagicMock()
        mock_prov.delete_coupon = AsyncMock()
        mock_prov.create_coupon = AsyncMock(return_value={"stripe_coupon_id": "coup_rmcust_new"})
        mock_prov.create_promotion_code = AsyncMock(return_value={"stripe_promotion_code_id": "promo_rmcust_new"})

        with patch("modules.payments.adapters.get_payment_provider", return_value=mock_prov):
            result = await update_discount(db, str(disc["id"]), {"restricted_to_customer_id": None})

        assert result["restricted_to_customer_id"] is None
        assert result["stripe_sync_status"] == "synced"
        mock_prov.delete_coupon.assert_called_once_with("coup_rmcust")
        mock_prov.create_coupon.assert_called_once()

    async def test_clearing_nullable_fields_persists(self, db, mock_user):
        """Setting nullable fields to None must update the DB row."""
        from modules.ecommerce.services.discount_service import update_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        from datetime import timedelta
        disc = await seed_discount(db, make_discount(
            code="CLRNULL", type="percentage", value=10,
            max_uses=50, valid_until=datetime.now(timezone.utc) + timedelta(days=30),
            max_uses_per_customer=3,
        ))

        result = await update_discount(db, str(disc["id"]), {
            "max_uses": None,
            "valid_until": None,
            "max_uses_per_customer": None,
        })

        assert result["max_uses"] is None
        assert result["valid_until"] is None
        assert result["max_uses_per_customer"] is None


class TestRestrictions:
    """Tests for product, customer, first-time, and per-customer usage restrictions."""

    async def test_customer_restricted_wrong_user_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        other_uid = tid("other-user")
        await seed_user(db, other_uid, "other@example.com")
        await seed_discount(db, make_discount(
            code="CUSTONLY", restricted_to_customer_id=other_uid,
        ))

        with pytest.raises(ValueError, match="not available for your account"):
            await validate_discount(
                db, "CUSTONLY", 5000, user_id=mock_user["user_id"],
            )

    async def test_customer_restricted_correct_user_passes(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(
            code="CUSTOK", restricted_to_customer_id=mock_user["user_id"],
        ))

        result = await validate_discount(
            db, "CUSTOK", 5000, user_id=mock_user["user_id"],
        )
        assert result["code"] == "CUSTOK"

    async def test_first_time_only_existing_customer_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="FIRST", first_time_transaction_only=True))

        # Create a completed order for this user
        await db.execute(
            text(
                "INSERT INTO ecommerce.orders "
                "(id, user_id, order_number, status, currency, subtotal, discount_amount, tax_amount, total) "
                "VALUES (:id, :uid, 'ORD-001', 'completed', 'USD', 5000, 0, 0, 5000)"
            ),
            {"id": tid("existing-order"), "uid": mock_user["user_id"]},
        )
        await db.flush()

        with pytest.raises(ValueError, match="first-time purchases"):
            await validate_discount(
                db, "FIRST", 5000, user_id=mock_user["user_id"],
            )

    async def test_first_time_only_new_customer_passes(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="FIRST2", first_time_transaction_only=True))

        result = await validate_discount(
            db, "FIRST2", 5000, user_id=mock_user["user_id"],
        )
        assert result["code"] == "FIRST2"

    async def test_per_customer_max_exceeded_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount, increment_customer_uses

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="PERCUST", max_uses_per_customer=1))

        # Simulate 1 usage
        await increment_customer_uses(db, str(disc["id"]), mock_user["user_id"])
        await db.flush()

        with pytest.raises(ValueError, match="maximum number of times"):
            await validate_discount(
                db, "PERCUST", 5000, user_id=mock_user["user_id"],
            )

    async def test_per_customer_max_within_limit_passes(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_discount(db, make_discount(code="PERCUST2", max_uses_per_customer=3))

        result = await validate_discount(
            db, "PERCUST2", 5000, user_id=mock_user["user_id"],
        )
        assert result["code"] == "PERCUST2"

    async def test_product_restricted_all_match_passes(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("prod-a"), name="Prod A"))
        disc = await seed_discount(db, make_discount(code="PRODOK"))
        await seed_discount_product_restriction(db, str(disc["id"]), str(prod["id"]))

        result = await validate_discount(
            db, "PRODOK", 5000,
            user_id=mock_user["user_id"],
            cart_product_ids=[str(prod["id"])],
        )
        assert result["code"] == "PRODOK"

    async def test_product_restricted_partial_match_raises(self, db, mock_user):
        from modules.ecommerce.services.discount_service import validate_discount

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod_a = await seed_product(db, make_synced_product(id=tid("prod-r1"), name="Prod R1"))
        await seed_discount(db, make_discount(id=tid("disc-restr"), code="PARTMATCH"))
        await seed_discount_product_restriction(db, tid("disc-restr"), str(prod_a["id"]))

        with pytest.raises(ValueError, match="not valid for all items"):
            await validate_discount(
                db, "PARTMATCH", 5000,
                user_id=mock_user["user_id"],
                cart_product_ids=[str(prod_a["id"]), tid("unknown-prod")],
            )

    async def test_increment_customer_uses_upsert(self, db, mock_user):
        from modules.ecommerce.services.discount_service import increment_customer_uses

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        disc = await seed_discount(db, make_discount(code="CUSTINC"))
        did = str(disc["id"])
        uid = mock_user["user_id"]

        # First call — creates row
        await increment_customer_uses(db, did, uid)
        await db.flush()
        row = (await db.execute(
            text("SELECT uses_count FROM ecommerce.discount_customer_uses WHERE discount_code_id = :did AND user_id = :uid"),
            {"did": did, "uid": uid},
        )).mappings().first()
        assert row["uses_count"] == 1

        # Second call — increments
        await increment_customer_uses(db, did, uid)
        await db.flush()
        row2 = (await db.execute(
            text("SELECT uses_count FROM ecommerce.discount_customer_uses WHERE discount_code_id = :did AND user_id = :uid"),
            {"did": did, "uid": uid},
        )).mappings().first()
        assert row2["uses_count"] == 2
