CREATE TABLE IF NOT EXISTS inbound_webhook_envelopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL,
    payload_json JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_inbound_webhook_envelopes_channel
        CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX IF NOT EXISTS ix_inbound_webhook_envelopes_channel
    ON inbound_webhook_envelopes (channel);

CREATE INDEX IF NOT EXISTS ix_inbound_webhook_envelopes_payload_hash
    ON inbound_webhook_envelopes (payload_hash);

CREATE INDEX IF NOT EXISTS ix_inbound_webhook_envelopes_status
    ON inbound_webhook_envelopes (status);


CREATE TABLE IF NOT EXISTS webhook_idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL,
    provider_message_id VARCHAR(255),
    provider_update_id VARCHAR(255),
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_webhook_idempotency_keys_channel
        CHECK (channel IN ('whatsapp', 'telegram')),
    CONSTRAINT uq_webhook_idempotency_keys_channel_key
        UNIQUE (channel, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_webhook_idempotency_keys_lookup
    ON webhook_idempotency_keys (channel, provider_message_id, provider_update_id);
