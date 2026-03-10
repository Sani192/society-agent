ALTER TABLE announcement_deliveries
ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_announcement_deliveries_claim_pending
ON announcement_deliveries (status, processing_started_at, sent_at, announcement_id);
