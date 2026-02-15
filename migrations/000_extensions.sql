-- Migration 000: Extensions, schemas, and utility functions
-- Must run before all other migrations.

-- UP
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- PostgreSQL schemas for namespace isolation
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ecommerce;
CREATE SCHEMA IF NOT EXISTS saas;
CREATE SCHEMA IF NOT EXISTS gdpr;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Reusable updated_at trigger function
-- Apply to any table with an updated_at column via:
--   CREATE TRIGGER set_updated_at BEFORE UPDATE ON schema.table
--   FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();
CREATE OR REPLACE FUNCTION core.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- DOWN
DROP FUNCTION IF EXISTS core.update_timestamp() CASCADE;
DROP SCHEMA IF EXISTS analytics CASCADE;
DROP SCHEMA IF EXISTS gdpr CASCADE;
DROP SCHEMA IF EXISTS saas CASCADE;
DROP SCHEMA IF EXISTS ecommerce CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP EXTENSION IF EXISTS "uuid-ossp";
