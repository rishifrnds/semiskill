-- PostgreSQL implicitly searches a session's temporary schema first for relations and types when
-- pg_temp is omitted from search_path. Put it explicitly last for every governed SECURITY DEFINER
-- function so an untrusted caller cannot temp-shadow catalog or SemiSkill relations.

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

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
