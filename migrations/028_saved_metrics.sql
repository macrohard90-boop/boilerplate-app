-- Migration 028: Saved custom metrics for analytics
-- Depends on: 004_analytics_schema.sql (analytics schema), 001_core_schema.sql (core.users)

-- UP

CREATE TABLE analytics.saved_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    sql_query TEXT NOT NULL,
    visualization_type VARCHAR(30) NOT NULL DEFAULT 'table'
        CHECK (visualization_type IN ('table', 'line_chart', 'bar_chart', 'number')),
    created_by UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_saved_metrics_created_by ON analytics.saved_metrics(created_by);

-- DOWN
DROP TABLE IF EXISTS analytics.saved_metrics CASCADE;
