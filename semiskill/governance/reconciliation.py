"""Pure reconciliation of append-only publication events with their frozen artifact chain."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind
from semiskill.artifacts.store import (
    PublicationProjectionRow,
    PublicationReconciliationBundle,
    ReconciledArtifactStore,
)
from semiskill.capture.intake import payload_fingerprint

_HASH = re.compile(r"^[0-9a-f]{64}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DECISIONS = frozenset({"approve", "unpublish"})
_ENVIRONMENTS = frozenset({"development", "test", "production"})
_LABELS = frozenset({"public", "team", "need-to-know", "regulated"})


@dataclass(frozen=True, slots=True)
class ProjectionIssue:
    code: str
    approval_id: uuid.UUID | None
    slug: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class ReconciledPublication:
    projection: PublicationProjectionRow
    skill_version: Artifact
    approval: Artifact
    frozen_evidence: object


@dataclass(frozen=True, slots=True)
class PublicationReconciliation:
    store: ReconciledArtifactStore
    active_by_slug: dict[str, ReconciledPublication]
    issues: tuple[ProjectionIssue, ...]
    invalid_approval_ids: frozenset[uuid.UUID]


def _semver(value: object) -> tuple[int, int, int] | None:
    match = _SEMVER.fullmatch(value) if isinstance(value, str) else None
    if match is None or any(len(part) > 18 for part in match.groups()):
        return None
    return tuple(int(part) for part in match.groups())


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() and Decimal("0") <= result <= Decimal("1") else None


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _chain_sha256(approval: Artifact, row: PublicationProjectionRow) -> str:
    material = (
        _canonical_json(approval.payload)
        + "|" + ",".join(str(value) for value in approval.input_refs)
        + "|" + (str(approval.corrects_ref) if approval.corrects_ref is not None else "")
        + "|" + row.policy_version
        + "|" + format(row.approve_threshold, "f")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _completed_at(artifact: Artifact) -> datetime:
    return artifact.timestamp_end or artifact.timestamp_start


def reconcile_publications(
    bundle: PublicationReconciliationBundle,
    *,
    environment: str | None = None,
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> PublicationReconciliation:
    """Return exact active heads or quarantine their slug; never choose a duplicate/newest winner."""
    from semiskill.governance.identity import IdentityRefused, identity_from_authentication
    from semiskill.governance.publish import (
        APPROVAL_SCHEMA,
        ApprovalChainInvalid,
        resolve_frozen_approval_evidence,
    )

    view = ReconciledArtifactStore(bundle)
    by_id = {artifact.artifact_id: artifact for artifact in bundle.artifacts}
    projections = tuple(bundle.projections)
    by_projection = {row.approval_id: row for row in projections}
    issues: list[ProjectionIssue] = []
    invalid: set[uuid.UUID] = set()
    affected_slugs: set[str] = set()
    frozen: dict[uuid.UUID, ReconciledPublication] = {}

    def issue(row: PublicationProjectionRow | None, code: str, detail: str) -> None:
        approval_id = row.approval_id if row is not None and isinstance(row.approval_id, uuid.UUID) else None
        slug = row.slug if row is not None and isinstance(row.slug, str) and row.slug else None
        if approval_id is not None:
            invalid.add(approval_id)
        if slug is not None:
            affected_slugs.add(slug)
        issues.append(ProjectionIssue(code, approval_id, slug, detail))

    for row in projections:
        uuid_values = (
            row.approval_id, row.skill_version_id, row.automated_review_id,
            row.content_review_id,
        )
        threshold = _decimal(row.approve_threshold)
        if (
            not all(isinstance(value, uuid.UUID) for value in uuid_values)
            or (row.corrects_ref is not None and not isinstance(row.corrects_ref, uuid.UUID))
            or row.decision not in _DECISIONS
            or not isinstance(row.slug, str) or not row.slug.strip()
            or _semver(row.version) is None
            or not isinstance(row.payload_sha256, str) or not _HASH.fullmatch(row.payload_sha256)
            or row.permissions_label not in _LABELS
            or row.environment not in _ENVIRONMENTS
            or not isinstance(row.policy_version, str) or not row.policy_version.strip()
            or not isinstance(row.approve_threshold, Decimal) or threshold is None
            or not isinstance(row.chain_sha256, str) or not _HASH.fullmatch(row.chain_sha256)
            or not isinstance(row.activated_at, datetime) or row.activated_at.tzinfo is None
            or not isinstance(row.activated_by, str) or not row.activated_by.strip()
        ):
            issue(row, "PROJECTION_DRIFT", "projection row has an invalid scalar shape")
            continue
        if environment is not None and row.environment != environment:
            issue(row, "PROJECTION_DRIFT", "projection environment differs from the requested snapshot")
            continue

        approval = by_id.get(row.approval_id)
        skill = by_id.get(row.skill_version_id)
        automated = by_id.get(row.automated_review_id)
        content = by_id.get(row.content_review_id)
        if approval is None or approval.artifact_type is not ArtifactType.APPROVAL:
            issue(row, "PROJECTION_ORPHAN", "approval artifact is missing or has the wrong type")
            continue
        if skill is None or skill.artifact_type is not ArtifactType.SKILL_VERSION:
            issue(row, "PROJECTION_ORPHAN", "skill-version artifact is missing or has the wrong type")
            continue
        if automated is None or automated.artifact_type is not ArtifactType.REVIEW:
            issue(row, "PROJECTION_ORPHAN", "automated review is missing or has the wrong type")
            continue
        if content is None or content.artifact_type is not ArtifactType.REVIEW:
            issue(row, "PROJECTION_ORPHAN", "content review is missing or has the wrong type")
            continue
        payload = approval.payload if isinstance(approval.payload, dict) else {}
        skill_payload = skill.payload if isinstance(skill.payload, dict) else {}
        skill_record = payload.get("skill") if isinstance(payload.get("skill"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        rollback = approval.rollback_ref if isinstance(approval.rollback_ref, dict) else {}
        expected_refs = [row.skill_version_id, row.automated_review_id, row.content_review_id]
        expected_rollback = (
            {
                "action": "unpublish",
                "skill_version_id": str(row.skill_version_id),
                "approval_id": str(row.approval_id),
            }
            if row.decision == "approve"
            else {"action": "reapprove", "approval_id": str(row.corrects_ref)}
        )
        if (
            approval.actor_kind is not ActorKind.HUMAN
            or approval.input_refs != expected_refs
            or approval.corrects_ref != row.corrects_ref
            or approval.permissions_label != row.permissions_label
            or payload.get("schema_version") != APPROVAL_SCHEMA
            or payload.get("decision") != row.decision
            or payload.get("published") is not (row.decision == "approve")
            or payload.get("environment") != row.environment
            or not isinstance(payload.get("reason"), str) or not payload["reason"].strip()
            or skill_record.get("artifact_id") != str(row.skill_version_id)
            or skill_record.get("slug") != row.slug
            or skill_record.get("version") != row.version
            or skill_record.get("payload_sha256") != row.payload_sha256
            or evidence.get("automated_review_id") != str(row.automated_review_id)
            or evidence.get("content_review_id") != str(row.content_review_id)
            or rollback != expected_rollback
            or skill_payload.get("slug") != row.slug
            or skill_payload.get("version") != row.version
            or skill_payload.get("payload_sha256") != row.payload_sha256
            or payload_fingerprint(skill_payload) != row.payload_sha256
            or skill.permissions_label != row.permissions_label
            or automated.permissions_label != row.permissions_label
            or content.permissions_label != row.permissions_label
            or _completed_at(approval) > row.activated_at
        ):
            issue(row, "PROJECTION_DRIFT", "projection fields disagree with the frozen artifacts")
            continue
        try:
            identity_from_authentication(
                payload.get("authentication"),
                artifact_actor=approval.actor,
                environment=row.environment,
                expected_entra_issuer=expected_entra_issuer,
                expected_entra_tenant=expected_entra_tenant,
            )
        except IdentityRefused:
            issue(row, "PROJECTION_DRIFT", "approval authentication is invalid")
            continue
        try:
            if _chain_sha256(approval, row) != row.chain_sha256:
                issue(row, "PROJECTION_DRIFT", "projection chain hash does not match")
                continue
        except (TypeError, ValueError, OverflowError):
            issue(row, "PROJECTION_DRIFT", "projection chain material is not canonical JSON")
            continue
        if row.decision == "approve":
            try:
                evidence_chain = resolve_frozen_approval_evidence(
                    view, skill_version=skill, approval=approval,
                )
            except ApprovalChainInvalid:
                issue(row, "PROJECTION_DRIFT", "frozen approval evidence is invalid")
                continue
            frozen[row.approval_id] = ReconciledPublication(
                row, skill, approval, evidence_chain,
            )

    children: dict[uuid.UUID, list[PublicationProjectionRow]] = {}
    for row in projections:
        if isinstance(row.corrects_ref, uuid.UUID):
            children.setdefault(row.corrects_ref, []).append(row)
    for target_id, rows in children.items():
        if len(rows) > 1:
            parent = by_projection.get(target_id)
            if parent is not None:
                issue(parent, "PROJECTION_TOPOLOGY", "projection target has multiple children")
            for row in rows:
                issue(row, "PROJECTION_TOPOLOGY", "projection target has multiple children")

    for row in projections:
        seen: set[uuid.UUID] = set()
        cursor = row
        while cursor.corrects_ref is not None:
            if cursor.approval_id in seen or cursor.corrects_ref == cursor.approval_id:
                issue(row, "PROJECTION_TOPOLOGY", "projection correction graph contains a cycle")
                break
            seen.add(cursor.approval_id)
            parent = by_projection.get(cursor.corrects_ref)
            if parent is None or parent.decision != "approve":
                issue(row, "PROJECTION_ORPHAN", "projection parent is missing or is not an approval")
                break
            if (
                row.slug != parent.slug
                or row.permissions_label != parent.permissions_label
                or row.activated_at < parent.activated_at
            ):
                issue(row, "PROJECTION_TOPOLOGY", "projection correction changes immutable lineage")
                break
            if row.decision == "approve" and (
                _semver(row.version) is None
                or _semver(parent.version) is None
                or _semver(row.version) <= _semver(parent.version)
            ):
                issue(row, "PROJECTION_TOPOLOGY", "superseding semver is not monotonic")
                break
            if row.decision == "unpublish":
                approval = by_id.get(row.approval_id)
                parent_approval = by_id.get(parent.approval_id)
                if (
                    approval is None or parent_approval is None
                    or approval.input_refs != parent_approval.input_refs
                    or not isinstance(approval.payload, dict)
                    or not isinstance(parent_approval.payload, dict)
                    or approval.payload.get("skill") != parent_approval.payload.get("skill")
                    or approval.payload.get("evidence") != parent_approval.payload.get("evidence")
                ):
                    issue(row, "PROJECTION_TOPOLOGY", "unpublish does not preserve frozen evidence")
                break
            cursor = parent

    historical: dict[str, list[PublicationProjectionRow]] = {}
    for row in sorted(projections, key=lambda item: (item.activated_at, str(item.approval_id))):
        if row.decision != "approve" or row.approval_id in invalid:
            continue
        prior_versions = historical.setdefault(row.slug, [])
        candidate = _semver(row.version)
        if any(candidate is None or candidate <= _semver(prior.version) for prior in prior_versions):
            issue(row, "PROJECTION_TOPOLOGY", "approval semver does not exceed publication history")
        prior_versions.append(row)

    corrected = {
        row.corrects_ref for row in projections if isinstance(row.corrects_ref, uuid.UUID)
    }
    candidates: dict[str, list[PublicationProjectionRow]] = {}
    for row in projections:
        if row.decision == "approve" and row.approval_id not in corrected:
            candidates.setdefault(row.slug, []).append(row)

    active: dict[str, ReconciledPublication] = {}
    for slug, rows in candidates.items():
        if len(rows) != 1:
            affected_slugs.add(slug)
            for row in rows:
                issues.append(ProjectionIssue(
                    "DUPLICATE_PUBLICATION_HEAD", row.approval_id, slug,
                    "slug has multiple uncorrected verified approval heads",
                ))
            continue
        row = rows[0]
        if slug in affected_slugs or row.approval_id in invalid:
            continue
        publication = frozen.get(row.approval_id)
        if publication is not None:
            active[slug] = publication

    return PublicationReconciliation(
        store=view,
        active_by_slug=active,
        issues=tuple(issues),
        invalid_approval_ids=frozenset(invalid),
    )
