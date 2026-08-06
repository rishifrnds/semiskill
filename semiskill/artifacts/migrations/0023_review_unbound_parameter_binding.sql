-- 0022 renamed the checksum-pinned 0019 wrapper.  Its two qualified parameter references must
-- follow that new name; define the complete function so no text-substitution migration is needed.
CREATE OR REPLACE FUNCTION append_verified_review_contract_v2_unbound(
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
    IF attempt_value IS NULL OR attempt_value > 64
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

    PERFORM pg_advisory_xact_lock(hashtextextended(
        'review-contract-id|' || contract_id::text, 0
    ));
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'review-contract-run|' || (contract_payload->>'batch_id') || '|' ||
        (contract_payload->>'run_id'), 0
    ));
    SELECT * INTO existing FROM artifacts
    WHERE artifact_id = append_verified_review_contract_v2_unbound.contract_id;
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
                WHERE projected.contract_id =
                    append_verified_review_contract_v2_unbound.contract_id
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
          AND prior_contract.payload->>'batch_id' = (contract_payload->>'batch_id')
          AND prior_contract.payload->>'run_id' = (contract_payload->>'run_id')
          AND prior_contract.artifact_id <>
              append_verified_review_contract_v2_unbound.contract_id
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

REVOKE ALL ON FUNCTION append_verified_review_contract_v2_unbound(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) FROM PUBLIC, semiskill_review_coordinator;
