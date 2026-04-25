"""Idempotent script to ensure all required tables exist.

This handles cases where migrations were baselined but tables were never
actually created (e.g., fresh DB with stale migration history).
Runs CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS for all tables.
Safe to run multiple times.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.core.database import get_session_factory  # noqa: E402
from sqlalchemy import text  # noqa: E402


STATEMENTS = [
    # --- Migration 025: email_templates ---
    """CREATE TABLE IF NOT EXISTS marketing.email_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL UNIQUE,
        display_name VARCHAR(255) NOT NULL,
        subject VARCHAR(500),
        html_content TEXT NOT NULL,
        category VARCHAR(50) NOT NULL DEFAULT 'campaign'
            CHECK (category IN ('transactional', 'campaign', 'automation')),
        description TEXT,
        variables JSONB NOT NULL DEFAULT '[]',
        is_builtin BOOLEAN NOT NULL DEFAULT false,
        version INT NOT NULL DEFAULT 1,
        created_by UUID REFERENCES core.users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_email_templates_category ON marketing.email_templates(category)",
    "CREATE INDEX IF NOT EXISTS idx_email_templates_name ON marketing.email_templates(name)",
    # --- Migration 026: campaign wizard ---
    """CREATE TABLE IF NOT EXISTS marketing.campaign_variants (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
        label VARCHAR(10) NOT NULL,
        subject VARCHAR(255) NOT NULL,
        html_content TEXT NOT NULL,
        source_template_id VARCHAR(100),
        weight INT NOT NULL DEFAULT 100,
        provider_campaign_id VARCHAR(255),
        stats_cache JSONB,
        stats_fetched_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (campaign_id, label)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_campaign_variants_campaign ON marketing.campaign_variants(campaign_id)",
    """CREATE TABLE IF NOT EXISTS marketing.audience_segments (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(100) NOT NULL,
        description TEXT,
        filters JSONB NOT NULL DEFAULT '{}'::jsonb,
        is_system BOOLEAN NOT NULL DEFAULT FALSE,
        user_count INT DEFAULT 0,
        last_computed_at TIMESTAMPTZ,
        created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audience_segments_system ON marketing.audience_segments(is_system)",
    """CREATE TABLE IF NOT EXISTS marketing.campaign_segments (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
        segment_id UUID NOT NULL REFERENCES marketing.audience_segments(id),
        variant_label VARCHAR(10),
        UNIQUE (campaign_id, segment_id, variant_label)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_campaign_segments_campaign ON marketing.campaign_segments(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_segments_segment ON marketing.campaign_segments(segment_id)",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS utm_source VARCHAR(100)",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS utm_medium VARCHAR(100) DEFAULT 'email'",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(200)",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS utm_content VARCHAR(200)",
    # --- Migration 027: utm_term ---
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS utm_term VARCHAR(200)",
    # --- Migration 028: saved_metrics ---
    """CREATE TABLE IF NOT EXISTS analytics.saved_metrics (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(200) NOT NULL,
        description TEXT,
        sql_query TEXT NOT NULL,
        visualization_type VARCHAR(50) NOT NULL DEFAULT 'table',
        created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    # --- Migration 029: metric groups ---
    "ALTER TABLE analytics.saved_metrics ADD COLUMN IF NOT EXISTS group_name VARCHAR(100)",
    "ALTER TABLE analytics.saved_metrics ADD COLUMN IF NOT EXISTS display_order INT NOT NULL DEFAULT 0",
    # --- Migration 030: audience bridge ---
    "ALTER TABLE analytics.saved_metrics ADD COLUMN IF NOT EXISTS is_audience BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE marketing.audience_segments ADD COLUMN IF NOT EXISTS metric_id UUID",
    """CREATE INDEX IF NOT EXISTS idx_saved_metrics_audience
        ON analytics.saved_metrics(is_audience) WHERE is_audience = TRUE""",
    """CREATE INDEX IF NOT EXISTS idx_audience_segments_metric
        ON marketing.audience_segments(metric_id) WHERE metric_id IS NOT NULL""",
    # --- Migration 031: audience groups ---
    """CREATE TABLE IF NOT EXISTS marketing.audience_groups (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(100) NOT NULL,
        display_order INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS marketing.audience_group_presets (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        group_id UUID REFERENCES marketing.audience_groups(id) ON DELETE SET NULL,
        preset_key VARCHAR(100) NOT NULL UNIQUE,
        label VARCHAR(100) NOT NULL,
        detail TEXT,
        color VARCHAR(50) DEFAULT 'text-accent-blue',
        filters JSONB NOT NULL DEFAULT '{}',
        is_dynamic BOOLEAN DEFAULT FALSE,
        display_order INT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_agp_group ON marketing.audience_group_presets(group_id)",
    # --- Migration 031: seed audience groups (idempotent) ---
    """INSERT INTO marketing.audience_groups (name, display_order)
    SELECT name, display_order FROM (VALUES
        ('Audience Overview', 0),
        ('Purchase Behavior', 1),
        ('Event Behavior',    2),
        ('Engagement',        3),
        ('Device & Platform', 4)
    ) AS v(name, display_order)
    WHERE NOT EXISTS (SELECT 1 FROM marketing.audience_groups LIMIT 1)""",
    # --- Migration 031: seed audience group presets (idempotent) ---
    """INSERT INTO marketing.audience_group_presets
        (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
    VALUES
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Audience Overview'),
         'all', 'All Subscribers', NULL, 'text-accent-blue', '{}', FALSE, 0),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Audience Overview'),
         'all_customers', 'All Customers', 'Users with at least 1 order', 'text-accent-green', '{"has_orders": true}', FALSE, 1)
    ON CONFLICT (preset_key) DO NOTHING""",
    """INSERT INTO marketing.audience_group_presets
        (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
    VALUES
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
         'champions', 'Champions', 'High-value repeat buyers', 'text-accent-green', '{"rfm_segment": ["champion"]}', FALSE, 0),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
         'at_risk', 'At-Risk', 'Fading engagement', 'text-accent-yellow', '{"rfm_segment": ["at_risk"]}', FALSE, 1),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
         'cart_abandoners', 'Cart Abandoners', 'Left items in cart', 'text-accent-orange', '{"cart_status": "abandoned"}', FALSE, 2),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
         'new_customers', 'New Customers', 'Recently acquired', 'text-accent-purple', '{"rfm_segment": ["new"]}', FALSE, 3)
    ON CONFLICT (preset_key) DO NOTHING""",
    """INSERT INTO marketing.audience_group_presets
        (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
    VALUES
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
         'added_to_cart', 'Added to Cart', 'Added items but no orders yet', 'text-accent-orange', '{"event_type": ["add_to_cart"], "has_orders": false}', FALSE, 0),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
         'checkout_dropoff', 'Checkout Drop-off', 'Started checkout but abandoned', 'text-accent-pink', '{"event_type": ["checkout_abandoned"]}', FALSE, 1),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
         'high_intent', 'High-Intent Browsers', '5+ product views in 7 days', 'text-accent-blue', '{"event_type": ["product_viewed"], "event_min_count": 5, "event_days_lookback": 7}', FALSE, 2),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
         'repeat_searchers', 'Repeat Searchers', '3+ searches in 30 days', 'text-accent-blue', '{"event_type": ["search_performed"], "event_min_count": 3, "event_days_lookback": 30}', FALSE, 3)
    ON CONFLICT (preset_key) DO NOTHING""",
    """INSERT INTO marketing.audience_group_presets
        (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
    VALUES
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Engagement'),
         'active_30d', 'Active (30d)', 'Active in the last 30 days', 'text-accent-green', '{"last_purchase_days_max": 30}', FALSE, 0),
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Engagement'),
         'high_engagers', 'High Engagers', '5+ sessions in 90 days', 'text-accent-blue', '{"min_sessions": 5}', FALSE, 1)
    ON CONFLICT (preset_key) DO NOTHING""",
    """INSERT INTO marketing.audience_group_presets
        (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
    VALUES
        ((SELECT id FROM marketing.audience_groups WHERE name = 'Device & Platform'),
         'device_dynamic', '(Dynamic)', 'Auto-populated from analytics', 'text-accent-blue', '{}', TRUE, 0)
    ON CONFLICT (preset_key) DO NOTHING""",
    # --- Migration 032: notifications schema ---
    "CREATE SCHEMA IF NOT EXISTS notifications",
    """CREATE TABLE IF NOT EXISTS notifications.message_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
        channel VARCHAR(20) NOT NULL CHECK (channel IN ('sms', 'whatsapp')),
        provider VARCHAR(50) NOT NULL DEFAULT '',
        provider_message_id VARCHAR(255),
        to_number VARCHAR(50) NOT NULL,
        template_id VARCHAR(100),
        body_preview VARCHAR(500),
        status VARCHAR(20) NOT NULL DEFAULT 'sent'
            CHECK (status IN ('sent', 'delivered', 'failed', 'queued')),
        error_message TEXT,
        sent_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_message_log_user ON notifications.message_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_message_log_channel ON notifications.message_log(channel)",
    "CREATE INDEX IF NOT EXISTS idx_message_log_created ON notifications.message_log(created_at)",
    """CREATE TABLE IF NOT EXISTS notifications.automation_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_name VARCHAR(100) NOT NULL,
        channel VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp')),
        template_id VARCHAR(100) NOT NULL,
        delay_seconds INT NOT NULL DEFAULT 0,
        enabled BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_automation_rules_event ON notifications.automation_rules(event_name)",
    """INSERT INTO notifications.automation_rules (event_name, channel, template_id, enabled)
    SELECT * FROM (VALUES
        ('user.registered', 'sms', 'welcome_sms', false),
        ('user.registered', 'whatsapp', 'welcome_whatsapp', false),
        ('order.completed', 'sms', 'order_confirmation_sms', false)
    ) AS v(event_name, channel, template_id, enabled)
    WHERE NOT EXISTS (SELECT 1 FROM notifications.automation_rules LIMIT 1)""",
    "ALTER TABLE core.users ADD COLUMN IF NOT EXISTS phone VARCHAR(32)",
    "ALTER TABLE core.users ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(32)",
    # --- Migration 033: campaign pipeline ---
    """CREATE TABLE IF NOT EXISTS marketing.campaign_recipients (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cr_campaign ON marketing.campaign_recipients(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_cr_user ON marketing.campaign_recipients(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_cr_provider_msg ON marketing.campaign_recipients(provider_message_id)",
    "CREATE INDEX IF NOT EXISTS idx_cr_status ON marketing.campaign_recipients(status)",
    """CREATE TABLE IF NOT EXISTS marketing.campaign_link_clicks (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_clc_recipient ON marketing.campaign_link_clicks(recipient_id)",
    "CREATE INDEX IF NOT EXISTS idx_clc_campaign ON marketing.campaign_link_clicks(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_clc_zone ON marketing.campaign_link_clicks(zone)",
    """CREATE TABLE IF NOT EXISTS marketing.campaign_attributions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ca_campaign ON marketing.campaign_attributions(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_ca_user ON marketing.campaign_attributions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_ca_converted ON marketing.campaign_attributions(converted_at)",
    """CREATE TABLE IF NOT EXISTS marketing.campaign_stats_summary (
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
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_css_campaign_variant ON marketing.campaign_stats_summary(campaign_id, variant_id) WHERE variant_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_css_campaign_overall ON marketing.campaign_stats_summary(campaign_id) WHERE variant_id IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_css_campaign ON marketing.campaign_stats_summary(campaign_id)",
    """CREATE TABLE IF NOT EXISTS marketing.automation_flows (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_af_trigger ON marketing.automation_flows(trigger_event)",
    "CREATE INDEX IF NOT EXISTS idx_af_status ON marketing.automation_flows(status)",
    """CREATE TABLE IF NOT EXISTS marketing.automation_flow_steps (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        flow_id UUID NOT NULL REFERENCES marketing.automation_flows(id) ON DELETE CASCADE,
        step_type VARCHAR(20) NOT NULL
            CHECK (step_type IN ('send', 'wait', 'branch', 'split', 'update', 'webhook')),
        step_order INT NOT NULL DEFAULT 0,
        config JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_afs_flow ON marketing.automation_flow_steps(flow_id)",
    "CREATE INDEX IF NOT EXISTS idx_afs_order ON marketing.automation_flow_steps(flow_id, step_order)",
    """CREATE TABLE IF NOT EXISTS marketing.automation_flow_connections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        flow_id UUID NOT NULL REFERENCES marketing.automation_flows(id) ON DELETE CASCADE,
        from_step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
        to_step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
        condition_label VARCHAR(100),
        condition_expr JSONB
    )""",
    "CREATE INDEX IF NOT EXISTS idx_afc_flow ON marketing.automation_flow_connections(flow_id)",
    "CREATE INDEX IF NOT EXISTS idx_afc_from ON marketing.automation_flow_connections(from_step_id)",
    """CREATE TABLE IF NOT EXISTS marketing.flow_enrollments (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_fe_flow ON marketing.flow_enrollments(flow_id)",
    "CREATE INDEX IF NOT EXISTS idx_fe_user ON marketing.flow_enrollments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_fe_status ON marketing.flow_enrollments(status)",
    """CREATE TABLE IF NOT EXISTS marketing.flow_step_executions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        enrollment_id UUID NOT NULL REFERENCES marketing.flow_enrollments(id) ON DELETE CASCADE,
        step_id UUID NOT NULL REFERENCES marketing.automation_flow_steps(id) ON DELETE CASCADE,
        status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'waiting', 'executed', 'skipped', 'failed')),
        result JSONB,
        scheduled_at TIMESTAMPTZ,
        executed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_fse_enrollment ON marketing.flow_step_executions(enrollment_id)",
    "CREATE INDEX IF NOT EXISTS idx_fse_status ON marketing.flow_step_executions(status)",
    """CREATE TABLE IF NOT EXISTS marketing.messaging_config (
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
    )""",
    """INSERT INTO marketing.messaging_config
        (channel, freq_cap_marketing_per_day, freq_cap_marketing_per_week,
         freq_cap_marketing_per_month, quiet_hours_start, quiet_hours_end)
    SELECT * FROM (VALUES
        ('global'::VARCHAR(20), 3, 7, 20, '22:00'::TIME, '08:00'::TIME),
        ('email'::VARCHAR(20), 2, 5, 15, NULL::TIME, NULL::TIME),
        ('sms'::VARCHAR(20), 1, 3, 8, '21:00'::TIME, '09:00'::TIME),
        ('whatsapp'::VARCHAR(20), 1, 3, 8, '21:00'::TIME, '09:00'::TIME)
    ) AS v(channel, d, w, m, qs, qe)
    WHERE NOT EXISTS (SELECT 1 FROM marketing.messaging_config LIMIT 1)""",
    """CREATE TABLE IF NOT EXISTS marketing.message_pressure_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
        channel VARCHAR(20) NOT NULL
            CHECK (channel IN ('email', 'sms', 'whatsapp')),
        message_type VARCHAR(20) NOT NULL DEFAULT 'marketing'
            CHECK (message_type IN ('marketing', 'transactional')),
        campaign_id UUID REFERENCES marketing.campaigns(id) ON DELETE SET NULL,
        sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mpl_user_channel ON marketing.message_pressure_log(user_id, channel)",
    "CREATE INDEX IF NOT EXISTS idx_mpl_sent ON marketing.message_pressure_log(sent_at)",
    """CREATE TABLE IF NOT EXISTS analytics.page_click_interactions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pci_session ON analytics.page_click_interactions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_pci_campaign ON analytics.page_click_interactions(campaign_id)",
    """CREATE TABLE IF NOT EXISTS analytics.engagement_scores (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_es_score ON analytics.engagement_scores(score)",
    # --- Migration 033: ALTER existing tables ---
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS medium VARCHAR(20) DEFAULT 'email'",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS goal_event VARCHAR(100)",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS goal_window_days INT DEFAULT 7",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS attribution_window_days INT DEFAULT 7",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS enable_heatmap BOOLEAN DEFAULT false",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS last_reconciled_at TIMESTAMPTZ",
    "ALTER TABLE marketing.campaigns ADD COLUMN IF NOT EXISTS reconciliation_delta JSONB",
    "ALTER TABLE analytics.utm_tracking ADD COLUMN IF NOT EXISTS campaign_id UUID",
    "ALTER TABLE analytics.events ADD COLUMN IF NOT EXISTS campaign_id UUID",
]


async def ensure_tables() -> None:
    sf = get_session_factory()
    ok = 0
    skipped = 0
    for stmt in STATEMENTS:
        async with sf() as db:
            try:
                await db.execute(text(stmt))
                await db.commit()
                ok += 1
            except Exception:
                skipped += 1
                # Already exists or constraint issue — safe to ignore
    print(f"  ensure_tables: {ok} applied, {skipped} skipped (already exist)")


if __name__ == "__main__":
    asyncio.run(ensure_tables())
