"""Unit tests for payment settings service — payment method toggles."""

import pytest
from modules.payments.services import payment_settings_service

pytestmark = pytest.mark.unit


class TestGetEnabledPaymentMethods:
    async def test_returns_none_when_no_setting(self, db):
        result = await payment_settings_service.get_enabled_payment_methods(db)
        assert result is None

    async def test_returns_enabled_methods(self, db):
        await payment_settings_service.upsert_setting(db, "payment_methods", {"card": True, "klarna": True, "paypal": False})
        result = await payment_settings_service.get_enabled_payment_methods(db)
        assert sorted(result) == ["card", "klarna"]

    async def test_returns_none_when_all_disabled(self, db):
        await payment_settings_service.upsert_setting(db, "payment_methods", {"card": False, "klarna": False})
        result = await payment_settings_service.get_enabled_payment_methods(db)
        assert result is None

    async def test_filters_unsupported_methods(self, db):
        await payment_settings_service.upsert_setting(db, "payment_methods", {"card": True, "bitcoin": True})
        result = await payment_settings_service.get_enabled_payment_methods(db)
        assert result == ["card"]


class TestSettingsCRUD:
    async def test_upsert_creates(self, db):
        val = await payment_settings_service.upsert_setting(db, "test_key", {"foo": "bar"})
        assert val == {"foo": "bar"}

    async def test_upsert_updates(self, db):
        await payment_settings_service.upsert_setting(db, "test_k2", {"a": 1})
        await payment_settings_service.upsert_setting(db, "test_k2", {"a": 2})
        result = await payment_settings_service.get_setting(db, "test_k2")
        assert result["a"] == 2

    async def test_delete_removes(self, db):
        await payment_settings_service.upsert_setting(db, "del_me", {"x": 1})
        await payment_settings_service.delete_setting(db, "del_me")
        assert await payment_settings_service.get_setting(db, "del_me") is None

    async def test_get_nonexistent_returns_none(self, db):
        assert await payment_settings_service.get_setting(db, "nope") is None
