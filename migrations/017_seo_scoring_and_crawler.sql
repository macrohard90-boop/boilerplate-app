-- Migration 017: SEO scoring, snapshots, and crawler tables
-- Depends on: 007_seo_schema.sql (seo schema + meta_overrides)

-- UP

-- SEO page scores (one per page per scoring run)
CREATE TABLE seo.page_scores (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path         VARCHAR(500) NOT NULL,
    score        INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    rule_results JSONB NOT NULL DEFAULT '[]',
    provider     VARCHAR(50) NOT NULL DEFAULT 'rule_based',
    scored_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_page_scores_path ON seo.page_scores(path);
CREATE INDEX idx_page_scores_scored_at ON seo.page_scores(scored_at);

-- SEO snapshots (full page state at a point in time, for audit trail)
CREATE TABLE seo.page_snapshots (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path       VARCHAR(500) NOT NULL,
    snapshot   JSONB NOT NULL,
    trigger    VARCHAR(50) NOT NULL DEFAULT 'manual',
    changed_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    diff       JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_page_snapshots_path ON seo.page_snapshots(path);
CREATE INDEX idx_page_snapshots_created_at ON seo.page_snapshots(created_at);

-- Crawler results (rendered HTML analysis)
CREATE TABLE seo.crawl_results (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path          VARCHAR(500) NOT NULL,
    status_code   INTEGER,
    rendered_meta JSONB,
    api_meta      JSONB,
    mismatches    JSONB,
    crawled_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crawl_results_path ON seo.crawl_results(path);
CREATE INDEX idx_crawl_results_crawled_at ON seo.crawl_results(crawled_at);

-- DOWN
DROP TABLE IF EXISTS seo.crawl_results CASCADE;
DROP TABLE IF EXISTS seo.page_snapshots CASCADE;
DROP TABLE IF EXISTS seo.page_scores CASCADE;
