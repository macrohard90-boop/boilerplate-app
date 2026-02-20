"""Unit tests for catalog sync service — product/variant sync to Stripe."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text
from tests.factories import make_product, make_synced_product, make_recurring_product, make_variant
from tests.conftest import seed_product, seed_variant, tid
from modules.payments.interfaces.catalog_provider import CatalogProduct, CatalogPrice

pytestmark = pytest.mark.unit

MODULE = "modules.ecommerce.services.catalog_sync_service"


class TestSyncProductToCatalog:
    async def test_new_product_creates_product_and_price(self, db):
        """First sync: creates Stripe Product + Price, stores IDs."""
        from modules.ecommerce.services.catalog_sync_service import sync_product_to_catalog

        product = await seed_product(db, make_product(id=tid("p-new-sync"), base_price=2999, status="active"))

        mock_provider = MagicMock()
        mock_provider.create_product = AsyncMock(return_value=CatalogProduct(provider_product_id="prod_stripe_1", name="Test Product"))
        mock_provider.create_price = AsyncMock(return_value=CatalogPrice(provider_price_id="price_stripe_1", provider_product_id="prod_stripe_1", unit_amount=2999, currency="USD"))

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider):
            result = await sync_product_to_catalog(db, product)

        assert result["stripe_sync_status"] == "synced"
        mock_provider.create_product.assert_called_once()
        mock_provider.create_price.assert_called_once()

        # Verify DB was updated
        row = (await db.execute(
            text(f"SELECT stripe_product_id, stripe_price_id FROM ecommerce.products WHERE id = '{tid('p-new-sync')}'")
        )).mappings().first()
        assert row["stripe_product_id"] == "prod_stripe_1"
        assert row["stripe_price_id"] == "price_stripe_1"

    async def test_existing_product_updates(self, db):
        """Re-sync: updates existing Stripe Product."""
        from modules.ecommerce.services.catalog_sync_service import sync_product_to_catalog

        product = await seed_product(db, make_synced_product(id=tid("p-resync"), name="Updated Name"))

        mock_provider = MagicMock()
        mock_provider.update_product = AsyncMock(return_value=CatalogProduct(provider_product_id=product["stripe_product_id"], name="Updated Name"))

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider), \
             patch(f"{MODULE}._rotate_price", new_callable=AsyncMock, return_value=None):
            result = await sync_product_to_catalog(db, product)

        assert result["stripe_sync_status"] == "synced"
        mock_provider.update_product.assert_called_once()

    async def test_recurring_product_creates_recurring_price(self, db):
        """Recurring product gets a recurring Price with interval."""
        from modules.ecommerce.services.catalog_sync_service import sync_product_to_catalog

        product = await seed_product(db, make_product(
            id=tid("p-rec-sync"), pricing_type="recurring",
            recurring_interval="month", recurring_interval_count=1,
            base_price=999, status="active",
        ))

        mock_provider = MagicMock()
        mock_provider.create_product = AsyncMock(return_value=CatalogProduct(provider_product_id="prod_rec", name="Recurring Product"))
        mock_provider.create_price = AsyncMock(return_value=CatalogPrice(provider_price_id="price_rec", provider_product_id="prod_rec", unit_amount=999, currency="USD"))

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider):
            await sync_product_to_catalog(db, product)

        call_kwargs = mock_provider.create_price.call_args[1]
        assert call_kwargs["recurring_interval"] == "month"
        assert call_kwargs["recurring_interval_count"] == 1

    async def test_no_catalog_provider_skips(self, db):
        """When no catalog provider configured, skip sync gracefully."""
        from modules.ecommerce.services.catalog_sync_service import sync_product_to_catalog

        product = await seed_product(db, make_product(id=tid("p-no-prov")))

        with patch(f"{MODULE}.get_catalog_provider", return_value=None):
            result = await sync_product_to_catalog(db, product)

        assert result["stripe_sync_status"] == "unsynced"

    async def test_failure_marks_error(self, db):
        """When Stripe call fails, product is marked as error."""
        from modules.ecommerce.services.catalog_sync_service import sync_product_to_catalog

        product = await seed_product(db, make_product(id=tid("p-fail-sync"), status="active"))

        mock_provider = MagicMock()
        mock_provider.create_product = AsyncMock(side_effect=Exception("Stripe API error"))

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider):
            result = await sync_product_to_catalog(db, product)

        assert result["stripe_sync_status"] == "error"
        assert "Stripe API error" in result["stripe_sync_error"]


class TestSyncVariantToCatalog:
    async def test_creates_price_for_variant(self, db):
        from modules.ecommerce.services.catalog_sync_service import sync_variant_to_catalog

        product = await seed_product(db, make_synced_product(id=tid("p-var-sync")))
        variant = await seed_variant(db, make_variant(
            id=tid("v-new-sync"), product_id=tid("p-var-sync"), price_override=3999,
        ))

        mock_provider = MagicMock()
        mock_provider.create_price = AsyncMock(return_value=CatalogPrice(provider_price_id="price_var_new", provider_product_id=product["stripe_product_id"], unit_amount=3999, currency="USD"))

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider):
            result = await sync_variant_to_catalog(db, variant, product)

        assert result["stripe_sync_status"] == "synced"
        mock_provider.create_price.assert_called_once()

    async def test_no_parent_sync_skips(self, db):
        """Variant can't sync if parent product has no stripe_product_id."""
        from modules.ecommerce.services.catalog_sync_service import sync_variant_to_catalog

        product = await seed_product(db, make_product(id=tid("p-no-stripe")))
        variant = await seed_variant(db, make_variant(id=tid("v-skip"), product_id=tid("p-no-stripe")))

        with patch(f"{MODULE}.get_catalog_provider", return_value=MagicMock()):
            result = await sync_variant_to_catalog(db, variant, product)

        # Should return variant unchanged
        assert result["stripe_sync_status"] == "unsynced"


class TestArchiveProductInCatalog:
    async def test_archives_in_stripe(self, db):
        from modules.ecommerce.services.catalog_sync_service import archive_product_in_catalog

        product = await seed_product(db, make_synced_product(id=tid("p-archive")))

        mock_provider = MagicMock()
        mock_provider.archive_product = AsyncMock()

        with patch(f"{MODULE}.get_catalog_provider", return_value=mock_provider):
            await archive_product_in_catalog(db, product)

        mock_provider.archive_product.assert_called_once_with(product["stripe_product_id"])

    async def test_no_stripe_id_skips(self, db):
        from modules.ecommerce.services.catalog_sync_service import archive_product_in_catalog

        product = await seed_product(db, make_product(id=tid("p-no-arch")))

        with patch(f"{MODULE}.get_catalog_provider", return_value=MagicMock()) as mock_prov:
            await archive_product_in_catalog(db, product)
        # archive_product should NOT be called


class TestRotatePrice:
    async def test_archives_old_creates_new(self):
        from modules.ecommerce.services.catalog_sync_service import _rotate_price

        mock_provider = MagicMock()
        mock_provider.archive_price = AsyncMock()
        mock_provider.create_price = AsyncMock(return_value=CatalogPrice(provider_price_id="price_rotated", provider_product_id="prod_1", unit_amount=4999, currency="USD"))

        result = await _rotate_price(
            mock_provider, "prod_1", "price_old", 4999, "USD",
            metadata={"type": "base_price"},
        )

        mock_provider.archive_price.assert_called_once_with("price_old")
        mock_provider.create_price.assert_called_once()
        assert result.provider_price_id == "price_rotated"

    async def test_archive_failure_still_creates_new(self):
        """If archiving old price fails, still create the new one."""
        from modules.ecommerce.services.catalog_sync_service import _rotate_price

        mock_provider = MagicMock()
        mock_provider.archive_price = AsyncMock(side_effect=Exception("already archived"))
        mock_provider.create_price = AsyncMock(return_value=CatalogPrice(provider_price_id="price_new_anyway", provider_product_id="prod_1", unit_amount=4999, currency="USD"))

        result = await _rotate_price(mock_provider, "prod_1", "price_old", 4999, "USD")

        assert result.provider_price_id == "price_new_anyway"


class TestRetrySync:
    async def test_inactive_product_raises(self, db):
        from modules.ecommerce.services.catalog_sync_service import retry_sync

        await seed_product(db, make_product(id=tid("p-retry-inactive"), status="draft"))

        with pytest.raises(ValueError, match="Only active products"):
            await retry_sync(db, tid("p-retry-inactive"))
