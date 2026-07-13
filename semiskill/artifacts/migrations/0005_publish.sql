-- semiskill/artifacts/migrations/0005_publish.sql
-- Publish/unpublish semantics: a skill is discoverable iff its LATEST approval is a positive,
-- published one. This lets the gated actuator unpublish/quarantine by appending a newer correcting
-- approval (published=false) — append-only, no UPDATE — and have the catalog reflect it immediately.
-- CREATE OR REPLACE replaces the 0002 definition; signature unchanged.

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
      AND (
          -- the ACTIVE approval (not superseded by a correction) for this skill must be published
          SELECT ap.payload->>'verdict' = 'approve' AND (ap.payload->>'published')::boolean IS TRUE
          FROM artifacts ap
          WHERE ap.artifact_type = 'approval' AND sv.artifact_id = ANY(ap.input_refs)
            AND NOT EXISTS (SELECT 1 FROM artifacts c
                            WHERE c.artifact_type = 'approval' AND c.corrects_ref = ap.artifact_id)
          ORDER BY ap.timestamp_start DESC
          LIMIT 1
      ) IS TRUE
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
