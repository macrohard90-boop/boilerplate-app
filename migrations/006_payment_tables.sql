-- Migration 006: Payment tables for Phase 4
-- Depends on: 001_core_schema.sql, 002_ecommerce_schema.sql
-- Template: ecommerce

-- UP

-- Merchant accounts (Stripe Connect Express)
CREATE TABLE IF NOT EXISTS ecommerce.merchant_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    stripe_account_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'onboarding', 'active', 'restricted', 'disabled')),
    business_name VARCHAR(255),
    charges_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    payouts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_merchant_accounts_user_id ON ecommerce.merchant_accounts(user_id);
CREATE INDEX idx_merchant_accounts_stripe_account_id ON ecommerce.merchant_accounts(stripe_account_id);

-- Webhook events for idempotency
CREATE TABLE IF NOT EXISTS ecommerce.webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_webhook_events_event_id ON ecommerce.webhook_events(event_id);
CREATE INDEX idx_webhook_events_event_type ON ecommerce.webhook_events(event_type);

-- DOWN

DROP TABLE IF EXISTS ecommerce.webhook_events CASCADE;
DROP TABLE IF EXISTS ecommerce.merchant_accounts CASCADE;
