-- Migration 032: Notifications schema (SMS + WhatsApp channels)
-- Depends on: 001_core_schema.sql (references core.users)
-- Creates the notifications schema for multi-channel messaging

-- UP

CREATE SCHEMA IF NOT EXISTS notifications;

-- SMS/WhatsApp send audit trail
CREATE TABLE notifications.message_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('sms', 'whatsapp')),
    provider VARCHAR(50) NOT NULL DEFAULT '',
    provider_message_id VARCHAR(255),
    to_number VARCHAR(50) NOT NULL,
    template_id VARCHAR(100),
    body_preview VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'sent'
        CHECK (status IN ('sent', 'delivered', 'failed', 'queued')),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_log_user ON notifications.message_log(user_id);
CREATE INDEX idx_message_log_channel ON notifications.message_log(channel);
CREATE INDEX idx_message_log_created ON notifications.message_log(created_at);

-- Event-driven automation dispatch rules (simple: event → channel → template)
CREATE TABLE notifications.automation_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name VARCHAR(100) NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp')),
    template_id VARCHAR(100) NOT NULL,
    delay_seconds INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_automation_rules_event ON notifications.automation_rules(event_name);

-- Seed default rules (disabled — operator enables per channel)
INSERT INTO notifications.automation_rules (event_name, channel, template_id, enabled) VALUES
    ('user.registered', 'sms', 'welcome_sms', false),
    ('user.registered', 'whatsapp', 'welcome_whatsapp', false),
    ('order.completed', 'sms', 'order_confirmation_sms', false);

-- Add phone columns to core.users for SMS/WhatsApp
ALTER TABLE core.users ADD COLUMN IF NOT EXISTS phone VARCHAR(32);
ALTER TABLE core.users ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(32);

-- DOWN
DROP TABLE IF EXISTS notifications.automation_rules;
DROP TABLE IF EXISTS notifications.message_log;
ALTER TABLE core.users DROP COLUMN IF EXISTS phone;
ALTER TABLE core.users DROP COLUMN IF EXISTS whatsapp_number;
DROP SCHEMA IF EXISTS notifications;
