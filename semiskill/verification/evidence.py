"""Strict, file-only validation for immutable full-suite run evidence.

This module intentionally imports no database, pytest, network or subprocess code.  Dashboard
readers follow only the fixed ``latest -> run -> output`` chain; directory recovery and test
execution belong exclusively to the producer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_SCHEMA = "semiskill.full-suite-run/v1"
LATEST_SCHEMA = "semiskill.full-suite-latest/v1"
REPORT_SCHEMA = "semiskill.pytest-report/v1"
PYTEST_PLUGIN = "semiskill.verification.pytest_reporter"
FULL_SUITE_TIMEOUT_SECONDS = 3600
MAX_RUN_BYTES = 64 * 1024
MAX_LATEST_BYTES = 8 * 1024
MAX_LOG_BYTES = 50 * 1024 * 1024

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_FIELDS = {
    "schema_version", "run_id", "started_at", "ended_at", "duration_seconds", "verdict",
    "exit_code", "result_complete", "failure_reason", "source", "database", "counts",
    "output", "runner", "credit", "run_sha256",
}
_COUNT_FIELDS = {
    "collected", "passed", "failed", "errors", "skipped", "xfailed", "xpassed", "not_run",
    "collection_errors", "deselected",
}
_SOURCE_FIELDS = {"vcs", "object_format", "commit", "tree", "clean"}
_DATABASE_FIELDS = {
    "engine", "environment", "database_name", "host", "port", "identity_sha256",
    "session_user_sha256",
}
_OUTPUT_FIELDS = {"ref", "sha256", "bytes"}
_RUNNER_FIELDS = {"entrypoint", "command", "pytest_plugin", "timeout_seconds"}
_LATEST_FIELDS = {
    "schema_version", "run_id", "run_ref", "run_sha256", "updated_at",
}


class FullSuiteEvidenceUnavailable(RuntimeError):
    """The immutable evidence chain is absent, malformed or detached from its bytes."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def document_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON value: {value}")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise FullSuiteEvidenceUnavailable("evidence_json_invalid") from exc


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FullSuiteEvidenceUnavailable("evidence_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise FullSuiteEvidenceUnavailable("evidence_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise FullSuiteEvidenceUnavailable("evidence_timestamp_invalid")
    return parsed


def _uuid(value: object) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise FullSuiteEvidenceUnavailable("evidence_run_id_invalid") from exc
    if str(parsed) != value:
        raise FullSuiteEvidenceUnavailable("evidence_run_id_invalid")
    return str(parsed)


def _plain(value: object, *, maximum: int) -> str:
    if (
        not isinstance(value, str) or not value or len(value) > maximum
        or any(ord(char) < 32 for char in value)
    ):
        raise FullSuiteEvidenceUnavailable("evidence_text_invalid")
    return value


def validate_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != _COUNT_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_counts_invalid")
    if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in value.values()):
        raise FullSuiteEvidenceUnavailable("evidence_counts_invalid")
    terminal = sum(value[key] for key in (
        "passed", "failed", "errors", "skipped", "xfailed", "xpassed", "not_run",
    ))
    if value["collected"] != terminal:
        raise FullSuiteEvidenceUnavailable("evidence_counts_do_not_conserve")
    return value


def run_digest(document: dict[str, Any]) -> str:
    basis = {key: value for key, value in document.items() if key != "run_sha256"}
    return sha256_bytes(canonical_bytes(basis))


def finalize_run(document: dict[str, Any]) -> dict[str, Any]:
    if "run_sha256" in document:
        raise ValueError("run document is already finalized")
    finalized = dict(document)
    finalized["run_sha256"] = run_digest(finalized)
    validate_run(finalized)
    return finalized


def validate_run(value: object, *, raw: bytes | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _RUN_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_run_shape_invalid")
    if value.get("schema_version") != RUN_SCHEMA or value.get("credit") != "none":
        raise FullSuiteEvidenceUnavailable("evidence_run_contract_invalid")
    run_id = _uuid(value.get("run_id"))
    started = parse_timestamp(value.get("started_at"))
    ended = parse_timestamp(value.get("ended_at"))
    if ended < started:
        raise FullSuiteEvidenceUnavailable("evidence_time_order_invalid")
    duration = value.get("duration_seconds")
    if (
        not isinstance(duration, (int, float)) or isinstance(duration, bool)
        or not math.isfinite(duration) or duration < 0
    ):
        raise FullSuiteEvidenceUnavailable("evidence_duration_invalid")
    if value.get("verdict") not in {"pass", "fail"}:
        raise FullSuiteEvidenceUnavailable("evidence_verdict_invalid")
    exit_code = value.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool) or not 0 <= exit_code <= 255:
        raise FullSuiteEvidenceUnavailable("evidence_exit_code_invalid")
    complete = value.get("result_complete")
    reason = value.get("failure_reason")
    if not isinstance(complete, bool):
        raise FullSuiteEvidenceUnavailable("evidence_result_state_invalid")
    if complete and reason is not None:
        raise FullSuiteEvidenceUnavailable("evidence_result_state_invalid")
    if not complete:
        _plain(reason, maximum=80)

    source = value.get("source")
    if not isinstance(source, dict) or set(source) != _SOURCE_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_source_invalid")
    object_format = source.get("object_format")
    object_pattern = _SHA1 if object_format == "sha1" else re.compile(r"^[0-9a-f]{64}$")
    if (
        source.get("vcs") != "git" or object_format not in {"sha1", "sha256"}
        or source.get("clean") is not True or not isinstance(source.get("commit"), str)
        or not object_pattern.fullmatch(source["commit"])
        or not isinstance(source.get("tree"), str) or not object_pattern.fullmatch(source["tree"])
    ):
        raise FullSuiteEvidenceUnavailable("evidence_source_invalid")

    database = value.get("database")
    if not isinstance(database, dict) or set(database) != _DATABASE_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_database_invalid")
    database_name = _plain(database.get("database_name"), maximum=128)
    host = _plain(database.get("host"), maximum=255)
    port = database.get("port")
    if (
        database.get("engine") != "postgresql" or database.get("environment") != "test"
        or not database_name.lower().endswith("_test")
        or not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535
        or not isinstance(database.get("identity_sha256"), str)
        or not _SHA256.fullmatch(database["identity_sha256"])
        or not isinstance(database.get("session_user_sha256"), str)
        or not _SHA256.fullmatch(database["session_user_sha256"])
    ):
        raise FullSuiteEvidenceUnavailable("evidence_database_invalid")
    del host

    counts = validate_counts(value.get("counts"))
    # Pytest's own zero exit remains authoritative for expected skips/xfails and non-strict XPASS.
    # We retain those counts visibly; only incomplete selection/execution or a non-zero exit blocks.
    should_pass = (
        complete and exit_code == 0 and counts["collected"] > 0
        and counts["failed"] == 0 and counts["errors"] == 0
        and counts["not_run"] == 0 and counts["collection_errors"] == 0
        and counts["deselected"] == 0
    )
    if (value.get("verdict") == "pass") != should_pass:
        raise FullSuiteEvidenceUnavailable("evidence_verdict_contradiction")

    output = value.get("output")
    if not isinstance(output, dict) or set(output) != _OUTPUT_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_output_invalid")
    expected_output_ref = f"outputs/{run_id}.log"
    output_bytes = output.get("bytes")
    if (
        output.get("ref") != expected_output_ref
        or not isinstance(output.get("sha256"), str) or not _SHA256.fullmatch(output["sha256"])
        or not isinstance(output_bytes, int) or isinstance(output_bytes, bool)
        or not 0 <= output_bytes <= MAX_LOG_BYTES
    ):
        raise FullSuiteEvidenceUnavailable("evidence_output_invalid")

    runner = value.get("runner")
    if not isinstance(runner, dict) or set(runner) != _RUNNER_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_runner_invalid")
    command = runner.get("command")
    if (
        runner.get("entrypoint") != "semiskill verify-full-suite"
        or runner.get("pytest_plugin") != PYTEST_PLUGIN
        or runner.get("timeout_seconds") != FULL_SUITE_TIMEOUT_SECONDS
        or not isinstance(command, list) or len(command) != 16
        or not all(isinstance(item, str) and item for item in command)
        or command[1:] != [
            "-m", "pytest", "-q", "-c", "pyproject.toml", "-o", "addopts=",
            "--strict-config", "--strict-markers", "-p", "no:cacheprovider", "--color=no",
            "tests", "-p", PYTEST_PLUGIN,
        ]
    ):
        raise FullSuiteEvidenceUnavailable("evidence_runner_invalid")

    if not isinstance(value.get("run_sha256"), str) or not _SHA256.fullmatch(value["run_sha256"]):
        raise FullSuiteEvidenceUnavailable("evidence_run_hash_invalid")
    if not hmac.compare_digest(value["run_sha256"], run_digest(value)):
        raise FullSuiteEvidenceUnavailable("evidence_run_hash_mismatch")
    if raw is not None and raw != document_bytes(value):
        raise FullSuiteEvidenceUnavailable("evidence_run_not_canonical")
    return value


def latest_document(run: dict[str, Any]) -> dict[str, Any]:
    validate_run(run)
    return {
        "schema_version": LATEST_SCHEMA,
        "run_id": run["run_id"],
        "run_ref": f"runs/{run['run_id']}.json",
        "run_sha256": run["run_sha256"],
        "updated_at": run["ended_at"],
    }


def validate_latest(value: object, *, raw: bytes | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _LATEST_FIELDS:
        raise FullSuiteEvidenceUnavailable("evidence_latest_shape_invalid")
    run_id = _uuid(value.get("run_id"))
    if (
        value.get("schema_version") != LATEST_SCHEMA
        or value.get("run_ref") != f"runs/{run_id}.json"
        or not isinstance(value.get("run_sha256"), str)
        or not _SHA256.fullmatch(value["run_sha256"])
    ):
        raise FullSuiteEvidenceUnavailable("evidence_latest_contract_invalid")
    parse_timestamp(value.get("updated_at"))
    if raw is not None and raw != document_bytes(value):
        raise FullSuiteEvidenceUnavailable("evidence_latest_not_canonical")
    return value


def _is_linklike(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
    except OSError:
        return True


def _read_regular(path: Path, *, maximum: int) -> bytes:
    try:
        if _is_linklike(path) or not path.is_file():
            raise FullSuiteEvidenceUnavailable("evidence_file_unavailable")
        before = path.stat()
        size = before.st_size
        if not 0 <= size <= maximum:
            raise FullSuiteEvidenceUnavailable("evidence_file_size_invalid")
        if before.st_nlink != 1:
            raise FullSuiteEvidenceUnavailable("evidence_file_link_invalid")
        raw = path.read_bytes()
        after = path.stat()
    except FullSuiteEvidenceUnavailable:
        raise
    except OSError as exc:
        raise FullSuiteEvidenceUnavailable("evidence_file_unavailable") from exc
    witness = lambda item: (  # noqa: E731 - compact immutable file witness
        item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns, item.st_nlink,
    )
    if len(raw) != size or witness(before) != witness(after):
        raise FullSuiteEvidenceUnavailable("evidence_file_changed")
    return raw


def read_latest_run(root: str | Path) -> dict[str, Any]:
    """Read one fixed evidence chain. Never glob, repair, execute, connect or fetch."""
    base = Path(root)
    try:
        if (
            _is_linklike(base) or not base.is_dir()
            or base.resolve(strict=True) != base.absolute()
            or _is_linklike(base / "runs") or not (base / "runs").is_dir()
            or _is_linklike(base / "outputs") or not (base / "outputs").is_dir()
        ):
            raise FullSuiteEvidenceUnavailable("evidence_root_unavailable")
    except OSError as exc:
        raise FullSuiteEvidenceUnavailable("evidence_root_unavailable") from exc
    in_progress = base / "in-progress.json"
    if in_progress.exists():
        _read_regular(in_progress, maximum=MAX_LATEST_BYTES)
        raise FullSuiteEvidenceUnavailable("evidence_run_in_progress")
    latest_path = base / "latest.json"
    latest_raw = _read_regular(latest_path, maximum=MAX_LATEST_BYTES)
    latest = validate_latest(strict_json_bytes(latest_raw), raw=latest_raw)
    run_path = base / "runs" / f"{latest['run_id']}.json"
    run_raw = _read_regular(run_path, maximum=MAX_RUN_BYTES)
    run = validate_run(strict_json_bytes(run_raw), raw=run_raw)
    if (
        run["run_id"] != latest["run_id"]
        or run["run_sha256"] != latest["run_sha256"]
        or run["ended_at"] != latest["updated_at"]
    ):
        raise FullSuiteEvidenceUnavailable("evidence_latest_detached")
    output_path = base / "outputs" / f"{run['run_id']}.log"
    output_raw = _read_regular(output_path, maximum=MAX_LOG_BYTES)
    if len(output_raw) != run["output"]["bytes"] or not hmac.compare_digest(
        sha256_bytes(output_raw), run["output"]["sha256"],
    ):
        raise FullSuiteEvidenceUnavailable("evidence_output_hash_mismatch")
    if _read_regular(latest_path, maximum=MAX_LATEST_BYTES) != latest_raw:
        raise FullSuiteEvidenceUnavailable("evidence_changed_during_read")
    if _read_regular(run_path, maximum=MAX_RUN_BYTES) != run_raw:
        raise FullSuiteEvidenceUnavailable("evidence_changed_during_read")
    if in_progress.exists():
        raise FullSuiteEvidenceUnavailable("evidence_run_in_progress")
    return run
