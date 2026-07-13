-- semiskill/artifacts/migrations/0001_artifacts.sql
-- L2 canonical append-only artifact store. Ported from aios 0001_artifacts.sql, with SemiSkill
-- domain enums, CHECK-constrained governance vocabularies, and the restricted role + SECURITY
-- DEFINER ACL read function front-loaded (CLAUDE.md: "ACLs enforced at query traversal").
--
-- L5/L6 artifact types (proposal, execution, sensor_reading, gold_set) are added to the enum in a
-- later migration via `ALTER TYPE artifact_type ADD VALUE` — never a new table.

CREATE TYPE artifact_type AS ENUM (
    'skill_version','scan_run','injection_test','review',
    'approval','comment','rating','reuse_event'
);
CREATE TYPE source_system AS ENUM ('github','sharepoint','cli','web');
CREATE TYPE actor_kind    AS ENUM ('human','service-account','agent');

CREATE TABLE artifacts (
    artifact_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type     artifact_type NOT NULL,
    source_system     source_system NOT NULL,
    actor             text NOT NULL,
    actor_kind        actor_kind NOT NULL,
    timestamp_start   timestamptz NOT NULL,
    timestamp_end     timestamptz,
    input_refs        uuid[] NOT NULL DEFAULT '{}',
    output_refs       uuid[] NOT NULL DEFAULT '{}',
    permissions_label text NOT NULL DEFAULT 'team'
                      CHECK (permissions_label IN ('public','team','need-to-know','regulated')),
    objective_tag     text NOT NULL DEFAULT 'velocity'
                      CHECK (objective_tag IN ('safety','velocity','reuse','compliance')),
    ground_truth_ref  text,
    eval_score        numeric(4,3) CHECK (eval_score >= 0 AND eval_score <= 1),
    rollback_ref      jsonb,
    cost_usd          numeric(10,4),
    corrects_ref      uuid REFERENCES artifacts(artifact_id),      -- self-FK: corrections point back
    payload           jsonb NOT NULL DEFAULT '{}',
    CHECK (timestamp_end IS NULL OR timestamp_end >= timestamp_start)
);

-- Append-only enforcement: corrections are new rows (corrects_ref), never UPDATE/DELETE.
CREATE OR REPLACE FUNCTION block_artifact_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'artifacts is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER artifacts_append_only
    BEFORE UPDATE OR DELETE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION block_artifact_mutation();

-- Structural ACL: the restricted app role reads ONLY through this SECURITY DEFINER function, which
-- ACL-pre-filters by permissions_label in SQL. search_path is pinned (a mutable search_path in a
-- SECURITY DEFINER function is a privilege-escalation vector).
CREATE OR REPLACE FUNCTION artifact_get(target uuid, allowed_labels text[])
RETURNS TABLE (
    artifact_id uuid, artifact_type artifact_type, source_system source_system,
    permissions_label text, objective_tag text, eval_score numeric, payload jsonb
) LANGUAGE sql STABLE SECURITY DEFINER
  SET search_path = pg_catalog, public
AS $$
    SELECT a.artifact_id, a.artifact_type, a.source_system, a.permissions_label,
           a.objective_tag, a.eval_score, a.payload
    FROM artifacts a
    WHERE a.artifact_id = target
      AND a.permissions_label = ANY(allowed_labels);   -- ACL pre-filter, in SQL
$$;

-- Restricted retrieval role (cluster-level; guarded so re-running the migration in a fresh test DB
-- is idempotent). It CANNOT SELECT the table directly — only EXECUTE the ACL function.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_app') THEN
        CREATE ROLE semiskill_app NOLOGIN;
    END IF;
END $$;
GRANT  USAGE ON SCHEMA public TO semiskill_app;
REVOKE ALL ON artifacts FROM semiskill_app;
GRANT  EXECUTE ON FUNCTION artifact_get(uuid, text[]) TO semiskill_app;
GRANT  semiskill_app TO CURRENT_USER;                  -- owner may SET ROLE for tests
