-- Harden authenticated review leases, committed review lineage, and scoped publication export.
--
-- 0016 introduced the review-contract projection.  This follow-up deliberately leaves that
-- checksum-tracked migration immutable and closes the gaps found during its adversarial review:
-- only the dedicated coordinator may invoke the actuator, leases do not consume lineage branches,
-- committed reviews are validated at INSERT, projection rows are not directly readable, and a
-- scoped export includes every contract and historical skill version needed to replay readiness.

-- The skill identity trigger must be able to compare prior versions even for INSERT-only
-- submitters.  It is a trigger-only capability and exposes no rows to its caller.
ALTER FUNCTION enforce_skill_version_identity_v1() SECURITY DEFINER;
ALTER FUNCTION enforce_skill_version_identity_v1()
    SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION enforce_skill_version_identity_v1() FROM PUBLIC;

-- A lease is not a completed review.  Several workers may receive replacement leases after an
-- interruption; the immutable content-review indexes below decide which completed child wins.
ALTER TABLE verified_review_contract_cells
    DROP CONSTRAINT IF EXISTS verified_review_contract_cells_lineage_id_attempt_key;
DROP INDEX IF EXISTS verified_review_contract_one_child;

-- Put a session-user guard in front of the 0016 implementation.  SECURITY DEFINER is required so
-- the coordinator never receives INSERT/SELECT on the artifact or projection tables.
ALTER FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) RENAME TO append_verified_review_contract_v1_internal;

REVOKE ALL ON FUNCTION append_verified_review_contract_v1_internal(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) FROM PUBLIC, semiskill_review_coordinator;

CREATE FUNCTION append_verified_review_contract(
    contract_id uuid, contract_source source_system, contract_actor text,
    contract_actor_kind actor_kind, started_at timestamptz, ended_at timestamptz,
    contract_input_refs uuid[], contract_output_refs uuid[], contract_permissions_label text,
    contract_objective_tag text, contract_ground_truth_ref text,
    contract_eval_score numeric, contract_rollback_ref jsonb, contract_cost_usd numeric,
    contract_corrects_ref uuid, contract_payload jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_review_coordinator', 'MEMBER') THEN
        RAISE EXCEPTION 'review contract issuance requires the coordinator capability'
            USING ERRCODE = '42501';
    END IF;
    RETURN append_verified_review_contract_v1_internal(
        contract_id, contract_source, contract_actor, contract_actor_kind, started_at, ended_at,
        contract_input_refs, contract_output_refs, contract_permissions_label,
        contract_objective_tag, contract_ground_truth_ref, contract_eval_score,
        contract_rollback_ref, contract_cost_usd, contract_corrects_ref, contract_payload
    );
END;
$$;

REVOKE ALL ON FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) TO semiskill_review_coordinator;

-- Validate the completed projection after the 0016 actuator has inserted all cells.  The trigger
-- is deferred because the parent projection row is inserted before its cells in the same call.
CREATE OR REPLACE FUNCTION validate_verified_review_contract_v2() RETURNS trigger AS $$
DECLARE
    contract artifacts%ROWTYPE;
    cell record;
    skill artifacts%ROWTYPE;
    prior artifacts%ROWTYPE;
    prior_skill artifacts%ROWTYPE;
    payload_cell jsonb;
    expected_count integer;
    actual_count integer;
BEGIN
    SELECT * INTO contract
    FROM artifacts
    WHERE artifact_id = NEW.contract_id AND artifact_type = 'gate_decision';
    IF NOT FOUND
       OR contract.permissions_label IS DISTINCT FROM NEW.permissions_label
       OR NEW.issued_by IS DISTINCT FROM session_user
       OR NEW.payload_sha256 IS DISTINCT FROM encode(sha256(convert_to(
            semiskill_canonical_json_v1(contract.payload), 'UTF8'
          )), 'hex')
       OR contract.ground_truth_ref IS DISTINCT FROM 'sha256:' || NEW.payload_sha256
       OR contract.payload->>'schema_version' IS DISTINCT FROM 'semiskill.review-batch/v1' THEN
        RAISE EXCEPTION 'verified review contract projection is not bound to its artifact'
            USING ERRCODE = '23514';
    END IF;

    expected_count := jsonb_array_length(contract.payload->'cells');
    SELECT count(*) INTO actual_count
    FROM verified_review_contract_cells projected
    WHERE projected.contract_id = NEW.contract_id;
    IF actual_count <> expected_count THEN
        RAISE EXCEPTION 'verified review contract projection has incomplete cells'
            USING ERRCODE = '23514';
    END IF;

    FOR cell IN
        SELECT projected.*
        FROM verified_review_contract_cells projected
        WHERE projected.contract_id = NEW.contract_id
        ORDER BY projected.slug
    LOOP
        SELECT value INTO payload_cell
        FROM jsonb_array_elements(contract.payload->'cells')
        WHERE value->>'slug' = cell.slug;
        IF NOT FOUND
           OR payload_cell->>'skill_version_id' IS DISTINCT FROM cell.skill_version_id::text
           OR payload_cell->>'lineage_id' IS DISTINCT FROM cell.lineage_id::text
           OR semiskill_positive_int_v1(contract.payload->'attempt') IS DISTINCT FROM cell.attempt
           OR payload_cell->>'prior_review_ref'
                IS DISTINCT FROM cell.prior_review_id::text
           OR payload_cell->>'reviewer_identity' IS DISTINCT FROM cell.reviewer_identity
           OR payload_cell->>'fixer_identity' IS DISTINCT FROM cell.fixer_identity THEN
            RAISE EXCEPTION 'verified review contract cell is not bound to its payload'
                USING ERRCODE = '23514';
        END IF;

        SELECT * INTO skill FROM artifacts
        WHERE artifact_id = cell.skill_version_id AND artifact_type = 'skill_version';
        IF NOT FOUND
           OR coalesce(skill.timestamp_end, skill.timestamp_start) > contract.timestamp_start
           OR skill.permissions_label IS DISTINCT FROM contract.permissions_label THEN
            RAISE EXCEPTION 'review contract predates or mislabels its skill version'
                USING ERRCODE = '23514';
        END IF;

        IF cell.attempt = 1 THEN
            IF cell.prior_review_id IS NOT NULL THEN
                RAISE EXCEPTION 'first review contract cell cannot name a prior review'
                    USING ERRCODE = '23514';
            END IF;
        ELSE
            SELECT * INTO prior FROM artifacts
            WHERE artifact_id = cell.prior_review_id
              AND artifact_type = 'review'
              AND payload->>'review_kind' = 'content_review'
              AND payload->>'schema_version' = '2';
            IF NOT FOUND
               OR cardinality(prior.input_refs) NOT IN (2, 3)
               OR coalesce(prior.timestamp_end, prior.timestamp_start) > contract.timestamp_start
               OR prior.permissions_label IS DISTINCT FROM skill.permissions_label
               OR semiskill_positive_int_v1(prior.payload->'attempt') <> cell.attempt - 1
               OR prior.payload->>'lineage_id' IS DISTINCT FROM cell.lineage_id::text
               OR prior.payload->>'slug' IS DISTINCT FROM cell.slug
               OR prior.payload->>'role' IS DISTINCT FROM skill.payload->>'role'
               OR prior.payload->>'level' IS DISTINCT FROM skill.payload->>'level'
               OR NOT review_contract_matches_v1(
                    prior.input_refs[2], prior.artifact_id, prior.input_refs[1]
                  ) THEN
                RAISE EXCEPTION 'review contract prior is not a verified canonical lineage head'
                    USING ERRCODE = '23514';
            END IF;
            SELECT * INTO prior_skill FROM artifacts
            WHERE artifact_id = prior.input_refs[1] AND artifact_type = 'skill_version';
            IF NOT FOUND
               OR prior_skill.permissions_label IS DISTINCT FROM skill.permissions_label
               OR prior_skill.payload->>'function' IS DISTINCT FROM skill.payload->>'function'
               OR skill_payload_sha256_v1(prior_skill.payload)
                    IS DISTINCT FROM prior.payload->>'skill_payload_sha256'
               OR (
                    prior_skill.artifact_id <> skill.artifact_id
                    AND NOT semiskill_semver_greater_v1(
                        skill.payload->>'version', prior_skill.payload->>'version'
                    )
               ) THEN
                RAISE EXCEPTION 'cross-version review contract changes a stable facet or version'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp;

REVOKE ALL ON FUNCTION validate_verified_review_contract_v2() FROM PUBLIC;
DROP TRIGGER IF EXISTS verified_review_contract_v2_validate ON verified_review_contracts;
CREATE CONSTRAINT TRIGGER verified_review_contract_v2_validate
AFTER INSERT ON verified_review_contracts
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION validate_verified_review_contract_v2();

-- Reject malformed or unleased canonical content reviews at the immutable INSERT boundary.  This
-- prevents a raw row from resetting a slug's lineage or poisoning readiness for all later rounds.
CREATE OR REPLACE FUNCTION validate_content_review_v2_insert() RETURNS trigger AS $$
DECLARE
    skill artifacts%ROWTYPE;
    prior artifacts%ROWTYPE;
    prior_skill artifacts%ROWTYPE;
    attempt_value integer;
    check_name text;
    check_value jsonb;
    finding jsonb;
    older_finding jsonb;
    finding_ids text[] := ARRAY[]::text[];
BEGIN
    IF NEW.artifact_type <> 'review'
       OR NEW.payload->>'review_kind' IS DISTINCT FROM 'content_review' THEN
        RETURN NEW;
    END IF;
    IF NOT pg_has_role(session_user, 'semiskill_pipeline', 'MEMBER') THEN
        RAISE EXCEPTION 'content review append requires the pipeline capability'
            USING ERRCODE = '42501';
    END IF;
    IF jsonb_typeof(NEW.payload) IS DISTINCT FROM 'object'
       OR NEW.payload->>'schema_version' IS DISTINCT FROM '2'
       OR NOT NEW.payload ?& ARRAY[
            'review_kind','schema_version','phase','prompt_version','run_id','batch_id','attempt',
            'slug','skill_payload_sha256','version','role','level','reviewer_identity',
            'fixer_identity','lineage_id','contract_artifact_id','prior_review_ref',
            'checks','findings'
       ]
       OR jsonb_object_length(NEW.payload - ARRAY[
            'review_kind','schema_version','phase','prompt_version','run_id','batch_id','attempt',
            'slug','skill_payload_sha256','version','role','level','reviewer_identity',
            'fixer_identity','lineage_id','contract_artifact_id','prior_review_ref',
            'checks','findings','agent_ready_claim'
       ]) <> 0
       OR (
            NEW.payload ? 'agent_ready_claim'
            AND jsonb_typeof(NEW.payload->'agent_ready_claim') IS DISTINCT FROM 'boolean'
       )
       OR NEW.source_system <> 'cli'
       OR NEW.actor_kind <> 'agent'
       OR NEW.objective_tag <> 'safety'
       OR NEW.actor IS DISTINCT FROM NEW.payload->>'reviewer_identity'
       OR cardinality(NEW.output_refs) <> 0
       OR NEW.eval_score IS NOT NULL
       OR NEW.rollback_ref IS NOT NULL
       OR NEW.cost_usd IS NOT NULL
       OR NEW.corrects_ref IS NOT NULL THEN
        RAISE EXCEPTION 'invalid canonical content review envelope' USING ERRCODE = '23514';
    END IF;

    attempt_value := semiskill_positive_int_v1(NEW.payload->'attempt');
    IF attempt_value IS NULL
       OR nullif(btrim(NEW.payload->>'slug'),'') IS NULL
       OR nullif(btrim(NEW.payload->>'run_id'),'') IS NULL
       OR nullif(btrim(NEW.payload->>'batch_id'),'') IS NULL
       OR nullif(btrim(NEW.payload->>'reviewer_identity'),'') IS NULL
       OR nullif(btrim(NEW.payload->>'fixer_identity'),'') IS NULL
       OR NEW.payload->>'reviewer_identity' = NEW.payload->>'fixer_identity'
       OR NEW.payload->>'lineage_id' !~
          '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
       OR (
            NEW.payload->>'phase' = 'review'
            AND NEW.payload->>'prompt_version' !~ '^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$'
       )
       OR (
            NEW.payload->>'phase' = 'recheck'
            AND NEW.payload->>'prompt_version' !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$'
       )
       OR NEW.payload->>'phase' NOT IN ('review','recheck') THEN
        RAISE EXCEPTION 'invalid canonical content review identity or prompt'
            USING ERRCODE = '23514';
    END IF;

    SELECT * INTO skill FROM artifacts
    WHERE artifact_id = NEW.input_refs[1] AND artifact_type = 'skill_version';
    IF NOT FOUND
       OR coalesce(skill.timestamp_end, skill.timestamp_start) > NEW.timestamp_start
       OR NEW.permissions_label IS DISTINCT FROM skill.permissions_label
       OR NEW.ground_truth_ref IS DISTINCT FROM skill_payload_sha256_v1(skill.payload)
       OR NEW.payload->>'skill_payload_sha256'
            IS DISTINCT FROM skill_payload_sha256_v1(skill.payload)
       OR NEW.payload->>'slug' IS DISTINCT FROM skill.payload->>'slug'
       OR NEW.payload->>'version' IS DISTINCT FROM skill.payload->>'version'
       OR NEW.payload->>'role' IS DISTINCT FROM skill.payload->>'role'
       OR NEW.payload->>'level' IS DISTINCT FROM skill.payload->>'level'
       OR NOT review_contract_matches_v1(
            NEW.input_refs[2], NEW.artifact_id, skill.artifact_id
          ) THEN
        RAISE EXCEPTION 'content review is not bound to its skill and verified contract'
            USING ERRCODE = '23514';
    END IF;

    IF jsonb_typeof(NEW.payload->'checks') IS DISTINCT FROM 'object'
       OR jsonb_object_length(NEW.payload->'checks') <> 4
       OR NOT NEW.payload->'checks' ?& ARRAY[
            'strict_lint','consistency','source_hash','artifact_reconciliation'
       ] THEN
        RAISE EXCEPTION 'content review deterministic checks are invalid'
            USING ERRCODE = '23514';
    END IF;
    FOREACH check_name IN ARRAY ARRAY[
        'strict_lint','consistency','source_hash','artifact_reconciliation'
    ] LOOP
        check_value := NEW.payload->'checks'->check_name;
        IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
           OR jsonb_object_length(check_value) <> 2
           OR NOT check_value ?& ARRAY['passed','evidence']
           OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
           OR nullif(btrim(check_value->>'evidence'),'') IS NULL THEN
            RAISE EXCEPTION 'content review deterministic check is invalid'
                USING ERRCODE = '23514';
        END IF;
    END LOOP;

    IF jsonb_typeof(NEW.payload->'findings') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'content review findings must be an array' USING ERRCODE = '23514';
    END IF;
    FOR finding IN SELECT value FROM jsonb_array_elements(NEW.payload->'findings') LOOP
        IF jsonb_typeof(finding) IS DISTINCT FROM 'object'
           OR jsonb_object_length(finding) <> 7
           OR NOT finding ?& ARRAY[
                'finding_id','category','severity','evidence','location',
                'required_change','disposition'
           ]
           OR nullif(btrim(finding->>'finding_id'),'') IS NULL
           OR finding->>'category' NOT IN (
                'technical_correctness','verb_honesty','hallucination_risk',
                'retrieval_budget','unused_slot','handoff_contract','facet_drift',
                'security','usability'
           )
           OR finding->>'severity' NOT IN ('blocking','non_blocking')
           OR nullif(btrim(finding->>'evidence'),'') IS NULL
           OR nullif(btrim(finding->>'location'),'') IS NULL
           OR nullif(btrim(finding->>'required_change'),'') IS NULL
           OR finding->>'disposition' NOT IN ('open','resolved','disputed')
           OR finding->>'finding_id' = ANY(finding_ids) THEN
            RAISE EXCEPTION 'content review finding is invalid' USING ERRCODE = '23514';
        END IF;
        finding_ids := array_append(finding_ids, finding->>'finding_id');
        SELECT prior_finding.value INTO older_finding
        FROM artifacts older
        CROSS JOIN LATERAL jsonb_array_elements(older.payload->'findings') prior_finding(value)
        WHERE older.artifact_type = 'review'
          AND older.payload->>'review_kind' = 'content_review'
          AND older.payload->>'schema_version' = '2'
          AND older.payload->>'slug' = NEW.payload->>'slug'
          AND older.payload->>'lineage_id' = NEW.payload->>'lineage_id'
          AND prior_finding.value->>'finding_id' = finding->>'finding_id'
        ORDER BY semiskill_positive_int_v1(older.payload->'attempt') DESC
        LIMIT 1;
        IF FOUND AND (
            older_finding->>'category' IS DISTINCT FROM finding->>'category'
            OR older_finding->>'severity' IS DISTINCT FROM finding->>'severity'
            OR older_finding->>'evidence' IS DISTINCT FROM finding->>'evidence'
            OR older_finding->>'location' IS DISTINCT FROM finding->>'location'
            OR older_finding->>'required_change' IS DISTINCT FROM finding->>'required_change'
            OR (
                older_finding->>'disposition' = 'resolved'
                AND finding->>'disposition' <> 'resolved'
            )
        ) THEN
            RAISE EXCEPTION 'content review finding identity changed or was reopened'
                USING ERRCODE = '23514';
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM artifacts other
        WHERE other.artifact_type = 'review'
          AND other.payload->>'review_kind' = 'content_review'
          AND other.payload->>'schema_version' = '2'
          AND other.payload->>'slug' = NEW.payload->>'slug'
          AND other.artifact_id <> NEW.artifact_id
          AND other.payload->>'lineage_id' IS DISTINCT FROM NEW.payload->>'lineage_id'
    ) THEN
        RAISE EXCEPTION 'content review cannot create a second lineage for a slug'
            USING ERRCODE = '23514';
    END IF;

    IF attempt_value = 1 THEN
        IF cardinality(NEW.input_refs) <> 2
           OR NEW.payload->'prior_review_ref' <> 'null'::jsonb
           OR EXISTS (
                SELECT 1 FROM artifacts other
                WHERE other.artifact_type = 'review'
                  AND other.payload->>'review_kind' = 'content_review'
                  AND other.payload->>'schema_version' = '2'
                  AND other.payload->>'slug' = NEW.payload->>'slug'
                  AND other.artifact_id <> NEW.artifact_id
           ) THEN
            RAISE EXCEPTION 'first content review cannot reset an existing lineage'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        IF cardinality(NEW.input_refs) <> 3
           OR NEW.payload->>'prior_review_ref' IS DISTINCT FROM NEW.input_refs[3]::text THEN
            RAISE EXCEPTION 'content review prior reference is invalid' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO prior FROM artifacts
        WHERE artifact_id = NEW.input_refs[3]
          AND artifact_type = 'review'
          AND payload->>'review_kind' = 'content_review'
          AND payload->>'schema_version' = '2';
        IF NOT FOUND
           OR cardinality(prior.input_refs) NOT IN (2, 3)
           OR coalesce(prior.timestamp_end, prior.timestamp_start) > NEW.timestamp_start
           OR prior.permissions_label IS DISTINCT FROM NEW.permissions_label
           OR semiskill_positive_int_v1(prior.payload->'attempt') <> attempt_value - 1
           OR prior.payload->>'lineage_id' IS DISTINCT FROM NEW.payload->>'lineage_id'
           OR prior.payload->>'slug' IS DISTINCT FROM NEW.payload->>'slug'
           OR prior.payload->>'role' IS DISTINCT FROM NEW.payload->>'role'
           OR prior.payload->>'level' IS DISTINCT FROM NEW.payload->>'level'
           OR NOT review_contract_matches_v1(
                prior.input_refs[2], prior.artifact_id, prior.input_refs[1]
              ) THEN
            RAISE EXCEPTION 'content review prior is not a verified canonical attempt'
                USING ERRCODE = '23514';
        END IF;
        SELECT * INTO prior_skill FROM artifacts
        WHERE artifact_id = prior.input_refs[1] AND artifact_type = 'skill_version';
        IF NOT FOUND
           OR prior_skill.permissions_label IS DISTINCT FROM skill.permissions_label
           OR prior_skill.payload->>'function' IS DISTINCT FROM skill.payload->>'function'
           OR skill_payload_sha256_v1(prior_skill.payload)
                IS DISTINCT FROM prior.payload->>'skill_payload_sha256'
           OR (
                prior_skill.artifact_id <> skill.artifact_id
                AND NOT semiskill_semver_greater_v1(
                    skill.payload->>'version', prior_skill.payload->>'version'
                )
           ) THEN
            RAISE EXCEPTION 'cross-version content review changes a stable facet or version'
                USING ERRCODE = '23514';
        END IF;
        IF EXISTS (
            SELECT 1 FROM artifacts older
            WHERE older.artifact_type = 'review'
              AND older.payload->>'review_kind' = 'content_review'
              AND older.payload->>'schema_version' = '2'
              AND older.payload->>'slug' = NEW.payload->>'slug'
              AND older.payload->>'lineage_id' = NEW.payload->>'lineage_id'
              AND (
                   older.payload->>'run_id' = NEW.payload->>'run_id'
                   OR older.payload->>'reviewer_identity' = NEW.payload->>'reviewer_identity'
                   OR older.payload->>'fixer_identity' = NEW.payload->>'reviewer_identity'
                   OR older.payload->>'reviewer_identity' = NEW.payload->>'fixer_identity'
              )
        ) THEN
            RAISE EXCEPTION 'content review identities are not independent across the lineage'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp;

REVOKE ALL ON FUNCTION validate_content_review_v2_insert() FROM PUBLIC;
DROP TRIGGER IF EXISTS artifacts_content_review_v2_validate ON artifacts;
CREATE TRIGGER artifacts_content_review_v2_validate
AFTER INSERT ON artifacts
FOR EACH ROW EXECUTE FUNCTION validate_content_review_v2_insert();

-- Runtime consumers can test coordinator provenance without reading contract payloads or labels.
CREATE OR REPLACE FUNCTION verified_review_contract_ids_v1()
RETURNS TABLE (contract_id uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NOT (
        pg_has_role(session_user, 'semiskill_app', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_pipeline', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_approval_actuator', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_acl_reader', 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'verified review contract IDs require a runtime capability'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT verified.contract_id
    FROM verified_review_contracts verified
    ORDER BY verified.contract_id;
END;
$$;

REVOKE ALL ON FUNCTION verified_review_contract_ids_v1() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION verified_review_contract_ids_v1()
TO semiskill_app, semiskill_pipeline, semiskill_approval_actuator, semiskill_acl_reader;
REVOKE ALL ON verified_review_contracts, verified_review_contract_cells
FROM semiskill_app, semiskill_submitter, semiskill_pipeline,
     semiskill_approval_actuator, semiskill_acl_reader, semiskill_export_reader;

-- Version two follows schema-v2 review refs:
-- PostgreSQL array [1] = reviewed skill, [2] = verified contract, [3] = prior review.
CREATE OR REPLACE FUNCTION export_scoped_publication_bundle_v2(requested_label text)
RETURNS TABLE (
    head_approval_id uuid, head_skill_version_id uuid, head_automated_review_id uuid,
    head_content_review_id uuid, head_slug text, head_permissions_label text,
    artifact_id uuid, artifact_type artifact_type, source_system source_system,
    actor text, actor_kind actor_kind, timestamp_start timestamptz, timestamp_end timestamptz,
    input_refs uuid[], output_refs uuid[], permissions_label text, objective_tag text,
    ground_truth_ref text, eval_score numeric, rollback_ref jsonb, cost_usd numeric,
    corrects_ref uuid, payload jsonb, artifact_is_verified_review_contract boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    marker_count integer;
    marker_authorized boolean;
    head_count integer;
    max_review_attempt integer;
BEGIN
    IF current_setting('role', true) <> 'semiskill_export_reader'
       OR NOT pg_has_role(session_user, 'semiskill_export_reader', 'MEMBER') THEN
        RAISE EXCEPTION 'scoped export requires the export reader capability'
            USING ERRCODE = '42501';
    END IF;
    IF requested_label NOT IN ('public', 'team', 'need-to-know', 'regulated') THEN
        RAISE EXCEPTION 'unsupported scoped export permission label'
            USING ERRCODE = '22023';
    END IF;
    SELECT count(*), coalesce(bool_or(marker.label = requested_label), false)
    INTO marker_count, marker_authorized
    FROM (VALUES
        ('public', 'semiskill_export_label_public'),
        ('team', 'semiskill_export_label_team'),
        ('need-to-know', 'semiskill_export_label_need_to_know'),
        ('regulated', 'semiskill_export_label_regulated')
    ) marker(label, role_name)
    WHERE EXISTS (
        SELECT 1
        FROM pg_auth_members membership
        JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
        JOIN pg_roles login_role ON login_role.oid = membership.member
        WHERE login_role.rolname = session_user
          AND granted_role.rolname = marker.role_name
    );
    IF marker_count <> 1 OR NOT marker_authorized THEN
        RAISE EXCEPTION 'export reader is not authorized for exactly this permission label'
            USING ERRCODE = '42501';
    END IF;
    SELECT count(*) INTO head_count
    FROM verified_active_publication_heads_v1() head
    WHERE head.permissions_label = requested_label;
    IF head_count > 100 THEN
        RAISE EXCEPTION 'scoped export exceeds the 100-head bound' USING ERRCODE = '54000';
    END IF;
    SELECT max((content.payload->>'attempt')::integer) INTO max_review_attempt
    FROM verified_active_publication_heads_v1() head
    JOIN artifacts content ON content.artifact_id = head.content_review_id
      AND content.artifact_type = 'review'
      AND content.permissions_label = requested_label
    WHERE head.permissions_label = requested_label
      AND content.payload->>'attempt' ~ '^[1-9][0-9]*$';
    IF max_review_attempt > 64 THEN
        RAISE EXCEPTION 'scoped export review lineage exceeds the 64-attempt bound'
            USING ERRCODE = '54000';
    END IF;

    RETURN QUERY
    WITH RECURSIVE heads AS (
        SELECT head.approval_id, head.skill_version_id, head.automated_review_id,
               head.content_review_id, head.slug, head.permissions_label
        FROM verified_active_publication_heads_v1() head
        WHERE head.permissions_label = requested_label
    ), content_lineage AS (
        SELECT head.approval_id, head.skill_version_id, head.automated_review_id,
               head.content_review_id, head.slug, head.permissions_label,
               head.content_review_id AS review_id, 0 AS depth,
               ARRAY[head.content_review_id]::uuid[] AS visited
        FROM heads head
        UNION ALL
        SELECT chain.approval_id, chain.skill_version_id, chain.automated_review_id,
               chain.content_review_id, chain.slug, chain.permissions_label,
               review.input_refs[3], chain.depth + 1,
               chain.visited || review.input_refs[3]
        FROM content_lineage chain
        JOIN artifacts review ON review.artifact_id = chain.review_id
          AND review.artifact_type = 'review'
          AND review.permissions_label = requested_label
        WHERE review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND review.payload->>'prior_review_ref' = review.input_refs[3]::text
          AND cardinality(review.input_refs) = 3
          AND review.input_refs[3] <> ALL(chain.visited)
          AND chain.depth < 64
    ), dependencies AS (
        SELECT head.approval_id, head.skill_version_id, head.automated_review_id,
               head.content_review_id, head.slug, head.permissions_label, base.dependency_id
        FROM heads head
        CROSS JOIN LATERAL (VALUES
            (head.approval_id), (head.skill_version_id),
            (head.automated_review_id), (head.content_review_id)
        ) base(dependency_id)
        UNION
        SELECT chain.approval_id, chain.skill_version_id, chain.automated_review_id,
               chain.content_review_id, chain.slug, chain.permissions_label, chain.review_id
        FROM content_lineage chain
        UNION
        SELECT chain.approval_id, chain.skill_version_id, chain.automated_review_id,
               chain.content_review_id, chain.slug, chain.permissions_label, review.input_refs[1]
        FROM content_lineage chain
        JOIN artifacts review ON review.artifact_id = chain.review_id
          AND review.artifact_type = 'review'
          AND review.permissions_label = requested_label
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND cardinality(review.input_refs) IN (2, 3)
        UNION
        SELECT chain.approval_id, chain.skill_version_id, chain.automated_review_id,
               chain.content_review_id, chain.slug, chain.permissions_label, review.input_refs[2]
        FROM content_lineage chain
        JOIN artifacts review ON review.artifact_id = chain.review_id
          AND review.artifact_type = 'review'
          AND review.permissions_label = requested_label
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND cardinality(review.input_refs) IN (2, 3)
        JOIN verified_review_contracts verified
          ON verified.contract_id = review.input_refs[2]
          AND verified.permissions_label = requested_label
        UNION
        SELECT head.approval_id, head.skill_version_id, head.automated_review_id,
               head.content_review_id, head.slug, head.permissions_label, scan_id.value::uuid
        FROM heads head
        JOIN artifacts approval ON approval.artifact_id = head.approval_id
          AND approval.artifact_type = 'approval'
          AND approval.permissions_label = requested_label
        CROSS JOIN LATERAL jsonb_array_elements_text(
            coalesce(approval.payload#>'{evidence,scan_artifact_ids}', '[]'::jsonb)
        ) scan_id(value)
        UNION
        SELECT head.approval_id, head.skill_version_id, head.automated_review_id,
               head.content_review_id, head.slug, head.permissions_label, scan_id
        FROM heads head
        JOIN artifacts automated ON automated.artifact_id = head.automated_review_id
          AND automated.artifact_type = 'review'
          AND automated.permissions_label = requested_label
        CROSS JOIN LATERAL unnest(automated.input_refs[2:]) scan_id
    )
    SELECT dependency.approval_id, dependency.skill_version_id,
           dependency.automated_review_id, dependency.content_review_id,
           dependency.slug, dependency.permissions_label,
           artifact.artifact_id, artifact.artifact_type, artifact.source_system,
           artifact.actor, artifact.actor_kind, artifact.timestamp_start, artifact.timestamp_end,
           artifact.input_refs, artifact.output_refs, artifact.permissions_label,
           artifact.objective_tag, artifact.ground_truth_ref, artifact.eval_score,
           artifact.rollback_ref, artifact.cost_usd, artifact.corrects_ref, artifact.payload,
           artifact.artifact_type = 'gate_decision' AND EXISTS (
               SELECT 1 FROM verified_review_contracts verified
               WHERE verified.contract_id = artifact.artifact_id
                 AND verified.permissions_label = requested_label
           )
    FROM dependencies dependency
    JOIN artifacts artifact ON artifact.artifact_id = dependency.dependency_id
      AND artifact.permissions_label = requested_label
    ORDER BY dependency.slug, artifact.timestamp_start, artifact.artifact_id;
END;
$$;

REVOKE ALL ON FUNCTION export_scoped_publication_bundle_v1(text)
FROM semiskill_export_reader;
REVOKE ALL ON FUNCTION export_scoped_publication_bundle_v2(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION export_scoped_publication_bundle_v2(text)
TO semiskill_export_reader;

-- 0014 ran before the review functions existed.  Re-apply its pg_temp-last invariant to every
-- governed SECURITY DEFINER function, including the renamed internal actuator.
DO $$
DECLARE
    governed record;
BEGIN
    FOR governed IN
        SELECT p.oid::pg_catalog.regprocedure AS signature
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef
        ORDER BY p.oid::regprocedure::text
    LOOP
        EXECUTE pg_catalog.format(
            'ALTER FUNCTION %s SET search_path = pg_catalog, public, pg_temp',
            governed.signature
        );
    END LOOP;
END
$$;
