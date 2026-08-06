-- Consolidate canonical review authority after the one-skill lease transition.
-- Existing migrations are checksum-pinned; every correction here is forward-only and declarative.

LOCK TABLE artifacts IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE verified_review_contracts IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE verified_review_contract_cells IN SHARE ROW EXCLUSIVE MODE;

-- No already-consumed canonical lease may be reinterpreted by the one-skill authority rule.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM artifacts review
        JOIN artifacts contract ON contract.artifact_id = review.input_refs[2]
        LEFT JOIN LATERAL (
            SELECT count(*) AS cell_count
            FROM verified_review_contract_cells projected_cell
            WHERE projected_cell.contract_id = contract.artifact_id
        ) projected ON true
        WHERE review.artifact_type = 'review'
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND (
               jsonb_typeof(contract.payload->'cells') IS DISTINCT FROM 'array'
               OR jsonb_array_length(contract.payload->'cells') <> 1
               OR projected.cell_count <> 1
          )
    ) THEN
        RAISE EXCEPTION 'existing canonical content review consumed a non-single-skill contract'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM verified_review_contracts projected
        JOIN artifacts contract ON contract.artifact_id = projected.contract_id
        WHERE contract.payload->>'schema_version' = 'semiskill.review-batch/v1'
        GROUP BY contract.payload->>'batch_id', contract.payload->>'run_id'
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'verified review contracts contain a duplicate batch/run identity'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM artifacts review
        WHERE review.artifact_type = 'review'
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND semiskill_positive_int_v1(review.payload->'attempt') = 1
        GROUP BY review.payload->>'slug'
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'existing canonical content reviews contain duplicate slug roots'
            USING ERRCODE = '23514';
    END IF;
END
$$;

-- The exported contract carries no token, assertion, raw claim set, or free-form metadata.  Its
-- subject is a one-way hash bound to the projection's actual coordinator database login.
CREATE OR REPLACE FUNCTION review_contract_authentication_valid_v1(target_contract_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1
        FROM verified_review_contracts projected
        JOIN artifacts contract ON contract.artifact_id = projected.contract_id
        CROSS JOIN LATERAL (
            SELECT contract.payload->'authentication_context' AS authentication
        ) claim
        WHERE projected.contract_id = target_contract_id
          AND contract.artifact_type = 'gate_decision'
          AND jsonb_typeof(claim.authentication) = 'object'
          AND jsonb_object_length(claim.authentication) = 2
          AND claim.authentication ?& ARRAY['provider','subject_sha256']
          AND jsonb_typeof(claim.authentication->'provider') = 'string'
          AND jsonb_typeof(claim.authentication->'subject_sha256') = 'string'
          AND claim.authentication->>'subject_sha256' ~ '^sha256:[0-9a-f]{64}$'
          AND (
               (
                   claim.authentication->>'provider' = 'database-role'
                   AND claim.authentication->>'subject_sha256' =
                       'sha256:' || encode(sha256(convert_to(projected.issued_by, 'UTF8')), 'hex')
               )
               OR (
                   claim.authentication->>'provider' = 'test'
                   AND right(current_database(), 5) = '_test'
               )
          )
    );
$$;
REVOKE ALL ON FUNCTION review_contract_authentication_valid_v1(uuid) FROM PUBLIC;

-- A verified projection authorizes exactly one cell, with a valid non-secret issuer claim.
CREATE OR REPLACE FUNCTION review_contract_matches_v1(
    contract_id_to_check uuid, review_id_to_check uuid, skill_id_to_check uuid
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1
        FROM verified_review_contracts projected
        JOIN verified_review_contract_cells projected_cell
          ON projected_cell.contract_id = projected.contract_id
        JOIN artifacts contract ON contract.artifact_id = projected.contract_id
          AND contract.artifact_type = 'gate_decision'
        JOIN artifacts review ON review.artifact_id = review_id_to_check
          AND review.artifact_type = 'review'
        JOIN artifacts skill ON skill.artifact_id = skill_id_to_check
          AND skill.artifact_type = 'skill_version'
        JOIN LATERAL (
            SELECT value AS cell FROM jsonb_array_elements(contract.payload->'cells')
            WHERE value->>'slug' = review.payload->>'slug'
              AND value->>'skill_version_id' = skill_id_to_check::text
        ) lease ON true
        WHERE projected.contract_id = contract_id_to_check
          AND jsonb_typeof(contract.payload->'cells') = 'array'
          AND jsonb_array_length(contract.payload->'cells') = 1
          AND (
              SELECT count(*) FROM verified_review_contract_cells only_cell
              WHERE only_cell.contract_id = projected.contract_id
          ) = 1
          AND review_contract_authentication_valid_v1(projected.contract_id)
          AND projected_cell.slug = review.payload->>'slug'
          AND projected_cell.skill_version_id = skill_id_to_check
          AND projected_cell.lineage_id::text = review.payload->>'lineage_id'
          AND projected_cell.attempt = semiskill_positive_int_v1(review.payload->'attempt')
          AND projected_cell.prior_review_id::text
              IS NOT DISTINCT FROM review.payload->>'prior_review_ref'
          AND projected_cell.reviewer_identity = review.payload->>'reviewer_identity'
          AND projected_cell.fixer_identity = review.payload->>'fixer_identity'
          AND projected.payload_sha256 = encode(sha256(convert_to(
                semiskill_canonical_json_v1(contract.payload), 'UTF8'
              )), 'hex')
          AND contract.ground_truth_ref = 'sha256:' || projected.payload_sha256
          AND contract.source_system = 'cli'
          AND contract.actor_kind = 'service-account'
          AND contract.objective_tag = 'safety'
          AND contract.actor = contract.payload->>'issuer_identity'
          AND contract.permissions_label = skill.permissions_label
          AND review.permissions_label = skill.permissions_label
          AND review.source_system = 'cli'
          AND review.actor_kind = 'agent'
          AND review.objective_tag = 'safety'
          AND review.actor = review.payload->>'reviewer_identity'
          AND coalesce(contract.timestamp_end, contract.timestamp_start) <= review.timestamp_start
          AND review.payload->>'schema_version' = '2'
          AND review.payload->>'contract_artifact_id' = contract_id_to_check::text
          AND cardinality(review.input_refs) = CASE
                WHEN review.payload->'prior_review_ref' = 'null'::jsonb THEN 2 ELSE 3 END
          AND review.input_refs[1] = skill_id_to_check
          AND review.input_refs[2] = contract_id_to_check
          AND lease.cell->>'skill_payload_sha256' = review.payload->>'skill_payload_sha256'
          AND lease.cell->>'version' = review.payload->>'version'
          AND lease.cell->>'role' = review.payload->>'role'
          AND lease.cell->>'level' = review.payload->>'level'
          AND lease.cell->>'reviewer_identity' = review.payload->>'reviewer_identity'
          AND lease.cell->>'fixer_identity' = review.payload->>'fixer_identity'
          AND lease.cell->>'lineage_id' = review.payload->>'lineage_id'
          AND lease.cell->'prior_review_ref' IS NOT DISTINCT FROM review.payload->'prior_review_ref'
          AND lease.cell->'checks' IS NOT DISTINCT FROM review.payload->'checks'
          AND contract.payload->>'batch_id' = review.payload->>'batch_id'
          AND contract.payload->>'run_id' = review.payload->>'run_id'
          AND contract.payload->>'phase' = review.payload->>'phase'
          AND contract.payload->>'prompt_version' = review.payload->>'prompt_version'
          AND contract.payload->'attempt' IS NOT DISTINCT FROM review.payload->'attempt'
    );
$$;
REVOKE ALL ON FUNCTION review_contract_matches_v1(uuid,uuid,uuid) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM artifacts review
        WHERE review.artifact_type = 'review'
          AND review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'schema_version' = '2'
          AND (
               cardinality(review.input_refs) NOT IN (2, 3)
               OR NOT review_contract_matches_v1(
                    review.input_refs[2], review.artifact_id, review.input_refs[1]
                  )
          )
    ) THEN
        RAISE EXCEPTION 'existing canonical content review has invalid contract authentication'
            USING ERRCODE = '23514';
    END IF;
END
$$;

-- Serialize and structurally reject concurrent roots even when their proposed lineage IDs differ.
CREATE UNIQUE INDEX content_review_v2_one_root_per_slug
ON artifacts ((payload->>'slug'))
WHERE artifact_type = 'review'
  AND payload->>'review_kind' = 'content_review'
  AND payload->>'schema_version' = '2'
  AND payload->'attempt' = '1'::jsonb;

-- Preserve the existing deep validator, but require the publication-safe P1 -> fresh P5 shape for
-- every SQL readiness decision.  The renamed implementation remains private and non-authoritative.
ALTER FUNCTION content_review_ready_v1(uuid,uuid)
RENAME TO content_review_ready_v1_pre_0022;
REVOKE ALL ON FUNCTION content_review_ready_v1_pre_0022(uuid,uuid) FROM PUBLIC;
CREATE FUNCTION content_review_ready_v1(content_id uuid, skill_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT content_review_publication_safe_v1(content_id)
       AND content_review_ready_v1_pre_0022(content_id, skill_id);
$$;
REVOKE ALL ON FUNCTION content_review_ready_v1(uuid,uuid) FROM PUBLIC;

-- Keep the checksum-pinned 0019 implementation as the validating/mutating core.  This public
-- wrapper adds login-bound authentication and semantic retry recovery under the same advisory key.
ALTER FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) RENAME TO append_verified_review_contract_v2_unbound;
REVOKE ALL ON FUNCTION append_verified_review_contract_v2_unbound(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) FROM PUBLIC, semiskill_review_coordinator;

CREATE FUNCTION append_verified_review_contract(
    p_contract_id uuid, p_contract_source source_system, p_contract_actor text,
    p_contract_actor_kind actor_kind, p_started_at timestamptz, p_ended_at timestamptz,
    p_input_refs uuid[], p_output_refs uuid[], p_permissions_label text,
    p_objective_tag text, p_ground_truth_ref text,
    p_eval_score numeric, p_rollback_ref jsonb, p_cost_usd numeric,
    p_corrects_ref uuid, p_payload jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    authentication jsonb;
    expected_subject text;
    prior_contract artifacts%ROWTYPE;
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_review_coordinator', 'MEMBER') THEN
        RAISE EXCEPTION 'review contract issuance requires the coordinator capability'
            USING ERRCODE = '42501';
    END IF;
    authentication := p_payload->'authentication_context';
    expected_subject := 'sha256:' || encode(
        sha256(convert_to(session_user, 'UTF8')), 'hex'
    );
    IF jsonb_typeof(authentication) IS DISTINCT FROM 'object'
       OR jsonb_object_length(authentication) <> 2
       OR NOT authentication ?& ARRAY['provider','subject_sha256']
       OR jsonb_typeof(authentication->'provider') IS DISTINCT FROM 'string'
       OR jsonb_typeof(authentication->'subject_sha256') IS DISTINCT FROM 'string'
       OR authentication->>'subject_sha256' !~ '^sha256:[0-9a-f]{64}$'
       OR NOT (
            (
                authentication->>'provider' = 'database-role'
                AND authentication->>'subject_sha256' = expected_subject
            )
            OR (
                authentication->>'provider' = 'test'
                AND right(current_database(), 5) = '_test'
            )
       ) THEN
        RAISE EXCEPTION 'review contract authentication_context is invalid or unbound'
            USING ERRCODE = '23514';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(
        'review-contract-id|' || p_contract_id::text, 0
    ));
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'review-contract-run|' || (p_payload->>'batch_id') || '|' || (p_payload->>'run_id'), 0
    ));
    SELECT prior.* INTO prior_contract
    FROM verified_review_contracts projected
    JOIN artifacts prior ON prior.artifact_id = projected.contract_id
    WHERE prior.payload->>'schema_version' = 'semiskill.review-batch/v1'
      AND prior.payload->>'batch_id' = p_payload->>'batch_id'
      AND prior.payload->>'run_id' = p_payload->>'run_id'
      AND prior.artifact_id <> p_contract_id
    ORDER BY prior.artifact_id
    LIMIT 1;
    IF FOUND THEN
        IF prior_contract.artifact_type = 'gate_decision'
           AND prior_contract.source_system IS NOT DISTINCT FROM p_contract_source
           AND prior_contract.actor IS NOT DISTINCT FROM p_contract_actor
           AND prior_contract.actor_kind IS NOT DISTINCT FROM p_contract_actor_kind
           AND prior_contract.input_refs IS NOT DISTINCT FROM p_input_refs
           AND prior_contract.output_refs IS NOT DISTINCT FROM p_output_refs
           AND prior_contract.permissions_label IS NOT DISTINCT FROM p_permissions_label
           AND prior_contract.objective_tag IS NOT DISTINCT FROM p_objective_tag
           AND prior_contract.ground_truth_ref IS NOT DISTINCT FROM p_ground_truth_ref
           AND prior_contract.eval_score IS NOT DISTINCT FROM p_eval_score
           AND prior_contract.rollback_ref IS NOT DISTINCT FROM p_rollback_ref
           AND prior_contract.cost_usd IS NOT DISTINCT FROM p_cost_usd
           AND prior_contract.corrects_ref IS NOT DISTINCT FROM p_corrects_ref
           AND prior_contract.payload IS NOT DISTINCT FROM p_payload
           AND review_contract_authentication_valid_v1(prior_contract.artifact_id) THEN
            RETURN prior_contract.artifact_id;
        END IF;
        RAISE EXCEPTION 'review contract run and batch identity identifies different bytes'
            USING ERRCODE = '23514';
    END IF;

    RETURN append_verified_review_contract_v2_unbound(
        p_contract_id, p_contract_source, p_contract_actor, p_contract_actor_kind,
        p_started_at, p_ended_at, p_input_refs, p_output_refs, p_permissions_label,
        p_objective_tag, p_ground_truth_ref, p_eval_score, p_rollback_ref, p_cost_usd,
        p_corrects_ref, p_payload
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
