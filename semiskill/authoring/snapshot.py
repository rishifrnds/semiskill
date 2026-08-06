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
_FLAG_NAMES = (
    "authored", "strict_lint_pass", "security_pass", "reviewed",
    "recheck_ready", "approved", "published",
)
_STATE_NAMES = (
    "missing", "lint_blocked", "consistency_blocked", "security_pending",
    "security_blocked", "review_pending", "review_blocked", "recheck_ready",
    "approval_rejected", "published", "published_stale", "invalid",
)
_BLOCKER_SOURCES = ("lint", "consistency", "scan", "review", "approval")


class SnapshotUnavailable(RuntimeError):
    """The configured snapshot source is absent, malformed, or internally inconsistent."""


def _semantic_validate_scoreboard(document: dict) -> None:
    """Recompute every count exposed by a persisted/provider-supplied scoreboard."""
    try:
        registry = document["registry"]
        funnel = document["funnel"]
        scope = document["scope"]
        cells = document["cells"]
        roles = document["roles"]
        anomalies = document["anomalies"]
        exclusive_states = document["exclusive_states"]
        consistency = document["consistency"]
        conservation = document["conservation"]
        release_gate = document["release_gate"]
    except KeyError as exc:
        raise SnapshotUnavailable("scoreboard semantic section is missing") from exc

    for mapping, names in (
        (registry, ("total", "active", "declined", "roles")),
        (scope, ("expected_active", "expected_declined", "expected_roles", "target_per_role")),
    ):
        if not isinstance(mapping, dict) or any(type(mapping.get(name)) is not int for name in names):
            raise SnapshotUnavailable("scoreboard registry/scope counts are invalid")
    if any(registry[name] < 0 for name in ("total", "active", "declined", "roles")):
        raise SnapshotUnavailable("scoreboard registry counts cannot be negative")
    if scope["target_per_role"] < 1:
        raise SnapshotUnavailable("scoreboard target_per_role must be positive")
    database = document.get("sources", {}).get("database")
    if not isinstance(database, dict) or database.get("environment") not in {
        "development", "test", "production",
    }:
        raise SnapshotUnavailable("scoreboard database environment is invalid")

    active_cells: list[dict] = []
    declined_cells: list[dict] = []
    slugs: set[str] = set()
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("slug"), str) or not cell["slug"]:
            raise SnapshotUnavailable("scoreboard cell identity is invalid")
        if cell["slug"] in slugs:
            raise SnapshotUnavailable("scoreboard cell slugs must be unique")
        slugs.add(cell["slug"])
        if not isinstance(cell.get("role"), str) or not cell["role"]:
            raise SnapshotUnavailable("scoreboard cell role is invalid")
        flags = cell.get("stage_flags")
        if not isinstance(flags, dict) or any(type(flags.get(name)) is not bool for name in _FLAG_NAMES):
            raise SnapshotUnavailable("scoreboard cell stage flags are invalid")
        blockers = cell.get("blockers")
        if not isinstance(blockers, list) or any(
            not isinstance(blocker, dict)
            or not isinstance(blocker.get("source"), str)
            or not isinstance(blocker.get("code"), str)
            for blocker in blockers
        ):
            raise SnapshotUnavailable("scoreboard cell blockers are invalid")
        status = cell.get("registry_status")
        if status == "active":
            if cell.get("state") not in _STATE_NAMES:
                raise SnapshotUnavailable("active scoreboard cell state is invalid")
            active_cells.append(cell)
        elif status == "declined":
            if cell.get("state") != "declined" or any(flags.values()):
                raise SnapshotUnavailable("declined cells cannot credit the funnel")
            declined_cells.append(cell)
        else:
            raise SnapshotUnavailable("scoreboard cell registry_status is invalid")

    expected_registry = {
        "total": len(cells),
        "active": len(active_cells),
        "declined": len(declined_cells),
        "roles": len({cell["role"] for cell in active_cells}),
    }
    if any(registry.get(key) != value for key, value in expected_registry.items()):
        raise SnapshotUnavailable("scoreboard registry counts do not match its cells")

    if type(funnel.get("active")) is not int or funnel["active"] != len(active_cells):
        raise SnapshotUnavailable("scoreboard active funnel count does not match its cells")
    for name in _FLAG_NAMES:
        expected = sum(cell["stage_flags"][name] for cell in active_cells)
        if type(funnel.get(name)) is not int or funnel[name] != expected:
            raise SnapshotUnavailable(f"scoreboard funnel {name!r} does not match its cells")
    blocked = funnel.get("blocked")
    if not isinstance(blocked, dict):
        raise SnapshotUnavailable("scoreboard blocked funnel is invalid")
    expected_blocked = sum(bool(cell["blockers"]) for cell in active_cells)
    if type(blocked.get("total")) is not int or blocked["total"] != expected_blocked:
        raise SnapshotUnavailable("scoreboard blocked total does not match its cells")
    for source in _BLOCKER_SOURCES:
        expected = sum(
            any(blocker["source"] == source for blocker in cell["blockers"])
            for cell in active_cells
        )
        if type(blocked.get(source)) is not int or blocked[source] != expected:
            raise SnapshotUnavailable("scoreboard blocked source count does not match its cells")

    expected_states = {
        name: sum(cell["state"] == name for cell in active_cells) for name in _STATE_NAMES
    }
    if exclusive_states != expected_states:
        raise SnapshotUnavailable("scoreboard exclusive states do not match its cells")

    if len(roles) != registry["roles"]:
        raise SnapshotUnavailable("scoreboard role count does not match the registry")
    seen_roles: set[str] = set()
    for role in roles:
        if not isinstance(role, dict) or not isinstance(role.get("role"), str):
            raise SnapshotUnavailable("scoreboard role row is invalid")
        name = role["role"]
        if name in seen_roles:
            raise SnapshotUnavailable("scoreboard role rows must be unique")
        seen_roles.add(name)
        mine = [cell for cell in active_cells if cell["role"] == name]
        declined = sum(cell["role"] == name for cell in declined_cells)
        published = sum(cell["stage_flags"]["published"] for cell in mine)
        target = scope["target_per_role"]
        expected_role = {
            "active": len(mine), "declined_provenance": declined,
            "published": published, "target": target,
            "gap": max(0, target - published), "meets_target": published >= target,
        }
        if any(role.get(key) != value for key, value in expected_role.items()):
            raise SnapshotUnavailable("scoreboard role coverage does not match its cells")
    if seen_roles != {cell["role"] for cell in active_cells}:
        raise SnapshotUnavailable("scoreboard role rows do not cover all active cells")

    if not isinstance(anomalies, dict) or any(
        not isinstance(values, list)
        or any(not isinstance(value, str) for value in values)
        or values != sorted(set(values))
        for values in anomalies.values()
    ):
        raise SnapshotUnavailable("scoreboard anomaly arrays must be sorted unique strings")
    expected_conservation_checks = {
        "registry_partition": registry["total"] == registry["active"] + registry["declined"],
        "active_state_partition": sum(expected_states.values()) == registry["active"],
        "role_active_partition": sum(role["active"] for role in roles) == registry["active"],
        "role_published_partition": (
            sum(role["published"] for role in roles) == funnel["published"]
        ),
        "review_partition": funnel["reviewed"] >= funnel["recheck_ready"],
        "approval_publication_partition": funnel["approved"] == funnel["published"],
        "funnel_bounds": all(0 <= funnel[name] <= registry["active"] for name in _FLAG_NAMES),
    }
    if conservation != {
        "passed": all(expected_conservation_checks.values()),
        "checks": expected_conservation_checks,
    }:
        raise SnapshotUnavailable("scoreboard conservation claims do not match its cells")
    if type(consistency.get("errors")) is not int or consistency["errors"] < 0:
        raise SnapshotUnavailable("scoreboard consistency error count is invalid")

    release_expected = {
        "REGISTRY_ACTIVE": (registry["active"], scope["expected_active"]),
        "REGISTRY_DECLINED": (registry["declined"], scope["expected_declined"]),
        "REGISTRY_ROLES": (registry["roles"], scope["expected_roles"]),
        "ALL_AUTHORED": (funnel["authored"], registry["active"]),
        "ALL_STRICT_LINT": (funnel["strict_lint_pass"], registry["active"]),
        "ALL_REVIEWED": (funnel["reviewed"], registry["active"]),
        "ALL_RECHECK_READY": (funnel["recheck_ready"], registry["active"]),
        "ALL_APPROVED": (funnel["approved"], registry["active"]),
        "ALL_PUBLISHED": (funnel["published"], registry["active"]),
        "ALL_ROLES_TARGET": (sum(role["meets_target"] for role in roles), registry["roles"]),
        "CONSISTENCY_ERRORS": (consistency["errors"], 0),
        "BLOCKERS": (blocked["total"], 0),
        "ANOMALIES": (sum(len(values) for values in anomalies.values()), 0),
        "CONSERVATION": (int(conservation["passed"]), 1),
    }
    checks = release_gate.get("checks")
    if not isinstance(checks, list) or len(checks) != len(release_expected):
        raise SnapshotUnavailable("scoreboard release checks are missing or duplicated")
    seen_codes: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or check.get("code") not in release_expected:
            raise SnapshotUnavailable("scoreboard release check is invalid")
        code = check["code"]
        if code in seen_codes:
            raise SnapshotUnavailable("scoreboard release check codes must be unique")
        seen_codes.add(code)
        actual, expected = release_expected[code]
        if check.get("actual") != actual or check.get("expected") != expected or (
            check.get("passed") is not (actual == expected)
        ):
            raise SnapshotUnavailable("scoreboard release check does not match authoritative state")
    expected_release = all(actual == expected for actual, expected in release_expected.values())
    if seen_codes != set(release_expected) or release_gate.get("passed") is not expected_release:
        raise SnapshotUnavailable("scoreboard release gate does not match its checks")


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
    _semantic_validate_scoreboard(document)
    return document


def validate_scoreboard_snapshot(document: object) -> dict:
    """Validate an in-memory provider result before it crosses a read API boundary."""
    return _validate_scoreboard(deepcopy(document))


def render_scoreboard_snapshot(document: object, *, style: str = "text") -> str:
    """Render only values from a semantically validated canonical snapshot."""
    snapshot = validate_scoreboard_snapshot(document)
    if style == "json":
        return json.dumps(snapshot, indent=2, sort_keys=True)
    funnel = snapshot["funnel"]
    roles = snapshot["roles"]
    if style == "markdown":
        lines = [
            f"### Canonical catalog scoreboard — {funnel['published']}/{funnel['active']} published",
            "",
            "| Role | Published | Target | Gap |",
            "|---|---:|---:|---:|",
        ]
        lines.extend(
            f"| {role['role']} | {role['published']} | {role['target']} | {role['gap']} |"
            for role in roles
        )
        lines.extend(["", f"Release gate: {'pass' if snapshot['release_gate']['passed'] else 'blocked'}"])
        return "\n".join(lines)
    if style != "text":
        raise ValueError(f"unknown scoreboard snapshot render style: {style!r}")
    lines = [
        f"canonical scoreboard · generated {snapshot['generated_at']}",
        f"registry {snapshot['registry']['active']} active + {snapshot['registry']['declined']} declined",
        (f"authored {funnel['authored']} · strict lint {funnel['strict_lint_pass']} · "
         f"security {funnel['security_pass']} · reviewed {funnel['reviewed']} · "
         f"ready {funnel['recheck_ready']} · approved {funnel['approved']} · "
         f"published {funnel['published']}"),
        "",
    ]
    lines.extend(
        f"  {('ok' if role['meets_target'] else 'SHORT'):5} {role['role']:34} "
        f"{role['published']}/{role['target']}"
        for role in roles
    )
    failed = [check for check in snapshot["release_gate"]["checks"] if not check["passed"]]
    lines.extend(["", f"release gate: {'pass' if not failed else 'blocked'}"])
    lines.extend(
        f"  - {check['code']}: {check['actual']} (expected {check['expected']})"
        for check in failed
    )
    return "\n".join(lines)


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


def _security_projection(
    store, skill_version, reviews, artifacts_by_id, preferred=None,
    judge_required_by_policy: bool = True,
) -> dict:
    from semiskill.artifacts.schema import ArtifactType
    from semiskill.authoring.gate import SECURITY_REVIEW_KIND
    from semiskill.governance.publish import MIN_APPROVAL_SAFETY, _canonical_score, _completed_at

    candidates = [
        review for review in reviews
        if isinstance(review.payload, dict)
        and review.payload.get("review_kind") == SECURITY_REVIEW_KIND
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
    payload = automated.payload if isinstance(automated.payload, dict) else {}
    if not isinstance(automated.payload, dict):
        errors.append("INVALID_AGGREGATE_PAYLOAD")
    if (
        automated.artifact_type is not ArtifactType.REVIEW
        or payload.get("review_kind") != SECURITY_REVIEW_KIND
        or payload.get("schema_version") != 1
        or payload.get("stage") != 6
    ):
        errors.append("INVALID_AGGREGATE_SCHEMA")
    if automated.permissions_label != skill_version.permissions_label:
        errors.append("AGGREGATE_PERMISSION_DRIFT")
    if _completed_at(skill_version) > automated.timestamp_start:
        errors.append("AGGREGATE_PREDATES_SKILL")
    refs = automated.input_refs[1:]
    if len(automated.input_refs) != 6 or automated.input_refs[0] != skill_version.artifact_id:
        errors.append("INVALID_SCAN_REFERENCE_COUNT")
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
        scan_payload = scan.payload if isinstance(scan.payload, dict) else {}
        if not isinstance(scan.payload, dict):
            errors.append("INVALID_SCAN_PAYLOAD")
        if len(scan.input_refs) != 1 or scan.input_refs[0] != skill_version.artifact_id:
            errors.append("DETACHED_SCAN_ARTIFACT")
        if scan.permissions_label != skill_version.permissions_label:
            errors.append("SCAN_PERMISSION_DRIFT")
        if _completed_at(skill_version) > scan.timestamp_start:
            errors.append("SCAN_PREDATES_SKILL")
        if _completed_at(scan) > automated.timestamp_start:
            errors.append("SCAN_COMPLETES_AFTER_AGGREGATE")
        scans.append(scan)

    stages = []
    seen: set[int] = set()
    for scan in sorted(scans, key=lambda artifact: (
        artifact.payload.get("stage")
        if isinstance(artifact.payload, dict) and type(artifact.payload.get("stage")) is int
        else 99,
        str(artifact.artifact_id),
    )):
        scan_payload = scan.payload if isinstance(scan.payload, dict) else {}
        stage = scan_payload.get("stage")
        if type(stage) is not int or stage not in {1, 2, 3, 4, 5} or stage in seen:
            errors.append("INVALID_OR_DUPLICATE_STAGE")
        else:
            seen.add(stage)
            expected_type = ArtifactType.INJECTION_TEST if stage == 3 else ArtifactType.SCAN_RUN
            if scan.artifact_type is not expected_type:
                errors.append("INVALID_STAGE_ARTIFACT_TYPE")
        status = scan_payload.get("status")
        sampled = scan_payload.get("sampled")
        hard_fail = scan_payload.get("hard_fail")
        safety = scan_payload.get("safety_score")
        if status not in {"passed", "failed", "not_run", "not_sampled"}:
            errors.append("INVALID_STAGE_STATUS")
        if type(sampled) is not bool:
            errors.append("INVALID_SAMPLED_STATE")
        elif sampled is not (status in {"passed", "failed"}):
            errors.append("STAGE_STATUS_SAMPLE_MISMATCH")
        if type(hard_fail) is not bool:
            errors.append("INVALID_HARD_FAIL")
        canonical_safety = _canonical_score(safety)
        if canonical_safety is None:
            errors.append("INVALID_STAGE_SAFETY")
            safety = None
        elif scan.eval_score is None or float(scan.eval_score) != canonical_safety:
            errors.append("STAGE_EVAL_SCORE_MISMATCH")
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
    if any(stage["hard_fail"] is not False for stage in stages):
        errors.append("HARD_FAIL_PRESENT")
    judge = next((stage for stage in stages if stage["stage"] == 5), None)
    judge_required = payload.get("judge_required")
    if type(judge_required) is not bool:
        errors.append("INVALID_JUDGE_REQUIREMENT")
    elif judge_required is not judge_required_by_policy:
        errors.append("JUDGE_POLICY_MISMATCH")
    elif judge_required and (judge is None or judge["status"] != "passed"):
        errors.append("REQUIRED_JUDGE_NOT_PASSED")
    elif not judge_required and judge is not None and judge["status"] not in {"passed", "not_sampled"}:
        errors.append("INVALID_OPTIONAL_JUDGE_STATUS")
    if payload.get("verdict") != "approve":
        errors.append("AGGREGATE_NOT_APPROVE")
    aggregate = payload.get("aggregate_safety")
    canonical_aggregate = _canonical_score(aggregate)
    if canonical_aggregate is None:
        errors.append("INVALID_AGGREGATE_SAFETY")
        aggregate = None
    elif automated.eval_score is None or float(automated.eval_score) != canonical_aggregate:
        errors.append("AGGREGATE_EVAL_SCORE_MISMATCH")
    measured = [
        stage["safety"] for stage, scan in zip(stages, sorted(scans, key=lambda artifact: (
            artifact.payload.get("stage")
            if isinstance(artifact.payload, dict) and type(artifact.payload.get("stage")) is int
            else 99,
            str(artifact.artifact_id),
        )))
        if isinstance(scan.payload, dict) and scan.payload.get("sampled") is True
        and stage["safety"] is not None
    ]
    if (
        canonical_aggregate is not None
        and (
            not measured
            or canonical_aggregate != min(measured)
            or canonical_aggregate < MIN_APPROVAL_SAFETY
        )
    ):
        errors.append("AGGREGATE_POLICY_MISMATCH")
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
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
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
        APPROVAL_SCHEMA, ApprovalChainInvalid, resolve_frozen_rejection_evidence,
    )
    from semiskill.governance.identity import IdentityRefused, identity_from_authentication
    from semiskill.governance.reconciliation import reconcile_publications

    if environment == "production" and (
        not isinstance(expected_entra_issuer, str) or not expected_entra_issuer.strip()
        or not isinstance(expected_entra_tenant, str) or not expected_entra_tenant.strip()
    ):
        raise SnapshotUnavailable("production Entra issuer and tenant policy are required")

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

    bundle_reader = getattr(store, "publication_reconciliation_bundle", None)
    if not callable(bundle_reader):
        raise SnapshotUnavailable("verified publication reconciliation bundle is unavailable")
    try:
        reconciliation = reconcile_publications(
            bundle_reader(),
            environment=environment,
            expected_entra_issuer=expected_entra_issuer,
            expected_entra_tenant=expected_entra_tenant,
        )
    except (TypeError, ValueError) as exc:
        raise SnapshotUnavailable("verified publication reconciliation bundle is malformed") from exc
    reconciled_store = reconciliation.store
    projected_ids = reconciled_store.verified_publication_ids()
    skill_versions = reconciled_store.by_type(ArtifactType.SKILL_VERSION)
    scans = (
        reconciled_store.by_type(ArtifactType.SCAN_RUN)
        + reconciled_store.by_type(ArtifactType.INJECTION_TEST)
    )
    reviews = reconciled_store.by_type(ArtifactType.REVIEW)
    approvals = reconciled_store.by_type(ArtifactType.APPROVAL)
    malformed_artifact_payloads = sorted(
        str(artifact.artifact_id)
        for artifact in [*skill_versions, *scans, *reviews, *approvals]
        if not isinstance(artifact.payload, dict)
    )
    artifacts_by_id = {
        artifact.artifact_id: artifact
        for artifact in [*skill_versions, *scans, *reviews, *approvals]
    }

    authoritative_approvals = [
        approval for approval in approvals
        if approval.actor_kind is ActorKind.HUMAN
        and isinstance(approval.payload, dict)
        and approval.payload.get("schema_version") == APPROVAL_SCHEMA
    ]
    def approval_contract_errors(approval) -> list[str]:
        payload = approval.payload if isinstance(approval.payload, dict) else {}
        errors: list[str] = []
        if not isinstance(approval.payload, dict):
            errors.append("payload")
        decision = payload.get("decision")
        if not isinstance(decision, str) or decision not in {"approve", "reject", "unpublish"}:
            errors.append("decision")
        if payload.get("published") is not (decision == "approve"):
            errors.append("published")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            errors.append("reason")
        approval_environment = payload.get("environment")
        if not isinstance(approval_environment, str) or approval_environment not in {
            "development", "test", "production",
        }:
            errors.append("environment")
        elif approval_environment != environment:
            errors.append("snapshot_environment")
        else:
            try:
                identity_from_authentication(
                    payload.get("authentication"),
                    artifact_actor=approval.actor,
                    environment=environment,
                    expected_entra_issuer=expected_entra_issuer,
                    expected_entra_tenant=expected_entra_tenant,
                )
            except IdentityRefused:
                errors.append("authentication")
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

    invalid_ids: set = set(reconciliation.invalid_approval_ids)
    invalid_approval_chains: list[str] = [
        str(issue.approval_id) for issue in reconciliation.issues
        if issue.approval_id is not None
    ]
    active_rejections: set = set()
    for approval in authoritative_approvals:
        contract_errors = approval_contract_errors(approval)
        if contract_errors:
            invalid_ids.add(approval.artifact_id)
            continue
        if approval.corrects_ref is not None and approval.artifact_id not in projected_ids:
            invalid_ids.add(approval.artifact_id)
            continue
        if approval.payload.get("decision") != "reject" or approval.corrects_ref is not None:
            continue
        skill_version = artifacts_by_id.get(approval.input_refs[0])
        if skill_version is None or skill_version.artifact_type is not ArtifactType.SKILL_VERSION:
            invalid_ids.add(approval.artifact_id)
        else:
            try:
                resolve_frozen_rejection_evidence(
                    reconciled_store, skill_version=skill_version, approval=approval,
                )
            except ApprovalChainInvalid:
                invalid_ids.add(approval.artifact_id)
            else:
                active_rejections.add(skill_version.artifact_id)

    invalid_approval_chains.extend(str(artifact_id) for artifact_id in sorted(
        invalid_ids, key=str,
    ))
    valid_publications = {
        slug: (
            publication.skill_version,
            publication.approval,
            publication.frozen_evidence,
        )
        for slug, publication in reconciliation.active_by_slug.items()
    }
    duplicate_active_publications = sorted({
        issue.slug for issue in reconciliation.issues
        if issue.code == "DUPLICATE_PUBLICATION_HEAD" and issue.slug is not None
    })
    orphaned_projection_rows = sorted({
        str(issue.approval_id) for issue in reconciliation.issues
        if issue.code == "PROJECTION_ORPHAN" and issue.approval_id is not None
    })
    projection_drift = sorted({
        str(issue.approval_id) for issue in reconciliation.issues
        if issue.code not in {"PROJECTION_ORPHAN", "DUPLICATE_PUBLICATION_HEAD"}
        and issue.approval_id is not None
    })
    authoritative_ids = {approval.artifact_id for approval in authoritative_approvals}
    ungated_publications = sorted(
        str(approval.artifact_id) for approval in approvals
        if isinstance(approval.payload, dict)
        and approval.payload.get("published") is True
        and (
            approval.artifact_id not in authoritative_ids
            or (projected_ids is not None and approval.artifact_id not in projected_ids)
        )
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
        "orphaned_projection_rows": orphaned_projection_rows,
        "projection_drift": projection_drift,
        "permission_label_drift": [],
        "duplicate_active_publications": duplicate_active_publications,
        "missing_required_stages": [],
        "post_approval_blockers": [],
        "malformed_artifact_payloads": malformed_artifact_payloads,
    }
    projection_issues_by_slug: dict[str, set[str]] = {}
    for issue in reconciliation.issues:
        if issue.slug is not None:
            projection_issues_by_slug.setdefault(issue.slug, set()).add(issue.code)

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
                "permissions": {"registry_expected": None, "skill_version": None,
                                "content_review": None, "approval": None,
                                "scan_labels": [], "all_match": False},
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
            if isinstance(version.payload, dict)
            and version.payload.get("slug") == slug and source_hash
            and payload_fingerprint(version.payload) == source_hash
        ]
        selected_version = published_version if current_publication else max(
            exact_versions, key=lambda artifact: (
                artifact.timestamp_start, str(artifact.artifact_id),
            ), default=None,
        )

        if selected_version is not None:
            if current_publication:
                content_state = readiness_for_review(
                    reconciled_store, selected_version, frozen.content_review,
                )
                content_review = frozen.content_review
                security = _security_projection(
                    reconciled_store, selected_version, reviews, artifacts_by_id,
                    preferred=frozen.automated_review,
                )
            else:
                content_state = readiness_for_version(reconciled_store, selected_version)
                content_review = content_state.review
                security = _security_projection(
                    reconciled_store, selected_version, reviews, artifacts_by_id,
                )
        else:
            slug_content = [
                review for review in reviews
                if isinstance(review.payload, dict)
                and review.payload.get("review_kind") == CONTENT_REVIEW_KIND
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

        security_ids = {
            stage["artifact_id"] for stage in security.get("stages", [])
            if stage.get("stage") != 6 and stage.get("artifact_id")
        }
        scan_permission_labels = sorted({
            artifact.permissions_label for artifact in scans
            if str(artifact.artifact_id) in security_ids
        })
        expected_permission = "public"
        permission_values = [
            selected_version.permissions_label if selected_version else None,
            content_review.permissions_label if content_review else None,
            approval.permissions_label if approval else None,
            *scan_permission_labels,
        ]
        present_permissions = [value for value in permission_values if value is not None]
        permission_drift = any(value != expected_permission for value in present_permissions)
        if permission_drift:
            anomalies["permission_label_drift"].append(slug)

        if current_publication:
            later_content = [
                review for review in reviews
                if isinstance(review.payload, dict)
                and review.payload.get("review_kind") == CONTENT_REVIEW_KIND
                and review.payload.get("slug") == slug
                and review.input_refs
                and review.input_refs[0] == published_version.artifact_id
                and review.timestamp_start > approval.timestamp_start
            ]
            if later_content:
                current_lineage = readiness_for_version(reconciled_store, published_version)
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
        if permission_drift:
            blockers.append({"code": "PERMISSION_LABEL_DRIFT", "source": "registry",
                              "artifact_id": None})
        for code in sorted(projection_issues_by_slug.get(slug, set())):
            blockers.append({"code": code, "source": "approval", "artifact_id": None})

        rejected = bool(selected_version and selected_version.artifact_id in active_rejections)
        if rejected:
            blockers.append({"code": "APPROVAL_REJECTED", "source": "approval",
                             "artifact_id": None})
        if publication and not current_publication:
            state = "published_stale"
        elif current_publication:
            state = "published"
        elif slug in projection_issues_by_slug:
            state = "invalid"
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

        finding_ids = sorted(
            finding.finding_id for finding in content_state.effective_findings
        ) if content_state is not None else []
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
            "permissions": {
                "registry_expected": expected_permission,
                "skill_version": selected_version.permissions_label if selected_version else None,
                "content_review": content_review.permissions_label if content_review else None,
                "approval": approval.permissions_label if approval else None,
                "scan_labels": scan_permission_labels,
                "all_match": bool(present_permissions) and not permission_drift,
            },
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
        values[:] = sorted(set(values))
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
                                               "artifact_reconciliation"],
                   "production_identity": {
                       "provider": "entra_oidc",
                       "issuer": expected_entra_issuer if environment == "production" else None,
                       "tenant_id": expected_entra_tenant if environment == "production" else None,
                   }},
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
