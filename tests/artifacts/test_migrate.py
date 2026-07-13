import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")


def _mig_count(dsn: str) -> int:
    with psycopg.connect(dsn) as conn:
        return conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]


@pytest.mark.integration
def test_apply_is_idempotent(pg_dsn, tmp_path):
    # A brand-new migration file is applied exactly once, and re-running is a no-op. Asserted as a
    # delta so it holds whether or not other migrations are already tracked in the shared DB.
    (tmp_path / "9001_probe.sql").write_text("CREATE TABLE IF NOT EXISTS mig_probe (id int);")
    before = _mig_count(pg_dsn)
    applied_first = apply_migrations(pg_dsn, tmp_path)
    applied_second = apply_migrations(pg_dsn, tmp_path)
    assert applied_first == ["9001_probe.sql"]
    assert applied_second == []            # already applied, not re-run
    assert _mig_count(pg_dsn) == before + 1


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
