-- 031_audience_groups.sql
-- Audience preset groups for the marketing admin.
-- Groups organise audience cards into collapsible sections
-- (Audience Overview, Purchase Behavior, etc.).
-- Presets are the individual audience cards within each group.

-- UP
CREATE TABLE marketing.audience_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE marketing.audience_group_presets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id UUID REFERENCES marketing.audience_groups(id) ON DELETE SET NULL,
    preset_key VARCHAR(100) NOT NULL UNIQUE,
    label VARCHAR(100) NOT NULL,
    detail TEXT,
    color VARCHAR(50) NOT NULL DEFAULT 'text-accent-blue',
    filters JSONB NOT NULL DEFAULT '{}',
    is_dynamic BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audience_group_presets_group_id
    ON marketing.audience_group_presets(group_id);

CREATE TRIGGER set_audience_groups_updated_at BEFORE UPDATE ON marketing.audience_groups
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

CREATE TRIGGER set_audience_group_presets_updated_at BEFORE UPDATE ON marketing.audience_group_presets
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Seed groups
INSERT INTO marketing.audience_groups (name, display_order) VALUES
    ('Audience Overview', 0),
    ('Purchase Behavior', 1),
    ('Event Behavior',    2),
    ('Engagement',        3),
    ('Device & Platform', 4);

-- Seed presets — Audience Overview
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order) VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Audience Overview'),
     'all', 'All Subscribers', NULL, 'text-accent-blue', '{}', FALSE, 0),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Audience Overview'),
     'all_customers', 'All Customers', 'Users with at least 1 order', 'text-accent-green', '{"has_orders": true}', FALSE, 1);

-- Seed presets — Purchase Behavior
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order) VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'champions', 'Champions', 'High-value repeat buyers', 'text-accent-green', '{"rfm_segment": ["champion"]}', FALSE, 0),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'at_risk', 'At-Risk', 'Fading engagement', 'text-accent-yellow', '{"rfm_segment": ["at_risk"]}', FALSE, 1),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'cart_abandoners', 'Cart Abandoners', 'Left items in cart', 'text-accent-orange', '{"cart_status": "abandoned"}', FALSE, 2),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'new_customers', 'New Customers', 'Recently acquired', 'text-accent-purple', '{"rfm_segment": ["new"]}', FALSE, 3);

-- Seed presets — Event Behavior
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order) VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
     'added_to_cart', 'Added to Cart', 'Added items but no orders yet', 'text-accent-orange', '{"event_type": ["add_to_cart"], "has_orders": false}', FALSE, 0),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
     'checkout_dropoff', 'Checkout Drop-off', 'Started checkout but abandoned', 'text-accent-pink', '{"event_type": ["checkout_abandoned"]}', FALSE, 1),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
     'high_intent', 'High-Intent Browsers', '5+ product views in 7 days', 'text-accent-blue', '{"event_type": ["product_viewed"], "event_min_count": 5, "event_days_lookback": 7}', FALSE, 2),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Event Behavior'),
     'repeat_searchers', 'Repeat Searchers', '3+ searches in 30 days', 'text-accent-blue', '{"event_type": ["search_performed"], "event_min_count": 3, "event_days_lookback": 30}', FALSE, 3);

-- Seed presets — Engagement
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order) VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Engagement'),
     'active_30d', 'Active (30d)', 'Active in the last 30 days', 'text-accent-green', '{"last_purchase_days_max": 30}', FALSE, 0),
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Engagement'),
     'high_engagers', 'High Engagers', '5+ sessions in 90 days', 'text-accent-blue', '{"min_sessions": 5}', FALSE, 1);

-- Seed presets — Device & Platform (dynamic, auto-populated from analytics)
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order) VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Device & Platform'),
     'device_dynamic', '(Dynamic)', 'Auto-populated from analytics', 'text-accent-blue', '{}', TRUE, 0);

-- DOWN
DROP TABLE IF EXISTS marketing.audience_group_presets;
DROP TABLE IF EXISTS marketing.audience_groups;
