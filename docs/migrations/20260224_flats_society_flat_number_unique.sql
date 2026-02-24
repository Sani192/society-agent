-- Enforce unique flat_number per society in flats.
-- 1) Detect duplicate flat rows by (society_id, flat_number)
-- 2) Re-point foreign key references to canonical flat IDs
-- 3) Delete duplicate flat rows
-- 4) Add unique constraint on (society_id, flat_number)

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT society_id, flat_number
            FROM flats
            GROUP BY society_id, flat_number
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE NOTICE 'Duplicate flats detected. Resolving duplicates before adding uniqueness constraint.';
    END IF;
END $$;

CREATE TEMP TABLE tmp_flat_dedup AS
WITH ranked AS (
    SELECT
        id,
        society_id,
        flat_number,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY society_id, flat_number
            ORDER BY created_at ASC NULLS LAST, id ASC
        ) AS rn,
        FIRST_VALUE(id) OVER (
            PARTITION BY society_id, flat_number
            ORDER BY created_at ASC NULLS LAST, id ASC
        ) AS canonical_id
    FROM flats
)
SELECT
    id AS duplicate_id,
    canonical_id
FROM ranked
WHERE rn > 1;

DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'flat_id'
          AND table_name <> 'flats'
    LOOP
        EXECUTE format(
            'UPDATE %I t
             SET flat_id = d.canonical_id
             FROM tmp_flat_dedup d
             WHERE t.flat_id = d.duplicate_id',
            rec.table_name
        );
    END LOOP;
END $$;

DELETE FROM flats f
USING tmp_flat_dedup d
WHERE f.id = d.duplicate_id;

DROP TABLE tmp_flat_dedup;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT society_id, flat_number
            FROM flats
            GROUP BY society_id, flat_number
            HAVING COUNT(*) > 1
        ) dups
    ) THEN
        RAISE EXCEPTION 'flats duplicate resolution failed: duplicates still exist';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_flats_society_flat_number'
    ) THEN
        ALTER TABLE flats
            ADD CONSTRAINT uq_flats_society_flat_number
            UNIQUE (society_id, flat_number);
    END IF;
END $$;
