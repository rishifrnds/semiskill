-- Correct and tighten the 0018 review boundary without rewriting an applied migration.

-- Existing history must not enter the hardened regime with ambiguous semantic-version identities.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM artifacts
        WHERE artifact_type = 'skill_version'
        GROUP BY payload->>'slug', payload->>'version'
        HAVING count(DISTINCT skill_payload_sha256_v1(payload)) > 1
    ) THEN
        RAISE EXCEPTION 'existing skill semantic version identifies different payload bytes'
            USING ERRCODE = '23514';
    END IF;
END
$$;

-- Replacement leases are allowed; committed review rows remain single-winner.
CREATE INDEX IF NOT EXISTS verified_review_contract_lineage_attempt_lookup
ON verified_review_contract_cells(lineage_id, attempt);
CREATE INDEX IF NOT EXISTS verified_review_contract_prior_lookup
ON verified_review_contract_cells(prior_review_id)
WHERE prior_review_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS content_review_v2_contract_slug_unique
ON artifacts ((input_refs[2]), (payload->>'slug'))
WHERE artifact_type = 'review'
  AND payload->>'review_kind' = 'content_review'
  AND payload->>'schema_version' = '2';

-- Strict JSON typing plus retry-safe, coordinator-only issuance.  The advisory locks serialize
-- both a repeated artifact ID and a repeated run/batch identity.  A byte-identical retry returns
-- the original ID; every collision with different bytes fails closed.
CREATE OR REPLACE FUNCTION append_verified_review_contract(
    contract_id uuid, contract_source source_system, contract_actor text,
    contract_actor_kind actor_kind, started_at timestamptz, ended_at timestamptz,
    contract_input_refs uuid[], contract_output_refs uuid[], contract_permissions_label text,
    contract_objective_tag text, contract_ground_truth_ref text,
    contract_eval_score numeric, contract_rollback_ref jsonb, contract_cost_usd numeric,
    contract_corrects_ref uuid, contract_payload jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    existing artifacts%ROWTYPE;
    cell jsonb;
    check_name text;
    check_value jsonb;
    text_name text;
    attempt_value integer;
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_review_coordinator', 'MEMBER') THEN
        RAISE EXCEPTION 'review contract issuance requires the coordinator capability'
            USING ERRCODE = '42501';
    END IF;
    IF jsonb_typeof(contract_payload) IS DISTINCT FROM 'object'
       OR jsonb_object_length(contract_payload) <> 9
       OR NOT contract_payload ?& ARRAY[
            'schema_version','batch_id','run_id','phase','prompt_version','attempt',
            'issuer_identity','authentication_context','cells'
       ]
       OR jsonb_typeof(contract_payload->'attempt') IS DISTINCT FROM 'number'
       OR jsonb_typeof(contract_payload->'authentication_context') IS DISTINCT FROM 'object'
       OR contract_payload->'authentication_context' = '{}'::jsonb
       OR jsonb_typeof(contract_payload->'cells') IS DISTINCT FROM 'array'
       OR jsonb_array_length(contract_payload->'cells') <> 1 THEN
        RAISE EXCEPTION 'invalid typed review contract envelope' USING ERRCODE = '23514';
    END IF;
    FOREACH text_name IN ARRAY ARRAY[
        'schema_version','batch_id','run_id','phase','prompt_version','issuer_identity'
    ] LOOP
        IF jsonb_typeof(contract_payload->text_name) IS DISTINCT FROM 'string'
           OR nullif(btrim(contract_payload->>text_name),'') IS NULL THEN
            RAISE EXCEPTION 'review contract text field % is invalid', text_name
                USING ERRCODE = '23514';
        END IF;
    END LOOP;
    attempt_value := semiskill_positive_int_v1(contract_payload->'attempt');
    IF attempt_value IS NULL
       OR contract_payload->>'schema_version' <> 'semiskill.review-batch/v1'
       OR (
            contract_payload->>'phase' = 'review'
            AND contract_payload->>'prompt_version'
                !~ '^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$'
       )
       OR (
            contract_payload->>'phase' = 'recheck'
            AND contract_payload->>'prompt_version'
                !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$'
       )
       OR contract_payload->>'phase' NOT IN ('review','recheck')
       OR (attempt_value = 1 AND contract_payload->>'phase' <> 'review')
       OR (contract_payload->>'phase' = 'recheck' AND attempt_value < 2) THEN
        RAISE EXCEPTION 'review contract phase, prompt, or attempt is invalid'
            USING ERRCODE = '23514';
    END IF;

    FOR cell IN SELECT value FROM jsonb_array_elements(contract_payload->'cells') LOOP
        IF jsonb_typeof(cell) IS DISTINCT FROM 'object'
           OR jsonb_object_length(cell) <> 11
           OR NOT cell ?& ARRAY[
                'slug','skill_version_id','skill_payload_sha256','version','role','level',
                'reviewer_identity','fixer_identity','lineage_id','prior_review_ref','checks'
           ] THEN
            RAISE EXCEPTION 'invalid typed review contract cell' USING ERRCODE = '23514';
        END IF;
        FOREACH text_name IN ARRAY ARRAY[
            'slug','skill_version_id','skill_payload_sha256','version','role','level',
            'reviewer_identity','fixer_identity','lineage_id'
        ] LOOP
            IF jsonb_typeof(cell->text_name) IS DISTINCT FROM 'string'
               OR nullif(btrim(cell->>text_name),'') IS NULL THEN
                RAISE EXCEPTION 'review contract cell text field % is invalid', text_name
                    USING ERRCODE = '23514';
            END IF;
        END LOOP;
        IF cell->>'skill_payload_sha256' !~ '^[0-9a-f]{64}$'
           OR jsonb_typeof(cell->'prior_review_ref') NOT IN ('string','null')
           OR (attempt_value = 1 AND cell->'prior_review_ref' <> 'null'::jsonb)
           OR (attempt_value > 1 AND jsonb_typeof(cell->'prior_review_ref') <> 'string')
           OR jsonb_typeof(cell->'checks') IS DISTINCT FROM 'object'
           OR jsonb_object_length(cell->'checks') <> 4
           OR NOT cell->'checks' ?& ARRAY[
                'strict_lint','consistency','source_hash','artifact_reconciliation'
           ] THEN
            RAISE EXCEPTION 'review contract cell references or checks are invalid'
                USING ERRCODE = '23514';
        END IF;
        FOREACH check_name IN ARRAY ARRAY[
            'strict_lint','consistency','source_hash','artifact_reconciliation'
        ] LOOP
            check_value := cell->'checks'->check_name;
            IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
               OR jsonb_object_length(check_value) <> 2
               OR NOT check_value ?& ARRAY['passed','evidence']
               OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
               OR jsonb_typeof(check_value->'evidence') IS DISTINCT FROM 'string'
               OR nullif(btrim(check_value->>'evidence'),'') IS NULL THEN
                RAISE EXCEPTION 'review contract check is not typed'
                    USING ERRCODE = '23514';
            END IF;
        END LOOP;
    END LOOP;

    PERFORM pg_advisory_xact_lock(hashtextextended('review-contract-id|' || contract_id::text, 0));
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'review-contract-run|' || contract_payload->>'batch_id' || '|' ||
        contract_payload->>'run_id', 0
    ));
    SELECT * INTO existing FROM artifacts WHERE artifact_id = contract_id;
    IF FOUND THEN
        IF existing.artifact_type = 'gate_decision'
           AND existing.source_system IS NOT DISTINCT FROM contract_source
           AND existing.actor IS NOT DISTINCT FROM contract_actor
           AND existing.actor_kind IS NOT DISTINCT FROM contract_actor_kind
           AND existing.timestamp_start IS NOT DISTINCT FROM started_at
           AND existing.timestamp_end IS NOT DISTINCT FROM ended_at
           AND existing.input_refs IS NOT DISTINCT FROM contract_input_refs
           AND existing.output_refs IS NOT DISTINCT FROM contract_output_refs
           AND existing.permissions_label IS NOT DISTINCT FROM contract_permissions_label
           AND existing.objective_tag IS NOT DISTINCT FROM contract_objective_tag
           AND existing.ground_truth_ref IS NOT DISTINCT FROM contract_ground_truth_ref
           AND existing.eval_score IS NOT DISTINCT FROM contract_eval_score
           AND existing.rollback_ref IS NOT DISTINCT FROM contract_rollback_ref
           AND existing.cost_usd IS NOT DISTINCT FROM contract_cost_usd
           AND existing.corrects_ref IS NOT DISTINCT FROM contract_corrects_ref
           AND existing.payload IS NOT DISTINCT FROM contract_payload
           AND EXISTS (
                SELECT 1 FROM verified_review_contracts projected
                WHERE projected.contract_id = contract_id
           ) THEN
            RETURN contract_id;
        END IF;
        RAISE EXCEPTION 'review contract ID already identifies different or unverified bytes'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM verified_review_contracts projected
        JOIN artifacts prior_contract ON prior_contract.artifact_id = projected.contract_id
        WHERE prior_contract.payload->>'schema_version' = 'semiskill.review-batch/v1'
          AND prior_contract.payload->>'batch_id' = contract_payload->>'batch_id'
          AND prior_contract.payload->>'run_id' = contract_payload->>'run_id'
          AND prior_contract.artifact_id <> contract_id
    ) THEN
        RAISE EXCEPTION 'review contract run and batch identity is already issued'
            USING ERRCODE = '23514';
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

-- 0018's AFTER trigger queried the just-inserted row as though it were an ancestor.  Patch the
-- checksum-pinned function definition deterministically: both history scans must exclude NEW.
DO $$
DECLARE
    original_definition text;
    corrected_definition text;
    needle text := 'WHERE older.artifact_type = ''review''';
    replacement text :=
        'WHERE older.artifact_id <> NEW.artifact_id AND older.artifact_type = ''review''';
    occurrence_count integer;
BEGIN
    SELECT pg_get_functiondef(
        'public.validate_content_review_v2_insert()'::regprocedure
    ) INTO original_definition;
    occurrence_count := (
        length(original_definition) - length(replace(original_definition, needle, ''))
    ) / length(needle);
    IF occurrence_count <> 2 THEN
        RAISE EXCEPTION 'unexpected 0018 content-review validator definition';
    END IF;
    corrected_definition := replace(original_definition, needle, replacement);
    EXECUTE corrected_definition;
END
$$;

-- This small BEFORE trigger adds exact scalar typing and the mandatory P1-before-P5 policy.  The
-- corrected 0018 AFTER trigger remains the deep database/contract/lineage validator.
CREATE OR REPLACE FUNCTION validate_content_review_v3_policy() RETURNS trigger AS $$
DECLARE
    text_name text;
    check_name text;
    check_value jsonb;
    finding jsonb;
    finding_name text;
    attempt_value integer;
BEGIN
    IF NEW.artifact_type <> 'review'
       OR NEW.payload->>'review_kind' IS DISTINCT FROM 'content_review' THEN
        RETURN NEW;
    END IF;
    IF jsonb_typeof(NEW.payload) IS DISTINCT FROM 'object'
       OR jsonb_typeof(NEW.payload->'schema_version') IS DISTINCT FROM 'number'
       OR jsonb_typeof(NEW.payload->'attempt') IS DISTINCT FROM 'number'
       OR jsonb_typeof(NEW.payload->'prior_review_ref') NOT IN ('string','null')
       OR jsonb_typeof(NEW.payload->'checks') IS DISTINCT FROM 'object'
       OR jsonb_typeof(NEW.payload->'findings') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'canonical content review JSON types are invalid'
            USING ERRCODE = '23514';
    END IF;
    FOREACH text_name IN ARRAY ARRAY[
        'review_kind','phase','prompt_version','run_id','batch_id','slug',
        'skill_payload_sha256','version','role','level','reviewer_identity','fixer_identity',
        'lineage_id','contract_artifact_id'
    ] LOOP
        IF jsonb_typeof(NEW.payload->text_name) IS DISTINCT FROM 'string'
           OR nullif(btrim(NEW.payload->>text_name),'') IS NULL THEN
            RAISE EXCEPTION 'content review text field % is invalid', text_name
                USING ERRCODE = '23514';
        END IF;
    END LOOP;
    attempt_value := semiskill_positive_int_v1(NEW.payload->'attempt');
    IF NEW.payload->>'schema_version' <> '2'
       OR attempt_value IS NULL
       OR (
            NEW.payload->>'phase' = 'review'
            AND NEW.payload->>'prompt_version'
                !~ '^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$'
       )
       OR (
            NEW.payload->>'phase' = 'recheck'
            AND NEW.payload->>'prompt_version'
                !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$'
       )
       OR NEW.payload->>'phase' NOT IN ('review','recheck')
       OR (attempt_value = 1 AND NEW.payload->>'phase' <> 'review')
       OR (NEW.payload->>'phase' = 'recheck' AND attempt_value < 2)
       OR (attempt_value = 1 AND NEW.payload->'prior_review_ref' <> 'null'::jsonb)
       OR (attempt_value > 1 AND jsonb_typeof(NEW.payload->'prior_review_ref') <> 'string') THEN
        RAISE EXCEPTION 'content review must begin with P1 before a calibrated P5 recheck'
            USING ERRCODE = '23514';
    END IF;
    FOREACH check_name IN ARRAY ARRAY[
        'strict_lint','consistency','source_hash','artifact_reconciliation'
    ] LOOP
        check_value := NEW.payload->'checks'->check_name;
        IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
           OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(check_value->'evidence') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'content review check JSON types are invalid'
                USING ERRCODE = '23514';
        END IF;
    END LOOP;
    FOR finding IN SELECT value FROM jsonb_array_elements(NEW.payload->'findings') LOOP
        FOREACH finding_name IN ARRAY ARRAY[
            'finding_id','category','severity','evidence','location',
            'required_change','disposition'
        ] LOOP
            IF jsonb_typeof(finding->finding_name) IS DISTINCT FROM 'string'
               OR nullif(btrim(finding->>finding_name),'') IS NULL THEN
                RAISE EXCEPTION 'content review finding JSON types are invalid'
                    USING ERRCODE = '23514';
            END IF;
        END LOOP;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp;

REVOKE ALL ON FUNCTION validate_content_review_v3_policy() FROM PUBLIC;
DROP TRIGGER IF EXISTS artifacts_content_review_v3_policy ON artifacts;
CREATE TRIGGER artifacts_content_review_v3_policy
BEFORE INSERT ON artifacts
FOR EACH ROW EXECUTE FUNCTION validate_content_review_v3_policy();

-- Publication/export may use only a chain that starts with P1, ends with P5, and whose every
-- contract contains exactly one lease.  Multi-cell review batches remain valid coordination
-- evidence, but cannot leak sibling cells through a published scoped export.
CREATE OR REPLACE FUNCTION content_review_publication_safe_v1(content_id uuid)
RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    review artifacts%ROWTYPE;
    contract artifacts%ROWTYPE;
    expected_attempt integer;
    prior_id uuid;
    visited uuid[] := ARRAY[]::uuid[];
BEGIN
    SELECT * INTO review
    FROM artifacts
    WHERE artifact_id = content_id
      AND artifact_type = 'review'
      AND payload->>'review_kind' = 'content_review'
      AND payload->>'schema_version' = '2';
    IF NOT FOUND THEN RETURN false; END IF;
    expected_attempt := semiskill_positive_int_v1(review.payload->'attempt');
    IF expected_attempt IS NULL OR expected_attempt < 2
       OR review.payload->>'phase' <> 'recheck'
       OR review.payload->>'prompt_version'
            !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$' THEN
        RETURN false;
    END IF;
    LOOP
        IF review.artifact_id = ANY(visited) THEN RETURN false; END IF;
        visited := array_append(visited, review.artifact_id);
        IF semiskill_positive_int_v1(review.payload->'attempt') <> expected_attempt
           OR cardinality(review.input_refs) <> (
                CASE WHEN expected_attempt = 1 THEN 2 ELSE 3 END
              )
           OR NOT review_contract_matches_v1(
                review.input_refs[2], review.artifact_id, review.input_refs[1]
              ) THEN
            RETURN false;
        END IF;
        SELECT * INTO contract FROM artifacts
        WHERE artifact_id = review.input_refs[2] AND artifact_type = 'gate_decision';
        IF NOT FOUND
           OR jsonb_typeof(contract.payload->'cells') <> 'array'
           OR jsonb_array_length(contract.payload->'cells') <> 1
           OR contract.payload#>>'{cells,0,slug}' IS DISTINCT FROM review.payload->>'slug' THEN
            RETURN false;
        END IF;
        IF expected_attempt = 1 THEN
            RETURN (
                review.payload->>'phase' = 'review'
                AND review.payload->>'prompt_version'
                    ~ '^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$'
                AND review.payload->'prior_review_ref' = 'null'::jsonb
            );
        END IF;
        prior_id := review.input_refs[3];
        IF review.payload->>'prior_review_ref' IS DISTINCT FROM prior_id::text THEN
            RETURN false;
        END IF;
        SELECT * INTO review FROM artifacts
        WHERE artifact_id = prior_id
          AND artifact_type = 'review'
          AND payload->>'review_kind' = 'content_review'
          AND payload->>'schema_version' = '2';
        IF NOT FOUND THEN RETURN false; END IF;
        expected_attempt := expected_attempt - 1;
    END LOOP;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

REVOKE ALL ON FUNCTION content_review_publication_safe_v1(uuid) FROM PUBLIC;
CREATE OR REPLACE FUNCTION enforce_publication_review_chain_v1() RETURNS trigger AS $$
BEGIN
    IF NOT content_review_publication_safe_v1(NEW.content_review_id) THEN
        RAISE EXCEPTION 'publication content review lacks a private P1-to-P5 evidence chain'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION enforce_publication_review_chain_v1() FROM PUBLIC;
DROP TRIGGER IF EXISTS verified_publication_review_chain_safe
ON verified_publication_events;
CREATE TRIGGER verified_publication_review_chain_safe
BEFORE INSERT ON verified_publication_events
FOR EACH ROW EXECUTE FUNCTION enforce_publication_review_chain_v1();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM verified_publication_events event
        WHERE NOT content_review_publication_safe_v1(event.content_review_id)
    ) THEN
        RAISE EXCEPTION 'existing publication has an unsafe review/export chain'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM artifacts review
        WHERE review.artifact_type = 'review'
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND (
               cardinality(review.input_refs) NOT IN (2,3)
               OR NOT review_contract_matches_v1(
                    review.input_refs[2], review.artifact_id, review.input_refs[1]
                  )
               OR (
                    semiskill_positive_int_v1(review.payload->'attempt') = 1
                    AND review.payload->>'phase' <> 'review'
               )
          )
    ) THEN
        RAISE EXCEPTION 'existing canonical content review fails the hardened contract'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM artifacts review
        WHERE review.artifact_type = 'review'
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
        GROUP BY review.payload->>'slug'
        HAVING count(DISTINCT review.payload->>'lineage_id') <> 1
    ) THEN
        RAISE EXCEPTION 'existing canonical content reviews contain multiple slug lineages'
            USING ERRCODE = '23514';
    END IF;
END
$$;

-- Exact, label-bound verification is available to runtime readers without enumeration.  Only the
-- pipeline reconciliation capability can enumerate the projection IDs.
CREATE OR REPLACE FUNCTION review_contract_verified_v1(
    target_contract_id uuid, requested_label text
) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NOT (
        pg_has_role(session_user, 'semiskill_app', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_pipeline', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_approval_actuator', 'MEMBER')
        OR pg_has_role(session_user, 'semiskill_acl_reader', 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'review contract verification requires a runtime capability'
            USING ERRCODE = '42501';
    END IF;
    IF requested_label NOT IN ('public','team','need-to-know','regulated') THEN
        RAISE EXCEPTION 'unsupported permission label' USING ERRCODE = '22023';
    END IF;
    RETURN EXISTS (
        SELECT 1
        FROM verified_review_contracts projected
        WHERE projected.contract_id = target_contract_id
          AND projected.permissions_label = requested_label
    );
END;
$$;
REVOKE ALL ON FUNCTION review_contract_verified_v1(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION review_contract_verified_v1(uuid,text)
TO semiskill_app, semiskill_pipeline, semiskill_approval_actuator, semiskill_acl_reader;

CREATE OR REPLACE FUNCTION verified_review_contract_ids_v1()
RETURNS TABLE (contract_id uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_pipeline', 'MEMBER') THEN
        RAISE EXCEPTION 'review contract enumeration requires the pipeline capability'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT projected.contract_id
    FROM verified_review_contracts projected
    ORDER BY projected.contract_id;
END;
$$;
REVOKE ALL ON FUNCTION verified_review_contract_ids_v1()
FROM PUBLIC, semiskill_app, semiskill_approval_actuator, semiskill_acl_reader,
     semiskill_export_reader, semiskill_review_coordinator;
GRANT EXECUTE ON FUNCTION verified_review_contract_ids_v1()
TO semiskill_pipeline;

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
