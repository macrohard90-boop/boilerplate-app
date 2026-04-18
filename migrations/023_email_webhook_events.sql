-- UP
-- Webhook idempotency table for email provider webhooks (bounce, complaint, delivery)
CREATE TABLE IF NOT EXISTS gdpr.email_webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_webhook_events_created
    ON gdpr.email_webhook_events(created_at);

-- DOWN
DROP TABLE IF EXISTS gdpr.email_webhook_events CASCADE;
