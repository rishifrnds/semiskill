import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")


@pytest.mark.integration
def test_apply_is_idempotent(pg_dsn, tmp_path):
    mig = tmp_path / "0001_init.sql"
    mig.write_text("CREATE TABLE t (id int);")
    applied_first = apply_migrations(pg_dsn, tmp_path)
    applied_second = apply_migrations(pg_dsn, tmp_path)
    assert applied_first == ["0001_init.sql"]
    assert applied_second == []  # already applied, not re-run
    with psycopg.connect(pg_dsn) as conn:
        n = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert n == 1


@pytest.mark.integration
def test_real_0001_applies(pg_dsn):
    applied = apply_migrations(pg_dsn, MIG)
    assert "0001_artifacts.sql" in applied
    with psycopg.connect(pg_dsn) as conn:
        cols = conn.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_name='artifacts'"
        ).fetchone()[0]
        assert cols == 17
        vals = {r[0] for r in conn.execute(
            "SELECT unnest(enum_range(NULL::artifact_type))::text"
        ).fetchall()}
    assert {"skill_version", "scan_run", "injection_test", "review",
            "approval", "comment", "rating", "reuse_event"} <= vals
