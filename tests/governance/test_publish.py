import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.context.retrieve import search_catalog
from semiskill.governance.gate import GateBlocked
from semiskill.governance.publish import publish_skill, PublishRefused
from semiskill.governance.rollback import unpublish_skill

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _scan(sv_id, t, hard_fail=False):
    return Artifact.new(artifact_type=t, source_system=SourceSystem.CLI, actor="pipeline",
                        actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=[sv_id],
                        payload={"hard_fail": hard_fail, "safety_score": 0.0 if hard_fail else 1.0})


def _scanned(store, verdict="approve", hard_fail=False, slug="dv/x"):
    sv = build_skill_version(skill_md=f"---\nname: X\nslug: {slug}\n---\nbody", actor="a")
    store.append(sv)
    scan = _scan(sv.artifact_id, ArtifactType.SCAN_RUN, hard_fail); store.append(scan)
    inj = _scan(sv.artifact_id, ArtifactType.INJECTION_TEST, hard_fail); store.append(inj)
    review = Artifact.new(artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI,
                          actor="controller", actor_kind=ActorKind.AGENT,
                          input_refs=[sv.artifact_id, scan.artifact_id, inj.artifact_id],
                          payload={"verdict": verdict})
    store.append(review)
    return sv, review


_YES = (lambda d: True)
_NO = (lambda d: False)


@pytest.mark.integration
def test_full_publish_path_makes_skill_discoverable(store, pg_dsn):
    sv, review = _scanned(store)
    approval = publish_skill(store=store, skill_version_id=sv.artifact_id,
                             review_id=review.artifact_id, approver_actor="alice", approver=_YES)
    assert approval.payload["published"] is True and approval.rollback_ref is not None
    assert "dv/x" in {c.slug for c in search_catalog(dsn=pg_dsn, principal=["team"])}


@pytest.mark.integration
def test_no_publish_without_human_signoff(store, pg_dsn):
    sv, review = _scanned(store)
    with pytest.raises(GateBlocked):
        publish_skill(store=store, skill_version_id=sv.artifact_id, review_id=review.artifact_id,
                      approver_actor="alice", approver=_NO)
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []           # never discoverable
    assert any(a.payload["outcome"] == "rejected"
               for a in store.by_type(ArtifactType.GATE_DECISION))        # audited


@pytest.mark.integration
def test_reject_review_refused(store, pg_dsn):
    sv, review = _scanned(store, verdict="reject")
    with pytest.raises(PublishRefused):
        publish_skill(store=store, skill_version_id=sv.artifact_id, review_id=review.artifact_id,
                      approver_actor="alice", approver=_YES)
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []


@pytest.mark.integration
def test_hard_fail_scan_refused_even_if_review_says_approve(store):
    sv, review = _scanned(store, hard_fail=True)      # forged approve review over a hard-fail scan
    with pytest.raises(PublishRefused):
        publish_skill(store=store, skill_version_id=sv.artifact_id, review_id=review.artifact_id,
                      approver_actor="alice", approver=_YES)


@pytest.mark.integration
def test_unpublish_removes_from_catalog(store, pg_dsn):
    sv, review = _scanned(store)
    approval = publish_skill(store=store, skill_version_id=sv.artifact_id,
                             review_id=review.artifact_id, approver_actor="alice", approver=_YES)
    assert {c.slug for c in search_catalog(dsn=pg_dsn, principal=["team"])} == {"dv/x"}
    corr = unpublish_skill(store=store, skill_version_id=sv.artifact_id,
                           published_approval_id=approval.artifact_id, approver_actor="alice",
                           approver=_YES)
    assert corr.corrects_ref == approval.artifact_id and corr.payload["published"] is False
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []           # quarantined
