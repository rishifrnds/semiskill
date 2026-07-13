import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")


@pytest.mark.integration
def test_update_and_delete_are_blocked(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(
            "INSERT INTO artifacts (artifact_type, source_system, actor, actor_kind, timestamp_start) "
            "VALUES ('skill_version','cli','rishi','human', now())"
        )
        conn.commit()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE artifacts SET actor='x'")
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM artifacts")
        conn.rollback()
