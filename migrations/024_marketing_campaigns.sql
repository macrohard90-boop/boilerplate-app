-- UP
-- Marketing module tables: campaigns, communication types, user preferences
CREATE SCHEMA IF NOT EXISTS marketing;

-- Email campaign management (metadata only — ESP stores per-recipient data)
CREATE TABLE marketing.campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    template_id VARCHAR(100) NOT NULL,
    template_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    email_type VARCHAR(30) NOT NULL DEFAULT 'marketing_email'
        CHECK (email_type IN ('marketing_email', 'transactional_email')),
    status VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'cancelled')),
    provider VARCHAR(50),
    provider_campaign_id VARCHAR(255),
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    recipient_count INT DEFAULT 0,
    stats_cache JSONB,
    stats_fetched_at TIMESTAMPTZ,
    created_by UUID REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_marketing_campaigns_status ON marketing.campaigns(status);
CREATE INDEX idx_marketing_campaigns_created ON marketing.campaigns(created_at);
CREATE INDEX idx_marketing_campaigns_provider_id ON marketing.campaigns(provider_campaign_id);

CREATE TRIGGER set_campaigns_updated_at BEFORE UPDATE ON marketing.campaigns
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Communication types (admin-defined marketing categories)
CREATE TABLE marketing.communication_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default communication types
INSERT INTO marketing.communication_types (name, description) VALUES
    ('newsletters', 'Regular updates and news about our products and services'),
    ('promotions', 'Special offers, discounts, and promotional campaigns'),
    ('product_updates', 'New product announcements and feature updates');

-- Per-user preferences for each communication type
CREATE TABLE marketing.user_communication_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    communication_type_id UUID NOT NULL REFERENCES marketing.communication_types(id) ON DELETE CASCADE,
    allowed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, communication_type_id)
);

CREATE INDEX idx_user_comm_prefs_user ON marketing.user_communication_preferences(user_id);

-- DOWN
-- (run manually to roll back — not auto-executed)
-- DROP TABLE IF EXISTS marketing.user_communication_preferences CASCADE;
-- DROP TABLE IF EXISTS marketing.communication_types CASCADE;
-- DROP TABLE IF EXISTS marketing.campaigns CASCADE;
-- DROP SCHEMA IF EXISTS marketing CASCADE;
