from dataclasses import replace
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.capture.events import build_reuse_event
from semiskill.context.provenance import get_lineage, get_reuse

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _art(t, refs=(), label="team", payload=None):
    a = Artifact.new(artifact_type=t, source_system=SourceSystem.CLI, actor="svc",
                     actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=list(refs), payload=payload or {})
    return a if label == "team" else replace(a, permissions_label=label)


def _md(slug):
    return f"---\nname: {slug}\nslug: {slug}\n---\nbody"


@pytest.mark.integration
def test_lineage_traces_verification_trail(store, pg_dsn):
    sv = _art(ArtifactType.SKILL_VERSION); store.append(sv)
    scan = _art(ArtifactType.SCAN_RUN, refs=[sv.artifact_id]); store.append(scan)
    review = _art(ArtifactType.REVIEW, refs=[scan.artifact_id]); store.append(review)
    approval = _art(ArtifactType.APPROVAL, refs=[review.artifact_id],
                    payload={"verdict": "approve"}); store.append(approval)

    res = get_lineage(dsn=pg_dsn, start_artifact_id=approval.artifact_id, principal=["team"])
    ids = {n.artifact_id for n in res.nodes}
    assert ids == {sv.artifact_id, scan.artifact_id, review.artifact_id, approval.artifact_id}
    assert (scan.artifact_id, sv.artifact_id) in res.edges       # child edge present


@pytest.mark.integration
def test_lineage_prunes_unauthorized_at_boundary(store, pg_dsn):
    sv = _art(ArtifactType.SKILL_VERSION, label="need-to-know"); store.append(sv)
    scan = _art(ArtifactType.SCAN_RUN, refs=[sv.artifact_id]); store.append(scan)          # team
    approval = _art(ArtifactType.APPROVAL, refs=[scan.artifact_id]); store.append(approval)  # team

    res = get_lineage(dsn=pg_dsn, start_artifact_id=approval.artifact_id, principal=["team"])
    ids = {n.artifact_id for n in res.nodes}
    assert sv.artifact_id not in ids                              # pruned at the boundary
    assert {scan.artifact_id, approval.artifact_id} <= ids


@pytest.mark.integration
def test_reuse_graph(store, pg_dsn):
    sv = build_skill_version(skill_md=_md("dv/x"), actor="a"); store.append(sv)
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u1"))
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u2", method="copy"))
    recs = get_reuse(dsn=pg_dsn, skill_version_id=sv.artifact_id, principal=["team"])
    assert {r.actor for r in recs} == {"u1", "u2"}
    assert {r.method for r in recs} == {"skills-add", "copy"}


@pytest.mark.integration
def test_reuse_gated_on_skill_visibility(store, pg_dsn):
    sv = build_skill_version(skill_md=_md("dv/secret"), actor="a", permissions_label="need-to-know")
    store.append(sv)
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u1",
                                   permissions_label="need-to-know"))
    # a team-only querier cannot see the skill, so its reuse graph is empty (fail closed)
    assert get_reuse(dsn=pg_dsn, skill_version_id=sv.artifact_id, principal=["team"]) == []
