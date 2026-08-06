import psycopg
import pytest

from tests.conftest import (
    _TEST_REQUIRED_CAPABILITIES,
    _direct_capability_memberships,
    _test_capability_lease,
)


@pytest.mark.integration
def test_capability_lease_restores_exact_memberships_after_failure(_migrated_db):
    dsn = _migrated_db
    with psycopg.connect(dsn) as conn:
        member = conn.execute("SELECT session_user").fetchone()[0]
        original = _direct_capability_memberships(conn, member)

    with pytest.raises(RuntimeError, match="forced fixture failure"):
        with _test_capability_lease(dsn):
            with psycopg.connect(dsn) as conn:
                assert _direct_capability_memberships(conn, member) == _TEST_REQUIRED_CAPABILITIES
            raise RuntimeError("forced fixture failure")

    with psycopg.connect(dsn) as conn:
        assert _direct_capability_memberships(conn, member) == original
