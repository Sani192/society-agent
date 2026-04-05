-- Remove denormalized society_id columns where event_id already determines society.
-- This supersedes trigger guards from 20260224_society_id_consistency_guards.sql.

BEGIN;

-- 1) Remove legacy consistency triggers/function.
DROP TRIGGER IF EXISTS trg_payment_requests_society_guard ON payment_requests;
DROP TRIGGER IF EXISTS trg_refund_requests_society_guard ON refund_requests;
DROP TRIGGER IF EXISTS trg_event_contributions_society_guard ON event_contributions;
DROP TRIGGER IF EXISTS trg_payment_reminders_society_guard ON payment_reminders;
DROP FUNCTION IF EXISTS enforce_society_id_consistency();

-- 2) Drop indexes that depend on denormalized society_id.
DROP INDEX IF EXISTS ix_payment_requests_society_id;
DROP INDEX IF EXISTS ix_refund_requests_society_id;
DROP INDEX IF EXISTS ix_event_contributions_society_id;
DROP INDEX IF EXISTS ix_payment_reminders_society_id;
DROP INDEX IF EXISTS ix_society_balance_society_id;

-- 3) Drop FK constraints that depend on the denormalized society_id columns.
ALTER TABLE payment_requests DROP CONSTRAINT IF EXISTS payment_requests_society_id_fkey;
ALTER TABLE refund_requests DROP CONSTRAINT IF EXISTS refund_requests_society_id_fkey;
ALTER TABLE event_contributions DROP CONSTRAINT IF EXISTS event_contributions_society_id_fkey;
ALTER TABLE payment_reminders DROP CONSTRAINT IF EXISTS payment_reminders_society_id_fkey;
ALTER TABLE society_balance DROP CONSTRAINT IF EXISTS society_balance_society_id_fkey;

-- 4) Drop denormalized columns.
ALTER TABLE payment_requests DROP COLUMN IF EXISTS society_id;
ALTER TABLE refund_requests DROP COLUMN IF EXISTS society_id;
ALTER TABLE event_contributions DROP COLUMN IF EXISTS society_id;
ALTER TABLE payment_reminders DROP COLUMN IF EXISTS society_id;
ALTER TABLE society_balance DROP COLUMN IF EXISTS society_id;

-- 5) Add/strengthen constraints and indexes keyed on event/flat business identity.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_payment_requests_event_request_code'
    ) THEN
        ALTER TABLE payment_requests
            ADD CONSTRAINT uq_payment_requests_event_request_code
            UNIQUE (event_id, request_code);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_refund_requests_event_request_code'
    ) THEN
        ALTER TABLE refund_requests
            ADD CONSTRAINT uq_refund_requests_event_request_code
            UNIQUE (event_id, request_code);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_event_contributions_event_code'
    ) THEN
        ALTER TABLE event_contributions
            ADD CONSTRAINT uq_event_contributions_event_code
            UNIQUE (event_id, contribution_code);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_society_balance_event'
    ) THEN
        ALTER TABLE society_balance
            ADD CONSTRAINT uq_society_balance_event
            UNIQUE (event_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_payment_requests_event_flat
    ON payment_requests (event_id, flat_id);
CREATE INDEX IF NOT EXISTS ix_payment_requests_event_status
    ON payment_requests (event_id, status);

CREATE INDEX IF NOT EXISTS ix_refund_requests_event_flat
    ON refund_requests (event_id, flat_id);
CREATE INDEX IF NOT EXISTS ix_refund_requests_event_status
    ON refund_requests (event_id, status);

CREATE INDEX IF NOT EXISTS ix_event_contributions_event_flat
    ON event_contributions (event_id, flat_id);
CREATE INDEX IF NOT EXISTS ix_event_contributions_event_created_at
    ON event_contributions (event_id, created_at);

CREATE INDEX IF NOT EXISTS ix_payment_reminders_event_flat
    ON payment_reminders (event_id, flat_id);
CREATE INDEX IF NOT EXISTS ix_payment_reminders_event_date
    ON payment_reminders (event_id, reminder_date);

COMMIT;
