-- Enforce one reminder per (event_id, flat_id, reminder_date).
-- Resolution policy for duplicates:
--   keep the latest created row (created_at DESC NULLS LAST, id DESC),
--   delete older duplicates.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT event_id, flat_id, reminder_date
            FROM payment_reminders
            GROUP BY event_id, flat_id, reminder_date
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE NOTICE 'Duplicate payment_reminders detected. Resolving before adding uniqueness constraint.';
    END IF;
END $$;

CREATE TEMP TABLE tmp_payment_reminder_dedup AS
WITH ranked AS (
    SELECT
        id,
        event_id,
        flat_id,
        reminder_date,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY event_id, flat_id, reminder_date
            ORDER BY created_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM payment_reminders
)
SELECT id AS duplicate_id
FROM ranked
WHERE rn > 1;

DELETE FROM payment_reminders pr
USING tmp_payment_reminder_dedup d
WHERE pr.id = d.duplicate_id;

DROP TABLE tmp_payment_reminder_dedup;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT event_id, flat_id, reminder_date
            FROM payment_reminders
            GROUP BY event_id, flat_id, reminder_date
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE EXCEPTION 'payment_reminders duplicate resolution failed: duplicates still exist';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_payment_reminders_event_flat_date'
    ) THEN
        ALTER TABLE payment_reminders
            ADD CONSTRAINT uq_payment_reminders_event_flat_date
            UNIQUE (event_id, flat_id, reminder_date);
    END IF;
END $$;
