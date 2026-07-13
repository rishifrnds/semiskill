import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.redteam.harness import BATTERY, run_battery, run_case, escapes, RedTeamCase

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.mark.integration
def test_full_battery_zero_escapes(store, pg_dsn):
    results = run_battery(store, pg_dsn)
    assert len(results) == len(BATTERY)
    assert all(r.caught for r in results)                 # every attack caught
    assert not any(r.published for r in results)          # zero escapes
    assert not any(r.corpus_readable for r in results)    # corpus stayed unreadable every case
    assert escapes(results) == []


@pytest.mark.integration
@pytest.mark.parametrize("case", BATTERY, ids=lambda c: c.name)
def test_each_case_blocked(store, pg_dsn, case):
    r = run_case(store, pg_dsn, case)
    assert r.ok, f"{case.name} ({case.attack_class}) escaped: {r}"


@pytest.mark.integration
def test_a_benign_control_is_not_caught(store, pg_dsn):
    # Sanity: a clean skill is NOT "caught" (so the malicious-blocked results aren't trivially passing
    # everything). A colluding approve on a CLEAN skill legitimately publishes it — that's not an escape.
    benign = RedTeamCase("benign-control", "none",
                         "---\nname: Clean\nslug: rt/clean\n---\nA helpful, safe skill.")
    r = run_case(store, pg_dsn, benign)
    assert r.caught is False and r.published is True and r.corpus_readable is False
