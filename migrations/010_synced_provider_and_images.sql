-- Migration 010: Add synced_provider to products and storage_path to product_images
-- Depends on: 009_stripe_catalog_sync.sql

-- UP

-- Track which payment provider a product is synced with
ALTER TABLE ecommerce.products
    ADD COLUMN IF NOT EXISTS synced_provider VARCHAR(50);

-- Track local file storage path for uploaded images
ALTER TABLE ecommerce.product_images
    ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500);

-- DOWN
ALTER TABLE ecommerce.product_images DROP COLUMN IF EXISTS storage_path;
ALTER TABLE ecommerce.products DROP COLUMN IF EXISTS synced_provider;
