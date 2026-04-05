-- Remove denormalized phone copy from phone-link OTP challenges.
-- Phone is resolved via committee_members join on committee_member_id.

ALTER TABLE committee_member_phone_link_challenges
    DROP COLUMN IF EXISTS phone_number;

DROP INDEX IF EXISTS ix_member_phone_challenges_member;
DROP INDEX IF EXISTS ix_member_phone_challenges_expires;
DROP INDEX IF EXISTS ix_member_phone_challenges_consumed;

CREATE INDEX IF NOT EXISTS ix_member_phone_challenges_member_lifecycle
    ON committee_member_phone_link_challenges(committee_member_id, expires_at, consumed_at);
