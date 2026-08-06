-- approval/v1: authenticated, exact-version publication decisions. Legacy approvals remain in the
-- append-only log but are no longer catalog-authoritative.

CREATE UNIQUE INDEX IF NOT EXISTS one_approval_correction_per_head
ON artifacts (corrects_ref)
WHERE artifact_type = 'approval' AND corrects_ref IS NOT NULL;

CREATE OR REPLACE FUNCTION validate_approval_v1() RETURNS trigger AS $$
DECLARE
    skill_id uuid;
    automated_id uuid;
    content_id uuid;
    decision text;
    provider text;
BEGIN
    IF NEW.artifact_type <> 'approval'
       OR NEW.payload->>'schema_version' IS DISTINCT FROM 'approval/v1' THEN
        RETURN NEW;
    END IF;
    IF NEW.actor_kind <> 'human' THEN
        RAISE EXCEPTION 'approval/v1 actor_kind must be human';
    END IF;
    decision := NEW.payload->>'decision';
    IF decision NOT IN ('approve', 'reject') THEN
        RAISE EXCEPTION 'approval/v1 decision must be approve or reject';
    END IF;
    IF nullif(btrim(NEW.payload->>'reason'), '') IS NULL THEN
        RAISE EXCEPTION 'approval/v1 reason is required';
    END IF;
    provider := NEW.payload#>>'{authentication,provider}';
    IF provider NOT IN ('local_os', 'entra_oidc')
       OR nullif(btrim(NEW.payload#>>'{authentication,subject}'), '') IS NULL THEN
        RAISE EXCEPTION 'approval/v1 authenticated subject/provider is required';
    END IF;
    IF cardinality(NEW.input_refs) <> 3 THEN
        RAISE EXCEPTION 'approval/v1 requires exact skill, automated review, content review refs';
    END IF;
    skill_id := (NEW.payload#>>'{skill,artifact_id}')::uuid;
    automated_id := (NEW.payload#>>'{evidence,automated_review_id}')::uuid;
    content_id := (NEW.payload#>>'{evidence,content_review_id}')::uuid;
    IF NEW.input_refs[1] <> skill_id OR NEW.input_refs[2] <> automated_id
       OR NEW.input_refs[3] <> content_id THEN
        RAISE EXCEPTION 'approval/v1 payload refs disagree with input_refs';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=skill_id
                   AND artifact_type='skill_version')
       OR NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=automated_id
                      AND artifact_type='review' AND payload->>'review_kind'='security_aggregate')
       OR NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=content_id
                      AND artifact_type='review' AND payload->>'review_kind'='content_review') THEN
        RAISE EXCEPTION 'approval/v1 evidence artifact types are invalid';
    END IF;
    IF ((NEW.payload->>'published')::boolean) IS DISTINCT FROM (decision = 'approve') THEN
        RAISE EXCEPTION 'approval/v1 published state disagrees with decision';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_approval_v1_insert ON artifacts;
CREATE TRIGGER validate_approval_v1_insert
BEFORE INSERT ON artifacts
FOR EACH ROW EXECUTE FUNCTION validate_approval_v1();

CREATE OR REPLACE FUNCTION catalog_search(
    q text, allowed_labels text[],
    f_function text DEFAULT NULL, f_role text DEFAULT NULL, f_level text DEFAULT NULL,
    limit_n int DEFAULT 100)
RETURNS TABLE (artifact_id uuid, slug text, name text, description text, version text,
               skill_function text, skill_role text, skill_level text,
               permissions_label text, payload jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    WITH valid_active AS (
        SELECT DISTINCT ON (ap.payload#>>'{skill,slug}') ap.*
        FROM artifacts ap
        WHERE ap.artifact_type='approval'
          AND ap.actor_kind='human'
          AND ap.payload->>'schema_version'='approval/v1'
          AND ap.payload->>'decision'='approve'
          AND (ap.payload->>'published')::boolean IS TRUE
          AND ap.permissions_label=ANY(allowed_labels)
          AND NOT EXISTS (SELECT 1 FROM artifacts c WHERE c.artifact_type='approval'
                          AND c.corrects_ref=ap.artifact_id)
          AND NOT EXISTS (
              SELECT 1 FROM unnest(ap.input_refs) ref
              JOIN artifacts evidence ON evidence.artifact_id=ref
              WHERE NOT evidence.permissions_label=ANY(allowed_labels)
          )
        ORDER BY ap.payload#>>'{skill,slug}', ap.timestamp_start DESC, ap.artifact_id DESC
    )
    SELECT sv.artifact_id,
           sv.payload->>'slug', sv.payload->>'name', sv.payload->>'description',
           sv.payload->>'version', sv.payload->>'function', sv.payload->>'role',
           sv.payload->>'level', sv.permissions_label, sv.payload
    FROM valid_active ap
    JOIN artifacts sv ON sv.artifact_id=(ap.payload#>>'{skill,artifact_id}')::uuid
    WHERE sv.artifact_type='skill_version'
      AND sv.permissions_label=ANY(allowed_labels)
      AND (f_function IS NULL OR sv.payload->>'function'=f_function)
      AND (f_role IS NULL OR sv.payload->>'role'=f_role)
      AND (f_level IS NULL OR sv.payload->>'level'=f_level)
      AND (q IS NULL OR q='' OR sv.payload->>'name' ILIKE '%' || q || '%'
           OR sv.payload->>'slug' ILIKE '%' || q || '%'
           OR sv.payload->>'description' ILIKE '%' || q || '%'
           OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(
                      coalesce(sv.payload->'tags','[]'::jsonb)) tag
                      WHERE tag ILIKE '%' || q || '%'))
    ORDER BY sv.payload->>'slug'
    LIMIT limit_n;
$$;

CREATE OR REPLACE FUNCTION skill_scan_report(skill_id uuid, allowed_labels text[])
RETURNS TABLE (verdict text, aggregate_safety numeric, stages jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    WITH active_approval AS (
        SELECT ap.*
        FROM artifacts ap
        WHERE ap.artifact_type='approval' AND ap.actor_kind='human'
          AND ap.payload->>'schema_version'='approval/v1'
          AND ap.payload->>'decision'='approve'
          AND (ap.payload->>'published')::boolean IS TRUE
          AND ap.payload#>>'{skill,artifact_id}'=skill_id::text
          AND ap.permissions_label=ANY(allowed_labels)
          AND NOT EXISTS (SELECT 1 FROM artifacts c WHERE c.artifact_type='approval'
                          AND c.corrects_ref=ap.artifact_id)
        ORDER BY ap.timestamp_start DESC, ap.artifact_id DESC LIMIT 1
    ), automated AS (
        SELECT r.* FROM active_approval ap
        JOIN artifacts r ON r.artifact_id=(ap.payload#>>'{evidence,automated_review_id}')::uuid
        WHERE r.permissions_label=ANY(allowed_labels)
          AND r.payload->>'review_kind'='security_aggregate'
    ), frozen_stages AS (
        SELECT coalesce(jsonb_agg(jsonb_build_object(
            'artifact_id', s.artifact_id, 'stage', s.payload->'stage',
            'status', s.payload->'status', 'sampled', s.payload->'sampled',
            'safety', s.eval_score, 'hard_fail', s.payload->'hard_fail'
        ) ORDER BY (s.payload->>'stage')::int), '[]'::jsonb) AS value
        FROM active_approval ap
        CROSS JOIN LATERAL jsonb_array_elements_text(
            ap.payload#>'{evidence,scan_artifact_ids}') ids(id)
        JOIN artifacts s ON s.artifact_id=ids.id::uuid
        WHERE s.permissions_label=ANY(allowed_labels)
    )
    SELECT automated.payload->>'verdict',
           (automated.payload->>'aggregate_safety')::numeric,
           frozen_stages.value
    FROM automated CROSS JOIN frozen_stages;
$$;

GRANT EXECUTE ON FUNCTION catalog_search(text, text[], text, text, text, int) TO semiskill_app;
GRANT EXECUTE ON FUNCTION skill_scan_report(uuid, text[]) TO semiskill_app;
