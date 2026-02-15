-- SaaS seed data
-- 3 plans with features, sample subscriptions

-- Plans (prices in cents)
INSERT INTO saas.plans (id, name, slug, description, price_monthly, price_yearly, currency, features, is_active) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'Free', 'free', 'Get started with basic features', 0, 0, 'USD',
     '{"storage_gb": 1, "api_calls": 1000, "team_members": 1}'::jsonb, TRUE),
    ('a1000000-0000-0000-0000-000000000002', 'Pro', 'pro', 'For growing teams and businesses', 2999, 29990, 'USD',
     '{"storage_gb": 50, "api_calls": 50000, "team_members": 10, "priority_support": true}'::jsonb, TRUE),
    ('a1000000-0000-0000-0000-000000000003', 'Enterprise', 'enterprise', 'Custom solutions for large organizations', 9999, 99990, 'USD',
     '{"storage_gb": 500, "api_calls": -1, "team_members": -1, "priority_support": true, "sla": true, "custom_domain": true}'::jsonb, TRUE)
ON CONFLICT (slug) DO NOTHING;

-- Plan Features
INSERT INTO saas.plan_features (plan_id, feature_key, feature_value, "limit") VALUES
    -- Free plan
    ('a1000000-0000-0000-0000-000000000001', 'storage_gb', '1 GB', 1),
    ('a1000000-0000-0000-0000-000000000001', 'api_calls', '1,000/month', 1000),
    ('a1000000-0000-0000-0000-000000000001', 'team_members', '1 member', 1),
    -- Pro plan
    ('a1000000-0000-0000-0000-000000000002', 'storage_gb', '50 GB', 50),
    ('a1000000-0000-0000-0000-000000000002', 'api_calls', '50,000/month', 50000),
    ('a1000000-0000-0000-0000-000000000002', 'team_members', '10 members', 10),
    ('a1000000-0000-0000-0000-000000000002', 'priority_support', 'Enabled', NULL),
    -- Enterprise plan
    ('a1000000-0000-0000-0000-000000000003', 'storage_gb', '500 GB', 500),
    ('a1000000-0000-0000-0000-000000000003', 'api_calls', 'Unlimited', NULL),
    ('a1000000-0000-0000-0000-000000000003', 'team_members', 'Unlimited', NULL),
    ('a1000000-0000-0000-0000-000000000003', 'priority_support', 'Enabled', NULL),
    ('a1000000-0000-0000-0000-000000000003', 'sla', '99.9% uptime', NULL),
    ('a1000000-0000-0000-0000-000000000003', 'custom_domain', 'Enabled', NULL)
ON CONFLICT DO NOTHING;

-- Sample subscriptions (admin on Enterprise, merchant on Pro, customer on Free)
INSERT INTO saas.subscriptions (id, user_id, plan_id, status, currency, current_period_start, current_period_end) VALUES
    ('a2000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001',
     'a1000000-0000-0000-0000-000000000003', 'active', 'USD',
     NOW() - INTERVAL '15 days', NOW() + INTERVAL '15 days'),
    ('a2000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002',
     'a1000000-0000-0000-0000-000000000002', 'active', 'USD',
     NOW() - INTERVAL '10 days', NOW() + INTERVAL '20 days'),
    ('a2000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003',
     'a1000000-0000-0000-0000-000000000001', 'active', 'USD',
     NOW() - INTERVAL '5 days', NOW() + INTERVAL '25 days')
ON CONFLICT DO NOTHING;
