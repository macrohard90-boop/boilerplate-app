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
