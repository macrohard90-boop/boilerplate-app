-- Migration 009: Add Stripe catalog sync columns to products and variants
-- Depends on: 002_ecommerce_schema.sql
-- Enables syncing local products/variants to Stripe Products + Prices API

-- UP

-- Products: Stripe product/price IDs and sync status
ALTER TABLE ecommerce.products
    ADD COLUMN stripe_product_id VARCHAR(255),
    ADD COLUMN stripe_price_id VARCHAR(255),
    ADD COLUMN stripe_sync_status VARCHAR(20) NOT NULL DEFAULT 'unsynced'
        CHECK (stripe_sync_status IN ('unsynced', 'synced', 'error')),
    ADD COLUMN stripe_sync_error TEXT;

CREATE INDEX idx_products_stripe_product_id ON ecommerce.products(stripe_product_id);
CREATE INDEX idx_products_stripe_sync_status ON ecommerce.products(stripe_sync_status);

-- Variants: Stripe price ID and sync status
ALTER TABLE ecommerce.product_variants
    ADD COLUMN stripe_price_id VARCHAR(255),
    ADD COLUMN stripe_sync_status VARCHAR(20) NOT NULL DEFAULT 'unsynced'
        CHECK (stripe_sync_status IN ('unsynced', 'synced', 'error')),
    ADD COLUMN stripe_sync_error TEXT;

CREATE INDEX idx_product_variants_stripe_price_id ON ecommerce.product_variants(stripe_price_id);

-- DOWN
DROP INDEX IF EXISTS ecommerce.idx_product_variants_stripe_price_id;
DROP INDEX IF EXISTS ecommerce.idx_products_stripe_sync_status;
DROP INDEX IF EXISTS ecommerce.idx_products_stripe_product_id;

ALTER TABLE ecommerce.product_variants
    DROP COLUMN IF EXISTS stripe_price_id,
    DROP COLUMN IF EXISTS stripe_sync_status,
    DROP COLUMN IF EXISTS stripe_sync_error;

ALTER TABLE ecommerce.products
    DROP COLUMN IF EXISTS stripe_product_id,
    DROP COLUMN IF EXISTS stripe_price_id,
    DROP COLUMN IF EXISTS stripe_sync_status,
    DROP COLUMN IF EXISTS stripe_sync_error;
