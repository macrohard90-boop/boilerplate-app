"""Test data factories for generating consistent test objects.

Each factory returns a plain dict with sensible defaults.
Pass keyword overrides to customize any field.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Domain object factories
# ---------------------------------------------------------------------------


def make_user(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "email": "user@test.com",
        "role": "customer",
    }
    return {**defaults, **overrides}


def make_product(**overrides) -> dict:
    _name = overrides.get("name", "Test Product")
    defaults = {
        "id": str(uuid.uuid4()),
        "name": _name,
        "slug": overrides.pop("slug", _name.lower().replace(" ", "-")),
        "description": "A test product",
        "sku": f"TST-{uuid.uuid4().hex[:6].upper()}",
        "base_price": 2999,
        "currency": "USD",
        "type": "physical",
        "status": "active",
        "pricing_type": "one_time",
        "stripe_product_id": None,
        "stripe_price_id": None,
        "stripe_sync_status": "unsynced",
        "stripe_sync_error": None,
        "synced_provider": None,
        "recurring_interval": None,
        "recurring_interval_count": 1,
        "trial_period_days": None,
    }
    return {**defaults, **overrides}


def make_synced_product(**overrides) -> dict:
    """Product that's already synced to Stripe."""
    defaults = {
        "stripe_product_id": f"prod_{uuid.uuid4().hex[:14]}",
        "stripe_price_id": f"price_{uuid.uuid4().hex[:14]}",
        "stripe_sync_status": "synced",
        "synced_provider": "stripe",
    }
    return make_product(**{**defaults, **overrides})


def make_recurring_product(**overrides) -> dict:
    """Recurring subscription product, synced to Stripe."""
    defaults = {
        "pricing_type": "recurring",
        "recurring_interval": "month",
        "recurring_interval_count": 1,
    }
    return make_synced_product(**{**defaults, **overrides})


def make_variant(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "name": "Default",
        "sku": f"VAR-{uuid.uuid4().hex[:6].upper()}",
        "price_override": None,
        "stock_quantity": 100,
        "stripe_price_id": None,
        "stripe_sync_status": "unsynced",
        "stripe_sync_error": None,
    }
    return {**defaults, **overrides}


def make_order(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "order_number": f"ORD-{uuid.uuid4().hex[:8].upper()}",
        "status": "pending",
        "subtotal": 2999,
        "discount_amount": 0,
        "tax_amount": 0,
        "total": 2999,
        "currency": "USD",
    }
    return {**defaults, **overrides}


def make_payment_record(**overrides) -> dict:
    defaults = {
        "order_id": str(uuid.uuid4()),
        "provider": "stripe",
        "provider_payment_id": f"pi_{uuid.uuid4().hex[:24]}",
        "status": "pending",
        "amount": 2999,
        "currency": "USD",
        "method": None,
        "charge_id": None,
    }
    return {**defaults, **overrides}


def make_discount(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "code": f"TEST{uuid.uuid4().hex[:4].upper()}",
        "type": "percentage",
        "value": 10,
        "currency": "USD",
        "min_order_amount": 0,
        "max_uses": None,
        "uses_count": 0,
        "active": True,
        "valid_from": datetime.now(timezone.utc),
        "valid_until": None,
        "applies_to": "all",
        "stripe_coupon_id": None,
        "stripe_promotion_code_id": None,
        "stripe_duration": "once",
        "stripe_duration_in_months": None,
        "stripe_sync_status": "unsynced",
        "stripe_sync_error": None,
        "restricted_to_customer_id": None,
        "first_time_transaction_only": False,
        "max_uses_per_customer": None,
    }
    return {**defaults, **overrides}


def make_cart(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "status": "active",
        "discount_code_id": None,
    }
    return {**defaults, **overrides}


def make_cart_item(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "cart_id": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "variant_id": str(uuid.uuid4()),
        "quantity": 1,
    }
    return {**defaults, **overrides}


def make_subscription(**overrides) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "variant_id": None,
        "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:14]}",
        "stripe_customer_id": f"cus_{uuid.uuid4().hex[:14]}",
        "status": "active",
        "current_period_start": datetime.now(timezone.utc),
        "current_period_end": datetime.now(timezone.utc),
        "trial_start": None,
        "trial_end": None,
        "cancel_at_period_end": False,
        "canceled_at": None,
        "discount_code_id": None,
    }
    return {**defaults, **overrides}


def make_merchant_account(**overrides) -> dict:
    defaults = {
        "user_id": str(uuid.uuid4()),
        "stripe_account_id": f"acct_{uuid.uuid4().hex[:14]}",
        "status": "onboarding",
        "charges_enabled": False,
        "payouts_enabled": False,
        "business_name": "Test Business",
    }
    return {**defaults, **overrides}


# ---------------------------------------------------------------------------
# Stripe API response mock factories
# ---------------------------------------------------------------------------


def make_stripe_payment_intent(**overrides):
    pi = MagicMock()
    pi.id = overrides.get("id", f"pi_{uuid.uuid4().hex[:24]}")
    pi.client_secret = overrides.get(
        "client_secret", f"pi_{uuid.uuid4().hex[:24]}_secret_test"
    )
    pi.status = overrides.get("status", "requires_payment_method")
    pi.amount = overrides.get("amount", 2999)
    pi.currency = overrides.get("currency", "usd")
    pi.metadata = overrides.get("metadata", {})
    return pi


def make_stripe_customer(**overrides):
    c = MagicMock()
    c.id = overrides.get("id", f"cus_{uuid.uuid4().hex[:14]}")
    c.email = overrides.get("email", "test@example.com")
    return c


def make_stripe_subscription(**overrides):
    sub = MagicMock()
    sub.id = overrides.get("id", f"sub_{uuid.uuid4().hex[:14]}")
    sub.status = overrides.get("status", "incomplete")
    sub.latest_invoice = MagicMock()
    sub.latest_invoice.confirmation_secret = MagicMock()
    sub.latest_invoice.confirmation_secret.client_secret = overrides.get(
        "client_secret", "seti_secret_test"
    )
    # Period info lives in items.data[0] in modern Stripe API
    period_start = overrides.get("period_start", 1700000000)
    period_end = overrides.get("period_end", 1702592000)
    item_data = {
        "current_period_start": period_start,
        "current_period_end": period_end,
    }
    item_mock = MagicMock()
    item_mock.get = lambda k, d=None: item_data.get(k, d)
    sub.__getitem__ = lambda self, k: (
        {"items": {"data": [item_mock]}}[k] if k == "items" else None
    )
    sub.metadata = overrides.get("metadata", {})
    return sub


def make_stripe_refund(**overrides):
    r = MagicMock()
    r.id = overrides.get("id", f"re_{uuid.uuid4().hex[:14]}")
    r.status = overrides.get("status", "succeeded")
    r.amount = overrides.get("amount", 2999)
    r.currency = overrides.get("currency", "usd")
    return r


def make_stripe_product(**overrides):
    p = MagicMock()
    p.id = overrides.get("id", f"prod_{uuid.uuid4().hex[:14]}")
    p.name = overrides.get("name", "Test Product")
    p.active = overrides.get("active", True)
    p.metadata = overrides.get("metadata", {})
    return p


def make_stripe_price(**overrides):
    p = MagicMock()
    p.id = overrides.get("id", f"price_{uuid.uuid4().hex[:14]}")
    p.unit_amount = overrides.get("unit_amount", 2999)
    p.currency = overrides.get("currency", "usd")
    p.active = overrides.get("active", True)
    return p


def make_stripe_coupon(**overrides):
    c = MagicMock()
    c.id = overrides.get("id", f"coup_{uuid.uuid4().hex[:10]}")
    return c


def make_stripe_promotion_code(**overrides):
    p = MagicMock()
    p.id = overrides.get("id", f"promo_{uuid.uuid4().hex[:10]}")
    return p


def make_stripe_account(**overrides):
    a = MagicMock()
    a.id = overrides.get("id", f"acct_{uuid.uuid4().hex[:14]}")
    a.charges_enabled = overrides.get("charges_enabled", False)
    a.payouts_enabled = overrides.get("payouts_enabled", False)
    return a


def make_stripe_account_link(**overrides):
    link = MagicMock()
    link.url = overrides.get("url", "https://connect.stripe.com/setup/e/test")
    return link


def make_stripe_checkout_session(**overrides):
    s = MagicMock()
    s.id = overrides.get("id", f"cs_{uuid.uuid4().hex[:14]}")
    s.url = overrides.get("url", "https://checkout.stripe.com/c/pay/test")
    return s


def make_stripe_login_link(**overrides):
    link = MagicMock()
    link.url = overrides.get("url", "https://connect.stripe.com/express/login/test")
    return link


def make_webhook_event(event_type: str, data: dict, **overrides) -> dict:
    """Build a webhook event dict as returned by verify_webhook."""
    return {
        "id": overrides.get("event_id", f"evt_{uuid.uuid4().hex[:14]}"),
        "type": event_type,
        "data": data,
    }
