import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import MigrationAdoptionRefused, apply_migrations

MIG = Path("semiskill/artifacts/migrations")


def _mig_count(dsn: str) -> int:
    with psycopg.connect(dsn) as conn:
        return conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]


@pytest.mark.integration
def test_apply_is_idempotent(pg_dsn, tmp_path):
    # A brand-new migration file is applied exactly once, and re-running is a no-op. Asserted as a
    # delta so it holds whether or not other migrations are already tracked in the shared DB.
    (tmp_path / "9001_probe.sql").write_text("CREATE TABLE IF NOT EXISTS mig_probe (id int);")
    # Self-clean so the test is repeatable against the shared (persistent) DB.
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS mig_probe")
        conn.execute("DELETE FROM schema_migrations WHERE filename = '9001_probe.sql'")
    before = _mig_count(pg_dsn)
    try:
        applied_first = apply_migrations(
            pg_dsn, tmp_path, allow_partial_test_directory=True,
        )
        applied_second = apply_migrations(
            pg_dsn, tmp_path, allow_partial_test_directory=True,
        )
        assert applied_first == ["9001_probe.sql"]
        assert applied_second == []            # already applied, not re-run
        assert _mig_count(pg_dsn) == before + 1
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS mig_probe")
            conn.execute("DELETE FROM schema_migrations WHERE filename='9001_probe.sql'")


@pytest.mark.integration
def test_applied_migration_content_cannot_change_silently(pg_dsn, tmp_path):
    migration = tmp_path / "9002_checksum_probe.sql"
    migration.write_text("CREATE TABLE checksum_probe (id int);", encoding="utf-8")
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS checksum_probe")
        conn.execute(
            "DELETE FROM schema_migrations WHERE filename = '9002_checksum_probe.sql'"
        )
    try:
        assert apply_migrations(
            pg_dsn, tmp_path, allow_partial_test_directory=True,
        ) == ["9002_checksum_probe.sql"]
        migration.write_text(
            "CREATE TABLE checksum_probe (id bigint);", encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="checksum differs"):
            apply_migrations(pg_dsn, tmp_path, allow_partial_test_directory=True)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS checksum_probe")
            conn.execute(
                "DELETE FROM schema_migrations WHERE filename = '9002_checksum_probe.sql'"
            )


@pytest.mark.integration
def test_legacy_null_checksum_is_never_silently_blessed(pg_dsn, tmp_path):
    migration = tmp_path / "9003_legacy_probe.sql"
    migration.write_text("SELECT 1;", encoding="utf-8")
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO schema_migrations (filename,sha256) VALUES "
            "('9003_legacy_probe.sql',NULL) ON CONFLICT (filename) DO UPDATE SET sha256=NULL"
        )
    try:
        with pytest.raises(RuntimeError, match="audited adoption is required"):
            apply_migrations(pg_dsn, tmp_path, allow_partial_test_directory=True)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute(
                "DELETE FROM schema_migrations WHERE filename='9003_legacy_probe.sql'"
            )


@pytest.mark.integration
def test_canonical_apply_refuses_global_unknown_or_null_history(pg_dsn):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO schema_migrations(filename,sha256) VALUES('9999_unknown.sql',NULL)"
        )
    try:
        with pytest.raises(RuntimeError, match="unknown or untrusted history"):
            apply_migrations(pg_dsn, MIG)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM schema_migrations WHERE filename='9999_unknown.sql'")


@pytest.mark.integration
def test_apply_rejects_noncanonical_migration_filename(pg_dsn, tmp_path):
    (tmp_path / "Not_Canonical.SQL").write_text("SELECT 1", encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="noncanonical migration filename"):
        apply_migrations(pg_dsn, tmp_path, allow_partial_test_directory=True)


@pytest.mark.integration
def test_0001_schema_present(pg_dsn):
    # The real 0001 (applied once per session) creates the 17-column artifacts table + enum.
    apply_migrations(pg_dsn, MIG)  # idempotent no-op here
    with psycopg.connect(pg_dsn) as conn:
        cols = conn.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_name='artifacts'"
        ).fetchone()[0]
        vals = {r[0] for r in conn.execute(
            "SELECT unnest(enum_range(NULL::artifact_type))::text"
        ).fetchall()}
    assert cols == 17
    assert {"skill_version", "scan_run", "injection_test", "review",
            "approval", "comment", "rating", "reuse_event"} <= vals
