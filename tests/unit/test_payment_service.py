"""Unit tests for payment record CRUD operations."""

import pytest
from sqlalchemy import text
from tests.factories import make_order, make_payment_record
from tests.conftest import seed_user, seed_order, seed_payment_record, tid

pytestmark = pytest.mark.unit


class TestCreatePaymentRecord:
    async def test_inserts_row(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(user_id=mock_user["user_id"]))
        record = await payment_service.create_payment_record(
            db, order_id=str(order["id"]), provider="stripe",
            provider_payment_id="pi_ins", amount=2999, currency="USD",
        )
        assert record["provider_payment_id"] == "pi_ins"
        assert record["status"] == "pending"
        assert record["amount"] == 2999

    async def test_stores_method(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(user_id=mock_user["user_id"]))
        record = await payment_service.create_payment_record(
            db, order_id=str(order["id"]), provider="stripe",
            provider_payment_id="pi_m", amount=1000, method="card",
        )
        assert record["method"] == "card"


class TestUpdatePaymentStatus:
    async def test_updates_and_returns(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(user_id=mock_user["user_id"]))
        await seed_payment_record(db, make_payment_record(order_id=str(order["id"]), provider_payment_id="pi_upd"))

        result = await payment_service.update_payment_status(db, "pi_upd", "succeeded")
        assert result["status"] == "succeeded"

    async def test_nonexistent_returns_none(self, db):
        from modules.payments.services import payment_service
        assert await payment_service.update_payment_status(db, "pi_nope", "succeeded") is None


class TestGetPaymentByOrder:
    async def test_returns_record(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(id=tid("o-get"), user_id=mock_user["user_id"]))
        await seed_payment_record(db, make_payment_record(order_id=tid("o-get"), provider_payment_id="pi_get"))

        result = await payment_service.get_payment_by_order(db, tid("o-get"))
        assert result is not None
        assert result["provider_payment_id"] == "pi_get"

    async def test_no_records_returns_none(self, db):
        from modules.payments.services import payment_service
        assert await payment_service.get_payment_by_order(db, tid("nonexistent")) is None


class TestGetPaymentByProviderId:
    async def test_returns_match(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(user_id=mock_user["user_id"]))
        await seed_payment_record(db, make_payment_record(order_id=str(order["id"]), provider_payment_id="pi_byid"))

        result = await payment_service.get_payment_by_provider_id(db, "pi_byid")
        assert result is not None


class TestCreateRefundRecord:
    async def test_stores_negative_amount(self, db, mock_user):
        from modules.payments.services import payment_service

        await seed_user(db, mock_user["user_id"], mock_user["email"])
        order = await seed_order(db, make_order(user_id=mock_user["user_id"]))
        record = await payment_service.create_refund_record(
            db, order_id=str(order["id"]), provider="stripe",
            provider_refund_id="re_1", amount=5000,
        )
        assert record["amount"] == -5000
        assert record["method"] == "refund"
        assert record["status"] == "refunded"
