-- Migration 015: Coupon restrictions — product targeting, customer limits, first-time-only
-- Extends the discount_codes table with Stripe-parity restriction features.

-- UP

-- 1. New columns on discount_codes
ALTER TABLE ecommerce.discount_codes
    ADD COLUMN restricted_to_customer_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    ADD COLUMN first_time_transaction_only BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN max_uses_per_customer INTEGER;

CREATE INDEX idx_discount_codes_customer_restriction
    ON ecommerce.discount_codes(restricted_to_customer_id)
    WHERE restricted_to_customer_id IS NOT NULL;

-- 2. Junction table: discount → products (product-specific targeting)
CREATE TABLE ecommerce.discount_product_restrictions (
    discount_code_id UUID NOT NULL REFERENCES ecommerce.discount_codes(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    PRIMARY KEY (discount_code_id, product_id)
);

CREATE INDEX idx_discount_product_restrictions_product
    ON ecommerce.discount_product_restrictions(product_id);

-- 3. Per-customer usage tracking table
CREATE TABLE ecommerce.discount_customer_uses (
    discount_code_id UUID NOT NULL REFERENCES ecommerce.discount_codes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    uses_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (discount_code_id, user_id)
);

-- DOWN
DROP TABLE IF EXISTS ecommerce.discount_customer_uses CASCADE;
DROP TABLE IF EXISTS ecommerce.discount_product_restrictions CASCADE;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS max_uses_per_customer;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS first_time_transaction_only;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS restricted_to_customer_id;
