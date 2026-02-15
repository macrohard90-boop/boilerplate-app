-- Migration 004: Analytics schema (6 tables — optional module)
-- Depends on: 001_core_schema.sql (references core.users)
-- Only runs when ENABLE_TRACKING=true
-- FUTURE: range partition on created_at (monthly) for page_views, analytics_sessions, events
-- RETENTION: consider archival policy for rows older than N months

-- UP

-- Page Views
CREATE TABLE analytics.page_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    session_id VARCHAR(255) NOT NULL,
    path VARCHAR(2048) NOT NULL,
    referrer VARCHAR(2048),
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_page_views_user_id ON analytics.page_views(user_id);
CREATE INDEX idx_page_views_session_id ON analytics.page_views(session_id);
CREATE INDEX idx_page_views_path ON analytics.page_views(path);
CREATE INDEX idx_page_views_created_at ON analytics.page_views(created_at);

-- Analytics Sessions (renamed from "sessions" to avoid collision with core.sessions)
CREATE TABLE analytics.analytics_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    page_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_analytics_sessions_user_id ON analytics.analytics_sessions(user_id);
CREATE INDEX idx_analytics_sessions_session_id ON analytics.analytics_sessions(session_id);
CREATE INDEX idx_analytics_sessions_started_at ON analytics.analytics_sessions(started_at);

-- Events
CREATE TABLE analytics.events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    session_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_user_id ON analytics.events(user_id);
CREATE INDEX idx_events_session_id ON analytics.events(session_id);
CREATE INDEX idx_events_event_type ON analytics.events(event_type);
CREATE INDEX idx_events_created_at ON analytics.events(created_at);

-- User Agents
CREATE TABLE analytics.user_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    raw TEXT NOT NULL,
    browser VARCHAR(100),
    browser_version VARCHAR(50),
    os VARCHAR(100),
    device_type VARCHAR(30) CHECK (device_type IN ('desktop', 'mobile', 'tablet', 'bot', 'unknown'))
);

CREATE INDEX idx_user_agents_session_id ON analytics.user_agents(session_id);
CREATE INDEX idx_user_agents_device_type ON analytics.user_agents(device_type);

-- Referral Sources
CREATE TABLE analytics.referral_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    source VARCHAR(255),
    medium VARCHAR(100),
    campaign VARCHAR(255)
);

CREATE INDEX idx_referral_sources_session_id ON analytics.referral_sources(session_id);
CREATE INDEX idx_referral_sources_source ON analytics.referral_sources(source);

-- UTM Tracking
CREATE TABLE analytics.utm_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    utm_source VARCHAR(255),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(255),
    utm_content VARCHAR(255),
    utm_term VARCHAR(255)
);

CREATE INDEX idx_utm_tracking_session_id ON analytics.utm_tracking(session_id);
CREATE INDEX idx_utm_tracking_source ON analytics.utm_tracking(utm_source);

-- DOWN
DROP TABLE IF EXISTS analytics.utm_tracking CASCADE;
DROP TABLE IF EXISTS analytics.referral_sources CASCADE;
DROP TABLE IF EXISTS analytics.user_agents CASCADE;
DROP TABLE IF EXISTS analytics.events CASCADE;
DROP TABLE IF EXISTS analytics.analytics_sessions CASCADE;
DROP TABLE IF EXISTS analytics.page_views CASCADE;
