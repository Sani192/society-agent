ALTER TABLE member_identities
ADD COLUMN preferred_language VARCHAR(8);

UPDATE member_identities
SET preferred_language = 'en'
WHERE preferred_language IS NULL;

ALTER TABLE member_identities
ALTER COLUMN preferred_language SET DEFAULT 'en';

ALTER TABLE member_identities
ALTER COLUMN preferred_language SET NOT NULL;

ALTER TABLE member_identities
ADD CONSTRAINT ck_member_identities_preferred_language
CHECK (preferred_language IN ('en', 'hi', 'gu'));
