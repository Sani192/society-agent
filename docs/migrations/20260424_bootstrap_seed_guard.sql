CREATE TABLE IF NOT EXISTS bootstrap_seed_guard (
    seed_key TEXT PRIMARY KEY,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
