"""Test-only builders for a complete valid approval/v1 evidence chain.

Production code has no callback or ungated shortcut. Tests that need a published catalog row use
this helper so their fixtures satisfy the same exact hash, scan, content-review, identity, and human
decision invariants as a real publication.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.authoring.gate import make_content_review
from semiskill.capture.intake import payload_fingerprint
from semiskill.governance.identity import AuthenticatedHuman
from semiskill.governance.publish import decide_publication


TEST_IDENTITY = AuthenticatedHuman(
    actor="test-human",
    subject="uid:99999",
    provider="local_os",
    auth_context={"account": "test-human", "uid": 99999},
)


@dataclass(frozen=True)
class PublishedFixture:
    skill_version: Artifact
    automated_review: Artifact
    content_review: Artifact
    scans: tuple[Artifact, ...]
    approval: Artifact


def content_checks() -> dict:
    return {
        "strict_lint": {"passed": True, "evidence": "test:lint:1.000"},
        "consistency": {"passed": True, "evidence": "test:consistency:0"},
        "source_hash": {"passed": True, "evidence": "test:hash:matched"},
        "artifact_reconciliation": {"passed": True, "evidence": "test:refs:matched"},
    }


def publish_test_skill(
    store,
    skill_version: Artifact,
    *,
    aggregate_safety: float = 1.0,
    reason: str = "Test human reviewed the exact fixture evidence.",
) -> PublishedFixture:
    """Publish an already-appended skill version through a valid frozen approval/v1 chain."""
    scans = []
    for stage in range(1, 6):
        artifact = Artifact.new(
            artifact_type=(ArtifactType.INJECTION_TEST if stage == 3 else ArtifactType.SCAN_RUN),
            source_system=SourceSystem.CLI,
            actor="test-pipeline",
            actor_kind=ActorKind.SERVICE_ACCOUNT,
            input_refs=[skill_version.artifact_id],
            payload={"stage": stage, "status": "passed", "sampled": True,
                     "safety_score": aggregate_safety, "hard_fail": False, "findings": []},
        ).with_eval_score(aggregate_safety)
        artifact = replace(artifact, permissions_label=skill_version.permissions_label,
                           objective_tag="safety")
        scans.append(artifact)
    automated = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="test-controller",
        actor_kind=ActorKind.AGENT,
        input_refs=[skill_version.artifact_id, *[scan.artifact_id for scan in scans]],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": "approve", "aggregate_safety": aggregate_safety,
                 "judge_required": True,
                 "scan_artifact_ids": [str(scan.artifact_id) for scan in scans]},
    ).with_eval_score(aggregate_safety)
    automated = replace(
        automated, permissions_label=skill_version.permissions_label, objective_tag="safety",
    )
    content = make_content_review(
        skill_version=skill_version,
        phase="recheck",
        prompt_version="P5-RECHECK-CALIBRATED@2",
        run_id=f"test-run:{uuid.uuid4()}",
        batch_id="test-batch",
        attempt=1,
        reviewer_identity=f"test-reviewer:{uuid.uuid4()}",
        fixer_identity=f"test-fixer:{uuid.uuid4()}",
        checks=content_checks(),
        findings=[],
    )
    store.append_many([*scans, automated, content])
    approval = decide_publication(
        store=store,
        skill_version_id=skill_version.artifact_id,
        automated_review_id=automated.artifact_id,
        content_review_id=content.artifact_id,
        expected_payload_sha256=payload_fingerprint(skill_version.payload),
        decision="approve",
        reason=reason,
        identity=TEST_IDENTITY,
        environment="test",
    )
    return PublishedFixture(skill_version, automated, content, tuple(scans), approval)


def publish_wave_sources(store, root) -> list[PublishedFixture]:
    """Capture every source directory and publish each through the valid test chain."""
    from semiskill.capture.intake import build_skill_version, load_skill_dir

    fixtures = []
    for skill_path in sorted(root.rglob("SKILL.md")):
        skill_md, files = load_skill_dir(skill_path.parent)
        skill_version = store.append(build_skill_version(
            skill_md=skill_md,
            actor="test-author",
            permissions_label="public",
            files=files,
        ))
        fixtures.append(publish_test_skill(store, skill_version))
    return fixtures
