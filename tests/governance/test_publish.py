import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
import psycopg

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import PostgresArtifactStore, PublicationReconciliationBundle
from semiskill.authoring.review_collection import BatchRejected
from semiskill.capture.intake import build_skill_version, payload_fingerprint
from semiskill.context.retrieve import search_catalog
from semiskill.governance.identity import AuthenticatedHuman
from semiskill.governance.publish import (
    ApprovalChainInvalid,
    PublishRefused,
    decide_publication,
    resolve_frozen_approval_evidence,
)
from semiskill.governance.rollback import decide_unpublication
from tests.support import append_test_content_review

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


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.review_contract_ids = set()

    def append(self, artifact):
        self.rows[artifact.artifact_id] = artifact
        return artifact

    def append_many(self, artifacts):
        return [self.append(artifact) for artifact in artifacts]

    def append_approval(self, artifact):
        return self.append(artifact)

    def append_review_contract(self, artifact):
        self.review_contract_ids.add(artifact.artifact_id)
        return self.append(artifact)

    def verified_review_contract_ids(self):
        return set(self.review_contract_ids)

    def get(self, artifact_id):
        return self.rows.get(artifact_id)

    def by_type(self, artifact_type):
        return [
            artifact for artifact in self.rows.values()
            if artifact.artifact_type is artifact_type
        ]

    def publication_reconciliation_bundle(self):
        return PublicationReconciliationBundle(
            tuple(self.rows.values()), (), tuple(self.review_contract_ids),
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
    artifact = Artifact.new(
        artifact_type=artifact_type,
        source_system=SourceSystem.CLI,
        actor="pipeline",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        input_refs=[sv.artifact_id],
        payload={"stage": stage, "status": status,
                 "sampled": status not in {"not_run", "not_sampled"}, "hard_fail": hard_fail,
                 "safety_score": 0.0 if hard_fail else 1.0, "findings": []},
    ).with_eval_score(0.0 if hard_fail else 1.0)
    return replace(artifact, permissions_label=sv.permissions_label)


def _chain(store, *, slug="dv-x", version="1.0.0", missing_stage=None,
           judge_status="passed", judge_required=True, hard_fail=False, findings=(),
           reviewer=None, fixer=None, permissions_label="team"):
    candidate = build_skill_version(
        skill_md=skill_md(slug, version), actor="author", permissions_label=permissions_label,
    )
    sv = next((
        artifact for artifact in store.by_type(ArtifactType.SKILL_VERSION)
        if artifact.payload.get("slug") == slug
        and payload_fingerprint(artifact.payload) == payload_fingerprint(candidate.payload)
    ), None) or store.append(candidate)
    prior_review = max((
        artifact for artifact in store.by_type(ArtifactType.REVIEW)
        if artifact.payload.get("review_kind") == "content_review"
        and artifact.payload.get("slug") == slug
        and artifact.permissions_label == sv.permissions_label
        and artifact.payload.get("role") == sv.payload.get("role")
        and artifact.payload.get("level") == sv.payload.get("level")
    ), key=lambda artifact: artifact.payload.get("attempt", 0), default=None)
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
                  "judge_required": judge_required,
                 "scan_artifact_ids": [str(scan.artifact_id) for scan in scans]},
    ).with_eval_score(1.0)
    security = store.append(replace(security, permissions_label=sv.permissions_label))
    content = append_test_content_review(
        store,
        sv,
        run_id=f"run:{uuid.uuid4()}",
        batch_id="batch-1",
        reviewer_identity=reviewer,
        fixer_identity=fixer,
        checks={
            "strict_lint": {"passed": True, "evidence": "lint:1.000"},
            "consistency": {"passed": True, "evidence": "consistency:0"},
            "source_hash": {"passed": True, "evidence": "hash:matched"},
            "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
        },
        findings=findings,
        prior_review=prior_review,
    )
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
        environment="test",
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
    assert approval.payload["authentication"]["actor"] == approval.actor
    assert approval.payload["reason"]
    assert {row.slug for row in search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    )} == {"dv-x"}


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
    with pytest.raises(BatchRejected, match="not independent"):
        _chain(store, slug="dv-collision", reviewer="same", fixer="same")


@pytest.mark.integration
def test_omitted_prior_blocker_cannot_be_laundered_by_a_later_recheck(store):
    blocking = [{
        "finding_id": "F-1", "category": "technical_correctness", "severity": "blocking",
        "evidence": "Step is wrong.", "location": "SKILL.md:10",
        "required_change": "Correct it.", "disposition": "disputed",
    }]
    skill, security, first, scans = _chain(
        store, slug="dv-omitted-blocker", findings=blocking,
    )
    second = append_test_content_review(
        store,
        skill,
        run_id="run:second",
        batch_id="batch-1",
        reviewer_identity="reviewer-2",
        fixer_identity="fixer-2",
        checks={
            "strict_lint": {"passed": True, "evidence": "lint:1.000"},
            "consistency": {"passed": True, "evidence": "consistency:0"},
            "source_hash": {"passed": True, "evidence": "hash:matched"},
            "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
        },
        findings=[],
        prior_review=first,
    )
    with pytest.raises(PublishRefused, match="content review is not ready"):
        decide(store, (skill, security, second, scans))


@pytest.mark.integration
def test_missing_required_stage_hard_fail_and_required_unsampled_judge_are_refused(store):
    with pytest.raises(PublishRefused, match="required scan stages"):
        decide(store, _chain(store, slug="dv-missing", missing_stage=2))
    with pytest.raises(PublishRefused, match="hard_fail"):
        decide(store, _chain(store, slug="dv-hard", hard_fail=True))
    with pytest.raises(PublishRefused, match="judge was required"):
        decide(store, _chain(store, slug="dv-unsampled", judge_status="not_sampled"))


@pytest.mark.integration
def test_actuator_enforces_registry_facets_and_policy_derived_judge_sampling(store, pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(
            "UPDATE publication_trust_policy "
            "SET allow_unregistered_test_fixtures=false WHERE policy_id=true"
        )
        conn.commit()

    with pytest.raises(psycopg.errors.CheckViolation, match="verified publication contract"):
        decide(store, _chain(store, slug="dv-not-in-registry"))
    with pytest.raises(psycopg.errors.CheckViolation, match="verified publication contract"):
        decide(store, _chain(store, slug="dv-repo-orientation"))
    with pytest.raises(psycopg.errors.CheckViolation, match="verified publication contract"):
        decide(store, _chain(
            store,
            slug="dv-signal-trace-localisation",
            permissions_label="public",
            judge_required=False,
            judge_status="not_sampled",
        ))

    approval = decide(store, _chain(
        store, slug="dv-signal-trace-localisation", permissions_label="public",
    ))
    assert approval.payload["skill"]["slug"] == "dv-signal-trace-localisation"


@pytest.mark.integration
@pytest.mark.parametrize("version", ["x", "01.0.0", "1.0", "1." + "9" * 19 + ".0"])
def test_root_publication_requires_canonical_core_semver(store, version):
    with pytest.raises(PublishRefused, match="core semver"):
        decide(store, _chain(store, slug="dv-bad-version", version=version))


@pytest.mark.parametrize(
    ("relationship", "message"),
    [
        ("scan_before_skill", "predates completion"),
        ("scan_finishes_after_aggregate", "not complete before its aggregate"),
        ("content_before_skill", "content review predates completion"),
        ("aggregate_before_skill", "automated review predates completion"),
    ],
)
def test_publication_rejects_temporally_impossible_evidence(relationship, message):
    memory = MemoryStore()
    chain = _chain(memory, slug=f"dv-time-{relationship}")
    skill, automated, content, scans = chain
    if relationship == "scan_before_skill":
        target = replace(scans[0], timestamp_start=skill.timestamp_start - timedelta(seconds=1))
    elif relationship == "scan_finishes_after_aggregate":
        target = replace(
            scans[0], timestamp_end=automated.timestamp_start + timedelta(seconds=1),
        )
    elif relationship == "content_before_skill":
        target = replace(content, timestamp_start=skill.timestamp_start - timedelta(seconds=1))
    else:
        target = replace(automated, timestamp_start=skill.timestamp_start - timedelta(seconds=1))
    memory.rows[target.artifact_id] = target
    with pytest.raises(PublishRefused, match=message):
        decide(memory, chain)


def test_frozen_badge_rejects_review_that_completed_after_approval():
    memory = MemoryStore()
    chain = _chain(memory, slug="dv-late-review")
    approval = decide(memory, chain)
    skill, automated, _content, _scans = chain
    memory.rows[automated.artifact_id] = replace(
        automated, timestamp_end=approval.timestamp_start + timedelta(seconds=1),
    )
    with pytest.raises(ApprovalChainInvalid, match="predates its frozen review"):
        resolve_frozen_approval_evidence(
            memory, skill_version=skill, approval=approval,
        )


@pytest.mark.integration
def test_reject_records_decision_without_publishing(store, pg_dsn):
    chain = _chain(store)
    approval = decide(store, chain, decision="reject", reason="Evidence is insufficient.")
    assert approval.payload["published"] is False and approval.payload["decision"] == "reject"
    assert search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    ) == []


@pytest.mark.integration
def test_repeated_identical_decision_is_idempotent(store):
    chain = _chain(store)
    first = decide(store, chain)
    second = decide(store, chain)
    assert second.artifact_id == first.artifact_id
    assert len(store.by_type(ArtifactType.APPROVAL)) == 1


@pytest.mark.integration
def test_projection_activation_is_not_before_the_accepted_approval(store):
    approval = decide(store, _chain(store, slug="dv-causal-activation"))
    row = store.publication_reconciliation_bundle().projections[0]

    assert row.approval_id == approval.artifact_id
    assert row.activated_at >= (approval.timestamp_end or approval.timestamp_start)


@pytest.mark.integration
def test_concurrent_identical_human_decisions_return_one_projected_approval(store):
    chain = _chain(store, slug="dv-concurrent-decision")
    barrier = threading.Barrier(2)

    def approve():
        barrier.wait(timeout=5)
        return decide(store, chain)

    with ThreadPoolExecutor(max_workers=2) as executor:
        approvals = [future.result(timeout=15) for future in [
            executor.submit(approve), executor.submit(approve),
        ]]
    assert approvals[0].artifact_id == approvals[1].artifact_id
    matching = [
        approval for approval in store.by_type(ArtifactType.APPROVAL)
        if approval.payload.get("skill", {}).get("slug") == "dv-concurrent-decision"
    ]
    assert len(matching) == 1


@pytest.mark.integration
def test_new_version_atomically_supersedes_active_version(store, pg_dsn):
    first_chain = _chain(store, slug="dv-same", version="1.0.0")
    first = decide(store, first_chain)
    second_chain = _chain(store, slug="dv-same", version="2.0.0")
    second = decide(store, second_chain)
    assert second.corrects_ref == first.artifact_id
    rows = search_catalog(dsn=pg_dsn, principal=["team"], trusted_clearance=True)
    assert [(row.slug, row.version) for row in rows] == [("dv-same", "2.0.0")]


@pytest.mark.integration
def test_explicit_authenticated_unpublish_is_idempotent_and_removes_catalog_entry(store, pg_dsn):
    approval = decide(store, _chain(store, slug="dv-remove"))
    correction = decide_unpublication(
        store=store,
        published_approval_id=approval.artifact_id,
        reason="The procedure was withdrawn after a domain-policy change.",
        identity=IDENTITY,
        environment="test",
    )
    again = decide_unpublication(
        store=store,
        published_approval_id=approval.artifact_id,
        reason="A repeated command returns the existing immutable correction.",
        identity=IDENTITY,
        environment="test",
    )
    assert correction.corrects_ref == approval.artifact_id and correction.payload["published"] is False
    assert again.artifact_id == correction.artifact_id
    assert search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    ) == []


@pytest.mark.integration
def test_unpublish_does_not_reset_verified_semver_history(store, pg_dsn):
    first = decide(store, _chain(store, slug="dv-epoch", version="2.0.0"))
    decide_unpublication(
        store=store,
        published_approval_id=first.artifact_id,
        reason="Withdraw this publication epoch.",
        identity=IDENTITY,
        environment="test",
    )

    with pytest.raises(BatchRejected, match="monotonic semver bump"):
        _chain(store, slug="dv-epoch", version="1.0.0")
    with pytest.raises(PublishRefused, match="every verified publication epoch"):
        decide(store, _chain(store, slug="dv-epoch", version="2.0.0"))

    upgraded = decide(store, _chain(store, slug="dv-epoch", version="2.0.1"))
    assert upgraded.corrects_ref is None
    assert [(row.slug, row.version) for row in search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    )] == [("dv-epoch", "2.0.1")]


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
    assert search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    ) == []


@pytest.mark.integration
def test_production_identity_policy_is_required_before_any_decision_is_appended(store):
    chain = _chain(store, slug="dv-production")
    entra = AuthenticatedHuman(
        actor="alice@example.com",
        subject="object-id",
        provider="entra_oidc",
        auth_context={
            "issuer": "https://issuer.example/tenant/v2.0",
            "tenant_id": "tenant-id",
            "object_id": "object-id",
            "amr": ["mfa"],
        },
    )
    with pytest.raises(PublishRefused, match="issuer policy is not configured"):
        decide(
            store,
            chain,
            identity=entra,
            environment="production",
            expected_entra_issuer=None,
            expected_entra_tenant=None,
        )
    assert store.by_type(ArtifactType.APPROVAL) == []


@pytest.mark.integration
def test_production_identity_wrong_tenant_is_refused_before_append(store):
    chain = _chain(store, slug="dv-wrong-tenant")
    entra = AuthenticatedHuman(
        actor="alice@example.com",
        subject="object-id",
        provider="entra_oidc",
        auth_context={"issuer": "issuer", "tenant_id": "tenant", "object_id": "object-id"},
    )
    with pytest.raises(PublishRefused, match="tenant"):
        decide(
            store,
            chain,
            identity=entra,
            environment="production",
            expected_entra_issuer="issuer",
            expected_entra_tenant="different-tenant",
        )
    assert store.by_type(ArtifactType.APPROVAL) == []
