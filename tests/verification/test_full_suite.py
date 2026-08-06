from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from semiskill import cli
from semiskill.verification import full_suite
from semiskill.verification.evidence import (
    PYTEST_PLUGIN,
    REPORT_SCHEMA,
    FullSuiteEvidenceUnavailable,
    document_bytes,
    finalize_run,
    latest_document,
    read_latest_run,
    sha256_bytes,
    strict_json_bytes,
    validate_run,
)


def _source(commit: str = "a" * 40, tree: str = "b" * 40) -> dict:
    return {
        "vcs": "git", "object_format": "sha1", "commit": commit, "tree": tree, "clean": True,
    }


def _database(identity: str = "c" * 64) -> dict:
    return {
        "engine": "postgresql", "environment": "test", "database_name": "semiskill_test",
        "host": "127.0.0.1", "port": 5432, "identity_sha256": f"sha256:{identity}",
        "session_user_sha256": "sha256:" + "d" * 64,
    }


def _counts(**overrides) -> dict:
    result = {
        "collected": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0,
        "xfailed": 0, "xpassed": 0, "not_run": 0, "collection_errors": 0,
        "deselected": 0,
    }
    result.update(overrides)
    return result


def _run(run_id: str | None = None, *, log: bytes = b"ok\n", **overrides) -> dict:
    run_id = run_id or str(uuid.uuid4())
    basis = {
        "schema_version": "semiskill.full-suite-run/v1",
        "run_id": run_id,
        "started_at": "2026-08-06T20:00:00.000000Z",
        "ended_at": "2026-08-06T20:00:01.000000Z",
        "duration_seconds": 1.0,
        "verdict": "pass",
        "exit_code": 0,
        "result_complete": True,
        "failure_reason": None,
        "source": _source(),
        "database": _database(),
        "counts": _counts(),
        "output": {
            "ref": f"outputs/{run_id}.log", "sha256": sha256_bytes(log), "bytes": len(log),
        },
        "runner": {
            "entrypoint": "semiskill verify-full-suite",
            "command": [sys.executable, *full_suite._COMMAND_TAIL],
            "pytest_plugin": PYTEST_PLUGIN,
            "timeout_seconds": 3600,
        },
        "credit": "none",
    }
    basis.update(overrides)
    return finalize_run(basis)


def _write_bundle(root: Path, run: dict, log: bytes = b"ok\n") -> None:
    (root / "runs").mkdir(parents=True)
    (root / "outputs").mkdir()
    (root / "runs" / f"{run['run_id']}.json").write_bytes(document_bytes(run))
    (root / "outputs" / f"{run['run_id']}.log").write_bytes(log)
    (root / "latest.json").write_bytes(document_bytes(latest_document(run)))


class _Lease(AbstractContextManager):
    def __init__(self, identities: list[dict] | None = None):
        self.identities = identities or [_database(), _database()]
        self.index = 0

    def __enter__(self):
        return self

    def observe(self):
        value = self.identities[min(self.index, len(self.identities) - 1)]
        self.index += 1
        return copy.deepcopy(value)

    def __exit__(self, exc_type, exc, traceback):
        return None


def _process(*, counts=None, exit_code=0, reason=None, log=b"suite output\n"):
    counts = counts or _counts()

    def run(command, *, repo_root, environment, log_path):
        assert command[1:] == full_suite._COMMAND_TAIL
        assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        log_path.write_bytes(log)
        report = {
            "schema_version": REPORT_SCHEMA,
            "run_nonce": environment["SEMISKILL_FULL_SUITE_RUN_NONCE"],
            "exit_code": exit_code,
            "counts": counts,
        }
        Path(environment["SEMISKILL_FULL_SUITE_REPORT_PATH"]).write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        return exit_code, reason

    return run


def test_valid_run_round_trips_through_fixed_file_only_chain(tmp_path):
    run = _run()
    _write_bundle(tmp_path, run)

    loaded = read_latest_run(tmp_path)

    assert loaded == run
    assert loaded["verdict"] == "pass" and loaded["credit"] == "none"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(extra=True),
        lambda value: value["counts"].update(passed=True),
        lambda value: value["counts"].update(collected=2),
        lambda value: value.update(verdict="fail"),
        lambda value: value["database"].update(database_name="semiskill"),
        lambda value: value["source"].update(clean=False),
        lambda value: value["runner"].update(command=["pytest"]),
    ],
)
def test_run_contract_rejects_unknown_malformed_nonconserving_or_contradictory_data(mutate):
    value = _run()
    mutate(value)
    value["run_sha256"] = full_suite.sha256_bytes(full_suite.canonical_bytes({
        key: item for key, item in value.items() if key != "run_sha256"
    }))
    with pytest.raises(FullSuiteEvidenceUnavailable):
        validate_run(value)


def test_reader_rejects_hash_tamper_duplicate_json_and_in_progress_marker(tmp_path):
    run = _run()
    _write_bundle(tmp_path, run)
    output = tmp_path / "outputs" / f"{run['run_id']}.log"
    output.write_bytes(b"tampered")
    with pytest.raises(FullSuiteEvidenceUnavailable, match="output_hash"):
        read_latest_run(tmp_path)

    output.write_bytes(b"ok\n")
    latest = tmp_path / "latest.json"
    latest.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
    with pytest.raises(FullSuiteEvidenceUnavailable, match="json_invalid"):
        read_latest_run(tmp_path)

    latest.write_bytes(document_bytes(latest_document(run)))
    (tmp_path / "in-progress.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FullSuiteEvidenceUnavailable, match="run_in_progress"):
        read_latest_run(tmp_path)


def test_reader_rejects_symlinked_fixed_chain_component(tmp_path):
    run = _run()
    _write_bundle(tmp_path, run)
    target = tmp_path / "real-latest.json"
    latest = tmp_path / "latest.json"
    latest.replace(target)
    try:
        latest.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(FullSuiteEvidenceUnavailable):
        read_latest_run(tmp_path)


def test_child_environment_removes_pytest_python_and_semiskill_injection(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTEST_ADDOPTS", "-x -p hostile")
    monkeypatch.setenv("PYTEST_PLUGINS", "hostile")
    monkeypatch.setenv("PYTHONPATH", "hostile")
    monkeypatch.setenv("GIT_DIR", "hostile")
    monkeypatch.setenv("SEMISKILL_SCOREBOARD_SNAPSHOT", "forged.json")
    monkeypatch.setenv("DATABASE_URL", "postgresql://catalog")
    dsn = "postgresql://test-user:secret@localhost/semiskill_test"

    environment = full_suite.child_environment(
        dsn, report_path=tmp_path / "report.json", nonce=str(uuid.uuid4()),
    )

    assert "PYTEST_ADDOPTS" not in environment and "PYTEST_PLUGINS" not in environment
    assert "PYTHONPATH" not in environment and "GIT_DIR" not in environment
    assert "SEMISKILL_SCOREBOARD_SNAPSHOT" not in environment
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert all(environment[key] == dsn for key in full_suite._DATABASE_ENVIRONMENT_KEYS)


def test_repository_probe_ignores_inherited_git_redirection(monkeypatch, tmp_path):
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path.cwd(), text=True,
        stdout=subprocess.PIPE, check=True,
    ).stdout.strip()
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "forged.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(Path.cwd()))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "forged.index"))

    identity = full_suite.repository_identity(Path.cwd())

    assert identity["vcs"] == "git"
    assert identity["object_format"] in {"sha1", "sha256"}
    assert identity["commit"] == expected


def test_runner_writes_pass_and_later_failure_as_immutable_latest(tmp_path):
    def probe(_root):
        return _source()

    def lease(_dsn):
        return _Lease()

    first = full_suite.run_full_suite(
        tmp_path, test_database_url="postgresql://ignored/semiskill_test",
        expected_database="semiskill_test",
        repository_probe=probe, lease_factory=lease, process_runner=_process(),
    )
    failure_counts = _counts(collected=1, passed=0, failed=1)
    second = full_suite.run_full_suite(
        tmp_path, test_database_url="postgresql://ignored/semiskill_test",
        expected_database="semiskill_test",
        repository_probe=probe, lease_factory=lease,
        process_runner=_process(counts=failure_counts, exit_code=1),
    )

    root = tmp_path / "dashboard" / "runs" / "full-suite"
    assert first["verdict"] == "pass" and second["verdict"] == "fail"
    assert read_latest_run(root)["run_id"] == second["run_id"]
    assert len(list((root / "runs").glob("*.json"))) == 2
    assert len(list((root / "outputs").glob("*.log"))) == 2


def test_runner_refuses_dirty_or_changed_source_and_changed_database(tmp_path):
    with pytest.raises(full_suite.FullSuiteRefused, match="repository_not_clean"):
        full_suite.run_full_suite(
            tmp_path, test_database_url="postgresql://ignored/semiskill_test",
            expected_database="semiskill_test",
            repository_probe=lambda _root: {**_source(), "clean": False},
            lease_factory=lambda _dsn: _Lease(), process_runner=_process(),
        )

    sources = iter([_source(), _source(tree="e" * 40)])
    with pytest.raises(full_suite.FullSuiteRefused, match="repository_changed"):
        full_suite.run_full_suite(
            tmp_path, test_database_url="postgresql://ignored/semiskill_test",
            expected_database="semiskill_test",
            repository_probe=lambda _root: next(sources), lease_factory=lambda _dsn: _Lease(),
            process_runner=_process(),
        )
    marker = tmp_path / "dashboard" / "runs" / "full-suite" / "in-progress.json"
    assert marker.is_file()

    identities = [_database(), _database("e" * 64)]
    with pytest.raises(full_suite.FullSuiteRefused, match="test_database_changed"):
        full_suite.run_full_suite(
            tmp_path, test_database_url="postgresql://ignored/semiskill_test",
            expected_database="semiskill_test",
            repository_probe=lambda _root: _source(),
            lease_factory=lambda _dsn: _Lease(identities), process_runner=_process(),
        )


def test_producer_recovery_removes_only_orphan_output_and_promotes_complete_run(tmp_path):
    root = tmp_path / "evidence"
    run = _run()
    _write_bundle(root, run)
    orphan = root / "outputs" / f"{uuid.uuid4()}.log"
    orphan.write_bytes(b"incomplete")

    full_suite.recover_evidence(root)

    assert not orphan.exists()
    assert (root / "orphans" / orphan.name).is_file()
    assert read_latest_run(root)["run_id"] == run["run_id"]


def test_recovery_never_guesses_latest_without_transaction_marker(tmp_path):
    root = tmp_path / "evidence"
    run = _run()
    _write_bundle(root, run)
    (root / "latest.json").unlink()

    with pytest.raises(full_suite.FullSuiteRefused, match="latest_pointer_missing"):
        full_suite.recover_evidence(root)


def test_recovery_materializes_interrupted_failure_instead_of_restoring_prior_pass(tmp_path):
    root = tmp_path / "evidence"
    prior = _run()
    _write_bundle(root, prior)
    interrupted_id = str(uuid.uuid4())
    marker = {
        "schema_version": "semiskill.full-suite-in-progress/v1",
        "run_id": interrupted_id,
        "started_at": "2026-08-06T20:00:02.000000Z",
        "source": _source(),
        "database": _database(),
        "runner": prior["runner"],
        "credit": "none",
    }
    (root / "in-progress.json").write_bytes(document_bytes(marker))

    full_suite.recover_evidence(root)

    recovered = read_latest_run(root)
    assert recovered["run_id"] == interrupted_id
    assert recovered["verdict"] == "fail"
    assert recovered["failure_reason"] == "runner_interrupted"
    assert recovered["result_complete"] is False
    assert (root / "runs" / f"{prior['run_id']}.json").is_file()


def test_interrupted_run_beats_prior_pass_with_future_wall_clock(tmp_path):
    root = tmp_path / "evidence"
    prior = _run(ended_at="2099-01-01T00:00:00.000000Z")
    _write_bundle(root, prior)
    interrupted_id = str(uuid.uuid4())
    marker = {
        "schema_version": "semiskill.full-suite-in-progress/v1",
        "run_id": interrupted_id,
        "started_at": "2026-08-06T20:00:02.000000Z",
        "source": _source(),
        "database": _database(),
        "runner": prior["runner"],
        "credit": "none",
    }
    (root / "in-progress.json").write_bytes(document_bytes(marker))

    full_suite.recover_evidence(root)

    recovered = read_latest_run(root)
    assert recovered["run_id"] == interrupted_id
    assert recovered["failure_reason"] == "runner_interrupted"


def test_recovery_keeps_in_progress_marker_until_latest_is_durable(monkeypatch, tmp_path):
    root = tmp_path / "evidence"
    prior = _run()
    _write_bundle(root, prior)
    marker = {
        "schema_version": "semiskill.full-suite-in-progress/v1",
        "run_id": str(uuid.uuid4()),
        "started_at": "2026-08-06T20:00:02.000000Z",
        "source": _source(),
        "database": _database(),
        "runner": prior["runner"],
        "credit": "none",
    }
    marker_path = root / "in-progress.json"
    marker_path.write_bytes(document_bytes(marker))
    original = full_suite._write_replace

    def fail_latest(path, data):
        if path.name == "latest.json":
            raise OSError("injected pointer failure")
        return original(path, data)

    monkeypatch.setattr(full_suite, "_write_replace", fail_latest)
    with pytest.raises(OSError, match="injected pointer failure"):
        full_suite.recover_evidence(root)
    assert marker_path.is_file()
    with pytest.raises(FullSuiteEvidenceUnavailable, match="run_in_progress"):
        read_latest_run(root)


def test_database_lease_uses_only_pg_catalog_qualified_identity_and_lock_sql():
    source = Path("semiskill/verification/full_suite.py").read_text(encoding="utf-8")
    assert "SET search_path TO pg_catalog, pg_temp" in source
    assert "pg_catalog.current_database()" in source
    assert "FROM pg_catalog.pg_database" in source
    assert "pg_catalog.pg_try_advisory_lock" in source
    assert "pg_catalog.pg_advisory_unlock" in source
    assert "replace_existing | write_through" in source


def test_runner_requires_exact_expected_test_database(tmp_path):
    with pytest.raises(full_suite.FullSuiteRefused, match="configuration_mismatch"):
        full_suite.run_full_suite(
            tmp_path,
            test_database_url="postgresql://ignored/semiskill_test",
            expected_database="another_test",
            repository_probe=lambda _root: _source(),
            lease_factory=lambda _dsn: _Lease(),
            process_runner=_process(),
        )


def test_zero_collection_or_missing_report_can_never_pass(tmp_path):
    zero = _counts(collected=0, passed=0)
    result = full_suite.run_full_suite(
        tmp_path,
        test_database_url="postgresql://ignored/semiskill_test",
        expected_database="semiskill_test",
        repository_probe=lambda _root: _source(),
        lease_factory=lambda _dsn: _Lease(),
        process_runner=_process(counts=zero),
    )
    assert result["verdict"] == "fail"

    def missing_report(command, *, repo_root, environment, log_path):
        log_path.write_bytes(b"no reporter output\n")
        return 0, None

    result = full_suite.run_full_suite(
        tmp_path,
        test_database_url="postgresql://ignored/semiskill_test",
        expected_database="semiskill_test",
        repository_probe=lambda _root: _source(),
        lease_factory=lambda _dsn: _Lease(),
        process_runner=missing_report,
    )
    assert result["verdict"] == "fail"
    assert result["result_complete"] is False
    assert result["failure_reason"] == "pytest_report_invalid"


def test_process_output_is_bounded_while_the_child_is_running(monkeypatch, tmp_path):
    monkeypatch.setattr(full_suite, "MAX_LOG_BYTES", 1024)
    log = tmp_path / "bounded.log"
    exit_code, reason = full_suite.execute_pytest(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"],
        repo_root=tmp_path, environment=os.environ.copy(), log_path=log,
    )
    assert exit_code == 125 and reason == "test_output_limit_exceeded"
    assert log.stat().st_size == 1024


def test_timeout_terminates_descendant_process_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(full_suite, "FULL_SUITE_TIMEOUT_SECONDS", 0.2)
    marker = tmp_path / "descendant-survived.txt"
    child = (
        "import pathlib,time;time.sleep(1);"
        f"pathlib.Path({str(marker)!r}).write_text('survived',encoding='utf-8')"
    )
    parent = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);time.sleep(10)"
    )
    exit_code, reason = full_suite.execute_pytest(
        [sys.executable, "-c", parent], repo_root=tmp_path,
        environment=os.environ.copy(), log_path=tmp_path / "timeout.log",
    )
    time.sleep(1.1)
    assert exit_code == 124 and reason == "runner_timeout"
    assert not marker.exists()


def test_builtin_reporter_preserves_skip_xfail_and_non_strict_xpass(tmp_path):
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "import pytest\n"
        "def test_pass(): assert True\n"
        "@pytest.mark.skip(reason='platform')\n"
        "def test_skip(): pass\n"
        "@pytest.mark.xfail(reason='known')\n"
        "def test_xfail(): assert False\n"
        "@pytest.mark.xfail(reason='unexpected pass', strict=False)\n"
        "def test_xpass(): assert True\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    nonce = str(uuid.uuid4())
    environment = os.environ.copy()
    environment.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "SEMISKILL_FULL_SUITE_REPORT_PATH": str(report),
        "SEMISKILL_FULL_SUITE_RUN_NONCE": nonce,
    })
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", sample.name, "-p", PYTEST_PLUGIN],
        cwd=tmp_path, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=30, check=False,
    )

    assert completed.returncode == 0, completed.stdout.decode("utf-8", errors="replace")
    result = strict_json_bytes(report.read_bytes())
    assert result["run_nonce"] == nonce
    assert result["counts"] == _counts(
        collected=4, passed=1, skipped=1, xfailed=1, xpassed=1,
    )


def test_cli_requires_explicit_test_database_url(monkeypatch, capsys):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert cli.main(["verify-full-suite", "--expected-database", "semiskill_test"]) == 2
    assert "explicit TEST_DATABASE_URL is required" in capsys.readouterr().out
