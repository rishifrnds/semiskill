import os
import pytest
import psycopg
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")


def _admin_dsn() -> str:
    # 127.0.0.1, not localhost — see semiskill/config.py (Windows IPv6 ::1 stall).
    return os.environ.get("DATABASE_URL", "postgresql://semiskill:semiskill@127.0.0.1:5432/semiskill")


@pytest.fixture(scope="session")
def _migrated_db() -> str:
    """Migrate the shared test DB ONCE per session.

    We deliberately do NOT create/drop a database per test: on Docker-for-Windows CREATE/DROP
    DATABASE takes minutes (VM filesystem), so a per-test disposable DB makes the suite unusable.
    Instead every test shares this migrated DB and gets a clean `artifacts` table via TRUNCATE
    (see `pg_dsn`). Skips the whole integration suite if no Postgres is reachable.
    """
    dsn = _admin_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.OperationalError as e:
        pytest.skip(f"no Postgres reachable at {dsn}: {e}")
    apply_migrations(dsn, MIG)
    return dsn


@pytest.fixture
def pg_dsn(_migrated_db) -> str:
    """Shared migrated DB with the artifacts table truncated before each test.

    TRUNCATE (not DELETE) resets state for tests without tripping the append-only trigger, which
    only fires BEFORE UPDATE OR DELETE — so production code still cannot mutate, but tests can reset.
    """
    dsn = _migrated_db
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("TRUNCATE artifacts")
    return dsn
