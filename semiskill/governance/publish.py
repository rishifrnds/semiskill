"""Explicit authenticated publication decisions bound to an exact verification chain."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Literal

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import (
    CONTENT_REVIEW_KIND,
    SECURITY_REVIEW_KIND,
    readiness_for_review,
    readiness_for_version,
)
from semiskill.capture.intake import payload_fingerprint
from semiskill.governance.identity import (
    AuthenticatedHuman,
    IdentityRefused,
    validate_identity_policy,
)

APPROVAL_SCHEMA = "approval/v1"
REQUIRED_SCAN_STAGES = frozenset({1, 2, 3, 4})
MIN_APPROVAL_SAFETY = 0.8
_CORE_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class PublishRefused(Exception):
    """A deterministic publication precondition was not met."""


class ApprovalChainInvalid(PublishRefused):
    """An active approval no longer resolves to one internally consistent frozen chain."""


@dataclass(frozen=True)
class FrozenApprovalEvidence:
    approval: Artifact
    automated_review: Artifact
    content_review: Artifact
    scans: tuple[Artifact, ...]


def _semver_tuple(value: object) -> tuple[int, int, int] | None:
    match = _CORE_SEMVER.fullmatch(value) if isinstance(value, str) else None
    return (
        tuple(int(part) for part in match.groups())
        if match and all(len(part) <= 18 for part in match.groups())
        else None
    )


def _completed_at(artifact: Artifact):
    return artifact.timestamp_end or artifact.timestamp_start


def _canonical_score(value: object) -> float | None:
    if type(value) not in {int, float}:
        return None
    try:
        decimal = Decimal(str(value))
    except InvalidOperation:
        return None
    if not decimal.is_finite() or decimal < 0 or decimal > 1:
        return None
    if decimal != decimal.quantize(Decimal("0.001")):
        return None
    return float(decimal)


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


def _artifact_batch(
    store: ArtifactStore,
    requests: list[tuple[object, ArtifactType, str]],
) -> list[Artifact]:
    parsed = [(_uuid(value, label), artifact_type, label) for value, artifact_type, label in requests]
    get_many = getattr(store, "get_many", None)
    if callable(get_many):
        rows = {artifact.artifact_id: artifact for artifact in get_many([row[0] for row in parsed])}
    else:
        rows = {artifact_id: store.get(artifact_id) for artifact_id, _type, _label in parsed}
    artifacts: list[Artifact] = []
    for artifact_id, artifact_type, label in parsed:
        artifact = rows.get(artifact_id)
        if artifact is None or artifact.artifact_type is not artifact_type:
            raise PublishRefused(f"{label} not found")
        artifacts.append(artifact)
    return artifacts


def _active_approvals(store: ArtifactStore) -> list[Artifact]:
    approvals = [
        artifact for artifact in store.by_type(ArtifactType.APPROVAL)
        if isinstance(artifact.payload, dict)
        and artifact.payload.get("schema_version") == APPROVAL_SCHEMA
    ]
    corrected = {artifact.corrects_ref for artifact in approvals if artifact.corrects_ref is not None}
    return [artifact for artifact in approvals if artifact.artifact_id not in corrected]


def _safe_authentication(identity: AuthenticatedHuman) -> dict:
    allowed = {
        "local_os": {"account", "sid", "uid"},
        "entra_oidc": {"issuer", "tenant_id", "object_id", "amr", "session_id"},
    }[identity.provider]
    context = {key: value for key, value in identity.auth_context.items() if key in allowed}
    return {
        "provider": identity.provider,
        "subject": identity.subject,
        "actor": identity.actor,
        "context": context,
    }


def _validate_environment(
    identity: AuthenticatedHuman,
    environment: str,
    *,
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> None:
    try:
        validate_identity_policy(
            identity,
            environment=environment,
            expected_entra_issuer=expected_entra_issuer,
            expected_entra_tenant=expected_entra_tenant,
        )
    except IdentityRefused as exc:
        raise PublishRefused(str(exc)) from exc


def _validate_evidence(
    *,
    store: ArtifactStore,
    skill_version: Artifact,
    automated: Artifact,
    content: Artifact,
    decision: str,
) -> list[Artifact]:
    scans = _validate_frozen_evidence(
        store=store, skill_version=skill_version, automated=automated, content=content,
    )
    if decision == "approve":
        _validate_approved_results(automated, scans)
        readiness = readiness_for_version(store, skill_version)
        if not readiness.ready or readiness.review is None:
            raise PublishRefused("content review is not ready")
        if readiness.review.artifact_id != content.artifact_id:
            raise PublishRefused("content review is not the latest exact recheck")
    return scans


def _validate_frozen_evidence(
    *,
    store: ArtifactStore,
    skill_version: Artifact,
    automated: Artifact,
    content: Artifact,
) -> list[Artifact]:
    if not isinstance(skill_version.payload, dict):
        raise PublishRefused("skill version payload must be an object")
    if not isinstance(automated.payload, dict):
        raise PublishRefused("automated review payload must be an object")
    if not isinstance(content.payload, dict):
        raise PublishRefused("content review payload must be an object")
    if automated.payload.get("review_kind") != SECURITY_REVIEW_KIND:
        raise PublishRefused("automated review is not a security aggregate")
    if automated.payload.get("schema_version") != 1 or automated.payload.get("stage") != 6:
        raise PublishRefused("automated review schema or aggregate stage is invalid")
    if not automated.input_refs or automated.input_refs[0] != skill_version.artifact_id:
        raise PublishRefused("automated review is detached from the exact skill version")
    if content.payload.get("review_kind") != CONTENT_REVIEW_KIND:
        raise PublishRefused("content review is not canonical independent evidence")
    if not content.input_refs or content.input_refs[0] != skill_version.artifact_id:
        raise PublishRefused("content review is detached from the exact skill version")
    if content.payload.get("skill_payload_sha256") != payload_fingerprint(skill_version.payload):
        raise PublishRefused("content review payload hash is stale")
    if _completed_at(skill_version) > automated.timestamp_start:
        raise PublishRefused("automated review predates completion of the skill version")
    if _completed_at(skill_version) > content.timestamp_start:
        raise PublishRefused("content review predates completion of the skill version")
    if skill_version.payload.get("payload_sha256") != payload_fingerprint(skill_version.payload):
        raise PublishRefused("skill version canonical payload hash is missing or stale")
    if _semver_tuple(skill_version.payload.get("version")) is None:
        raise PublishRefused("skill version requires a canonical core semver")
    if content.ground_truth_ref != payload_fingerprint(skill_version.payload):
        raise PublishRefused("content review ground truth hash is stale")
    if any(
        artifact.permissions_label != skill_version.permissions_label
        for artifact in (automated, content)
    ):
        raise PublishRefused("review evidence permission label differs from the skill version")

    aggregate = automated.payload.get("aggregate_safety")
    aggregate_score = _canonical_score(aggregate)
    if aggregate_score is None:
        raise PublishRefused(
            "automated review aggregate_safety must be a three-decimal number in [0,1]"
        )
    if automated.eval_score is None or float(automated.eval_score) != aggregate_score:
        raise PublishRefused("automated review eval_score disagrees with aggregate_safety")
    if automated.payload.get("verdict") not in {"approve", "reject"}:
        raise PublishRefused("automated review verdict is invalid")
    if type(automated.payload.get("judge_required")) is not bool:
        raise PublishRefused("automated review judge_required must be a boolean")

    scan_ids = automated.input_refs[1:]
    recorded_ids = automated.payload.get("scan_artifact_ids")
    if recorded_ids != [str(artifact_id) for artifact_id in scan_ids]:
        raise PublishRefused("automated review scan references do not match its frozen payload")
    get_many = getattr(store, "get_many", None)
    if callable(get_many):
        scan_rows = {artifact.artifact_id: artifact for artifact in get_many(list(scan_ids))}
    else:
        scan_rows = {scan_id: store.get(scan_id) for scan_id in scan_ids}
    scans: list[Artifact] = []
    for scan_id in scan_ids:
        scan = scan_rows.get(scan_id)
        if scan is None or scan.artifact_type not in {ArtifactType.SCAN_RUN, ArtifactType.INJECTION_TEST}:
            raise PublishRefused("automated review references a missing or invalid scan")
        if not isinstance(scan.payload, dict):
            raise PublishRefused("scan payload must be an object")
        if not scan.input_refs or scan.input_refs[0] != skill_version.artifact_id:
            raise PublishRefused("scan is detached from the exact skill version")
        if scan.permissions_label != skill_version.permissions_label:
            raise PublishRefused("scan permission label differs from the skill version")
        stage = scan.payload.get("stage")
        if type(stage) is not int or stage not in {1, 2, 3, 4, 5}:
            raise PublishRefused("scan stage is invalid")
        if scan.payload.get("status") not in {"passed", "failed", "not_run", "not_sampled"}:
            raise PublishRefused(f"scan stage {stage} status is invalid")
        if type(scan.payload.get("sampled")) is not bool:
            raise PublishRefused(f"scan stage {stage} sampled must be a boolean")
        if type(scan.payload.get("hard_fail")) is not bool:
            raise PublishRefused(f"scan stage {stage} hard_fail must be a boolean")
        score = scan.payload.get("safety_score")
        canonical_score = _canonical_score(score)
        if canonical_score is None:
            raise PublishRefused(
                f"scan stage {stage} safety_score must be a three-decimal number in [0,1]"
            )
        if scan.eval_score is None or float(scan.eval_score) != canonical_score:
            raise PublishRefused(f"scan stage {stage} eval_score disagrees with safety_score")
        status = scan.payload["status"]
        sampled = scan.payload["sampled"]
        if sampled is not (status in {"passed", "failed"}):
            raise PublishRefused(f"scan stage {stage} status and sampled state disagree")
        expected_type = ArtifactType.INJECTION_TEST if stage == 3 else ArtifactType.SCAN_RUN
        if scan.artifact_type is not expected_type:
            raise PublishRefused(f"scan stage {stage} artifact type is invalid")
        if _completed_at(skill_version) > scan.timestamp_start:
            raise PublishRefused(f"scan stage {stage} predates completion of the skill version")
        if _completed_at(scan) > automated.timestamp_start:
            raise PublishRefused(f"scan stage {stage} was not complete before its aggregate")
        scans.append(scan)

    stages = [scan.payload["stage"] for scan in scans]
    if len(stages) != len(set(stages)) or not REQUIRED_SCAN_STAGES.issubset(set(stages)):
        raise PublishRefused("required scan stages 1/2/3/4 are not present exactly once")
    if stages.count(5) != 1:
        raise PublishRefused("stage 5 sampling state is missing or duplicated")
    return scans


def _validate_approved_results(automated: Artifact, scans: list[Artifact]) -> None:
    if any(scan.payload["hard_fail"] for scan in scans):
        raise PublishRefused("exact scan chain contains a hard_fail")
    if automated.payload.get("verdict") != "approve":
        raise PublishRefused("automated review verdict is not approve")
    aggregate = float(automated.payload["aggregate_safety"])
    measured = [
        float(scan.payload["safety_score"])
        for scan in scans if scan.payload["sampled"]
    ]
    if not measured or aggregate != min(measured) or aggregate < MIN_APPROVAL_SAFETY:
        raise PublishRefused("automated review aggregate does not satisfy approval policy")
    for scan in scans:
        if scan.payload["stage"] in REQUIRED_SCAN_STAGES and (
            scan.payload["status"] != "passed" or scan.payload["sampled"] is not True
        ):
            raise PublishRefused(f"required scan stage {scan.payload['stage']} did not pass")
    judge = next(scan for scan in scans if scan.payload["stage"] == 5)
    if automated.payload["judge_required"] and judge.payload["status"] != "passed":
        raise PublishRefused("judge was required but stage 5 is not passed")


def resolve_frozen_approval_evidence(
    store: ArtifactStore,
    *,
    skill_version: Artifact,
    approval: Artifact,
) -> FrozenApprovalEvidence:
    """Resolve the exact immutable evidence named by one active published approval.

    This deliberately validates the approved content review itself, not the latest review for the
    slug. Later scans or rechecks must remain visible history without rewriting an older badge.
    """
    def invalid(message: str) -> None:
        raise ApprovalChainInvalid(message)

    if approval.artifact_type is not ArtifactType.APPROVAL:
        invalid("artifact is not an approval")
    payload = approval.payload if isinstance(approval.payload, dict) else {}
    if not isinstance(approval.payload, dict):
        invalid("approval payload must be an object")
    if (
        approval.actor_kind is not ActorKind.HUMAN
        or payload.get("schema_version") != APPROVAL_SCHEMA
        or payload.get("decision") != "approve"
        or payload.get("published") is not True
    ):
        invalid("approval is not an authoritative published human approval/v1")
    if approval.permissions_label != skill_version.permissions_label:
        invalid("approval permission label differs from the skill version")

    skill = payload.get("skill")
    evidence = payload.get("evidence")
    if not isinstance(skill, dict) or not isinstance(evidence, dict):
        invalid("approval skill or evidence payload is malformed")
    expected_skill = {
        "artifact_id": str(skill_version.artifact_id),
        "slug": skill_version.payload.get("slug"),
        "version": skill_version.payload.get("version"),
        "payload_sha256": payload_fingerprint(skill_version.payload),
    }
    if any(skill.get(key) != value for key, value in expected_skill.items()):
        invalid("approval skill identity does not match the exact skill version")
    if approval.rollback_ref != {
        "action": "unpublish",
        "skill_version_id": str(skill_version.artifact_id),
        "approval_id": str(approval.artifact_id),
    }:
        invalid("approval rollback reference is missing or detached")
    if len(approval.input_refs) != 3 or approval.input_refs[0] != skill_version.artifact_id:
        invalid("approval does not have the exact skill/review input references")
    if evidence.get("automated_review_id") != str(approval.input_refs[1]):
        invalid("approval automated review payload disagrees with input_refs")
    if evidence.get("content_review_id") != str(approval.input_refs[2]):
        invalid("approval content review payload disagrees with input_refs")

    automated = store.get(approval.input_refs[1])
    content = store.get(approval.input_refs[2])
    if automated is None or automated.artifact_type is not ArtifactType.REVIEW:
        invalid("approval automated review is missing or invalid")
    if content is None or content.artifact_type is not ArtifactType.REVIEW:
        invalid("approval content review is missing or invalid")
    if _completed_at(automated) > approval.timestamp_start or (
        _completed_at(content) > approval.timestamp_start
    ):
        invalid("approval predates its frozen review evidence")
    try:
        scans = _validate_frozen_evidence(
            store=store, skill_version=skill_version, automated=automated, content=content,
        )
        _validate_approved_results(automated, scans)
    except PublishRefused as exc:
        raise ApprovalChainInvalid(str(exc)) from exc
    if evidence.get("scan_artifact_ids") != [str(scan.artifact_id) for scan in scans]:
        invalid("approval scan IDs disagree with the automated review chain")
    frozen_readiness = readiness_for_review(store, skill_version, content)
    if not frozen_readiness.ready:
        invalid("approved content review is not independently recheck-ready")
    return FrozenApprovalEvidence(approval, automated, content, tuple(scans))


def resolve_frozen_rejection_evidence(
    store: ArtifactStore,
    *,
    skill_version: Artifact,
    approval: Artifact,
) -> FrozenApprovalEvidence:
    """Validate the exact evidence chain for a non-publishing human rejection."""
    def invalid(message: str) -> None:
        raise ApprovalChainInvalid(message)

    payload = approval.payload if isinstance(approval.payload, dict) else {}
    if not isinstance(approval.payload, dict):
        invalid("rejection payload must be an object")
    if (
        approval.artifact_type is not ArtifactType.APPROVAL
        or approval.actor_kind is not ActorKind.HUMAN
        or payload.get("schema_version") != APPROVAL_SCHEMA
        or payload.get("decision") != "reject"
        or payload.get("published") is not False
    ):
        invalid("artifact is not an authoritative human rejection/v1")
    if approval.permissions_label != skill_version.permissions_label:
        invalid("rejection permission label differs from the skill version")
    skill = payload.get("skill")
    evidence = payload.get("evidence")
    expected_skill = {
        "artifact_id": str(skill_version.artifact_id),
        "slug": skill_version.payload.get("slug"),
        "version": skill_version.payload.get("version"),
        "payload_sha256": payload_fingerprint(skill_version.payload),
    }
    if not isinstance(skill, dict) or any(
        skill.get(key) != value for key, value in expected_skill.items()
    ):
        invalid("rejection skill identity does not match the exact skill version")
    if not isinstance(evidence, dict) or len(approval.input_refs) != 3:
        invalid("rejection evidence references are malformed")
    if approval.input_refs[0] != skill_version.artifact_id:
        invalid("rejection does not reference the exact skill version")
    if evidence.get("automated_review_id") != str(approval.input_refs[1]) or (
        evidence.get("content_review_id") != str(approval.input_refs[2])
    ):
        invalid("rejection evidence payload disagrees with input_refs")
    automated = store.get(approval.input_refs[1])
    content = store.get(approval.input_refs[2])
    if automated is None or automated.artifact_type is not ArtifactType.REVIEW:
        invalid("rejection automated review is missing or invalid")
    if content is None or content.artifact_type is not ArtifactType.REVIEW:
        invalid("rejection content review is missing or invalid")
    try:
        scans = _validate_frozen_evidence(
            store=store, skill_version=skill_version, automated=automated, content=content,
        )
    except PublishRefused as exc:
        raise ApprovalChainInvalid(str(exc)) from exc
    if evidence.get("scan_artifact_ids") != [str(scan.artifact_id) for scan in scans]:
        invalid("rejection scan IDs disagree with the automated review chain")
    return FrozenApprovalEvidence(approval, automated, content, tuple(scans))


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
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> Artifact:
    """Record one explicit human decision; approval publishes, rejection never does."""
    if decision not in {"approve", "reject"}:
        raise PublishRefused("decision must be approve or reject")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason:
        raise PublishRefused("a non-empty human decision reason is required")
    _validate_environment(
        identity,
        environment,
        expected_entra_issuer=expected_entra_issuer,
        expected_entra_tenant=expected_entra_tenant,
    )
    skill_version, automated, content = _artifact_batch(store, [
        (skill_version_id, ArtifactType.SKILL_VERSION, "skill version"),
        (automated_review_id, ArtifactType.REVIEW, "automated review"),
        (content_review_id, ArtifactType.REVIEW, "content review"),
    ])
    try:
        fingerprint = payload_fingerprint(skill_version.payload)
    except ValueError as exc:
        raise PublishRefused("skill version payload is malformed") from exc
    if expected_payload_sha256 != fingerprint:
        raise PublishRefused("expected payload hash does not match the exact skill version")
    scans = _validate_evidence(
        store=store,
        skill_version=skill_version,
        automated=automated,
        content=content,
        decision=decision,
    )

    slug = skill_version.payload.get("slug")
    if decision == "approve" and environment != "test":
        registry_reader = getattr(store, "publication_registry_entry", None)
        if not callable(registry_reader):
            raise PublishRefused("publication registry authority is unavailable")
        registry_entry = registry_reader(slug)
        if (
            not isinstance(registry_entry, dict)
            or registry_entry.get("active") is not True
            or registry_entry.get("slug") != slug
            or registry_entry.get("role") != skill_version.payload.get("role")
            or registry_entry.get("level") != skill_version.payload.get("level")
            or registry_entry.get("permissions_label") != skill_version.permissions_label
        ):
            raise PublishRefused("skill is unregistered or its publication facets drifted")
        if automated.payload.get("judge_required") is not registry_entry.get("judge_required"):
            raise PublishRefused("judge sampling does not match immutable registry policy")

    reconciliation = None
    if decision == "approve":
        from semiskill.governance.reconciliation import reconcile_publications

        bundle_reader = getattr(store, "publication_reconciliation_bundle", None)
        if not callable(bundle_reader):
            raise PublishRefused("verified publication reconciliation bundle is unavailable")
        try:
            reconciliation = reconcile_publications(
                bundle_reader(),
                environment=environment,
                expected_entra_issuer=expected_entra_issuer,
                expected_entra_tenant=expected_entra_tenant,
            )
        except (TypeError, ValueError) as exc:
            raise PublishRefused("verified publication reconciliation bundle is malformed") from exc
        if reconciliation.issues:
            raise PublishRefused("verified publication history contains projection anomalies")

    authentication = _safe_authentication(identity)
    existing_candidates = _active_approvals(store)
    if reconciliation is not None:
        projected_ids = reconciliation.store.verified_publication_ids()
        existing_candidates = [
            approval for approval in existing_candidates
            if approval.artifact_id in projected_ids
        ]
    for existing in existing_candidates:
        payload = existing.payload
        if (
            payload.get("decision") == decision
            and payload.get("reason") == reason
            and payload.get("skill", {}).get("artifact_id") == str(skill_version.artifact_id)
            and payload.get("evidence", {}).get("automated_review_id") == str(automated.artifact_id)
            and payload.get("evidence", {}).get("content_review_id") == str(content.artifact_id)
            and payload.get("authentication") == authentication
        ):
            if decision == "approve":
                activate = getattr(store, "activate_approval", None)
                if not callable(activate):
                    raise PublishRefused("verified publication actuator is unavailable")
                activate(existing.artifact_id)
            return existing

    corrects = None
    if decision == "approve":
        candidate_version = _semver_tuple(skill_version.payload.get("version"))
        historical = [
            row for row in reconciliation.store.publication_projections()
            if row.decision == "approve" and row.slug == slug
        ]
        if candidate_version is None or any(
            _semver_tuple(row.version) is None
            or candidate_version <= _semver_tuple(row.version)
            for row in historical
        ):
            raise PublishRefused(
                "approval requires a semver greater than every verified publication epoch"
            )
        active = reconciliation.active_by_slug.get(slug)
        corrects = active.approval if active is not None else None

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
    append_approval = getattr(store, "append_approval", None)
    if not callable(append_approval):
        raise PublishRefused("verified publication actuator is unavailable")
    return append_approval(approval)


def publish_skill(*_args, **_kwargs):
    """Tombstone for the callback-based API, which could fabricate human sign-off."""
    raise PublishRefused(
        "publish_skill callback API was removed; use decide_publication with authenticated identity"
    )
