ALTER TABLE channel_message_events
    DROP CONSTRAINT IF EXISTS ck_channel_message_events_event_type;

ALTER TABLE channel_message_events
    ADD CONSTRAINT ck_channel_message_events_event_type
        CHECK (
            event_type IN (
                'webhook_received',
                'message_parsed',
                'reply_generated',
                'send_attempt',
                'send_result',
                'delivery_status',
                'processing_completed',
                'exception'
            )
        );

CREATE TABLE IF NOT EXISTS channel_dead_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(255) NOT NULL,
    correlation_id VARCHAR(255),
    channel VARCHAR(20) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    payload_json JSONB,
    error_class VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    stack_summary JSONB,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_channel_dead_letters_channel
        CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX IF NOT EXISTS ix_channel_dead_letters_trace_id
    ON channel_dead_letters (trace_id);

CREATE INDEX IF NOT EXISTS ix_channel_dead_letters_correlation_id
    ON channel_dead_letters (correlation_id);
