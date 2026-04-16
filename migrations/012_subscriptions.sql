-- Migration 012: Subscription products and recurring payments
-- Adds recurring pricing fields to products, subscriptions table, and Stripe customer mapping

-- UP

-- Add recurring pricing columns to products
ALTER TABLE ecommerce.products
    ADD COLUMN pricing_type VARCHAR(20) NOT NULL DEFAULT 'one_time'
        CHECK (pricing_type IN ('one_time', 'recurring')),
    ADD COLUMN recurring_interval VARCHAR(20)
        CHECK (recurring_interval IN ('day', 'week', 'month', 'year')),
    ADD COLUMN recurring_interval_count INTEGER DEFAULT 1,
    ADD COLUMN trial_period_days INTEGER;

-- Expand product type constraint to include 'subscription'
ALTER TABLE ecommerce.products DROP CONSTRAINT IF EXISTS products_type_check;
ALTER TABLE ecommerce.products ADD CONSTRAINT products_type_check
    CHECK (type IN ('physical', 'digital', 'subscription'));

-- Stripe customer mapping (one Stripe Customer per user)
CREATE TABLE IF NOT EXISTS ecommerce.stripe_customers (
    user_id UUID PRIMARY KEY REFERENCES core.users(id) ON DELETE CASCADE,
    stripe_customer_id VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Subscriptions table (tracks active customer subscriptions)
CREATE TABLE ecommerce.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE RESTRICT,
    variant_id UUID REFERENCES ecommerce.product_variants(id),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'past_due', 'canceled', 'unpaid', 'trialing', 'paused', 'incomplete')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    canceled_at TIMESTAMPTZ,
    trial_start TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    discount_code_id UUID REFERENCES ecommerce.discount_codes(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user_id ON ecommerce.subscriptions(user_id);
CREATE INDEX idx_subscriptions_product_id ON ecommerce.subscriptions(product_id);
CREATE INDEX idx_subscriptions_stripe_sub_id ON ecommerce.subscriptions(stripe_subscription_id);
CREATE INDEX idx_subscriptions_status ON ecommerce.subscriptions(status);

CREATE TRIGGER set_subscriptions_updated_at BEFORE UPDATE ON ecommerce.subscriptions
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();


-- DOWN
DROP TABLE IF EXISTS ecommerce.subscriptions CASCADE;
DROP TABLE IF EXISTS ecommerce.stripe_customers CASCADE;
ALTER TABLE ecommerce.products DROP COLUMN IF EXISTS trial_period_days;
ALTER TABLE ecommerce.products DROP COLUMN IF EXISTS recurring_interval_count;
ALTER TABLE ecommerce.products DROP COLUMN IF EXISTS recurring_interval;
ALTER TABLE ecommerce.products DROP COLUMN IF EXISTS pricing_type;
ALTER TABLE ecommerce.products DROP CONSTRAINT IF EXISTS products_type_check;
ALTER TABLE ecommerce.products ADD CONSTRAINT products_type_check CHECK (type IN ('physical', 'digital'));
