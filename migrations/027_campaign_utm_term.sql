-- UP
-- Add utm_term column to campaigns table for full UTM tracking support

ALTER TABLE marketing.campaigns
    ADD COLUMN IF NOT EXISTS utm_term VARCHAR(200);

-- DOWN

ALTER TABLE marketing.campaigns
    DROP COLUMN IF EXISTS utm_term;
