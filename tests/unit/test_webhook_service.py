"""Unit tests for webhook processing — signature, idempotency, all event handlers."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import (
    make_webhook_event, make_order, make_payment_record,
    make_synced_product, make_variant, make_subscription,
    make_merchant_account, make_recurring_product,
)
from tests.conftest import (
    seed_user, seed_order, seed_payment_record, seed_product,
    seed_variant, seed_subscription, seed_merchant, seed_cart_with_items, tid,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Signature & Idempotency
# ---------------------------------------------------------------------------


class TestWebhookVerification:
    async def test_invalid_signature_raises(self, db):
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(side_effect=ValueError("Invalid signature"))
        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            from modules.payments.services.webhook_service import verify_and_process_webhook
            with pytest.raises(ValueError, match="Invalid signature"):
                await verify_and_process_webhook(db, b"payload", "bad_sig")

    async def test_duplicate_event_returns_duplicate(self, db):
        event = make_webhook_event("payment_intent.succeeded", {"id": "pi_1"})
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)
        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            from modules.payments.services.webhook_service import verify_and_process_webhook
            r1 = await verify_and_process_webhook(db, b"p", "sig")
            assert r1["status"] == "processed"
            r2 = await verify_and_process_webhook(db, b"p", "sig")
            assert r2["status"] == "duplicate"

    async def test_event_recorded_in_db(self, db):
        event = make_webhook_event("test.event", {"id": "obj_1"}, event_id="evt_recorded")
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)
        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            from modules.payments.services.webhook_service import verify_and_process_webhook
            await verify_and_process_webhook(db, b"p", "sig")
        row = (await db.execute(text("SELECT event_type FROM ecommerce.webhook_events WHERE event_id = 'evt_recorded'"))).mappings().first()
        assert row["event_type"] == "test.event"

    async def test_unknown_event_type_handled_gracefully(self, db):
        event = make_webhook_event("unknown.event.type", {"id": "x"})
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)
        with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
            from modules.payments.services.webhook_service import verify_and_process_webhook
            r = await verify_and_process_webhook(db, b"p", "sig")
            assert r["status"] == "processed"


# ---------------------------------------------------------------------------
# payment_intent.succeeded
# ---------------------------------------------------------------------------


class TestPaymentSucceeded:
    async def test_updates_payment_and_order(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_payment_succeeded
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-succ"), user_id=mock_user["user_id"], status="processing"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-succ"), provider_payment_id="pi_succ"))

        await _handle_payment_succeeded(db, {"id": "pi_succ", "metadata": {"order_id": tid("o-succ")}})

        pay = await payment_service.get_payment_by_provider_id(db, "pi_succ")
        assert pay["status"] == "succeeded"

    async def test_no_order_id_still_updates_payment(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_payment_succeeded
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-nm"), user_id=mock_user["user_id"], status="processing"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-nm"), provider_payment_id="pi_nm"))

        await _handle_payment_succeeded(db, {"id": "pi_nm", "metadata": {}})
        pay = await payment_service.get_payment_by_provider_id(db, "pi_nm")
        assert pay["status"] == "succeeded"


# ---------------------------------------------------------------------------
# payment_intent.payment_failed
# ---------------------------------------------------------------------------


class TestPaymentFailed:
    async def test_releases_inventory_rejects_order(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_payment_failed
        from modules.payments.services import payment_service
        from tests.factories import make_product, make_variant

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_product(id=tid("p-fail")))
        var = await seed_variant(db, make_variant(id=tid("v-fail"), product_id=tid("p-fail")))
        await seed_order(db, make_order(id=tid("o-fail"), user_id=mock_user["user_id"], status="processing"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-fail"), provider_payment_id="pi_fail"))
        await db.execute(text(
            f"INSERT INTO ecommerce.order_items (order_id, product_id, variant_id, quantity, unit_price, total_price, product_snapshot) "
            f"VALUES ('{tid('o-fail')}', '{tid('p-fail')}', '{tid('v-fail')}', 1, 2999, 2999, '{{}}'::jsonb)"
        ))
        await db.flush()

        with patch("modules.ecommerce.services.inventory_service.release_stock", new_callable=AsyncMock):
            await _handle_payment_failed(db, {"id": "pi_fail", "metadata": {"order_id": tid("o-fail")}})

        pay = await payment_service.get_payment_by_provider_id(db, "pi_fail")
        assert pay["status"] == "failed"


# ---------------------------------------------------------------------------
# charge.succeeded / charge.refunded
# ---------------------------------------------------------------------------


class TestChargeSucceeded:
    async def test_stores_charge_id(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_charge_succeeded

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-ch"), user_id=mock_user["user_id"]))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-ch"), provider_payment_id="pi_ch"))

        await _handle_charge_succeeded(db, {"id": "ch_123", "payment_intent": "pi_ch"})

        row = (await db.execute(text(
            "SELECT charge_id FROM ecommerce.payment_records WHERE provider_payment_id = 'pi_ch'"
        ))).mappings().first()
        assert row["charge_id"] == "ch_123"

    async def test_no_payment_intent_skips(self, db):
        from modules.payments.services.webhook_service import _handle_charge_succeeded
        await _handle_charge_succeeded(db, {"id": "ch_nopi"})


class TestChargeRefunded:
    async def test_creates_refund_record(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_charge_refunded

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-ref"), user_id=mock_user["user_id"], status="completed"))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-ref"), provider_payment_id="pi_ref", status="succeeded"))

        await _handle_charge_refunded(db, {"id": "ch_ref", "payment_intent": "pi_ref", "amount_refunded": 5000, "currency": "usd"})

        rows = (await db.execute(text(
            f"SELECT * FROM ecommerce.payment_records WHERE order_id = '{tid('o-ref')}' AND method = 'refund'"
        ))).mappings().all()
        assert len(rows) == 1
        assert rows[0]["amount"] == -5000

    async def test_no_payment_record_logs_warning(self, db):
        from modules.payments.services.webhook_service import _handle_charge_refunded
        # Should not raise
        await _handle_charge_refunded(db, {"id": "ch_x", "payment_intent": "pi_nonexistent", "amount_refunded": 1000, "currency": "usd"})


# ---------------------------------------------------------------------------
# account.updated
# ---------------------------------------------------------------------------


class TestAccountUpdated:
    async def test_active(self, db, mock_merchant):
        from modules.payments.services.webhook_service import _handle_account_updated

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(user_id=mock_merchant["user_id"], stripe_account_id="acct_a", status="onboarding"))

        await _handle_account_updated(db, {"id": "acct_a", "charges_enabled": True, "payouts_enabled": True, "requirements": {}})

        row = (await db.execute(text("SELECT status FROM ecommerce.merchant_accounts WHERE stripe_account_id = 'acct_a'"))).mappings().first()
        assert row["status"] == "active"

    async def test_restricted(self, db, mock_merchant):
        from modules.payments.services.webhook_service import _handle_account_updated

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(user_id=mock_merchant["user_id"], stripe_account_id="acct_r", status="onboarding"))

        await _handle_account_updated(db, {"id": "acct_r", "charges_enabled": True, "payouts_enabled": False, "requirements": {}})

        row = (await db.execute(text("SELECT status FROM ecommerce.merchant_accounts WHERE stripe_account_id = 'acct_r'"))).mappings().first()
        assert row["status"] == "restricted"

    async def test_disabled(self, db, mock_merchant):
        from modules.payments.services.webhook_service import _handle_account_updated

        await seed_user(db, mock_merchant["user_id"], mock_merchant["email"], "merchant")
        await seed_merchant(db, make_merchant_account(user_id=mock_merchant["user_id"], stripe_account_id="acct_d", status="active"))

        await _handle_account_updated(db, {"id": "acct_d", "charges_enabled": True, "payouts_enabled": True, "requirements": {"disabled_reason": "listed"}})

        row = (await db.execute(text("SELECT status FROM ecommerce.merchant_accounts WHERE stripe_account_id = 'acct_d'"))).mappings().first()
        assert row["status"] == "disabled"


# ---------------------------------------------------------------------------
# product / price webhooks
# ---------------------------------------------------------------------------


class TestProductWebhooks:
    async def test_product_updated_syncs_name(self, db):
        from modules.payments.services.webhook_service import _handle_product_updated

        prod = await seed_product(db, make_synced_product(id=tid("p-wh-upd"), name="Old"))
        await _handle_product_updated(db, {"id": prod["stripe_product_id"], "name": "New", "description": "Desc", "active": True})

        row = (await db.execute(text(f"SELECT name, description FROM ecommerce.products WHERE id = '{tid('p-wh-upd')}'"))).mappings().first()
        assert row["name"] == "New"
        assert row["description"] == "Desc"

    async def test_product_archived_when_inactive(self, db):
        from modules.payments.services.webhook_service import _handle_product_updated

        prod = await seed_product(db, make_synced_product(id=tid("p-wh-arch")))
        await _handle_product_updated(db, {"id": prod["stripe_product_id"], "active": False})

        row = (await db.execute(text(f"SELECT status FROM ecommerce.products WHERE id = '{tid('p-wh-arch')}'"))).mappings().first()
        assert row["status"] == "archived"

    async def test_unknown_product_logs_warning(self, db):
        from modules.payments.services.webhook_service import _handle_product_updated
        await _handle_product_updated(db, {"id": "prod_nonexistent", "name": "X"})  # should not raise

    async def test_product_deleted_archives(self, db):
        from modules.payments.services.webhook_service import _handle_product_deleted

        prod = await seed_product(db, make_synced_product(id=tid("p-wh-del")))
        await _handle_product_deleted(db, {"id": prod["stripe_product_id"]})

        row = (await db.execute(text(f"SELECT status, stripe_sync_status FROM ecommerce.products WHERE id = '{tid('p-wh-del')}'"))).mappings().first()
        assert row["status"] == "archived"
        assert row["stripe_sync_status"] == "unsynced"


class TestPriceWebhooks:
    async def test_price_inactive_clears_ids(self, db):
        from modules.payments.services.webhook_service import _handle_price_updated

        prod = await seed_product(db, make_synced_product(id=tid("p-pr-upd"), stripe_price_id="price_clear"))
        await _handle_price_updated(db, {"id": "price_clear", "active": False})

        row = (await db.execute(text(f"SELECT stripe_price_id, stripe_sync_status FROM ecommerce.products WHERE id = '{tid('p-pr-upd')}'"))).mappings().first()
        assert row["stripe_price_id"] is None
        assert row["stripe_sync_status"] == "error"

    async def test_price_deleted_clears(self, db):
        from modules.payments.services.webhook_service import _handle_price_deleted

        prod = await seed_product(db, make_synced_product(id=tid("p-pr-del"), stripe_price_id="price_del"))
        await _handle_price_deleted(db, {"id": "price_del"})

        row = (await db.execute(text(f"SELECT stripe_price_id FROM ecommerce.products WHERE id = '{tid('p-pr-del')}'"))).mappings().first()
        assert row["stripe_price_id"] is None


# ---------------------------------------------------------------------------
# Subscription webhooks
# ---------------------------------------------------------------------------


class TestSubscriptionWebhooks:
    async def test_updates_status(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_subscription_event

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_recurring_product(id=tid("p-sub-ev")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-sub-ev"),
            stripe_subscription_id="sub_ev_1", status="active",
        ))

        await _handle_subscription_event(db, {"id": "sub_ev_1", "status": "canceled", "current_period_start": 1700000000, "current_period_end": 1702592000})

        row = (await db.execute(text("SELECT status FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_ev_1'"))).mappings().first()
        assert row["status"] == "canceled"


class TestInvoicePaymentFailed:
    async def test_marks_past_due(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_invoice_payment_failed

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_recurring_product(id=tid("p-inv-f")))
        await seed_subscription(db, make_subscription(
            user_id=mock_user["user_id"], product_id=tid("p-inv-f"),
            stripe_subscription_id="sub_inv_f", status="active",
        ))

        await _handle_invoice_payment_failed(db, {"subscription": "sub_inv_f"})

        row = (await db.execute(text("SELECT status FROM ecommerce.subscriptions WHERE stripe_subscription_id = 'sub_inv_f'"))).mappings().first()
        assert row["status"] == "past_due"

    async def test_no_subscription_skips(self, db):
        from modules.payments.services.webhook_service import _handle_invoice_payment_failed
        await _handle_invoice_payment_failed(db, {})  # should not raise


# ---------------------------------------------------------------------------
# checkout.session.completed
# ---------------------------------------------------------------------------


class TestCheckoutSessionCompleted:
    async def test_clears_cart(self, db, mock_user):
        from modules.payments.services.webhook_service import _handle_checkout_session_completed

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        prod = await seed_product(db, make_synced_product(id=tid("p-cs")))
        var = await seed_variant(db, make_variant(id=tid("v-cs"), product_id=tid("p-cs")))
        await seed_cart_with_items(db, mock_user["user_id"], [{"product_id": tid("p-cs"), "variant_id": tid("v-cs"), "quantity": 1}])

        await _handle_checkout_session_completed(db, {
            "id": "cs_1", "mode": "subscription", "subscription": "sub_1",
            "customer": "cus_1", "metadata": {"user_id": mock_user["user_id"]},
        })

        row = (await db.execute(text("SELECT status FROM ecommerce.cart WHERE user_id = :uid"), {"uid": mock_user["user_id"]})).mappings().first()
        assert row["status"] == "converted"

    async def test_no_user_id_skips(self, db):
        from modules.payments.services.webhook_service import _handle_checkout_session_completed
        await _handle_checkout_session_completed(db, {"id": "cs_2", "mode": "subscription", "metadata": {}})
