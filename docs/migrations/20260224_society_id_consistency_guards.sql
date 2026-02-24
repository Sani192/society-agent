-- Keep denormalized society_id for read/query performance.
-- Guard integrity for tables that also carry event_id and/or flat_id.

CREATE OR REPLACE FUNCTION enforce_society_id_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_society UUID;
    flat_society UUID;
BEGIN
    IF NEW.event_id IS NOT NULL THEN
        SELECT e.society_id INTO event_society
        FROM events e
        WHERE e.id = NEW.event_id;

        IF event_society IS NULL THEN
            RAISE EXCEPTION 'Invalid event_id % for table %', NEW.event_id, TG_TABLE_NAME;
        END IF;

        IF NEW.society_id <> event_society THEN
            RAISE EXCEPTION
                'society_id % does not match events.society_id % for event_id % in %',
                NEW.society_id,
                event_society,
                NEW.event_id,
                TG_TABLE_NAME;
        END IF;
    END IF;

    IF NEW.flat_id IS NOT NULL THEN
        SELECT f.society_id INTO flat_society
        FROM flats f
        WHERE f.id = NEW.flat_id;

        IF flat_society IS NULL THEN
            RAISE EXCEPTION 'Invalid flat_id % for table %', NEW.flat_id, TG_TABLE_NAME;
        END IF;

        IF NEW.society_id <> flat_society THEN
            RAISE EXCEPTION
                'society_id % does not match flats.society_id % for flat_id % in %',
                NEW.society_id,
                flat_society,
                NEW.flat_id,
                TG_TABLE_NAME;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_payment_requests_society_guard ON payment_requests;
CREATE TRIGGER trg_payment_requests_society_guard
BEFORE INSERT OR UPDATE OF society_id, event_id, flat_id ON payment_requests
FOR EACH ROW EXECUTE FUNCTION enforce_society_id_consistency();

DROP TRIGGER IF EXISTS trg_refund_requests_society_guard ON refund_requests;
CREATE TRIGGER trg_refund_requests_society_guard
BEFORE INSERT OR UPDATE OF society_id, event_id, flat_id ON refund_requests
FOR EACH ROW EXECUTE FUNCTION enforce_society_id_consistency();

DROP TRIGGER IF EXISTS trg_event_contributions_society_guard ON event_contributions;
CREATE TRIGGER trg_event_contributions_society_guard
BEFORE INSERT OR UPDATE OF society_id, event_id, flat_id ON event_contributions
FOR EACH ROW EXECUTE FUNCTION enforce_society_id_consistency();

DROP TRIGGER IF EXISTS trg_payment_reminders_society_guard ON payment_reminders;
CREATE TRIGGER trg_payment_reminders_society_guard
BEFORE INSERT OR UPDATE OF society_id, event_id, flat_id ON payment_reminders
FOR EACH ROW EXECUTE FUNCTION enforce_society_id_consistency();
