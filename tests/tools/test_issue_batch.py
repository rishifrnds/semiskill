import json
import re
import subprocess
import uuid
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.authoring.review_collection import MAX_BATCH_SIZE
from semiskill.authoring.snapshot import full_input_tree_sha256
from semiskill.capture.intake import build_skill_version, payload_fingerprint
from tools.collect_wave import load_contract
from tools.issue_batch import (
    REPO,
    BatchRefused,
    Refusal,
    _cell_checks,
    _lease_cell,
    _select_cells,
    _verify_snapshot_freshness,
    render_worker_prompt,
    run_issue_batch,
)


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
    """Same fake-store shape as tests/tools/test_collect_wave.py — no live DB needed."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.review_contract_ids = set()

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
        return next((row for row in self.rows if row.artifact_id == artifact_id), None)

    def database_identity(self, *, environment):
        return {
            "engine": "postgresql", "environment": environment,
            "database_name": "semiskill_fake", "identity_sha256": "sha256:" + "9" * 64,
        }


def _skill(slug="dv-a"):
    return build_skill_version(skill_md=SKILL.format(slug=slug), actor="author")


def _cell(skill, *, status, blockers=(), role=None, level=None,
          content_review_id=None):
    payload_sha = payload_fingerprint(skill.payload)
    return {
        "slug": skill.payload["slug"],
        "role": role or skill.payload["role"],
        "level": level or skill.payload["level"],
        "registry_status": "active",
        "blockers": list(blockers),
        "stage_flags": {"strict_lint_pass": True},
        "payload_hashes": {"source": payload_sha, "skill_version": payload_sha},
        "checks": {
            "lint": {"status": "passed", "predicted_verdict": "approve",
                      "errors": 0, "warnings": 0, "advisories": 0},
            "consistency": {"status": "passed", "errors": 0, "warnings": 0},
            "security": {"status": "passed"},
            "content_review": {"status": status},
        },
        "artifacts": {
            "skill_version_id": str(skill.artifact_id),
            "automated_review_id": str(uuid.uuid4()),
            "content_review_id": content_review_id,
            "scan_artifact_ids": [str(uuid.uuid4())],
        },
    }


def _prior_review(skill, *, lineage_id=None, attempt=1):
    lineage_id = lineage_id or str(uuid.uuid4())
    review = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="reviewer:prior",
        actor_kind=ActorKind.AGENT,
        input_refs=[skill.artifact_id],
        payload={
            "review_kind": "content_review",
            "schema_version": 2,
            "slug": skill.payload["slug"],
            "attempt": attempt,
            "lineage_id": lineage_id,
            "role": skill.payload["role"],
            "level": skill.payload["level"],
            "skill_payload_sha256": payload_fingerprint(skill.payload),
        },
    )
    return replace(review, permissions_label=skill.permissions_label)


# --------------------------------------------------------------------------------------
# Selection is a pure function of the snapshot
# --------------------------------------------------------------------------------------

def test_review_phase_selects_unreviewed_unblocked_cells_only():
    a, b, c = _skill("dv-a"), _skill("dv-b"), _skill("dv-c")
    document = {"cells": [
        _cell(a, status="unreviewed"),
        _cell(b, status="unreviewed", blockers=[{"source": "lint", "code": "STRICT_LINT_BLOCKED"}]),
        _cell(c, status="reviewed"),
    ]}
    selected = _select_cells(document, phase="review", size=10)
    assert [cell["slug"] for cell in selected] == ["dv-a"]


def test_recheck_phase_selects_reviewed_cells_with_only_a_review_blocker():
    a, b, c = _skill("dv-a"), _skill("dv-b"), _skill("dv-c")
    document = {"cells": [
        _cell(a, status="reviewed", blockers=[{"source": "review", "code": "CONTENT_REVIEW_BLOCKED"}]),
        _cell(b, status="reviewed", blockers=[
            {"source": "review", "code": "CONTENT_REVIEW_BLOCKED"},
            {"source": "scan", "code": "SECURITY_BLOCKED"},
        ]),
        _cell(c, status="unreviewed"),
    ]}
    selected = _select_cells(document, phase="recheck", size=10)
    assert [cell["slug"] for cell in selected] == ["dv-a"]


def test_selection_is_a_pure_function_of_the_snapshot_and_caps_at_size():
    skills = [_skill(f"dv-{index}") for index in range(15)]
    document = {"cells": [_cell(skill, status="unreviewed") for skill in skills]}
    first = _select_cells(document, phase="review", size=MAX_BATCH_SIZE)
    second = _select_cells(document, phase="review", size=MAX_BATCH_SIZE)
    assert first == second
    assert len(first) == MAX_BATCH_SIZE == 10


# --------------------------------------------------------------------------------------
# Per-cell binding and refusal
# --------------------------------------------------------------------------------------

def test_lease_cell_refuses_hash_mismatch_with_a_typed_reason():
    skill = _skill("dv-a")
    store = Store([skill])
    cell = _cell(skill, status="unreviewed")
    cell["payload_hashes"]["skill_version"] = "0" * 64
    result = _lease_cell(store, cell, phase="review")
    assert isinstance(result, Refusal)
    assert result.reason == "HASH_MISMATCH"
    assert result.slug == "dv-a"


def test_lease_cell_refuses_missing_skill_version_id():
    skill = _skill("dv-a")
    store = Store([skill])
    cell = _cell(skill, status="unreviewed")
    cell["artifacts"]["skill_version_id"] = None
    result = _lease_cell(store, cell, phase="review")
    assert isinstance(result, Refusal)
    assert result.reason == "MISSING_SKILL_VERSION_ID"


def test_lease_cell_refuses_when_skill_version_is_not_in_the_store():
    skill = _skill("dv-a")
    store = Store([])  # skill was never captured / no longer present
    cell = _cell(skill, status="unreviewed")
    result = _lease_cell(store, cell, phase="review")
    assert isinstance(result, Refusal)
    assert result.reason == "SKILL_VERSION_NOT_FOUND"


def test_lease_cell_refuses_recheck_with_no_prior_review_reference():
    skill = _skill("dv-a")
    store = Store([skill])
    cell = _cell(skill, status="reviewed", content_review_id=None)
    result = _lease_cell(store, cell, phase="recheck")
    assert isinstance(result, Refusal)
    assert result.reason == "MISSING_PRIOR_REVIEW"


def test_lease_cell_recheck_binds_attempt_and_lineage_from_the_prior_review():
    skill = _skill("dv-a")
    prior = _prior_review(skill, attempt=1)
    store = Store([skill, prior])
    cell = _cell(skill, status="reviewed", content_review_id=str(prior.artifact_id))
    result = _lease_cell(store, cell, phase="recheck")
    assert not isinstance(result, Refusal)
    cell_contract, meta = result
    assert meta["attempt"] == 2
    assert cell_contract.lineage_id == prior.payload["lineage_id"]
    assert cell_contract.prior_review_ref == prior.artifact_id
    assert cell_contract.reviewer_identity != cell_contract.fixer_identity


def test_lease_cell_review_phase_ignores_a_leftover_prior_review_reference():
    skill = _skill("dv-a")
    store = Store([skill])
    cell = _cell(skill, status="unreviewed")
    result = _lease_cell(store, cell, phase="review")
    assert not isinstance(result, Refusal)
    cell_contract, meta = result
    assert meta["attempt"] == 1
    assert cell_contract.prior_review_ref is None
    assert cell_contract.fixer_identity == "not-applicable:pre-fix"


def test_cell_checks_reflect_failed_snapshot_evidence_as_unpassed():
    skill = _skill("dv-a")
    cell = _cell(skill, status="unreviewed")
    cell["checks"]["consistency"]["status"] = "failed"
    cell["checks"]["consistency"]["errors"] = 3
    checks = _cell_checks(cell)
    assert checks["consistency"]["passed"] is False
    assert checks["strict_lint"]["passed"] is True


# --------------------------------------------------------------------------------------
# Full round trip through collect_wave.py's own validator
# --------------------------------------------------------------------------------------

def test_issued_contract_round_trips_through_collect_wave_validate(tmp_path):
    skill = _skill("dv-a")
    store = Store([skill])
    document = {"cells": [_cell(skill, status="unreviewed")]}

    manifest = run_issue_batch(
        store=store, document=document, phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3", size=10, out_dir=tmp_path,
        batch_id="batch-test", verify_freshness=False,
    )

    assert manifest["issued"] == 1 and manifest["refused"] == 0
    contract_path = tmp_path / "dv-a.contract.json"
    assert contract_path.exists()
    loaded = load_contract(store, contract_path)  # must not raise BatchRejected
    assert loaded.cells["dv-a"].skill_version.artifact_id == skill.artifact_id

    prompt_text = (tmp_path / "dv-a.prompt.txt").read_text(encoding="utf-8")
    assert not re.search(r"\{\{[^{}]+\}\}", prompt_text)
    assert str(skill.artifact_id) in prompt_text


def test_recheck_contract_round_trips_through_collect_wave_validate(tmp_path):
    skill = _skill("dv-a")
    prior = _prior_review(skill, attempt=1)
    store = Store([skill, prior])
    document = {"cells": [
        _cell(skill, status="reviewed", content_review_id=str(prior.artifact_id)),
    ]}

    manifest = run_issue_batch(
        store=store, document=document, phase="recheck",
        prompt_version="P5-RECHECK-CALIBRATED@3", size=10, out_dir=tmp_path,
        batch_id="batch-recheck", verify_freshness=False,
    )

    assert manifest["issued"] == 1 and manifest["refused"] == 0
    contract_path = tmp_path / "dv-a.contract.json"
    loaded = load_contract(store, contract_path)
    assert loaded.cells["dv-a"].prior_review_ref == prior.artifact_id


def test_batch_never_exceeds_max_batch_size(tmp_path):
    skills = [_skill(f"dv-{index}") for index in range(12)]
    store = Store(skills)
    document = {"cells": [_cell(skill, status="unreviewed") for skill in skills]}
    with pytest.raises(BatchRefused, match="--size"):
        run_issue_batch(
            store=store, document=document, phase="review",
            prompt_version="P1-ADVERSARIAL-REVIEW@3", size=11, out_dir=tmp_path,
            verify_freshness=False,
        )


def test_a_hash_mismatch_refuses_only_that_cell_and_the_rest_continue(tmp_path):
    a, b = _skill("dv-a"), _skill("dv-b")
    store = Store([a, b])
    cell_a = _cell(a, status="unreviewed")
    cell_a["payload_hashes"]["skill_version"] = "0" * 64
    document = {"cells": [cell_a, _cell(b, status="unreviewed")]}

    manifest = run_issue_batch(
        store=store, document=document, phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3", size=10, out_dir=tmp_path,
        verify_freshness=False,
    )

    assert manifest["issued"] == 1 and manifest["refused"] == 1
    assert manifest["refusals"][0]["slug"] == "dv-a"
    assert manifest["refusals"][0]["reason"] == "HASH_MISMATCH"
    assert (tmp_path / "dv-b.contract.json").exists()
    assert not (tmp_path / "dv-a.contract.json").exists()


def test_unknown_phase_is_refused_before_touching_the_store(tmp_path):
    store = Store([])
    with pytest.raises(BatchRefused):
        run_issue_batch(
            store=store, document={"cells": []}, phase="bogus",
            prompt_version="P1-ADVERSARIAL-REVIEW@3", size=1, out_dir=tmp_path,
            verify_freshness=False,
        )


def test_prompt_version_must_match_the_phases_calibrated_template(tmp_path):
    store = Store([])
    with pytest.raises(BatchRefused, match="calibrated"):
        run_issue_batch(
            store=store, document={"cells": []}, phase="review",
            prompt_version="P5-RECHECK-CALIBRATED@3", size=1, out_dir=tmp_path,
            verify_freshness=False,
        )


# --------------------------------------------------------------------------------------
# Prompt rendering
# --------------------------------------------------------------------------------------

def test_render_worker_prompt_leaves_no_unresolved_placeholder():
    context = {
        "SLUG": "dv-a", "SKILL_VERSION_ID": str(uuid.uuid4()), "PAYLOAD_SHA256": "a" * 64,
        "ROLE": "dv-engineer", "LEVEL": "senior", "VERSION": "1.0.0",
        "BATCH_ID": "batch-1", "RUN_ID": "run-1", "ATTEMPT": "1",
        "READ_SCOPE": "skills/dv-a/", "WRITE_SCOPE_OR_NONE": "none",
        "TOOL_ALLOWLIST": "Read, Grep, Glob", "REPO": str(REPO),
        "REVIEWER_IDENTITY": "reviewer:dv-a:1", "FRESH_REVIEWER_IDENTITY": "reviewer:dv-a:1",
        "FIXER_IDENTITY": "not-applicable:pre-fix",
        "PRIOR_REVIEW_REF_OR_NULL": "null",
        "DETERMINISTIC_CHECK_EVIDENCE": json.dumps({"strict_lint": {"passed": True, "evidence": "x"}}),
    }
    rendered = render_worker_prompt("P1-ADVERSARIAL-REVIEW@3", context)
    assert "{{" not in rendered
    assert "dv-a" in rendered and "reviewer:dv-a:1" in rendered
    json.loads(rendered[rendered.index("{"):])  # the trailing return schema is valid JSON


def test_render_worker_prompt_refuses_an_unknown_prompt_version():
    with pytest.raises(BatchRefused, match="no section"):
        render_worker_prompt("P9-DOES-NOT-EXIST@1", {})


# --------------------------------------------------------------------------------------
# Snapshot freshness (requirement 1) — uses the real repository tree so the hashes are genuine,
# but this exercises only source-provenance drift detection, never security_blocked/pass state.
# --------------------------------------------------------------------------------------

def _real_sources() -> dict:
    registry_path = REPO / "specs" / "skill_registry.json"
    skills_root = REPO / "skills"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True, capture_output=True,
        text=True, encoding="utf-8",
    ).stdout.strip()
    return {
        "repository": {"commit": commit, "dirty": True},
        "registry": {
            "path": "specs/skill_registry.json",
            "sha256": "sha256:" + sha256(registry_path.read_bytes()).hexdigest(),
        },
        "skills": {
            "root": "skills",
            "full_tree_sha256": full_input_tree_sha256(skills_root),
        },
        "database": {
            "environment": "development", "database_name": "semiskill_fake",
            "identity_sha256": "sha256:" + "9" * 64,
        },
    }


def test_verify_snapshot_freshness_accepts_a_genuinely_current_snapshot():
    store = Store([])
    document = {"sources": _real_sources()}
    _verify_snapshot_freshness(document, repo_root=REPO, store=store)  # must not raise


def test_verify_snapshot_freshness_refuses_a_stale_registry_hash():
    store = Store([])
    sources = _real_sources()
    sources["registry"]["sha256"] = "sha256:" + "0" * 64
    with pytest.raises(BatchRefused, match="source-mismatched"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_a_stale_skills_tree_hash():
    store = Store([])
    sources = _real_sources()
    sources["skills"]["full_tree_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(BatchRefused, match="stale"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_a_database_mismatch():
    store = Store([])
    sources = _real_sources()
    sources["database"]["identity_sha256"] = "sha256:" + "1" * 64
    with pytest.raises(BatchRefused, match="database-mismatched"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_a_moved_commit():
    store = Store([])
    sources = _real_sources()
    sources["repository"]["commit"] = "0" * 40
    with pytest.raises(BatchRefused, match="source-mismatched"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


# --------------------------------------------------------------------------------------
# Snapshot freshness — path containment. The snapshot document is untrusted input (CLAUDE.md:
# treat every submitted artifact as an injection payload); `sources.registry.path` /
# `sources.skills.root` must never let this file read or hash a file outside the repository.
# --------------------------------------------------------------------------------------

def test_verify_snapshot_freshness_refuses_an_absolute_registry_path_escape(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("outside-the-repo", encoding="utf-8")
    store = Store([])
    sources = _real_sources()
    sources["registry"]["path"] = str(secret)
    with pytest.raises(BatchRefused, match="escapes the repository"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_a_relative_traversal_registry_path():
    store = Store([])
    sources = _real_sources()
    sources["registry"]["path"] = "../../../../../../etc/passwd"
    with pytest.raises(BatchRefused, match="escapes the repository"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_an_absolute_skills_root_escape(tmp_path):
    store = Store([])
    sources = _real_sources()
    sources["skills"]["root"] = str(tmp_path)
    with pytest.raises(BatchRefused, match="escapes the repository"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)


def test_verify_snapshot_freshness_refuses_an_empty_registry_path():
    store = Store([])
    sources = _real_sources()
    sources["registry"]["path"] = ""
    with pytest.raises(BatchRefused, match="empty"):
        _verify_snapshot_freshness({"sources": sources}, repo_root=REPO, store=store)
