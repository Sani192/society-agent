-- Announcement deliveries no longer persist recipient identifiers.
-- Recipient identifiers are resolved at send-time from (member_identity_id, channel).

BEGIN;

ALTER TABLE announcement_deliveries
    DROP COLUMN IF EXISTS recipient_id;

COMMIT;
