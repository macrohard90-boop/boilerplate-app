"""Unit tests for order reaper — stale order cleanup."""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_order, make_payment_record, make_product, make_variant
from tests.conftest import seed_user, seed_order, seed_payment_record, seed_product, seed_variant, tid

pytestmark = pytest.mark.unit


def _make_session_factory(db):
    """Create a mock session factory that yields our test db session."""
    def factory():
        @asynccontextmanager
        async def _ctx():
            yield db
        return _ctx()
    return factory


class TestReapStaleOrders:
    @pytest.mark.xfail(reason="BUG: reaper uses status='expired' which violates orders_status_check constraint (valid: pending/processing/accepted/completed/rejected/refunded)")
    async def test_expires_stale_orders_and_releases_inventory(self, db, mock_user):
        """Orders stuck in 'processing' beyond timeout get expired."""
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        product = await seed_product(db, make_product(id=tid("p-reap")))
        variant = await seed_variant(db, make_variant(id=tid("v-reap"), product_id=tid("p-reap"), stock_quantity=10))

        # Create an order that's been processing for a long time
        await db.execute(text(
            "INSERT INTO ecommerce.orders (id, user_id, order_number, status, subtotal, total, currency, created_at) "
            f"VALUES ('{tid('ord-stale')}', :uid, 'ORD-STALE', 'processing', 2999, 2999, 'USD', NOW() - INTERVAL '2 hours')"
        ), {"uid": mock_user["user_id"]})
        await db.execute(text(
            f"INSERT INTO ecommerce.order_items (order_id, product_id, variant_id, quantity, unit_price, total_price, product_snapshot) "
            f"VALUES ('{tid('ord-stale')}', '{tid('p-reap')}', '{tid('v-reap')}', 1, 2999, 2999, '{{}}'::jsonb)"
        ))
        await db.execute(text(
            "INSERT INTO ecommerce.payment_records (order_id, provider, provider_payment_id, status, amount, currency) "
            f"VALUES ('{tid('ord-stale')}', 'stripe', 'pi_stale', 'pending', 2999, 'USD')"
        ))
        await db.flush()

        from modules.payments.services.order_reaper import reap_stale_orders

        mock_provider = MagicMock()
        mock_provider.cancel_payment = AsyncMock()

        with patch("modules.payments.services.order_reaper.get_session_factory", return_value=_make_session_factory(db)), \
             patch("modules.payments.services.order_reaper.settings") as mock_settings, \
             patch("modules.ecommerce.services.inventory_service.release_stock", new_callable=AsyncMock) as mock_release, \
             patch("modules.payments.adapters.get_payment_provider", return_value=mock_provider):
            mock_settings.checkout_timeout = 60  # 60 min timeout
            count = await reap_stale_orders()

        assert count == 1

        # Verify order is now expired
        row = (await db.execute(text(f"SELECT status FROM ecommerce.orders WHERE id = '{tid('ord-stale')}'"))).mappings().first()
        assert row["status"] == "expired"

        # Verify payment record is expired
        pay_row = (await db.execute(text(f"SELECT status FROM ecommerce.payment_records WHERE order_id = '{tid('ord-stale')}'"))).mappings().first()
        assert pay_row["status"] == "expired"

    async def test_no_stale_orders_returns_zero(self, db):
        """When no stale orders exist, returns 0."""
        from modules.payments.services.order_reaper import reap_stale_orders

        with patch("modules.payments.services.order_reaper.get_session_factory", return_value=_make_session_factory(db)), \
             patch("modules.payments.services.order_reaper.settings") as mock_settings:
            mock_settings.checkout_timeout = 60
            count = await reap_stale_orders()

        assert count == 0

    @pytest.mark.xfail(reason="BUG: reaper uses status='expired' which violates orders_status_check constraint")
    async def test_cancel_payment_failure_continues(self, db, mock_user):
        """If canceling the PaymentIntent fails, the order still gets expired."""
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await db.execute(text(
            "INSERT INTO ecommerce.orders (id, user_id, order_number, status, subtotal, total, currency, created_at) "
            f"VALUES ('{tid('ord-cancel-fail')}', :uid, 'ORD-CF', 'processing', 1000, 1000, 'USD', NOW() - INTERVAL '2 hours')"
        ), {"uid": mock_user["user_id"]})
        await db.execute(text(
            "INSERT INTO ecommerce.payment_records (order_id, provider, provider_payment_id, status, amount, currency) "
            f"VALUES ('{tid('ord-cancel-fail')}', 'stripe', 'pi_cancel_fail', 'pending', 1000, 'USD')"
        ))
        await db.flush()

        from modules.payments.services.order_reaper import reap_stale_orders

        mock_provider = MagicMock()
        mock_provider.cancel_payment = AsyncMock(side_effect=Exception("Already canceled"))

        with patch("modules.payments.services.order_reaper.get_session_factory", return_value=_make_session_factory(db)), \
             patch("modules.payments.services.order_reaper.settings") as mock_settings, \
             patch("modules.payments.adapters.get_payment_provider", return_value=mock_provider):
            mock_settings.checkout_timeout = 60
            count = await reap_stale_orders()

        assert count == 1
        row = (await db.execute(text(f"SELECT status FROM ecommerce.orders WHERE id = '{tid('ord-cancel-fail')}'"))).mappings().first()
        assert row["status"] == "expired"
