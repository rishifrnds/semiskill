"""SemiSkill command centre — a local, dependency-free dashboard server.

Serves `index.html` and a live `/api/state` assembled from real signals:
  * repo      — git history, tracked files, module LOC, test inventory
  * runtime   — read-only Postgres artifact-store liveness
  * verification — immutable, source-bound Python full-suite evidence (non-crediting)
  * scoreboard — validated canonical catalog state (never inferred from fixtures or API visibility)
  * plan      — the curated model in `model.json` (features, risks, launch, GTM)
  * inbox     — actions the user has clicked, appended to `inbox.jsonl`

The dashboard's buttons POST template IDs to `/api/action`, which durably appends one
non-crediting receipt per request. A separate governed worker must validate a receipt before
performing work; browser text and legacy rows are never executable instructions.

Read-mostly by construction: the only mutation path appends or archives task-queue
events under `dashboard/`. Mutation requests cannot invoke command actuators; read-only
state collection may run bounded Git and read-only database observations.

    python dashboard/server.py            # http://127.0.0.1:8899
"""
from __future__ import annotations

import copy
import json
import hashlib
import hmac
import math
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import uuid
import webbrowser
from dataclasses import fields
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INBOX = HERE / "inbox.jsonl"
MODEL = HERE / "model.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dashboard import action_queue                              # noqa: E402
from dashboard.action_queue import (                           # noqa: E402
    ActionQueue,
    QueueError,
    strict_json_loads,
)
from semiskill.authoring.snapshot import (                    # noqa: E402
    SnapshotUnavailable,
    load_progress,
    load_scoreboard_snapshot,
)
from semiskill.artifacts.schema import (                       # noqa: E402
    OBJECTIVE_TAGS,
    PERMISSIONS_LABELS,
    ActorKind,
    Artifact,
    ArtifactType,
    SourceSystem,
)
from semiskill.verification.evidence import (                  # noqa: E402
    FullSuiteEvidenceUnavailable,
    read_latest_run,
    validate_counts,
)

PORT = int(os.environ.get("SEMISKILL_DASHBOARD_PORT", "8899"))

_DEFAULT_SCOREBOARD_MAX_AGE_SECONDS = 900
_DEFAULT_PROGRESS_MAX_AGE_SECONDS = 300
_DEFAULT_FULL_SUITE_MAX_AGE_SECONDS = 86_400
_MAX_FULL_SUITE_AGE_SECONDS = 604_800
_MAX_FUTURE_SKEW_SECONDS = 60
_MIGRATION_NAME = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")
_CANONICAL_SOURCE_PATHS = {
    "registry": "specs/skill_registry.json",
    "skills": "skills",
}
_CANONICAL_SCOPE = {
    "phase": "dv-84",
    "expected_active": 84,
    "expected_declined": 20,
    "expected_roles": 16,
    "target_per_role": 5,
}
_ADOPTION_0015_ATTESTATION_KEYS = frozenset({
    "required_relations_present",
    "required_functions_present",
    "critical_projection_index_exact",
    "authority_triggers_exact",
    "capability_roles_hardened",
    "capability_memberships_exact",
    "security_definer_paths_hardened",
    "direct_table_boundary_exact",
    "function_boundary_exact",
    "projection_and_policy_start_empty",
    "public_schema_create_revoked",
})
_CHECKPOINT_0015_ATTESTATION_KEYS = _ADOPTION_0015_ATTESTATION_KEYS | {
    "held_out_seed_exact",
    "judge_gold_set_empty",
    "registry_rows_exact",
    "schema_inventory_exact",
}
_POST_MIGRATION_ATTESTATION_KEYS = _ADOPTION_0015_ATTESTATION_KEYS | {
    "held_out_baseline_intact",
    "review_root_index_exact",
    "registry_rows_exact",
    "schema_inventory_exact",
}
_CURRENT_SCHEMA_ATTESTATION_KEYS = (
    _POST_MIGRATION_ATTESTATION_KEYS - {"projection_and_policy_start_empty"}
)
_FORWARD_EVIDENCE_SCHEMA = "migration-forward-execution/v1"
_FORWARD_AUDIT_NAMESPACE = uuid.UUID("e79d5d73-8b2a-5a8a-8c9d-6b25c86cb77b")
_MAX_ACTION_BODY_BYTES = 16_384
_MAX_DRAIN_SECONDS = 0.25       # best-effort drain budget; see Handler._drain_unread_body
_JSON_CONTENT_TYPE = re.compile(
    r'^application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$',
    re.IGNORECASE,
)
_INVALID_BODY = object()
_FULL_SUITE_SCOPE = {
    "kind": "python-full-suite",
    "test_root": "tests",
    "selection": "all",
    "execution": "serial",
    "database_environment": "test",
    "credit": "none",
}


class DashboardSnapshotRejected(RuntimeError):
    """Controlled fail-closed reason; raw source/database exceptions never cross the API."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class OperationalProbeUnavailable(RuntimeError):
    """Expected operational-source failure with a closed, non-secret reason code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_OPERATIONAL_OBSERVATION_KEYS = {
    "status", "reason", "observed_at", "identity", "scope", "freshness", "data",
}


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _unavailable_observation(reason: str, *, observed_at: str | None = None) -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "observed_at": observed_at or _now(),
        "identity": None,
        "scope": None,
        "freshness": None,
        "data": None,
    }


def _available_observation(
    *, identity: dict, scope: dict, data: dict, observed_at: str | None = None,
    freshness: dict | None = None, status: str = "available", reason: str | None = None,
) -> dict:
    return {
        "status": status,
        "reason": reason,
        "observed_at": observed_at or _now(),
        "identity": identity,
        "scope": scope,
        "freshness": freshness or {
            "status": "fresh", "age_seconds": 0, "max_age_seconds": None,
        },
        "data": data,
    }


def _validated_observation(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != _OPERATIONAL_OBSERVATION_KEYS:
        raise ValueError("invalid operational observation")
    status = value.get("status")
    if status not in {"available", "stale", "unavailable"}:
        raise ValueError("invalid operational status")
    observed = _timestamp(value.get("observed_at"))
    source_age = (_timestamp(_now()) - observed).total_seconds()
    if source_age < -_MAX_FUTURE_SKEW_SECONDS or source_age > 60:
        raise ValueError("operational observation is not current")
    if status == "unavailable":
        if not isinstance(value.get("reason"), str) or not value["reason"]:
            raise ValueError("unavailable reason missing")
        if any(value.get(key) is not None for key in ("identity", "scope", "freshness", "data")):
            raise ValueError("unavailable observation contains data")
        return value
    if not all(isinstance(value.get(key), dict) for key in ("identity", "scope", "freshness", "data")):
        raise ValueError("available observation metadata missing")
    if status == "available" and value.get("reason") is not None:
        raise ValueError("available observation has reason")
    if status == "stale" and (not isinstance(value.get("reason"), str) or not value["reason"]):
        raise ValueError("stale observation reason missing")
    expected_freshness = "fresh" if status == "available" else "stale"
    freshness = value["freshness"]
    if set(freshness) != {"status", "age_seconds", "max_age_seconds"}:
        raise ValueError("freshness shape mismatch")
    age_seconds, max_age_seconds = freshness["age_seconds"], freshness["max_age_seconds"]
    if (
        freshness.get("status") != expected_freshness
        or isinstance(age_seconds, bool) or not isinstance(age_seconds, int) or age_seconds < 0
        or (
            max_age_seconds is not None
            and (isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int)
                 or max_age_seconds < 15)
        )
        or (status == "stale" and (max_age_seconds is None or age_seconds <= max_age_seconds))
        or (status == "available" and max_age_seconds is not None and age_seconds > max_age_seconds)
    ):
        raise ValueError("freshness status mismatch")
    return value


def _valid_object_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is not None


def _validate_repo_observation(value: dict) -> None:
    if value["status"] == "unavailable":
        return
    identity, scope, data = value["identity"], value["scope"], value["data"]
    if (
        set(identity) != {"root", "commit", "tree", "inventory_sha256"}
        or identity.get("root") != ROOT.resolve().as_posix()
        or not _valid_object_id(identity.get("commit")) or not _valid_object_id(identity.get("tree"))
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(identity.get("inventory_sha256", ""))) is None
        or scope != {
            "history_limit": 80, "module_root": "semiskill", "test_root": "tests",
            "test_glob": "test_*.py", "test_count_kind": "static_function_definitions",
        }
    ):
        raise ValueError("invalid repository identity")
    required = {
        "commits", "branch", "dirty", "dirty_files", "dirty_files_truncated",
        "modules", "tests", "total_tests", "total_loc",
    }
    if (
        set(data) != required or not isinstance(data["branch"], str) or not data["branch"]
        or not data["commits"] or not data["modules"] or not data["tests"]
    ):
        raise ValueError("invalid repository data")
    for key in ("dirty", "total_tests", "total_loc"):
        if isinstance(data[key], bool) or not isinstance(data[key], int) or data[key] < 0:
            raise ValueError("invalid repository count")
    if not all(isinstance(data[key], list) for key in ("commits", "dirty_files", "modules", "tests")):
        raise ValueError("invalid repository collection")
    if (
        not isinstance(data["dirty_files_truncated"], bool)
        or len(data["dirty_files"]) != min(data["dirty"], 20)
        or data["dirty_files_truncated"] != (data["dirty"] > 20)
    ):
        raise ValueError("invalid repository dirty state")
    if (
        not all(isinstance(item, str) and item for item in data["dirty_files"])
        or not all(
            isinstance(item, dict) and set(item) == {"sha", "date", "subject", "kind", "phase"}
            and isinstance(item["sha"], str) and isinstance(item["date"], str)
            and isinstance(item["subject"], str) and isinstance(item["kind"], str)
            and isinstance(item["phase"], str)
            for item in data["commits"]
        )
        or not all(
            isinstance(item, dict) and set(item) == {"path", "count", "group"}
            and isinstance(item["path"], str) and isinstance(item["group"], str)
            and not isinstance(item["count"], bool) and isinstance(item["count"], int)
            and item["count"] > 0
            for item in data["tests"]
        )
        or not all(
            isinstance(item, dict) and set(item) == {"path", "loc", "layer"}
            and isinstance(item["path"], str) and isinstance(item["layer"], str)
            and not isinstance(item["loc"], bool) and isinstance(item["loc"], int)
            and item["loc"] > 0
            for item in data["modules"]
        )
    ):
        raise ValueError("invalid repository inventory row")
    if sum(item.get("count", -1) for item in data["tests"]) != data["total_tests"]:
        raise ValueError("invalid repository test total")
    if sum(item.get("loc", -1) for item in data["modules"]) != data["total_loc"]:
        raise ValueError("invalid repository LOC total")
    for item in data["commits"]:
        if (
            re.fullmatch(r"[0-9a-f]{4,64}", item["sha"]) is None
            or item["kind"] not in {"wip", "feat", "rotate"}
            or (item["phase"] and re.fullmatch(r"[A-Z0-9-]+", item["phase"]) is None)
        ):
            raise ValueError("invalid repository commit row")
        _timestamp(item["date"])
    for item in data["tests"]:
        path = PurePosixPath(item["path"])
        if (
            path.is_absolute() or ".." in path.parts or not item["path"].startswith("tests/")
            or not item["group"]
        ):
            raise ValueError("invalid repository test row")
    for item in data["modules"]:
        path = PurePosixPath(item["path"])
        if (
            path.is_absolute() or ".." in path.parts or not item["path"].startswith("semiskill/")
            or item["layer"] not in {"L1", "L2", "L3", "L4", "L5", "L6", "core"}
        ):
            raise ValueError("invalid repository module row")


def _validate_state_observation(value: dict, *, repository_commit: str | None = None) -> None:
    if value["status"] == "unavailable":
        return
    identity, scope, data = value["identity"], value["scope"], value["data"]
    files = identity.get("files")
    if (
        set(identity) != {"repository_commit", "files"}
        or not _valid_object_id(identity.get("repository_commit"))
        or (repository_commit is not None and identity.get("repository_commit") != repository_commit)
        or scope != {
            "required_files": ["STATUS.md", "MEMORY.md", "BLOCKERS.md"],
            "parser": "project-state/v1",
        }
        or not isinstance(files, list) or len(files) != 3
        or {item.get("path") for item in files if isinstance(item, dict)}
        != {"STATUS.md", "MEMORY.md", "BLOCKERS.md"}
        or any(
            not isinstance(item, dict) or set(item) != {"path", "sha256"}
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(item.get("sha256", ""))) is None
            for item in files
        )
    ):
        raise ValueError("invalid state identity")
    blockers = data.get("blockers")
    if (
        set(data) != {
            "phase", "active_step", "right_now", "gaps", "steps", "blockers",
            "blocker_count", "status_updated_at",
        }
        or not isinstance(data.get("phase"), str) or not data["phase"]
        or not isinstance(data.get("active_step"), str) or not data["active_step"]
        or data.get("right_now") != data.get("active_step")
        or not isinstance(data.get("gaps"), list) or not isinstance(data.get("steps"), list)
        or not isinstance(blockers, list) or isinstance(data.get("blocker_count"), bool)
        or data.get("blocker_count") != len(blockers)
    ):
        raise ValueError("invalid project state")
    blocker_ids = []
    for blocker in blockers:
        if (
            not isinstance(blocker, dict) or set(blocker) != {"id", "title"}
            or re.fullmatch(r"BLK-\d{3}", str(blocker.get("id", ""))) is None
            or not isinstance(blocker.get("title"), str) or not blocker["title"]
        ):
            raise ValueError("invalid blocker row")
        blocker_ids.append(blocker["id"])
    if len(set(blocker_ids)) != len(blocker_ids):
        raise ValueError("duplicate blocker row")
    if not all(isinstance(item, str) and item for item in data["gaps"]):
        raise ValueError("invalid state gap")
    for step in data["steps"]:
        if (
            not isinstance(step, dict) or set(step) != {"id", "ts", "status", "what"}
            or not all(isinstance(step.get(key), str) and step[key]
                       for key in ("id", "ts", "status", "what"))
        ):
            raise ValueError("invalid state step")
        _timestamp(step["ts"])
    updated = _timestamp(data.get("status_updated_at"))
    actual_age = int((_timestamp(_now()) - updated).total_seconds())
    if actual_age < -_MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("invalid state timestamp")
    if abs(max(0, actual_age) - value["freshness"]["age_seconds"]) > 2:
        raise ValueError("state freshness is detached from status timestamp")


def _validate_adr_observation(value: dict, *, repository_commit: str | None = None) -> None:
    if value["status"] == "unavailable":
        return
    identity, scope, data = value["identity"], value["scope"], value["data"]
    items = data.get("items")
    if (
        set(identity) != {"repository_commit", "path", "sha256"}
        or not _valid_object_id(identity.get("repository_commit"))
        or (repository_commit is not None and identity.get("repository_commit") != repository_commit)
        or identity.get("path") != "DECISIONS.md"
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(identity.get("sha256", ""))) is None
        or scope != {"parser": "adr-heading/v1", "heading": "## [ADR-NNN] title"}
        or set(data) != {"items", "count"} or not isinstance(items, list) or not items
        or isinstance(data.get("count"), bool) or data.get("count") != len(items)
    ):
        raise ValueError("invalid ADR observation")
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    numbers = [int(item.split("-", 1)[1]) for item in ids
               if isinstance(item, str) and re.fullmatch(r"ADR-\d{3}", item)]
    if (
        len(ids) != len(items) or len(set(ids)) != len(ids) or len(numbers) != len(ids)
        or numbers != sorted(numbers)
        or any(
            set(item) != {"id", "title"} or not isinstance(item.get("title"), str)
            or not item["title"]
            for item in items if isinstance(item, dict)
        )
    ):
        raise ValueError("invalid ADR items")


def _full_suite_max_age_seconds() -> int:
    raw = os.environ.get(
        "SEMISKILL_FULL_SUITE_MAX_AGE_SECONDS", str(_DEFAULT_FULL_SUITE_MAX_AGE_SECONDS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise OperationalProbeUnavailable("freshness_configuration_invalid") from exc
    if not 15 <= value <= _MAX_FULL_SUITE_AGE_SECONDS:
        raise OperationalProbeUnavailable("freshness_configuration_invalid")
    return value


def _validate_full_suite_observation(value: dict, *, repository: dict | None = None) -> None:
    if value["status"] == "unavailable":
        return
    identity, scope, data = value["identity"], value["scope"], value["data"]
    if (
        not isinstance(identity, dict)
        or set(identity) != {
            "run_id", "run_sha256", "source_commit", "source_tree",
            "database_identity_sha256",
        }
        or not isinstance(scope, dict) or scope != _FULL_SUITE_SCOPE
        or not isinstance(data, dict)
        or set(data) != {
            "verdict", "started_at", "ended_at", "duration_seconds", "exit_code",
            "result_complete", "failure_reason", "counts", "database", "artifact",
        }
    ):
        raise ValueError("invalid full-suite observation")
    try:
        if str(uuid.UUID(identity["run_id"])) != identity["run_id"]:
            raise ValueError("invalid full-suite run identity")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid full-suite run identity") from exc
    digest = r"sha256:[0-9a-f]{64}"
    if (
        re.fullmatch(digest, str(identity.get("run_sha256", ""))) is None
        or not _valid_object_id(identity.get("source_commit"))
        or not _valid_object_id(identity.get("source_tree"))
        or len(identity["source_commit"]) != len(identity["source_tree"])
        or re.fullmatch(digest, str(identity.get("database_identity_sha256", ""))) is None
    ):
        raise ValueError("invalid full-suite identity")
    started, ended = _timestamp(data.get("started_at")), _timestamp(data.get("ended_at"))
    duration = data.get("duration_seconds")
    exit_code = data.get("exit_code")
    if (
        ended < started
        or not isinstance(duration, (int, float)) or isinstance(duration, bool)
        or not math.isfinite(duration) or duration < 0
        or not isinstance(exit_code, int) or isinstance(exit_code, bool)
        or not 0 <= exit_code <= 255
        or not isinstance(data.get("result_complete"), bool)
    ):
        raise ValueError("invalid full-suite result")
    failure_reason = data.get("failure_reason")
    if (
        (data["result_complete"] and failure_reason is not None)
        or (
            not data["result_complete"]
            and (not isinstance(failure_reason, str) or not re.fullmatch(r"[a-z0-9_]{1,80}", failure_reason))
        )
    ):
        raise ValueError("invalid full-suite result")
    counts = validate_counts(data.get("counts"))
    should_pass = (
        data["result_complete"] and exit_code == 0 and counts["collected"] > 0
        and counts["failed"] == 0 and counts["errors"] == 0 and counts["not_run"] == 0
        and counts["collection_errors"] == 0 and counts["deselected"] == 0
    )
    if data.get("verdict") not in {"pass", "fail"} or (data["verdict"] == "pass") != should_pass:
        raise ValueError("invalid full-suite verdict")
    database = data.get("database")
    if (
        not isinstance(database, dict)
        or set(database) != {
            "engine", "environment", "database_name", "identity_sha256",
            "session_user_sha256",
        }
        or database.get("engine") != "postgresql" or database.get("environment") != "test"
        or not isinstance(database.get("database_name"), str)
        or re.fullmatch(r"[a-z][a-z0-9_]*_test", database["database_name"]) is None
        or re.fullmatch(digest, str(database.get("identity_sha256", ""))) is None
        or re.fullmatch(digest, str(database.get("session_user_sha256", ""))) is None
        or database["identity_sha256"] != identity["database_identity_sha256"]
    ):
        raise ValueError("invalid full-suite database")
    artifact = data.get("artifact")
    run_id = identity["run_id"]
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"run_ref", "run_sha256", "output_ref", "output_sha256"}
        or artifact.get("run_ref") != f"dashboard/runs/full-suite/runs/{run_id}.json"
        or artifact.get("run_sha256") != identity["run_sha256"]
        or artifact.get("output_ref") != f"dashboard/runs/full-suite/outputs/{run_id}.log"
        or re.fullmatch(digest, str(artifact.get("output_sha256", ""))) is None
    ):
        raise ValueError("invalid full-suite artifact")
    now = _timestamp(value["observed_at"])
    raw_age_seconds = (now - ended).total_seconds()
    if raw_age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("invalid full-suite timestamp")
    age_seconds = math.ceil(max(0, raw_age_seconds))
    if abs(max(0, age_seconds) - value["freshness"]["age_seconds"]) > 2:
        raise ValueError("full-suite freshness detached")
    if value["freshness"]["max_age_seconds"] != _full_suite_max_age_seconds():
        raise ValueError("full-suite freshness configuration detached")
    if value["status"] == "stale" and value.get("reason") != "full_suite_expired":
        raise ValueError("invalid full-suite stale reason")
    if repository is not None:
        repo_identity = repository.get("identity") if isinstance(repository, dict) else None
        repo_data = repository.get("data") if isinstance(repository, dict) else None
        if (
            not isinstance(repository, dict) or repository.get("status") != "available"
            or not isinstance(repo_identity, dict) or not isinstance(repo_data, dict)
            or repo_data.get("dirty") != 0
            or repo_identity.get("commit") != identity["source_commit"]
            or repo_identity.get("tree") != identity["source_tree"]
        ):
            raise ValueError("full-suite repository binding invalid")


def _collect_observation(collector, validator=None) -> dict:
    try:
        value = _validated_observation(collector())
        if validator is not None:
            validator(value)
        return value
    except OperationalProbeUnavailable as exc:
        return _unavailable_observation(exc.reason)
    except Exception:  # noqa: BLE001 - one bad source must not hide the verified scoreboard
        return _unavailable_observation("probe_unavailable")


def _sh(args: list[str], timeout: int = 20) -> tuple[int, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("GIT_"):
            environment.pop(key, None)
    environment.update(
        GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
    )
    command = args
    if args and args[0] == "git":
        command = ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *args[1:]]
    try:
        p = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as e:                                   # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise DashboardSnapshotRejected("clock_skew") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DashboardSnapshotRejected("clock_skew")
    return parsed.astimezone(timezone.utc)


def _max_age_seconds(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise DashboardSnapshotRejected("freshness_configuration_invalid") from exc
    if not 15 <= value <= 3_600:
        raise DashboardSnapshotRejected("freshness_configuration_invalid")
    return value


def _freshness_validation(*, generated_at: str, observed_at: str, kind: str) -> dict:
    generated = _timestamp(generated_at)
    observed = _timestamp(observed_at)
    age = (observed - generated).total_seconds()
    if age < -_MAX_FUTURE_SKEW_SECONDS:
        raise DashboardSnapshotRejected("clock_skew" if kind == "snapshot" else "progress_clock_skew")
    env_name = (
        "SEMISKILL_SCOREBOARD_MAX_AGE_SECONDS"
        if kind == "snapshot" else "SEMISKILL_PROGRESS_MAX_AGE_SECONDS"
    )
    default = (
        _DEFAULT_SCOREBOARD_MAX_AGE_SECONDS
        if kind == "snapshot" else _DEFAULT_PROGRESS_MAX_AGE_SECONDS
    )
    maximum = _max_age_seconds(env_name, default)
    if age > maximum:
        raise DashboardSnapshotRejected("snapshot_expired" if kind == "snapshot" else "progress_expired")
    return {"age_seconds": max(0, int(age)), "max_age_seconds": maximum}


def _repository_identity() -> tuple[str, bool]:
    rc, commit = _sh(["git", "rev-parse", "HEAD"])
    if rc != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit.strip()):
        raise DashboardSnapshotRejected("source_unavailable")
    rc, status = _sh(["git", "status", "--porcelain", "--untracked-files=normal"])
    if rc != 0:
        raise DashboardSnapshotRejected("source_unavailable")
    return commit.strip(), bool(status.strip())


def _safe_source_path(value: object, *, kind: str) -> Path:
    expected = _CANONICAL_SOURCE_PATHS.get(kind)
    if not isinstance(value, str) or value != expected or "\\" in value:
        raise DashboardSnapshotRejected(f"{kind}_path_invalid")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise DashboardSnapshotRejected(f"{kind}_path_invalid")
    try:
        target = (ROOT / Path(*relative.parts)).resolve(strict=True)
    except OSError as exc:
        raise DashboardSnapshotRejected(f"{kind}_path_invalid") from exc
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise DashboardSnapshotRejected(f"{kind}_path_invalid") from exc
    candidate = ROOT
    for part in relative.parts:
        candidate = candidate / part
        try:
            stat = candidate.lstat()
        except OSError as exc:
            raise DashboardSnapshotRejected(f"{kind}_path_invalid") from exc
        if candidate.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & 0x400):
            raise DashboardSnapshotRejected(f"{kind}_path_invalid")
    if kind == "registry" and not target.is_file():
        raise DashboardSnapshotRejected("registry_path_invalid")
    if kind == "skills" and not target.is_dir():
        raise DashboardSnapshotRejected("skills_path_invalid")
    return target


def _validate_dashboard_scope(snapshot: dict) -> None:
    scope = snapshot.get("scope")
    if not isinstance(scope, dict) or any(
        scope.get(key) != expected for key, expected in _CANONICAL_SCOPE.items()
    ):
        raise DashboardSnapshotRejected("scope_mismatch")


def _rebuild_snapshot(snapshot: dict, registry_path: Path, skills_root: Path) -> dict:
    try:
        from semiskill.artifacts.store import PostgresArtifactStore  # noqa: PLC0415
        from semiskill.authoring.snapshot import build_scoreboard_snapshot  # noqa: PLC0415
        from semiskill.config import Config  # noqa: PLC0415

        environment = snapshot["sources"]["database"]["environment"]
        return build_scoreboard_snapshot(
            store=PostgresArtifactStore(Config.from_env().database_url),
            registry_path=registry_path,
            skills_root=skills_root,
            generated_at=snapshot["generated_at"],
            expected_active=_CANONICAL_SCOPE["expected_active"],
            expected_declined=_CANONICAL_SCOPE["expected_declined"],
            expected_roles=_CANONICAL_SCOPE["expected_roles"],
            target_per_role=_CANONICAL_SCOPE["target_per_role"],
            environment=environment,
            repository_root=ROOT,
            phase=_CANONICAL_SCOPE["phase"],
            expected_entra_issuer=os.environ.get("SEMISKILL_ENTRA_ISSUER"),
            expected_entra_tenant=os.environ.get("SEMISKILL_ENTRA_TENANT_ID"),
        )
    except DashboardSnapshotRejected:
        raise
    except Exception as exc:  # database/parser details remain local
        raise DashboardSnapshotRejected("database_unavailable") from exc


def _live_snapshot_validation(snapshot: dict, *, migration: dict | None = None) -> dict:
    _validate_dashboard_scope(snapshot)
    sources = snapshot["sources"]
    repository = sources["repository"]
    if repository.get("dirty") is not False:
        raise DashboardSnapshotRejected("snapshot_source_dirty")
    current_commit, current_dirty = _repository_identity()
    if current_commit != repository.get("commit"):
        raise DashboardSnapshotRejected("source_commit_mismatch")
    if current_dirty:
        raise DashboardSnapshotRejected("working_tree_dirty")

    registry_source = sources.get("registry")
    skills_source = sources.get("skills")
    if not isinstance(registry_source, dict) or not isinstance(skills_source, dict):
        raise DashboardSnapshotRejected("source_path_invalid")
    registry_path = _safe_source_path(registry_source.get("path"), kind="registry")
    skills_root = _safe_source_path(skills_source.get("root"), kind="skills")
    try:
        registry_sha256 = "sha256:" + hashlib.sha256(registry_path.read_bytes()).hexdigest()
        from semiskill.authoring.export_scope import _skills_tree_sha256  # noqa: PLC0415
        from semiskill.authoring.snapshot import full_input_tree_sha256  # noqa: PLC0415
        skills_sha256 = _skills_tree_sha256(skills_root)
        full_skills_sha256 = full_input_tree_sha256(skills_root)
    except Exception as exc:
        raise DashboardSnapshotRejected("skills_tree_mismatch") from exc
    if registry_sha256 != registry_source.get("sha256"):
        raise DashboardSnapshotRejected("registry_hash_mismatch")
    if skills_sha256 != skills_source.get("tree_sha256"):
        raise DashboardSnapshotRejected("skills_tree_mismatch")
    if full_skills_sha256 != skills_source.get("full_tree_sha256"):
        raise DashboardSnapshotRejected("skills_full_tree_mismatch")

    live = _rebuild_snapshot(snapshot, registry_path, skills_root)
    if live["sources"]["registry"]["sha256"] != registry_source["sha256"]:
        raise DashboardSnapshotRejected("registry_hash_mismatch")
    if live["sources"]["skills"]["tree_sha256"] != skills_source["tree_sha256"]:
        raise DashboardSnapshotRejected("skills_tree_mismatch")
    if live["sources"]["skills"]["full_tree_sha256"] != skills_source["full_tree_sha256"]:
        raise DashboardSnapshotRejected("skills_full_tree_mismatch")
    if live["sources"]["database"] != sources["database"]:
        raise DashboardSnapshotRejected("database_identity_mismatch")
    if live["snapshot_id"] != snapshot["snapshot_id"]:
        raise DashboardSnapshotRejected("database_state_mismatch")
    migration = migration if migration is not None else migration_witness_signal()
    if migration.get("status") != "verified":
        raise DashboardSnapshotRejected("schema_witness_mismatch")
    migration_database = migration.get("database")
    migration_tracker = migration.get("tracker")
    if (
        not isinstance(migration_database, dict)
        or not isinstance(migration_tracker, dict)
        or migration_database.get("environment") != sources["database"]["environment"]
        or migration_database.get("database_name") != sources["database"]["database_name"]
        or migration_tracker.get("exact") is not True
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(migration_tracker.get("sha256"))
        ) is None
        or migration.get("schema", {}).get("status") != "verified"
    ):
        raise DashboardSnapshotRejected("schema_witness_mismatch")
    adoption = migration.get("adoption")
    forward = migration.get("forward")
    authority_chain = migration.get("authority_chain")
    if (
        not isinstance(adoption, dict)
        or not isinstance(forward, dict)
        or not isinstance(authority_chain, dict)
        or forward.get("prior_artifact_id") != adoption.get("artifact_id")
        or authority_chain != _migration_authority_chain_projection(
            adoption, forward, migration_tracker["sha256"],
        )
    ):
        raise DashboardSnapshotRejected("migration_authority_chain_invalid")
    final_commit, final_dirty = _repository_identity()
    if final_commit != current_commit or final_dirty or final_dirty != current_dirty:
        raise DashboardSnapshotRejected("source_changed_during_validation")
    return {
        "status": "verified",
        "snapshot_id": live["snapshot_id"],
        "source_commit": current_commit,
        "database_identity_sha256": live["sources"]["database"]["identity_sha256"],
        "migration_tracker_sha256": migration_tracker["sha256"],
        "migration_adoption_artifact_id": adoption["artifact_id"],
        "migration_forward_artifact_id": forward["artifact_id"],
        "migration_authority_chain_sha256": authority_chain["sha256"],
    }


# ---------------------------------------------------------------- signals

def _required_git(args: list[str]) -> str:
    rc, output = _sh(["git", *args])
    if rc != 0:
        raise OperationalProbeUnavailable("git_unavailable")
    return output


def _read_inventory_file(path: Path) -> tuple[str, str]:
    if path.is_symlink() or not path.is_file():
        raise OperationalProbeUnavailable("source_inventory_unavailable")
    try:
        path.resolve().relative_to(ROOT.resolve())
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise OperationalProbeUnavailable("source_inventory_unavailable") from exc
    return text, _sha256_bytes(raw)


def repo_signals() -> dict:
    observed_at = _now()
    try:
        top_level = _required_git(["rev-parse", "--show-toplevel"]).strip()
        if not top_level or Path(top_level).resolve() != ROOT.resolve():
            raise OperationalProbeUnavailable("repository_identity_mismatch")
        commit = _required_git(["rev-parse", "HEAD"]).strip().lower()
        tree = _required_git(["rev-parse", "HEAD^{tree}"]).strip().lower()
        object_id = r"[0-9a-f]{40}|[0-9a-f]{64}"
        if not re.fullmatch(object_id, commit) or not re.fullmatch(object_id, tree):
            raise OperationalProbeUnavailable("repository_identity_invalid")
        log = _required_git(["log", "--format=%h|%aI|%s", "-n", "80"])
        status = _required_git(["status", "--porcelain=v1", "--untracked-files=all"])
        branch = _required_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if not branch:
            raise OperationalProbeUnavailable("repository_identity_invalid")

        commits = []
        for line in log.splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3 or not parts[0] or not parts[1]:
                raise OperationalProbeUnavailable("git_history_invalid")
            sha, iso, subject = parts
            _timestamp(iso)
            kind = "rotate" if subject.startswith("rotate:") else (
                "feat" if subject.startswith(("feat:", "fix:")) else "wip")
            phase = ""
            match = re.search(r"\b([A-G]|P0|G)-(\d{3})\b", subject)
            if match:
                phase = match.group(1)
            commits.append({
                "sha": sha, "date": iso, "subject": subject, "kind": kind, "phase": phase,
            })
        if not commits:
            raise OperationalProbeUnavailable("git_history_invalid")

        module_root = ROOT / "semiskill"
        test_root = ROOT / "tests"
        if not module_root.is_dir() or not test_root.is_dir():
            raise OperationalProbeUnavailable("source_inventory_unavailable")
        modules, tests, inventory = [], [], []
        for path in sorted(module_root.rglob("*.py")):
            text, digest = _read_inventory_file(path)
            relative = path.relative_to(ROOT).as_posix()
            inventory.append({"path": relative, "sha256": digest})
            loc = len(text.splitlines())
            if loc:
                modules.append({"path": relative, "loc": loc, "layer": _layer_of(relative)})
        test_re = re.compile(r"^\s*(?:async\s+)?def\s+test_", re.M)
        for path in sorted(test_root.rglob("test_*.py")):
            text, digest = _read_inventory_file(path)
            relative = path.relative_to(ROOT).as_posix()
            inventory.append({"path": relative, "sha256": digest})
            count = len(test_re.findall(text))
            if count:
                parts = relative.split("/")
                tests.append({
                    "path": relative, "count": count,
                    "group": parts[1] if len(parts) > 2 else "root",
                })
        if not modules or not tests:
            raise OperationalProbeUnavailable("source_inventory_unavailable")
        final_commit = _required_git(["rev-parse", "HEAD"]).strip().lower()
        final_tree = _required_git(["rev-parse", "HEAD^{tree}"]).strip().lower()
        final_status = _required_git(
            ["status", "--porcelain=v1", "--untracked-files=all"]
        )
        final_branch = _required_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if (
            final_commit != commit or final_tree != tree or final_status != status
            or final_branch != branch
        ):
            raise OperationalProbeUnavailable("source_changed_during_observation")
        dirty_files = [line for line in status.splitlines() if line.strip()]
        return _available_observation(
            observed_at=observed_at,
            identity={
                "root": ROOT.resolve().as_posix(),
                "commit": commit,
                "tree": tree,
                "inventory_sha256": _canonical_sha256(inventory),
            },
            scope={
                "history_limit": 80,
                "module_root": "semiskill",
                "test_root": "tests",
                "test_glob": "test_*.py",
                "test_count_kind": "static_function_definitions",
            },
            data={
                "commits": commits,
                "branch": branch,
                "dirty": len(dirty_files),
                "dirty_files": dirty_files[:20],
                "dirty_files_truncated": len(dirty_files) > 20,
                "modules": modules,
                "tests": tests,
                "total_tests": sum(item["count"] for item in tests),
                "total_loc": sum(item["loc"] for item in modules),
            },
        )
    except OperationalProbeUnavailable as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except Exception:  # noqa: BLE001
        return _unavailable_observation("source_inventory_unavailable", observed_at=observed_at)


_LAYER_MAP = [
    ("semiskill/capture", "L1"), ("semiskill/cli.py", "L1"),
    ("semiskill/artifacts", "L2"), ("semiskill/spine", "L2"),
    ("semiskill/context", "L3"), ("semiskill/api.py", "L3"),
    ("semiskill/governance", "L4"),
    ("semiskill/intelligence", "L5"),
    ("semiskill/scanners", "L6"), ("semiskill/sensor", "L6"),
    ("semiskill/redteam", "L6"),
]


def _layer_of(path: str) -> str:
    for prefix, layer in _LAYER_MAP:
        if path.startswith(prefix):
            return layer
    return "core"


def _markdown_section(value: str, heading: str) -> str | None:
    matches = re.findall(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", value, flags=re.M | re.S,
    )
    if len(matches) != 1 or not matches[0].strip():
        return None
    return matches[0].strip()


def _repository_commit(repository: dict | None) -> str | None:
    if not isinstance(repository, dict) or repository.get("status") != "available":
        return None
    identity = repository.get("identity")
    commit = identity.get("commit") if isinstance(identity, dict) else None
    return commit if isinstance(commit, str) else None


def state_files(*, repository: dict | None = None) -> dict:
    observed_at = _now()
    commit = _repository_commit(repository)
    if commit is None:
        return _unavailable_observation("repository_unavailable", observed_at=observed_at)
    try:
        contents, file_identity = {}, []
        for name in ("STATUS.md", "MEMORY.md", "BLOCKERS.md"):
            path = ROOT / name
            if path.is_symlink() or not path.is_file():
                raise OperationalProbeUnavailable("required_file_unavailable")
            raw = path.read_bytes()
            contents[name] = raw.decode("utf-8", errors="strict")
            file_identity.append({"path": name, "sha256": _sha256_bytes(raw)})

        status = contents["STATUS.md"]
        memory = contents["MEMORY.md"]
        phase = _markdown_section(memory, "Current Phase")
        active_step = _markdown_section(status, "Active step")
        updated_matches = re.findall(r"^_Last updated:\s*([^_]+)_\r?$", status, re.M)
        if phase is None or active_step is None or len(updated_matches) != 1:
            raise OperationalProbeUnavailable("state_contract_invalid")
        status_updated_at = updated_matches[0].strip()
        now = _timestamp(observed_at)
        updated = _timestamp(status_updated_at)
        age_seconds = int((now - updated).total_seconds())
        if age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
            raise OperationalProbeUnavailable("state_clock_skew")
        age_seconds = max(0, age_seconds)
        max_age_seconds = _max_age_seconds("SEMISKILL_STATE_MAX_AGE_SECONDS", 900)

        steps = re.findall(
            r"^- \[([^\]]+)\]\s+(\S+)\s+status:\s*(\w+)\s*\n\s+what:\s*(.+)$",
            memory,
            re.M,
        )
        live_blockers = re.sub(r"<!--.*?-->", "", contents["BLOCKERS.md"], flags=re.S)
        candidate_lines = [
            line.strip() for line in live_blockers.splitlines()
            if re.match(r"^#{1,6}\s+\[BLK", line.strip())
        ]
        parsed_blockers = []
        blocker_ids = set()
        for line in candidate_lines:
            match = re.fullmatch(r"## \[(BLK-\d{3})\]\s+(.+)", line)
            if match is None or match.group(1) in blocker_ids:
                raise OperationalProbeUnavailable("blocker_register_invalid")
            blocker_ids.add(match.group(1))
            parsed_blockers.append({"id": match.group(1), "title": match.group(2).strip()})
        data = {
            "phase": phase,
            "active_step": active_step,
            "right_now": active_step,
            "gaps": re.findall(
                r"^- (Stage.+|pgvector.+|SharePoint.+|Phase G.+)$", status, re.M,
            ),
            "steps": [
                {"id": item_id, "ts": timestamp, "status": step_status, "what": what}
                for item_id, timestamp, step_status, what in steps
            ],
            "blockers": parsed_blockers,
            "blocker_count": len(parsed_blockers),
            "status_updated_at": status_updated_at,
        }
        freshness = {
            "status": "fresh" if age_seconds <= max_age_seconds else "stale",
            "age_seconds": age_seconds,
            "max_age_seconds": max_age_seconds,
        }
        return _available_observation(
            observed_at=observed_at,
            identity={"repository_commit": commit, "files": file_identity},
            scope={
                "required_files": ["STATUS.md", "MEMORY.md", "BLOCKERS.md"],
                "parser": "project-state/v1",
            },
            data=data,
            freshness=freshness,
            status="available" if freshness["status"] == "fresh" else "stale",
            reason=None if freshness["status"] == "fresh" else "status_expired",
        )
    except OperationalProbeUnavailable as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except DashboardSnapshotRejected as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except (OSError, UnicodeDecodeError):
        return _unavailable_observation("required_file_unavailable", observed_at=observed_at)
    except Exception:  # noqa: BLE001
        return _unavailable_observation("state_contract_invalid", observed_at=observed_at)


def _runtime_probe() -> tuple[dict, dict, dict]:
    """Return a read-only inventory bound to a non-secret database identity."""
    try:
        import psycopg  # noqa: PLC0415
        from psycopg.conninfo import conninfo_to_dict  # noqa: PLC0415
        from semiskill.config import Config  # noqa: PLC0415
    except ImportError as exc:
        raise OperationalProbeUnavailable("driver_unavailable") from exc
    try:
        dsn = Config.from_env().database_url
        parameters = conninfo_to_dict(dsn)
        expected_database = parameters.get("dbname")
        environment = os.environ.get("SEMISKILL_ENVIRONMENT", "development")
        if (
            not isinstance(expected_database, str) or not expected_database
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", environment)
            or (environment != "development" and not os.environ.get("DATABASE_URL"))
        ):
            raise ValueError("invalid database identity")
    except Exception as exc:
        raise OperationalProbeUnavailable("configuration_invalid") from exc
    try:
        conn = psycopg.connect(dsn, connect_timeout=2)
    except Exception as exc:
        raise OperationalProbeUnavailable("connection_unavailable") from exc
    try:
        with conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '2000ms'")
            conn.execute("SET LOCAL lock_timeout = '1000ms'")
            with conn.cursor() as cursor:
                cursor.execute("select current_database(), current_user")
                identity_row = cursor.fetchone()
                cursor.execute("select count(*) from public.artifacts")
                total_row = cursor.fetchone()
                cursor.execute(
                    "select artifact_type, count(*) from public.artifacts group by 1 order by 1"
                )
                type_rows = cursor.fetchall()
    except Exception as exc:
        raise OperationalProbeUnavailable("query_unavailable") from exc
    if (
        not isinstance(identity_row, (tuple, list)) or len(identity_row) != 2
        or identity_row[0] != expected_database
    ):
        raise OperationalProbeUnavailable("identity_mismatch")
    try:
        total = int(total_row[0])
        by_type = [{"type": str(kind), "n": int(count)} for kind, count in type_rows]
    except (TypeError, ValueError, IndexError) as exc:
        raise OperationalProbeUnavailable("query_unavailable") from exc
    if (
        total < 0 or any(item["n"] < 0 or not item["type"] for item in by_type)
        or len({item["type"] for item in by_type}) != len(by_type)
        or sum(item["n"] for item in by_type) != total
    ):
        raise OperationalProbeUnavailable("query_unavailable")
    fingerprint = {
        "engine": "postgresql",
        "environment": environment,
        "database_name": expected_database,
        "host": parameters.get("host", ""),
        "port": str(parameters.get("port", "")),
        "configured_user": parameters.get("user", ""),
        "session_user": str(identity_row[1]),
    }
    identity = {
        "engine": "postgresql",
        "environment": environment,
        "database_name": expected_database,
        "identity_sha256": _canonical_sha256(fingerprint),
    }
    scope = {
        "kind": "database-wide-raw-artifact-inventory",
        "relation": "public.artifacts",
        "transaction": "read-only",
        "catalog_binding": "none",
        "credit": "none",
    }
    return identity, scope, {"artifacts": total, "by_type": by_type, "complete": True}


def _validate_runtime_payload(identity: object, scope: object, data: object) -> None:
    if not isinstance(identity, dict) or set(identity) != {
        "engine", "environment", "database_name", "identity_sha256",
    }:
        raise OperationalProbeUnavailable("invalid_observation")
    if (
        identity.get("engine") != "postgresql"
        or not isinstance(identity.get("environment"), str) or not identity["environment"]
        or not isinstance(identity.get("database_name"), str) or not identity["database_name"]
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(identity.get("identity_sha256", "")))
    ):
        raise OperationalProbeUnavailable("invalid_observation")
    if not isinstance(scope, dict) or scope != {
        "kind": "database-wide-raw-artifact-inventory",
        "relation": "public.artifacts",
        "transaction": "read-only",
        "catalog_binding": "none",
        "credit": "none",
    }:
        raise OperationalProbeUnavailable("invalid_observation")
    if not isinstance(data, dict) or set(data) != {"artifacts", "by_type", "complete"}:
        raise OperationalProbeUnavailable("invalid_observation")
    total, by_type = data["artifacts"], data["by_type"]
    if (
        isinstance(total, bool) or not isinstance(total, int) or total < 0
        or data["complete"] is not True or not isinstance(by_type, list)
    ):
        raise OperationalProbeUnavailable("invalid_observation")
    seen, counted = set(), 0
    for item in by_type:
        if not isinstance(item, dict) or set(item) != {"type", "n"}:
            raise OperationalProbeUnavailable("invalid_observation")
        count = item["n"]
        if (
            not isinstance(item["type"], str) or not item["type"] or item["type"] in seen
            or isinstance(count, bool) or not isinstance(count, int) or count < 0
        ):
            raise OperationalProbeUnavailable("invalid_observation")
        seen.add(item["type"])
        counted += count
    if counted != total:
        raise OperationalProbeUnavailable("invalid_observation")


def runtime_signals() -> dict:
    """Typed read-only database inventory; this probe starts no process or HTTP request."""
    observed_at = _now()
    try:
        identity, scope, data = _runtime_probe()
        _validate_runtime_payload(identity, scope, data)
        db = _available_observation(
            observed_at=observed_at, identity=identity, scope=scope, data=data,
        )
    except OperationalProbeUnavailable as exc:
        db = _unavailable_observation(exc.reason, observed_at=observed_at)
    except Exception:  # noqa: BLE001
        db = _unavailable_observation("probe_unavailable", observed_at=observed_at)
    return {"checked_at": observed_at, "db": db}


def full_suite_signal(*, repository: dict | None = None) -> dict:
    """Project immutable full-suite evidence without executing, connecting or repairing anything."""
    observed_at = _now()
    repo_identity = repository.get("identity") if isinstance(repository, dict) else None
    repo_data = repository.get("data") if isinstance(repository, dict) else None
    if (
        not isinstance(repository, dict) or repository.get("status") != "available"
        or not isinstance(repo_identity, dict) or not isinstance(repo_data, dict)
    ):
        return _unavailable_observation("repository_unavailable", observed_at=observed_at)
    if repo_data.get("dirty") != 0:
        return _unavailable_observation("working_tree_dirty", observed_at=observed_at)
    commit, tree = repo_identity.get("commit"), repo_identity.get("tree")
    if not _valid_object_id(commit) or not _valid_object_id(tree) or len(commit) != len(tree):
        return _unavailable_observation("repository_identity_invalid", observed_at=observed_at)
    root = ROOT / "dashboard" / "runs" / "full-suite"
    try:
        run = read_latest_run(root)
        expected_format = "sha1" if len(commit) == 40 else "sha256"
        if run["source"]["object_format"] != expected_format:
            raise OperationalProbeUnavailable("source_object_format_mismatch")
        if run["source"]["commit"] != commit:
            raise OperationalProbeUnavailable("source_commit_mismatch")
        if run["source"]["tree"] != tree:
            raise OperationalProbeUnavailable("source_tree_mismatch")
        ended = _timestamp(run["ended_at"])
        raw_age_seconds = (_timestamp(observed_at) - ended).total_seconds()
        if raw_age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
            raise OperationalProbeUnavailable("full_suite_clock_skew")
        age_seconds = math.ceil(max(0, raw_age_seconds))
        max_age_seconds = _full_suite_max_age_seconds()
        stale = age_seconds > max_age_seconds
        database = run["database"]
        return _available_observation(
            observed_at=observed_at,
            identity={
                "run_id": run["run_id"],
                "run_sha256": run["run_sha256"],
                "source_commit": commit,
                "source_tree": tree,
                "database_identity_sha256": database["identity_sha256"],
            },
            scope=dict(_FULL_SUITE_SCOPE),
            freshness={
                "status": "stale" if stale else "fresh",
                "age_seconds": age_seconds,
                "max_age_seconds": max_age_seconds,
            },
            status="stale" if stale else "available",
            reason="full_suite_expired" if stale else None,
            data={
                "verdict": run["verdict"],
                "started_at": run["started_at"],
                "ended_at": run["ended_at"],
                "duration_seconds": run["duration_seconds"],
                "exit_code": run["exit_code"],
                "result_complete": run["result_complete"],
                "failure_reason": run["failure_reason"],
                "counts": dict(run["counts"]),
                "database": {
                    "engine": database["engine"],
                    "environment": database["environment"],
                    "database_name": database["database_name"],
                    "identity_sha256": database["identity_sha256"],
                    "session_user_sha256": database["session_user_sha256"],
                },
                "artifact": {
                    "run_ref": f"dashboard/runs/full-suite/runs/{run['run_id']}.json",
                    "run_sha256": run["run_sha256"],
                    "output_ref": f"dashboard/runs/full-suite/{run['output']['ref']}",
                    "output_sha256": run["output"]["sha256"],
                },
            },
        )
    except OperationalProbeUnavailable as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except FullSuiteEvidenceUnavailable as exc:
        reason = str(exc)
        if re.fullmatch(r"[a-z0-9_]{1,80}", reason) is None:
            reason = "full_suite_evidence_invalid"
        return _unavailable_observation(reason, observed_at=observed_at)
    except DashboardSnapshotRejected as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except Exception:  # noqa: BLE001 - the reader discloses no filesystem exception detail
        return _unavailable_observation("full_suite_evidence_invalid", observed_at=observed_at)


def canonical_snapshot_signals(*, migration: dict | None = None) -> dict:
    """Load canonical catalog state or expose an explicit, non-substituted unavailable state."""
    observed_at = _now()
    scoreboard = {
        "status": "unavailable", "observed_at": observed_at,
        "reason": "not_configured", "snapshot": None, "validation": None,
    }
    progress = {
        "status": "unavailable", "observed_at": observed_at,
        "reason": "scoreboard_unavailable", "snapshot": None, "validation": None,
    }
    scoreboard_path = os.environ.get("SEMISKILL_SCOREBOARD_SNAPSHOT")
    if not scoreboard_path:
        return {"scoreboard": scoreboard, "progress": progress}
    try:
        snapshot = load_scoreboard_snapshot(scoreboard_path)
    except SnapshotUnavailable:
        scoreboard["reason"] = "invalid_or_unavailable"
        return {"scoreboard": scoreboard, "progress": progress}
    environment = os.environ.get("SEMISKILL_ENVIRONMENT", "development")
    if snapshot["sources"]["database"]["environment"] != environment:
        scoreboard["reason"] = "environment_mismatch"
        return {"scoreboard": scoreboard, "progress": progress}
    migration = migration if migration is not None else migration_witness_signal()
    try:
        freshness = _freshness_validation(
            generated_at=snapshot["generated_at"], observed_at=observed_at, kind="snapshot",
        )
        live_validation = _live_snapshot_validation(snapshot, migration=migration)
    except DashboardSnapshotRejected as exc:
        scoreboard["reason"] = exc.reason
        return {"scoreboard": scoreboard, "progress": progress}

    scoreboard.update(
        status="available", reason=None, snapshot=snapshot,
        validation={**freshness, **live_validation, "validated_at": observed_at},
    )
    progress["reason"] = "not_configured"
    progress_path = os.environ.get("SEMISKILL_PROGRESS_SNAPSHOT")
    if progress_path:
        try:
            progress_snapshot = load_progress(progress_path, snapshot["snapshot_id"])
        except SnapshotUnavailable:
            progress["reason"] = "invalid_or_unavailable"
        else:
            try:
                scoreboard_time = _timestamp(snapshot["generated_at"])
                progress_time = _timestamp(progress_snapshot["generated_at"])
                if progress_time < scoreboard_time:
                    raise DashboardSnapshotRejected("progress_older_than_scoreboard")
                progress_freshness = _freshness_validation(
                    generated_at=progress_snapshot["generated_at"],
                    observed_at=observed_at,
                    kind="progress",
                )
                maximum = progress_freshness["max_age_seconds"]
                observed_time = _timestamp(observed_at)
                for worker in progress_snapshot["workers"]:
                    started = _timestamp(worker["started_at"])
                    updated = _timestamp(worker["updated_at"])
                    if started > updated or updated > progress_time:
                        raise DashboardSnapshotRejected("worker_time_order_invalid")
                    worker_age = (observed_time - updated).total_seconds()
                    if worker_age < -_MAX_FUTURE_SKEW_SECONDS:
                        raise DashboardSnapshotRejected("worker_clock_skew")
                    if worker_age > maximum:
                        raise DashboardSnapshotRejected("worker_stale")
            except DashboardSnapshotRejected as exc:
                progress["reason"] = exc.reason
            else:
                progress.update(
                    status="available", reason=None, snapshot=progress_snapshot,
                    validation={**progress_freshness, "validated_at": observed_at},
                )
    return {"scoreboard": scoreboard, "progress": progress}


def _migration_tracker_sha256(rows: list[dict[str, str]]) -> str:
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _migration_repository_rows() -> list[dict[str, str]]:
    rows = []
    directory = ROOT / "semiskill" / "artifacts" / "migrations"
    for path in sorted(directory.glob("*.sql")):
        stat = path.lstat()
        if (
            not _MIGRATION_NAME.fullmatch(path.name)
            or path.is_symlink()
            or bool(getattr(stat, "st_file_attributes", 0) & 0x400)
            or not path.is_file()
        ):
            raise DashboardSnapshotRejected("migration_source_invalid")
        rows.append({"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not rows:
        raise DashboardSnapshotRejected("migration_source_invalid")
    return rows


def _read_migration_database_state(dsn: str, *, connect=None) -> dict:
    if connect is None:
        import psycopg  # noqa: PLC0415
        connect = psycopg.connect
    from semiskill.artifacts.migrate import _post_migration_attestations  # noqa: PLC0415

    with connect(dsn, connect_timeout=3) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '3000ms'")
        conn.execute("SET LOCAL lock_timeout = '1000ms'")
        database_name = conn.execute("SELECT current_database()").fetchone()[0]
        tracker_rows = [
            {"filename": filename, "sha256": checksum}
            for filename, checksum in conn.execute(
                "SELECT filename,sha256 FROM public.schema_migrations ORDER BY filename"
            ).fetchall()
        ]
        audits = conn.execute(
            "SELECT artifact_id,timestamp_start,source_system::text,actor_kind::text,"
            "permissions_label,objective_tag,ground_truth_ref,payload,input_refs,actor,"
            "timestamp_end,output_refs,eval_score,rollback_ref,cost_usd,corrects_ref "
            "FROM public.artifacts "
            "WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version' IN "
            "('migration-checksum-adoption/v1','migration-forward-execution/v1') "
            "ORDER BY timestamp_start,artifact_id LIMIT 5"
        ).fetchall()
        projection_rows = conn.execute(
            "SELECT count(*) FROM public.verified_publication_events"
        ).fetchone()[0]
        schema_attestations = _post_migration_attestations(conn)
        conn.rollback()
    return {
        "database_name": database_name,
        "tracker_rows": tracker_rows,
        "audits": audits,
        "projection_rows": projection_rows,
        "schema_attestations": schema_attestations,
    }


def _canonical_filename_list(value: object, *, repository: set[str], removed: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(name, str) or not _MIGRATION_NAME.fullmatch(name) for name in value)
        or len(value) != len(set(value))
    ):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    if removed:
        if any(name in repository for name in value):
            raise DashboardSnapshotRejected("adoption_witness_invalid")
    elif any(name not in repository for name in value):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    return value


def _audit_time_order_valid(timestamp_start: object, timestamp_end: object) -> bool:
    try:
        return (
            isinstance(timestamp_start, datetime)
            and isinstance(timestamp_end, datetime)
            and timestamp_end >= timestamp_start
        )
    except (TypeError, ValueError):
        return False


def _adoption_payload_contract_valid(
    payload: dict,
    *,
    repository_rows: list[dict[str, str]],
) -> bool:
    expected_keys = {
        "adopted_filenames", "adoption_id", "applied_filenames", "database",
        "decision", "environment", "final_tracker", "historical_limit",
        "operator_authentication", "plan_sha256", "post_migration_attestations",
        "reason", "removed_orphaned_relations", "removed_orphaned_test_fixtures",
        "repository_manifest", "schema_attestations", "schema_version",
        "source_commit", "tracked_manifest", "trusted_manifest_sha256",
    }
    if set(payload) != expected_keys:
        return False
    try:
        from semiskill.artifacts.migrate import (  # noqa: PLC0415
            MigrationAdoptionRefused,
            _ADOPTION_SCHEMA_ATTESTATION_KEYS,
            _trusted_legacy_manifest,
        )
        manifest = _project_manifest_with_bytes(
            payload.get("repository_manifest"), reason="adoption_witness_invalid",
        )
        trusted, trusted_sha256 = _trusted_legacy_manifest(manifest)
    except (DashboardSnapshotRejected, MigrationAdoptionRefused, TypeError, ValueError):
        return False
    projected_manifest = [
        {"filename": row["filename"], "sha256": row["sha256"]}
        for row in manifest
    ]
    tracked = payload.get("tracked_manifest")
    adopted = payload.get("adopted_filenames")
    applied = payload.get("applied_filenames")
    removed = payload.get("removed_orphaned_test_fixtures")
    removed_relations = payload.get("removed_orphaned_relations")
    schema = payload.get("schema_attestations")
    trusted_names = [row["filename"] for row in trusted["migrations"]]
    if (
        projected_manifest != repository_rows
        or not isinstance(tracked, list)
        or not isinstance(adopted, list)
        or not isinstance(applied, list)
        or not isinstance(removed, list)
        or not isinstance(removed_relations, list)
        or not isinstance(schema, dict)
        or set(schema) != _ADOPTION_SCHEMA_ATTESTATION_KEYS
        or any(value is not True for value in schema.values())
        or payload.get("trusted_manifest_sha256") != trusted_sha256
        or payload.get("historical_limit") != trusted.get("historical_limit")
        or adopted + applied != [row["filename"] for row in repository_rows]
        or (removed, removed_relations) not in (
            ([], []),
            (["9001_probe.sql"], ["public.mig_probe"]),
        )
    ):
        return False
    tracked_names = []
    for row in tracked:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256", "applied_at"}
            or not isinstance(row.get("filename"), str)
            or _MIGRATION_NAME.fullmatch(row["filename"]) is None
            or (
                row.get("sha256") is not None
                and re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])) is None
            )
            or not isinstance(row.get("applied_at"), str)
            or not row["applied_at"].strip()
        ):
            return False
        tracked_names.append(row["filename"])
    if (
        tracked_names != sorted(trusted_names + removed)
        or len(tracked_names) != len(set(tracked_names))
        or adopted != [
            row["filename"] for row in tracked
            if row["filename"] in trusted_names and row["sha256"] is None
        ]
    ):
        return False
    reconstructed_plan = {
        "schema_version": "migration-checksum-adoption-plan/v1",
        "database": payload.get("database"),
        "environment": payload.get("environment"),
        "source_commit": payload.get("source_commit"),
        "tracked_prefix": trusted_names,
        "tracked_manifest": tracked,
        "repository_manifest": manifest,
        "trusted_manifest_sha256": trusted_sha256,
        "orphaned_test_fixtures_to_remove": removed,
        "orphaned_relations_to_drop": removed_relations,
        "legacy_null_filenames": adopted,
        "legacy_null_count": len(adopted),
        "pending_filenames": applied,
        "schema_attestations": schema,
        "historical_limit": trusted["historical_limit"],
    }
    return payload.get("plan_sha256") == _canonical_sha256(reconstructed_plan)


def _project_adoption_witness(
    audits: list,
    *,
    repository_rows: list[dict[str, str]],
    environment: str,
    database_name: str,
) -> dict | None:
    if len(audits) > 1:
        raise DashboardSnapshotRejected("adoption_witness_ambiguous")
    if not audits:
        return None
    if len(audits[0]) != 16:
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    (
        artifact_id, timestamp_start, source_system, actor_kind, permissions_label,
        objective_tag, ground_truth_ref, payload, input_refs, actor, timestamp_end,
        output_refs, eval_score, rollback_ref, cost_usd, corrects_ref,
    ) = audits[0]
    if not isinstance(payload, dict):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    plan_sha256 = payload.get("plan_sha256")
    source_commit = payload.get("source_commit")
    database = payload.get("database")
    post = payload.get("post_migration_attestations")
    operator = payload.get("operator_authentication")
    reason = payload.get("reason")
    if (
        source_system != "cli"
        or not isinstance(actor, str)
        or not actor.strip()
        or actor_kind != "human"
        or not _audit_time_order_valid(timestamp_start, timestamp_end)
        or list(input_refs or []) != []
        or list(output_refs or []) != []
        or permissions_label != "need-to-know"
        or objective_tag != "compliance"
        or ground_truth_ref != plan_sha256
        or eval_score is not None
        or cost_usd is not None
        or corrects_ref is not None
        or rollback_ref != {
            "supported": False,
            "reason": "historical checksum adoption is an irreversible attestation",
        }
        or payload.get("schema_version") != "migration-checksum-adoption/v1"
        or payload.get("decision") != "adopt_and_apply"
        or payload.get("adoption_id") != str(artifact_id)
        or payload.get("environment") != environment
        or not isinstance(reason, str)
        or not 20 <= len(reason) <= 1000
        or reason != reason.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in reason)
        or not isinstance(database, dict)
        or database.get("database_name") != database_name
        or not isinstance(operator, dict)
        or set(operator) != {"provider", "subject_sha256"}
        or operator.get("provider") not in {"local_os", "entra_oidc"}
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(operator.get("subject_sha256"))
        ) is None
        or payload.get("final_tracker") != repository_rows
        or not isinstance(post, dict)
        or set(post) != _ADOPTION_0015_ATTESTATION_KEYS
        or any(value is not True for value in post.values())
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(plan_sha256))
        or not re.fullmatch(r"[0-9a-f]{40}", str(source_commit))
        or not _adoption_payload_contract_valid(
            payload, repository_rows=repository_rows,
        )
    ):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    try:
        timestamp = timestamp_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (AttributeError, TypeError, ValueError) as exc:
        raise DashboardSnapshotRejected("adoption_witness_invalid") from exc
    repository_names = {row["filename"] for row in repository_rows}
    adopted = _canonical_filename_list(payload.get("adopted_filenames"), repository=repository_names)
    applied = _canonical_filename_list(payload.get("applied_filenames"), repository=repository_names)
    removed = _canonical_filename_list(
        payload.get("removed_orphaned_test_fixtures"), repository=repository_names, removed=True,
    )
    removed_relations = payload.get("removed_orphaned_relations")
    if (
        not isinstance(removed_relations, list)
        or any(not isinstance(name, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", name)
               for name in removed_relations)
        or len(removed_relations) != len(set(removed_relations))
        or set(adopted) & set(applied)
    ):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    return {
        "artifact_id": str(artifact_id),
        "timestamp": timestamp,
        "environment": environment,
        "source_commit": source_commit,
        "plan_sha256": plan_sha256,
        "payload_sha256": _canonical_sha256(payload),
        "final_tracker_sha256": _migration_tracker_sha256(repository_rows),
        "adopted_count": len(adopted),
        "applied_count": len(applied),
        "attestations_passed": len(post),
        "attestations_total": len(post),
        "removed_test_fixtures": removed,
        "historical_limit": (
            "Reviewed hashes and schema attest the adopted present state; they cannot prove "
            "which bytes were executed historically."
        ),
    }


def _project_manifest_with_bytes(
    value: object, *, reason: str = "forward_witness_invalid",
) -> list[dict[str, str | int]]:
    if not isinstance(value, list) or not value:
        raise DashboardSnapshotRejected(reason)
    projected = []
    names = []
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256", "bytes"}
            or not isinstance(row.get("filename"), str)
            or _MIGRATION_NAME.fullmatch(row["filename"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) is None
            or type(row.get("bytes")) is not int
            or not 0 < row["bytes"] <= 2_000_000
        ):
            raise DashboardSnapshotRejected(reason)
        path = ROOT / "semiskill" / "artifacts" / "migrations" / row["filename"]
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DashboardSnapshotRejected(reason) from exc
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise DashboardSnapshotRejected(reason)
        names.append(row["filename"])
        projected.append(dict(row))
    if names != sorted(names) or len(names) != len(set(names)):
        raise DashboardSnapshotRejected(reason)
    return projected


def _project_tracker(value: object, *, reason: str = "forward_witness_invalid") -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise DashboardSnapshotRejected(reason)
    rows = []
    names = []
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256"}
            or not isinstance(row.get("filename"), str)
            or _MIGRATION_NAME.fullmatch(row["filename"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) is None
        ):
            raise DashboardSnapshotRejected(reason)
        names.append(row["filename"])
        rows.append(dict(row))
    if names != sorted(names) or len(names) != len(set(names)):
        raise DashboardSnapshotRejected(reason)
    return rows


def _project_tracked_manifest(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise DashboardSnapshotRejected("forward_witness_invalid")
    projected = []
    names = []
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256", "applied_at"}
            or not isinstance(row.get("filename"), str)
            or _MIGRATION_NAME.fullmatch(row["filename"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) is None
            or not isinstance(row.get("applied_at"), str)
            or not row["applied_at"].strip()
            or len(row["applied_at"]) > 128
        ):
            raise DashboardSnapshotRejected("forward_witness_invalid")
        names.append(row["filename"])
        projected.append({"filename": row["filename"], "sha256": row["sha256"]})
    if names != sorted(names) or len(names) != len(set(names)):
        raise DashboardSnapshotRejected("forward_witness_invalid")
    return projected


def _project_forward_witness(
    audits: list,
    *,
    adoption_audit: tuple,
    adoption: dict,
    repository_rows: list[dict[str, str]],
    environment: str,
    database_name: str,
) -> dict:
    if len(audits) != 1 or len(audits[0]) != 16:
        raise DashboardSnapshotRejected("forward_witness_ambiguous")
    (
        artifact_id, timestamp_start, source_system, actor_kind, permissions_label,
        objective_tag, ground_truth_ref, payload, input_refs, actor, timestamp_end,
        output_refs, eval_score, rollback_ref, cost_usd, corrects_ref,
    ) = audits[0]
    if not isinstance(payload, dict):
        raise DashboardSnapshotRejected("forward_witness_invalid")
    expected_keys = {
        "schema_version", "migration_id", "decision", "policy_id", "environment",
        "reason", "source_commit", "plan_sha256", "database",
        "operator_authentication", "prior_audit", "tracker_before",
        "repository_manifest", "pending_manifest", "pre_migration_attestation",
        "post_migration_attestations", "applied_filenames", "final_tracker",
    }
    database = payload.get("database")
    operator = payload.get("operator_authentication")
    prior = payload.get("prior_audit")
    pre = payload.get("pre_migration_attestation")
    post = payload.get("post_migration_attestations")
    plan_sha256 = payload.get("plan_sha256")
    source_commit = payload.get("source_commit")
    try:
        adoption_id = uuid.UUID(adoption["artifact_id"])
        expected_id = uuid.uuid5(
            _FORWARD_AUDIT_NAMESPACE,
            f"{database['identity_sha256']}|{plan_sha256}",
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise DashboardSnapshotRejected("forward_witness_invalid") from exc
    if (
        set(payload) != expected_keys
        or source_system != "cli"
        or not isinstance(actor, str)
        or not actor.strip()
        or actor_kind != "human"
        or not _audit_time_order_valid(timestamp_start, timestamp_end)
        or not _audit_time_order_valid(adoption_audit[1], adoption_audit[10])
        or not _audit_time_order_valid(adoption_audit[10], timestamp_start)
        or list(input_refs or []) != [adoption_id]
        or list(output_refs or []) != []
        or permissions_label != "need-to-know"
        or objective_tag != "compliance"
        or ground_truth_ref != plan_sha256
        or eval_score is not None
        or cost_usd is not None
        or corrects_ref is not None
        or rollback_ref != {
            "supported": False,
            "reason": "forward schema migrations are irreversible attestations",
        }
        or artifact_id != expected_id
        or payload.get("schema_version") != _FORWARD_EVIDENCE_SCHEMA
        or payload.get("migration_id") != str(artifact_id)
        or payload.get("decision") != "apply_reviewed_forward_migration"
        or payload.get("policy_id") != "migration/0015-to-0023@1"
        or payload.get("environment") != environment
        or not isinstance(payload.get("reason"), str)
        or not payload["reason"].strip()
        or re.fullmatch(r"[0-9a-f]{40}", str(source_commit)) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(plan_sha256)) is None
        or not isinstance(database, dict)
        or database.get("database_name") != database_name
        or adoption_audit[7].get("database") != database
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(database.get("identity_sha256"))
        ) is None
        or not isinstance(operator, dict)
        or operator.get("actor") != actor
        or not isinstance(prior, dict)
        or prior != {
            "artifact_id": adoption["artifact_id"],
            "schema_version": "migration-checksum-adoption/v1",
            "plan_sha256": adoption["plan_sha256"],
            "payload_sha256": adoption["payload_sha256"],
        }
        or not isinstance(pre, dict)
        or pre.get("policy_id") != "schema/0015@1"
        or not isinstance(pre.get("results"), dict)
        or set(pre["results"]) != _CHECKPOINT_0015_ATTESTATION_KEYS
        or any(value is not True for value in pre["results"].values())
        or not isinstance(post, dict)
        or set(post) != _POST_MIGRATION_ATTESTATION_KEYS
        or any(value is not True for value in post.values())
    ):
        raise DashboardSnapshotRejected("forward_witness_invalid")
    tracker_before = _project_tracked_manifest(payload.get("tracker_before"))
    final_tracker = _project_tracker(payload.get("final_tracker"))
    repository_manifest = _project_manifest_with_bytes(payload.get("repository_manifest"))
    pending_manifest = _project_manifest_with_bytes(payload.get("pending_manifest"))
    projected_repository = [
        {"filename": row["filename"], "sha256": row["sha256"]}
        for row in repository_manifest
    ]
    if (
        tracker_before != adoption_audit[7].get("final_tracker")
        or final_tracker != repository_rows
        or projected_repository != repository_rows
        or tracker_before != projected_repository[:len(tracker_before)]
        or pending_manifest != repository_manifest[len(tracker_before):]
        or payload.get("applied_filenames") != [row["filename"] for row in pending_manifest]
    ):
        raise DashboardSnapshotRejected("forward_witness_invalid")
    reconstructed_plan = {
        "schema_version": "migration-forward-plan/v1",
        "action": "apply_reviewed_forward_migration",
        "policy_id": payload["policy_id"],
        "source_commit": source_commit,
        "environment": environment,
        "database": database,
        "migrator": {
            "session_user_sha256": database.get("session_user_sha256"),
            "explicit_role_bound": True,
        },
        "operator_authentication": operator,
        "reason": payload["reason"],
        "prior_audit": prior,
        "tracker_manifest": payload["tracker_before"],
        "repository_manifest": repository_manifest,
        "pending_manifest": pending_manifest,
        "from_filename": tracker_before[-1]["filename"],
        "to_filename": repository_rows[-1]["filename"],
        "pre_attestation": pre,
        "post_attestation_contract": {
            "policy_id": "schema/0023@1",
            "required_keys": sorted(_POST_MIGRATION_ATTESTATION_KEYS),
            "expected_all_true": True,
        },
        "plan_sha256": plan_sha256,
    }
    try:
        from semiskill.artifacts.migrate import (  # noqa: PLC0415
            MigrationAdoptionRefused,
            _validate_forward_plan_document,
        )
        _validate_forward_plan_document(reconstructed_plan, plan_sha256)
    except (MigrationAdoptionRefused, TypeError, ValueError) as exc:
        raise DashboardSnapshotRejected("forward_witness_invalid") from exc
    try:
        timestamp = timestamp_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (AttributeError, TypeError, ValueError) as exc:
        raise DashboardSnapshotRejected("forward_witness_invalid") from exc
    return {
        "artifact_id": str(artifact_id),
        "timestamp": timestamp,
        "environment": environment,
        "source_commit": source_commit,
        "plan_sha256": plan_sha256,
        "from_migration": tracker_before[-1]["filename"],
        "to_migration": repository_rows[-1]["filename"],
        "applied_count": len(pending_manifest),
        "attestations_passed": len(post),
        "attestations_total": len(post),
        "prior_artifact_id": adoption["artifact_id"],
    }


def _migration_authority_chain_projection(
    adoption: dict, forward: dict, tracker_sha256: str,
) -> dict:
    body = {
        "schema_version": "migration-authority-chain/v1",
        "adoption_artifact_id": adoption.get("artifact_id"),
        "adoption_payload_sha256": adoption.get("payload_sha256"),
        "forward_artifact_id": forward.get("artifact_id"),
        "forward_plan_sha256": forward.get("plan_sha256"),
        "prior_artifact_id": forward.get("prior_artifact_id"),
        "tracker_sha256": tracker_sha256,
    }
    return {**body, "sha256": _canonical_sha256(body)}


def migration_witness_signal() -> dict:
    """Return a sanitized live tracker/adoption projection; never raw auth or audit payloads."""
    observed_at = _now()
    unavailable = {
        "status": "unavailable", "reason": "database_unavailable",
        "observed_at": observed_at, "tracker": None, "schema": None, "adoption": None,
        "forward": None, "authority_chain": None,
    }
    try:
        from semiskill.config import Config  # noqa: PLC0415
        repository_rows = _migration_repository_rows()
        environment = os.environ.get("SEMISKILL_ENVIRONMENT", "development")
        database_state = _read_migration_database_state(Config.from_env().database_url)
    except DashboardSnapshotRejected as exc:
        unavailable["reason"] = exc.reason
        return unavailable
    except Exception:
        return unavailable
    try:
        database_name = database_state["database_name"]
        tracker_rows = database_state["tracker_rows"]
        if tracker_rows != repository_rows:
            raise DashboardSnapshotRejected("migration_tracker_mismatch")
        schema = database_state["schema_attestations"]
        if (
            not isinstance(schema, dict)
            or set(schema) != _POST_MIGRATION_ATTESTATION_KEYS
            or any(schema.get(key) is not True for key in _CURRENT_SCHEMA_ATTESTATION_KEYS)
            or type(schema.get("projection_and_policy_start_empty")) is not bool
        ):
            raise DashboardSnapshotRejected("schema_witness_mismatch")
        adoption_audits = [
            row for row in database_state["audits"]
            if len(row) == 16 and isinstance(row[7], dict)
            and row[7].get("schema_version") == "migration-checksum-adoption/v1"
        ]
        forward_audits = [
            row for row in database_state["audits"]
            if len(row) == 16 and isinstance(row[7], dict)
            and row[7].get("schema_version") == _FORWARD_EVIDENCE_SCHEMA
        ]
        if len(adoption_audits) != 1 or len(forward_audits) != 1:
            raise DashboardSnapshotRejected("migration_witness_chain_incomplete")
        checkpoint_rows = _project_tracked_manifest(
            forward_audits[0][7].get("tracker_before"),
        )
        adoption = _project_adoption_witness(
            adoption_audits, repository_rows=checkpoint_rows,
            environment=environment, database_name=database_name,
        )
        forward = _project_forward_witness(
            forward_audits,
            adoption_audit=adoption_audits[0],
            adoption=adoption,
            repository_rows=repository_rows,
            environment=environment,
            database_name=database_name,
        )
    except DashboardSnapshotRejected as exc:
        unavailable["reason"] = exc.reason
        unavailable["tracker"] = {
            "repository_count": len(repository_rows), "tracked_count": len(
                database_state.get("tracker_rows", [])
            ),
        }
        return unavailable
    except Exception:
        unavailable["reason"] = "migration_witness_invalid"
        return unavailable
    tracker_sha256 = _migration_tracker_sha256(tracker_rows)
    authority_chain = _migration_authority_chain_projection(
        adoption, forward, tracker_sha256,
    )
    return {
        "status": "verified", "reason": None, "observed_at": observed_at,
        "database": {"environment": environment, "database_name": database_name},
        "tracker": {
            "repository_count": len(repository_rows),
            "tracked_count": len(tracker_rows),
            "latest_migration": tracker_rows[-1]["filename"],
            "sha256": tracker_sha256,
            "exact": True,
        },
        "schema": {
            "status": "verified",
            "passed": len(_CURRENT_SCHEMA_ATTESTATION_KEYS),
            "total": len(_CURRENT_SCHEMA_ATTESTATION_KEYS),
        },
        "projection_rows": database_state["projection_rows"],
        "adoption": adoption,
        "forward": forward,
        "authority_chain": authority_chain,
    }


def redteam_signal(path: str | Path | None = None) -> dict:
    """Expose fixture inputs as inventory, never as evidence that an attack was executed."""
    fixture = Path(path) if path is not None else (
        ROOT / "tests" / "redteam" / "fixtures" / "generated_attacks.json"
    )
    unavailable = {
        "status": "unavailable",
        "reason": "corpus_invalid_or_unavailable",
        "observed_at": None,
        "corpus_observed_at": None,
        "corpus": [],
        "execution": None,
    }
    try:
        rows = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            return unavailable
        corpus = []
        names: set[str] = set()
        digests: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                return unavailable
            name = row.get("name")
            attack_class = row.get("attack_class")
            technique = row.get("technique")
            skill_md = row.get("skill_md")
            if not all(isinstance(value, str) and value.strip()
                       for value in (name, attack_class, technique, skill_md)):
                return unavailable
            digest = "sha256:" + hashlib.sha256(skill_md.encode("utf-8")).hexdigest()
            if name in names or digest in digests:
                return unavailable
            names.add(name)
            digests.add(digest)
            corpus.append({
                "name": name,
                "attack_class": attack_class,
                "technique": technique,
                "input_sha256": digest,
                "outcome": "not_executed",
            })
        corpus_observed_at = datetime.fromtimestamp(
            fixture.stat().st_mtime, timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return unavailable
    return {
        "status": "not_executed",
        "reason": "no_authoritative_execution_result",
        "observed_at": None,
        "corpus_observed_at": corpus_observed_at,
        "corpus": corpus,
        "execution": None,
    }


def _remove_unexecuted_redteam_credit(model: dict, redteam: dict) -> None:
    if redteam.get("execution") is not None:
        return
    for feature in model.get("features", []):
        if feature.get("id") == "F-L6-06":
            feature.update(
                name="Red-team harness and input corpus",
                declared_status="partial",
                note=("Harness tests and adversarial inputs exist; no immutable execution result "
                      "is bound to the current corpus."),
            )
    for item in model.get("launch_checklist", []):
        if item.get("id") == "LC-11":
            item.update(
                item="Authoritative corpus-bound red-team execution result",
                declared_status="todo",
            )
    for risk in model.get("risks", []):
        if risk.get("id") == "R-07":
            risk["detail"] = (
                "The current red-team escape result is unavailable; the block rate on honest "
                "skills is also unmeasured, and over-blocking kills adoption."
            )
    for metric in model.get("gtm", {}).get("metrics", []):
        if metric.get("id") == "M-05":
            metric["measurement"] = {
                "status": "unmeasured",
                "value": None,
                "observed_at": None,
                "evidence_ref": None,
                "reason": "authoritative corpus execution result is unavailable",
            }


def adrs(*, repository: dict | None = None) -> dict:
    observed_at = _now()
    commit = _repository_commit(repository)
    if commit is None:
        return _unavailable_observation("repository_unavailable", observed_at=observed_at)
    path = ROOT / "DECISIONS.md"
    try:
        if path.is_symlink() or not path.is_file():
            raise OperationalProbeUnavailable("required_file_unavailable")
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        active = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        candidate_lines = [
            line.strip() for line in active.splitlines()
            if re.match(r"^#{1,6}\s+\[ADR", line.strip())
        ]
        items, numbers = [], []
        for line in candidate_lines:
            match = re.fullmatch(r"## \[(ADR-(\d{3}))\]\s+(.+)", line)
            if match is None:
                raise OperationalProbeUnavailable("adr_register_invalid")
            items.append({"id": match.group(1), "title": match.group(3).strip()})
            numbers.append(int(match.group(2)))
        if not items or len(set(numbers)) != len(numbers) or numbers != sorted(numbers):
            raise OperationalProbeUnavailable("adr_register_invalid")
        return _available_observation(
            observed_at=observed_at,
            identity={
                "repository_commit": commit,
                "path": "DECISIONS.md",
                "sha256": _sha256_bytes(raw),
            },
            scope={"parser": "adr-heading/v1", "heading": "## [ADR-NNN] title"},
            data={"items": items, "count": len(items)},
        )
    except OperationalProbeUnavailable as exc:
        return _unavailable_observation(exc.reason, observed_at=observed_at)
    except (OSError, UnicodeDecodeError):
        return _unavailable_observation("required_file_unavailable", observed_at=observed_at)
    except Exception:  # noqa: BLE001
        return _unavailable_observation("adr_register_invalid", observed_at=observed_at)


def read_inbox() -> list[dict]:
    if not INBOX.exists():
        return []
    rows = []
    for line in INBOX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                row = strict_json_loads(line)
            except (ValueError, json.JSONDecodeError) as exc:
                raise action_queue.QueueUnavailable("queue corrupt") from exc
            if not isinstance(row, dict):
                raise action_queue.QueueUnavailable("queue corrupt")
            rows.append(ActionQueue._public_row(row))
    return rows


def read_public_model() -> dict:
    loaded = action_queue.load_pinned_model(MODEL)
    return action_queue.public_model(loaded)


def read_public_templates() -> list[dict]:
    """Compatibility projection; state assembly reads the complete model exactly once."""
    return read_public_model()["actions"]


def read_state_inputs() -> tuple[dict, list[dict]]:
    """Default file-backed state inputs; the HTTP server supplies its queue-owned equivalent."""
    return read_public_model(), read_inbox()


def artifact_schema_signal() -> dict:
    """Project the imported canonical schema instead of duplicating it in presentation code."""
    return {
        "source": "semiskill/artifacts/schema.py",
        "fields": [
            {"name": item.name, "type": str(item.type)}
            for item in fields(Artifact)
        ],
        "vocabularies": {
            "artifact_type": [item.value for item in ArtifactType],
            "source_system": [item.value for item in SourceSystem],
            "actor_kind": [item.value for item in ActorKind],
            "permissions_label": list(PERMISSIONS_LABELS),
            "objective_tag": list(OBJECTIVE_TAGS),
        },
    }


def _collect_runtime_signals() -> dict:
    try:
        runtime = runtime_signals()
        if not isinstance(runtime, dict) or set(runtime) != {"checked_at", "db"}:
            raise ValueError("invalid runtime observation")
        _timestamp(runtime["checked_at"])
        runtime["db"] = _validated_observation(runtime["db"])
        if runtime["db"]["status"] != "unavailable":
            _validate_runtime_payload(
                runtime["db"]["identity"], runtime["db"]["scope"], runtime["db"]["data"],
            )
        return runtime
    except OperationalProbeUnavailable as exc:
        observed_at = _now()
        return {"checked_at": observed_at, "db": _unavailable_observation(
            exc.reason, observed_at=observed_at,
        )}
    except Exception:  # noqa: BLE001
        observed_at = _now()
        return {"checked_at": observed_at, "db": _unavailable_observation(
            "probe_unavailable", observed_at=observed_at,
        )}


def build_state(state_reader=None, model_reader=None) -> dict:
    if model_reader is None:
        model, inbox = (state_reader or read_state_inputs)()
    else:
        model = model_reader()
        inbox = (state_reader or read_inbox)()
    model = copy.deepcopy(model)
    inbox = copy.deepcopy(inbox)
    if not isinstance(model, dict) or not isinstance(model.get("actions"), list):
        raise action_queue.QueueUnavailable("dashboard model invalid")
    if not isinstance(inbox, list):
        raise action_queue.QueueUnavailable("queue projection invalid")
    migration = migration_witness_signal()
    canonical = canonical_snapshot_signals(migration=migration)
    redteam = redteam_signal()
    _remove_unexecuted_redteam_credit(model, redteam)
    repository = _collect_observation(repo_signals, _validate_repo_observation)
    repository_commit = _repository_commit(repository)
    full_suite = _collect_observation(
        lambda: full_suite_signal(repository=repository),
        lambda value: _validate_full_suite_observation(value, repository=repository),
    )
    project_state = _collect_observation(
        lambda: state_files(repository=repository),
        lambda value: _validate_state_observation(
            value, repository_commit=repository_commit,
        ),
    )
    decision_register = _collect_observation(
        lambda: adrs(repository=repository),
        lambda value: _validate_adr_observation(
            value, repository_commit=repository_commit,
        ),
    )
    return {
        "generated_at": _now(),
        "artifact_schema": artifact_schema_signal(),
        "model": model,
        "repo": repository,
        "state": project_state,
        "runtime": _collect_runtime_signals(),
        "verification": {"full_suite": full_suite},
        "scoreboard": canonical["scoreboard"],
        "progress": canonical["progress"],
        "migration": migration,
        "redteam": redteam,
        "adrs": decision_register,
        "inbox": inbox,
    }


# ---------------------------------------------------------------- http


class DashboardHTTPServer(ThreadingHTTPServer):
    """Loopback server with one queue owner and one process-local CSRF capability."""

    daemon_threads = True

    def __init__(self, server_address, handler, *, action_queue: ActionQueue, csrf_token=None):
        super().__init__(server_address, handler)
        self.action_queue = action_queue
        self.expected_authority = f"127.0.0.1:{self.server_address[1]}"
        self.expected_origin = f"http://{self.expected_authority}"
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)

    def server_close(self):
        try:
            self.action_queue.close()
        finally:
            super().server_close()

class Handler(BaseHTTPRequestHandler):
    server_version = "SemiSkillCommandCentre/1.0"

    def log_message(self, *a):
        pass

    def _security_headers(self):
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def _drain_unread_body(self) -> None:
        """Discard a bounded amount of unread request body before responding and closing.

        A rejection answers before consuming the body. Closing a socket that still holds unread
        data makes Windows send RST, which discards the response just written — so a correct
        415/421/403 never reaches the client and the failure looks like a flaky test rather than a
        delivery bug.

        Bounded in BOTH size and time deliberately. An unbounded drain would let a client stream
        forever into an already-rejected request, and a drain that waited for a declared-but-never-
        sent body would pin the worker. Both are denial-of-service shapes this fail-closed server
        exists to refuse, so the drain is best-effort: if it cannot finish within the budget it
        gives up and lets the close happen.
        """
        if getattr(self, "_body_consumed", False) or self.command != "POST":
            return
        self._body_consumed = True
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"\d+", lengths[0] or ""):
            return
        try:
            remaining = min(int(lengths[0]), _MAX_ACTION_BODY_BYTES)
        except (ValueError, OverflowError):
            return
        if remaining <= 0:
            return
        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(_MAX_DRAIN_SECONDS)
            while remaining > 0:
                chunk = self.rfile.read1(min(4096, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                self._drained_bytes = getattr(self, "_drained_bytes", 0) + len(chunk)
        except (TimeoutError, socket.timeout, OSError, ValueError):
            pass                            # best-effort only; never fail a rejection on the drain
        finally:
            try:
                self.connection.settimeout(previous_timeout)
            except OSError:
                pass

    def _json(self, code: int, body, *, headers=None):
        self._drain_unread_body()
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _single_header(self, name: str) -> str | None:
        values = self.headers.get_all(name, [])
        return values[0] if len(values) == 1 else None

    def _require_host(self) -> bool:
        expected = self.server.expected_authority
        if self._single_header("Host") != expected:
            self._json(421, {"error": "misdirected_request"})
            return False
        return True

    def _require_mutation_authority(self) -> bool:
        if self._single_header("Origin") != self.server.expected_origin:
            self._json(403, {"error": "origin_rejected"})
            return False
        supplied = self._single_header("X-SemiSkill-CSRF")
        if supplied is None or not hmac.compare_digest(supplied, self.server.csrf_token):
            self._json(403, {"error": "csrf_rejected"})
            return False
        return True

    def _read_json_object(self):
        if self.headers.get_all("Transfer-Encoding", []):
            self.close_connection = True
            self._json(400, {"error": "unsupported_transfer_encoding"})
            return _INVALID_BODY
        lengths = self.headers.get_all("Content-Length", [])
        if not lengths:
            self._json(411, {"error": "content_length_required"})
            return _INVALID_BODY
        if len(lengths) != 1 or not re.fullmatch(r"\d+", lengths[0]):
            self._json(400, {"error": "invalid_content_length"})
            return _INVALID_BODY
        if len(lengths[0]) > 20:
            self.close_connection = True
            self._json(400, {"error": "invalid_content_length"})
            return _INVALID_BODY
        try:
            length = int(lengths[0])
        except (ValueError, OverflowError):
            self.close_connection = True
            self._json(400, {"error": "invalid_content_length"})
            return _INVALID_BODY
        if length > _MAX_ACTION_BODY_BYTES:
            self.close_connection = True
            self._json(413, {"error": "request_too_large"})
            return _INVALID_BODY
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or not _JSON_CONTENT_TYPE.fullmatch(content_types[0]):
            self._json(415, {"error": "unsupported_media_type"})
            return _INVALID_BODY

        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(5)
            self._body_consumed = True      # attempted; a later drain must not re-read or re-wait
            raw = self.rfile.read(length)
        except (TimeoutError, socket.timeout, OSError):
            self.close_connection = True
            self._json(400, {"error": "incomplete_body"})
            return _INVALID_BODY
        finally:
            try:
                self.connection.settimeout(previous_timeout)
            except OSError:
                pass
        if len(raw) != length:
            self.close_connection = True
            self._json(400, {"error": "incomplete_body"})
            return _INVALID_BODY
        try:
            payload = strict_json_loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
            self._json(400, {"error": "invalid_json"})
            return _INVALID_BODY
        if not isinstance(payload, dict):
            self._json(422, {"error": "json_object_required"})
            return _INVALID_BODY
        return payload

    def _queue_error(self, exc: QueueError):
        return self._json(exc.status, {"error": exc.code})

    def _file(self, path: Path, ctype: str):
        if not path.exists():
            return self._json(404, {"error": "not found"})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._require_host():
            return None
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            return self._file(HERE / "index.html", "text/html; charset=utf-8")
        if route == "/api/state":
            try:
                return self._json(200, build_state(
                    self.server.action_queue.state_inputs,
                    None,
                ))
            except QueueError as exc:
                return self._queue_error(exc)
            except Exception:                                # noqa: BLE001
                return self._json(500, {"error": "state_unavailable"})
        if route == "/api/session":
            return self._json(200, {
                "schema_version": "semiskill.dashboard-session/v1",
                "csrf_token": self.server.csrf_token,
                "action_schema_version": action_queue.ACTION_REQUEST_SCHEMA,
                "archive_schema_version": action_queue.ARCHIVE_REQUEST_SCHEMA,
            })
        if route == "/api/inbox":
            try:
                return self._json(200, {
                    "schema_version": "semiskill.dashboard-inbox/v1",
                    "status": "available",
                    "inbox": self.server.action_queue.read(),
                })
            except QueueError as exc:
                return self._queue_error(exc)
        prefix = "/api/inbox/receipts/"
        if route.startswith(prefix):
            try:
                receipt = self.server.action_queue.receipt(route.removeprefix(prefix))
                return self._json(200, receipt) if receipt else self._json(
                    404, {"error": "not_found"}
                )
            except QueueError as exc:
                return self._queue_error(exc)
        return self._json(404, {"error": "unknown route"})

    def do_POST(self):
        self._body_consumed = False
        if not self._require_host():
            return None
        parsed = urlparse(self.path)
        route = parsed.path
        if parsed.query or parsed.params:
            return self._json(404, {"error": "unknown route"})
        if route not in {"/api/action", "/api/inbox/archive"}:
            return self._json(404, {"error": "unknown route"})
        if not self._require_mutation_authority():
            return None
        payload = self._read_json_object()
        if payload is _INVALID_BODY:
            return None
        try:
            if route == "/api/action":
                receipt = self.server.action_queue.enqueue(payload)
                return self._json(
                    202,
                    receipt,
                    headers={"Location": f"/api/inbox/receipts/{receipt['receipt_id']}"},
                )
            return self._json(200, self.server.action_queue.archive(payload))
        except QueueError as exc:
            return self._queue_error(exc)

    def do_OPTIONS(self):
        if not self._require_host():
            return None
        return self._json(405, {"error": "method_not_allowed"}, headers={"Allow": "GET, POST"})


def main():
    try:                                    # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                       # noqa: BLE001
        pass
    queue = ActionQueue(inbox_path=INBOX, model_path=MODEL)
    try:
        httpd = DashboardHTTPServer(("127.0.0.1", PORT), Handler, action_queue=queue)
    except Exception:
        queue.close()
        raise
    url = f"http://127.0.0.1:{PORT}"
    print(f"SemiSkill command centre -> {url}")
    print(f"  action queue: {INBOX}")
    print("  (buttons on the dashboard append to that file; Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
