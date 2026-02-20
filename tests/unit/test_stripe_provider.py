"""Unit tests for StripeProvider adapter — all Stripe SDK calls."""

import pytest
from unittest.mock import patch, MagicMock
from tests.factories import (
    make_stripe_payment_intent, make_stripe_customer, make_stripe_subscription,
    make_stripe_refund, make_stripe_product, make_stripe_price,
    make_stripe_coupon, make_stripe_promotion_code, make_stripe_account,
    make_stripe_account_link, make_stripe_checkout_session, make_stripe_login_link,
)
from modules.payments.adapters.stripe_provider import StripeProvider

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# create_payment
# ---------------------------------------------------------------------------


class TestCreatePayment:
    async def test_automatic_methods_when_none_specified(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            provider = StripeProvider()
            result = await provider.create_payment("order-1", 2999, "USD", "user-1")
            kw = mock_create.call_args[1]
            assert kw["automatic_payment_methods"] == {"enabled": True}
            assert "payment_method_types" not in kw
            assert result.provider_payment_id == pi.id
            assert result.client_secret == pi.client_secret

    async def test_explicit_method_types(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            provider = StripeProvider()
            await provider.create_payment("o1", 5000, "USD", "u1", payment_method_types=["card", "klarna"])
            kw = mock_create.call_args[1]
            assert kw["payment_method_types"] == ["card", "klarna"]
            assert "automatic_payment_methods" not in kw

    async def test_connect_account_with_platform_fee(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            provider = StripeProvider()
            await provider.create_payment("o1", 10000, "USD", "u1", merchant_account_id="acct_test")
            kw = mock_create.call_args[1]
            assert kw["stripe_account"] == "acct_test"
            assert kw["application_fee_amount"] == 1000  # 10%

    async def test_custom_fee_overrides_percentage(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            provider = StripeProvider()
            await provider.create_payment("o1", 10000, "USD", "u1", merchant_account_id="acct_t", fee_amount=500)
            assert mock_create.call_args[1]["application_fee_amount"] == 500

    async def test_zero_fee_omits_application_fee(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            provider = StripeProvider()
            await provider.create_payment("o1", 10000, "USD", "u1", merchant_account_id="acct_t", fee_amount=0)
            assert "application_fee_amount" not in mock_create.call_args[1]

    async def test_status_mapping_pending(self):
        pi = make_stripe_payment_intent(status="requires_payment_method")
        with patch("stripe.PaymentIntent.create", return_value=pi):
            result = await StripeProvider().create_payment("o1", 2999, "USD", "u1")
            assert result.status == "pending"

    async def test_metadata_includes_order_and_customer(self):
        pi = make_stripe_payment_intent()
        with patch("stripe.PaymentIntent.create", return_value=pi) as mock_create:
            await StripeProvider().create_payment("o1", 2999, "USD", "u1", metadata={"order_number": "ORD-1"})
            meta = mock_create.call_args[1]["metadata"]
            assert meta["order_id"] == "o1"
            assert meta["customer_id"] == "u1"
            assert meta["order_number"] == "ORD-1"

    async def test_stripe_error_propagates(self):
        import stripe
        with patch("stripe.PaymentIntent.create", side_effect=stripe.StripeError("Bad")):
            with pytest.raises(stripe.StripeError):
                await StripeProvider().create_payment("o1", 2999, "USD", "u1")


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_succeeded(self):
        pi = make_stripe_payment_intent(status="succeeded")
        with patch("stripe.PaymentIntent.retrieve", return_value=pi):
            r = await StripeProvider().get_status("pi_1")
            assert r.status == "succeeded"

    async def test_processing(self):
        pi = make_stripe_payment_intent(status="processing")
        with patch("stripe.PaymentIntent.retrieve", return_value=pi):
            assert (await StripeProvider().get_status("pi_1")).status == "processing"

    async def test_canceled_maps_to_failed(self):
        pi = make_stripe_payment_intent(status="canceled")
        with patch("stripe.PaymentIntent.retrieve", return_value=pi):
            assert (await StripeProvider().get_status("pi_1")).status == "failed"

    async def test_unknown_maps_to_unknown(self):
        pi = make_stripe_payment_intent(status="weird")
        with patch("stripe.PaymentIntent.retrieve", return_value=pi):
            assert (await StripeProvider().get_status("pi_1")).status == "unknown"


# ---------------------------------------------------------------------------
# cancel / refund
# ---------------------------------------------------------------------------


class TestCancelPayment:
    async def test_calls_stripe(self):
        with patch("stripe.PaymentIntent.cancel") as m:
            await StripeProvider().cancel_payment("pi_1")
            m.assert_called_once_with("pi_1")


class TestRefund:
    async def test_full_refund(self):
        ref = make_stripe_refund(amount=5000)
        with patch("stripe.Refund.create", return_value=ref) as m:
            r = await StripeProvider().refund("pi_1")
            m.assert_called_once_with(payment_intent="pi_1")
            assert r.status == "refunded"
            assert r.amount == 5000

    async def test_partial_refund(self):
        ref = make_stripe_refund(amount=2000)
        with patch("stripe.Refund.create", return_value=ref) as m:
            await StripeProvider().refund("pi_1", amount=2000)
            assert m.call_args[1]["amount"] == 2000

    async def test_with_reason(self):
        ref = make_stripe_refund()
        with patch("stripe.Refund.create", return_value=ref) as m:
            await StripeProvider().refund("pi_1", reason="duplicate")
            assert m.call_args[1]["reason"] == "duplicate"


# ---------------------------------------------------------------------------
# verify_webhook
# ---------------------------------------------------------------------------


class TestVerifyWebhook:
    async def test_valid_signature(self):
        event = {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_1"}}}
        with patch("stripe.Webhook.construct_event", return_value=event):
            r = await StripeProvider().verify_webhook(b"payload", "sig")
            assert r["id"] == "evt_1"
            assert r["data"]["id"] == "pi_1"

    async def test_invalid_signature_raises(self):
        import stripe
        with patch("stripe.Webhook.construct_event", side_effect=stripe.SignatureVerificationError("bad", "h")):
            with pytest.raises(ValueError, match="Invalid signature"):
                await StripeProvider().verify_webhook(b"p", "bad")


# ---------------------------------------------------------------------------
# Customer & Subscription
# ---------------------------------------------------------------------------


class TestCustomer:
    async def test_create(self):
        cust = make_stripe_customer(id="cus_123", email="a@b.com")
        with patch("stripe.Customer.create", return_value=cust):
            r = await StripeProvider().create_customer("a@b.com", metadata={"user_id": "u1"})
            assert r.provider_customer_id == "cus_123"


class TestSubscription:
    async def test_create_basic(self):
        sub = make_stripe_subscription(id="sub_1")
        with patch("stripe.Subscription.create", return_value=sub) as m:
            r = await StripeProvider().create_subscription("cus_1", "price_1")
            kw = m.call_args[1]
            assert kw["customer"] == "cus_1"
            assert kw["items"] == [{"price": "price_1"}]
            assert r.provider_subscription_id == "sub_1"

    async def test_create_with_coupon(self):
        sub = make_stripe_subscription()
        with patch("stripe.Subscription.create", return_value=sub) as m:
            await StripeProvider().create_subscription("cus_1", "price_1", coupon_id="coup_1")
            assert m.call_args[1]["discounts"] == [{"coupon": "coup_1"}]

    async def test_create_with_trial(self):
        sub = make_stripe_subscription()
        with patch("stripe.Subscription.create", return_value=sub) as m:
            await StripeProvider().create_subscription("cus_1", "price_1", trial_period_days=14)
            assert m.call_args[1]["trial_period_days"] == 14

    async def test_cancel_at_period_end(self):
        with patch("stripe.Subscription.modify") as m:
            await StripeProvider().cancel_subscription("sub_1", at_period_end=True)
            m.assert_called_once_with("sub_1", cancel_at_period_end=True)

    async def test_cancel_immediately(self):
        with patch("stripe.Subscription.cancel") as m:
            await StripeProvider().cancel_subscription("sub_1", at_period_end=False)
            m.assert_called_once_with("sub_1")


# ---------------------------------------------------------------------------
# Coupon
# ---------------------------------------------------------------------------


class TestCoupon:
    async def test_percentage(self):
        coup = make_stripe_coupon(id="coup_pct")
        with patch("stripe.Coupon.create", return_value=coup) as m:
            r = await StripeProvider().create_coupon(coupon_type="percentage", value=20, duration="once")
            assert m.call_args[1]["percent_off"] == 20
            assert "amount_off" not in m.call_args[1]
            assert r["stripe_coupon_id"] == "coup_pct"

    async def test_fixed(self):
        coup = make_stripe_coupon()
        with patch("stripe.Coupon.create", return_value=coup) as m:
            await StripeProvider().create_coupon(coupon_type="fixed", value=500, currency="USD", duration="once")
            assert m.call_args[1]["amount_off"] == 500
            assert m.call_args[1]["currency"] == "usd"

    async def test_repeating_duration(self):
        coup = make_stripe_coupon()
        with patch("stripe.Coupon.create", return_value=coup) as m:
            await StripeProvider().create_coupon(coupon_type="percentage", value=10, duration="repeating", duration_in_months=3)
            assert m.call_args[1]["duration_in_months"] == 3

    async def test_delete_success(self):
        with patch("stripe.Coupon.delete") as m:
            await StripeProvider().delete_coupon("coup_1")
            m.assert_called_once_with("coup_1")

    async def test_delete_failure_no_raise(self):
        with patch("stripe.Coupon.delete", side_effect=Exception("gone")):
            await StripeProvider().delete_coupon("coup_bad")  # should not raise


# ---------------------------------------------------------------------------
# Catalog: Product / Price
# ---------------------------------------------------------------------------


class TestCatalog:
    async def test_create_product_with_images_max_8(self):
        prod = make_stripe_product(id="prod_1")
        with patch("stripe.Product.create", return_value=prod) as m:
            await StripeProvider().create_product("Shirt", images=["http://img"] * 10)
            assert len(m.call_args[1]["images"]) == 8

    async def test_create_price_one_time(self):
        price = make_stripe_price(id="price_1")
        with patch("stripe.Price.create", return_value=price) as m:
            r = await StripeProvider().create_price("prod_1", 2999, "USD")
            assert "recurring" not in m.call_args[1]
            assert r.provider_price_id == "price_1"

    async def test_create_price_recurring(self):
        price = make_stripe_price()
        with patch("stripe.Price.create", return_value=price) as m:
            await StripeProvider().create_price("prod_1", 999, "USD", recurring_interval="month")
            assert m.call_args[1]["recurring"] == {"interval": "month", "interval_count": 1}

    async def test_archive_product(self):
        with patch("stripe.Product.modify") as m:
            await StripeProvider().archive_product("prod_1")
            m.assert_called_once_with("prod_1", active=False)


# ---------------------------------------------------------------------------
# Checkout Session
# ---------------------------------------------------------------------------


class TestCheckoutSession:
    async def test_subscription_mode(self):
        sess = make_stripe_checkout_session(id="cs_1", url="https://checkout.stripe.com/t")
        with patch("stripe.checkout.Session.create", return_value=sess) as m:
            r = await StripeProvider().create_checkout_session(
                [{"price": "price_1", "quantity": 1}],
                mode="subscription", customer_id="cus_1",
                success_url="http://ok", cancel_url="http://no",
            )
            kw = m.call_args[1]
            assert kw["mode"] == "subscription"
            assert kw["customer"] == "cus_1"
            assert r["session_id"] == "cs_1"

    async def test_with_discounts(self):
        sess = make_stripe_checkout_session()
        with patch("stripe.checkout.Session.create", return_value=sess) as m:
            await StripeProvider().create_checkout_session(
                [{"price": "p1", "quantity": 1}],
                mode="subscription", success_url="ok", cancel_url="no",
                discounts=[{"coupon": "coup_1"}],
            )
            assert m.call_args[1]["discounts"] == [{"coupon": "coup_1"}]
