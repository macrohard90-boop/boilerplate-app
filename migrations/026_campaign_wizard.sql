-- UP
-- Campaign wizard: A/B variants, audience segments, UTM tracking

-- Campaign variants (A/B/C/D+ split testing)
CREATE TABLE marketing.campaign_variants (
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
);

CREATE INDEX idx_campaign_variants_campaign ON marketing.campaign_variants(campaign_id);

CREATE TRIGGER set_campaign_variants_updated_at BEFORE UPDATE ON marketing.campaign_variants
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Reusable audience segments with structured filter criteria
CREATE TABLE marketing.audience_segments (
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
);

CREATE INDEX idx_audience_segments_system ON marketing.audience_segments(is_system);

CREATE TRIGGER set_audience_segments_updated_at BEFORE UPDATE ON marketing.audience_segments
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Links campaigns (or specific variants) to audience segments
CREATE TABLE marketing.campaign_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES marketing.audience_segments(id),
    variant_label VARCHAR(10),
    UNIQUE (campaign_id, segment_id, variant_label)
);

CREATE INDEX idx_campaign_segments_campaign ON marketing.campaign_segments(campaign_id);
CREATE INDEX idx_campaign_segments_segment ON marketing.campaign_segments(segment_id);

-- Add UTM tracking columns to campaigns
ALTER TABLE marketing.campaigns
    ADD COLUMN utm_source VARCHAR(100),
    ADD COLUMN utm_medium VARCHAR(100) DEFAULT 'email',
    ADD COLUMN utm_campaign VARCHAR(200),
    ADD COLUMN utm_content VARCHAR(200);

-- Seed system audience segments
INSERT INTO marketing.audience_segments (name, description, filters, is_system) VALUES
    ('All Subscribers', 'Everyone with marketing email consent', '{}'::jsonb, TRUE),
    ('Champions', 'Highest-value repeat buyers', '{"rfm_segment": ["champion"]}'::jsonb, TRUE),
    ('Loyal Customers', 'Frequent buyers with strong purchase history', '{"rfm_segment": ["loyal"]}'::jsonb, TRUE),
    ('At-Risk Customers', 'Declining or inactive buyers who may churn', '{"rfm_segment": ["at_risk", "hibernating"]}'::jsonb, TRUE),
    ('New Customers', 'Recently signed up with no or few purchases', '{"rfm_segment": ["new"]}'::jsonb, TRUE),
    ('Cart Abandoners', 'Users with abandoned shopping carts', '{"cart_status": "abandoned"}'::jsonb, TRUE),
    ('High Spenders', 'Customers who have spent over $100 lifetime', '{"total_spent_min": 10000}'::jsonb, TRUE),
    ('Recent Buyers', 'Purchased within the last 30 days', '{"last_purchase_days_max": 30}'::jsonb, TRUE);

-- DOWN
DROP TABLE IF EXISTS marketing.campaign_segments CASCADE;
DROP TABLE IF EXISTS marketing.audience_segments CASCADE;
DROP TABLE IF EXISTS marketing.campaign_variants CASCADE;
ALTER TABLE marketing.campaigns
    DROP COLUMN IF EXISTS utm_source,
    DROP COLUMN IF EXISTS utm_medium,
    DROP COLUMN IF EXISTS utm_campaign,
    DROP COLUMN IF EXISTS utm_content;
