-- Authenticated review-contract issuance and content-review schema v2.
--
-- Agent output is untrusted.  A content review can contribute to publication only when every
-- coordinator-owned field came from a dedicated, append-only review-contract actuator.  The
-- projection below is the authority witness; a raw gate_decision row is audit-only.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_review_coordinator') THEN
        CREATE ROLE semiskill_review_coordinator NOLOGIN NOINHERIT;
    END IF;
END $$;
ALTER ROLE semiskill_review_coordinator NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS verified_review_contracts (
    contract_id uuid PRIMARY KEY REFERENCES artifacts(artifact_id),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    permissions_label text NOT NULL CHECK (
        permissions_label IN ('public','team','need-to-know','regulated')
    ),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    issued_by text NOT NULL CHECK (length(btrim(issued_by)) > 0)
);

CREATE TABLE IF NOT EXISTS verified_review_contract_cells (
    contract_id uuid NOT NULL REFERENCES verified_review_contracts(contract_id),
    slug text NOT NULL CHECK (length(btrim(slug)) > 0),
    skill_version_id uuid NOT NULL REFERENCES artifacts(artifact_id),
    lineage_id uuid NOT NULL,
    attempt integer NOT NULL CHECK (attempt > 0),
    prior_review_id uuid NULL REFERENCES artifacts(artifact_id),
    reviewer_identity text NOT NULL CHECK (length(btrim(reviewer_identity)) > 0),
    fixer_identity text NOT NULL CHECK (length(btrim(fixer_identity)) > 0),
    PRIMARY KEY (contract_id, slug),
    UNIQUE (lineage_id, attempt)
);
CREATE UNIQUE INDEX IF NOT EXISTS verified_review_contract_one_child
ON verified_review_contract_cells(prior_review_id) WHERE prior_review_id IS NOT NULL;

CREATE OR REPLACE FUNCTION reject_review_contract_projection_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'verified review-contract projection is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS verified_review_contracts_block_mutation ON verified_review_contracts;
CREATE TRIGGER verified_review_contracts_block_mutation
BEFORE UPDATE OR DELETE ON verified_review_contracts
FOR EACH ROW EXECUTE FUNCTION reject_review_contract_projection_mutation();
DROP TRIGGER IF EXISTS verified_review_contracts_block_truncate ON verified_review_contracts;
CREATE TRIGGER verified_review_contracts_block_truncate
BEFORE TRUNCATE ON verified_review_contracts
FOR EACH STATEMENT EXECUTE FUNCTION reject_review_contract_projection_mutation();

DROP TRIGGER IF EXISTS verified_review_contract_cells_block_mutation
ON verified_review_contract_cells;
CREATE TRIGGER verified_review_contract_cells_block_mutation
BEFORE UPDATE OR DELETE ON verified_review_contract_cells
FOR EACH ROW EXECUTE FUNCTION reject_review_contract_projection_mutation();
DROP TRIGGER IF EXISTS verified_review_contract_cells_block_truncate
ON verified_review_contract_cells;
CREATE TRIGGER verified_review_contract_cells_block_truncate
BEFORE TRUNCATE ON verified_review_contract_cells
FOR EACH STATEMENT EXECUTE FUNCTION reject_review_contract_projection_mutation();

CREATE OR REPLACE FUNCTION enforce_skill_version_identity_v1() RETURNS trigger AS $$
BEGIN
    IF NEW.artifact_type = 'skill_version' THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(
            coalesce(NEW.payload->>'slug','') || '|' || coalesce(NEW.payload->>'version',''), 0
        ));
        IF EXISTS (
            SELECT 1 FROM artifacts prior
            WHERE prior.artifact_type = 'skill_version'
              AND prior.payload->>'slug' IS NOT DISTINCT FROM NEW.payload->>'slug'
              AND prior.payload->>'version' IS NOT DISTINCT FROM NEW.payload->>'version'
              AND skill_payload_sha256_v1(prior.payload)
                  IS DISTINCT FROM skill_payload_sha256_v1(NEW.payload)
        ) THEN
            RAISE EXCEPTION 'skill semantic version already identifies different payload bytes'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS artifacts_skill_version_identity ON artifacts;
CREATE TRIGGER artifacts_skill_version_identity
BEFORE INSERT ON artifacts
FOR EACH ROW EXECUTE FUNCTION enforce_skill_version_identity_v1();

CREATE OR REPLACE FUNCTION append_verified_review_contract(
    contract_id uuid, contract_source source_system, contract_actor text,
    contract_actor_kind actor_kind, started_at timestamptz, ended_at timestamptz,
    contract_input_refs uuid[], contract_output_refs uuid[], contract_permissions_label text,
    contract_objective_tag text, contract_ground_truth_ref text,
    contract_eval_score numeric, contract_rollback_ref jsonb, contract_cost_usd numeric,
    contract_corrects_ref uuid, contract_payload jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    cell jsonb;
    check_name text;
    check_value jsonb;
    skill artifacts%ROWTYPE;
    prior artifacts%ROWTYPE;
    slug_value text;
    previous_slug text := NULL;
    reviewer_value text;
    fixer_value text;
    skill_id uuid;
    lineage_value uuid;
    prior_id uuid;
    attempt_value integer;
    expected_skill_refs uuid[] := ARRAY[]::uuid[];
    expected_prior_refs uuid[] := ARRAY[]::uuid[];
    seen_reviewers text[] := ARRAY[]::text[];
    expected_digest text;
BEGIN
    IF contract_source <> 'cli'
       OR contract_actor_kind <> 'service-account'
       OR contract_objective_tag <> 'safety'
       OR contract_corrects_ref IS NOT NULL
       OR cardinality(contract_output_refs) <> 0
       OR contract_eval_score IS NOT NULL
       OR contract_cost_usd IS NOT NULL
       OR contract_rollback_ref IS NOT NULL
       OR contract_payload->>'schema_version' IS DISTINCT FROM 'semiskill.review-batch/v1'
       OR jsonb_typeof(contract_payload) IS DISTINCT FROM 'object'
       OR jsonb_object_length(contract_payload) <> 9
       OR NOT contract_payload ?& ARRAY[
            'schema_version','batch_id','run_id','phase','prompt_version','attempt',
            'issuer_identity','authentication_context','cells'
       ]
       OR nullif(btrim(contract_payload->>'batch_id'),'') IS NULL
       OR nullif(btrim(contract_payload->>'run_id'),'') IS NULL
       OR contract_payload->>'phase' NOT IN ('review','recheck')
       OR nullif(btrim(contract_payload->>'prompt_version'),'') IS NULL
       OR semiskill_positive_int_v1(contract_payload->'attempt') IS NULL
       OR contract_actor IS DISTINCT FROM contract_payload->>'issuer_identity'
       OR nullif(btrim(contract_actor),'') IS NULL
       OR jsonb_typeof(contract_payload->'authentication_context') IS DISTINCT FROM 'object'
       OR contract_payload->'authentication_context' = '{}'::jsonb
       OR jsonb_typeof(contract_payload->'cells') IS DISTINCT FROM 'array'
       OR jsonb_array_length(contract_payload->'cells') NOT BETWEEN 1 AND 10 THEN
        RAISE EXCEPTION 'invalid verified review contract envelope' USING ERRCODE = '23514';
    END IF;
    expected_digest := 'sha256:' || encode(sha256(convert_to(
        semiskill_canonical_json_v1(contract_payload), 'UTF8'
    )), 'hex');
    IF contract_ground_truth_ref IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'review contract digest mismatch' USING ERRCODE = '23514';
    END IF;
    attempt_value := semiskill_positive_int_v1(contract_payload->'attempt');

    FOR cell IN SELECT value FROM jsonb_array_elements(contract_payload->'cells') LOOP
        IF jsonb_typeof(cell) IS DISTINCT FROM 'object'
           OR jsonb_object_length(cell) <> 11
           OR NOT cell ?& ARRAY[
                'slug','skill_version_id','skill_payload_sha256','version','role','level',
                'reviewer_identity','fixer_identity','lineage_id','prior_review_ref','checks'
           ] THEN
            RAISE EXCEPTION 'invalid verified review contract cell' USING ERRCODE = '23514';
        END IF;
        slug_value := nullif(btrim(cell->>'slug'),'');
        reviewer_value := nullif(btrim(cell->>'reviewer_identity'),'');
        fixer_value := nullif(btrim(cell->>'fixer_identity'),'');
        IF slug_value IS NULL OR reviewer_value IS NULL OR fixer_value IS NULL
           OR reviewer_value = fixer_value OR reviewer_value = ANY(seen_reviewers)
           OR (previous_slug IS NOT NULL AND slug_value <= previous_slug) THEN
            RAISE EXCEPTION 'review contract identities/slugs are invalid' USING ERRCODE = '23514';
        END IF;
        previous_slug := slug_value;
        seen_reviewers := array_append(seen_reviewers, reviewer_value);
        BEGIN
            skill_id := (cell->>'skill_version_id')::uuid;
            lineage_value := (cell->>'lineage_id')::uuid;
            prior_id := CASE WHEN cell->'prior_review_ref' = 'null'::jsonb THEN NULL
                             ELSE (cell->>'prior_review_ref')::uuid END;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'review contract UUID is invalid' USING ERRCODE = '23514';
        END;
        SELECT * INTO skill FROM artifacts
        WHERE artifact_id = skill_id AND artifact_type = 'skill_version';
        IF NOT FOUND
           OR skill.permissions_label IS DISTINCT FROM contract_permissions_label
           OR skill.payload->>'slug' IS DISTINCT FROM slug_value
           OR skill.payload->>'version' IS DISTINCT FROM cell->>'version'
           OR skill.payload->>'role' IS DISTINCT FROM cell->>'role'
           OR skill.payload->>'level' IS DISTINCT FROM cell->>'level'
           OR skill_payload_sha256_v1(skill.payload)
              IS DISTINCT FROM cell->>'skill_payload_sha256' THEN
            RAISE EXCEPTION 'review contract skill binding is invalid' USING ERRCODE = '23514';
        END IF;
        IF jsonb_typeof(cell->'checks') IS DISTINCT FROM 'object'
           OR jsonb_object_length(cell->'checks') <> 4
           OR NOT cell->'checks' ?& ARRAY[
                'strict_lint','consistency','source_hash','artifact_reconciliation'
           ] THEN
            RAISE EXCEPTION 'review contract checks are invalid' USING ERRCODE = '23514';
        END IF;
        FOREACH check_name IN ARRAY ARRAY[
            'strict_lint','consistency','source_hash','artifact_reconciliation'
        ] LOOP
            check_value := cell->'checks'->check_name;
            IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
               OR jsonb_object_length(check_value) <> 2
               OR NOT check_value ?& ARRAY['passed','evidence']
               OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
               OR nullif(btrim(check_value->>'evidence'),'') IS NULL THEN
                RAISE EXCEPTION 'review contract deterministic check is invalid'
                    USING ERRCODE = '23514';
            END IF;
        END LOOP;
        IF attempt_value = 1 THEN
            IF prior_id IS NOT NULL OR EXISTS (
                SELECT 1 FROM artifacts review
                WHERE review.artifact_type = 'review'
                  AND review.payload->>'review_kind' = 'content_review'
                  AND review.payload->>'slug' = slug_value
            ) THEN
                RAISE EXCEPTION 'first review lease cannot reset existing lineage'
                    USING ERRCODE = '23514';
            END IF;
        ELSE
            SELECT * INTO prior FROM artifacts
            WHERE artifact_id = prior_id AND artifact_type = 'review'
              AND payload->>'review_kind' = 'content_review';
            IF NOT FOUND
               OR semiskill_positive_int_v1(prior.payload->'attempt') <> attempt_value - 1
               OR prior.payload->>'lineage_id' IS DISTINCT FROM lineage_value::text
               OR prior.payload->>'slug' IS DISTINCT FROM slug_value
               OR prior.payload->>'role' IS DISTINCT FROM cell->>'role'
               OR prior.payload->>'level' IS DISTINCT FROM cell->>'level' THEN
                RAISE EXCEPTION 'review contract prior lineage is invalid' USING ERRCODE = '23514';
            END IF;
            IF prior.input_refs[1] IS DISTINCT FROM skill_id
               AND NOT semiskill_semver_greater_v1(
                    cell->>'version', prior.payload->>'version'
               ) THEN
                RAISE EXCEPTION 'cross-version review lease requires a monotonic semver bump'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        expected_skill_refs := array_append(expected_skill_refs, skill_id);
        IF prior_id IS NOT NULL THEN
            expected_prior_refs := array_append(expected_prior_refs, prior_id);
        END IF;
    END LOOP;
    IF contract_input_refs IS DISTINCT FROM expected_skill_refs || expected_prior_refs THEN
        RAISE EXCEPTION 'review contract input references do not match cells'
            USING ERRCODE = '23514';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(contract_payload->>'batch_id', 0));
    INSERT INTO artifacts (
        artifact_id, artifact_type, source_system, actor, actor_kind,
        timestamp_start, timestamp_end, input_refs, output_refs, permissions_label,
        objective_tag, ground_truth_ref, eval_score, rollback_ref, cost_usd,
        corrects_ref, payload
    ) VALUES (
        contract_id, 'gate_decision', contract_source, contract_actor, contract_actor_kind,
        started_at, ended_at, contract_input_refs, contract_output_refs,
        contract_permissions_label, contract_objective_tag, contract_ground_truth_ref,
        contract_eval_score, contract_rollback_ref, contract_cost_usd,
        contract_corrects_ref, contract_payload
    );
    INSERT INTO verified_review_contracts (
        contract_id, payload_sha256, permissions_label, issued_by
    ) VALUES (
        contract_id, substr(expected_digest, 8), contract_permissions_label, session_user
    );
    FOR cell IN SELECT value FROM jsonb_array_elements(contract_payload->'cells') LOOP
        INSERT INTO verified_review_contract_cells (
            contract_id, slug, skill_version_id, lineage_id, attempt, prior_review_id,
            reviewer_identity, fixer_identity
        ) VALUES (
            contract_id, cell->>'slug', (cell->>'skill_version_id')::uuid,
            (cell->>'lineage_id')::uuid, attempt_value,
            CASE WHEN cell->'prior_review_ref' = 'null'::jsonb THEN NULL
                 ELSE (cell->>'prior_review_ref')::uuid END,
            cell->>'reviewer_identity', cell->>'fixer_identity'
        );
    END LOOP;
    RETURN contract_id;
END;
$$;

CREATE OR REPLACE FUNCTION review_contract_matches_v1(
    contract_id_to_check uuid, review_id_to_check uuid, skill_id_to_check uuid
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
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

CREATE OR REPLACE FUNCTION content_review_ready_v1(content_id uuid, skill_id uuid)
RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    sv artifacts%ROWTYPE;
    current_sv artifacts%ROWTYPE;
    prior_sv artifacts%ROWTYPE;
    cr artifacts%ROWTYPE;
    prior artifacts%ROWTYPE;
    fingerprint text;
    top_id uuid := content_id;
    expected_attempt integer;
    current_attempt integer;
    candidate_count integer;
    check_name text;
    check_value jsonb;
    finding jsonb;
    newer_finding jsonb;
    finding_id text;
    lineage_id_value text;
    finding_ids text[] := ARRAY[]::text[];
    seen_run_ids text[] := ARRAY[]::text[];
    seen_reviewers text[] := ARRAY[]::text[];
    seen_fixers text[] := ARRAY[]::text[];
    effective_findings jsonb := '{}'::jsonb;
BEGIN
    SELECT * INTO sv FROM artifacts
    WHERE artifact_id = skill_id AND artifact_type = 'skill_version';
    IF NOT FOUND THEN RETURN false; END IF;
    SELECT * INTO cr FROM artifacts
    WHERE artifact_id = content_id AND artifact_type = 'review';
    IF NOT FOUND OR cardinality(cr.input_refs) < 2 OR cr.input_refs[1] <> skill_id THEN
        RETURN false;
    END IF;
    expected_attempt := semiskill_positive_int_v1(cr.payload->'attempt');
    lineage_id_value := cr.payload->>'lineage_id';
    IF expected_attempt IS NULL OR lineage_id_value !~
       '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
    THEN RETURN false; END IF;

    SELECT count(*) INTO candidate_count
    FROM artifacts candidate
    WHERE candidate.artifact_type = 'review'
      AND candidate.payload->>'review_kind' = 'content_review'
      AND candidate.payload->>'slug' = cr.payload->>'slug'
      AND candidate.payload->>'lineage_id' = lineage_id_value;
    IF candidate_count <> expected_attempt THEN RETURN false; END IF;

    LOOP
        current_attempt := semiskill_positive_int_v1(cr.payload->'attempt');
        IF cardinality(cr.input_refs) < 2 THEN RETURN false; END IF;
        SELECT * INTO current_sv FROM artifacts
        WHERE artifact_id = cr.input_refs[1] AND artifact_type = 'skill_version';
        IF NOT FOUND THEN RETURN false; END IF;
        fingerprint := skill_payload_sha256_v1(current_sv.payload);
        IF current_attempt IS DISTINCT FROM expected_attempt
           OR cr.payload->>'review_kind' IS DISTINCT FROM 'content_review'
           OR cr.payload->>'schema_version' IS DISTINCT FROM '2'
           OR cr.permissions_label IS DISTINCT FROM current_sv.permissions_label
           OR coalesce(current_sv.timestamp_end, current_sv.timestamp_start) > cr.timestamp_start
           OR cr.payload->>'skill_payload_sha256' IS DISTINCT FROM fingerprint
           OR cr.ground_truth_ref IS DISTINCT FROM fingerprint
           OR cr.payload->>'slug' IS DISTINCT FROM current_sv.payload->>'slug'
           OR cr.payload->>'version' IS DISTINCT FROM current_sv.payload->>'version'
           OR cr.payload->>'role' IS DISTINCT FROM current_sv.payload->>'role'
           OR cr.payload->>'level' IS DISTINCT FROM current_sv.payload->>'level'
           OR cr.payload->>'lineage_id' IS DISTINCT FROM lineage_id_value
           OR NOT review_contract_matches_v1(cr.input_refs[2], cr.artifact_id, current_sv.artifact_id)
           OR jsonb_typeof(cr.payload->'checks') IS DISTINCT FROM 'object'
           OR jsonb_typeof(cr.payload->'findings') IS DISTINCT FROM 'array' THEN
            RETURN false;
        END IF;
        IF cr.payload->>'phase' = 'review' THEN
            IF cr.payload->>'prompt_version' !~ '^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$'
            THEN RETURN false; END IF;
        ELSIF cr.payload->>'phase' = 'recheck' THEN
            IF cr.payload->>'prompt_version' !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$'
            THEN RETURN false; END IF;
        ELSE
            RETURN false;
        END IF;
        IF cr.artifact_id = top_id AND cr.payload->>'phase' <> 'recheck' THEN RETURN false; END IF;
        IF cr.payload->>'run_id' = ANY(seen_run_ids)
           OR cr.payload->>'reviewer_identity' = ANY(seen_reviewers)
           OR cr.payload->>'reviewer_identity' = ANY(seen_fixers)
           OR cr.payload->>'fixer_identity' = ANY(seen_reviewers) THEN
            RETURN false;
        END IF;
        seen_run_ids := array_append(seen_run_ids, cr.payload->>'run_id');
        seen_reviewers := array_append(seen_reviewers, cr.payload->>'reviewer_identity');
        seen_fixers := array_append(seen_fixers, cr.payload->>'fixer_identity');

        FOREACH check_name IN ARRAY ARRAY[
            'strict_lint','consistency','source_hash','artifact_reconciliation'
        ] LOOP
            check_value := cr.payload->'checks'->check_name;
            IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
               OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
               OR nullif(btrim(check_value->>'evidence'),'') IS NULL
               OR (cr.artifact_id = top_id AND check_value->'passed' <> 'true'::jsonb)
            THEN RETURN false; END IF;
        END LOOP;

        finding_ids := ARRAY[]::text[];
        FOR finding IN SELECT value FROM jsonb_array_elements(cr.payload->'findings') LOOP
            IF jsonb_typeof(finding) IS DISTINCT FROM 'object'
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
               OR finding->>'disposition' NOT IN ('open','resolved','disputed') THEN
                RETURN false;
            END IF;
            finding_id := finding->>'finding_id';
            IF finding_id = ANY(finding_ids) THEN RETURN false; END IF;
            finding_ids := array_append(finding_ids, finding_id);
            newer_finding := effective_findings->finding_id;
            IF newer_finding IS NULL THEN
                effective_findings := effective_findings || jsonb_build_object(finding_id, finding);
            ELSIF newer_finding->>'category' IS DISTINCT FROM finding->>'category'
               OR newer_finding->>'severity' IS DISTINCT FROM finding->>'severity'
               OR (finding->>'disposition' = 'resolved'
                   AND newer_finding->>'disposition' <> 'resolved') THEN
                RETURN false;
            END IF;
        END LOOP;

        IF expected_attempt = 1 THEN
            IF cardinality(cr.input_refs) <> 2 OR cr.payload->'prior_review_ref' <> 'null'::jsonb
            THEN RETURN false; END IF;
            EXIT;
        END IF;
        IF cardinality(cr.input_refs) <> 3
           OR cr.payload->>'prior_review_ref' IS DISTINCT FROM cr.input_refs[3]::text THEN
            RETURN false;
        END IF;
        SELECT * INTO prior FROM artifacts
        WHERE artifact_id = cr.input_refs[3] AND artifact_type = 'review';
        IF NOT FOUND OR coalesce(prior.timestamp_end, prior.timestamp_start) > cr.timestamp_start
        THEN RETURN false; END IF;
        IF cardinality(prior.input_refs) < 2 THEN RETURN false; END IF;
        SELECT * INTO prior_sv FROM artifacts
        WHERE artifact_id = prior.input_refs[1] AND artifact_type = 'skill_version';
        IF NOT FOUND
           OR prior.payload->>'slug' IS DISTINCT FROM cr.payload->>'slug'
           OR prior.payload->>'role' IS DISTINCT FROM cr.payload->>'role'
           OR prior.payload->>'level' IS DISTINCT FROM cr.payload->>'level'
           OR prior.payload->>'lineage_id' IS DISTINCT FROM lineage_id_value
           OR semiskill_positive_int_v1(prior.payload->'attempt') <> expected_attempt - 1
           OR skill_payload_sha256_v1(prior_sv.payload)
              IS DISTINCT FROM prior.payload->>'skill_payload_sha256' THEN
            RETURN false;
        END IF;
        IF current_sv.artifact_id = prior_sv.artifact_id THEN
            IF cr.payload->>'version' IS DISTINCT FROM prior.payload->>'version'
               OR cr.payload->>'skill_payload_sha256'
                  IS DISTINCT FROM prior.payload->>'skill_payload_sha256' THEN
                RETURN false;
            END IF;
        ELSIF NOT semiskill_semver_greater_v1(
            cr.payload->>'version', prior.payload->>'version'
        ) THEN
            RETURN false;
        END IF;
        cr := prior;
        expected_attempt := expected_attempt - 1;
    END LOOP;

    FOR finding IN SELECT value FROM jsonb_each(effective_findings) LOOP
        IF finding->>'severity' = 'blocking'
           AND finding->>'disposition' IN ('open','disputed') THEN RETURN false; END IF;
    END LOOP;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS content_review_v2_lineage_attempt_unique
ON artifacts ((payload->>'lineage_id'), (payload->>'attempt'))
WHERE artifact_type = 'review'
  AND payload->>'review_kind' = 'content_review'
  AND payload->>'schema_version' = '2';
CREATE UNIQUE INDEX IF NOT EXISTS content_review_v2_one_child
ON artifacts ((payload->>'prior_review_ref'))
WHERE artifact_type = 'review'
  AND payload->>'review_kind' = 'content_review'
  AND payload->>'schema_version' = '2'
  AND payload->>'prior_review_ref' IS NOT NULL;

REVOKE ALL ON verified_review_contracts, verified_review_contract_cells FROM PUBLIC;
GRANT SELECT ON verified_review_contracts, verified_review_contract_cells
TO semiskill_app, semiskill_pipeline, semiskill_approval_actuator, semiskill_acl_reader;
REVOKE ALL ON FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION append_verified_review_contract(
    uuid,source_system,text,actor_kind,timestamptz,timestamptz,uuid[],uuid[],text,text,
    text,numeric,jsonb,numeric,uuid,jsonb
) TO semiskill_review_coordinator;
GRANT USAGE ON SCHEMA public TO semiskill_review_coordinator;
GRANT USAGE ON TYPE source_system, actor_kind TO semiskill_review_coordinator;
REVOKE ALL ON FUNCTION review_contract_matches_v1(uuid,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION content_review_ready_v1(uuid,uuid) FROM PUBLIC;
REVOKE semiskill_review_coordinator FROM CURRENT_USER;
