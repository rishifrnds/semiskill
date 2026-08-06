"""Produce immutable, source-bound evidence for the fixed serial Python test suite."""
from __future__ import annotations

import contextlib
import hmac
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from semiskill.verification.evidence import (
    FULL_SUITE_TIMEOUT_SECONDS,
    MAX_LOG_BYTES,
    PYTEST_PLUGIN,
    REPORT_SCHEMA,
    RUN_SCHEMA,
    FullSuiteEvidenceUnavailable,
    canonical_bytes,
    document_bytes,
    finalize_run,
    latest_document,
    parse_timestamp,
    sha256_bytes,
    strict_json_bytes,
    validate_counts,
    validate_latest,
    validate_run,
)

_COMMAND_TAIL = [
    "-m", "pytest", "-q", "-c", "pyproject.toml", "-o", "addopts=",
    "--strict-config", "--strict-markers", "-p", "no:cacheprovider", "--color=no",
    "tests", "-p", PYTEST_PLUGIN,
]
_DATABASE_ENVIRONMENT_KEYS = (
    "TEST_DATABASE_URL", "DATABASE_URL", "SEMISKILL_APPROVAL_DATABASE_URL",
    "SEMISKILL_REVIEW_COORDINATOR_DATABASE_URL", "SEMISKILL_EXPORT_DATABASE_URL",
)
_ADVISORY_LOCK_ID = 8_341_917_441_246_441_003
_RUN_FILE = re.compile(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.json$")
_LOG_FILE = re.compile(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.log$")


class FullSuiteRefused(RuntimeError):
    """The runner cannot establish a safe, exact execution/evidence boundary."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _git(repo_root: Path, *args: str) -> str:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("GIT_"):
            environment.pop(key, None)
    environment.update(
        GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
    )
    try:
        completed = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *args],
            cwd=repo_root, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FullSuiteRefused("repository_probe_unavailable") from exc
    if completed.returncode != 0:
        raise FullSuiteRefused("repository_probe_unavailable")
    return completed.stdout


def repository_identity(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    try:
        top = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    except (OSError, RuntimeError) as exc:
        raise FullSuiteRefused("repository_probe_unavailable") from exc
    if top != root:
        raise FullSuiteRefused("repository_root_mismatch")
    object_format = _git(root, "rev-parse", "--show-object-format").strip()
    commit = _git(root, "rev-parse", "HEAD").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    width = 40 if object_format == "sha1" else 64 if object_format == "sha256" else 0
    if (
        width == 0 or not re.fullmatch(rf"[0-9a-f]{{{width}}}", commit)
        or not re.fullmatch(rf"[0-9a-f]{{{width}}}", tree)
    ):
        raise FullSuiteRefused("repository_identity_invalid")
    return {
        "vcs": "git", "object_format": object_format, "commit": commit, "tree": tree,
        "clean": status == "",
    }


def _database_identity(conn, *, expected_database: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT pg_catalog.current_database(),session_user,"
        "coalesce(pg_catalog.inet_server_addr()::text,'local-socket'),"
        "coalesce(pg_catalog.inet_server_port(),0),"
        "(SELECT oid::text FROM pg_catalog.pg_database "
        "WHERE datname=pg_catalog.current_database()),"
        "pg_catalog.current_setting('server_version_num')"
    ).fetchone()
    database_name, session_user, host, port, database_oid, server_version = row
    if database_name != expected_database or not database_name.lower().endswith("_test"):
        raise FullSuiteRefused("test_database_identity_mismatch")
    private_identity = {
        "engine": "postgresql", "environment": "test", "database_name": database_name,
        "host": host, "port": int(port), "database_oid": database_oid,
        "server_version": server_version, "session_user": session_user,
    }
    public_identity = {
        "engine": "postgresql", "environment": "test", "database_name": database_name,
        "host": host, "port": int(port),
        "identity_sha256": sha256_bytes(canonical_bytes(private_identity)),
        "session_user_sha256": sha256_bytes(session_user.encode("utf-8")),
    }
    return public_identity


class TestDatabaseLease:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None
        self.expected_database = ""

    def __enter__(self):
        try:
            import psycopg  # noqa: PLC0415
            from psycopg.conninfo import conninfo_to_dict  # noqa: PLC0415

            self.expected_database = conninfo_to_dict(self.dsn).get("dbname", "")
            if not self.expected_database.lower().endswith("_test"):
                raise FullSuiteRefused("test_database_name_invalid")
            self.conn = psycopg.connect(self.dsn, connect_timeout=3, autocommit=True)
            self.conn.execute("SET search_path TO pg_catalog, pg_temp")
            locked = self.conn.execute(
                "SELECT pg_catalog.pg_try_advisory_lock(%s)", (_ADVISORY_LOCK_ID,),
            ).fetchone()[0]
            if locked is not True:
                raise FullSuiteRefused("test_database_already_leased")
            self.observe()
            return self
        except FullSuiteRefused:
            self.close()
            raise
        except Exception as exc:  # DSNs and database diagnostics never cross the boundary
            self.close()
            raise FullSuiteRefused("test_database_unavailable") from exc

    def observe(self) -> dict[str, Any]:
        if self.conn is None:
            raise FullSuiteRefused("test_database_unavailable")
        try:
            return _database_identity(self.conn, expected_database=self.expected_database)
        except FullSuiteRefused:
            raise
        except Exception as exc:
            raise FullSuiteRefused("test_database_unavailable") from exc

    def close(self) -> None:
        if self.conn is None:
            return
        try:
            self.conn.execute("SELECT pg_catalog.pg_advisory_unlock(%s)", (_ADVISORY_LOCK_ID,))
        except Exception:
            pass
        self.conn.close()
        self.conn = None

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError) as exc:
        handle.close()
        raise FullSuiteRefused("full_suite_runner_already_active") from exc
    return handle


def _release_lock(handle) -> None:
    if handle is None or handle.closed:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_temp(parent: Path, prefix: str, data: bytes) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=parent, prefix=prefix, suffix=".tmp", delete=False,
    )
    path = Path(handle.name)
    with handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _move_no_replace(source: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(str(target))
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
        if not move_file(str(source), str(target), 0x00000008):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.link(source, target)
        source.unlink()
        _fsync_directory(target.parent)


def _write_no_replace(path: Path, data: bytes) -> None:
    temporary = _write_temp(path.parent, f".full-suite-{path.name}-", data)
    try:
        _move_no_replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_replace(path: Path, data: bytes) -> None:
    temporary = _write_temp(path.parent, f".full-suite-{path.name}-", data)
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            move_file = kernel32.MoveFileExW
            move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            move_file.restype = ctypes.c_int
            replace_existing = 0x00000001
            write_through = 0x00000008
            if not move_file(str(temporary), str(path), replace_existing | write_through):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            os.replace(temporary, path)
            _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _plain_directory(path: Path) -> None:
    try:
        if path.exists() and (
            path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
            or not path.is_dir()
        ):
            raise FullSuiteRefused("evidence_path_invalid")
        path.mkdir(parents=True, exist_ok=True)
    except FullSuiteRefused:
        raise
    except OSError as exc:
        raise FullSuiteRefused("evidence_path_unavailable") from exc


def _read_run(path: Path) -> dict[str, Any]:
    try:
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1
            or path.stat().st_size > 64 * 1024
        ):
            raise FullSuiteRefused("immutable_run_invalid")
        raw = path.read_bytes()
        return validate_run(strict_json_bytes(raw), raw=raw)
    except (OSError, FullSuiteEvidenceUnavailable) as exc:
        raise FullSuiteRefused("immutable_run_invalid") from exc


def _read_in_progress(path: Path) -> dict[str, Any]:
    try:
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1
            or path.stat().st_size > 64 * 1024
        ):
            raise FullSuiteRefused("in_progress_marker_invalid")
        raw = path.read_bytes()
        document = strict_json_bytes(raw)
        required = {
            "schema_version", "run_id", "started_at", "source", "database", "runner", "credit",
        }
        if (
            not isinstance(document, dict) or set(document) != required
            or document.get("schema_version") != "semiskill.full-suite-in-progress/v1"
            or document.get("credit") != "none" or raw != document_bytes(document)
            or str(uuid.UUID(str(document.get("run_id")))) != document.get("run_id")
        ):
            raise FullSuiteRefused("in_progress_marker_invalid")
        parse_timestamp(document.get("started_at"))
        return document
    except FullSuiteRefused:
        raise
    except (OSError, ValueError, FullSuiteEvidenceUnavailable) as exc:
        raise FullSuiteRefused("in_progress_marker_invalid") from exc


def _quarantine_orphan(path: Path, orphan_dir: Path) -> None:
    target = orphan_dir / path.name
    if target.exists():
        raise FullSuiteRefused("orphan_output_collision")
    _move_no_replace(path, target)


def recover_evidence(root: Path) -> None:
    """Producer-only recovery: preserve interrupted failures and repair only the latest pointer."""
    runs = root / "runs"
    outputs = root / "outputs"
    orphans = root / "orphans"
    for directory in (root, runs, outputs, orphans):
        _plain_directory(directory)
        for candidate in directory.iterdir():
            if candidate.name.startswith(".full-suite-") and candidate.name.endswith(".tmp"):
                if candidate.is_symlink() or not candidate.is_file():
                    raise FullSuiteRefused("evidence_temp_invalid")
                candidate.unlink()
    for path in orphans.iterdir():
        if _LOG_FILE.fullmatch(path.name) is None or path.is_symlink() or not path.is_file():
            raise FullSuiteRefused("unexpected_orphan_file")

    run_documents: dict[str, dict[str, Any]] = {}
    for path in runs.iterdir():
        match = _RUN_FILE.fullmatch(path.name)
        if match is None:
            raise FullSuiteRefused("unexpected_run_file")
        document = _read_run(path)
        if document["run_id"] != match.group(1):
            raise FullSuiteRefused("immutable_run_identity_mismatch")
        run_documents[document["run_id"]] = document

    output_paths: dict[str, Path] = {}
    for path in outputs.iterdir():
        match = _LOG_FILE.fullmatch(path.name)
        if (
            match is None or path.is_symlink() or not path.is_file()
            or path.stat().st_nlink != 1 or path.stat().st_size > MAX_LOG_BYTES
        ):
            raise FullSuiteRefused("unexpected_output_file")
        output_paths[match.group(1)] = path

    in_progress = root / "in-progress.json"
    forced_latest_id = None
    if in_progress.exists():
        marker = _read_in_progress(in_progress)
        marker_id = marker["run_id"]
        forced_latest_id = marker_id
        if marker_id not in run_documents:
            marker_output = output_paths.get(marker_id)
            if marker_output is None:
                marker_output = outputs / f"{marker_id}.log"
                _write_no_replace(
                    marker_output,
                    b"[semiskill] prior full-suite producer was interrupted before completion\n",
                )
                output_paths[marker_id] = marker_output
            output_raw = marker_output.read_bytes()
            ended_at = _utc_now()
            duration = max(
                0.0,
                (parse_timestamp(ended_at) - parse_timestamp(marker["started_at"])).total_seconds(),
            )
            interrupted = finalize_run({
                "schema_version": RUN_SCHEMA,
                "run_id": marker_id,
                "started_at": marker["started_at"],
                "ended_at": ended_at,
                "duration_seconds": round(duration, 6),
                "verdict": "fail",
                "exit_code": 255,
                "result_complete": False,
                "failure_reason": "runner_interrupted",
                "source": marker["source"],
                "database": marker["database"],
                "counts": _empty_counts(),
                "output": {
                    "ref": f"outputs/{marker_id}.log", "sha256": sha256_bytes(output_raw),
                    "bytes": len(output_raw),
                },
                "runner": marker["runner"],
                "credit": "none",
            })
            _write_no_replace(runs / f"{marker_id}.json", document_bytes(interrupted))
            run_documents[marker_id] = interrupted
    for run_id in sorted(set(output_paths) - set(run_documents)):
        _quarantine_orphan(output_paths[run_id], orphans)
        output_paths.pop(run_id)
    if set(run_documents) != set(output_paths):
        raise FullSuiteRefused("immutable_output_missing")
    for run_id, document in run_documents.items():
        raw = output_paths[run_id].read_bytes()
        if (
            len(raw) != document["output"]["bytes"]
            or not hmac.compare_digest(sha256_bytes(raw), document["output"]["sha256"])
        ):
            raise FullSuiteRefused("immutable_output_mismatch")

    latest_path = root / "latest.json"
    if not run_documents:
        if latest_path.exists():
            raise FullSuiteRefused("latest_pointer_detached")
        return
    if forced_latest_id is not None:
        authoritative = run_documents[forced_latest_id]
    else:
        try:
            if latest_path.is_symlink() or not latest_path.is_file():
                raise FullSuiteRefused("latest_pointer_missing")
            latest_raw = latest_path.read_bytes()
            latest = validate_latest(strict_json_bytes(latest_raw), raw=latest_raw)
            authoritative = run_documents.get(latest["run_id"])
            if (
                authoritative is None or authoritative["run_sha256"] != latest["run_sha256"]
                or authoritative["ended_at"] != latest["updated_at"]
            ):
                raise FullSuiteRefused("latest_pointer_detached")
        except FullSuiteRefused:
            raise
        except (OSError, FullSuiteEvidenceUnavailable) as exc:
            raise FullSuiteRefused("latest_pointer_invalid") from exc
    expected = document_bytes(latest_document(authoritative))
    if not latest_path.exists() or latest_path.read_bytes() != expected:
        _write_replace(latest_path, expected)
    if in_progress.exists():
        in_progress.unlink()
        _fsync_directory(root)


def child_environment(dsn: str, *, report_path: Path, nonce: str) -> dict[str, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("SEMISKILL_") or key.startswith("PYTEST_") or key.startswith("GIT_"):
            environment.pop(key, None)
    for key in (
        "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "PYTHONWARNINGS",
        "COVERAGE_PROCESS_START", "DATABASE_URL",
    ):
        environment.pop(key, None)
    environment.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "SEMISKILL_ENVIRONMENT": "test",
        "SEMISKILL_FULL_SUITE_REPORT_PATH": str(report_path),
        "SEMISKILL_FULL_SUITE_RUN_NONCE": nonce,
    })
    for key in _DATABASE_ENVIRONMENT_KEYS:
        environment[key] = dsn
    return environment


def require_configured_test_database(dsn: str, *, expected_database: str) -> None:
    if not isinstance(expected_database, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]*_test", expected_database,
    ):
        raise FullSuiteRefused("expected_test_database_invalid")
    try:
        from psycopg.conninfo import conninfo_to_dict  # noqa: PLC0415

        configured = conninfo_to_dict(dsn).get("dbname", "")
    except Exception as exc:
        raise FullSuiteRefused("test_database_configuration_invalid") from exc
    if configured != expected_database:
        raise FullSuiteRefused("test_database_configuration_mismatch")


def _normalize_exit_code(value: int) -> int:
    return min(255, 128 + abs(value)) if value < 0 else min(255, value)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        taskkill = Path(system_root) / "System32" / "taskkill.exe"
        try:
            subprocess.run(
                [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            with contextlib.suppress(OSError):
                process.kill()
    else:
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        process.wait(timeout=10)


def execute_pytest(
    command: list[str], *, repo_root: Path, environment: dict[str, str], log_path: Path,
) -> tuple[int, str | None]:
    try:
        with log_path.open("xb") as handle:
            try:
                popen_options: dict[str, Any] = {}
                if os.name == "nt":
                    popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    popen_options["start_new_session"] = True
                process = subprocess.Popen(
                    command, cwd=repo_root, env=environment, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_options,
                )
            except OSError:
                handle.write(b"[semiskill] test process could not be started\n")
                failure_reason = "runner_launch_failed"
                exit_code = 255
            else:
                exceeded = threading.Event()
                drain_errors: list[BaseException] = []

                def drain_output() -> None:
                    written = 0
                    try:
                        assert process.stdout is not None
                        while True:
                            chunk = process.stdout.read(64 * 1024)
                            if not chunk:
                                break
                            remaining = max(0, MAX_LOG_BYTES - written)
                            if remaining:
                                part = chunk[:remaining]
                                handle.write(part)
                                written += len(part)
                            if len(chunk) > remaining:
                                exceeded.set()
                    except BaseException as exc:  # propagated on the controller thread
                        drain_errors.append(exc)

                drain = threading.Thread(target=drain_output, name="full-suite-output", daemon=True)
                drain.start()
                try:
                    return_code = process.wait(timeout=FULL_SUITE_TIMEOUT_SECONDS)
                    failure_reason = None
                    exit_code = _normalize_exit_code(return_code)
                except subprocess.TimeoutExpired:
                    _terminate_process_tree(process)
                    failure_reason = "runner_timeout"
                    exit_code = 124
                drain.join(timeout=15)
                if drain.is_alive():
                    _terminate_process_tree(process)
                    drain.join(timeout=5)
                if drain.is_alive() or drain_errors:
                    raise FullSuiteRefused("test_output_drain_failed")
                if exceeded.is_set():
                    failure_reason = "test_output_limit_exceeded"
                    exit_code = 125
            handle.flush()
            os.fsync(handle.fileno())
        return exit_code, failure_reason
    except OSError as exc:
        raise FullSuiteRefused("test_output_unavailable") from exc


def _empty_counts() -> dict[str, int]:
    return {
        "collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
        "xfailed": 0, "xpassed": 0, "not_run": 0, "collection_errors": 0,
        "deselected": 0,
    }


def _report(report_path: Path, *, nonce: str, exit_code: int) -> tuple[dict[str, int], bool]:
    try:
        if report_path.is_symlink() or not report_path.is_file() or report_path.stat().st_size > 16_384:
            return _empty_counts(), False
        document = strict_json_bytes(report_path.read_bytes())
        if not isinstance(document, dict) or set(document) != {
            "schema_version", "run_nonce", "exit_code", "counts",
        }:
            return _empty_counts(), False
        if (
            document.get("schema_version") != REPORT_SCHEMA
            or document.get("run_nonce") != nonce
            or document.get("exit_code") != exit_code
        ):
            return _empty_counts(), False
        return validate_counts(document.get("counts")), True
    except (OSError, FullSuiteEvidenceUnavailable):
        return _empty_counts(), False


def run_full_suite(
    repo_root: str | Path,
    *,
    test_database_url: str,
    expected_database: str,
    repository_probe: Callable[[str | Path], dict[str, Any]] = repository_identity,
    lease_factory: Callable[[str], Any] = TestDatabaseLease,
    process_runner: Callable[..., tuple[int, str | None]] = execute_pytest,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_root = root / "dashboard" / "runs" / "full-suite"
    require_configured_test_database(test_database_url, expected_database=expected_database)
    _plain_directory(output_root)
    lock = _acquire_lock(output_root / "producer.lock")
    run_id = str(uuid.uuid4())
    temp_log = output_root / f".full-suite-{run_id}.log.tmp"
    report_path = output_root / f".full-suite-{run_id}.report.tmp"
    final_log = output_root / "outputs" / f"{run_id}.log"
    final_run = output_root / "runs" / f"{run_id}.json"
    in_progress = output_root / "in-progress.json"
    completed_evidence = False
    try:
        recover_evidence(output_root)
        source_before = repository_probe(root)
        if source_before.get("clean") is not True:
            raise FullSuiteRefused("repository_not_clean")
        command = [sys.executable, *_COMMAND_TAIL]
        nonce = str(uuid.uuid4())
        started_at = _utc_now()
        started_monotonic = time.monotonic()
        with lease_factory(test_database_url) as lease:
            database_before = lease.observe()
            _write_replace(in_progress, document_bytes({
                "schema_version": "semiskill.full-suite-in-progress/v1",
                "run_id": run_id,
                "started_at": started_at,
                "source": source_before,
                "database": database_before,
                "runner": {
                    "entrypoint": "semiskill verify-full-suite", "command": command,
                    "pytest_plugin": PYTEST_PLUGIN, "timeout_seconds": FULL_SUITE_TIMEOUT_SECONDS,
                },
                "credit": "none",
            }))
            environment = child_environment(test_database_url, report_path=report_path, nonce=nonce)
            exit_code, failure_reason = process_runner(
                command, repo_root=root, environment=environment, log_path=temp_log,
            )
            database_after = lease.observe()
        if database_after != database_before:
            raise FullSuiteRefused("test_database_changed_during_run")
        source_after = repository_probe(root)
        if source_after != source_before or source_after.get("clean") is not True:
            raise FullSuiteRefused("repository_changed_during_run")
        counts, report_complete = _report(report_path, nonce=nonce, exit_code=exit_code)
        result_complete = report_complete and failure_reason is None
        if not result_complete and failure_reason is None:
            failure_reason = "pytest_report_invalid"
        try:
            log_size = temp_log.stat().st_size
        except OSError as exc:
            raise FullSuiteRefused("test_output_unavailable") from exc
        if log_size > MAX_LOG_BYTES:
            temp_log.unlink()
            temp_log = _write_temp(
                output_root, f".full-suite-{run_id}-",
                b"[semiskill] test output exceeded the immutable evidence limit\n",
            )
            log_size = temp_log.stat().st_size
            counts = _empty_counts()
            result_complete = False
            failure_reason = "test_output_limit_exceeded"
            exit_code = 125
        log_raw = temp_log.read_bytes()
        ended_at = _utc_now()
        # Expected skips/xfails and non-strict XPASS remain visible but follow pytest's zero exit.
        should_pass = (
            result_complete and exit_code == 0 and counts["collected"] > 0
            and counts["failed"] == 0
            and counts["errors"] == 0 and counts["not_run"] == 0
            and counts["collection_errors"] == 0 and counts["deselected"] == 0
        )
        document = finalize_run({
            "schema_version": RUN_SCHEMA,
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": round(time.monotonic() - started_monotonic, 6),
            "verdict": "pass" if should_pass else "fail",
            "exit_code": exit_code,
            "result_complete": result_complete,
            "failure_reason": failure_reason,
            "source": source_before,
            "database": database_before,
            "counts": counts,
            "output": {
                "ref": f"outputs/{run_id}.log", "sha256": sha256_bytes(log_raw),
                "bytes": log_size,
            },
            "runner": {
                "entrypoint": "semiskill verify-full-suite", "command": command,
                "pytest_plugin": PYTEST_PLUGIN, "timeout_seconds": FULL_SUITE_TIMEOUT_SECONDS,
            },
            "credit": "none",
        })
        validate_run(document)
        _move_no_replace(temp_log, final_log)
        _write_no_replace(final_run, document_bytes(document))
        _write_replace(output_root / "latest.json", document_bytes(latest_document(document)))
        completed_evidence = True
        return document
    except FullSuiteRefused:
        raise
    except Exception as exc:  # all unexpected paths remain non-secret and fail closed
        raise FullSuiteRefused("full_suite_run_failed") from exc
    finally:
        for path in (temp_log, report_path):
            with contextlib.suppress(OSError):
                if path.exists() and path.is_file() and not path.is_symlink():
                    path.unlink()
        if final_log.exists() and not final_run.exists():
            with contextlib.suppress(OSError):
                _plain_directory(output_root / "orphans")
                _quarantine_orphan(final_log, output_root / "orphans")
        if completed_evidence:
            with contextlib.suppress(OSError):
                if in_progress.exists() and in_progress.is_file() and not in_progress.is_symlink():
                    in_progress.unlink()
        _release_lock(lock)
