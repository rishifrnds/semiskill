import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")

_INS = ("INSERT INTO artifacts (artifact_type, source_system, actor, actor_kind, timestamp_start) "
        "VALUES (%s, 'cli', 'u', 'human', now())")


@pytest.mark.integration
def test_new_pipeline_artifact_types_present(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        vals = {r[0] for r in conn.execute(
            "SELECT unnest(enum_range(NULL::artifact_type))::text").fetchall()}
    assert {"gate_decision", "sensor_reading", "gold_set"} <= vals


@pytest.mark.integration
def test_submitter_may_append_submission_types(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET ROLE semiskill_submitter")
        for t in ("skill_version", "comment", "rating", "reuse_event"):
            conn.execute(_INS, (t,))
        conn.execute("RESET ROLE")
        conn.commit()


@pytest.mark.integration
@pytest.mark.parametrize("forged", ["approval", "scan_run", "injection_test", "review"])
def test_submitter_cannot_forge_verification_types(pg_dsn, forged):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET ROLE semiskill_submitter")
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(_INS, (forged,))
        conn.rollback()


@pytest.mark.integration
def test_owner_may_append_approval(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(_INS, ("approval",))   # as owner (privileged) — allowed
        conn.commit()
