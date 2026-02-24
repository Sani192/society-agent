-- Migrate payment/refund requester references from text phone to user_flat_mappings FK.
-- Phase 1: Add new nullable FK columns while legacy requested_by still exists.
ALTER TABLE payment_requests
    ADD COLUMN IF NOT EXISTS requested_by_mapping_id UUID REFERENCES user_flat_mappings(id);

ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS requested_by_mapping_id UUID REFERENCES user_flat_mappings(id);

-- Phase 2: Backfill FK columns from society_id + normalized requested_by.
WITH normalized_mappings AS (
    SELECT
        id,
        society_id,
        regexp_replace(user_identifier, '[^0-9]', '', 'g') AS normalized_identifier
    FROM user_flat_mappings
),
normalized_requests AS (
    SELECT
        id,
        society_id,
        regexp_replace(requested_by, '[^0-9]', '', 'g') AS normalized_requested_by
    FROM payment_requests
    WHERE requested_by_mapping_id IS NULL
)
UPDATE payment_requests pr
SET requested_by_mapping_id = nm.id
FROM normalized_requests nr
JOIN normalized_mappings nm
  ON nm.society_id = nr.society_id
 AND nm.normalized_identifier = nr.normalized_requested_by
WHERE pr.id = nr.id;

WITH normalized_mappings AS (
    SELECT
        id,
        society_id,
        regexp_replace(user_identifier, '[^0-9]', '', 'g') AS normalized_identifier
    FROM user_flat_mappings
),
normalized_requests AS (
    SELECT
        id,
        society_id,
        regexp_replace(requested_by, '[^0-9]', '', 'g') AS normalized_requested_by
    FROM refund_requests
    WHERE requested_by_mapping_id IS NULL
)
UPDATE refund_requests rr
SET requested_by_mapping_id = nm.id
FROM normalized_requests nr
JOIN normalized_mappings nm
  ON nm.society_id = nr.society_id
 AND nm.normalized_identifier = nr.normalized_requested_by
WHERE rr.id = nr.id;

-- Phase 3: Enforce non-null only when all rows are backfilled successfully.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM payment_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        ALTER TABLE payment_requests
            ALTER COLUMN requested_by_mapping_id SET NOT NULL;
    ELSE
        RAISE NOTICE 'payment_requests.requested_by_mapping_id has NULL rows; skipping NOT NULL + drop for now';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM refund_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        ALTER TABLE refund_requests
            ALTER COLUMN requested_by_mapping_id SET NOT NULL;
    ELSE
        RAISE NOTICE 'refund_requests.requested_by_mapping_id has NULL rows; skipping NOT NULL + drop for now';
    END IF;
END
$$;

-- Phase 4: Drop legacy text columns only after FK backfill is complete.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM payment_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        ALTER TABLE payment_requests DROP COLUMN IF EXISTS requested_by;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM refund_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        ALTER TABLE refund_requests DROP COLUMN IF EXISTS requested_by;
    END IF;
END
$$;
