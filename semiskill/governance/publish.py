"""Explicit authenticated publication decisions bound to an exact verification chain."""
from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Literal

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import (
    CONTENT_REVIEW_KIND,
    SECURITY_REVIEW_KIND,
    readiness_for_version,
)
from semiskill.capture.intake import payload_fingerprint
from semiskill.governance.identity import AuthenticatedHuman

APPROVAL_SCHEMA = "approval/v1"
REQUIRED_SCAN_STAGES = frozenset({1, 2, 3, 4})


class PublishRefused(Exception):
    """A deterministic publication precondition was not met."""


def _uuid(value, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PublishRefused(f"{field} is not a UUID") from exc


def _artifact(store: ArtifactStore, value, artifact_type: ArtifactType, label: str) -> Artifact:
    artifact = store.get(_uuid(value, label))
    if artifact is None or artifact.artifact_type is not artifact_type:
        raise PublishRefused(f"{label} not found")
    return artifact


def _active_approvals(store: ArtifactStore) -> list[Artifact]:
    approvals = [
        artifact for artifact in store.by_type(ArtifactType.APPROVAL)
        if artifact.payload.get("schema_version") == APPROVAL_SCHEMA
    ]
    corrected = {artifact.corrects_ref for artifact in approvals if artifact.corrects_ref is not None}
    return [artifact for artifact in approvals if artifact.artifact_id not in corrected]


def _safe_authentication(identity: AuthenticatedHuman) -> dict:
    allowed = {
        "local_os": {"account", "sid", "uid"},
        "entra_oidc": {"issuer", "tenant_id", "object_id", "amr", "session_id"},
    }[identity.provider]
    context = {key: value for key, value in identity.auth_context.items() if key in allowed}
    return {"provider": identity.provider, "subject": identity.subject, "context": context}


def _validate_environment(identity: AuthenticatedHuman, environment: str) -> None:
    if environment == "production" and identity.provider != "entra_oidc":
        raise PublishRefused("production accepts only an Entra/OIDC authenticated identity")
    if environment not in {"development", "test", "production"}:
        raise PublishRefused(f"unknown approval environment: {environment!r}")


def _validate_evidence(
    *,
    store: ArtifactStore,
    skill_version: Artifact,
    automated: Artifact,
    content: Artifact,
    decision: str,
) -> list[Artifact]:
    if automated.payload.get("review_kind") != SECURITY_REVIEW_KIND:
        raise PublishRefused("automated review is not a security aggregate")
    if not automated.input_refs or automated.input_refs[0] != skill_version.artifact_id:
        raise PublishRefused("automated review is detached from the exact skill version")
    if content.payload.get("review_kind") != CONTENT_REVIEW_KIND:
        raise PublishRefused("content review is not canonical independent evidence")
    if not content.input_refs or content.input_refs[0] != skill_version.artifact_id:
        raise PublishRefused("content review is detached from the exact skill version")
    if content.payload.get("skill_payload_sha256") != payload_fingerprint(skill_version.payload):
        raise PublishRefused("content review payload hash is stale")

    scan_ids = automated.input_refs[1:]
    recorded_ids = automated.payload.get("scan_artifact_ids")
    if recorded_ids != [str(artifact_id) for artifact_id in scan_ids]:
        raise PublishRefused("automated review scan references do not match its frozen payload")
    scans: list[Artifact] = []
    for scan_id in scan_ids:
        scan = store.get(scan_id)
        if scan is None or scan.artifact_type not in {ArtifactType.SCAN_RUN, ArtifactType.INJECTION_TEST}:
            raise PublishRefused("automated review references a missing or invalid scan")
        if not scan.input_refs or scan.input_refs[0] != skill_version.artifact_id:
            raise PublishRefused("scan is detached from the exact skill version")
        scans.append(scan)

    if decision == "approve":
        if any(scan.payload.get("hard_fail") for scan in scans):
            raise PublishRefused("exact scan chain contains a hard_fail")
        if automated.payload.get("verdict") != "approve":
            raise PublishRefused("automated review verdict is not approve")
        stages = [scan.payload.get("stage") for scan in scans]
        if len(stages) != len(set(stages)) or not REQUIRED_SCAN_STAGES.issubset(set(stages)):
            raise PublishRefused("required scan stages 1/2/3/4 are not present exactly once")
        for scan in scans:
            if scan.payload.get("stage") in REQUIRED_SCAN_STAGES and scan.payload.get("status") != "passed":
                raise PublishRefused(
                    f"required scan stage {scan.payload.get('stage')} did not pass"
                )
        judge = next((scan for scan in scans if scan.payload.get("stage") == 5), None)
        if judge is None:
            raise PublishRefused("stage 5 sampling state is missing")
        if automated.payload.get("judge_required") is True and judge.payload.get("status") != "passed":
            raise PublishRefused("judge was required but stage 5 is not passed")
        readiness = readiness_for_version(store, skill_version)
        if not readiness.ready or readiness.review is None:
            raise PublishRefused("content review is not ready")
        if readiness.review.artifact_id != content.artifact_id:
            raise PublishRefused("content review is not the latest exact recheck")
    return scans


def decide_publication(
    *,
    store: ArtifactStore,
    skill_version_id,
    automated_review_id,
    content_review_id,
    expected_payload_sha256: str,
    decision: Literal["approve", "reject"],
    reason: str,
    identity: AuthenticatedHuman,
    environment: str,
) -> Artifact:
    """Record one explicit human decision; approval publishes, rejection never does."""
    if decision not in {"approve", "reject"}:
        raise PublishRefused("decision must be approve or reject")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason:
        raise PublishRefused("a non-empty human decision reason is required")
    _validate_environment(identity, environment)
    skill_version = _artifact(store, skill_version_id, ArtifactType.SKILL_VERSION, "skill version")
    automated = _artifact(store, automated_review_id, ArtifactType.REVIEW, "automated review")
    content = _artifact(store, content_review_id, ArtifactType.REVIEW, "content review")
    fingerprint = payload_fingerprint(skill_version.payload)
    if expected_payload_sha256 != fingerprint:
        raise PublishRefused("expected payload hash does not match the exact skill version")
    scans = _validate_evidence(
        store=store,
        skill_version=skill_version,
        automated=automated,
        content=content,
        decision=decision,
    )

    authentication = _safe_authentication(identity)
    for existing in _active_approvals(store):
        payload = existing.payload
        if (
            payload.get("decision") == decision
            and payload.get("reason") == reason
            and payload.get("skill", {}).get("artifact_id") == str(skill_version.artifact_id)
            and payload.get("evidence", {}).get("automated_review_id") == str(automated.artifact_id)
            and payload.get("evidence", {}).get("content_review_id") == str(content.artifact_id)
            and payload.get("authentication") == authentication
        ):
            return existing

    corrects = None
    if decision == "approve":
        slug = skill_version.payload.get("slug")
        candidates = [
            approval for approval in _active_approvals(store)
            if approval.payload.get("published") is True
            and approval.payload.get("skill", {}).get("slug") == slug
        ]
        corrects = max(candidates, key=lambda artifact: artifact.timestamp_start, default=None)

    approval = Artifact.new(
        artifact_type=ArtifactType.APPROVAL,
        source_system=(SourceSystem.CLI if identity.provider == "local_os" else SourceSystem.WEB),
        actor=identity.actor,
        actor_kind=ActorKind.HUMAN,
        input_refs=[skill_version.artifact_id, automated.artifact_id, content.artifact_id],
        payload={
            "schema_version": APPROVAL_SCHEMA,
            "decision": decision,
            "verdict": decision,
            "published": decision == "approve",
            "reason": reason,
            "environment": environment,
            "skill": {
                "artifact_id": str(skill_version.artifact_id),
                "slug": skill_version.payload.get("slug"),
                "version": skill_version.payload.get("version"),
                "payload_sha256": fingerprint,
            },
            "evidence": {
                "automated_review_id": str(automated.artifact_id),
                "content_review_id": str(content.artifact_id),
                "scan_artifact_ids": [str(scan.artifact_id) for scan in scans],
            },
            "authentication": authentication,
        },
    )
    approval = replace(
        approval,
        permissions_label=skill_version.permissions_label,
        objective_tag="safety",
        corrects_ref=(corrects.artifact_id if corrects is not None else None),
        rollback_ref={
            "action": "unpublish",
            "skill_version_id": str(skill_version.artifact_id),
            "approval_id": str(approval.artifact_id),
        } if decision == "approve" else None,
    )
    return store.append(approval)


def publish_skill(*_args, **_kwargs):
    """Tombstone for the callback-based API, which could fabricate human sign-off."""
    raise PublishRefused(
        "publish_skill callback API was removed; use decide_publication with authenticated identity"
    )
