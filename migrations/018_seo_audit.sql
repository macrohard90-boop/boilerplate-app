-- Migration 018: SEO site audit table
-- Depends on: 007_seo_schema.sql (seo schema), 001_core_schema.sql (core.users)

-- Full site audit reports (one per audit run)
CREATE TABLE seo.site_audits (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checks       JSONB NOT NULL DEFAULT '[]',
    summary      JSONB NOT NULL DEFAULT '{}',
    score        INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    triggered_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_site_audits_created ON seo.site_audits(created_at);
