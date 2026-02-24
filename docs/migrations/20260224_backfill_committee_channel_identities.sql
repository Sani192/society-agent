-- Backfill committee_member_channel_identities for legacy rows before enforcing
-- strict identity-only committee resolution.
--
-- This inserts a WhatsApp identity for active committee members that currently
-- have no WhatsApp channel identity row.

INSERT INTO committee_member_channel_identities (
    id,
    committee_member_id,
    channel_type,
    external_user_id,
    username,
    is_verified,
    created_at
)
SELECT
    gen_random_uuid(),
    cm.id,
    'whatsapp',
    cm.phone_number,
    NULL,
    TRUE,
    NOW()
FROM committee_members cm
WHERE cm.is_active = TRUE
  AND cm.phone_number IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM committee_member_channel_identities ci
      WHERE ci.committee_member_id = cm.id
        AND ci.channel_type = 'whatsapp'
  );
