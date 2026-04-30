-- 041_email_events_sending_status.sql
-- Add 'sending' status to email_events for Brevo webhook confirmation flow

-- UP

ALTER TABLE gdpr.email_events DROP CONSTRAINT IF EXISTS email_events_status_check;
ALTER TABLE gdpr.email_events ADD CONSTRAINT email_events_status_check
  CHECK (status IN ('queued', 'sending', 'sent', 'delivered', 'bounced', 'complained', 'skipped'));

-- DOWN

ALTER TABLE gdpr.email_events DROP CONSTRAINT IF EXISTS email_events_status_check;
ALTER TABLE gdpr.email_events ADD CONSTRAINT email_events_status_check
  CHECK (status IN ('queued', 'sent', 'delivered', 'bounced', 'complained', 'skipped'));
