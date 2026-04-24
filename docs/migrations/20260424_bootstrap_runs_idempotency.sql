-- Idempotency guard for bootstrap seed script.
CREATE TABLE IF NOT EXISTS bootstrap_runs (
    "key" TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT bootstrap_runs_status_completed_ck CHECK (status = 'completed')
);
