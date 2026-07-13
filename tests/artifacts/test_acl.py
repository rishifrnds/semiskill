import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")

_INSERT = ("INSERT INTO artifacts (artifact_type, source_system, actor, actor_kind, "
           "timestamp_start, permissions_label) "
           "VALUES ('skill_version','cli','rishi','human', now(), %s)")


@pytest.mark.integration
def test_app_role_cannot_select_artifacts_directly(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(_INSERT, ("regulated",))
        conn.commit()
        conn.execute("SET ROLE semiskill_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM artifacts")
        conn.rollback()  # clear the aborted transaction


@pytest.mark.integration
def test_artifact_get_filters_by_label(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        aid = conn.execute(_INSERT + " RETURNING artifact_id", ("regulated",)).fetchone()[0]
        conn.commit()
        conn.execute("SET ROLE semiskill_app")
        n_wrong = conn.execute(
            "SELECT count(*) FROM artifact_get(%s, ARRAY['team'])", (aid,)
        ).fetchone()[0]
        n_right = conn.execute(
            "SELECT count(*) FROM artifact_get(%s, ARRAY['regulated'])", (aid,)
        ).fetchone()[0]
        conn.execute("RESET ROLE")
    assert n_wrong == 0
    assert n_right == 1
