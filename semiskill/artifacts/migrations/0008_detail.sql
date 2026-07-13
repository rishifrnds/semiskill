-- semiskill/artifacts/migrations/0008_detail.sql
-- Skill detail: the verification/scan report (latest review verdict + aggregate safety + per-stage
-- scan results) for a skill, ACL-gated on the skill being visible. Feeds the UI verification badge.
CREATE OR REPLACE FUNCTION skill_scan_report(skill_id uuid, allowed_labels text[])
RETURNS TABLE (verdict text, aggregate_safety numeric, stages jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    WITH vis AS (
        SELECT 1 FROM artifacts
        WHERE artifact_id = skill_id AND artifact_type = 'skill_version'
          AND permissions_label = ANY(allowed_labels)
    ),
    latest_review AS (
        SELECT r.payload->>'verdict' AS verdict, (r.payload->>'aggregate_safety')::numeric AS agg
        FROM artifacts r
        WHERE r.artifact_type = 'review' AND skill_id = ANY(r.input_refs)
        ORDER BY r.timestamp_start DESC
        LIMIT 1
    ),
    stages AS (
        SELECT coalesce(jsonb_agg(jsonb_build_object(
                   'stage', s.payload->'stage', 'safety', s.eval_score,
                   'hard_fail', s.payload->'hard_fail') ORDER BY s.timestamp_start), '[]'::jsonb) AS j
        FROM artifacts s
        WHERE s.artifact_type IN ('scan_run', 'injection_test') AND skill_id = ANY(s.input_refs)
    )
    SELECT lr.verdict, lr.agg, st.j
    FROM stages st
    LEFT JOIN latest_review lr ON true
    WHERE EXISTS (SELECT 1 FROM vis);
$$;
GRANT EXECUTE ON FUNCTION skill_scan_report(uuid, text[]) TO semiskill_app;
