-- Audit and observability hardening updates

ALTER TABLE channel_message_events
    ADD COLUMN IF NOT EXISTS society_id UUID REFERENCES societies(id);

CREATE INDEX IF NOT EXISTS ix_channel_message_events_society_id
    ON channel_message_events (society_id);

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS trace_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS metadata_json JSONB,
    ADD COLUMN IF NOT EXISTS old_values_json JSONB,
    ADD COLUMN IF NOT EXISTS new_values_json JSONB;

CREATE INDEX IF NOT EXISTS ix_audit_logs_source_performed_at
    ON audit_logs (source, performed_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_trace_id
    ON audit_logs (trace_id);
