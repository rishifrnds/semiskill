-- The verified publication projection is append-only authority just like the artifact spine.
-- Row triggers do not fire for TRUNCATE, so protect the statement path explicitly.

CREATE OR REPLACE FUNCTION reject_verified_publication_truncate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'verified publication projection is append-only (TRUNCATE blocked)';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS verified_publication_events_block_truncate
    ON verified_publication_events;
CREATE TRIGGER verified_publication_events_block_truncate
BEFORE TRUNCATE ON verified_publication_events
FOR EACH STATEMENT EXECUTE FUNCTION reject_verified_publication_truncate();
