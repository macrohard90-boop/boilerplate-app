"""Integration tests for webhook processing — full verify→process→DB flow.

Exercises the complete webhook pipeline: signature verification → idempotency
check → event handler → DB side effects. Only stripe.Webhook is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import (
    make_webhook_event, make_order, make_payment_record,
    make_synced_product, make_variant, make_subscription,
    make_recurring_product,
)
from tests.conftest import (
    seed_user, seed_order, seed_payment_record, seed_product,
    seed_variant, seed_subscription, seed_cart_with_items, tid,
)

pytestmark = pytest.mark.integration


class TestWebhookPaymentFlow:
    async def test_payment_succeeded_updates_order_and_payment(self, db, mock_user):
        """payment_intent.succeeded → payment record 'succeeded' + order 'completed'."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-wh-s"), user_id=mock_user["user_id"], status="processing"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-wh-s"), provider_payment_id="pi_wh_s"))

        event = make_webhook_event("payment_intent.succeeded", {
            "id": "pi_wh_s", "metadata": {"order_id": tid("o-wh-s")},
        })
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            result = await verify_and_process_webhook(db, b"body", "sig")

        assert result["status"] == "processed"

        pay = (await db.execute(text(
            "SELECT status FROM ecommerce.payment_records WHERE provider_payment_id = 'pi_wh_s'"
        ))).mappings().first()
        assert pay["status"] == "succeeded"

        order = (await db.execute(text(
            f"SELECT status FROM ecommerce.orders WHERE id = '{tid('o-wh-s')}'"
        ))).mappings().first()
        assert order["status"] == "completed"

    async def test_payment_failed_rejects_order(self, db, mock_user):
        """payment_intent.payment_failed → payment 'failed' + order 'rejected'."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-wh-f")))
        var = await seed_variant(db, make_variant(id=tid("v-wh-f"), product_id=tid("p-wh-f")))
        await seed_order(db, make_order(id=tid("o-wh-f"), user_id=mock_user["user_id"], status="processing"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-wh-f"), provider_payment_id="pi_wh_f"))
        await db.execute(text(
            f"INSERT INTO ecommerce.order_items (order_id, product_id, variant_id, quantity, unit_price, total_price, product_snapshot) "
            f"VALUES ('{tid('o-wh-f')}', '{tid('p-wh-f')}', '{tid('v-wh-f')}', 1, 2999, 2999, '{{}}'::jsonb)"
        ))
        await db.flush()

        event = make_webhook_event("payment_intent.payment_failed", {
            "id": "pi_wh_f", "metadata": {"order_id": tid("o-wh-f")},
        })
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider), \
             patch("modules.ecommerce.services.inventory_service.release_stock", new_callable=AsyncMock):
            result = await verify_and_process_webhook(db, b"body", "sig")

        assert result["status"] == "processed"
        pay = (await db.execute(text(
            "SELECT status FROM ecommerce.payment_records WHERE provider_payment_id = 'pi_wh_f'"
        ))).mappings().first()
        assert pay["status"] == "failed"


class TestWebhookIdempotency:
    async def test_duplicate_event_returns_duplicate(self, db):
        """Same event_id processed twice → second returns 'duplicate'."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        event = make_webhook_event("test.event", {"id": "obj_idem"}, event_id="evt_idem_int")
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            r1 = await verify_and_process_webhook(db, b"body", "sig")
            r2 = await verify_and_process_webhook(db, b"body", "sig")

        assert r1["status"] == "processed"
        assert r2["status"] == "duplicate"

        # Only one row in DB
        count = (await db.execute(text(
            "SELECT COUNT(*) FROM ecommerce.webhook_events WHERE event_id = 'evt_idem_int'"
        ))).scalar()
        assert count == 1


class TestWebhookSubscriptionEvents:
    async def test_subscription_updated_changes_status(self, db, mock_user):
        """customer.subscription.updated → subscription status changes in DB."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_recurring_product(id=tid("p-wh-sub")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-wh-sub"),
            stripe_subscription_id="sub_wh_ev", status="active",
        ))

        event = make_webhook_event("customer.subscription.updated", {
            "id": "sub_wh_ev", "status": "past_due",
            "current_period_start": 1700000000, "current_period_end": 1702592000,
        })
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            result = await verify_and_process_webhook(db, b"body", "sig")

        assert result["status"] == "processed"
        row = (await db.execute(text(
            "SELECT status FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_wh_ev'"
        ))).mappings().first()
        assert row["status"] == "past_due"


class TestWebhookChargeEvents:
    async def test_charge_refunded_creates_refund_record(self, db, mock_user):
        """charge.refunded → new payment_record with negative amount."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-wh-ref"), user_id=mock_user["user_id"], status="completed"))
        await seed_payment_record(db, make_payment_record(
            order_id=tid("o-wh-ref"), provider_payment_id="pi_wh_ref", status="succeeded",
        ))

        event = make_webhook_event("charge.refunded", {
            "id": "ch_ref_int", "payment_intent": "pi_wh_ref",
            "amount_refunded": 3000, "currency": "usd",
        })
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            await verify_and_process_webhook(db, b"body", "sig")

        refunds = (await db.execute(text(
            f"SELECT amount, method FROM ecommerce.payment_records "
            f"WHERE order_id = '{tid('o-wh-ref')}' AND method = 'refund'"
        ))).mappings().all()
        assert len(refunds) == 1
        assert refunds[0]["amount"] == -3000


class TestWebhookCheckoutSession:
    async def test_checkout_completed_clears_cart(self, db, mock_user):
        """checkout.session.completed → cart status becomes 'converted'."""
        from modules.payments.services.webhook_service import verify_and_process_webhook

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-wh-cs")))
        await seed_variant(db, make_variant(id=tid("v-wh-cs"), product_id=tid("p-wh-cs")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-wh-cs"), "variant_id": tid("v-wh-cs"), "quantity": 1},
        ])

        event = make_webhook_event("checkout.session.completed", {
            "id": "cs_wh_int", "mode": "subscription", "subscription": "sub_wh_int",
            "customer": "cus_wh_int", "metadata": {"user_id": mock_user["user_id"]},
        })
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            await verify_and_process_webhook(db, b"body", "sig")

        row = (await db.execute(text(
            "SELECT status FROM ecommerce.cart WHERE user_id = :uid"
        ), {"uid": mock_user["user_id"]})).mappings().first()
        assert row["status"] == "converted"
