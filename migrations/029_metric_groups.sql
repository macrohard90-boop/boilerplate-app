-- 029_metric_groups.sql
-- Add grouping and ordering to saved custom metrics.

-- UP
ALTER TABLE analytics.saved_metrics
    ADD COLUMN group_name VARCHAR(100) DEFAULT NULL,
    ADD COLUMN display_order INT NOT NULL DEFAULT 0;

CREATE INDEX idx_saved_metrics_group ON analytics.saved_metrics(group_name);

-- DOWN
DROP INDEX IF EXISTS analytics.idx_saved_metrics_group;

ALTER TABLE analytics.saved_metrics
    DROP COLUMN IF EXISTS group_name,
    DROP COLUMN IF EXISTS display_order;
