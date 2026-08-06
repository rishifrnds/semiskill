"""Canonical scoreboard/progress documents and fail-closed persistence.

The scoreboard is authoritative deterministic JSON. Worker progress is a separate ephemeral
document that references one scoreboard snapshot and can never alter its counts.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

SCOREBOARD_SCHEMA = "semiskill.scoreboard/v1"
PROGRESS_SCHEMA = "semiskill.progress/v1"


class SnapshotUnavailable(RuntimeError):
    """The configured snapshot source is absent, malformed, or internally inconsistent."""


def _canonical_bytes(document: dict) -> bytes:
    body = deepcopy(document)
    body.pop("snapshot_id", None)
    body.pop("generated_at", None)
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def finalize_scoreboard(body: dict, *, generated_at: str) -> dict:
    """Stamp schema/time and derive an ID unaffected by observation time or mapping order."""
    if not isinstance(body, dict):
        raise ValueError("scoreboard body must be an object")
    document = deepcopy(body)
    document["schema_version"] = SCOREBOARD_SCHEMA
    document["generated_at"] = generated_at
    document["snapshot_id"] = "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    _validate_scoreboard(document)
    return document


def _validate_scoreboard(document: object) -> dict:
    if not isinstance(document, dict):
        raise SnapshotUnavailable("scoreboard snapshot must be a JSON object")
    if document.get("schema_version") != SCOREBOARD_SCHEMA:
        raise SnapshotUnavailable("unsupported scoreboard snapshot schema")
    for key, expected in (
        ("snapshot_id", str), ("generated_at", str), ("scope", dict), ("sources", dict),
        ("registry", dict), ("funnel", dict), ("roles", list), ("cells", list),
        ("conservation", dict), ("anomalies", dict), ("release_gate", dict),
    ):
        if not isinstance(document.get(key), expected):
            raise SnapshotUnavailable(f"scoreboard snapshot field {key!r} is missing or invalid")
    expected_id = "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    if document["snapshot_id"] != expected_id:
        raise SnapshotUnavailable("scoreboard snapshot_id does not match its canonical content")
    return document


def validate_scoreboard_snapshot(document: object) -> dict:
    """Validate an in-memory provider result before it crosses a read API boundary."""
    return _validate_scoreboard(deepcopy(document))


def write_json_atomic(path: str | Path, document: dict) -> Path:
    """Write one complete UTF-8 JSON document or leave the prior file intact."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent,
        prefix=f".{target.name}.", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(document, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def load_scoreboard_snapshot(path: str | Path) -> dict:
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable(f"scoreboard snapshot unavailable: {target}") from exc
    return _validate_scoreboard(document)


def validate_progress_snapshot(document: object, snapshot_id: str) -> dict:
    """Validate ephemeral progress without allowing it to alter canonical scoreboard state."""
    if not isinstance(document, dict) or document.get("schema_version") != PROGRESS_SCHEMA:
        raise SnapshotUnavailable("unsupported progress snapshot schema")
    if document.get("scoreboard_snapshot_id") != snapshot_id:
        raise SnapshotUnavailable("progress scoreboard_snapshot_id does not match the scoreboard")
    if not isinstance(document.get("generated_at"), str) or not isinstance(
        document.get("workers"), list,
    ):
        raise SnapshotUnavailable("progress snapshot fields are missing or invalid")
    worker_ids: set[str] = set()
    for index, worker in enumerate(document["workers"]):
        if not isinstance(worker, dict):
            raise SnapshotUnavailable(f"progress worker {index} must be an object")
        for field in ("worker_id", "slug", "stage", "started_at", "updated_at"):
            if not isinstance(worker.get(field), str) or not worker[field].strip():
                raise SnapshotUnavailable(f"progress worker {index} field {field!r} is invalid")
        if type(worker.get("attempt")) is not int or worker["attempt"] < 1:
            raise SnapshotUnavailable(f"progress worker {index} attempt is invalid")
        if worker["worker_id"] in worker_ids:
            raise SnapshotUnavailable("progress worker_id values must be unique")
        worker_ids.add(worker["worker_id"])
    return deepcopy(document)


def load_progress(path: str | Path, snapshot_id: str) -> dict:
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable(f"progress snapshot unavailable: {target}") from exc
    return validate_progress_snapshot(document, snapshot_id)


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _repository_identity(root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True,
            text=True, encoding="utf-8",
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True,
            text=True, encoding="utf-8",
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return "unknown", True


def _validate_database_environment(database: dict, environment: str) -> None:
    """Prevent caller-supplied labels from disguising test/dev state as production state."""
    name = database.get("database_name") if isinstance(database, dict) else None
    if not isinstance(name, str) or not name:
        raise SnapshotUnavailable("database identity is missing its database name")
    is_test = name.lower().endswith("_test")
    production_name = os.environ.get("SEMISKILL_PRODUCTION_DATABASE_NAME")
    if environment == "test" and not is_test:
        raise SnapshotUnavailable("test snapshots require an isolated *_test database")
    if environment == "development" and (
        is_test or (production_name is not None and name == production_name)
    ):
        raise SnapshotUnavailable("development snapshot database identity is inconsistent")
    if environment == "production":
        if not production_name or name != production_name or is_test:
            raise SnapshotUnavailable("production database identity is not explicitly configured")
    if environment not in {"development", "test", "production"}:
        raise SnapshotUnavailable("snapshot environment is invalid")


def _security_projection(store, skill_version, reviews, artifacts_by_id, preferred=None) -> dict:
    from semiskill.artifacts.schema import ArtifactType
    from semiskill.authoring.gate import SECURITY_REVIEW_KIND

    candidates = [
        review for review in reviews
        if review.payload.get("review_kind") == SECURITY_REVIEW_KIND
        and review.input_refs and review.input_refs[0] == skill_version.artifact_id
    ]
    automated = preferred or max(
        candidates, key=lambda artifact: (artifact.timestamp_start, str(artifact.artifact_id)),
        default=None,
    )
    if automated is None:
        return {
            "status": "unscanned", "aggregate_verdict": None, "aggregate_safety": None,
            "judge_required": None, "automated_review_id": None, "stages": [], "errors": [],
        }

    errors: list[str] = []
    payload = automated.payload
    refs = automated.input_refs[1:]
    recorded = payload.get("scan_artifact_ids")
    if recorded != [str(ref) for ref in refs]:
        errors.append("SCAN_REFERENCE_MISMATCH")
    scans = []
    for ref in refs:
        scan = artifacts_by_id.get(ref)
        if scan is None or scan.artifact_type not in {
            ArtifactType.SCAN_RUN, ArtifactType.INJECTION_TEST,
        }:
            errors.append("MISSING_SCAN_ARTIFACT")
            continue
        if not scan.input_refs or scan.input_refs[0] != skill_version.artifact_id:
            errors.append("DETACHED_SCAN_ARTIFACT")
        scans.append(scan)

    stages = []
    seen: set[int] = set()
    for scan in sorted(scans, key=lambda artifact: (
        artifact.payload.get("stage") if type(artifact.payload.get("stage")) is int else 99,
        str(artifact.artifact_id),
    )):
        stage = scan.payload.get("stage")
        if type(stage) is not int or stage not in {1, 2, 3, 4, 5} or stage in seen:
            errors.append("INVALID_OR_DUPLICATE_STAGE")
        else:
            seen.add(stage)
        status = scan.payload.get("status")
        hard_fail = scan.payload.get("hard_fail")
        safety = scan.payload.get("safety_score")
        if status not in {"passed", "failed", "not_run", "not_sampled"}:
            errors.append("INVALID_STAGE_STATUS")
        if type(hard_fail) is not bool:
            errors.append("INVALID_HARD_FAIL")
        if type(safety) not in {int, float} or not 0.0 <= float(safety) <= 1.0:
            errors.append("INVALID_STAGE_SAFETY")
            safety = None
        stages.append({
            "stage": stage,
            "status": status if isinstance(status, str) else "invalid",
            "artifact_id": str(scan.artifact_id),
            "hard_fail": hard_fail if type(hard_fail) is bool else None,
            "safety": float(safety) if safety is not None else None,
        })

    if not {1, 2, 3, 4}.issubset(seen) or 5 not in seen:
        errors.append("MISSING_REQUIRED_STAGE")
    required = [stage for stage in stages if stage["stage"] in {1, 2, 3, 4}]
    if any(stage["status"] != "passed" or stage["hard_fail"] for stage in required):
        errors.append("REQUIRED_STAGE_BLOCKED")
    judge = next((stage for stage in stages if stage["stage"] == 5), None)
    judge_required = payload.get("judge_required")
    if type(judge_required) is not bool:
        errors.append("INVALID_JUDGE_REQUIREMENT")
    elif judge_required and (judge is None or judge["status"] != "passed"):
        errors.append("REQUIRED_JUDGE_NOT_PASSED")
    elif not judge_required and judge is not None and judge["status"] not in {"passed", "not_sampled"}:
        errors.append("INVALID_OPTIONAL_JUDGE_STATUS")
    if payload.get("verdict") != "approve":
        errors.append("AGGREGATE_NOT_APPROVE")
    aggregate = payload.get("aggregate_safety")
    if type(aggregate) not in {int, float} or not 0.0 <= float(aggregate) <= 1.0:
        errors.append("INVALID_AGGREGATE_SAFETY")
        aggregate = None
    status = "passed" if not errors else (
        "blocked" if any(code in errors for code in {
            "REQUIRED_STAGE_BLOCKED", "REQUIRED_JUDGE_NOT_PASSED", "AGGREGATE_NOT_APPROVE",
        }) else "invalid"
    )
    stages.append({
        "stage": 6,
        "status": "passed" if payload.get("verdict") == "approve" else "failed",
        "artifact_id": str(automated.artifact_id),
        "hard_fail": payload.get("verdict") != "approve",
        "safety": float(aggregate) if aggregate is not None else None,
    })
    return {
        "status": status,
        "aggregate_verdict": payload.get("verdict"),
        "aggregate_safety": float(aggregate) if aggregate is not None else None,
        "judge_required": judge_required if type(judge_required) is bool else None,
        "automated_review_id": str(automated.artifact_id),
        "stages": stages,
        "errors": sorted(set(errors)),
    }


def build_scoreboard_snapshot(
    *,
    store,
    registry_path: str | Path,
    skills_root: str | Path,
    generated_at: str,
    expected_active: int = 84,
    expected_declined: int = 20,
    expected_roles: int = 16,
    target_per_role: int | None = None,
    environment: str = "development",
    source_commit: str | None = None,
    repository_dirty: bool | None = None,
    repository_root: str | Path | None = None,
    phase: str = "dv-84",
) -> dict:
    """Derive one complete authoritative snapshot from registry, source tree, and artifacts."""
    from semiskill.artifacts.schema import ArtifactType, ActorKind
    from semiskill.authoring import facets
    from semiskill.authoring.consistency import RegistryError, check_pack
    from semiskill.authoring.gate import (
        CONTENT_REVIEW_KIND, INVALID, READY, REVIEWED, STALE, UNREVIEWED,
        readiness_for_review, readiness_for_version,
    )
    from semiskill.authoring.lint import lint_wave_dir
    from semiskill.authoring.scoreboard import load_registry
    from semiskill.capture.intake import build_skill_version, load_skill_dir, payload_fingerprint
    from semiskill.governance.publish import (
        APPROVAL_SCHEMA, ApprovalChainInvalid, resolve_frozen_approval_evidence,
    )

    registry_file = Path(registry_path)
    root = Path(skills_root)
    repo_root = Path(repository_root) if repository_root is not None else Path.cwd()
    raw_registry = json.loads(registry_file.read_text(encoding="utf-8"))
    registry = load_registry(registry_file)
    active_rows = [row for row in registry if not row.get("declined")]
    declined_rows = [row for row in registry if row.get("declined")]
    target = target_per_role if target_per_role is not None else (
        raw_registry.get("target_per_role", 5) if isinstance(raw_registry, dict) else 5
    )
    if type(target) is not int or target < 1:
        raise SnapshotUnavailable("registry target_per_role must be a positive integer")

    lint_report = lint_wave_dir(root)
    lint_by_slug = {report.slug: report for report in lint_report.reports if report.slug}
    try:
        consistency_findings = check_pack(root)
        consistency_registry_error = None
    except RegistryError as exc:
        consistency_findings = []
        consistency_registry_error = type(exc).__name__
    consistency_by_slug: dict[str, list] = {}
    for finding in consistency_findings:
        consistency_by_slug.setdefault(finding.slug, []).append(finding)
    consistency_errors = sum(finding.level == "error" for finding in consistency_findings)
    if consistency_registry_error:
        consistency_errors += 1

    skill_versions = store.by_type(ArtifactType.SKILL_VERSION)
    scans = store.by_type(ArtifactType.SCAN_RUN) + store.by_type(ArtifactType.INJECTION_TEST)
    reviews = store.by_type(ArtifactType.REVIEW)
    approvals = store.by_type(ArtifactType.APPROVAL)
    artifacts_by_id = {
        artifact.artifact_id: artifact
        for artifact in [*skill_versions, *scans, *reviews, *approvals]
    }

    authoritative_approvals = [
        approval for approval in approvals
        if approval.actor_kind is ActorKind.HUMAN
        and approval.payload.get("schema_version") == APPROVAL_SCHEMA
    ]
    approval_by_id = {approval.artifact_id: approval for approval in authoritative_approvals}

    def approval_contract_errors(approval) -> list[str]:
        payload = approval.payload
        errors: list[str] = []
        decision = payload.get("decision")
        if decision not in {"approve", "reject", "unpublish"}:
            errors.append("decision")
        if payload.get("published") is not (decision == "approve"):
            errors.append("published")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            errors.append("reason")
        authentication = payload.get("authentication")
        if not isinstance(authentication, dict) or authentication.get("provider") not in {
            "local_os", "entra_oidc",
        } or not isinstance(authentication.get("subject"), str) or not authentication["subject"].strip():
            errors.append("authentication")
        if payload.get("environment") not in {"development", "test", "production"}:
            errors.append("environment")
        elif payload.get("environment") == "production" and (
            not isinstance(authentication, dict)
            or authentication.get("provider") != "entra_oidc"
        ):
            errors.append("production_identity")
        skill = payload.get("skill")
        evidence = payload.get("evidence")
        if len(approval.input_refs) != 3 or not isinstance(skill, dict) or not isinstance(evidence, dict):
            errors.append("references")
        elif (
            skill.get("artifact_id") != str(approval.input_refs[0])
            or evidence.get("automated_review_id") != str(approval.input_refs[1])
            or evidence.get("content_review_id") != str(approval.input_refs[2])
        ):
            errors.append("reference_payload")
        return errors

    valid_publication_candidates: dict[str, list[tuple]] = {}
    invalid_approval_chains: list[str] = []
    active_rejections: set = set()
    invalid_ids: set = set()
    valid_positive: dict = {}
    for approval in authoritative_approvals:
        contract_errors = approval_contract_errors(approval)
        if contract_errors:
            invalid_ids.add(approval.artifact_id)
            continue
        if approval.payload.get("decision") != "approve":
            continue
        skill_version = artifacts_by_id.get(approval.input_refs[0])
        if skill_version is None or skill_version.artifact_type is not ArtifactType.SKILL_VERSION:
            invalid_ids.add(approval.artifact_id)
            continue
        try:
            frozen = resolve_frozen_approval_evidence(
                store, skill_version=skill_version, approval=approval,
            )
        except ApprovalChainInvalid:
            invalid_ids.add(approval.artifact_id)
            continue
        valid_positive[approval.artifact_id] = (skill_version, approval, frozen)

    valid_corrections: set = set()
    suppressed: set = set()
    correction_children: dict = {}
    for correction in authoritative_approvals:
        if correction.corrects_ref is not None:
            correction_children.setdefault(correction.corrects_ref, []).append(correction)
    for children in correction_children.values():
        if len(children) > 1:
            invalid_ids.update(child.artifact_id for child in children)
    for correction in sorted(authoritative_approvals, key=lambda artifact: (
        artifact.timestamp_start, str(artifact.artifact_id),
    )):
        if correction.corrects_ref is None:
            if correction.payload.get("decision") == "unpublish":
                invalid_ids.add(correction.artifact_id)
            continue
        correction_target = approval_by_id.get(correction.corrects_ref)
        target_positive = valid_positive.get(correction.corrects_ref)
        decision = correction.payload.get("decision")
        target_lineage_valid = bool(
            target_positive is not None
            and (
                correction_target.corrects_ref is None
                or correction_target.artifact_id in valid_corrections
            )
        ) if correction_target is not None else False
        relationship_valid = bool(
            correction.artifact_id not in invalid_ids
            and correction_target is not None
            and target_lineage_valid
            and correction.permissions_label == correction_target.permissions_label
            and correction.timestamp_start >= correction_target.timestamp_start
            and correction.payload.get("skill", {}).get("slug")
            == correction_target.payload.get("skill", {}).get("slug")
        )
        if decision == "approve":
            relationship_valid = relationship_valid and correction.artifact_id in valid_positive
        elif decision == "unpublish":
            relationship_valid = relationship_valid and (
                correction.input_refs == correction_target.input_refs
                and correction.payload.get("skill") == correction_target.payload.get("skill")
                and correction.payload.get("evidence") == correction_target.payload.get("evidence")
            )
        else:
            relationship_valid = False
        if relationship_valid:
            valid_corrections.add(correction.artifact_id)
            suppressed.add(correction_target.artifact_id)
        else:
            invalid_ids.add(correction.artifact_id)

    for approval in authoritative_approvals:
        if approval.payload.get("decision") == "reject" and approval.corrects_ref is None:
            if approval.artifact_id in invalid_ids:
                continue
            skill_version = artifacts_by_id.get(approval.input_refs[0])
            if skill_version is None or skill_version.artifact_type is not ArtifactType.SKILL_VERSION:
                invalid_ids.add(approval.artifact_id)
            else:
                active_rejections.add(skill_version.artifact_id)

    for approval_id, publication in valid_positive.items():
        approval = publication[1]
        if approval_id in suppressed:
            continue
        if approval.corrects_ref is not None and approval_id not in valid_corrections:
            invalid_ids.add(approval_id)
            continue
        slug = publication[0].payload.get("slug")
        if slug:
            valid_publication_candidates.setdefault(slug, []).append(publication)
    invalid_approval_chains.extend(str(artifact_id) for artifact_id in sorted(
        invalid_ids, key=str,
    ))
    duplicate_active_publications = sorted(
        slug for slug, candidates in valid_publication_candidates.items() if len(candidates) > 1
    )
    valid_publications = {
        slug: max(candidates, key=lambda item: (
            item[1].timestamp_start, str(item[1].artifact_id),
        ))
        for slug, candidates in valid_publication_candidates.items()
    }
    authoritative_ids = {approval.artifact_id for approval in authoritative_approvals}
    ungated_publications = sorted(
        str(approval.artifact_id) for approval in approvals
        if approval.artifact_id not in authoritative_ids
        and approval.payload.get("published") is True
    )

    disk_slugs = {path.parent.name for path in root.glob("*/SKILL.md")}
    active_slugs = {row["slug"] for row in active_rows}
    declined_slugs = {row["slug"] for row in declined_rows}
    source_payloads: dict[str, dict] = {}
    source_hashes: dict[str, str] = {}
    source_errors: dict[str, str] = {}
    for slug in sorted(disk_slugs):
        try:
            skill_md, files = load_skill_dir(root / slug)
            candidate = build_skill_version(skill_md=skill_md, actor="scoreboard", files=files)
            source_payloads[slug] = candidate.payload
            source_hashes[slug] = payload_fingerprint(candidate.payload)
        except (OSError, ValueError) as exc:
            source_errors[slug] = type(exc).__name__

    level_order = {value: index for index, value in enumerate(facets.LEVELS)}
    anomalies: dict[str, list[str]] = {
        "facet_drift": [],
        "unregistered_authored": sorted(disk_slugs - active_slugs),
        "unregistered_publications": sorted(set(valid_publications) - active_slugs),
        "declined_publications": sorted(set(valid_publications) & declined_slugs),
        "ungated_publications": ungated_publications,
        "stale_source_hashes": [],
        "stale_review_hashes": [],
        "stale_approval_hashes": [],
        "invalid_review_lineage": [],
        "invalid_approval_chains": sorted(invalid_approval_chains),
        "duplicate_active_publications": duplicate_active_publications,
        "missing_required_stages": [],
        "post_approval_blockers": [],
    }

    cells: list[dict] = []
    for row in registry:
        slug = row["slug"]
        declined = bool(row.get("declined"))
        decline = row.get("declined")
        decline_reason = (
            decline.get("why") if isinstance(decline, dict) else str(decline)
        ) if decline else None
        if declined:
            cells.append({
                "slug": slug, "role": row["role"], "level": row["level"],
                "title": row.get("title", slug), "registry_status": "declined",
                "declined_reason": decline_reason, "state": "declined",
                "stage_flags": {key: False for key in (
                    "authored", "strict_lint_pass", "security_pass", "reviewed",
                    "recheck_ready", "approved", "published",
                )},
                "payload_hashes": {"source": None, "skill_version": None,
                                   "content_review": None, "approval": None,
                                   "all_match": False},
                "facets": {"registry": {"role": row["role"], "level": row["level"]},
                           "source": {"role": None, "level": None},
                           "published": {"role": None, "level": None}, "drift": False},
                "checks": {"lint": {"status": "missing", "predicted_verdict": None,
                                      "errors": 0, "warnings": 0, "advisories": 0,
                                      "finding_codes": []},
                           "consistency": {"status": "missing", "errors": 0, "warnings": 0,
                                           "finding_codes": []},
                           "security": {"status": "unscanned", "aggregate_verdict": None,
                                        "aggregate_safety": None, "judge_required": None,
                                        "stages": []},
                           "content_review": {"status": UNREVIEWED, "attempt": None,
                                              "reviewer_identity": None, "fixer_identity": None,
                                              "open_blocking": 0, "open_non_blocking": 0,
                                              "finding_ids": []}},
                "artifacts": {"skill_version_id": None, "automated_review_id": None,
                              "content_review_id": None, "approval_id": None,
                              "scan_artifact_ids": [], "rollback_ref": None},
                "approval": {"status": "none", "decision": None, "actor": None,
                             "authentication_provider": None},
                "blockers": [],
            })
            continue

        authored = slug in disk_slugs
        source_payload = source_payloads.get(slug)
        source_hash = source_hashes.get(slug)
        lint_item = lint_by_slug.get(slug)
        lint_findings = list(lint_item.findings) if lint_item is not None else []
        lint_counts = {
            level: sum(finding.level == level for finding in lint_findings)
            for level in ("error", "warn", "advisory")
        }
        strict_lint_pass = bool(
            lint_item is not None and lint_item.predicted_verdict == "approve" and not lint_findings
        )
        slug_consistency = consistency_by_slug.get(slug, [])
        consistency_error_count = sum(finding.level == "error" for finding in slug_consistency)
        consistency_warning_count = sum(finding.level != "error" for finding in slug_consistency)

        publication = valid_publications.get(slug)
        published_version = publication[0] if publication else None
        approval = publication[1] if publication else None
        frozen = publication[2] if publication else None
        current_publication = bool(
            publication and source_hash
            and approval.payload["skill"]["payload_sha256"] == source_hash
        )
        if publication and not current_publication:
            anomalies["stale_source_hashes"].append(slug)
            anomalies["stale_approval_hashes"].append(slug)

        exact_versions = [
            version for version in skill_versions
            if version.payload.get("slug") == slug and source_hash
            and payload_fingerprint(version.payload) == source_hash
        ]
        selected_version = published_version if current_publication else max(
            exact_versions, key=lambda artifact: (
                artifact.timestamp_start, str(artifact.artifact_id),
            ), default=None,
        )

        if selected_version is not None:
            if current_publication:
                content_state = readiness_for_review(store, selected_version, frozen.content_review)
                content_review = frozen.content_review
                security = _security_projection(
                    store, selected_version, reviews, artifacts_by_id,
                    preferred=frozen.automated_review,
                )
            else:
                content_state = readiness_for_version(store, selected_version)
                content_review = content_state.review
                security = _security_projection(store, selected_version, reviews, artifacts_by_id)
        else:
            slug_content = [
                review for review in reviews
                if review.payload.get("review_kind") == CONTENT_REVIEW_KIND
                and review.payload.get("slug") == slug
            ]
            content_review = max(slug_content, key=lambda artifact: (
                artifact.timestamp_start, str(artifact.artifact_id),
            ), default=None)
            content_state = None
            security = {"status": "unscanned", "aggregate_verdict": None,
                        "aggregate_safety": None, "judge_required": None,
                        "automated_review_id": None, "stages": [], "errors": []}

        content_status = content_state.status if content_state is not None else (
            STALE if content_review is not None else UNREVIEWED
        )
        reviewed = bool(
            content_review is not None
            and selected_version is not None
            and content_review.input_refs
            and content_review.input_refs[0] == selected_version.artifact_id
        )
        recheck_ready = content_status == READY
        if content_status == STALE:
            anomalies["stale_review_hashes"].append(slug)
        if content_status == INVALID:
            anomalies["invalid_review_lineage"].append(slug)
        if "MISSING_REQUIRED_STAGE" in security.get("errors", []):
            anomalies["missing_required_stages"].append(slug)

        if current_publication:
            later_content = [
                review for review in reviews
                if review.payload.get("review_kind") == CONTENT_REVIEW_KIND
                and review.payload.get("slug") == slug
                and review.input_refs
                and review.input_refs[0] == published_version.artifact_id
                and review.timestamp_start > approval.timestamp_start
            ]
            if later_content:
                current_lineage = readiness_for_version(store, published_version)
                if not current_lineage.ready:
                    anomalies["post_approval_blockers"].append(slug)
                if current_lineage.status == INVALID:
                    anomalies["invalid_review_lineage"].append(slug)

        source_facets = {
            "role": source_payload.get("role") if source_payload else None,
            "level": source_payload.get("level") if source_payload else None,
        }
        published_facets = {
            "role": published_version.payload.get("role") if published_version else None,
            "level": published_version.payload.get("level") if published_version else None,
        }
        facet_drift = (
            source_payload is not None
            and (source_facets["role"], source_facets["level"]) != (row["role"], row["level"])
        ) or (
            published_version is not None
            and (published_facets["role"], published_facets["level"])
            != (row["role"], row["level"])
        )
        if facet_drift:
            anomalies["facet_drift"].append(slug)

        blockers: list[dict] = []
        if not authored:
            blockers.append({"code": "SOURCE_MISSING", "source": "filesystem", "artifact_id": None})
        if slug in source_errors:
            blockers.append({"code": "SOURCE_INVALID", "source": "filesystem", "artifact_id": None})
        if authored and not strict_lint_pass:
            blockers.append({"code": "STRICT_LINT_BLOCKED", "source": "lint", "artifact_id": None})
        if consistency_error_count or consistency_registry_error:
            blockers.append({"code": "CONSISTENCY_BLOCKED", "source": "consistency", "artifact_id": None})
        if security["status"] in {"blocked", "invalid"}:
            blockers.append({"code": "SECURITY_BLOCKED", "source": "scan",
                             "artifact_id": security.get("automated_review_id")})
        if reviewed and not recheck_ready:
            blockers.append({"code": "CONTENT_REVIEW_BLOCKED", "source": "review",
                             "artifact_id": str(content_review.artifact_id) if content_review else None})
        if publication and not current_publication:
            blockers.append({"code": "APPROVAL_STALE", "source": "approval",
                             "artifact_id": str(approval.artifact_id)})
        if facet_drift:
            blockers.append({"code": "FACET_DRIFT", "source": "registry", "artifact_id": None})

        rejected = bool(selected_version and selected_version.artifact_id in active_rejections)
        if rejected:
            blockers.append({"code": "APPROVAL_REJECTED", "source": "approval",
                             "artifact_id": None})
        if publication and not current_publication:
            state = "published_stale"
        elif current_publication:
            state = "published"
        elif not authored:
            state = "missing"
        elif slug in source_errors:
            state = "invalid"
        elif not strict_lint_pass:
            state = "lint_blocked"
        elif consistency_error_count or consistency_registry_error:
            state = "consistency_blocked"
        elif rejected:
            state = "approval_rejected"
        elif security["status"] == "unscanned":
            state = "security_pending"
        elif security["status"] != "passed":
            state = "security_blocked"
        elif not reviewed:
            state = "review_pending"
        elif not recheck_ready:
            state = "review_blocked"
        else:
            state = "recheck_ready"

        finding_ids = []
        if content_review is not None and isinstance(content_review.payload.get("findings"), list):
            finding_ids = sorted(
                finding.get("finding_id") for finding in content_review.payload["findings"]
                if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
            )
        scan_ids = [
            stage["artifact_id"] for stage in security["stages"]
            if stage["stage"] != 6 and stage["artifact_id"]
        ]
        content_hash = content_review.payload.get("skill_payload_sha256") if content_review else None
        approval_hash = approval.payload["skill"]["payload_sha256"] if approval else None
        skill_hash = payload_fingerprint(selected_version.payload) if selected_version else None
        hashes = [source_hash, skill_hash, content_hash, approval_hash]
        all_match = all(value is not None for value in hashes) and len(set(hashes)) == 1
        cells.append({
            "slug": slug, "role": row["role"], "level": row["level"],
            "title": row.get("title", slug), "registry_status": "active",
            "declined_reason": None, "state": state,
            "stage_flags": {
                "authored": authored, "strict_lint_pass": strict_lint_pass,
                "security_pass": security["status"] == "passed", "reviewed": reviewed,
                "recheck_ready": recheck_ready, "approved": current_publication,
                "published": current_publication,
            },
            "payload_hashes": {"source": source_hash, "skill_version": skill_hash,
                               "content_review": content_hash, "approval": approval_hash,
                               "all_match": all_match},
            "facets": {"registry": {"role": row["role"], "level": row["level"]},
                       "source": source_facets, "published": published_facets,
                       "drift": bool(facet_drift)},
            "checks": {
                "lint": {"status": "passed" if strict_lint_pass else (
                    "missing" if lint_item is None else "failed"),
                    "predicted_verdict": lint_item.predicted_verdict if lint_item else None,
                    "errors": lint_counts["error"], "warnings": lint_counts["warn"],
                    "advisories": lint_counts["advisory"],
                    "finding_codes": sorted({finding.rule for finding in lint_findings})},
                "consistency": {"status": "invalid" if consistency_registry_error else (
                    "failed" if consistency_error_count else "passed"),
                    "errors": consistency_error_count, "warnings": consistency_warning_count,
                    "finding_codes": sorted({finding.rule for finding in slug_consistency})},
                "security": {key: security[key] for key in (
                    "status", "aggregate_verdict", "aggregate_safety", "judge_required", "stages",
                )},
                "content_review": {
                    "status": content_status,
                    "attempt": content_review.payload.get("attempt") if content_review else None,
                    "reviewer_identity": content_review.payload.get("reviewer_identity") if content_review else None,
                    "fixer_identity": content_review.payload.get("fixer_identity") if content_review else None,
                    "open_blocking": content_state.open_blocking_findings if content_state else 0,
                    "open_non_blocking": content_state.open_non_blocking_findings if content_state else 0,
                    "finding_ids": finding_ids,
                },
            },
            "artifacts": {
                "skill_version_id": str(selected_version.artifact_id) if selected_version else None,
                "automated_review_id": security.get("automated_review_id"),
                "content_review_id": str(content_review.artifact_id) if content_review else None,
                "approval_id": str(approval.artifact_id) if approval else None,
                "scan_artifact_ids": scan_ids,
                "rollback_ref": approval.rollback_ref if approval else None,
            },
            "approval": {
                "status": "approved" if current_publication else (
                    "invalid" if publication else ("rejected" if rejected else "none")),
                "decision": approval.payload.get("decision") if approval else (
                    "reject" if rejected else None),
                "actor": approval.actor if approval else None,
                "authentication_provider": approval.payload.get("authentication", {}).get("provider")
                if approval else None,
            },
            "blockers": sorted(blockers, key=lambda blocker: (blocker["source"], blocker["code"])),
        })

    for values in anomalies.values():
        values.sort()
    cells.sort(key=lambda cell: (
        cell["role"], level_order.get(cell["level"], 999), cell["level"], cell["slug"],
    ))
    active_cells = [cell for cell in cells if cell["registry_status"] == "active"]
    flag_names = (
        "authored", "strict_lint_pass", "security_pass", "reviewed",
        "recheck_ready", "approved", "published",
    )
    funnel = {name: sum(cell["stage_flags"][name] for cell in active_cells) for name in flag_names}
    blocked_cells = [cell for cell in active_cells if cell["blockers"]]
    funnel["active"] = len(active_cells)
    funnel["blocked"] = {
        "total": len(blocked_cells),
        **{
            source: sum(any(blocker["source"] == source for blocker in cell["blockers"])
                        for cell in active_cells)
            for source in ("lint", "consistency", "scan", "review", "approval")
        },
    }
    state_names = (
        "missing", "lint_blocked", "consistency_blocked", "security_pending",
        "security_blocked", "review_pending", "review_blocked", "recheck_ready",
        "approval_rejected", "published", "published_stale", "invalid",
    )
    exclusive_states = {name: sum(cell["state"] == name for cell in active_cells) for name in state_names}

    roles = []
    active_roles = sorted({row["role"] for row in active_rows})
    for role in active_roles:
        mine = [cell for cell in active_cells if cell["role"] == role]
        declined_count = sum(row["role"] == role for row in declined_rows)
        published_count = sum(cell["stage_flags"]["published"] for cell in mine)
        roles.append({
            "role": role, "active": len(mine), "declined_provenance": declined_count,
            "published": published_count, "target": target,
            "gap": max(0, target - published_count),
            "meets_target": published_count >= target,
        })

    if sum(exclusive_states.values()) != len(active_cells):
        raise SnapshotUnavailable("exclusive scoreboard states do not conserve active registry cells")
    if sum(role["active"] for role in roles) != len(active_cells):
        raise SnapshotUnavailable("role active counts do not conserve the registry")
    if sum(role["published"] for role in roles) != funnel["published"]:
        raise SnapshotUnavailable("role published counts do not conserve the funnel")

    conservation_checks = {
        "registry_partition": len(registry) == len(active_cells) + len(declined_rows),
        "active_state_partition": sum(exclusive_states.values()) == len(active_cells),
        "role_active_partition": sum(role["active"] for role in roles) == len(active_cells),
        "role_published_partition": (
            sum(role["published"] for role in roles) == funnel["published"]
        ),
        "review_partition": funnel["reviewed"] >= funnel["recheck_ready"],
        "approval_publication_partition": funnel["approved"] == funnel["published"],
        "funnel_bounds": all(0 <= funnel[name] <= len(active_cells) for name in flag_names),
    }
    conservation = {
        "passed": all(conservation_checks.values()),
        "checks": conservation_checks,
    }

    checks = [
        ("REGISTRY_ACTIVE", len(active_cells), expected_active),
        ("REGISTRY_DECLINED", len(declined_rows), expected_declined),
        ("REGISTRY_ROLES", len(active_roles), expected_roles),
        ("ALL_AUTHORED", funnel["authored"], len(active_cells)),
        ("ALL_STRICT_LINT", funnel["strict_lint_pass"], len(active_cells)),
        ("ALL_REVIEWED", funnel["reviewed"], len(active_cells)),
        ("ALL_RECHECK_READY", funnel["recheck_ready"], len(active_cells)),
        ("ALL_APPROVED", funnel["approved"], len(active_cells)),
        ("ALL_PUBLISHED", funnel["published"], len(active_cells)),
        ("ALL_ROLES_TARGET", sum(role["meets_target"] for role in roles), len(active_roles)),
        ("CONSISTENCY_ERRORS", consistency_errors, 0),
        ("BLOCKERS", funnel["blocked"]["total"], 0),
        ("ANOMALIES", sum(len(values) for values in anomalies.values()), 0),
        ("CONSERVATION", int(conservation["passed"]), 1),
    ]
    release_checks = [
        {"code": code, "passed": actual == expected, "actual": actual, "expected": expected}
        for code, actual, expected in checks
    ]

    if source_commit is None or repository_dirty is None:
        detected_commit, detected_dirty = _repository_identity(repo_root)
        source_commit = source_commit if source_commit is not None else detected_commit
        repository_dirty = repository_dirty if repository_dirty is not None else detected_dirty
    registry_bytes = registry_file.read_bytes()
    skill_tree_material = "\n".join(
        f"{slug}:{source_hashes.get(slug, 'invalid:' + source_errors.get(slug, 'missing'))}"
        for slug in sorted(disk_slugs)
    ).encode("utf-8")
    database = store.database_identity(environment=environment) if hasattr(
        store, "database_identity"
    ) else {"engine": "unknown", "environment": environment, "database_name": "unknown",
            "identity_sha256": "sha256:" + "0" * 64}
    _validate_database_environment(database, environment)
    active_levels = sorted(
        {row["level"] for row in active_rows},
        key=lambda level: (level_order.get(level, 999), level),
    )
    body = {
        "scope": {"phase": phase,
                  "access_scope": "internal-catalog-operators",
                  "contains_all_permission_labels": True,
                  "scoped_export_eligible": False,
                  "expected_active": expected_active, "expected_declined": expected_declined,
                  "expected_roles": expected_roles, "target_per_role": target,
                  "declines_credit_role_target": False},
        "sources": {
            "repository": {"commit": source_commit, "dirty": bool(repository_dirty),
                           "tree_sha256": _sha256_bytes(skill_tree_material)},
            "registry": {"path": registry_file.as_posix(),
                         "sha256": _sha256_bytes(registry_bytes)},
            "skills": {"root": root.as_posix(), "tree_sha256": _sha256_bytes(skill_tree_material)},
            "database": database,
        },
        "policy": {"required_scan_stages": [1, 2, 3, 4, 6], "judge_stage": 5,
                   "judge_skipped_status": "not_sampled",
                   "required_content_checks": ["strict_lint", "consistency", "source_hash",
                                               "artifact_reconciliation"]},
        "registry": {"total": len(registry), "active": len(active_cells),
                     "declined": len(declined_rows), "roles": len(active_roles),
                     "levels": active_levels},
        "funnel": funnel,
        "exclusive_states": exclusive_states,
        "conservation": conservation,
        "roles": roles,
        "cells": cells,
        "anomalies": anomalies,
        "consistency": {"errors": consistency_errors,
                        "warnings": sum(f.level != "error" for f in consistency_findings),
                        "registry_error": consistency_registry_error},
        "release_gate": {"passed": all(check["passed"] for check in release_checks),
                         "checks": release_checks},
    }
    return finalize_scoreboard(body, generated_at=generated_at)
