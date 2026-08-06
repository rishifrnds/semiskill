from dataclasses import replace
import uuid

import pytest

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.authoring.gate import (
    INVALID,
    READY,
    REVIEWED,
    STALE,
    make_content_review,
    readiness_for_review,
    readiness_for_version,
)
from semiskill.capture.intake import build_skill_version
from semiskill.authoring.review_collection import (
    BatchRejected,
    ReviewBatchContract,
    ReviewCellContract,
    issue_review_batch_contract,
)


SKILL_MD = """---
name: dv-review-contract
description: Review a contract. Use when a contract needs checking.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Review Contract
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: 1.0.0
---
# Review Contract

Follow the bounded procedure and record exact evidence.
"""


class Store:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.review_contract_ids = {
            row.artifact_id for row in self.rows
            if row.artifact_type is ArtifactType.GATE_DECISION
        }

    def append(self, artifact):
        self.rows.append(artifact)
        return artifact

    def append_review_contract(self, artifact):
        self.rows.append(artifact)
        self.review_contract_ids.add(artifact.artifact_id)
        return artifact

    def verified_review_contract_ids(self):
        return set(self.review_contract_ids)

    def get(self, artifact_id):
        return next((a for a in self.rows if a.artifact_id == artifact_id), None)

    def by_type(self, artifact_type):
        return [a for a in self.rows if a.artifact_type is artifact_type]


def skill():
    return build_skill_version(skill_md=SKILL_MD, actor="author")


def checks(**overrides):
    value = {
        "strict_lint": {"passed": True, "evidence": "lint:1.000"},
        "consistency": {"passed": True, "evidence": "consistency:0"},
        "source_hash": {"passed": True, "evidence": "sha256:matched"},
        "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
    }
    value.update(overrides)
    return value


def finding(*, severity="blocking", disposition="open", finding_id="F-1"):
    return {
        "finding_id": finding_id,
        "category": "technical_correctness",
        "severity": severity,
        "evidence": "Step 2 names a signal that does not exist.",
        "location": "SKILL.md:42",
        "required_change": "Use the registry signal name.",
        "disposition": disposition,
    }


def review(store, sv, **overrides):
    args = dict(
        skill_version=sv,
        phase="recheck",
        prompt_version="P5-RECHECK-CALIBRATED@2",
        run_id="run-1",
        batch_id="batch-1",
        attempt=1,
        reviewer_identity="reviewer-context-1",
        fixer_identity="fixer-context-1",
        checks=checks(),
        findings=[],
    )
    args.update(overrides)
    prior = args.get("prior_review")
    if args["phase"] == "recheck" and args["attempt"] == 1 and prior is None:
        prior = review(
            store,
            sv,
            phase="review",
            prompt_version="P1-ADVERSARIAL-REVIEW@2",
            run_id=f"{args['run_id']}:p1",
            batch_id=f"{args['batch_id']}:p1",
            attempt=1,
            reviewer_identity=f"{args['reviewer_identity']}:p1",
            fixer_identity=f"{args['fixer_identity']}:p1",
            checks=args["checks"],
            findings=args["findings"],
        )
        args["prior_review"] = prior
        args["attempt"] = 2
    lineage_id = args.pop(
        "lineage_id",
        prior.payload["lineage_id"] if prior is not None else str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"gate-test:{sv.payload['slug']}")
        ),
    )
    contract = ReviewBatchContract(
        batch_id=args["batch_id"],
        run_id=args["run_id"],
        phase=args["phase"],
        prompt_version=args["prompt_version"],
        attempt=args["attempt"],
        cells={sv.payload["slug"]: ReviewCellContract(
            skill_version=sv,
            reviewer_identity=args["reviewer_identity"],
            fixer_identity=args["fixer_identity"],
            checks=args["checks"],
            lineage_id=lineage_id,
            prior_review_ref=prior.artifact_id if prior is not None else None,
        )},
        issuer_identity="test-review-coordinator",
        authentication_context={
            "provider": "test", "subject_sha256": "sha256:" + "a" * 64,
        },
    )
    issued = issue_review_batch_contract(store=store, contract=contract)
    artifact = make_content_review(
        **args,
        lineage_id=lineage_id,
        contract_artifact=issued.contract_artifact,
    )
    return store.append(artifact)


def test_agent_ready_claim_is_ignored_when_blocking_finding_is_open():
    sv = skill()
    store = Store([sv])
    review(store, sv, findings=[finding()], agent_ready_claim=True)
    state = readiness_for_version(store, sv)

    assert state.status == REVIEWED
    assert not state.ready and state.open_blocking_findings == 1


def test_zero_open_blockers_is_ready_only_with_passing_checks():
    sv = skill()
    ready_store = Store([sv])
    review(ready_store, sv, findings=[finding(disposition="resolved")])
    assert readiness_for_version(ready_store, sv).status == READY

    failed_store = Store([sv])
    review(
        failed_store, sv,
        run_id="run-2",
        checks=checks(consistency={"passed": False, "evidence": "C005"}),
    )
    state = readiness_for_version(failed_store, sv)
    assert state.status == REVIEWED and not state.ready
    assert "check consistency did not pass" in state.errors


def test_review_for_old_payload_hash_is_stale_after_skill_edit():
    old = skill()
    store = Store([old])
    review(store, old)
    changed = replace(old, payload={**old.payload, "body": old.payload["body"] + "\nChanged."})
    store.rows.append(changed)

    state = readiness_for_version(store, changed)

    assert state.status == STALE and not state.ready
    assert "payload hash does not match skill version" in state.errors


def test_malformed_later_version_lineage_is_rejected_before_it_can_poison_readiness():
    first_version = skill()
    store = Store([first_version])
    review(store, first_version)
    second_version = build_skill_version(
        skill_md=SKILL_MD.replace("semiskill-version: 1.0.0", "semiskill-version: 2.0.0"),
        actor="author",
    )
    store.rows.append(second_version)
    with pytest.raises(BatchRejected, match="exact prior review"):
        review(store, second_version, attempt=9, run_id="later-version")
    assert readiness_for_version(store, first_version).status == READY


def test_recheck_reviewer_must_differ_from_fixer():
    sv = skill()
    store = Store([sv])
    with pytest.raises(BatchRejected, match="not independent"):
        review(store, sv, reviewer_identity="same-context", fixer_identity="same-context")


def test_recheck_must_reference_prior_attempt_and_increment_without_gaps():
    sv = skill()
    missing_store = Store([sv])
    first = review(missing_store, sv)
    with pytest.raises(BatchRejected, match="exact prior review"):
        review(missing_store, sv, attempt=3, run_id="run-2")
    assert readiness_for_version(missing_store, sv).status == READY

    gap_store = Store([sv])
    first = review(gap_store, sv)
    with pytest.raises(BatchRejected, match="increment prior review"):
        review(gap_store, sv, attempt=4, run_id="run-3", prior_review=first)
    assert readiness_for_version(gap_store, sv).status == READY


def test_duplicate_or_branched_attempts_fail_closed():
    sv = skill()
    store = Store([sv])
    first = review(store, sv)
    review(store, sv, run_id="run-duplicate", reviewer_identity="reviewer-2")
    state = readiness_for_version(store, sv)
    assert state.status == INVALID
    assert "content review lineage has duplicate attempt 1" in state.errors

    review(store, sv, attempt=3, run_id="run-2", prior_review=first,
           reviewer_identity="reviewer-3")
    review(store, sv, attempt=3, run_id="run-branch", prior_review=first,
           reviewer_identity="reviewer-4")
    state = readiness_for_version(store, sv)
    assert state.status == INVALID
    assert "content review lineage has duplicate attempt 3" in state.errors


def test_structurally_invalid_earlier_round_cannot_anchor_ready_recheck():
    sv = skill()
    store = Store([sv])
    with pytest.raises(BatchRejected, match="not independent"):
        review(store, sv, reviewer_identity="same", fixer_identity="same")


def test_slug_version_role_and_level_must_match_skill_version():
    sv = skill()
    store = Store([sv])
    art = review(store, sv)
    bad_payload = {**art.payload, "role": "soc-dv-engineer"}
    bad = replace(art, payload=bad_payload)
    store.rows[-1] = bad
    state = readiness_for_version(store, sv)
    assert state.status == INVALID and "role does not match skill version" in state.errors


def test_legacy_and_security_reviews_never_count_as_content_readiness():
    sv = skill()
    legacy = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="legacy-import",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        payload={"review_kind": "content_review_legacy", "ready": True, "slug": sv.payload["slug"]},
    )
    security = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="controller",
        actor_kind=ActorKind.AGENT,
        input_refs=[sv.artifact_id],
        payload={"review_kind": "security_aggregate", "verdict": "approve"},
    )
    state = readiness_for_version(Store([sv, legacy, security]), sv)
    assert state.status == "unreviewed" and not state.ready


def test_disputed_blocking_finding_blocks_and_all_rounds_remain_queryable():
    sv = skill()
    store = Store([sv])
    first = review(store, sv, findings=[finding(disposition="open")])
    second = review(
        store, sv,
        attempt=3,
        run_id="run-2",
        reviewer_identity="reviewer-context-2",
        prior_review=first,
        findings=[finding(disposition="disputed")],
    )
    state = readiness_for_version(store, sv)

    assert state.status == REVIEWED and state.open_blocking_findings == 1
    assert store.get(first.artifact_id) is first and store.get(second.artifact_id) is second


def test_omitted_prior_blocker_remains_effective_until_explicitly_resolved():
    sv = skill()
    store = Store([sv])
    first = review(store, sv, findings=[finding(disposition="disputed")])
    omitted = review(
        store, sv,
        attempt=3,
        run_id="run-2",
        reviewer_identity="reviewer-context-2",
        prior_review=first,
        findings=[],
    )
    blocked = readiness_for_version(store, sv)
    assert blocked.status == REVIEWED and blocked.open_blocking_findings == 1

    resolved = review(
        store, sv,
        attempt=4,
        run_id="run-3",
        reviewer_identity="reviewer-context-3",
        prior_review=omitted,
        findings=[finding(disposition="resolved")],
    )
    assert readiness_for_version(store, sv).status == READY
    assert readiness_for_review(store, sv, first).status == REVIEWED

    review(
        store, sv,
        attempt=5,
        run_id="run-4",
        reviewer_identity="reviewer-context-4",
        prior_review=resolved,
        findings=[],
    )
    final_state = readiness_for_version(store, sv)
    assert final_state.status == READY
    assert [(row.finding_id, row.disposition) for row in final_state.effective_findings] == [
        ("F-1", "resolved"),
    ]


def test_finding_identity_and_reviewer_context_are_immutable_across_lineage():
    sv = skill()
    store = Store([sv])
    first = review(store, sv, findings=[finding()])
    changed = finding(disposition="resolved")
    changed["severity"] = "non_blocking"
    review(
        store, sv,
        attempt=3,
        run_id="run-2",
        reviewer_identity="reviewer-context-1",
        prior_review=first,
        findings=[changed],
    )
    state = readiness_for_version(store, sv)
    assert state.status == INVALID
    assert "finding F-1 identity changed across review attempts" in state.errors
    assert "reviewer_identity must be unique across the review lineage" in state.errors


def test_malformed_string_boolean_is_invalid_not_coerced():
    sv = skill()
    store = Store([sv])
    art = review(store, sv)
    malformed = replace(art, payload={
        **art.payload,
        "checks": {**art.payload["checks"], "strict_lint": {"passed": "true", "evidence": "x"}},
    })
    store.rows[-1] = malformed
    state = readiness_for_version(store, sv)
    assert state.status == INVALID and "check strict_lint passed must be a boolean" in state.errors
