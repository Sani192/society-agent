CREATE TABLE IF NOT EXISTS channel_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL,
    external_user_id VARCHAR(255) NOT NULL,
    chat_id_or_phone VARCHAR(255),
    first_occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_channel_conversation_user UNIQUE (channel, external_user_id),
    CONSTRAINT ck_channel_conversations_channel CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX IF NOT EXISTS ix_channel_conversations_channel_external_user
    ON channel_conversations (channel, external_user_id);

CREATE TABLE IF NOT EXISTS channel_message_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(255),
    correlation_id VARCHAR(255),
    channel VARCHAR(20) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    provider_message_id VARCHAR(255),
    provider_update_id VARCHAR(255),
    chat_id_or_phone VARCHAR(255),
    external_user_id VARCHAR(255),
    message_text_raw TEXT,
    message_text_redacted TEXT,
    payload_json JSONB,
    http_status INTEGER,
    provider_error_code VARCHAR(100),
    provider_error_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_channel_message_events_channel
        CHECK (channel IN ('whatsapp', 'telegram')),
    CONSTRAINT ck_channel_message_events_direction
        CHECK (direction IN ('inbound', 'outbound', 'status', 'system')),
    CONSTRAINT ck_channel_message_events_event_type
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
        )
);

CREATE INDEX IF NOT EXISTS ix_channel_message_events_channel_external_user_occurred
    ON channel_message_events (channel, external_user_id, occurred_at);

CREATE INDEX IF NOT EXISTS ix_channel_message_events_provider_message_id
    ON channel_message_events (provider_message_id);

CREATE INDEX IF NOT EXISTS ix_channel_message_events_trace_id
    ON channel_message_events (trace_id);

CREATE INDEX IF NOT EXISTS ix_channel_message_events_correlation_id
    ON channel_message_events (correlation_id);


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
