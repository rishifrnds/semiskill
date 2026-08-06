import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from semiskill.artifacts.migrate import apply_migrations

MIG = Path("semiskill/artifacts/migrations")

_TEST_CAPABILITY_ROLES = (
    "semiskill_approval_actuator",
    "semiskill_review_coordinator",
    "semiskill_acl_reader",
    "semiskill_export_reader",
    "semiskill_export_label_public",
    "semiskill_export_label_team",
    "semiskill_export_label_need_to_know",
    "semiskill_export_label_regulated",
)
_TEST_REQUIRED_CAPABILITIES = frozenset({
    "semiskill_approval_actuator",
    "semiskill_review_coordinator",
    "semiskill_acl_reader",
    "semiskill_export_reader",
    "semiskill_export_label_public",
})


def _direct_capability_memberships(conn, member: str) -> frozenset[str]:
    return frozenset(row[0] for row in conn.execute(
        "SELECT granted.rolname FROM pg_auth_members membership "
        "JOIN pg_roles granted ON granted.oid=membership.roleid "
        "JOIN pg_roles member ON member.oid=membership.member "
        "WHERE member.rolname=%s AND granted.rolname=ANY(%s) ORDER BY granted.rolname",
        (member, list(_TEST_CAPABILITY_ROLES)),
    ).fetchall())


def _direct_membership_options_are_default(conn, member: str) -> bool:
    if int(conn.execute("SHOW server_version_num").fetchone()[0]) >= 160000:
        predicate = "NOT membership.admin_option AND membership.inherit_option AND membership.set_option"
    else:
        predicate = "NOT membership.admin_option"
    return bool(conn.execute(
        "SELECT coalesce(bool_and(" + predicate + "),true) FROM pg_auth_members membership "
        "JOIN pg_roles granted ON granted.oid=membership.roleid "
        "JOIN pg_roles member ON member.oid=membership.member "
        "WHERE member.rolname=%s AND granted.rolname=ANY(%s)",
        (member, list(_TEST_CAPABILITY_ROLES)),
    ).fetchone()[0])


def _replace_direct_capability_memberships(conn, member: str, desired: frozenset[str]) -> None:
    for role in _TEST_CAPABILITY_ROLES:
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(role), sql.Identifier(member))
        )
    for role in sorted(desired):
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(sql.Identifier(role), sql.Identifier(member))
        )


@contextmanager
def _test_capability_lease(dsn: str):
    """Lease exact test-only capabilities and transactionally restore the prior direct grants."""
    member = None
    original_memberships = None
    try:
        with psycopg.connect(dsn) as conn:
            session_user, current_user = conn.execute(
                "SELECT session_user,current_user"
            ).fetchone()
            if session_user != current_user:
                raise RuntimeError("test database capability lease requires an unassumed login role")
            member = session_user
            original_memberships = _direct_capability_memberships(conn, member)
            if not _direct_membership_options_are_default(conn, member):
                raise RuntimeError("test database capability lease found non-default grant options")
            _replace_direct_capability_memberships(
                conn, member, _TEST_REQUIRED_CAPABILITIES
            )
            if _direct_capability_memberships(conn, member) != _TEST_REQUIRED_CAPABILITIES:
                raise RuntimeError("test database capability lease was not applied exactly")
            if not _direct_membership_options_are_default(conn, member):
                raise RuntimeError("test database capability lease has unsafe grant options")
        yield
    finally:
        if member is not None and original_memberships is not None:
            with psycopg.connect(dsn) as conn:
                session_user, current_user = conn.execute(
                    "SELECT session_user,current_user"
                ).fetchone()
                if session_user != member or current_user != member:
                    raise RuntimeError("test database login identity changed before lease restoration")
                _replace_direct_capability_memberships(conn, member, original_memberships)
                if _direct_capability_memberships(conn, member) != original_memberships:
                    raise RuntimeError("test database capability lease was not restored exactly")
                if not _direct_membership_options_are_default(conn, member):
                    raise RuntimeError("restored test database grants have unsafe options")


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
    # Remove only historical probe debris from the isolated test database. These exact fixtures
    # predate the per-test finally blocks; no catalog database is ever targeted by this fixture.
    with psycopg.connect(dsn, autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0]:
            conn.execute(
                "DELETE FROM schema_migrations WHERE filename IN "
                "('9001_probe.sql','9002_checksum_probe.sql','9003_legacy_probe.sql')"
            )
        conn.execute("DROP TABLE IF EXISTS mig_probe, checksum_probe")
    apply_migrations(dsn, MIG)
    return dsn


@pytest.fixture
def pg_dsn(_migrated_db) -> str:
    """Reset only `_test` and restore every cluster-global test capability afterward."""
    dsn = _migrated_db
    with _test_capability_lease(dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute("ALTER TABLE artifacts DISABLE TRIGGER artifacts_block_truncate")
            conn.execute(
                "ALTER TABLE verified_publication_events DISABLE TRIGGER "
                "verified_publication_events_block_truncate"
            )
            conn.execute(
                "ALTER TABLE verified_review_contracts DISABLE TRIGGER "
                "verified_review_contracts_block_truncate"
            )
            conn.execute(
                "ALTER TABLE verified_review_contract_cells DISABLE TRIGGER "
                "verified_review_contract_cells_block_truncate"
            )
            conn.execute(
                "TRUNCATE verified_review_contract_cells, verified_review_contracts, "
                "verified_publication_events, artifacts"
            )
            conn.execute(
                "ALTER TABLE verified_review_contract_cells ENABLE TRIGGER "
                "verified_review_contract_cells_block_truncate"
            )
            conn.execute(
                "ALTER TABLE verified_review_contracts ENABLE TRIGGER "
                "verified_review_contracts_block_truncate"
            )
            conn.execute(
                "ALTER TABLE verified_publication_events ENABLE TRIGGER "
                "verified_publication_events_block_truncate"
            )
            conn.execute("ALTER TABLE artifacts ENABLE TRIGGER artifacts_block_truncate")
            conn.execute("DELETE FROM publication_trust_policy")
            conn.execute(
                "INSERT INTO publication_trust_policy "
                "(policy_id,environment,database_name,policy_version,approve_threshold,enabled,"
                "allow_unregistered_test_fixtures) "
                "VALUES (true,'test',current_database(),'publication-v1',0.8,true,true)"
            )
        yield dsn
