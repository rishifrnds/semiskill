"""Regression test over the Design/Verification seed wave crafted by the Workflow fan-out (G-002).

Every generated role-enablement skill must reach the catalog ONLY via the full pipeline + approval
(a passing scan_run + a real published approval — no back-door, ADR-003), and the catalog must be
faceted by function.
"""
import json
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.context.retrieve import search_catalog
from semiskill.seed import seed_skill

MIG = Path("semiskill/artifacts/migrations")
_SEEDS = json.loads((Path(__file__).parent / "fixtures" / "generated_seeds.json").read_text(encoding="utf-8"))


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.mark.integration
def test_generated_seed_wave_is_scanned_and_queued_without_auto_approval(store, pg_dsn):
    for s in _SEEDS:
        r = seed_skill(store=store, dsn=pg_dsn, skill_md=s["skill_md"])
        assert not r.published
        scans = [a for a in store.by_type(ArtifactType.SCAN_RUN) if r.skill_version_id in a.input_refs]
        assert scans and not any(a.payload.get("hard_fail") for a in scans)      # passing scan trail
        assert not any(a.input_refs and a.input_refs[0] == r.skill_version_id
                       for a in store.by_type(ArtifactType.APPROVAL))

    cat = {c.slug for c in search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    )}
    dv = {c.slug for c in search_catalog(
        dsn=pg_dsn, principal=["team"], function="design-verification",
        trusted_clearance=True,
    )}
    assert cat == set() and dv == set()
