"""Stripe test mode utilities — confirm payments without a browser."""

import logging
import os

logger = logging.getLogger(__name__)

_stripe = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe

        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not stripe.api_key:
            raise RuntimeError("STRIPE_SECRET_KEY not set — cannot confirm payments")
        _stripe = stripe
    return _stripe


def confirm_payment_intent(client_secret: str, decline: bool = False) -> dict:
    """Confirm a PaymentIntent using Stripe test payment methods.

    Args:
        client_secret: The client_secret from POST /api/checkout
        decline: If True, use pm_card_declined to simulate failure

    Returns:
        dict with status, payment_intent_id
    """
    stripe = _get_stripe()

    # Extract PaymentIntent ID from client_secret
    # Format: pi_xxxxx_secret_yyyyy
    pi_id = client_secret.split("_secret_")[0]

    payment_method = "pm_card_declined" if decline else "pm_card_visa"

    try:
        pi = stripe.PaymentIntent.confirm(
            pi_id,
            payment_method=payment_method,
        )
        return {
            "payment_intent_id": pi.id,
            "status": pi.status,
            "amount": pi.amount,
            "currency": pi.currency,
        }
    except stripe.error.CardError as e:
        # Expected for declined cards
        return {
            "payment_intent_id": pi_id,
            "status": "failed",
            "error": str(e),
        }
    except Exception as e:
        logger.error("Stripe confirm failed for %s: %s", pi_id, e)
        return {
            "payment_intent_id": pi_id,
            "status": "error",
            "error": str(e),
        }


def cleanup_stripe_test_data() -> dict:
    """List counts of test data in Stripe (informational only).

    Actual deletion must be done manually via Stripe Dashboard:
    Settings → Test Data → Delete all test data
    """
    stripe = _get_stripe()

    counts = {}
    try:
        customers = stripe.Customer.list(limit=1)
        counts["customers"] = customers.get("total_count", "unknown")
    except Exception:
        counts["customers"] = "error"

    try:
        products = stripe.Product.list(limit=1, active=True)
        counts["products"] = products.get("total_count", "unknown")
    except Exception:
        counts["products"] = "error"

    return counts
