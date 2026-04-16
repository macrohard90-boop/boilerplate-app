-- Migration 011: Payment settings key-value store
-- Used for admin-configurable payment method toggles

-- UP

CREATE TABLE IF NOT EXISTS ecommerce.payment_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DOWN
DROP TABLE IF EXISTS ecommerce.payment_settings CASCADE;
