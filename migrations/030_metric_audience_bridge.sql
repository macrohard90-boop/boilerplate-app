-- 030_metric_audience_bridge.sql
-- Bridge analytics custom metrics to campaign audience system.
-- Audience-flagged metrics (SQL queries returning user_id) appear as
-- selectable audiences in the Campaign Wizard.

-- UP
ALTER TABLE analytics.saved_metrics
    ADD COLUMN is_audience BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE marketing.audience_segments
    ADD COLUMN metric_id UUID REFERENCES analytics.saved_metrics(id) ON DELETE SET NULL;

CREATE INDEX idx_saved_metrics_audience
    ON analytics.saved_metrics(is_audience) WHERE is_audience = TRUE;
CREATE INDEX idx_audience_segments_metric
    ON marketing.audience_segments(metric_id) WHERE metric_id IS NOT NULL;

-- DOWN
DROP INDEX IF EXISTS marketing.idx_audience_segments_metric;
DROP INDEX IF EXISTS analytics.idx_saved_metrics_audience;

ALTER TABLE marketing.audience_segments DROP COLUMN IF EXISTS metric_id;
ALTER TABLE analytics.saved_metrics DROP COLUMN IF EXISTS is_audience;
