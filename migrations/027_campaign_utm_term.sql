-- Migration 027: Add utm_term column to campaigns table
-- Required for full UTM tracking support (source, medium, campaign, content, term)

ALTER TABLE marketing.campaigns
    ADD COLUMN IF NOT EXISTS utm_term VARCHAR(200);
