"""SemiSkill command centre — a local, dependency-free dashboard server.

Serves `index.html` and a live `/api/state` assembled from real signals:
  * repo      — git history, tracked files, module LOC, test inventory
  * runtime   — read-only Postgres artifact-store liveness
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

import json
import hashlib
import hmac
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
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

PORT = int(os.environ.get("SEMISKILL_DASHBOARD_PORT", "8899"))

_DEFAULT_SCOREBOARD_MAX_AGE_SECONDS = 900
_DEFAULT_PROGRESS_MAX_AGE_SECONDS = 300
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
_POST_MIGRATION_ATTESTATION_KEYS = frozenset({
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
_CURRENT_SCHEMA_ATTESTATION_KEYS = (
    _POST_MIGRATION_ATTESTATION_KEYS - {"projection_and_policy_start_empty"}
)
_MAX_ACTION_BODY_BYTES = 16_384
_JSON_CONTENT_TYPE = re.compile(
    r'^application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$',
    re.IGNORECASE,
)
_INVALID_BODY = object()


class DashboardSnapshotRejected(RuntimeError):
    """Controlled fail-closed reason; raw source/database exceptions never cross the API."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sh(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
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
    if (
        not isinstance(migration_database, dict)
        or migration_database.get("environment") != sources["database"]["environment"]
        or migration_database.get("database_name") != sources["database"]["database_name"]
        or migration.get("tracker", {}).get("exact") is not True
        or migration.get("schema", {}).get("status") != "verified"
    ):
        raise DashboardSnapshotRejected("schema_witness_mismatch")
    final_commit, final_dirty = _repository_identity()
    if final_commit != current_commit or final_dirty or final_dirty != current_dirty:
        raise DashboardSnapshotRejected("source_changed_during_validation")
    return {
        "status": "verified",
        "snapshot_id": live["snapshot_id"],
        "source_commit": current_commit,
        "database_identity_sha256": live["sources"]["database"]["identity_sha256"],
        "migration_tracker_sha256": migration["tracker"]["sha256"],
    }


# ---------------------------------------------------------------- signals

def repo_signals() -> dict:
    rc, log = _sh(["git", "log", "--format=%h|%aI|%s", "-n", "80"])
    commits = []
    if rc == 0:
        for line in log.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                sha, iso, subject = parts
                kind = "rotate" if subject.startswith("rotate:") else (
                    "feat" if subject.startswith(("feat:", "fix:")) else "wip")
                phase = ""
                m = re.search(r"\b([A-G]|P0|G)-(\d{3})\b", subject)
                if m:
                    phase = m.group(1)
                commits.append({"sha": sha, "date": iso, "subject": subject,
                                "kind": kind, "phase": phase})

    rc, status = _sh(["git", "status", "--porcelain"])
    dirty = [line for line in status.splitlines() if line.strip()] if rc == 0 else []
    rc, branch = _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    modules, tests = [], []
    for p in sorted((ROOT / "semiskill").rglob("*.py")):
        loc = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        if loc:
            modules.append({"path": p.relative_to(ROOT).as_posix(), "loc": loc,
                            "layer": _layer_of(p.relative_to(ROOT).as_posix())})
    test_re = re.compile(r"^\s*(?:async\s+)?def\s+test_", re.M)
    for p in sorted((ROOT / "tests").rglob("test_*.py")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        n = len(test_re.findall(txt))
        if n:
            rel = p.relative_to(ROOT).as_posix()
            tests.append({"path": rel, "count": n, "group": rel.split("/")[1]})

    return {"commits": commits, "branch": branch.strip(), "dirty": len(dirty),
            "dirty_files": dirty[:20], "modules": modules, "tests": tests,
            "total_tests": sum(t["count"] for t in tests),
            "test_count_kind": "static_function_definitions",
            "total_loc": sum(m["loc"] for m in modules)}


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


def state_files() -> dict:
    out = {}
    for name in ("STATUS.md", "MEMORY.md", "BLOCKERS.md"):
        p = ROOT / name
        out[name] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    status = out["STATUS.md"]
    memory = out["MEMORY.md"]
    phase = ""
    m = re.search(r"^## Current Phase\s*\n(.+)$", memory, re.M)
    if m:
        phase = m.group(1).strip()
    right_now = ""
    m = re.search(r"^## Right now\s*\n((?:.+\n?)+?)(?:\n##|\Z)", status, re.M)
    if m:
        right_now = m.group(1).strip()
    gaps = re.findall(r"^- (Stage.+|pgvector.+|SharePoint.+|Phase G.+)$", status, re.M)
    steps = re.findall(r"^- \[([^\]]+)\]\s+(\S+)\s+status:\s*(\w+)\s*\n\s+what:\s*(.+)$",
                       memory, re.M)
    # strip HTML comments first — BLOCKERS.md keeps its entry template commented out
    live_blockers = re.sub(r"<!--.*?-->", "", out["BLOCKERS.md"], flags=re.S)
    blockers = [
        line.strip() for line in live_blockers.splitlines() if line.startswith("## [BLK-")
    ]
    return {"phase": phase, "right_now": right_now, "gaps": gaps,
            "steps": [{"id": a, "ts": b, "status": c, "what": d} for a, b, c, d in steps],
            "blockers": blockers}


def runtime_signals() -> dict:
    """Read-only database liveness; this probe starts no process or HTTP request."""
    out = {"checked_at": _now()}

    db = {"status": "down", "detail": ""}
    try:
        import psycopg                                        # noqa: PLC0415
        from semiskill.config import Config                   # noqa: PLC0415
        dsn = Config.from_env().database_url
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cur:
                cur.execute("select count(*) from artifacts")
                total = cur.fetchone()[0]
                cur.execute("select artifact_type, count(*) from artifacts group by 1 order by 2 desc")
                by_type = [{"type": t, "n": n} for t, n in cur.fetchall()]
        db = {"status": "up", "detail": "", "artifacts": total, "by_type": by_type}
    except Exception:                                         # noqa: BLE001
        db["detail"] = "database probe unavailable"
    out["db"] = db
    return out


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
        database_name = conn.execute("SELECT current_database()").fetchone()[0]
        tracker_rows = [
            {"filename": filename, "sha256": checksum}
            for filename, checksum in conn.execute(
                "SELECT filename,sha256 FROM public.schema_migrations ORDER BY filename"
            ).fetchall()
        ]
        audits = conn.execute(
            "SELECT artifact_id,timestamp_start,source_system,actor_kind,permissions_label,"
            "objective_tag,ground_truth_ref,payload FROM public.artifacts "
            "WHERE artifact_type='gate_decision' "
            "AND payload->>'schema_version'='migration-checksum-adoption/v1' "
            "ORDER BY timestamp_start,artifact_id LIMIT 2"
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
    (
        artifact_id, timestamp_start, source_system, actor_kind, permissions_label,
        objective_tag, ground_truth_ref, payload,
    ) = audits[0]
    if not isinstance(payload, dict):
        raise DashboardSnapshotRejected("adoption_witness_invalid")
    plan_sha256 = payload.get("plan_sha256")
    source_commit = payload.get("source_commit")
    database = payload.get("database")
    post = payload.get("post_migration_attestations")
    if (
        source_system != "cli"
        or actor_kind != "human"
        or permissions_label != "need-to-know"
        or objective_tag != "compliance"
        or ground_truth_ref != plan_sha256
        or payload.get("schema_version") != "migration-checksum-adoption/v1"
        or payload.get("decision") != "adopt_and_apply"
        or payload.get("adoption_id") != str(artifact_id)
        or payload.get("environment") != environment
        or not isinstance(database, dict)
        or database.get("database_name") != database_name
        or payload.get("final_tracker") != repository_rows
        or not isinstance(post, dict)
        or set(post) != _POST_MIGRATION_ATTESTATION_KEYS
        or any(value is not True for value in post.values())
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(plan_sha256))
        or not re.fullmatch(r"[0-9a-f]{40}", str(source_commit))
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


def migration_witness_signal() -> dict:
    """Return a sanitized live tracker/adoption projection; never raw auth or audit payloads."""
    observed_at = _now()
    unavailable = {
        "status": "unavailable", "reason": "database_unavailable",
        "observed_at": observed_at, "tracker": None, "schema": None, "adoption": None,
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
        ):
            raise DashboardSnapshotRejected("schema_witness_mismatch")
        adoption = _project_adoption_witness(
            database_state["audits"], repository_rows=repository_rows,
            environment=environment, database_name=database_name,
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
    return {
        "status": "verified", "reason": None, "observed_at": observed_at,
        "database": {"environment": environment, "database_name": database_name},
        "tracker": {
            "repository_count": len(repository_rows),
            "tracked_count": len(tracker_rows),
            "latest_migration": tracker_rows[-1]["filename"],
            "sha256": _migration_tracker_sha256(tracker_rows),
            "exact": True,
        },
        "schema": {
            "status": "verified",
            "passed": len(_CURRENT_SCHEMA_ATTESTATION_KEYS),
            "total": len(_CURRENT_SCHEMA_ATTESTATION_KEYS),
        },
        "projection_rows": database_state["projection_rows"],
        "adoption": adoption,
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
                status="partial",
                note=("Harness tests and adversarial inputs exist; no immutable execution result "
                      "is bound to the current corpus."),
            )
    for item in model.get("launch_checklist", []):
        if item.get("id") == "LC-11":
            item.update(item="Authoritative corpus-bound red-team execution result", status="todo")
    for risk in model.get("risks", []):
        if risk.get("id") == "R-07":
            risk["detail"] = (
                "The current red-team escape result is unavailable; the block rate on honest "
                "skills is also unmeasured, and over-blocking kills adoption."
            )
    for metric in model.get("gtm", {}).get("metrics", []):
        if metric.get("id") == "M-05":
            metric.update(
                current="unmeasured",
                source="authoritative corpus-bound red-team result artifact (not available)",
            )


def adrs() -> list[dict]:
    p = ROOT / "DECISIONS.md"
    if not p.exists():
        return []
    return [{"id": i, "title": t.strip()} for i, t in
            re.findall(r"^## \[(ADR-\d+)\]\s*(.+)$", p.read_text(encoding="utf-8"), re.M)]


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


def read_public_templates() -> list[dict]:
    templates, registry_sha256 = action_queue._load_templates(MODEL)
    if action_queue._load_model_manifest(MODEL.with_suffix(".sha256")) != registry_sha256:
        raise action_queue.QueueUnavailable("template manifest mismatch")
    return [
        {
            "id": template["template_id"],
            "group": template["group"],
            "label": template["title"],
            "description": (
                f"Hash-bound schema-v1 {template['group']} request; the server resolves the "
                "integrity-pinned prompt when queued."
            ),
        }
        for template in templates.values()
    ]


def build_state(inbox_reader=None, template_reader=None) -> dict:
    inbox_reader = inbox_reader or read_inbox
    template_reader = template_reader or read_public_templates
    model = strict_json_loads(MODEL.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(model, dict):
        raise action_queue.QueueUnavailable("dashboard model invalid")
    model["actions"] = template_reader()
    migration = migration_witness_signal()
    canonical = canonical_snapshot_signals(migration=migration)
    redteam = redteam_signal()
    _remove_unexecuted_redteam_credit(model, redteam)
    return {
        "generated_at": _now(),
        "model": model,
        "repo": repo_signals(),
        "state": state_files(),
        "runtime": runtime_signals(),
        "scoreboard": canonical["scoreboard"],
        "progress": canonical["progress"],
        "migration": migration,
        "redteam": redteam,
        "adrs": adrs(),
        "inbox": inbox_reader(),
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

    def _json(self, code: int, body, *, headers=None):
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
                    self.server.action_queue.read,
                    self.server.action_queue.public_templates,
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
