-- Page registry: single source of truth for all known pages.
-- Populated by filesystem scan + DB queries on startup / admin sync.

-- UP

CREATE TABLE IF NOT EXISTS seo.page_registry (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    path         VARCHAR(500) NOT NULL UNIQUE,
    source       VARCHAR(50) NOT NULL DEFAULT 'manual',
    -- source: 'filesystem', 'database', 'manual', 'override'
    is_dynamic   BOOLEAN NOT NULL DEFAULT FALSE,
    -- TRUE for template routes like [slug] (not individually scored)
    changefreq   VARCHAR(20) NOT NULL DEFAULT 'monthly',
    priority     REAL NOT NULL DEFAULT 0.5,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_page_registry_path ON seo.page_registry(path);
CREATE INDEX IF NOT EXISTS idx_page_registry_source ON seo.page_registry(source);

-- DOWN
DROP TABLE IF EXISTS seo.page_registry CASCADE;
