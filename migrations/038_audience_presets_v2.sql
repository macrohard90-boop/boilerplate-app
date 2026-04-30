-- 038_audience_presets_v2.sql
-- Expand audience presets with purchase, subscription, browse intent,
-- cart behavior, and lifecycle targeting audiences.
-- Adds new groups and ~20 new presets that use the expanded filter engine.

-- UP

-- Ensure saved_metrics has preset_key and audience_filters columns
-- (used by the audience seed service to link presets to metrics)
ALTER TABLE analytics.saved_metrics ADD COLUMN IF NOT EXISTS preset_key VARCHAR(100) UNIQUE;
ALTER TABLE analytics.saved_metrics ADD COLUMN IF NOT EXISTS audience_filters JSONB;
CREATE INDEX IF NOT EXISTS idx_saved_metrics_preset_key ON analytics.saved_metrics(preset_key) WHERE preset_key IS NOT NULL;

-- Deduplicate audience_groups by name (keep earliest created)
DELETE FROM marketing.audience_groups a
USING marketing.audience_groups b
WHERE a.name = b.name AND a.created_at > b.created_at;

-- Ensure name is unique (missing from original schema)
DO $$ BEGIN
  ALTER TABLE marketing.audience_groups ADD CONSTRAINT audience_groups_name_key UNIQUE (name);
EXCEPTION WHEN duplicate_table THEN NULL;
END $$;

-- Add new groups
INSERT INTO marketing.audience_groups (name, display_order) VALUES
    ('Subscription',    5),
    ('Browse Intent',   6),
    ('Cart Behavior',   7),
    ('Lifecycle',       8)
ON CONFLICT (name) DO NOTHING;

-- =====================================================================
-- A. Purchase-Based (add to existing "Purchase Behavior" group)
-- =====================================================================
INSERT INTO marketing.audience_group_presets
    (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'first_time_buyers', 'First-Time Buyers', 'Exactly 1 order',
     'text-accent-green',
     '{"order_count_min": 1, "order_count_max": 1}',
     FALSE, 10),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'repeat_buyers', 'Repeat Buyers', '2+ orders',
     'text-accent-blue',
     '{"order_count_min": 2}',
     FALSE, 11),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'high_spenders', 'High Spenders ($100+)', 'Total spend >= $100',
     'text-accent-purple',
     '{"total_spent_min": 10000}',
     FALSE, 12),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'recent_buyers_30d', 'Recent Buyers (30d)', 'Purchased in last 30 days',
     'text-accent-green',
     '{"last_purchase_days_max": 30}',
     FALSE, 13),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Purchase Behavior'),
     'coupon_users', 'Coupon Users', 'Bought with any discount code',
     'text-accent-orange',
     '{"has_coupon": true}',
     FALSE, 14)
ON CONFLICT (preset_key) DO UPDATE SET
    label = EXCLUDED.label,
    detail = EXCLUDED.detail,
    color = EXCLUDED.color,
    filters = EXCLUDED.filters,
    display_order = EXCLUDED.display_order;

-- =====================================================================
-- B. Subscription
-- =====================================================================
INSERT INTO marketing.audience_group_presets
    (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Subscription'),
     'active_subscribers', 'Active Subscribers', 'Currently subscribed',
     'text-accent-green',
     '{"subscription_status": ["active"]}',
     FALSE, 0),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Subscription'),
     'cancelled_subscribers_30d', 'Cancelled (30d)', 'Cancelled subscription in last 30 days',
     'text-accent-orange',
     '{"subscription_cancelled_days": 30}',
     FALSE, 1),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Subscription'),
     'non_subscribers', 'Non-Subscribers', 'Never had a subscription',
     'text-accent-blue',
     '{"no_subscription": true}',
     FALSE, 2)
ON CONFLICT (preset_key) DO UPDATE SET
    label = EXCLUDED.label,
    detail = EXCLUDED.detail,
    color = EXCLUDED.color,
    filters = EXCLUDED.filters,
    display_order = EXCLUDED.display_order;

-- =====================================================================
-- C. Browse Intent
-- =====================================================================
INSERT INTO marketing.audience_group_presets
    (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Browse Intent'),
     'high_intent_browsers', 'High-Intent Browsers', '3+ product views in 14d, no orders',
     'text-accent-blue',
     '{"order_count_max": 0, "event_type": ["product_viewed"], "event_min_count": 3, "event_days_lookback": 14}',
     FALSE, 0),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Browse Intent'),
     'repeat_searchers_v2', 'Repeat Searchers', '2+ searches in 14 days',
     'text-accent-blue',
     '{"event_type": ["search_performed"], "event_min_count": 2, "event_days_lookback": 14}',
     FALSE, 1),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Browse Intent'),
     'unmet_demand', 'Unmet Demand', 'Searched with no results in 30d',
     'text-accent-orange',
     '{"event_type": ["search_no_results"], "event_min_count": 1, "event_days_lookback": 30}',
     FALSE, 2),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Browse Intent'),
     'oos_interest', 'Out-of-Stock Interest', 'Viewed OOS product in 30d',
     'text-accent-pink',
     '{"event_type": ["out_of_stock_viewed"], "event_min_count": 1, "event_days_lookback": 30}',
     FALSE, 3)
ON CONFLICT (preset_key) DO UPDATE SET
    label = EXCLUDED.label,
    detail = EXCLUDED.detail,
    color = EXCLUDED.color,
    filters = EXCLUDED.filters,
    display_order = EXCLUDED.display_order;

-- =====================================================================
-- D. Cart Behavior
-- =====================================================================
INSERT INTO marketing.audience_group_presets
    (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Cart Behavior'),
     'recent_cart_abandoners_7d', 'Recent Cart Abandoners (7d)', 'Abandoned cart in last 7 days',
     'text-accent-orange',
     '{"cart_abandoned_days": 7}',
     FALSE, 0),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Cart Behavior'),
     'high_value_cart_abandoners', 'High-Value Abandoners ($50+)', 'Abandoned cart worth $50+',
     'text-accent-pink',
     '{"cart_abandoned_days": 90, "min_cart_value": 5000}',
     FALSE, 1),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Cart Behavior'),
     'checkout_dropoffs', 'Checkout Dropoffs', 'Started checkout in 14d, no orders',
     'text-accent-pink',
     '{"event_type": ["checkout_started"], "event_min_count": 1, "event_days_lookback": 14, "order_count_max": 0}',
     FALSE, 2),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Cart Behavior'),
     'added_no_checkout_7d', 'Added, No Checkout (7d)', 'Added to cart but never started checkout',
     'text-accent-orange',
     '{"event_type": ["add_to_cart"], "event_min_count": 1, "event_days_lookback": 7, "not_event_type": ["checkout_started"], "not_event_days_lookback": 7}',
     FALSE, 3)
ON CONFLICT (preset_key) DO UPDATE SET
    label = EXCLUDED.label,
    detail = EXCLUDED.detail,
    color = EXCLUDED.color,
    filters = EXCLUDED.filters,
    display_order = EXCLUDED.display_order;

-- =====================================================================
-- E. Lifecycle
-- =====================================================================
INSERT INTO marketing.audience_group_presets
    (group_id, preset_key, label, detail, color, filters, is_dynamic, display_order)
VALUES
    ((SELECT id FROM marketing.audience_groups WHERE name = 'Lifecycle'),
     'new_signups_7d', 'New Signups (7d)', 'Registered in last 7 days',
     'text-accent-green',
     '{"signup_days_max": 7}',
     FALSE, 0),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Lifecycle'),
     'never_purchased_30d', 'Never Purchased (30d+)', 'Signed up 30+ days ago, no orders',
     'text-accent-orange',
     '{"signup_days_min": 30, "order_count_max": 0}',
     FALSE, 1),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Lifecycle'),
     'active_7d', 'Active (7d)', 'Has page views in last 7 days',
     'text-accent-green',
     '{"active_days": 7}',
     FALSE, 2),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Lifecycle'),
     'lapsed_60d', 'Lapsed (60d+)', 'No activity in 60+ days',
     'text-accent-pink',
     '{"inactive_days": 60}',
     FALSE, 3),

    ((SELECT id FROM marketing.audience_groups WHERE name = 'Lifecycle'),
     'declining_engagement', 'Declining Engagement', 'Negative velocity, still engaged',
     'text-accent-yellow',
     '{"velocity_max": -0.01, "score_above": 0}',
     FALSE, 4)
ON CONFLICT (preset_key) DO UPDATE SET
    label = EXCLUDED.label,
    detail = EXCLUDED.detail,
    color = EXCLUDED.color,
    filters = EXCLUDED.filters,
    display_order = EXCLUDED.display_order;

-- DOWN
DELETE FROM marketing.audience_group_presets WHERE preset_key IN (
    'first_time_buyers', 'repeat_buyers', 'high_spenders', 'recent_buyers_30d', 'coupon_users',
    'active_subscribers', 'cancelled_subscribers_30d', 'non_subscribers',
    'high_intent_browsers', 'repeat_searchers_v2', 'unmet_demand', 'oos_interest',
    'recent_cart_abandoners_7d', 'high_value_cart_abandoners', 'checkout_dropoffs', 'added_no_checkout_7d',
    'new_signups_7d', 'never_purchased_30d', 'active_7d', 'lapsed_60d', 'declining_engagement'
);
DELETE FROM marketing.audience_groups WHERE name IN ('Subscription', 'Browse Intent', 'Cart Behavior', 'Lifecycle');
