-- Migration 005: OAuth identities for account linking
-- Depends on: 001_core_schema.sql
-- Always runs (not template-gated)

-- UP

CREATE TABLE core.oauth_identities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

CREATE INDEX idx_oauth_identities_user_id ON core.oauth_identities(user_id);

-- DOWN
DROP TABLE IF EXISTS core.oauth_identities;
