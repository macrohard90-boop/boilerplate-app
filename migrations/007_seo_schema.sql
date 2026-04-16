-- Phase 8: SEO schema — meta tag overrides
-- Depends on: 000_extensions.sql (uuid-ossp)

-- UP

CREATE SCHEMA IF NOT EXISTS seo;

CREATE TABLE seo.meta_overrides (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path        VARCHAR(500) NOT NULL UNIQUE,
    title       VARCHAR(60),
    description VARCHAR(160),
    robots_index BOOLEAN NOT NULL DEFAULT TRUE,
    robots_follow BOOLEAN NOT NULL DEFAULT TRUE,
    canonical_url TEXT,
    created_by  UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_meta_overrides_path ON seo.meta_overrides(path);

-- DOWN
DROP TABLE IF EXISTS seo.meta_overrides CASCADE;
DROP SCHEMA IF EXISTS seo CASCADE;
