-- Migration 019: SEO keyword research & tracking tables
-- Depends on: 007_seo_schema.sql (seo schema)

-- Target keywords assigned to pages (admin-managed)
CREATE TABLE seo.target_keywords (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword     VARCHAR(200) NOT NULL,
    path        VARCHAR(500),                      -- NULL = site-wide keyword
    priority    SMALLINT DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_target_kw_keyword_path
    ON seo.target_keywords(keyword, COALESCE(path, ''));

-- Auto-discovered keyword suggestions (from providers)
CREATE TABLE seo.keyword_suggestions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword        VARCHAR(200) NOT NULL,
    search_volume  INTEGER,
    competition    REAL,
    trend          VARCHAR(20),
    source         VARCHAR(50) NOT NULL,
    depth_level    SMALLINT DEFAULT 1,             -- 1st/2nd/3rd degree
    seed_keyword   VARCHAR(200),                   -- what seed generated this
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kw_suggestions_keyword ON seo.keyword_suggestions(keyword);
CREATE INDEX idx_kw_suggestions_seed ON seo.keyword_suggestions(seed_keyword);

-- Keyword ranking history (from Search Console or manual entry)
CREATE TABLE seo.keyword_rankings (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword      VARCHAR(200) NOT NULL,
    position     REAL NOT NULL,
    impressions  INTEGER NOT NULL DEFAULT 0,
    clicks       INTEGER NOT NULL DEFAULT 0,
    ctr          REAL NOT NULL DEFAULT 0,
    date         DATE NOT NULL,
    source       VARCHAR(50) NOT NULL DEFAULT 'manual',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kw_rankings_keyword ON seo.keyword_rankings(keyword);
CREATE INDEX idx_kw_rankings_date ON seo.keyword_rankings(date);
CREATE UNIQUE INDEX idx_kw_rankings_unique ON seo.keyword_rankings(keyword, date, source);
