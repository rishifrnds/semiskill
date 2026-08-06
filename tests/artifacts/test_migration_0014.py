from pathlib import Path

import psycopg
import pytest

from semiskill.artifacts.migrate import _post_migration_attestations, apply_migrations


MIGRATIONS = Path("semiskill/artifacts/migrations")


@pytest.mark.integration
def test_every_public_security_definer_places_pg_temp_last(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    with psycopg.connect(pg_dsn) as conn:
        configs = conn.execute(
            "SELECT p.oid::regprocedure::text,p.proconfig FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.prosecdef ORDER BY 1"
        ).fetchall()
    assert configs
    assert all(
        config is not None and "search_path=pg_catalog, public, pg_temp" in config
        for _signature, config in configs
    )


@pytest.mark.integration
def test_temp_artifacts_table_cannot_shadow_acl_reader(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    with psycopg.connect(pg_dsn) as conn:
        artifact_id = conn.execute(
            "INSERT INTO public.artifacts "
            "(artifact_type,source_system,actor,actor_kind,timestamp_start,permissions_label) "
            "VALUES ('skill_version','cli','fixture','human',clock_timestamp(),'public') "
            "RETURNING artifact_id"
        ).fetchone()[0]
        conn.execute(
            "CREATE TEMP TABLE artifacts (artifact_id uuid,artifact_type artifact_type,"
            "source_system source_system,permissions_label text,objective_tag text,"
            "eval_score numeric,payload jsonb)"
        )
        conn.execute("SET ROLE semiskill_app")
        visible = conn.execute(
            "SELECT count(*) FROM public.artifact_get(%s,ARRAY['public'])",
            (artifact_id,),
        ).fetchone()[0]
        conn.execute("RESET ROLE")
    assert visible == 1


@pytest.mark.integration
def test_authoritative_tables_block_truncate_and_cascade(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    with psycopg.connect(pg_dsn) as conn:
        artifact_id = conn.execute(
            "INSERT INTO public.artifacts "
            "(artifact_type,source_system,actor,actor_kind,timestamp_start) "
            "VALUES ('skill_version','cli','fixture','human',clock_timestamp()) "
            "RETURNING artifact_id"
        ).fetchone()[0]
        conn.commit()
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute("TRUNCATE public.artifacts CASCADE")
        conn.rollback()
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute("TRUNCATE public.verified_publication_events")
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) FROM public.artifacts WHERE artifact_id=%s", (artifact_id,)
        ).fetchone()[0] == 1


@pytest.mark.integration
def test_post_attestation_rejects_any_unpinned_security_definer(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("ALTER FUNCTION public.artifact_get(uuid,text[]) RESET search_path")
        assert not _post_migration_attestations(conn)["security_definer_paths_hardened"]
        conn.rollback()
