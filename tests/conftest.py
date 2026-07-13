import os
import uuid
import pytest
import psycopg


def _admin_dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://semiskill:semiskill@localhost:5432/semiskill")


@pytest.fixture
def pg_dsn():
    """A disposable database per test, dropped on teardown (mirrors AIOS).

    Skips the test (rather than failing) when no Postgres is reachable, so the unit suite stays
    green on a machine without the dev DB up. Bring the DB up with `docker compose up -d db`.
    """
    base = _admin_dsn()
    dbname = f"semiskill_test_{uuid.uuid4().hex[:8]}"
    try:
        with psycopg.connect(base, autocommit=True, connect_timeout=3) as conn:
            conn.execute(f'CREATE DATABASE "{dbname}"')
    except psycopg.OperationalError as e:
        pytest.skip(f"no Postgres reachable at {base}: {e}")
    test_dsn = base.rsplit("/", 1)[0] + f"/{dbname}"
    try:
        yield test_dsn
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (dbname,),
            )
            conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
