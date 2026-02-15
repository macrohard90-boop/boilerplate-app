-- Migration 002: SaaS schema (6 tables — template choice: saas)
-- Depends on: 001_core_schema.sql (references core.users)
-- Only runs when APP_TEMPLATE=saas

-- UP

-- Plans
CREATE TABLE saas.plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    price_monthly INTEGER NOT NULL,
    price_yearly INTEGER NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_slug ON saas.plans(slug);
CREATE INDEX idx_plans_is_active ON saas.plans(is_active);
CREATE INDEX idx_plans_created_at ON saas.plans(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON saas.plans
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Plan Features
CREATE TABLE saas.plan_features (
    plan_id UUID NOT NULL REFERENCES saas.plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    feature_value VARCHAR(255),
    "limit" INTEGER,
    PRIMARY KEY (plan_id, feature_key)
);

-- Subscriptions
CREATE TABLE saas.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    plan_id UUID NOT NULL REFERENCES saas.plans(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'trialing', 'paused')),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user_id ON saas.subscriptions(user_id);
CREATE INDEX idx_subscriptions_plan_id ON saas.subscriptions(plan_id);
CREATE INDEX idx_subscriptions_status ON saas.subscriptions(status);
CREATE INDEX idx_subscriptions_user_status ON saas.subscriptions(user_id, status);
CREATE INDEX idx_subscriptions_created_at ON saas.subscriptions(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON saas.subscriptions
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Usage Records
CREATE TABLE saas.usage_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id UUID NOT NULL REFERENCES saas.subscriptions(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_records_subscription_id ON saas.usage_records(subscription_id);
CREATE INDEX idx_usage_records_feature_key ON saas.usage_records(feature_key);
CREATE INDEX idx_usage_records_recorded_at ON saas.usage_records(recorded_at);

-- Invoices
CREATE TABLE saas.invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    subscription_id UUID NOT NULL REFERENCES saas.subscriptions(id) ON DELETE RESTRICT,
    amount INTEGER NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'paid', 'void', 'uncollectible')),
    due_date TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_user_id ON saas.invoices(user_id);
CREATE INDEX idx_invoices_subscription_id ON saas.invoices(subscription_id);
CREATE INDEX idx_invoices_status ON saas.invoices(status);
CREATE INDEX idx_invoices_created_at ON saas.invoices(created_at);

-- Invoice Items
CREATE TABLE saas.invoice_items (
    invoice_id UUID NOT NULL REFERENCES saas.invoices(id) ON DELETE CASCADE,
    description VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price INTEGER NOT NULL,
    total INTEGER NOT NULL,
    PRIMARY KEY (invoice_id, description)
);

-- DOWN
DROP TABLE IF EXISTS saas.invoice_items CASCADE;
DROP TABLE IF EXISTS saas.invoices CASCADE;
DROP TABLE IF EXISTS saas.usage_records CASCADE;
DROP TABLE IF EXISTS saas.subscriptions CASCADE;
DROP TABLE IF EXISTS saas.plan_features CASCADE;
DROP TABLE IF EXISTS saas.plans CASCADE;
