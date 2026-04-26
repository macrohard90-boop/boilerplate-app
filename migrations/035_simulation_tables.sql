-- Simulation result storage for the simulation report tab
-- UP

CREATE TABLE IF NOT EXISTS analytics.simulation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    target_url VARCHAR(255),
    user_count INT,
    status VARCHAR(20) DEFAULT 'running',
    sections_run TEXT[],
    summary JSONB DEFAULT '{}',
    phase_results JSONB DEFAULT '[]',
    check_results JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.simulation_user_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES analytics.simulation_runs(id) ON DELETE CASCADE,
    user_email VARCHAR(255),
    persona VARCHAR(50),
    actions JSONB DEFAULT '[]',
    events_expected INT DEFAULT 0,
    events_recorded INT DEFAULT 0,
    result VARCHAR(10)
);

CREATE INDEX IF NOT EXISTS idx_sim_user_results_run_id
    ON analytics.simulation_user_results(run_id);

-- DOWN

DROP TABLE IF EXISTS analytics.simulation_user_results CASCADE;
DROP TABLE IF EXISTS analytics.simulation_runs CASCADE;
