-- Normalize pending_users to store flat_id only.
-- Adds flat_id, backfills existing rows, enforces non-null, and removes legacy flat_number.

ALTER TABLE pending_users
    ADD COLUMN IF NOT EXISTS flat_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_pending_users_flat_id'
    ) THEN
        ALTER TABLE pending_users
            ADD CONSTRAINT fk_pending_users_flat_id
            FOREIGN KEY (flat_id) REFERENCES flats(id);
    END IF;
END $$;

UPDATE pending_users pu
SET flat_id = f.id
FROM flats f
WHERE pu.flat_id IS NULL
  AND pu.society_id = f.society_id
  AND pu.flat_number = f.flat_number;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pending_users WHERE flat_id IS NULL) THEN
        RAISE EXCEPTION 'pending_users.flat_id backfill incomplete: found rows without matching flats';
    END IF;
END $$;

ALTER TABLE pending_users
    ALTER COLUMN flat_id SET NOT NULL;

ALTER TABLE pending_users
    DROP COLUMN IF EXISTS flat_number;
