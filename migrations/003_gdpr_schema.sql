-- Migration 003: GDPR schema (7 tables — always present)
-- Depends on: 001_core_schema.sql (references core.users)

-- UP

-- Consent Records
CREATE TABLE gdpr.consent_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    consent_type VARCHAR(30) NOT NULL CHECK (consent_type IN (
        'marketing_email', 'transactional_email', 'third_party_sharing',
        'analytics', 'cookies_analytics', 'cookies_marketing'
    )),
    granted BOOLEAN NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consent_records_user_id ON gdpr.consent_records(user_id);
CREATE INDEX idx_consent_records_consent_type ON gdpr.consent_records(consent_type);
CREATE INDEX idx_consent_records_user_type ON gdpr.consent_records(user_id, consent_type);
CREATE INDEX idx_consent_records_created_at ON gdpr.consent_records(created_at);

-- Data Export Requests
CREATE TABLE gdpr.data_export_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'expired', 'failed')),
    file_url TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_data_export_user_id ON gdpr.data_export_requests(user_id);
CREATE INDEX idx_data_export_status ON gdpr.data_export_requests(status);

-- Deletion Requests
CREATE TABLE gdpr.deletion_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'grace_period', 'processing', 'completed', 'cancelled')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    grace_period_ends TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_deletion_requests_user_id ON gdpr.deletion_requests(user_id);
CREATE INDEX idx_deletion_requests_status ON gdpr.deletion_requests(status);

-- Cookie Preferences
CREATE TABLE gdpr.cookie_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE CASCADE,
    session_id VARCHAR(255),
    necessary BOOLEAN NOT NULL DEFAULT TRUE,
    analytics BOOLEAN NOT NULL DEFAULT FALSE,
    marketing BOOLEAN NOT NULL DEFAULT FALSE,
    preferences BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cookie_prefs_user_id ON gdpr.cookie_preferences(user_id);
CREATE INDEX idx_cookie_prefs_session_id ON gdpr.cookie_preferences(session_id);
CREATE INDEX idx_cookie_prefs_created_at ON gdpr.cookie_preferences(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON gdpr.cookie_preferences
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Consent Audit Log
CREATE TABLE gdpr.consent_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    consent_type VARCHAR(30) NOT NULL,
    old_value BOOLEAN,
    new_value BOOLEAN,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consent_audit_user_id ON gdpr.consent_audit_log(user_id);
CREATE INDEX idx_consent_audit_consent_type ON gdpr.consent_audit_log(consent_type);
CREATE INDEX idx_consent_audit_created_at ON gdpr.consent_audit_log(created_at);

-- Email Preferences (app-side source of truth, synced to email provider)
CREATE TABLE gdpr.email_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES core.users(id) ON DELETE CASCADE,
    marketing_email BOOLEAN NOT NULL DEFAULT FALSE,
    transactional_email BOOLEAN NOT NULL DEFAULT TRUE,
    suppressed_at TIMESTAMPTZ,
    suppression_reason VARCHAR(30) CHECK (suppression_reason IN (
        'bounce', 'complaint', 'manual', 'deletion_request'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_email_prefs_user_id ON gdpr.email_preferences(user_id);
CREATE INDEX idx_email_prefs_suppressed ON gdpr.email_preferences(suppressed_at) WHERE suppressed_at IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON gdpr.email_preferences
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Email Events (audit trail)
CREATE TABLE gdpr.email_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    email_type VARCHAR(30) NOT NULL CHECK (email_type IN ('marketing_email', 'transactional_email')),
    template_id VARCHAR(100) NOT NULL,
    provider VARCHAR(50),
    provider_message_id VARCHAR(255),
    consent_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'sent', 'delivered', 'bounced', 'complained', 'skipped'
    )),
    skip_reason VARCHAR(30) CHECK (skip_reason IN ('no_consent', 'suppressed')),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_email_events_user_id ON gdpr.email_events(user_id);
CREATE INDEX idx_email_events_email_type ON gdpr.email_events(email_type);
CREATE INDEX idx_email_events_status ON gdpr.email_events(status);
CREATE INDEX idx_email_events_provider_msg ON gdpr.email_events(provider_message_id);
CREATE INDEX idx_email_events_created_at ON gdpr.email_events(created_at);

-- DOWN
DROP TABLE IF EXISTS gdpr.email_events CASCADE;
DROP TABLE IF EXISTS gdpr.email_preferences CASCADE;
DROP TABLE IF EXISTS gdpr.consent_audit_log CASCADE;
DROP TABLE IF EXISTS gdpr.cookie_preferences CASCADE;
DROP TABLE IF EXISTS gdpr.deletion_requests CASCADE;
DROP TABLE IF EXISTS gdpr.data_export_requests CASCADE;
DROP TABLE IF EXISTS gdpr.consent_records CASCADE;
