-- Drop deprecated denormalized phone number from committee_member_channel_identities.
-- Run this on existing databases before deploying code that removes the ORM field.

DROP INDEX IF EXISTS ix_committee_member_channel_identities_phone_number;
ALTER TABLE committee_member_channel_identities DROP COLUMN IF EXISTS phone_number;
