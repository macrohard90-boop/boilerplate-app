-- UP
-- Add trigger column to page_views to track what caused the pageview
-- (navigated, tab_switch, idle, closed)
ALTER TABLE analytics.page_views ADD COLUMN IF NOT EXISTS trigger varchar(50);

-- DOWN
ALTER TABLE analytics.page_views DROP COLUMN IF EXISTS trigger;
