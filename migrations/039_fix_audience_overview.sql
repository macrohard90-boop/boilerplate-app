-- UP: Fix Audience Overview presets
-- Rename "All Subscribers" to "All Marketing Opt-ins" (it was misleading)
UPDATE marketing.audience_group_presets
SET label = 'All Marketing Opt-ins',
    detail = 'Users with marketing email consent'
WHERE preset_key = 'all';

-- Add "All Active Subscribers" to Audience Overview group
INSERT INTO marketing.audience_group_presets (group_id, preset_key, label, detail, filters, display_order)
SELECT ag.id, 'all_active_subscribers', 'All Active Subscribers',
       'Users with an active subscription',
       '{"subscription_status": ["active"]}'::jsonb, 2
FROM marketing.audience_groups ag
WHERE ag.name = 'Audience Overview'
ON CONFLICT (preset_key) DO UPDATE
SET label = EXCLUDED.label, detail = EXCLUDED.detail, filters = EXCLUDED.filters;

-- DOWN:
-- UPDATE marketing.audience_group_presets SET label = 'All Subscribers', detail = '' WHERE preset_key = 'all';
-- DELETE FROM marketing.audience_group_presets WHERE preset_key = 'all_active_subscribers';
