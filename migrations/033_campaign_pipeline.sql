-- Migration 033: Campaign pipeline tables
-- Depends on: 024_marketing_campaigns.sql, 026_campaign_wizard.sql, 004_analytics_schema.sql
-- Creates the full campaign delivery, attribution, automation flow, and guardrail tables

-- UP

-- ============================================================
-- 1. Campaign Delivery
-- ============================================================

-- Per-recipient delivery tracking (INSERT-BEFORE-SEND pattern)
CREATE TABLE marketing.campaign_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES marketing.campaign_variants(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL DEFAULT 'email'
        CHECK (channel IN ('email', 'sms', 'whatsapp')),
    to_address VARCHAR(255) NOT NULL,
    provider VARCHAR(50),
    provider_message_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'sending'
        CHECK (status IN ('sending', 'sent', 'delivered', 'opened', 'clicked',
                          'bounced', 'complained', 'unsubscribed', 'failed')),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cr_campaign ON marketing.campaign_recipients(campaign_id);
CREATE INDEX idx_cr_user ON marketing.campaign_recipients(user_id);
CREATE INDEX idx_cr_provider_msg ON marketing.campaign_recipients(provider_message_id);
CREATE INDEX idx_cr_status ON marketing.campaign_recipients(status);
CREATE UNIQUE INDEX idx_cr_campaign_user_unique
    ON marketing.campaign_recipients(campaign_id, user_id);

-- Layer 1 click tracking (email zones from webhooks)
CREATE TABLE marketing.campaign_link_clicks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES marketing.campaign_recipients(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    zone VARCHAR(20),
    click_number INT NOT NULL DEFAULT 1,
    ip_address VARCHAR(45),
    user_agent TEXT,
    clicked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clc_recipient ON marketing.campaign_link_clicks(recipient_id);
CREATE INDEX idx_clc_campaign ON marketing.campaign_link_clicks(campaign_id);
CREATE INDEX idx_clc_zone ON marketing.campaign_link_clicks(zone);

-- ============================================================
-- 2. Attribution
-- ============================================================

-- Links conversions back to campaigns (multi-touch attribution)
CREATE TABLE marketing.campaign_attributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES marketing.campaign_recipients(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL DEFAULT 'email'
        CHECK (channel IN ('email', 'sms', 'whatsapp')),
    conversion_event VARCHAR(100) NOT NULL,
    conversion_value NUMERIC(12,2) DEFAULT 0,
    conversion_currency VARCHAR(3) DEFAULT 'USD',
    converted BOOLEAN NOT NULL DEFAULT true,
    converted_at TIMESTAMPTZ,
    attribution_window_days INT NOT NULL DEFAULT 7,
    touch_sequence JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ca_campaign ON marketing.campaign_attributions(campaign_id);
CREATE INDEX idx_ca_user ON marketing.campaign_attributions(user_id);
CREATE INDEX idx_ca_converted ON marketing.campaign_attributions(converted_at);

-- Pre-aggregated funnel metrics (refreshed by background worker)
CREATE TABLE marketing.campaign_stats_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES marketing.campaign_variants(id) ON DELETE SET NULL,
    total_sent INT NOT NULL DEFAULT 0,
    total_delivered INT NOT NULL DEFAULT 0,
    total_opened INT NOT NULL DEFAULT 0,
    total_clicked INT NOT NULL DEFAULT 0,
    total_bounced INT NOT NULL DEFAULT 0,
    total_complained INT NOT NULL DEFAULT 0,
    total_unsubscribed INT NOT NULL DEFAULT 0,
    total_conversions INT NOT NULL DEFAULT 0,
    total_revenue NUMERIC(12,2) NOT NULL DEFAULT 0,
    open_rate NUMERIC(6,4) DEFAULT 0,
    click_rate NUMERIC(6,4) DEFAULT 0,
    conversion_rate NUMERIC(6,4) DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial unique indexes for NULL-safe upsert (NULL != NULL in standard UNIQUE)
CREATE UNIQUE INDEX idx_css_campaign_variant
    ON marketing.campaign_stats_summary(campaign_id, variant_id)
    WHERE variant_id IS NOT NULL;
CREATE UNIQUE INDEX idx_css_campaign_overall
    ON marketing.campaign_stats_summary(campaign_id)
    WHERE variant_id IS NULL;
CREATE INDEX idx_css_campaign ON marketing.campaign_stats_summary(campaign_id);

-- ============================================================
-- 3. Automation Flows
-- ============================================================

-- Flow definitions (welcome, cart abandon, post-purchase, win-back, etc.)
CREATE TABLE marketing.automation_flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_event VARCHAR(100) NOT NULL,
    trigger_conditions JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'archived')),
    goal_event VARCHAR(100),
    goal_window_days INT DEFAULT 7,
    allow_reentry BOOLEAN NOT NULL DEFAULT false,
    max_chain_depth INT NOT NULL DEFAULT 5,
    exit_tag VARCHAR(100),
    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_af_trigger ON marketing.automation_flows(trigger_event);
CREATE INDEX idx_af_status ON marketing.automation_flows(status);

CREATE TRIGGER set_automation_flows_updated_at BEFORE UPDATE ON marketing.automation_flows
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Steps within a flow (send, wait, branch, split, update, webhook)
CREATE TABLE marketing.automation_flow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES marketing.automation_flows(id) ON DELETE CASCADE,
    step_type VARCHAR(20) NOT NULL
        CHECK (step_type IN ('send', 'wait', 'branch', 'split', 'update', 'webhook')),
    step_order INT NOT NULL DEFAULT 0,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_afs_flow ON marketing.automation_flow_steps(flow_id);
CREATE INDEX idx_afs_order ON marketing.automation_flow_steps(flow_id, step_order);

-- Non-linear step connections (for branches, splits, merge points)
CREATE TABLE marketing.automation_flow_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES marketing.automation_flows(id) ON DELETE CASCADE,
    from_step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
    to_step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
    condition_label VARCHAR(100),
    condition_expr JSONB,
    UNIQUE (flow_id, from_step_id, to_step_id)
);

CREATE INDEX idx_afc_flow ON marketing.automation_flow_connections(flow_id);
CREATE INDEX idx_afc_from ON marketing.automation_flow_connections(from_step_id);

-- Per-user enrollment in flows
CREATE TABLE marketing.flow_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES marketing.automation_flows(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    current_step_id UUID REFERENCES marketing.automation_flow_steps(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'goal_reached', 'exited', 'error')),
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    exit_reason VARCHAR(255),
    trigger_payload JSONB DEFAULT '{}'::jsonb,
    chain_depth INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_fe_flow ON marketing.flow_enrollments(flow_id);
CREATE INDEX idx_fe_user ON marketing.flow_enrollments(user_id);
CREATE INDEX idx_fe_status ON marketing.flow_enrollments(status);
-- Uniqueness: one active enrollment per user per flow
CREATE UNIQUE INDEX idx_fe_active_unique
    ON marketing.flow_enrollments(flow_id, user_id) WHERE status = 'active';

-- Log of every step execution
CREATE TABLE marketing.flow_step_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id UUID NOT NULL REFERENCES marketing.flow_enrollments(id) ON DELETE CASCADE,
    step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'waiting', 'executed', 'skipped', 'failed')),
    result JSONB,
    scheduled_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fse_enrollment ON marketing.flow_step_executions(enrollment_id);
CREATE INDEX idx_fse_status ON marketing.flow_step_executions(status);
CREATE INDEX idx_fse_scheduled ON marketing.flow_step_executions(scheduled_at)
    WHERE status = 'waiting';

-- ============================================================
-- 4. Guardrails
-- ============================================================

-- Per-channel messaging configuration (freq caps, quiet hours, sunset)
CREATE TABLE marketing.messaging_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL UNIQUE
        CHECK (channel IN ('email', 'sms', 'whatsapp', 'global')),
    freq_cap_marketing_per_day INT DEFAULT 2,
    freq_cap_marketing_per_week INT DEFAULT 5,
    freq_cap_marketing_per_month INT DEFAULT 15,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    quiet_hours_timezone VARCHAR(50) DEFAULT 'UTC',
    sunset_inactivity_days INT DEFAULT 180,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default guardrail config
INSERT INTO marketing.messaging_config
    (channel, freq_cap_marketing_per_day, freq_cap_marketing_per_week,
     freq_cap_marketing_per_month, quiet_hours_start, quiet_hours_end)
VALUES
    ('global', 3, 7, 20, '22:00', '08:00'),
    ('email', 2, 5, 15, NULL, NULL),
    ('sms', 1, 3, 8, '21:00', '09:00'),
    ('whatsapp', 1, 3, 8, '21:00', '09:00');

-- Per-user message pressure log (for frequency capping)
CREATE TABLE marketing.message_pressure_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL
        CHECK (channel IN ('email', 'sms', 'whatsapp')),
    message_type VARCHAR(20) NOT NULL DEFAULT 'marketing'
        CHECK (message_type IN ('marketing', 'transactional')),
    campaign_id UUID REFERENCES marketing.campaigns(id) ON DELETE SET NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_mpl_user_channel ON marketing.message_pressure_log(user_id, channel);
CREATE INDEX idx_mpl_sent ON marketing.message_pressure_log(sent_at);

-- ============================================================
-- 5. Analytics Extensions
-- ============================================================

-- Layer 2+3 click interactions (landing page / mirror page JS clicks)
CREATE TABLE analytics.page_click_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES marketing.campaigns(id) ON DELETE SET NULL,
    page_url TEXT NOT NULL,
    element_selector TEXT,
    element_text VARCHAR(500),
    x_position INT,
    y_position INT,
    viewport_width INT,
    viewport_height INT,
    clicked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pci_session ON analytics.page_click_interactions(session_id);
CREATE INDEX idx_pci_campaign ON analytics.page_click_interactions(campaign_id);

-- Engagement scores (computed by background worker)
CREATE TABLE analytics.engagement_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE UNIQUE,
    score NUMERIC(8,2) NOT NULL DEFAULT 0,
    velocity NUMERIC(8,2) NOT NULL DEFAULT 0,
    last_email_open TIMESTAMPTZ,
    last_email_click TIMESTAMPTZ,
    last_sms_click TIMESTAMPTZ,
    last_site_visit TIMESTAMPTZ,
    last_purchase TIMESTAMPTZ,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_es_score ON analytics.engagement_scores(score);

-- ============================================================
-- 6. ALTER existing tables
-- ============================================================

-- Extend campaigns for multi-channel + attribution
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS medium VARCHAR(20) DEFAULT 'email';
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS goal_event VARCHAR(100);
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS goal_window_days INT DEFAULT 7;
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS attribution_window_days INT DEFAULT 7;
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS enable_heatmap BOOLEAN DEFAULT false;
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS last_reconciled_at TIMESTAMPTZ;
ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS reconciliation_delta JSONB;

-- Link UTM tracking and events to campaigns
ALTER TABLE analytics.utm_tracking ADD COLUMN IF NOT EXISTS campaign_id UUID;
ALTER TABLE analytics.events ADD COLUMN IF NOT EXISTS campaign_id UUID;

-- DOWN
DROP TABLE IF EXISTS analytics.engagement_scores CASCADE;
DROP TABLE IF EXISTS analytics.page_click_interactions CASCADE;
DROP TABLE IF EXISTS marketing.message_pressure_log CASCADE;
DROP TABLE IF EXISTS marketing.messaging_config CASCADE;
DROP TABLE IF EXISTS marketing.flow_step_executions CASCADE;
DROP TABLE IF EXISTS marketing.flow_enrollments CASCADE;
DROP TABLE IF EXISTS marketing.automation_flow_connections CASCADE;
DROP TABLE IF EXISTS marketing.automation_flow_steps CASCADE;
DROP TABLE IF EXISTS marketing.automation_flows CASCADE;
DROP TABLE IF EXISTS marketing.campaign_stats_summary CASCADE;
DROP TABLE IF EXISTS marketing.campaign_attributions CASCADE;
DROP TABLE IF EXISTS marketing.campaign_link_clicks CASCADE;
DROP TABLE IF EXISTS marketing.campaign_recipients CASCADE;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS medium;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS goal_event;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS goal_window_days;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS attribution_window_days;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS enable_heatmap;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS last_reconciled_at;
ALTER TABLE marketing.campaigns DROP COLUMN IF EXISTS reconciliation_delta;
ALTER TABLE analytics.utm_tracking DROP COLUMN IF EXISTS campaign_id;
ALTER TABLE analytics.events DROP COLUMN IF EXISTS campaign_id;
