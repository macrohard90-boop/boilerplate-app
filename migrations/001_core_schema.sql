-- Migration 001: Core schema (7 tables — always present)
-- Depends on: 000_extensions.sql
-- RETENTION: consider archival policy for audit_log rows older than N months

-- UP

-- Roles table (no FK dependencies)
CREATE TABLE core.roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users table
CREATE TABLE core.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE RESTRICT,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON core.users(email);
CREATE INDEX idx_users_role_id ON core.users(role_id);
CREATE INDEX idx_users_is_active ON core.users(is_active);
CREATE INDEX idx_users_created_at ON core.users(created_at);
CREATE INDEX idx_users_deleted_at ON core.users(deleted_at) WHERE deleted_at IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Permissions table
CREATE TABLE core.permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE CASCADE,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(role_id, resource, action)
);

CREATE INDEX idx_permissions_role_id ON core.permissions(role_id);

-- Sessions table
CREATE TABLE core.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    device VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_sessions_user_id ON core.sessions(user_id);
CREATE INDEX idx_sessions_created_at ON core.sessions(created_at);
CREATE INDEX idx_sessions_expires_at ON core.sessions(expires_at);

-- API Keys table
CREATE TABLE core.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    rate_limit INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user_id ON core.api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON core.api_keys(key_hash);
CREATE INDEX idx_api_keys_is_active ON core.api_keys(is_active);

-- Audit Log table
-- FUTURE: range partition on created_at (monthly)
CREATE TABLE core.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES core.api_keys(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id UUID,
    ip_address VARCHAR(45),
    payload_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON core.audit_log(user_id);
CREATE INDEX idx_audit_log_api_key_id ON core.audit_log(api_key_id);
CREATE INDEX idx_audit_log_action ON core.audit_log(action);
CREATE INDEX idx_audit_log_resource ON core.audit_log(resource);
CREATE INDEX idx_audit_log_created_at ON core.audit_log(created_at);
CREATE INDEX idx_audit_log_user_action ON core.audit_log(user_id, action);

-- Exchange Rates table
CREATE TABLE core.exchange_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    base_currency CHAR(3) NOT NULL,
    target_currency CHAR(3) NOT NULL,
    rate NUMERIC(12, 6) NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'manual',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(base_currency, target_currency)
);

CREATE INDEX idx_exchange_rates_base ON core.exchange_rates(base_currency);
CREATE INDEX idx_exchange_rates_created_at ON core.exchange_rates(created_at);

-- DOWN
DROP TABLE IF EXISTS core.exchange_rates CASCADE;
DROP TABLE IF EXISTS core.audit_log CASCADE;
DROP TABLE IF EXISTS core.api_keys CASCADE;
DROP TABLE IF EXISTS core.sessions CASCADE;
DROP TABLE IF EXISTS core.permissions CASCADE;
DROP TABLE IF EXISTS core.users CASCADE;
DROP TABLE IF EXISTS core.roles CASCADE;
