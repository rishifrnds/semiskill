from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from semiskill.artifacts.migrate import (
    MigrationAdoptionRefused,
    _assert_repository_matches_commit,
    _assert_trusted_manifest_matches_commit,
    _resolve_migration_source,
    _validate_database_environment,
    adopt_legacy_migration_checksums,
    apply_migrations,
    plan_legacy_migration_checksums,
)
from semiskill.governance.identity import AuthenticatedHuman


MIGRATIONS = Path("semiskill/artifacts/migrations")
LEGACY_FILENAMES = tuple(f"{number:04d}_" for number in range(1, 11))


def _test_admin() -> tuple[str, dict[str, str]]:
    dsn = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://semiskill:semiskill@127.0.0.1:5432/semiskill_test",
    )
    params = conninfo_to_dict(dsn)
    params.pop("dbname", None)
    return make_conninfo(**params, dbname="postgres"), params


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    admin_dsn, params = _test_admin()
    database = f"semiskill_adopt_{uuid.uuid4().hex[:10]}_test"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    dsn = make_conninfo(**params, dbname=database)
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        shutil.copyfile(path, migration_dir / path.name)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    for prefix in LEGACY_FILENAMES:
        source = next(migration_dir.glob(f"{prefix}*.sql"))
        shutil.copyfile(source, legacy_dir / source.name)
    apply_migrations(dsn, legacy_dir)
    with psycopg.connect(dsn) as conn:
        conn.execute("UPDATE schema_migrations SET sha256=NULL")
        conn.commit()
    monkeypatch.setattr(
        "semiskill.artifacts.migrate._resolve_migration_source",
        lambda _repo_root: (migration_dir, "a" * 40),
    )
    monkeypatch.setenv("SEMISKILL_MIGRATOR_ROLE", params.get("user", "semiskill"))
    try:
        yield dsn, database, migration_dir
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def _identity() -> AuthenticatedHuman:
    return AuthenticatedHuman(
        actor="test-operator",
        subject="uid:1001",
        provider="local_os",
        auth_context={"account": "test-operator", "uid": 1001},
    )


def _adopt(dsn, database, migration_dir, plan, *, removals=()):
    return adopt_legacy_migration_checksums(
        dsn,
        migration_dir,
        expected_database=database,
        expected_plan_sha256=plan["plan_sha256"],
        remove_orphaned_test_fixtures=removals,
        identity=_identity(),
        environment="test",
        reason="Reviewed the exact legacy foundation manifest before isolated migration tests.",
    )


def _plan(dsn, database, migration_dir, **kwargs):
    return plan_legacy_migration_checksums(
        dsn,
        migration_dir,
        expected_database=database,
        environment="test",
        **kwargs,
    )


@pytest.mark.integration
def test_adoption_is_exact_audited_atomic_and_allows_future_suffix(legacy_database):
    dsn, database, migration_dir = legacy_database
    plan = _plan(dsn, database, migration_dir)
    assert plan["legacy_null_count"] == 10
    assert plan["tracked_prefix"] == [
        next(migration_dir.glob(f"{prefix}*.sql")).name for prefix in LEGACY_FILENAMES
    ]
    assert plan["repository_manifest"][-1]["filename"].startswith("001")

    result = _adopt(dsn, database, migration_dir, plan)
    assert result["plan_sha256"] == plan["plan_sha256"]
    assert len(result["adopted_filenames"]) == 10

    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT filename,sha256 FROM schema_migrations ORDER BY filename"
        ).fetchall()
        audit = conn.execute(
            "SELECT actor,payload FROM artifacts WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version'='migration-checksum-adoption/v1'"
        ).fetchone()
        assert all(checksum == hashlib.sha256(
            (migration_dir / filename).read_bytes()
        ).hexdigest() for filename, checksum in rows)
        assert audit[0] == "test-operator"
        assert audit[1]["environment"] == "test"
        assert audit[1]["reason"].startswith("Reviewed the exact legacy")
        assert audit[1]["source_commit"] == "a" * 40
        assert audit[1]["plan_sha256"] == plan["plan_sha256"]
        assert audit[1]["historical_limit"]
        with pytest.raises(psycopg.Error):
            conn.execute(
                "UPDATE artifacts SET payload='{}' WHERE artifact_id=%s", (audit[1]["adoption_id"],)
            )
        conn.rollback()
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute("TRUNCATE public.artifacts")
        conn.rollback()
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute("TRUNCATE public.artifacts CASCADE")
        conn.rollback()
        assert conn.execute(
            "SELECT count(*) FROM artifacts WHERE artifact_id=%s",
            (audit[1]["adoption_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles granted "
            "ON granted.oid=m.roleid WHERE granted.rolname IN "
            "('semiskill_approval_actuator','semiskill_acl_reader',"
            "'semiskill_export_reader','semiskill_export_label_public',"
            "'semiskill_export_label_team','semiskill_export_label_need_to_know',"
            "'semiskill_export_label_regulated')"
        ).fetchone()[0] == 0

    assert result["applied_filenames"] == [
        path.name for path in sorted(migration_dir.glob("*.sql"))
    ][10:]
    assert apply_migrations(dsn, migration_dir) == []


@pytest.mark.integration
def test_plan_refuses_wrong_database_and_unknown_tracker_history(legacy_database):
    dsn, database, migration_dir = legacy_database
    with pytest.raises(MigrationAdoptionRefused, match="database identity"):
            plan_legacy_migration_checksums(
                dsn, migration_dir, expected_database="another_database",
                environment="test",
            )
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO schema_migrations(filename,sha256) VALUES('9001_probe.sql',NULL)"
        )
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="exact trusted legacy set"):
            plan_legacy_migration_checksums(
                dsn, migration_dir, expected_database=database,
                environment="test",
            )
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE sha256 IS NOT NULL"
        ).fetchone()[0] == 0
        conn.execute("CREATE TABLE public.mig_probe(id integer)")
        conn.execute("INSERT INTO public.mig_probe VALUES (1)")
        conn.commit()

    with pytest.raises(MigrationAdoptionRefused, match="exact empty test probe"):
        _plan(
            dsn, database, migration_dir,
            remove_orphaned_test_fixtures=("9001_probe.sql",),
        )
    with psycopg.connect(dsn) as conn:
        conn.execute("TRUNCATE public.mig_probe")
        conn.commit()

    cleanup_plan = _plan(
        dsn, database, migration_dir,
        remove_orphaned_test_fixtures=("9001_probe.sql",),
    )
    result = adopt_legacy_migration_checksums(
        dsn,
        migration_dir,
        expected_database=database,
        expected_plan_sha256=cleanup_plan["plan_sha256"],
        remove_orphaned_test_fixtures=("9001_probe.sql",),
        identity=_identity(),
        environment="test",
        reason="Acknowledged an isolated historical probe without claiming its unknown bytes.",
    )
    assert result["removed_orphaned_test_fixtures"] == ["9001_probe.sql"]
    assert result["removed_orphaned_relations"] == ["public.mig_probe"]
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE filename='9001_probe.sql'"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT to_regclass('public.mig_probe')").fetchone()[0] is None


@pytest.mark.integration
def test_adoption_rechecks_raw_bytes_and_rolls_back(legacy_database):
    dsn, database, migration_dir = legacy_database
    plan = _plan(dsn, database, migration_dir)
    target = next(migration_dir.glob("0005_*.sql"))
    target.write_bytes(target.read_bytes() + b"\n-- changed after plan\n")
    with pytest.raises(MigrationAdoptionRefused, match="manifest|plan"):
        _adopt(dsn, database, migration_dir, plan)
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE sha256 IS NOT NULL"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM artifacts WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version'='migration-checksum-adoption/v1'"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_mixed_history_updates_only_null_rows_and_repeat_refuses(legacy_database):
    dsn, database, migration_dir = legacy_database
    first = next(migration_dir.glob("0001_*.sql"))
    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE schema_migrations SET sha256=%s WHERE filename=%s",
            (first_hash, first.name),
        )
        conn.commit()
    plan = _plan(dsn, database, migration_dir)
    result = _adopt(dsn, database, migration_dir, plan)
    assert first.name not in result["adopted_filenames"]
    assert len(result["adopted_filenames"]) == 9
    with pytest.raises(
        MigrationAdoptionRefused,
        match="no legacy NULL checksums|exact trusted legacy set",
    ):
        plan_legacy_migration_checksums(
            dsn, migration_dir, expected_database=database,
            environment="test",
        )
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM artifacts WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version'='migration-checksum-adoption/v1'"
        ).fetchone()[0] == 1


@pytest.mark.integration
def test_audit_insert_failure_rolls_back_every_checksum(legacy_database, monkeypatch):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute("ALTER TABLE schema_migrations DROP COLUMN sha256")
        conn.execute("INSERT INTO schema_migrations(filename) VALUES('9001_probe.sql')")
        conn.execute("CREATE TABLE public.mig_probe(id integer)")
        conn.commit()
    plan = _plan(
        dsn, database, migration_dir,
        remove_orphaned_test_fixtures=("9001_probe.sql",),
    )
    collision = uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO artifacts (artifact_id,artifact_type,source_system,actor,"
            "actor_kind,timestamp_start) VALUES (%s,'skill_version','cli','fixture',"
            "'service-account',clock_timestamp())",
            (collision,),
        )
        conn.commit()
    monkeypatch.setattr("semiskill.artifacts.migrate.uuid.uuid4", lambda: collision)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _adopt(
            dsn, database, migration_dir, plan,
            removals=("9001_probe.sql",),
        )
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM artifacts WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version'='migration-checksum-adoption/v1'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE filename='9001_probe.sql'"
        ).fetchone()[0] == 1
        assert conn.execute("SELECT to_regclass('public.mig_probe')").fetchone()[0] is not None
        assert conn.execute(
            "SELECT to_regclass('public.verified_publication_events')"
        ).fetchone()[0] is None
        assert conn.execute(
            "SELECT to_regprocedure('public.activate_verified_publication(uuid)')"
        ).fetchone()[0] is None
        assert conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='schema_migrations' "
            "AND column_name='sha256'"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_real_legacy_tracker_without_sha_column_is_adopted_only_after_review(legacy_database):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute("ALTER TABLE schema_migrations DROP COLUMN sha256")
        conn.commit()
    plan = _plan(dsn, database, migration_dir)
    assert all(row["sha256"] is None for row in plan["tracked_manifest"])
    result = _adopt(dsn, database, migration_dir, plan)
    assert len(result["adopted_filenames"]) == 10
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE sha256 IS NOT NULL"
        ).fetchone()[0] == len(tuple(migration_dir.glob("*.sql")))


@pytest.mark.integration
def test_schema_attestation_failure_never_changes_tracker(legacy_database):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute("ALTER TABLE artifacts DISABLE TRIGGER artifacts_append_only")
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="artifact_triggers_exact"):
        _plan(dsn, database, migration_dir)
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM schema_migrations WHERE sha256 IS NOT NULL"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_environment_must_match_database_classification(legacy_database, monkeypatch):
    dsn, database, migration_dir = legacy_database
    with pytest.raises(MigrationAdoptionRefused, match="development database identity"):
        plan_legacy_migration_checksums(
            dsn, migration_dir, expected_database=database, environment="development",
        )
    monkeypatch.setenv("SEMISKILL_PRODUCTION_DATABASE_NAME", database)
    with pytest.raises(MigrationAdoptionRefused, match="production database identity"):
        plan_legacy_migration_checksums(
            dsn, migration_dir, expected_database=database, environment="production",
        )


def test_development_environment_is_bound_to_the_configured_database(monkeypatch):
    monkeypatch.delenv("SEMISKILL_PRODUCTION_DATABASE_NAME", raising=False)
    monkeypatch.delenv("SEMISKILL_DEVELOPMENT_DATABASE_NAME", raising=False)
    with pytest.raises(MigrationAdoptionRefused, match="development database identity"):
        _validate_database_environment({"database_name": "semiskill"}, "development")
    monkeypatch.setenv("SEMISKILL_DEVELOPMENT_DATABASE_NAME", "semiskill")
    monkeypatch.setenv("SEMISKILL_PRODUCTION_DATABASE_NAME", "semiskill_production")
    _validate_database_environment({"database_name": "semiskill"}, "development")
    with pytest.raises(MigrationAdoptionRefused, match="development database identity"):
        _validate_database_environment({"database_name": "company_production"}, "development")
    monkeypatch.setenv("SEMISKILL_DEVELOPMENT_DATABASE_NAME", "semiskill_dev")
    _validate_database_environment({"database_name": "semiskill_dev"}, "development")


@pytest.mark.integration
def test_configured_migrator_identity_is_mandatory(legacy_database, monkeypatch):
    dsn, database, migration_dir = legacy_database
    monkeypatch.setenv("SEMISKILL_MIGRATOR_ROLE", "not_the_database_owner")
    with pytest.raises(MigrationAdoptionRefused, match="configured migration identity"):
        _plan(dsn, database, migration_dir)


@pytest.mark.integration
def test_generic_migration_bootstrap_refuses_non_test_before_schema_write(tmp_path):
    admin_dsn, params = _test_admin()
    database = f"semiskill_non_test_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    dsn = make_conninfo(**params, dbname=database)
    migration = tmp_path / "9001_probe.sql"
    migration.write_text("SELECT 1", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="restricted to isolated"):
            apply_migrations(dsn, tmp_path, allow_partial_test_directory=True)
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT to_regclass('public.schema_migrations')"
            ).fetchone()[0] is None
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.mark.integration
def test_shadow_search_path_cannot_redirect_plan_or_adoption(legacy_database):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute("CREATE SCHEMA shadow")
        conn.execute(
            "CREATE TABLE shadow.schema_migrations "
            "(filename text PRIMARY KEY, applied_at timestamptz DEFAULT now(), sha256 text)"
        )
        conn.execute("INSERT INTO shadow.schema_migrations(filename) VALUES('evil.sql')")
        conn.commit()
    params = conninfo_to_dict(dsn)
    shadow_dsn = make_conninfo(**params, options="-csearch_path=shadow,public")
    plan = _plan(shadow_dsn, database, migration_dir)
    _adopt(shadow_dsn, database, migration_dir, plan)
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT array_agg(filename ORDER BY filename) FROM shadow.schema_migrations"
        ).fetchone()[0] == ["evil.sql"]
        assert conn.execute(
            "SELECT count(*) FROM public.schema_migrations WHERE sha256 IS NULL"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_pretracked_pending_migration_with_absent_objects_is_refused(legacy_database):
    dsn, database, migration_dir = legacy_database
    pending = migration_dir / "0011_verified_publication_projection.sql"
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO public.schema_migrations(filename,sha256) VALUES(%s,%s)",
            (pending.name, hashlib.sha256(pending.read_bytes()).hexdigest()),
        )
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="exact trusted legacy set"):
        _plan(dsn, database, migration_dir)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            "CREATE OR REPLACE FUNCTION public.block_artifact_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
            "function_definitions_exact",
        ),
        (
            "DROP INDEX public.one_approval_correction_per_head; "
            "CREATE INDEX one_approval_correction_per_head ON public.artifacts(artifact_id)",
            "approval_index_exact",
        ),
        (
            "CREATE FUNCTION public.tracker_passthrough() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN RETURN NEW; END $$; "
            "CREATE TRIGGER tracker_passthrough BEFORE INSERT ON public.schema_migrations "
            "FOR EACH ROW EXECUTE FUNCTION public.tracker_passthrough()",
            "migration_tracker_has_no_triggers",
        ),
    ],
)
def test_exact_schema_attestation_rejects_same_name_or_extra_objects(
    legacy_database, mutation, finding,
):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute(mutation)
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match=finding):
        _plan(dsn, database, migration_dir)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            "ALTER TABLE public.schema_migrations DROP CONSTRAINT schema_migrations_pkey",
            "tracker_contract_exact",
        ),
        (
            "ALTER TABLE public.schema_migrations SET UNLOGGED",
            "relation_security_exact",
        ),
        (
            "UPDATE pg_index SET indisvalid=false WHERE "
            "indexrelid='public.one_approval_correction_per_head'::regclass",
            "approval_index_exact",
        ),
        (
            "CREATE INDEX unexpected_artifact_idx ON public.artifacts(actor)",
            "authority_index_inventories_exact",
        ),
        (
            "CREATE INDEX unexpected_tracker_idx ON public.schema_migrations(applied_at)",
            "authority_index_inventories_exact",
        ),
        (
            "ALTER TABLE public.schema_migrations ALTER COLUMN applied_at DROP DEFAULT",
            "tracker_contract_exact",
        ),
        (
            "ALTER TYPE public.actor_kind ADD VALUE 'rogue'",
            "artifact_enums_exact",
        ),
        (
            "GRANT CREATE ON SCHEMA public TO semiskill_pipeline",
            "schema_and_default_acl_exact|public_schema_shadow_surface_absent",
        ),
        (
            "REVOKE EXECUTE ON FUNCTION public.artifact_get(uuid,text[]) FROM semiskill_app",
            "function_security_exact",
        ),
        (
            "ALTER TABLE public.injection_corpus ENABLE ROW LEVEL SECURITY",
            "relation_security_exact",
        ),
        (
            "ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO semiskill_pipeline",
            "schema_and_default_acl_exact",
        ),
        (
            "DROP TRIGGER artifacts_append_only ON public.artifacts; "
            "CREATE TRIGGER artifacts_append_only BEFORE UPDATE OR DELETE ON public.artifacts "
            "FOR EACH ROW WHEN (false) EXECUTE FUNCTION public.block_artifact_mutation()",
            "artifact_triggers_exact",
        ),
        (
            "CREATE FUNCTION public.current_database() RETURNS name LANGUAGE sql "
            "IMMUTABLE AS $$ SELECT 'spoofed'::name $$",
            "public_function_inventory_exact",
        ),
        (
            "CREATE TABLE public.pg_roles(rolname name)",
            "public_schema_shadow_surface_absent",
        ),
        (
            "CREATE INDEX one_verified_correction_per_head ON public.artifacts(artifact_id)",
            "pending_0011_boundary_clean",
        ),
        (
            "ALTER TABLE public.judge_gold_set ADD CONSTRAINT force_positive_label "
            "CHECK (human_label = 1) NOT VALID",
            "held_out_tables_exact",
        ),
        (
            "GRANT SELECT(pattern) ON public.injection_corpus TO semiskill_pipeline",
            "authority_column_acls_absent",
        ),
        (
            "ALTER TYPE public.artifact_type OWNER TO semiskill_pipeline",
            "artifact_enum_security_exact",
        ),
        (
            "CREATE TABLE public.artifacts_child() INHERITS (public.artifacts)",
            "authority_relations_have_no_inheritance",
        ),
        (
            "CREATE TABLE public.corpus_child() INHERITS (public.injection_corpus)",
            "authority_relations_have_no_inheritance",
        ),
        (
            "GRANT SELECT(human_label) ON public.judge_gold_set TO semiskill_pipeline",
            "authority_column_acls_absent",
        ),
        (
            "GRANT SELECT(payload) ON public.artifacts TO semiskill_pipeline",
            "authority_column_acls_absent",
        ),
    ],
)
def test_tracker_trigger_and_public_shadow_contracts_are_exact(
    legacy_database, mutation, finding,
):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute(mutation)
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match=finding):
        _plan(dsn, database, migration_dir)


@pytest.mark.integration
def test_direct_rogue_table_grant_is_refused(legacy_database):
    dsn, database, migration_dir = legacy_database
    rogue = f"semiskill_rogue_acl_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(rogue)))
        conn.execute(
            sql.SQL("GRANT SELECT ON public.artifacts TO {}").format(sql.Identifier(rogue))
        )
    try:
        with pytest.raises(MigrationAdoptionRefused, match="relation_security_exact"):
            _plan(dsn, database, migration_dir)
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("REVOKE ALL ON public.artifacts FROM {}").format(
                    sql.Identifier(rogue)
                )
            )
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(rogue)))


@pytest.mark.integration
def test_apply_refuses_noncontiguous_exact_hash_suffix(legacy_database):
    dsn, _database, migration_dir = legacy_database
    repository = sorted(migration_dir.glob("*.sql"))
    with psycopg.connect(dsn) as conn:
        for path in repository[:10]:
            conn.execute(
                "UPDATE public.schema_migrations SET sha256=%s WHERE filename=%s",
                (hashlib.sha256(path.read_bytes()).hexdigest(), path.name),
            )
        suffix = repository[11]
        conn.execute(
            "INSERT INTO public.schema_migrations(filename,sha256) VALUES(%s,%s)",
            (suffix.name, hashlib.sha256(suffix.read_bytes()).hexdigest()),
        )
        conn.commit()
    with pytest.raises(RuntimeError, match="exact ordered repository prefix"):
        apply_migrations(dsn, migration_dir)


@pytest.mark.integration
def test_pending_capability_membership_for_rogue_login_is_refused(legacy_database):
    dsn, database, migration_dir = legacy_database
    rogue = f"semiskill_rogue_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(rogue)))
        conn.execute(
            sql.SQL("GRANT semiskill_approval_actuator TO {}").format(sql.Identifier(rogue))
        )
    try:
        with pytest.raises(MigrationAdoptionRefused, match="pending_0011_boundary_clean"):
            _plan(dsn, database, migration_dir)
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("REVOKE semiskill_approval_actuator FROM {}").format(
                    sql.Identifier(rogue)
                )
            )
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(rogue)))


@pytest.mark.integration
def test_orphan_cleanup_refuses_an_empty_partition(legacy_database):
    dsn, database, migration_dir = legacy_database
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO public.schema_migrations(filename,sha256) "
            "VALUES('9001_probe.sql',NULL)"
        )
        conn.execute("CREATE TABLE public.probe_parent(id integer) PARTITION BY RANGE(id)")
        conn.execute(
            "CREATE TABLE public.mig_probe PARTITION OF public.probe_parent "
            "FOR VALUES FROM (0) TO (10)"
        )
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="exact empty test probe"):
        _plan(
            dsn, database, migration_dir,
            remove_orphaned_test_fixtures=("9001_probe.sql",),
        )


@pytest.mark.parametrize(
    ("identity", "reason", "message"),
    [
        (_identity(), "Reviewed the exact manifest.\nInjected", "printable adoption reason"),
        (
            AuthenticatedHuman(
                actor="bad\nactor", subject="uid:7", provider="local_os",
                auth_context={"account": "bad\nactor", "uid": 7},
            ),
            "Reviewed the exact manifest and approved this isolated adoption.",
            "identity fields",
        ),
        (
            AuthenticatedHuman(
                actor="x" * 513, subject="uid:7", provider="local_os",
                auth_context={"account": "x" * 513, "uid": 7},
            ),
            "Reviewed the exact manifest and approved this isolated adoption.",
            "identity fields",
        ),
    ],
)
def test_actor_and_reason_reject_controls_and_oversize_values(identity, reason, message):
    with pytest.raises(MigrationAdoptionRefused, match=message):
        adopt_legacy_migration_checksums(
            "not-used", ".", expected_database="not-used",
            expected_plan_sha256="sha256:" + "0" * 64,
            identity=identity, environment="test", reason=reason,
        )


def test_collected_source_contracts_must_equal_recorded_commit(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    artifacts = root / "semiskill" / "artifacts"
    migrations = artifacts / "migrations"
    migrations.mkdir(parents=True)
    module = artifacts / "migrate.py"
    manifest = artifacts / "legacy_migration_manifest.json"
    migration = migrations / "0001_probe.sql"
    second_migration = migrations / "0002_probe.sql"
    module.write_text("# fixture\n", encoding="utf-8")
    manifest_doc = {"schema_version": "fixture/v1", "value": "trusted"}
    manifest.write_text(json.dumps(manifest_doc), encoding="utf-8")
    raw = b"SELECT 1;\n"
    second_raw = b"SELECT 2;\n"
    migration.write_bytes(raw)
    second_migration.write_bytes(second_raw)
    (root / ".gitignore").write_text("*_ignored.sql\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "tests@semiskill.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "SemiSkill Tests"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    monkeypatch.setattr("semiskill.artifacts.migrate.__file__", str(module))
    monkeypatch.setattr("semiskill.artifacts.migrate._LEGACY_MANIFEST", manifest)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "hostile-git-dir"))

    resolved_directory, resolved_head = _resolve_migration_source(root)
    assert resolved_directory == migrations and resolved_head == head

    collected = [
        {
            "filename": migration.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        {
            "filename": second_migration.name,
            "sha256": hashlib.sha256(second_raw).hexdigest(),
            "bytes": len(second_raw),
        },
    ]
    _assert_repository_matches_commit(migrations, head, collected)
    trusted_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            manifest_doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    _assert_trusted_manifest_matches_commit(migrations, head, trusted_digest)

    poisoned = [{**collected[0], "sha256": "0" * 64}]
    with pytest.raises(MigrationAdoptionRefused, match="recorded commit"):
        _assert_repository_matches_commit(migrations, head, collected[:1])
    poisoned = [{**collected[0], "sha256": "0" * 64}, collected[1]]
    with pytest.raises(MigrationAdoptionRefused, match="recorded commit"):
        _assert_repository_matches_commit(migrations, head, poisoned)
    with pytest.raises(MigrationAdoptionRefused, match="recorded commit"):
        _assert_trusted_manifest_matches_commit(
            migrations, head, "sha256:" + "0" * 64,
        )

    ignored = migrations / "9999_ignored.sql"
    ignored.write_text("SELECT 'ignored';\n", encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="committed source tree"):
        _resolve_migration_source(root)
    ignored.unlink()

    monkeypatch.delenv("GIT_DIR")
    subprocess.run(
        ["git", "update-index", "--assume-unchanged", migration.relative_to(root).as_posix()],
        cwd=root, check=True,
    )
    migration.write_text("SELECT 'assume-unchanged poison';\n", encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="recorded commit"):
        _resolve_migration_source(root)
