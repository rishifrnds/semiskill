from dataclasses import replace
import json

import pytest

from semiskill.authoring.review_collection import (
    BatchRejected,
    collect_review_batch,
    import_legacy_review_files,
)
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

    def append_many(self, artifacts):
        self.append_many_calls += 1
        self.rows.extend(artifacts)
        return list(artifacts)

    def get(self, artifact_id):
        return next((a for a in self.rows if a.artifact_id == artifact_id), None)

    def by_type(self, artifact_type):
        return [a for a in self.rows if a.artifact_type is artifact_type]


def version(slug):
    return build_skill_version(skill_md=SKILL.format(slug=slug), actor="author")


def result(sv, **overrides):
    value = {
        "slug": sv.payload["slug"],
        "skill_version_id": str(sv.artifact_id),
        "skill_payload_sha256": payload_fingerprint(sv.payload),
        "version": sv.payload["version"],
        "role": sv.payload["role"],
        "level": sv.payload["level"],
        "phase": "recheck",
        "prompt_version": "P5-RECHECK-CALIBRATED@2",
        "run_id": "run-1",
        "batch_id": "batch-1",
        "attempt": 1,
        "reviewer_identity": f"reviewer:{sv.payload['slug']}:context-1",
        "fixer_identity": f"fixer:{sv.payload['slug']}:context-1",
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
    return value


def collect(store, skills, results):
    return collect_review_batch(store=store, skill_versions={s.payload["slug"]: s for s in skills},
                                results=results)


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


def test_mixed_run_or_attempt_rejects_whole_batch():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    with pytest.raises(BatchRejected, match="mixed run_id"):
        collect(store, [a, b], [result(a), result(b, run_id="run-2")])
    with pytest.raises(BatchRejected, match="mixed attempt"):
        collect(store, [a, b], [result(a), result(b, attempt=2)])
    assert store.append_many_calls == 0


def test_string_boolean_is_rejected_not_coerced():
    a = version("dv-a")
    bad_checks = result(a)["checks"]
    bad_checks["strict_lint"] = {"passed": "true", "evidence": "lint"}
    store = Store([a])
    with pytest.raises(BatchRejected, match="must be a boolean"):
        collect(store, [a], [result(a, checks=bad_checks)])
    assert store.append_many_calls == 0


def test_reused_reviewer_invocation_identity_rejects_batch():
    a, b = version("dv-a"), version("dv-b")
    shared = "reviewer:shared-context"
    store = Store([a, b])
    with pytest.raises(BatchRejected, match="reviewer identities must be unique"):
        collect(store, [a, b], [
            result(a, reviewer_identity=shared), result(b, reviewer_identity=shared),
        ])
    assert store.append_many_calls == 0


def test_valid_batch_appends_every_review_once_after_full_validation():
    a, b = version("dv-a"), version("dv-b")
    store = Store([a, b])
    reviews = collect(store, [a, b], [result(a), result(b)])
    assert len(reviews) == 2 and store.append_many_calls == 1
    assert {r.payload["slug"] for r in reviews} == {"dv-a", "dv-b"}


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
    second = collect(store, [a], [second_result])[0]
    assert second.input_refs == [a.artifact_id, first.artifact_id]
    assert store.get(first.artifact_id) is first and store.get(second.artifact_id) is second

    wrong = replace(first, payload={**first.payload, "attempt": 9})
    broken_store = Store([a, wrong])
    with pytest.raises(BatchRejected, match="increment prior review"):
        collect(broken_store, [a], [second_result])


def test_collector_rejects_duplicate_root_or_branch_without_appending():
    a = version("dv-a")
    store = Store([a])
    first = collect(store, [a], [result(a)])[0]
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="attempt 1 already exists"):
        collect(store, [a], [result(
            a, run_id="duplicate-root", reviewer_identity="reviewer:duplicate",
        )])
    assert store.append_many_calls == calls

    second = collect(store, [a], [result(
        a, attempt=2, run_id="run-2", prior_review_ref=str(first.artifact_id),
        reviewer_identity="reviewer:round-2", fixer_identity="fixer:round-2",
    )])[0]
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="attempt 2 already exists"):
        collect(store, [a], [result(
            a, attempt=2, run_id="branch", prior_review_ref=str(first.artifact_id),
            reviewer_identity="reviewer:branch", fixer_identity="fixer:branch",
        )])
    assert store.append_many_calls == calls and store.get(second.artifact_id) is second


def test_collector_normalizes_malformed_stored_attempt_to_batch_rejection():
    a = version("dv-a")
    store = Store([a])
    first = collect(store, [a], [result(a)])[0]
    malformed = replace(first, payload={**first.payload, "attempt": None})
    store.rows.append(malformed)
    calls = store.append_many_calls
    with pytest.raises(BatchRejected, match="existing review lineage has an invalid attempt"):
        collect(store, [a], [result(
            a, attempt=2, run_id="run-2", prior_review_ref=str(first.artifact_id),
            reviewer_identity="reviewer:round-2", fixer_identity="fixer:round-2",
        )])
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
        collect(store, [a, b], followups)
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
