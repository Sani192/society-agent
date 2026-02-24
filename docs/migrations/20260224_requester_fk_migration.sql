-- Migrate payment/refund requester references from legacy text columns to
-- canonical requester mapping FKs.

-- 1) Add requester FK columns (nullable for backfill window).
ALTER TABLE payment_requests
    ADD COLUMN requested_by_mapping_id UUID REFERENCES user_flat_mappings(id);

ALTER TABLE refund_requests
    ADD COLUMN requested_by_mapping_id UUID REFERENCES user_flat_mappings(id);

-- 2) Backfill payment_requests.requested_by_mapping_id by matching
--    society_id + normalized requested_by against user_flat_mappings.user_identifier.
WITH normalized_mappings AS (
    SELECT
        id,
        society_id,
        regexp_replace(user_identifier, '[^0-9]', '', 'g') AS normalized_identifier
    FROM user_flat_mappings
), normalized_requests AS (
    SELECT
        id,
        society_id,
        regexp_replace(requested_by, '[^0-9]', '', 'g') AS normalized_requested_by
    FROM payment_requests
)
UPDATE payment_requests pr
SET requested_by_mapping_id = nm.id
FROM normalized_requests nr
JOIN normalized_mappings nm
  ON nm.society_id = nr.society_id
 AND nm.normalized_identifier = nr.normalized_requested_by
WHERE pr.id = nr.id;

-- 3) Backfill refund_requests.requested_by_mapping_id.
WITH normalized_mappings AS (
    SELECT
        id,
        society_id,
        regexp_replace(user_identifier, '[^0-9]', '', 'g') AS normalized_identifier
    FROM user_flat_mappings
), normalized_requests AS (
    SELECT
        id,
        society_id,
        regexp_replace(requested_by, '[^0-9]', '', 'g') AS normalized_requested_by
    FROM refund_requests
)
UPDATE refund_requests rr
SET requested_by_mapping_id = nm.id
FROM normalized_requests nr
JOIN normalized_mappings nm
  ON nm.society_id = nr.society_id
 AND nm.normalized_identifier = nr.normalized_requested_by
WHERE rr.id = nr.id;

-- 4) Fail migration if any row is still unmapped.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM payment_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Unmapped payment_requests rows remain after requester FK backfill';
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM refund_requests WHERE requested_by_mapping_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Unmapped refund_requests rows remain after requester FK backfill';
    END IF;
END
$$;

-- 5) Enforce non-null FK columns.
ALTER TABLE payment_requests
    ALTER COLUMN requested_by_mapping_id SET NOT NULL;

ALTER TABLE refund_requests
    ALTER COLUMN requested_by_mapping_id SET NOT NULL;

-- 6) Drop legacy requester text columns.
ALTER TABLE payment_requests
    DROP COLUMN requested_by;

ALTER TABLE refund_requests
    DROP COLUMN requested_by;
