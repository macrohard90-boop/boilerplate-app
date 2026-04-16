-- GEO (Generative Engine Optimization) scoring tables
-- Stores page-level GEO scores with dimension breakdowns and rule results.

-- UP

CREATE TABLE IF NOT EXISTS seo.geo_page_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path VARCHAR(500) NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    dimension_scores JSONB,
    rule_results JSONB NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'geo_rule_based',
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geo_scores_path ON seo.geo_page_scores(path);
CREATE INDEX IF NOT EXISTS idx_geo_scores_scored_at ON seo.geo_page_scores(scored_at DESC);

-- DOWN
DROP TABLE IF EXISTS seo.geo_page_scores CASCADE;
