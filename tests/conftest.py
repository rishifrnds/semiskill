import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")


def _test_dsn() -> str:
    """Return an isolated test database and fail closed on a catalog-looking database name."""
    dsn = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://semiskill:semiskill@127.0.0.1:5432/semiskill_test",
    )
    database = conninfo_to_dict(dsn).get("dbname", "")
    if not database.endswith("_test"):
        raise RuntimeError(
            "TEST_DATABASE_URL dbname must end in '_test'; refusing to truncate a catalog database"
        )
    return dsn


def _ensure_test_database(dsn: str) -> None:
    """Create the exact guarded local test DB when a container predates the init file."""
    params = conninfo_to_dict(dsn)
    database = params.pop("dbname")
    admin_dsn = make_conninfo(**params, dbname="postgres")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))


@pytest.fixture(scope="session")
def _migrated_db() -> str:
    """Create/migrate the isolated test DB once; never fall back to DATABASE_URL."""
    dsn = _test_dsn()
    try:
        _ensure_test_database(dsn)
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.OperationalError as exc:
        pytest.skip(f"no Postgres reachable at guarded test database: {exc}")
    apply_migrations(dsn, MIG)
    return dsn


@pytest.fixture
def pg_dsn(_migrated_db) -> str:
    """Reset only the isolated `_test` database before each integration test."""
    dsn = _migrated_db
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("TRUNCATE verified_publication_events, artifacts")
        conn.execute("DELETE FROM publication_trust_policy")
        current_user = conn.execute("SELECT current_user").fetchone()[0]
        conn.execute(
            sql.SQL("GRANT semiskill_approval_actuator TO {}")
            .format(sql.Identifier(current_user))
        )
        conn.execute(
            sql.SQL("GRANT semiskill_acl_reader TO {}")
            .format(sql.Identifier(current_user))
        )
        conn.execute(
            "INSERT INTO publication_trust_policy "
            "(policy_id,environment,database_name,policy_version,approve_threshold,enabled,"
            "allow_unregistered_test_fixtures) "
            "VALUES (true,'test',current_database(),'publication-v1',0.8,true,true)"
        )
    return dsn
