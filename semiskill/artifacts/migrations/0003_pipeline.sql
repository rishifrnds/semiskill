-- semiskill/artifacts/migrations/0003_pipeline.sql
-- Phase C foundation: new pipeline artifact types + structural publish-path enforcement.
--
-- IRREVERSIBLE: ALTER TYPE ADD VALUE cannot be rolled back. PG16 allows it in-transaction as long as
-- the value is not used in the same transaction (these are not — the trigger below only references
-- pre-existing enum values).
ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'gate_decision';
ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'sensor_reading';
ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'gold_set';

-- Submitter role: may append ONLY submission + interaction artifacts. This makes self-publishing
-- structurally impossible — a submitter cannot forge a scan_run / review / approval, so it can never
-- manufacture the published-approval that the catalog derives discoverability from (ADR-002).
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_submitter') THEN
        CREATE ROLE semiskill_submitter NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO semiskill_submitter;
GRANT INSERT ON artifacts TO semiskill_submitter;      -- INSERT only; reads go via catalog_search
GRANT semiskill_submitter TO CURRENT_USER;             -- owner may SET ROLE in tests / submission path

CREATE OR REPLACE FUNCTION enforce_submitter_types() RETURNS trigger AS $$
BEGIN
    IF current_user = 'semiskill_submitter'
       AND NEW.artifact_type NOT IN ('skill_version', 'comment', 'rating', 'reuse_event') THEN
        RAISE EXCEPTION 'role semiskill_submitter may not append artifact_type %', NEW.artifact_type;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER artifacts_submitter_types
    BEFORE INSERT ON artifacts
    FOR EACH ROW EXECUTE FUNCTION enforce_submitter_types();
