-- semiskill/artifacts/migrations/0002_context.sql
-- L3 Context: ACL-enforced catalog search + provenance/reuse graph as SECURITY DEFINER functions.
-- semiskill_app (created in 0001) gets EXECUTE only; it still cannot SELECT artifacts directly.
-- Every function ACL-filters by permissions_label and pins search_path (a mutable search_path in a
-- SECURITY DEFINER function is a privilege-escalation vector). Mirrors aios 0004_provenance.sql.

-- Catalog search: PUBLISHED skill_versions only — i.e. a skill_version that a positive, published
-- `approval` artifact references (the same gate as spine/lifecycle.derive_state PUBLISHED). Nothing
-- is discoverable here until Phase C's approval actuator has written that approval. ACL-filtered,
-- with an optional text query and function/role/level facets.
CREATE OR REPLACE FUNCTION catalog_search(
    q text, allowed_labels text[],
    f_function text DEFAULT NULL, f_role text DEFAULT NULL, f_level text DEFAULT NULL,
    limit_n int DEFAULT 100)
RETURNS TABLE (artifact_id uuid, slug text, name text, description text, version text,
               skill_function text, skill_role text, skill_level text,
               permissions_label text, payload jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    SELECT sv.artifact_id,
           sv.payload->>'slug', sv.payload->>'name', sv.payload->>'description',
           sv.payload->>'version', sv.payload->>'function', sv.payload->>'role',
           sv.payload->>'level', sv.permissions_label, sv.payload
    FROM artifacts sv
    WHERE sv.artifact_type = 'skill_version'
      AND sv.permissions_label = ANY(allowed_labels)
      AND EXISTS (
          SELECT 1 FROM artifacts ap
          WHERE ap.artifact_type = 'approval'
            AND ap.payload->>'verdict' = 'approve'
            AND (ap.payload->>'published')::boolean IS TRUE
            AND sv.artifact_id = ANY(ap.input_refs)
      )
      AND (f_function IS NULL OR sv.payload->>'function' = f_function)
      AND (f_role     IS NULL OR sv.payload->>'role'     = f_role)
      AND (f_level    IS NULL OR sv.payload->>'level'    = f_level)
      AND (
          q IS NULL OR q = ''
          OR sv.payload->>'name' ILIKE '%' || q || '%'
          OR sv.payload->>'slug' ILIKE '%' || q || '%'
          OR sv.payload->>'description' ILIKE '%' || q || '%'
          OR EXISTS (SELECT 1
                     FROM jsonb_array_elements_text(coalesce(sv.payload->'tags', '[]'::jsonb)) tg
                     WHERE tg ILIKE '%' || q || '%')
      )
    ORDER BY sv.payload->>'slug'
    LIMIT limit_n;
$$;

-- Lineage: ancestry via input_refs, ACL-pruned at each hop, depth-bounded. Traces a skill's
-- verification trail (approval -> review -> scan_runs -> skill_version). Mirror of aios lineage().
CREATE OR REPLACE FUNCTION lineage(start uuid, allowed_labels text[], max_depth int)
RETURNS TABLE (artifact_id uuid, artifact_type artifact_type, permissions_label text,
               payload jsonb, depth int, parent_id uuid)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    WITH RECURSIVE walk(artifact_id, parent_id, depth) AS (
        SELECT a.artifact_id, NULL::uuid, 0
        FROM artifacts a
        WHERE a.artifact_id = start AND a.permissions_label = ANY(allowed_labels)
      UNION
        SELECT c.artifact_id, w.artifact_id, w.depth + 1
        FROM walk w
        JOIN artifacts p ON p.artifact_id = w.artifact_id
        CROSS JOIN LATERAL unnest(p.input_refs) AS ref(id)
        JOIN artifacts c ON c.artifact_id = ref.id
        WHERE w.depth < max_depth AND c.permissions_label = ANY(allowed_labels)
    )
    SELECT w.artifact_id, a.artifact_type, a.permissions_label, a.payload, w.depth, w.parent_id
    FROM walk w JOIN artifacts a USING (artifact_id);
$$;

-- Reuse graph: the reuse_event rows referencing a skill (who reused it, how), ACL-filtered and
-- gated on the skill itself being visible to the caller (fail-closed visibility gate).
CREATE OR REPLACE FUNCTION reuse_events_for_skill(skill_id uuid, allowed_labels text[])
RETURNS TABLE (artifact_id uuid, actor text, method text, ts timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    WITH vis AS (
        SELECT 1 FROM artifacts
        WHERE artifact_id = skill_id AND artifact_type = 'skill_version'
          AND permissions_label = ANY(allowed_labels)
    )
    SELECT r.artifact_id, r.actor, r.payload->>'method', r.timestamp_start
    FROM artifacts r
    WHERE EXISTS (SELECT 1 FROM vis)
      AND r.artifact_type = 'reuse_event'
      AND skill_id = ANY(r.input_refs)
      AND r.permissions_label = ANY(allowed_labels)
    ORDER BY r.timestamp_start;
$$;

GRANT EXECUTE ON FUNCTION catalog_search(text, text[], text, text, text, int) TO semiskill_app;
GRANT EXECUTE ON FUNCTION lineage(uuid, text[], int) TO semiskill_app;
GRANT EXECUTE ON FUNCTION reuse_events_for_skill(uuid, text[]) TO semiskill_app;
