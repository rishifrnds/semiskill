import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.gate import make_content_review
from semiskill.capture.intake import build_skill_version, payload_fingerprint
from semiskill.context.retrieve import search_catalog
from semiskill.governance.identity import AuthenticatedHuman
from semiskill.governance.publish import PublishRefused, decide_publication
from semiskill.governance.rollback import decide_unpublication

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


IDENTITY = AuthenticatedHuman(
    actor="RISHI_PC\\rishi",
    subject="S-1-5-21-test",
    provider="local_os",
    auth_context={"account": "RISHI_PC\\rishi", "sid": "S-1-5-21-test"},
)


def skill_md(slug, version="1.0.0"):
    return f"""---
name: {slug}
description: Check {slug}. Use when it needs verification.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: {slug}
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: {version}
---
# Procedure

1. Inspect bounded evidence and record the result.
"""


def _scan(sv, stage, *, status="passed", hard_fail=False):
    artifact_type = ArtifactType.INJECTION_TEST if stage == 3 else ArtifactType.SCAN_RUN
    return Artifact.new(
        artifact_type=artifact_type,
        source_system=SourceSystem.CLI,
        actor="pipeline",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        input_refs=[sv.artifact_id],
        payload={"stage": stage, "status": status, "hard_fail": hard_fail,
                 "safety_score": 0.0 if hard_fail else 1.0, "findings": []},
    )


def _chain(store, *, slug="dv-x", version="1.0.0", missing_stage=None,
           judge_status="passed", hard_fail=False, findings=(), reviewer="reviewer", fixer="fixer"):
    sv = store.append(build_skill_version(skill_md=skill_md(slug, version), actor="author"))
    scans = []
    for stage in range(1, 6):
        if stage == missing_stage:
            continue
        scan = _scan(sv, stage, status=judge_status if stage == 5 else "passed",
                     hard_fail=hard_fail and stage == 1)
        scans.append(store.append(scan))
    security = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="controller",
        actor_kind=ActorKind.AGENT,
        input_refs=[sv.artifact_id, *[scan.artifact_id for scan in scans]],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": "reject" if hard_fail else "approve", "aggregate_safety": 1.0,
                 "judge_required": True,
                 "scan_artifact_ids": [str(scan.artifact_id) for scan in scans]},
    )
    security = store.append(security)
    content = make_content_review(
        skill_version=sv,
        phase="recheck",
        prompt_version="P5-RECHECK-CALIBRATED@2",
        run_id=f"run:{uuid.uuid4()}",
        batch_id="batch-1",
        attempt=1,
        reviewer_identity=reviewer,
        fixer_identity=fixer,
        checks={
            "strict_lint": {"passed": True, "evidence": "lint:1.000"},
            "consistency": {"passed": True, "evidence": "consistency:0"},
            "source_hash": {"passed": True, "evidence": "hash:matched"},
            "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
        },
        findings=findings,
    )
    content = store.append(content)
    return sv, security, content, scans


def decide(store, chain, **overrides):
    sv, security, content, _scans = chain
    args = dict(
        store=store,
        skill_version_id=sv.artifact_id,
        automated_review_id=security.artifact_id,
        content_review_id=content.artifact_id,
        expected_payload_sha256=payload_fingerprint(sv.payload),
        decision="approve",
        reason="Reviewed the exact evidence and accepted the residual risk.",
        identity=IDENTITY,
        environment="development",
    )
    args.update(overrides)
    return decide_publication(**args)


@pytest.mark.integration
def test_approval_binds_identity_version_hash_reason_and_both_reviews(store, pg_dsn):
    chain = _chain(store)
    approval = decide(store, chain)
    sv, security, content, scans = chain

    assert approval.actor_kind is ActorKind.HUMAN
    assert approval.input_refs == [sv.artifact_id, security.artifact_id, content.artifact_id]
    assert approval.payload["schema_version"] == "approval/v1"
    assert approval.payload["skill"]["payload_sha256"] == payload_fingerprint(sv.payload)
    assert approval.payload["evidence"]["scan_artifact_ids"] == [str(s.artifact_id) for s in scans]
    assert approval.payload["authentication"]["provider"] == "local_os"
    assert approval.payload["reason"]
    assert {row.slug for row in search_catalog(dsn=pg_dsn, principal=["team"])} == {"dv-x"}


@pytest.mark.integration
def test_wrong_expected_hash_or_detached_review_is_refused(store):
    chain = _chain(store)
    with pytest.raises(PublishRefused, match="payload hash"):
        decide(store, chain, expected_payload_sha256="0" * 64)

    other = _chain(store, slug="dv-other")
    with pytest.raises(PublishRefused, match="automated review"):
        decide(store, chain, automated_review_id=other[1].artifact_id)


@pytest.mark.integration
def test_open_blocking_finding_and_identity_collision_are_refused(store):
    blocking = [{
        "finding_id": "F-1", "category": "technical_correctness", "severity": "blocking",
        "evidence": "Step is wrong.", "location": "SKILL.md:10",
        "required_change": "Correct it.", "disposition": "open",
    }]
    with pytest.raises(PublishRefused, match="content review is not ready"):
        decide(store, _chain(store, slug="dv-blocked", findings=blocking))
    with pytest.raises(PublishRefused, match="content review is not ready"):
        decide(store, _chain(store, slug="dv-collision", reviewer="same", fixer="same"))


@pytest.mark.integration
def test_missing_required_stage_hard_fail_and_required_unsampled_judge_are_refused(store):
    with pytest.raises(PublishRefused, match="required scan stages"):
        decide(store, _chain(store, slug="dv-missing", missing_stage=2))
    with pytest.raises(PublishRefused, match="hard_fail"):
        decide(store, _chain(store, slug="dv-hard", hard_fail=True))
    with pytest.raises(PublishRefused, match="judge was required"):
        decide(store, _chain(store, slug="dv-unsampled", judge_status="not_sampled"))


@pytest.mark.integration
def test_reject_records_decision_without_publishing(store, pg_dsn):
    chain = _chain(store)
    approval = decide(store, chain, decision="reject", reason="Evidence is insufficient.")
    assert approval.payload["published"] is False and approval.payload["decision"] == "reject"
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []


@pytest.mark.integration
def test_repeated_identical_decision_is_idempotent(store):
    chain = _chain(store)
    first = decide(store, chain)
    second = decide(store, chain)
    assert second.artifact_id == first.artifact_id
    assert len(store.by_type(ArtifactType.APPROVAL)) == 1


@pytest.mark.integration
def test_new_version_atomically_supersedes_active_version(store, pg_dsn):
    first_chain = _chain(store, slug="dv-same", version="1.0.0")
    first = decide(store, first_chain)
    second_chain = _chain(store, slug="dv-same", version="2.0.0")
    second = decide(store, second_chain)
    assert second.corrects_ref == first.artifact_id
    rows = search_catalog(dsn=pg_dsn, principal=["team"])
    assert [(row.slug, row.version) for row in rows] == [("dv-same", "2.0.0")]


@pytest.mark.integration
def test_explicit_authenticated_unpublish_is_idempotent_and_removes_catalog_entry(store, pg_dsn):
    approval = decide(store, _chain(store, slug="dv-remove"))
    correction = decide_unpublication(
        store=store,
        published_approval_id=approval.artifact_id,
        reason="The procedure was withdrawn after a domain-policy change.",
        identity=IDENTITY,
        environment="development",
    )
    again = decide_unpublication(
        store=store,
        published_approval_id=approval.artifact_id,
        reason="A repeated command returns the existing immutable correction.",
        identity=IDENTITY,
        environment="development",
    )
    assert correction.corrects_ref == approval.artifact_id and correction.payload["published"] is False
    assert again.artifact_id == correction.artifact_id
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []


@pytest.mark.integration
def test_legacy_callback_style_approval_is_preserved_but_not_catalog_authoritative(store, pg_dsn):
    sv, security, _content, _scans = _chain(store, slug="dv-legacy")
    legacy = Artifact.new(
        artifact_type=ArtifactType.APPROVAL,
        source_system=SourceSystem.WEB,
        actor="legacy",
        actor_kind=ActorKind.HUMAN,
        input_refs=[sv.artifact_id, security.artifact_id],
        payload={"verdict": "approve", "published": True},
    )
    store.append(legacy)
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []
