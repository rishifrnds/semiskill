from dataclasses import replace

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.authoring.gate import (
    INVALID,
    READY,
    REVIEWED,
    STALE,
    make_content_review,
    readiness_for_version,
)
from semiskill.capture.intake import build_skill_version


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

    def append(self, artifact):
        self.rows.append(artifact)
        return artifact

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


def review(sv, **overrides):
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
    return make_content_review(**args)


def test_agent_ready_claim_is_ignored_when_blocking_finding_is_open():
    sv = skill()
    art = review(sv, findings=[finding()], agent_ready_claim=True)
    state = readiness_for_version(Store([sv, art]), sv)

    assert state.status == REVIEWED
    assert not state.ready and state.open_blocking_findings == 1


def test_zero_open_blockers_is_ready_only_with_passing_checks():
    sv = skill()
    ready = review(sv, findings=[finding(disposition="resolved")])
    assert readiness_for_version(Store([sv, ready]), sv).status == READY

    failed = review(
        sv,
        run_id="run-2",
        checks=checks(consistency={"passed": False, "evidence": "C005"}),
    )
    state = readiness_for_version(Store([sv, failed]), sv)
    assert state.status == REVIEWED and not state.ready
    assert "check consistency did not pass" in state.errors


def test_review_for_old_payload_hash_is_stale_after_skill_edit():
    old = skill()
    art = review(old)
    changed = replace(old, payload={**old.payload, "body": old.payload["body"] + "\nChanged."})

    state = readiness_for_version(Store([old, art, changed]), changed)

    assert state.status == STALE and not state.ready
    assert "payload hash does not match skill version" in state.errors


def test_another_version_review_cannot_shadow_exact_version_readiness():
    first_version = skill()
    first_review = review(first_version)
    second_version = build_skill_version(
        skill_md=SKILL_MD.replace("semiskill-version: 1.0.0", "semiskill-version: 2.0.0"),
        actor="author",
    )
    malformed_later = review(second_version, attempt=9, run_id="later-version")

    state = readiness_for_version(
        Store([first_version, first_review, second_version, malformed_later]), first_version,
    )

    assert state.status == READY and state.review.artifact_id == first_review.artifact_id


def test_recheck_reviewer_must_differ_from_fixer():
    sv = skill()
    art = review(sv, reviewer_identity="same-context", fixer_identity="same-context")
    state = readiness_for_version(Store([sv, art]), sv)
    assert state.status == INVALID and "reviewer and fixer identities are not independent" in state.errors


def test_recheck_must_reference_prior_attempt_and_increment_without_gaps():
    sv = skill()
    first = review(sv)
    missing = review(sv, attempt=2, run_id="run-2")
    assert readiness_for_version(Store([sv, first, missing]), sv).status == INVALID

    gap = review(sv, attempt=3, run_id="run-3", prior_review=first)
    state = readiness_for_version(Store([sv, first, gap]), sv)
    assert state.status == INVALID
    assert "attempt must increment prior review by exactly one" in state.errors


def test_duplicate_or_branched_attempts_fail_closed():
    sv = skill()
    first = review(sv)
    duplicate_root = review(sv, run_id="run-duplicate", reviewer_identity="reviewer-2")
    state = readiness_for_version(Store([sv, first, duplicate_root]), sv)
    assert state.status == INVALID
    assert "content review lineage has duplicate attempt 1" in state.errors

    second = review(sv, attempt=2, run_id="run-2", prior_review=first,
                    reviewer_identity="reviewer-3")
    branch = review(sv, attempt=2, run_id="run-branch", prior_review=first,
                    reviewer_identity="reviewer-4")
    state = readiness_for_version(Store([sv, first, second, branch]), sv)
    assert state.status == INVALID
    assert "content review lineage has duplicate attempt 2" in state.errors


def test_structurally_invalid_earlier_round_cannot_anchor_ready_recheck():
    sv = skill()
    malformed_first = review(sv, reviewer_identity="same", fixer_identity="same")
    apparently_ready = review(
        sv, attempt=2, run_id="run-2", prior_review=malformed_first,
        reviewer_identity="fresh-reviewer", fixer_identity="fresh-fixer",
    )
    state = readiness_for_version(Store([sv, malformed_first, apparently_ready]), sv)
    assert state.status == INVALID
    assert "reviewer and fixer identities are not independent" in state.errors


def test_slug_version_role_and_level_must_match_skill_version():
    sv = skill()
    art = review(sv)
    bad_payload = {**art.payload, "role": "soc-dv-engineer"}
    bad = replace(art, payload=bad_payload)
    state = readiness_for_version(Store([sv, bad]), sv)
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
    first = review(sv, findings=[finding(disposition="open")])
    second = review(
        sv,
        attempt=2,
        run_id="run-2",
        prior_review=first,
        findings=[finding(disposition="disputed")],
    )
    store = Store([sv, first, second])

    state = readiness_for_version(store, sv)

    assert state.status == REVIEWED and state.open_blocking_findings == 1
    assert store.get(first.artifact_id) is first and store.get(second.artifact_id) is second


def test_malformed_string_boolean_is_invalid_not_coerced():
    sv = skill()
    art = review(sv)
    malformed = replace(art, payload={
        **art.payload,
        "checks": {**art.payload["checks"], "strict_lint": {"passed": "true", "evidence": "x"}},
    })
    state = readiness_for_version(Store([sv, malformed]), sv)
    assert state.status == INVALID and "check strict_lint passed must be a boolean" in state.errors
