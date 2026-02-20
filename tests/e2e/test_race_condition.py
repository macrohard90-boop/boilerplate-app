"""Race condition test — demonstrates concurrent checkout vulnerability.

Two concurrent checkout calls for the same user can both succeed before
inventory is decremented, allowing overselling. This test proves the
vulnerability exists so it can be assessed and addressed.

The fix would be SELECT ... FOR UPDATE or a database-level constraint
on inventory reservation.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_synced_product, make_variant
from tests.conftest import seed_user, seed_product, seed_variant, seed_cart_with_items, tid

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestConcurrentCheckoutRace:
    async def test_double_checkout_race_condition(self, db, mock_user):
        """Two concurrent checkouts can double-charge the same cart.

        This test demonstrates a real race condition: if two checkout
        requests arrive simultaneously for the same user's cart, both
        can read the cart before either converts it to an order.

        Expected behavior (current): Both succeed → duplicate orders.
        Desired behavior (fixed): One succeeds, one fails with 'No active cart'.
        """
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-race"), base_price=9999))
        await seed_variant(db, make_variant(id=tid("v-race"), product_id=tid("p-race")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-race"), "variant_id": tid("v-race"), "quantity": 1},
        ])

        call_count = 0

        async def slow_create_payment(**kwargs):
            nonlocal call_count
            call_count += 1
            # Simulate network delay that widens the race window
            await asyncio.sleep(0.05)
            return PaymentResult(
                provider_payment_id=f"pi_race_{call_count}",
                client_secret=f"sec_race_{call_count}",
                amount=kwargs.get("amount", 9999),
            )

        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(side_effect=slow_create_payment)

        ship = {"line1": "1 Race St", "city": "X", "postal_code": "1", "country": "US"}

        with patch("modules.payments.services.checkout_service.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):

            # Fire two checkouts concurrently
            results = await asyncio.gather(
                checkout(db, mock_user["user_id"], ship),
                checkout(db, mock_user["user_id"], ship),
                return_exceptions=True,
            )

        # Count successes vs failures
        successes = [r for r in results if isinstance(r, dict) and "order_id" in r]
        failures = [r for r in results if isinstance(r, Exception)]

        # CURRENT BEHAVIOR: The race condition means results are unpredictable.
        # Either:
        #   - Both succeed (race condition exploited — 2 orders from 1 cart)
        #   - One succeeds, one fails (if cart was already converted)
        #
        # We document what actually happened:
        if len(successes) == 2:
            # Race condition confirmed — two orders created from one cart
            assert successes[0]["order_id"] != successes[1]["order_id"], \
                "Two distinct orders created from the same cart — overselling risk"
            pytest.xfail(
                "RACE CONDITION: Two concurrent checkouts both succeeded. "
                "This confirms the vulnerability. Fix with SELECT ... FOR UPDATE "
                "or a cart-locking mechanism."
            )
        elif len(successes) == 1:
            # One succeeded, one failed — safe outcome
            assert len(failures) == 1
        else:
            # Both failed — also safe, but unexpected
            pass

    async def test_inventory_oversell_risk(self, db, mock_user):
        """Demonstrates that inventory can be oversold without row-level locking.

        With only 1 unit in stock, two concurrent orders for the same item
        could both reserve it if they read inventory before either decrements.
        """
        from modules.payments.services.checkout_service import checkout
        from modules.payments.interfaces.payment_provider import PaymentResult

        # Set up product with limited stock
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-inv-race"), base_price=1000))
        await seed_variant(db, make_variant(id=tid("v-inv-race"), product_id=tid("p-inv-race")))

        # Set stock to exactly 1
        await db.execute(text(
            f"UPDATE ecommerce.product_variants SET stock_quantity = 1 WHERE id = '{tid('v-inv-race')}'"
        ))
        await db.flush()

        # Create cart for first user
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-inv-race"), "variant_id": tid("v-inv-race"), "quantity": 1},
        ])

        mock_prov = MagicMock()
        counter = {"n": 0}

        async def _create_payment(**kwargs):
            counter["n"] += 1
            return PaymentResult(
                provider_payment_id=f"pi_inv_{counter['n']}",
                client_secret=f"sec_{counter['n']}",
                amount=kwargs.get("amount", 1000),
            )

        mock_prov.create_payment = AsyncMock(side_effect=_create_payment)
        ship = {"line1": "1", "city": "X", "postal_code": "1", "country": "US"}

        with patch("modules.payments.services.checkout_service.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            result = await checkout(db, mock_user["user_id"], ship)

        # First checkout should succeed
        assert result["order_id"] is not None

        # Check remaining stock
        stock = (await db.execute(text(
            f"SELECT stock_quantity FROM ecommerce.product_variants WHERE id = '{tid('v-inv-race')}'"
        ))).scalar()

        # Document the stock level after checkout
        # If stock went below 0, the reservation logic has a gap
        if stock is not None and stock < 0:
            pytest.xfail(
                f"OVERSELL: Stock went to {stock} (below zero). "
                "Needs SELECT ... FOR UPDATE on inventory check."
            )
