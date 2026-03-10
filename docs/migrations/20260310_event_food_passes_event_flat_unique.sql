-- Enforce one EventFoodPass row per (event_id, flat_id).
-- Resolution policy for pre-existing duplicates:
--   keep the most recently updated row (updated_at DESC, id DESC),
--   delete older duplicates.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT event_id, flat_id
            FROM event_food_passes
            GROUP BY event_id, flat_id
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE NOTICE 'Duplicate event_food_passes detected. Resolving duplicates before adding uniqueness constraint.';
    END IF;
END $$;

CREATE TEMP TABLE tmp_event_food_pass_dedup AS
WITH ranked AS (
    SELECT
        id,
        event_id,
        flat_id,
        updated_at,
        ROW_NUMBER() OVER (
            PARTITION BY event_id, flat_id
            ORDER BY updated_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM event_food_passes
)
SELECT id AS duplicate_id
FROM ranked
WHERE rn > 1;

DELETE FROM event_food_passes efp
USING tmp_event_food_pass_dedup d
WHERE efp.id = d.duplicate_id;

DROP TABLE tmp_event_food_pass_dedup;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT event_id, flat_id
            FROM event_food_passes
            GROUP BY event_id, flat_id
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE EXCEPTION 'event_food_passes duplicate resolution failed: duplicates still exist';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_event_food_passes_event_flat'
    ) THEN
        ALTER TABLE event_food_passes
            ADD CONSTRAINT uq_event_food_passes_event_flat
            UNIQUE (event_id, flat_id);
    END IF;
END $$;
