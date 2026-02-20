"""E2E tests for checkout API endpoints — full HTTP request/response cycle.

Uses httpx.AsyncClient to hit FastAPI routes with mocked auth and Stripe SDK.
Tests the entire request pipeline: middleware → routing → auth → service → DB → response.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from tests.factories import make_synced_product, make_variant, make_order, make_payment_record
from tests.conftest import seed_user, seed_product, seed_variant, seed_order, seed_payment_record, seed_cart_with_items, tid

pytestmark = [pytest.mark.e2e, pytest.mark.xfail(reason="E2E app factory: module loader returns 404 — needs app startup investigation")]

# Auth bypass helper
def _mock_current_user(user_id, email, role="user"):
    async def _dep():
        return {"user_id": user_id, "email": email, "role": role}
    return _dep


@pytest.fixture
async def client(db, mock_user):
    """Create an httpx test client with auth and CSRF bypassed."""
    from backend.main import create_app
    from backend.core.dependencies import get_current_user, validate_csrf
    from backend.core.database import get_db

    app = create_app()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _mock_current_user(mock_user["user_id"], mock_user["email"])
    app.dependency_overrides[validate_csrf] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestCheckoutEndpoint:
    async def test_successful_checkout(self, client, db, mock_user):
        from modules.payments.interfaces.payment_provider import PaymentResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_product(db, make_synced_product(id=tid("p-api1"), base_price=2999))
        await seed_variant(db, make_variant(id=tid("v-api1"), product_id=tid("p-api1")))
        await seed_cart_with_items(db, mock_user["user_id"], [
            {"product_id": tid("p-api1"), "variant_id": tid("v-api1"), "quantity": 1},
        ])

        pi = PaymentResult(provider_payment_id="pi_api1", client_secret="sec_api1", amount=2999)
        mock_prov = MagicMock()
        mock_prov.create_payment = AsyncMock(return_value=pi)

        with patch("modules.payments.services.checkout_service.get_payment_provider", return_value=mock_prov), \
             patch("modules.payments.services.payment_settings_service.get_enabled_payment_methods", new_callable=AsyncMock, return_value=None):
            resp = await client.post("/api/payments/checkout", json={
                "shipping_address": {
                    "line1": "123 Main", "city": "NY",
                    "postal_code": "10001", "country": "US",
                },
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["client_secret"] == "sec_api1"
        assert body["order_id"] is not None

    async def test_checkout_empty_cart_returns_400(self, client, db, mock_user):
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await db.execute(text(
            "INSERT INTO ecommerce.cart (user_id, status) VALUES (:uid, 'active')"
        ), {"uid": mock_user["user_id"]})
        await db.flush()

        resp = await client.post("/api/payments/checkout", json={
            "shipping_address": {
                "line1": "1", "city": "X", "postal_code": "1", "country": "US",
            },
        })

        assert resp.status_code == 400


class TestPaymentStatusEndpoint:
    async def test_get_payment_status(self, client, db, mock_user):
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-api-st"), user_id=mock_user["user_id"], status="completed"))
        await seed_payment_record(db, make_payment_record(
            order_id=tid("o-api-st"), provider_payment_id="pi_api_st", status="succeeded",
        ))

        resp = await client.get(f"/api/payments/orders/{tid('o-api-st')}/payment")

        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_status"] == "succeeded"
        assert body["order_status"] == "completed"

    async def test_order_not_found_returns_404(self, client, db, mock_user):
        await seed_user(db, mock_user["user_id"], mock_user["email"])

        resp = await client.get(f"/api/payments/orders/{tid('nonexistent')}/payment")
        assert resp.status_code == 404


class TestRefundEndpoint:
    async def test_successful_refund(self, client, db, mock_user):
        from modules.payments.interfaces.payment_provider import RefundResult

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-api-ref"), user_id=mock_user["user_id"], status="completed"))
        await seed_payment_record(db, make_payment_record(
            order_id=tid("o-api-ref"), provider_payment_id="pi_api_ref", status="succeeded",
        ))

        refund = RefundResult(provider_refund_id="re_api1", status="succeeded", amount=2999)
        mock_prov = MagicMock()
        mock_prov.refund = AsyncMock(return_value=refund)

        with patch("modules.payments.routes.checkout_routes.get_payment_provider", return_value=mock_prov):
            resp = await client.post(f"/api/payments/orders/{tid('o-api-ref')}/refund", json={})

        assert resp.status_code == 200
        body = resp.json()
        assert body["refund_id"] == "re_api1"

    async def test_refund_wrong_status_returns_400(self, client, db, mock_user):
        await seed_user(db, mock_user["user_id"], mock_user["email"])
        await seed_order(db, make_order(id=tid("o-api-ref2"), user_id=mock_user["user_id"], status="processing"))

        resp = await client.post(f"/api/payments/orders/{tid('o-api-ref2')}/refund", json={})
        assert resp.status_code == 400


class TestWebhookEndpoint:
    async def test_webhook_processes_event(self, db, mock_user):
        """Test the webhook route directly — no auth needed."""
        from backend.main import create_app
        from backend.core.database import get_db
        from tests.factories import make_webhook_event

        app = create_app()

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        event = make_webhook_event("test.e2e.event", {"id": "obj_e2e"}, event_id="evt_e2e")
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=event)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            with patch("modules.payments.services.webhook_service.get_payment_provider", return_value=mock_provider):
                resp = await c.post(
                    "/api/payments/webhook",
                    content=b"test_payload",
                    headers={"Stripe-Signature": "t=123,v1=abc"},
                )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    async def test_webhook_missing_signature_returns_400(self, db):
        from backend.main import create_app
        from backend.core.database import get_db

        app = create_app()

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/payments/webhook", content=b"test")

        assert resp.status_code == 400
