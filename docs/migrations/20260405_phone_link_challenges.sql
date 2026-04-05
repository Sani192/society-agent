-- Phone-link OTP challenge storage for secure Telegram onboarding

CREATE TABLE IF NOT EXISTS committee_member_phone_link_challenges (
    id UUID PRIMARY KEY,
    committee_member_id UUID NOT NULL REFERENCES committee_members(id) ON DELETE CASCADE,
    channel_type VARCHAR(50) NOT NULL,
    external_user_id VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    phone_number VARCHAR(20) NOT NULL,
    otp_hash VARCHAR(64) NOT NULL,
    otp_salt VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ,
    attempts_used INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT ck_member_phone_challenge_channel CHECK (channel_type IN ('whatsapp', 'telegram'))
);

CREATE INDEX IF NOT EXISTS ix_member_phone_challenges_member ON committee_member_phone_link_challenges(committee_member_id);
CREATE INDEX IF NOT EXISTS ix_member_phone_challenges_channel ON committee_member_phone_link_challenges(channel_type, external_user_id);
CREATE INDEX IF NOT EXISTS ix_member_phone_challenges_expires ON committee_member_phone_link_challenges(expires_at);
CREATE INDEX IF NOT EXISTS ix_member_phone_challenges_consumed ON committee_member_phone_link_challenges(consumed_at);
