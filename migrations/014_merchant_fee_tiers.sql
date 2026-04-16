-- Migration 014: Merchant fee tiers (volume-based platform fees)
-- Replaces the single PLATFORM_FEE_PERCENT env var with a tier system.

-- UP

BEGIN;

-- Global fee tier schedule (default for all merchants)
CREATE TABLE IF NOT EXISTS ecommerce.fee_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    min_volume INT NOT NULL DEFAULT 0,
    max_volume INT,
    fee_percent NUMERIC(5,2) NOT NULL,
    fee_flat INT NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-merchant fee overrides (optional)
CREATE TABLE IF NOT EXISTS ecommerce.merchant_fee_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_account_id UUID NOT NULL REFERENCES ecommerce.merchant_accounts(id) ON DELETE CASCADE,
    fee_percent NUMERIC(5,2) NOT NULL,
    fee_flat INT NOT NULL DEFAULT 0,
    min_volume INT NOT NULL DEFAULT 0,
    max_volume INT,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(merchant_account_id, sort_order)
);

-- Track aggregate merchant sales volume for tier calculation
ALTER TABLE ecommerce.merchant_accounts
    ADD COLUMN IF NOT EXISTS total_sales_volume BIGINT DEFAULT 0;

-- Seed default tiers
INSERT INTO ecommerce.fee_tiers (name, min_volume, max_volume, fee_percent, fee_flat, sort_order)
VALUES
    ('Starter',     0,       1000000,  15.00, 30, 1),
    ('Growth',      1000001, 5000000,  12.00, 25, 2),
    ('Enterprise',  5000001, NULL,     10.00, 20, 3)
ON CONFLICT DO NOTHING;

COMMIT;

-- DOWN
ALTER TABLE ecommerce.merchant_accounts DROP COLUMN IF EXISTS total_sales_volume;
DROP TABLE IF EXISTS ecommerce.merchant_fee_overrides CASCADE;
DROP TABLE IF EXISTS ecommerce.fee_tiers CASCADE;
