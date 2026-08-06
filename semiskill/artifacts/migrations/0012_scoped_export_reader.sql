-- One bounded, single-label read capability for offline materialization.
-- The caller cannot SELECT artifacts or enumerate all heads. The SECURITY DEFINER function checks
-- both session membership and the actively assumed role before it touches publication state.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_export_reader') THEN
        CREATE ROLE semiskill_export_reader NOLOGIN NOINHERIT NOSUPERUSER
            NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_export_label_public') THEN
        CREATE ROLE semiskill_export_label_public NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_export_label_team') THEN
        CREATE ROLE semiskill_export_label_team NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_export_label_need_to_know') THEN
        CREATE ROLE semiskill_export_label_need_to_know NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_export_label_regulated') THEN
        CREATE ROLE semiskill_export_label_regulated NOLOGIN NOINHERIT;
    END IF;
END $$;
ALTER ROLE semiskill_export_reader NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_export_label_public NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_export_label_team NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_export_label_need_to_know NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE semiskill_export_label_regulated NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO semiskill_export_reader;
GRANT USAGE ON TYPE artifact_type, source_system, actor_kind TO semiskill_export_reader;
REVOKE ALL ON artifacts FROM semiskill_export_reader;
REVOKE ALL ON verified_publication_events FROM semiskill_export_reader;
REVOKE semiskill_export_reader FROM CURRENT_USER;
REVOKE semiskill_export_label_public FROM CURRENT_USER;
REVOKE semiskill_export_label_team FROM CURRENT_USER;
REVOKE semiskill_export_label_need_to_know FROM CURRENT_USER;
REVOKE semiskill_export_label_regulated FROM CURRENT_USER;

CREATE OR REPLACE FUNCTION export_scoped_publication_bundle_v1(requested_label text)
RETURNS TABLE (
    head_approval_id uuid, head_skill_version_id uuid, head_automated_review_id uuid,
    head_content_review_id uuid, head_slug text, head_permissions_label text,
    artifact_id uuid, artifact_type artifact_type, source_system source_system,
    actor text, actor_kind actor_kind, timestamp_start timestamptz, timestamp_end timestamptz,
    input_refs uuid[], output_refs uuid[], permissions_label text, objective_tag text,
    ground_truth_ref text, eval_score numeric, rollback_ref jsonb, cost_usd numeric,
    corrects_ref uuid, payload jsonb
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
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
               head.content_review_id AS dependency_id, 0 AS depth,
               ARRAY[head.content_review_id]::uuid[] AS visited
        FROM heads head
        UNION ALL
        SELECT chain.approval_id, chain.skill_version_id, chain.automated_review_id,
               chain.content_review_id, chain.slug, chain.permissions_label,
               review.input_refs[2], chain.depth + 1,
               chain.visited || review.input_refs[2]
        FROM content_lineage chain
        JOIN artifacts review ON review.artifact_id = chain.dependency_id
          AND review.artifact_type = 'review'
          AND review.permissions_label = requested_label
        WHERE review.payload->>'review_kind' = 'content_review'
          AND review.payload->>'prior_review_ref' IS NOT NULL
          AND cardinality(review.input_refs) = 2
          AND review.input_refs[2] <> ALL(chain.visited)
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
               chain.content_review_id, chain.slug, chain.permissions_label, chain.dependency_id
        FROM content_lineage chain
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
           artifact.rollback_ref, artifact.cost_usd, artifact.corrects_ref, artifact.payload
    FROM dependencies dependency
    JOIN artifacts artifact ON artifact.artifact_id = dependency.dependency_id
      AND artifact.permissions_label = requested_label
    ORDER BY dependency.slug, artifact.timestamp_start, artifact.artifact_id;
END;
$$;

REVOKE ALL ON FUNCTION export_scoped_publication_bundle_v1(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION export_scoped_publication_bundle_v1(text)
TO semiskill_export_reader;
REVOKE ALL ON FUNCTION verified_active_publication_heads_v1() FROM semiskill_export_reader;
REVOKE ALL ON FUNCTION artifact_get(uuid, text[]) FROM semiskill_export_reader;
REVOKE ALL ON FUNCTION lineage(uuid, text[], integer) FROM semiskill_export_reader;
REVOKE ALL ON FUNCTION reuse_events_for_skill(uuid, text[]) FROM semiskill_export_reader;
REVOKE EXECUTE ON FUNCTION catalog_search(text, text[], text, text, text, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION skill_scan_report(uuid, text[]) FROM PUBLIC;
