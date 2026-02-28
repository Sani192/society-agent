ALTER TABLE announcement_deliveries
ADD COLUMN IF NOT EXISTS rendered_payload JSONB;
