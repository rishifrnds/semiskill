-- Close two foundation gaps discovered during the audited legacy-checksum adoption review.
-- The canonical artifact spine must resist TRUNCATE as well as row UPDATE/DELETE, and capability
-- roles created conditionally by earlier migrations must be hardened even if a role pre-existed.

CREATE OR REPLACE FUNCTION block_artifact_truncate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'artifacts is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS artifacts_block_truncate ON artifacts;
CREATE TRIGGER artifacts_block_truncate
BEFORE TRUNCATE ON artifacts
FOR EACH STATEMENT EXECUTE FUNCTION block_artifact_truncate();

ALTER ROLE semiskill_app NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_submitter NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_pipeline NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_approval_actuator NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_acl_reader NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

-- A test run against another database in the same cluster may have granted these cluster-global
-- capabilities to the owner. Deployment provisions dedicated identities later; migration never
-- carries ambient owner membership across the trust boundary.
REVOKE semiskill_approval_actuator FROM CURRENT_USER;
REVOKE semiskill_acl_reader FROM CURRENT_USER;
REVOKE semiskill_export_reader FROM CURRENT_USER;
REVOKE semiskill_export_label_public FROM CURRENT_USER;
REVOKE semiskill_export_label_team FROM CURRENT_USER;
REVOKE semiskill_export_label_need_to_know FROM CURRENT_USER;
REVOKE semiskill_export_label_regulated FROM CURRENT_USER;

REVOKE ALL ON artifacts FROM semiskill_app, semiskill_pipeline,
    semiskill_approval_actuator, semiskill_acl_reader;
REVOKE ALL ON verified_publication_events FROM semiskill_app, semiskill_submitter,
    semiskill_pipeline, semiskill_approval_actuator, semiskill_acl_reader;
