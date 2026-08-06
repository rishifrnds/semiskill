"""Single-label, snapshot-bound authorization for offline exports.

Static files cannot enforce an ACL after download.  Their security boundary is therefore the
materialization operation: resolve one authenticated principal, choose exactly one permission
label, bind the active publication heads to a canonical scoreboard snapshot, and stamp that scope
into every export.  Exporters consume this object; they never load an all-label catalog and filter
it after the fact.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Mapping

from semiskill.artifacts.schema import Artifact, ArtifactType, PERMISSIONS_LABELS
from semiskill.artifacts.store import ScopedPublicationBundle
from semiskill.authoring.snapshot import validate_scoreboard_snapshot
from semiskill.capture.intake import payload_fingerprint
from semiskill.context.acl import ResolvedPrincipal
from semiskill.governance.publish import (
    ApprovalChainInvalid,
    FrozenApprovalEvidence,
    resolve_frozen_approval_evidence,
)

EXPORT_SCOPE_SCHEMA = "semiskill.export-scope/v1"


class ExportRefused(RuntimeError):
    """The requested materialization is not authorized or no longer matches its evidence."""


def _sha256(value: object) -> bool:
    if not isinstance(value, str):
        return False
    raw = value[7:] if value.startswith("sha256:") else value
    if len(raw) != 64:
        return False
    try:
        int(raw, 16)
    except ValueError:
        return False
    return True


def _utc(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an aware UTC RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an aware UTC RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be an aware UTC RFC3339 timestamp")
    return value


def _uuid(value: object, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ExportRefused(f"{field} is not a UUID") from exc


@dataclass(frozen=True, slots=True)
class ExportPublicationRef:
    slug: str
    skill_version_id: uuid.UUID
    approval_id: uuid.UUID
    automated_review_id: uuid.UUID
    content_review_id: uuid.UUID
    scan_artifact_ids: tuple[uuid.UUID, ...]
    payload_sha256: str
    permissions_label: str

    def __post_init__(self):
        if not isinstance(self.slug, str) or not self.slug.strip():
            raise ValueError("export publication slug is required")
        if self.permissions_label not in PERMISSIONS_LABELS:
            raise ValueError("export publication permission label is invalid")
        if not _sha256(self.payload_sha256):
            raise ValueError("export publication payload hash is invalid")
        for field in (
            "skill_version_id", "approval_id", "automated_review_id", "content_review_id",
        ):
            if not isinstance(getattr(self, field), uuid.UUID):
                raise ValueError(f"export publication {field} must be a UUID")
        if not self.scan_artifact_ids or any(
            not isinstance(value, uuid.UUID) for value in self.scan_artifact_ids
        ):
            raise ValueError("export publication scan IDs must be a non-empty UUID tuple")


@dataclass(frozen=True, slots=True)
class ExportScope:
    principal: ResolvedPrincipal
    permission_label: str
    generated_at: str
    scoreboard_snapshot_id: str
    scoreboard_generated_at: str
    source_commit: str
    source_skills_root: str
    source_tree_sha256: str
    database_environment: str
    database_name: str
    database_identity_sha256: str
    export_reader_identity_sha256: str
    publications: tuple[ExportPublicationRef, ...]
    schema_version: str = EXPORT_SCOPE_SCHEMA

    def __post_init__(self):
        if self.schema_version != EXPORT_SCOPE_SCHEMA:
            raise ValueError("unsupported export scope schema")
        if not isinstance(self.principal, ResolvedPrincipal):
            raise ValueError("export scope requires a resolved principal")
        if not self.principal.trusted_for_export:
            raise ValueError("export scope requires a trusted resolver-issued principal")
        if self.permission_label not in PERMISSIONS_LABELS:
            raise ValueError("export scope permission label is invalid")
        if self.permission_label not in self.principal.labels:
            raise ValueError("export permission label exceeds the principal clearance")
        if self.database_environment not in {"development", "test", "production"}:
            raise ValueError("export database environment is invalid")
        if self.database_environment == "production" and self.principal.provider != "entra_oidc":
            raise ValueError("production exports require an Entra/OIDC resolved principal")
        if not isinstance(self.database_name, str) or not self.database_name.strip():
            raise ValueError("export database name is required")
        if not isinstance(self.source_commit, str) or not self.source_commit.strip() or (
            self.source_commit == "unknown"
        ):
            raise ValueError("export source commit is required")
        root = PurePosixPath(self.source_skills_root)
        if (
            not self.source_skills_root
            or root.is_absolute()
            or ".." in root.parts
            or "\\" in self.source_skills_root
        ):
            raise ValueError("export skills root must be a safe repository-relative path")
        for value, field in (
            (self.scoreboard_snapshot_id, "scoreboard snapshot ID"),
            (self.source_tree_sha256, "source tree hash"),
            (self.database_identity_sha256, "database identity hash"),
            (self.export_reader_identity_sha256, "export reader identity hash"),
        ):
            if not _sha256(value):
                raise ValueError(f"export {field} is invalid")
        _utc(self.generated_at, "export generated_at")
        _utc(self.scoreboard_generated_at, "scoreboard generated_at")
        ordered = tuple(sorted(self.publications, key=lambda ref: ref.slug))
        if ordered != self.publications or len({ref.slug for ref in ordered}) != len(ordered):
            raise ValueError("export publications must be unique and sorted by slug")
        if any(ref.permissions_label != self.permission_label for ref in ordered):
            raise ValueError("export scope cannot contain mixed permission labels")

    @property
    def scope_id(self) -> str:
        payload = json.dumps(
            self.safe_dict(include_scope_id=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def safe_dict(self, *, include_scope_id: bool = True) -> dict:
        """Return the non-secret stamp; other clearances and auth context never leave memory."""
        document = {
            "schema_version": self.schema_version,
            "principal": {
                "principal_ref": "sha256:" + hashlib.sha256(
                    self.principal.subject.encode("utf-8")
                ).hexdigest(),
                "provider": self.principal.provider,
            },
            "permission_label": self.permission_label,
            "generated_at": self.generated_at,
            "scoreboard_snapshot_id": self.scoreboard_snapshot_id,
            "scoreboard_generated_at": self.scoreboard_generated_at,
            "source_commit": self.source_commit,
            "source_skills_root": self.source_skills_root,
            "source_tree_sha256": self.source_tree_sha256,
            "database": {
                "environment": self.database_environment,
                "database_name": self.database_name,
                "identity_sha256": self.database_identity_sha256,
                "export_reader_identity_sha256": self.export_reader_identity_sha256,
            },
            "publications": [
                {
                    **asdict(ref),
                    "skill_version_id": str(ref.skill_version_id),
                    "approval_id": str(ref.approval_id),
                    "automated_review_id": str(ref.automated_review_id),
                    "content_review_id": str(ref.content_review_id),
                    "scan_artifact_ids": [str(value) for value in ref.scan_artifact_ids],
                }
                for ref in self.publications
            ],
        }
        if include_scope_id:
            document["scope_id"] = self.scope_id
        return document

    def assert_store_identity(self, store) -> None:
        reader = getattr(store, "database_identity", None)
        if not callable(reader):
            raise ExportRefused("export store cannot prove its database identity")
        observed = reader(environment=self.database_environment)
        if not isinstance(observed, dict) or (
            observed.get("identity_sha256") != self.database_identity_sha256
            or observed.get("database_name") != self.database_name
            or observed.get("environment") != self.database_environment
        ):
            raise ExportRefused("export scope database identity is stale or mismatched")
        export_reader = getattr(store, "export_database_identity", None)
        export_identity = export_reader(
            environment=self.database_environment,
        ) if callable(export_reader) else None
        if not isinstance(export_identity, dict) or (
            export_identity.get("identity_sha256") != self.export_reader_identity_sha256
            or export_identity.get("permission_label") != self.permission_label
        ):
            raise ExportRefused("export reader capability is stale or mismatched")


def _repository_identity(repo_root: Path) -> tuple[str, bool]:
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=normal"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExportRefused("repository identity is unavailable") from exc
    return head, bool(status.strip())


def _skills_tree_sha256(root: Path) -> str:
    """Recompute the canonical source material used by the scoreboard tree identity."""
    from semiskill.capture.intake import (
        build_skill_version,
        load_skill_source,
        shared_bundle_for_skills_root,
    )

    rows: dict[str, str] = {}
    shared_bundle = shared_bundle_for_skills_root(root)
    for skill_path in sorted(root.rglob("SKILL.md")):
        skill_md, files = load_skill_source(skill_path.parent, shared_bundle=shared_bundle)
        payload = build_skill_version(
            skill_md=skill_md, actor="export-scope-tree", files=files,
        ).payload
        slug = payload["slug"]
        if slug in rows:
            raise ExportRefused(f"duplicate source slug while binding export tree: {slug}")
        rows[slug] = payload_fingerprint(payload)
    material = "\n".join(f"{slug}:{rows[slug]}" for slug in sorted(rows)).encode("utf-8")
    return "sha256:" + hashlib.sha256(material).hexdigest()


def make_export_scope(
    *,
    principal: ResolvedPrincipal,
    permission_label: str,
    scoreboard: Mapping[str, object],
    generated_at: str,
    repo_root: str | Path,
    store,
) -> ExportScope:
    """Derive one authorized label from a validated all-label operator scoreboard."""
    if not isinstance(principal, ResolvedPrincipal) or not principal.trusted_for_export:
        raise ExportRefused("a trusted resolver-issued principal is required")
    if permission_label not in principal.labels:
        raise ExportRefused("requested export label exceeds the resolved principal clearance")
    try:
        snapshot = validate_scoreboard_snapshot(dict(scoreboard))
    except Exception as exc:  # validation details may disclose internal snapshot state
        raise ExportRefused("canonical scoreboard snapshot is invalid") from exc

    snapshot_environment = snapshot.get("sources", {}).get("database", {}).get("environment")
    if snapshot_environment == "production" and principal.provider != "entra_oidc":
        raise ExportRefused("production exports require an Entra/OIDC resolved principal")

    sources = snapshot["sources"]
    repository = sources["repository"]
    skills = sources.get("skills") if isinstance(sources, dict) else None
    database = sources["database"]
    if repository.get("dirty") is not False:
        raise ExportRefused("offline exports require a clean source snapshot")
    current_commit, current_dirty = _repository_identity(Path(repo_root))
    if current_dirty or current_commit != repository.get("commit"):
        raise ExportRefused("offline export source no longer matches the scoreboard snapshot")
    source_tree = skills.get("tree_sha256") if isinstance(skills, dict) else (
        repository.get("tree_sha256")
    )
    if not _sha256(source_tree):
        raise ExportRefused("scoreboard source tree hash is unavailable")
    skills_root = skills.get("root") if isinstance(skills, dict) else None
    try:
        relative_root = PurePosixPath(skills_root)
    except TypeError as exc:
        raise ExportRefused("scoreboard skills root is unavailable") from exc
    if (
        not skills_root or relative_root.is_absolute() or ".." in relative_root.parts
        or "\\" in skills_root
    ):
        raise ExportRefused("scoreboard skills root is unsafe")
    try:
        observed_tree = _skills_tree_sha256(Path(repo_root).resolve() / Path(*relative_root.parts))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExportRefused("scoreboard skills tree cannot be recomputed safely") from exc
    if observed_tree != source_tree:
        raise ExportRefused("offline export source tree no longer matches the scoreboard snapshot")
    if any(snapshot["anomalies"].values()):
        raise ExportRefused("scoreboard contains publication anomalies")
    try:
        observed_database = store.database_identity(environment=database["environment"])
        export_database = store.export_database_identity(environment=database["environment"])
    except Exception as exc:
        raise ExportRefused("export database capabilities are unavailable") from exc
    if (
        observed_database.get("identity_sha256") != database.get("identity_sha256")
        or observed_database.get("database_name") != database.get("database_name")
    ):
        raise ExportRefused("scoreboard database identity no longer matches the export store")
    if export_database.get("permission_label") != permission_label:
        raise ExportRefused("export database capability does not authorize the requested label")

    refs: list[ExportPublicationRef] = []
    for cell in snapshot["cells"]:
        if not cell["stage_flags"]["published"]:
            continue
        permissions = cell.get("permissions")
        if not isinstance(permissions, dict) or permissions.get("registry_expected") != permission_label:
            continue
        if (
            cell.get("state") != "published"
            or cell.get("blockers")
            or permissions.get("all_match") is not True
            or any(permissions.get(key) != permission_label for key in (
                "skill_version", "approval", "content_review",
            ))
            or any(label != permission_label for label in permissions.get("scan_labels", []))
        ):
            raise ExportRefused(f"published cell {cell.get('slug')} has invalid scoped evidence")
        artifacts = cell.get("artifacts")
        hashes = cell.get("payload_hashes")
        if not isinstance(artifacts, dict) or not isinstance(hashes, dict) or (
            hashes.get("all_match") is not True
        ):
            raise ExportRefused(f"published cell {cell.get('slug')} lacks exact artifact hashes")
        refs.append(ExportPublicationRef(
            slug=cell["slug"],
            skill_version_id=_uuid(artifacts.get("skill_version_id"), "skill_version_id"),
            approval_id=_uuid(artifacts.get("approval_id"), "approval_id"),
            automated_review_id=_uuid(
                artifacts.get("automated_review_id"), "automated_review_id",
            ),
            content_review_id=_uuid(artifacts.get("content_review_id"), "content_review_id"),
            scan_artifact_ids=tuple(
                _uuid(value, "scan_artifact_id")
                for value in artifacts.get("scan_artifact_ids", [])
            ),
            payload_sha256=hashes.get("skill_version"),
            permissions_label=permission_label,
        ))

    try:
        return ExportScope(
            principal=principal,
            permission_label=permission_label,
            generated_at=generated_at,
            scoreboard_snapshot_id=snapshot["snapshot_id"],
            scoreboard_generated_at=snapshot["generated_at"],
            source_commit=repository["commit"],
            source_skills_root=skills_root,
            source_tree_sha256=source_tree,
            database_environment=database["environment"],
            database_name=database["database_name"],
            database_identity_sha256=database["identity_sha256"],
            export_reader_identity_sha256=export_database["identity_sha256"],
            publications=tuple(sorted(refs, key=lambda ref: ref.slug)),
        )
    except ValueError as exc:
        raise ExportRefused(str(exc)) from exc


class _ArtifactSubset:
    def __init__(
        self,
        artifacts: tuple[Artifact, ...],
        verified_review_contract_ids: tuple[uuid.UUID, ...],
    ):
        self._rows = artifacts
        self._by_id = {artifact.artifact_id: artifact for artifact in artifacts}
        self._verified_review_contract_ids = frozenset(verified_review_contract_ids)

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        return self._by_id.get(artifact_id)

    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]:
        return [self._by_id[value] for value in artifact_ids if value in self._by_id]

    def by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        return [row for row in self._rows if row.artifact_type is artifact_type]

    def verified_review_contract_ids(self) -> set[uuid.UUID]:
        return set(self._verified_review_contract_ids)

    def review_contract_verified(
        self, contract_id: uuid.UUID, permissions_label: str,
    ) -> bool:
        artifact = self._by_id.get(contract_id)
        return (
            contract_id in self._verified_review_contract_ids
            and artifact is not None
            and artifact.artifact_type is ArtifactType.GATE_DECISION
            and artifact.permissions_label == permissions_label
        )


@dataclass(frozen=True, slots=True)
class ScopedPublication:
    reference: ExportPublicationRef
    skill_version: Artifact
    approval: Artifact
    evidence: FrozenApprovalEvidence


def load_scoped_publications(store, scope: ExportScope) -> tuple[ScopedPublication, ...]:
    """Load only authorized payloads and prove they still equal the snapshot's active heads."""
    if not isinstance(scope, ExportScope):
        raise ExportRefused("an explicit export scope is required")
    scope.assert_store_identity(store)
    reader = getattr(store, "scoped_publication_bundle", None)
    if not callable(reader):
        raise ExportRefused("scoped publication reader is unavailable")
    try:
        bundle = reader(scope.permission_label)
    except Exception as exc:
        raise ExportRefused("scoped publication read failed") from exc
    if not isinstance(bundle, ScopedPublicationBundle):
        raise ExportRefused("scoped publication reader returned a malformed bundle")
    if any(not hasattr(head, "slug") for head in bundle.heads) or any(
        not isinstance(artifact, Artifact) for artifact in bundle.artifacts
    ):
        raise ExportRefused("scoped publication bundle contains malformed rows")
    artifact_ids = [artifact.artifact_id for artifact in bundle.artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ExportRefused("scoped publication bundle contains duplicate artifact IDs")
    if len(bundle.artifacts) > 20100:
        raise ExportRefused("scoped publication bundle exceeds its evidence bound")
    if any(
        artifact.permissions_label != scope.permission_label for artifact in bundle.artifacts
    ):
        raise ExportRefused("scoped publication bundle contains a different permission label")

    expected_heads = {
        ref.slug: (
            ref.approval_id, ref.skill_version_id, ref.automated_review_id,
            ref.content_review_id, ref.permissions_label,
        )
        for ref in scope.publications
    }
    actual_heads = {
        head.slug: (
            head.approval_id, head.skill_version_id, head.automated_review_id,
            head.content_review_id, head.permissions_label,
        )
        for head in bundle.heads
    }
    if actual_heads != expected_heads or len(actual_heads) != len(bundle.heads):
        raise ExportRefused("active publication heads no longer match the export snapshot")

    verified_contract_ids = tuple(bundle.verified_review_contract_ids)
    if len(verified_contract_ids) != len(set(verified_contract_ids)):
        raise ExportRefused("scoped publication bundle contains duplicate contract witnesses")
    subset = _ArtifactSubset(bundle.artifacts, verified_contract_ids)
    for contract_id in verified_contract_ids:
        contract = subset.get(contract_id)
        if contract is None or contract.artifact_type is not ArtifactType.GATE_DECISION:
            raise ExportRefused("scoped publication bundle has an invalid contract witness")
    reachable: set[uuid.UUID] = set()
    reachable_contracts: set[uuid.UUID] = set()
    for ref in scope.publications:
        if len(ref.scan_artifact_ids) != len(set(ref.scan_artifact_ids)):
            raise ExportRefused(f"{ref.slug}: export snapshot has duplicate scan IDs")
        reachable.update((
            ref.approval_id, ref.skill_version_id, ref.automated_review_id,
            ref.content_review_id, *ref.scan_artifact_ids,
        ))
        review_id = ref.content_review_id
        visited: set[uuid.UUID] = set()
        for _depth in range(64):
            if review_id in visited:
                raise ExportRefused(f"{ref.slug}: content-review lineage contains a cycle")
            visited.add(review_id)
            review = subset.get(review_id)
            if review is None or review.artifact_type is not ArtifactType.REVIEW:
                raise ExportRefused(f"{ref.slug}: content-review lineage is missing")
            if not isinstance(review.payload, dict) or (
                review.payload.get("review_kind") != "content_review"
                or review.payload.get("schema_version") != 2
            ):
                raise ExportRefused(f"{ref.slug}: content-review lineage is malformed")
            prior_ref = review.payload.get("prior_review_ref") if isinstance(
                review.payload, dict
            ) else None
            expected_refs = 2 if prior_ref is None else 3
            if len(review.input_refs) != expected_refs:
                raise ExportRefused(f"{ref.slug}: content-review lineage is malformed")
            reviewed_skill_id = review.input_refs[0]
            contract_id = review.input_refs[1]
            reviewed_skill = subset.get(reviewed_skill_id)
            contract = subset.get(contract_id)
            if (
                reviewed_skill is None
                or reviewed_skill.artifact_type is not ArtifactType.SKILL_VERSION
                or contract is None
                or contract.artifact_type is not ArtifactType.GATE_DECISION
                or contract_id not in set(verified_contract_ids)
            ):
                raise ExportRefused(f"{ref.slug}: review skill or contract evidence is missing")
            reachable.update((reviewed_skill_id, contract_id))
            reachable_contracts.add(contract_id)
            if prior_ref is None:
                break
            review_id = review.input_refs[2]
            if str(review_id) != prior_ref:
                raise ExportRefused(f"{ref.slug}: content-review prior reference disagrees")
            reachable.add(review_id)
        else:
            raise ExportRefused(f"{ref.slug}: content-review lineage exceeds 64 attempts")
    if set(verified_contract_ids) != reachable_contracts:
        raise ExportRefused("scoped publication bundle has missing or unrelated contract witnesses")
    if set(artifact_ids) != reachable:
        raise ExportRefused("scoped publication bundle contains missing or unrelated evidence")
    rows: list[ScopedPublication] = []
    for ref in scope.publications:
        skill = subset.get(ref.skill_version_id)
        approval = subset.get(ref.approval_id)
        if skill is None or skill.artifact_type is not ArtifactType.SKILL_VERSION:
            raise ExportRefused(f"{ref.slug}: scoped skill version is missing")
        if approval is None or approval.artifact_type is not ArtifactType.APPROVAL:
            raise ExportRefused(f"{ref.slug}: scoped approval is missing")
        if payload_fingerprint(skill.payload) != ref.payload_sha256.removeprefix("sha256:"):
            raise ExportRefused(f"{ref.slug}: scoped payload hash is stale")
        try:
            frozen = resolve_frozen_approval_evidence(
                subset, skill_version=skill, approval=approval,
            )
        except ApprovalChainInvalid as exc:
            raise ExportRefused(f"{ref.slug}: frozen approval chain is invalid") from exc
        if (
            frozen.automated_review.artifact_id != ref.automated_review_id
            or frozen.content_review.artifact_id != ref.content_review_id
            or tuple(scan.artifact_id for scan in frozen.scans) != ref.scan_artifact_ids
        ):
            raise ExportRefused(f"{ref.slug}: frozen evidence differs from the export snapshot")
        rows.append(ScopedPublication(ref, skill, approval, frozen))
    return tuple(rows)
