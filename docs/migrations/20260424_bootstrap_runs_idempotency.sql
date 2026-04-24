-- Idempotency guard for bootstrap seed script.
CREATE TABLE IF NOT EXISTS bootstrap_runs (
    "key" TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT bootstrap_runs_status_completed_ck CHECK (status = 'completed')
);

DO $$
BEGIN
    IF to_regclass('public.bootstrap_seed_guard') IS NOT NULL THEN
        INSERT INTO bootstrap_runs ("key", status, completed_at)
        SELECT
            'initial_bootstrap_v1' AS "key",
            'completed' AS status,
            COALESCE(completed_at, NOW()) AS completed_at
        FROM bootstrap_seed_guard
        WHERE seed_key = 'initial_bootstrap'
        ON CONFLICT ("key") DO NOTHING;
    END IF;
END $$;
