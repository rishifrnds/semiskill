import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import (
    PostgresArtifactStore,
    PublicationReconciliationBundle,
)
from semiskill.authoring.snapshot import SnapshotUnavailable, build_scoreboard_snapshot
from semiskill.capture.intake import build_skill_version, load_skill_dir
from semiskill.governance.reconciliation import _chain_sha256
from tests.support import (
    append_test_content_review,
    content_checks,
    publish_test_skill,
    publish_wave_sources,
)

MIGRATIONS = Path("semiskill/artifacts/migrations")


class MemoryStore:
    def __init__(self, rows=(), database_name="semiskill_dev", projections=()):
        self.rows = list(rows)
        self.database_name = database_name
        self.projections = tuple(projections)
        self.review_contract_ids = {
            row.artifact_id for row in self.rows
            if row.artifact_type is ArtifactType.GATE_DECISION
        }

    def get(self, artifact_id):
        return next((row for row in self.rows if row.artifact_id == artifact_id), None)

    def append(self, artifact):
        self.rows.append(artifact)
        return artifact

    def append_many(self, artifacts):
        self.rows.extend(artifacts)
        return list(artifacts)

    def append_review_contract(self, artifact):
        self.rows.append(artifact)
        self.review_contract_ids.add(artifact.artifact_id)
        return artifact

    def verified_review_contract_ids(self):
        return set(self.review_contract_ids)

    def by_type(self, artifact_type):
        return [row for row in self.rows if row.artifact_type is artifact_type]

    def database_identity(self, *, environment):
        return {"engine": "memory", "environment": environment,
                "database_name": self.database_name,
                "identity_sha256": "sha256:" + "1" * 64}

    def publication_reconciliation_bundle(self):
        return PublicationReconciliationBundle(
            tuple(self.rows), self.projections, tuple(self.review_contract_ids),
        )


def _rows(store):
    types = (
        ArtifactType.SKILL_VERSION, ArtifactType.SCAN_RUN, ArtifactType.INJECTION_TEST,
        ArtifactType.REVIEW, ArtifactType.APPROVAL,
    )
    return [row for artifact_type in types for row in store.by_type(artifact_type)]


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    return PostgresArtifactStore(pg_dsn)


def _skill(slug: str, *, role="dv-engineer", level="senior") -> str:
    return f"""---
name: {slug}
description: Review {slug}. Use when exact evidence needs bounded verification.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: {slug}
  semiskill-function: design-verification
  semiskill-role: {role}
  semiskill-level: {level}
  semiskill-version: 1.0.0
  semiskill-owner: dv-guild
  semiskill-tags: evidence, review
---
# {slug}

## Procedure

1. Read a bounded evidence window and record the exact source location.
2. Compare the observed value with the documented expected value.

## Gotchas

Do not infer missing evidence.

## Human verification

A reviewer checks the cited source and conclusion.
"""


def _registry(path: Path, cells: list[dict], target=1) -> Path:
    path.write_text(json.dumps({"target_per_role": target, "cells": cells}), encoding="utf-8")
    return path


def _write_shared(root: Path, *, profile: bytes = b"profile-v1\n") -> Path:
    shared = root / "_shared"
    shared.mkdir(exist_ok=True)
    (shared / "team-profile.md").write_bytes(profile)
    (shared / "failure-signature-schema.md").write_bytes(b"schema\n")
    (shared / "handoff-vocabulary.md").write_bytes(b"vocabulary\n")
    return shared


@pytest.mark.integration
def test_snapshot_reconciles_exact_published_chain_and_non_crediting_decline(store, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-one"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
        {"slug": "declined-x", "role": "dv-engineer", "level": "n/a",
         "declined": {"why": "provenance only"}},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store,
        registry_path=registry,
        skills_root=root,
        generated_at="2026-08-06T00:00:00Z",
        expected_active=1,
        expected_declined=1,
        expected_roles=1,
        target_per_role=1,
        environment="test",
        source_commit="test-commit",
        repository_dirty=False,
    )

    assert snapshot["registry"] == {"total": 2, "active": 1, "declined": 1,
                                    "roles": 1, "levels": ["senior"]}
    assert snapshot["funnel"]["published"] == 1
    assert snapshot["roles"][0]["published"] == 1
    assert snapshot["roles"][0]["declined_provenance"] == 1
    cell = next(c for c in snapshot["cells"] if c["slug"] == "dv-one")
    assert cell["state"] == "published"
    assert cell["artifacts"]["approval_id"] == str(fixture.approval.artifact_id)
    assert cell["artifacts"]["content_review_id"] == str(fixture.content_review.artifact_id)
    assert cell["artifacts"]["scan_artifact_ids"] == [str(s.artifact_id) for s in fixture.scans]


@pytest.mark.integration
def test_repository_84_snapshot_conserves_registry_funnel_and_roles(store, pg_dsn):
    snapshot = build_scoreboard_snapshot(
        store=store,
        registry_path="specs/skill_registry.json",
        skills_root="skills",
        generated_at="2026-08-06T00:00:00Z",
        environment="test",
        source_commit="test-commit",
        repository_dirty=False,
    )

    assert snapshot["registry"]["active"] == 84
    assert snapshot["registry"]["declined"] == 20
    assert snapshot["registry"]["roles"] == 16
    assert snapshot["funnel"]["authored"] == 84
    assert snapshot["funnel"]["published"] == 0
    assert len(snapshot["cells"]) == 104
    assert sum(snapshot["exclusive_states"].values()) == 84
    assert sum(role["active"] for role in snapshot["roles"]) == 84
    assert sum(role["published"] for role in snapshot["roles"]) == 0
    assert snapshot["sources"]["database"]["database_name"].endswith("_test")
    assert snapshot["anomalies"]["unregistered_authored"] == []


@pytest.mark.integration
def test_source_edit_is_published_stale_without_rewriting_frozen_badge(store, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-one"
    d.mkdir(parents=True)
    skill_path = d / "SKILL.md"
    skill_path.write_text(_skill("dv-one"), encoding="utf-8")
    publish_wave_sources(store, root)
    skill_path.write_text(_skill("dv-one") + "\nA later source edit.\n", encoding="utf-8")
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test-commit", repository_dirty=True,
    )

    cell = snapshot["cells"][0]
    assert cell["state"] == "published_stale"
    assert cell["stage_flags"]["published"] is False
    assert snapshot["anomalies"]["stale_source_hashes"] == ["dv-one"]
    assert snapshot["funnel"]["published"] == 0


@pytest.mark.integration
def test_shared_only_edit_invalidates_publication_and_scoreboard_credit(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    shared = _write_shared(root)
    fixture = publish_wave_sources(store, root)[0]
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    baseline = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test-commit", repository_dirty=False,
    )
    assert baseline["cells"][0]["state"] == "published"

    (shared / "team-profile.md").write_bytes(b"profile-v2\n")
    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:01:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test-commit", repository_dirty=True,
    )

    cell = snapshot["cells"][0]
    assert cell["state"] == "published_stale"
    assert cell["stage_flags"]["approved"] is False
    assert cell["stage_flags"]["published"] is False
    assert cell["payload_hashes"]["all_match"] is False
    assert cell["payload_hashes"]["source"] != cell["payload_hashes"]["approval"]
    assert cell["artifacts"]["approval_id"] == str(fixture.approval.artifact_id)
    assert snapshot["funnel"]["published"] == 0
    assert snapshot["anomalies"]["stale_source_hashes"] == ["dv-one"]
    assert snapshot["anomalies"]["stale_review_hashes"] == ["dv-one"]
    assert snapshot["anomalies"]["stale_approval_hashes"] == ["dv-one"]
    assert snapshot["release_gate"]["passed"] is False


def test_prior_version_review_is_stale_evidence_without_review_funnel_credit(tmp_path):
    old = build_skill_version(skill_md=_skill("dv-one"), actor="author")
    memory = MemoryStore([old])
    append_test_content_review(
        memory, old, prompt_version="P5-RECHECK-CALIBRATED@2", run_id="old-run",
        batch_id="old-batch", reviewer_identity="old-reviewer",
        fixer_identity="old-fixer", checks=content_checks(), findings=[],
    )
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(
        _skill("dv-one").replace("semiskill-version: 1.0.0", "semiskill-version: 2.0.0"),
        encoding="utf-8",
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, source_commit="test", repository_dirty=False,
    )

    cell = snapshot["cells"][0]
    assert cell["checks"]["content_review"]["status"] == "stale"
    assert cell["stage_flags"]["reviewed"] is False
    assert snapshot["funnel"]["reviewed"] == 0
    assert snapshot["anomalies"]["stale_review_hashes"] == ["dv-one"]


@pytest.mark.integration
def test_later_review_for_another_version_does_not_taint_frozen_badge(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    newer = store.append(build_skill_version(
        skill_md=_skill("dv-one").replace("semiskill-version: 1.0.0", "semiskill-version: 2.0.0"),
        actor="author",
    ))
    later = append_test_content_review(
        store, newer, prompt_version="P5-RECHECK-CALIBRATED@2", run_id="new-run",
        batch_id="new-batch", reviewer_identity="new-reviewer",
        fixer_identity="new-fixer", checks=content_checks(), findings=[{
            "finding_id": "B-1", "category": "technical_correctness", "severity": "blocking",
            "evidence": "new version issue", "location": "SKILL.md:1",
            "required_change": "fix new version", "disposition": "open",
        }], prior_review=fixture.content_review,
    )
    assert later.timestamp_start >= fixture.approval.timestamp_start
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["cells"][0]["state"] == "published"
    assert snapshot["anomalies"]["post_approval_blockers"] == []


@pytest.mark.integration
def test_later_exact_lineage_collision_blocks_release_without_rewriting_badge(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    duplicate = append_test_content_review(
        store, fixture.skill_version, prompt_version="P5-RECHECK-CALIBRATED@2",
        run_id="duplicate-run", batch_id="duplicate-batch",
        reviewer_identity="duplicate-reviewer", fixer_identity="duplicate-fixer",
        checks=content_checks(), findings=[],
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["cells"][0]["state"] == "published"
    assert snapshot["anomalies"]["post_approval_blockers"] == ["dv-one"]
    assert snapshot["anomalies"]["invalid_review_lineage"] == ["dv-one"]
    assert snapshot["release_gate"]["passed"] is False


@pytest.mark.integration
def test_every_non_authoritative_published_claim_is_anomalous(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    skill_version = store.append(build_skill_version(skill_md=_skill("dv-one"), actor="author"))
    forged = store.append(Artifact.new(
        artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
        actor="legacy", actor_kind=ActorKind.HUMAN, input_refs=[skill_version.artifact_id],
        payload={"published": True},
    ))
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])
    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["anomalies"]["ungated_publications"] == [str(forged.artifact_id)]
    assert snapshot["funnel"]["published"] == 0


@pytest.mark.integration
def test_generic_skill_permission_label_drift_is_visible_and_release_blocking(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    skill_md, files = load_skill_dir(directory)
    skill_version = store.append(build_skill_version(
        skill_md=skill_md, actor="author", permissions_label="team", files=files,
    ))
    publish_test_skill(store, skill_version)
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])
    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    cell = snapshot["cells"][0]
    assert cell["permissions"] == {
        "registry_expected": "public", "skill_version": "team",
        "content_review": "team", "approval": "team", "scan_labels": ["team"],
        "all_match": False,
    }
    assert snapshot["anomalies"]["permission_label_drift"] == ["dv-one"]
    assert any(blocker["code"] == "PERMISSION_LABEL_DRIFT" for blocker in cell["blockers"])


@pytest.mark.integration
def test_snapshot_environment_rejects_approval_from_other_environment(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    memory = MemoryStore(
        _rows(store), database_name="semiskill_dev",
        projections=store.publication_reconciliation_bundle().projections,
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])
    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="development",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["funnel"]["published"] == 0
    assert snapshot["anomalies"]["invalid_approval_chains"] == [
        str(fixture.approval.artifact_id),
    ]


@pytest.mark.integration
def test_detached_rejection_evidence_cannot_block_skill(store, tmp_path):
    root = tmp_path / "skills"
    for slug in ("dv-one", "dv-two"):
        directory = root / slug
        directory.mkdir(parents=True)
        directory.joinpath("SKILL.md").write_text(_skill(slug), encoding="utf-8")
    first, second = publish_wave_sources(store, root)
    payload = {
        **second.approval.payload,
        "decision": "reject", "verdict": "reject", "published": False,
        "skill": first.approval.payload["skill"],
    }
    forged = Artifact.new(
        artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
        actor="rejector", actor_kind=ActorKind.HUMAN,
        input_refs=[first.skill_version.artifact_id, second.automated_review.artifact_id,
                    second.content_review.artifact_id],
        payload=payload,
    )
    forged = replace(forged, permissions_label="public")
    rows = [row for row in _rows(store) if row.artifact_type is not ArtifactType.APPROVAL]
    memory = MemoryStore([*rows, forged], database_name="semiskill_test")
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-two", "role": "dv-engineer", "level": "senior"},
    ], target=2)
    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=2, expected_declined=0,
        expected_roles=1, target_per_role=2, environment="test",
        source_commit="test", repository_dirty=False,
    )
    first_cell = next(cell for cell in snapshot["cells"] if cell["slug"] == "dv-one")
    assert first_cell["state"] != "approval_rejected"
    assert snapshot["anomalies"]["invalid_approval_chains"] == [str(forged.artifact_id)]


@pytest.mark.integration
def test_cross_skill_correction_is_invalid_and_cannot_suppress_publication(store, tmp_path):
    root = tmp_path / "skills"
    for slug in ("dv-one", "dv-two"):
        directory = root / slug
        directory.mkdir(parents=True)
        directory.joinpath("SKILL.md").write_text(_skill(slug), encoding="utf-8")
    fixtures = publish_wave_sources(store, root)
    first, second = fixtures
    forged = Artifact.new(
        artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
        actor=second.approval.actor, actor_kind=ActorKind.HUMAN,
        input_refs=list(second.approval.input_refs), payload=second.approval.payload,
    )
    forged = replace(
        forged, permissions_label=second.approval.permissions_label,
        corrects_ref=first.approval.artifact_id,
        rollback_ref=second.approval.rollback_ref,
    )
    memory = MemoryStore(
        [*_rows(store), forged], database_name="semiskill_test",
        projections=store.publication_reconciliation_bundle().projections,
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": slug, "role": "dv-engineer", "level": "senior"}
        for slug in ("dv-one", "dv-two")
    ], target=2)

    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=2, expected_declined=0,
        expected_roles=1, target_per_role=2, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["funnel"]["published"] == 2
    assert snapshot["anomalies"]["invalid_approval_chains"] == [str(forged.artifact_id)]
    assert snapshot["scope"]["access_scope"] == "internal-catalog-operators"
    assert snapshot["scope"]["scoped_export_eligible"] is False


@pytest.mark.integration
def test_branched_approval_corrections_are_invalid_and_do_not_hide_valid_head(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    branches = []
    for actor in ("branch-one", "branch-two"):
        branch = Artifact.new(
            artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
            actor=actor, actor_kind=ActorKind.HUMAN,
            input_refs=list(fixture.approval.input_refs), payload=fixture.approval.payload,
        )
        branches.append(replace(
            branch, permissions_label=fixture.approval.permissions_label,
            corrects_ref=fixture.approval.artifact_id,
            rollback_ref=fixture.approval.rollback_ref,
        ))
    memory = MemoryStore(
        [*_rows(store), *branches], database_name="semiskill_test",
        projections=store.publication_reconciliation_bundle().projections,
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["funnel"]["published"] == 1
    assert snapshot["anomalies"]["invalid_approval_chains"] == sorted(
        str(branch.artifact_id) for branch in branches
    )
    assert snapshot["conservation"]["passed"] is True


@pytest.mark.integration
def test_duplicate_projected_heads_credit_zero_and_mark_the_registry_cell_invalid(store, tmp_path):
    root = tmp_path / "skills"
    directory = root / "dv-one"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    bundle = store.publication_reconciliation_bundle()
    base_row = bundle.projections[0]
    clone_id = uuid.uuid4()
    clone = replace(
        fixture.approval,
        artifact_id=clone_id,
        rollback_ref={
            "action": "unpublish",
            "skill_version_id": str(fixture.skill_version.artifact_id),
            "approval_id": str(clone_id),
        },
    )
    clone_row = replace(
        base_row,
        approval_id=clone_id,
        activated_at=clone.timestamp_start,
        chain_sha256="0" * 64,
    )
    clone_row = replace(clone_row, chain_sha256=_chain_sha256(clone, clone_row))
    memory = MemoryStore(
        [*_rows(store), clone],
        database_name="semiskill_test",
        projections=(*bundle.projections, clone_row),
    )
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=memory, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test", repository_dirty=False,
    )
    assert snapshot["funnel"]["published"] == 0
    assert snapshot["anomalies"]["duplicate_active_publications"] == ["dv-one"]
    assert snapshot["cells"][0]["state"] == "invalid"
    assert any(
        blocker["code"] == "DUPLICATE_PUBLICATION_HEAD"
        for blocker in snapshot["cells"][0]["blockers"]
    )


def test_database_environment_label_cannot_disguise_test_state(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    registry = _registry(tmp_path / "registry.json", [])
    with pytest.raises(SnapshotUnavailable, match="database identity"):
        build_scoreboard_snapshot(
            store=MemoryStore(database_name="semiskill_test"), registry_path=registry,
            skills_root=root, generated_at="2026-08-06T00:00:00Z",
            expected_active=0, expected_declined=0, expected_roles=0,
            target_per_role=1, environment="development", source_commit="test",
            repository_dirty=False,
        )


def test_production_snapshot_requires_explicit_entra_tenant_policy(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    registry = _registry(tmp_path / "registry.json", [])
    with pytest.raises(SnapshotUnavailable, match="Entra issuer and tenant policy"):
        build_scoreboard_snapshot(
            store=MemoryStore(database_name="semiskill_prod"), registry_path=registry,
            skills_root=root, generated_at="2026-08-06T00:00:00Z",
            expected_active=0, expected_declined=0, expected_roles=0,
            target_per_role=1, environment="production", source_commit="test",
            repository_dirty=False,
        )
