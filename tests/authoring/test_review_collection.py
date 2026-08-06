from dataclasses import replace
import json
import uuid

import pytest

from semiskill.artifacts.schema import ArtifactType
from semiskill.authoring.review_collection import (
    BatchRejected,
    ReviewBatchContract,
    ReviewCellContract,
    collect_review_contract_batch,
    import_legacy_review_files,
    issue_review_batch_contract,
)
from semiskill.authoring.gate import REVIEWED, readiness_for_version
from semiskill.capture.intake import build_skill_version, payload_fingerprint


SKILL = """---
name: {slug}
description: Check {slug}. Use when it needs a review.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: {slug}
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: 1.0.0
---
# Procedure

1. Inspect the bounded evidence and record the result.
"""


class Store:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.append_many_calls = 0
        self.review_contract_ids = {
            row.artifact_id for row in self.rows
            if row.artifact_type is ArtifactType.GATE_DECISION
        }

    def append_many(self, artifacts):
        self.append_many_calls += 1
        self.rows.extend(artifacts)
        return list(artifacts)

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


def version(slug, semver="1.0.0"):
    skill_md = SKILL.format(slug=slug).replace("semiskill-version: 1.0.0", f"semiskill-version: {semver}")
    return build_skill_version(skill_md=skill_md, actor="author")


def result(sv, **overrides):
    value = {
        "slug": sv.payload["slug"],
        "skill_version_id": str(sv.artifact_id),
        "skill_payload_sha256": payload_fingerprint(sv.payload),
        "version": sv.payload["version"],
        "role": sv.payload["role"],
        "level": sv.payload["level"],
        "phase": "review",
        "prompt_version": "P1-ADVERSARIAL-REVIEW@2",
        "run_id": "run-1",
        "batch_id": "batch-1",
        "attempt": 1,
        "reviewer_identity": f"reviewer:{sv.payload['slug']}:context-1",
        "fixer_identity": f"fixer:{sv.payload['slug']}:context-1",
        "lineage_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"test:{sv.payload['slug']}")),
        "prior_review_ref": None,
        "checks": {
            "strict_lint": {"passed": True, "evidence": "lint:1.000"},
            "consistency": {"passed": True, "evidence": "consistency:0"},
            "source_hash": {"passed": True, "evidence": "hash:matched"},
            "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
        },
        "findings": [],
    }
    value.update(overrides)
    if "phase" not in overrides and value["attempt"] > 1:
        value["phase"] = "recheck"
    if "prompt_version" not in overrides and value["attempt"] > 1:
        value["prompt_version"] = "P5-RECHECK-CALIBRATED@2"
    return value


def batch_contract(
    skills,
    *,
    phase=None,
    prompt_version=None,
    run_id="run-1",
    batch_id="batch-1",
    attempt=1,
    reviewers=None,
    fixers=None,
    prior_refs=None,
    checks_by_slug=None,
    lineages=None,
    authentication_context=None,
):
    phase = phase or ("review" if attempt == 1 else "recheck")
    prompt_version = prompt_version or (
        "P1-ADVERSARIAL-REVIEW@2"
        if attempt == 1 else "P5-RECHECK-CALIBRATED@2"
    )
    reviewers = reviewers or {}
    fixers = fixers or {}
    prior_refs = prior_refs or {}
    checks_by_slug = checks_by_slug or {}
    lineages = lineages or {}
    cells = {}
    for skill in skills:
        slug = skill.payload["slug"]
        cells[slug] = ReviewCellContract(
            skill_version=skill,
            reviewer_identity=reviewers.get(slug, f"reviewer:{slug}:context-{attempt}"),
            fixer_identity=fixers.get(slug, f"fixer:{slug}:context-{attempt}"),
            checks=checks_by_slug.get(slug, result(skill)["checks"]),
            lineage_id=lineages.get(
                slug, str(uuid.uuid5(uuid.NAMESPACE_URL, f"test:{slug}")),
            ),
            prior_review_ref=prior_refs.get(slug),
        )
    return ReviewBatchContract(
        batch_id=batch_id,
        run_id=run_id,
        phase=phase,
        prompt_version=prompt_version,
        attempt=attempt,
        cells=cells,
        issuer_identity="test-review-coordinator",
        authentication_context=authentication_context or {
            "provider": "test",
            "subject_sha256": "sha256:" + "a" * 64,
        },
    )


def collect(store, skills, results, **contract_kwargs):
    contracts = issue_contract_batch(store, skills, **contract_kwargs)
    bound_results = bind_results(contracts, results)
    return collect_review_contract_batch(
        store=store,
        contracts=contracts,
        results=bound_results,
    )


def issue_contract_batch(store, skills, **contract_kwargs):
    base_run_id = contract_kwargs.pop("run_id", "run-1")
    contracts = []
    for skill in skills:
        slug = skill.payload["slug"]
        contract = batch_contract(
            [skill],
            run_id=f"{base_run_id}:{slug}",
            **contract_kwargs,
        )
        contracts.append(issue_review_batch_contract(store=store, contract=contract))
    return contracts


def bind_results(contracts, results):
    contracts_by_slug = {
        next(iter(contract.cells)): contract
        for contract in contracts
    }
    bound_results = []
    for row in results:
        bound = dict(row)
        contract = contracts_by_slug.get(bound.get("slug"))
        if contract is not None:
            cell = contract.cells[bound["slug"]]
            assert contract.contract_artifact is not None
            bound.update({
                "phase": contract.phase,
                "prompt_version": contract.prompt_version,
                "run_id": contract.run_id,
                "batch_id": contract.batch_id,
                "attempt": contract.attempt,
                "reviewer_identity": cell.reviewer_identity,
                "fixer_identity": cell.fixer_identity,
                "lineage_id": cell.lineage_id,
                "contract_artifact_id": str(contract.contract_artifact.artifact_id),
                "prior_review_ref": str(cell.prior_review_ref) if cell.prior_review_ref else None,
            })
        bound_results.append(bound)
    return bound_results


def test_unknown_slug_rejects_whole_batch_without_appending_any_artifact():
    a = version("dv-a")
    b = version("dv-b")
    store = Store([a])
    with pytest.raises(BatchRejected, match="unknown slugs"):
        collect(store, [a], [result(a), result(b)])
    assert store.append_many_calls == 0


def test_wrong_hash_rejects_whole_batch():
    a = version("dv-a")
    store = Store([a])
    with pytest.raises(BatchRejected, match="payload hash"):
        collect(store, [a], [result(a, skill_payload_sha256="0" * 64)])
    assert store.append_many_calls == 0


def test_missing_recheck_rejects_whole_batch():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    with pytest.raises(BatchRejected, match="missing slugs"):
        collect(store, [a, b], [result(a)])
    assert store.append_many_calls == 0
    assert store.by_type(ArtifactType.REVIEW) == []


def test_mixed_run_or_attempt_rejects_whole_batch():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    contracts = issue_contract_batch(store, [a, b])
    rows = bind_results(contracts, [result(a), result(b)])
    rows[1]["run_id"] = "run-2"
    with pytest.raises(BatchRejected, match="run_id does not match"):
        collect_review_contract_batch(store=store, contracts=contracts, results=rows)
    rows = bind_results(contracts, [result(a), result(b)])
    rows[1]["attempt"] = 2
    with pytest.raises(BatchRejected, match="attempt does not match"):
        collect_review_contract_batch(store=store, contracts=contracts, results=rows)
    assert store.append_many_calls == 0


def test_string_boolean_is_rejected_not_coerced():
    a = version("dv-a")
    bad_checks = result(a)["checks"]
    bad_checks["strict_lint"] = {"passed": "true", "evidence": "lint"}
    store = Store([a])
    with pytest.raises(BatchRejected, match="checks do not match"):
        collect(store, [a], [result(a, checks=bad_checks)])
    assert store.append_many_calls == 0


def test_agent_cannot_flip_a_failed_coordinator_check_to_ready():
    skill = version("dv-a")
    trusted = result(skill)["checks"]
    trusted["source_hash"] = {"passed": False, "evidence": "hash:mismatch"}
    forged = result(skill)
    store = Store([skill])

    with pytest.raises(BatchRejected, match="checks do not match"):
        collect(
            store,
            [skill],
            [forged],
            checks_by_slug={"dv-a": trusted},
        )
    assert store.append_many_calls == 0


def test_malformed_coordinator_check_is_rejected_before_agent_output():
    skill = version("dv-a")
    malformed = result(skill)["checks"]
    malformed["strict_lint"] = {"passed": "true", "evidence": "lint"}
    store = Store([skill])
    with pytest.raises(BatchRejected, match="passed must be a boolean"):
        collect(
            store,
            [skill],
            [result(skill)],
            checks_by_slug={"dv-a": malformed},
        )
    assert store.append_many_calls == 0


@pytest.mark.parametrize("authentication_context", [
    {"provider": "test", "subject": "coordinator:test"},
    {"provider": "test", "subject_sha256": "sha256:" + "a" * 64, "token": "secret"},
    {"provider": "test", "subject_sha256": "not-a-hash"},
    {"provider": "unknown", "subject_sha256": "sha256:" + "a" * 64},
])
def test_review_contract_authentication_context_is_bounded_and_non_secret(authentication_context):
    skill = version("dv-a")
    store = Store([skill])

    with pytest.raises(BatchRejected, match="authentication_context"):
        collect(
            store,
            [skill],
            [result(skill)],
            authentication_context=authentication_context,
        )

    assert store.by_type(ArtifactType.GATE_DECISION) == []
    assert store.by_type(ArtifactType.REVIEW) == []


def test_semantic_contract_retry_adopts_the_existing_verified_artifact():
    class RetryStore(Store):
        def append_review_contract(self, artifact):
            existing = replace(artifact, artifact_id=uuid.uuid4())
            self.rows.append(existing)
            self.review_contract_ids.add(existing.artifact_id)
            return existing

    skill = version("dv-a")
    store = RetryStore([skill])
    issued = issue_review_batch_contract(store=store, contract=batch_contract([skill]))

    assert issued.contract_artifact in store.rows
    assert issued.contract_artifact.artifact_id in store.review_contract_ids


def test_semantic_contract_retry_rejects_a_different_existing_envelope():
    class CollisionStore(Store):
        def append_review_contract(self, artifact):
            existing = replace(
                artifact,
                artifact_id=uuid.uuid4(),
                payload={**artifact.payload, "run_id": "collision"},
            )
            self.rows.append(existing)
            self.review_contract_ids.add(existing.artifact_id)
            return existing

    skill = version("dv-a")
    store = CollisionStore([skill])

    with pytest.raises(BatchRejected, match="semantically different"):
        issue_review_batch_contract(store=store, contract=batch_contract([skill]))


def test_reused_reviewer_invocation_identity_rejects_batch():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    contracts = issue_contract_batch(store, [a, b])
    rows = bind_results(contracts, [result(a), result(b)])
    rows[1]["reviewer_identity"] = rows[0]["reviewer_identity"]
    with pytest.raises(BatchRejected, match="reviewer_identity does not match"):
        collect_review_contract_batch(store=store, contracts=contracts, results=rows)
    assert store.append_many_calls == 0


def test_coordinator_contract_rejects_reused_reviewer_identity():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    shared = "reviewer:shared-context"
    with pytest.raises(BatchRejected, match="requires unique reviewer identities"):
        collect(
            store,
            [a, b],
            [result(a, reviewer_identity=shared), result(b, reviewer_identity=shared)],
            reviewers={"dv-a": shared, "dv-b": shared},
        )
    assert store.append_many_calls == 0


def test_valid_batch_appends_every_review_once_after_full_validation():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    reviews = collect(store, [a, b], [result(a), result(b)])
    assert len(reviews) == 2 and store.append_many_calls == 1
    assert {r.payload["slug"] for r in reviews} == {"dv-a", "dv-b"}
    assert len({review.input_refs[1] for review in reviews}) == 2
    assert len({review.payload["run_id"] for review in reviews}) == 2
    assert len({review.payload["reviewer_identity"] for review in reviews}) == 2


def test_orchestrator_batch_rejects_more_than_ten_independent_contracts():
    skills = [version(f"dv-{index}") for index in range(11)]
    store = Store(skills)
    contracts = issue_contract_batch(store, skills)
    rows = bind_results(contracts, [result(skill) for skill in skills])

    with pytest.raises(BatchRejected, match="limited to 10 skills"):
        collect_review_contract_batch(store=store, contracts=contracts, results=rows)

    assert store.append_many_calls == 0
    assert store.by_type(ArtifactType.REVIEW) == []


def test_initial_adversarial_review_is_preserved_but_cannot_create_readiness():
    skill = version("dv-a")
    store = Store([skill])
    initial = result(
        skill,
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3",
        fixer_identity="not-applicable:pre-fix",
        findings=[{
            "finding_id": "P1-1",
            "category": "technical_correctness",
            "severity": "blocking",
            "evidence": "The stated behavior is not supported.",
            "location": "SKILL.md:20",
            "required_change": "Replace it with a bounded evidence-based step.",
            "disposition": "open",
        }],
    )

    review = collect(
        store,
        [skill],
        [initial],
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3",
        fixers={"dv-a": "not-applicable:pre-fix"},
    )[0]
    readiness = readiness_for_version(store, skill)
    assert review.payload["phase"] == "review"
    assert readiness.status == REVIEWED and readiness.ready is False
    assert "not an independent recheck" in readiness.errors[0]


def test_initial_review_requires_the_calibrated_p1_prompt():
    skill = version("dv-a")
    store = Store([skill])
    with pytest.raises(BatchRejected, match="calibrated P1"):
        collect(
            store,
            [skill],
            [result(
                skill,
                phase="review",
                prompt_version="P5-RECHECK-CALIBRATED@2",
                fixer_identity="not-applicable:pre-fix",
            )],
            phase="review",
            prompt_version="P5-RECHECK-CALIBRATED@2",
            fixers={"dv-a": "not-applicable:pre-fix"},
        )
    assert store.append_many_calls == 0


def test_followup_round_preserves_prior_review_and_requires_exact_lineage():
    a = version("dv-a")
    store = Store([a])
    first = collect(store, [a], [result(a)])[0]
    second_result = result(
        a,
        attempt=2,
        run_id="run-2",
        prior_review_ref=str(first.artifact_id),
        reviewer_identity="reviewer:dv-a:context-2",
        fixer_identity="fixer:dv-a:context-2",
    )
    second = collect(
        store,
        [a],
        [second_result],
        attempt=2,
        run_id="run-2",
        prior_refs={"dv-a": first.artifact_id},
        reviewers={"dv-a": "reviewer:dv-a:context-2"},
        fixers={"dv-a": "fixer:dv-a:context-2"},
    )[0]
    assert second.input_refs == [
        a.artifact_id,
        uuid.UUID(second.payload["contract_artifact_id"]),
        first.artifact_id,
    ]
    assert store.get(first.artifact_id) is first and store.get(second.artifact_id) is second

    wrong = replace(first, payload={**first.payload, "attempt": 9})
    broken_store = Store([a, wrong])
    with pytest.raises(BatchRejected, match="increment prior review"):
        collect(
            broken_store,
            [a],
            [second_result],
            attempt=2,
            run_id="run-2",
            prior_refs={"dv-a": first.artifact_id},
            reviewers={"dv-a": "reviewer:dv-a:context-2"},
            fixers={"dv-a": "fixer:dv-a:context-2"},
        )


def test_cross_version_recheck_must_carry_and_dispose_every_prior_blocker():
    original = version("dv-a", "1.0.0")
    fixed = version("dv-a", "1.0.1")
    store = Store([original, fixed])
    blocker = {
        "finding_id": "P1-1",
        "category": "technical_correctness",
        "severity": "blocking",
        "evidence": "The original procedure is incorrect.",
        "location": "SKILL.md:12",
        "required_change": "Correct the bounded procedure.",
        "disposition": "open",
    }
    first = collect(
        store,
        [original],
        [result(
            original,
            phase="review",
            prompt_version="P1-ADVERSARIAL-REVIEW@3",
            fixer_identity="not-applicable:pre-fix",
            findings=[blocker],
        )],
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3",
        fixers={"dv-a": "not-applicable:pre-fix"},
    )[0]

    omitted = collect(
        store,
        [fixed],
        [result(
            fixed,
            attempt=2,
            run_id="run-2",
            prior_review_ref=str(first.artifact_id),
            reviewer_identity="reviewer:dv-a:context-2",
            fixer_identity="fixer:dv-a:context-2",
        )],
        attempt=2,
        run_id="run-2",
        prior_refs={"dv-a": first.artifact_id},
        reviewers={"dv-a": "reviewer:dv-a:context-2"},
        fixers={"dv-a": "fixer:dv-a:context-2"},
    )[0]
    blocked = readiness_for_version(store, fixed)
    assert blocked.status == REVIEWED and blocked.open_blocking_findings == 1

    resolved_finding = {**blocker, "disposition": "resolved"}
    corrected = version("dv-a", "1.0.2")
    store.rows.append(corrected)
    collect(
        store,
        [corrected],
        [result(
            corrected,
            attempt=3,
            run_id="run-3",
            prior_review_ref=str(omitted.artifact_id),
            reviewer_identity="reviewer:dv-a:context-3",
            fixer_identity="fixer:dv-a:context-3",
            findings=[resolved_finding],
        )],
        attempt=3,
        run_id="run-3",
        prior_refs={"dv-a": omitted.artifact_id},
        reviewers={"dv-a": "reviewer:dv-a:context-3"},
        fixers={"dv-a": "fixer:dv-a:context-3"},
    )
    assert readiness_for_version(store, corrected).ready is True


def test_collector_rejects_duplicate_root_or_branch_without_appending():
    a = version("dv-a")
    store = Store([a])
    first = collect(store, [a], [result(a)])[0]
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="attempt 1 already exists"):
        collect(
            store,
            [a],
            [result(a, run_id="duplicate-root", reviewer_identity="reviewer:duplicate")],
            run_id="duplicate-root",
            reviewers={"dv-a": "reviewer:duplicate"},
        )
    assert store.append_many_calls == calls

    second_result = result(
        a, attempt=2, run_id="run-2", prior_review_ref=str(first.artifact_id),
        reviewer_identity="reviewer:round-2", fixer_identity="fixer:round-2",
    )
    second = collect(
        store,
        [a],
        [second_result],
        attempt=2,
        run_id="run-2",
        prior_refs={"dv-a": first.artifact_id},
        reviewers={"dv-a": "reviewer:round-2"},
        fixers={"dv-a": "fixer:round-2"},
    )[0]
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="attempt 2 already exists"):
        collect(
            store,
            [a],
            [result(
                a, attempt=2, run_id="branch", prior_review_ref=str(first.artifact_id),
                reviewer_identity="reviewer:branch", fixer_identity="fixer:branch",
            )],
            attempt=2,
            run_id="branch",
            prior_refs={"dv-a": first.artifact_id},
            reviewers={"dv-a": "reviewer:branch"},
            fixers={"dv-a": "fixer:branch"},
        )
    assert store.append_many_calls == calls and store.get(second.artifact_id) is second


def test_collector_normalizes_malformed_stored_attempt_to_batch_rejection():
    a = version("dv-a")
    store = Store([a])
    first = collect(store, [a], [result(a)])[0]
    malformed = replace(first, payload={**first.payload, "attempt": None})
    store.rows.append(malformed)
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="existing review lineage has an invalid attempt"):
        collect(
            store,
            [a],
            [result(
                a, attempt=2, run_id="run-2", prior_review_ref=str(first.artifact_id),
                reviewer_identity="reviewer:round-2", fixer_identity="fixer:round-2",
            )],
            attempt=2,
            run_id="run-2",
            prior_refs={"dv-a": first.artifact_id},
            reviewers={"dv-a": "reviewer:round-2"},
            fixers={"dv-a": "fixer:round-2"},
        )
    assert store.append_many_calls == calls


def test_reused_lineage_context_rejects_the_entire_collector_batch():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    first = collect(store, [a, b], [result(a), result(b)])
    calls = store.append_many_calls
    followups = [
        result(
            skill,
            attempt=2,
            run_id="run-1",
            prior_review_ref=str(prior.artifact_id),
            reviewer_identity=f"reviewer:{skill.payload['slug']}:context-2",
            fixer_identity=f"fixer:{skill.payload['slug']}:context-2",
        )
        for skill, prior in zip((a, b), first)
    ]
    with pytest.raises(BatchRejected, match="run_id must be unique"):
        collect(
            store,
            [a, b],
            followups,
            attempt=2,
            run_id="run-1",
            prior_refs={
                skill.payload["slug"]: prior.artifact_id
                for skill, prior in zip((a, b), first)
            },
            reviewers={
                skill.payload["slug"]: f"reviewer:{skill.payload['slug']}:context-2"
                for skill in (a, b)
            },
            fixers={
                skill.payload["slug"]: f"fixer:{skill.payload['slug']}:context-2"
                for skill in (a, b)
            },
        )
    assert store.append_many_calls == calls


def test_legacy_import_preserves_raw_record_but_is_non_authoritative(tmp_path):
    source = tmp_path / "skills" / "dv-a" / "REVIEW.json"
    source.parent.mkdir(parents=True)
    raw = {"slug": "dv-a", "recheck": {"ready": True, "agent": "legacy-label"}}
    source.write_text(json.dumps(raw), encoding="utf-8")
    store = Store()

    imported = import_legacy_review_files(
        store=store, review_files=[source], archive_root=tmp_path / "archive",
    )

    assert len(imported) == 1 and imported[0].input_refs == []
    assert imported[0].payload["review_kind"] == "content_review_legacy"
    assert imported[0].payload["legacy_unbound"] is True
    assert imported[0].payload["raw_record"] == raw
    assert not source.exists()
    archived = list((tmp_path / "archive" / "dv-a").glob("*.json"))
    assert len(archived) == 1

    assert import_legacy_review_files(
        store=store, review_files=[], archive_root=tmp_path / "archive",
    ) == []
    assert store.append_many_calls == 1


def test_failed_legacy_import_does_not_move_any_file(tmp_path):
    class FailingStore(Store):
        def append_many(self, artifacts):
            self.append_many_calls += 1
            raise RuntimeError("database unavailable")

    source = tmp_path / "skills" / "dv-a" / "REVIEW.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"slug":"dv-a"}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="database unavailable"):
        import_legacy_review_files(
            store=FailingStore(), review_files=[source], archive_root=tmp_path / "archive",
        )

    assert source.exists() and not (tmp_path / "archive").exists()
