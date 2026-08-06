-- PostgreSQL exposes jsonb_object_keys but no object-length helper.  Keep the review-contract
-- actuator's exact-field-count checks readable and immutable through this narrowly scoped helper.

CREATE OR REPLACE FUNCTION jsonb_object_length(doc jsonb) RETURNS integer
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = pg_catalog AS $$
    SELECT count(*)::integer FROM jsonb_object_keys(doc);
$$;

REVOKE ALL ON FUNCTION jsonb_object_length(jsonb) FROM PUBLIC;
