"""Built-in pytest result reporter used only by ``semiskill verify-full-suite``."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from semiskill.verification.evidence import REPORT_SCHEMA

_states: dict[str, str] = {}
_selected: list[str] = []
_deselected = 0
_collection_errors = 0


def pytest_sessionstart(session) -> None:
    global _selected, _deselected, _collection_errors
    _states.clear()
    _selected = []
    _deselected = 0
    _collection_errors = 0


def pytest_collection_finish(session) -> None:
    global _selected
    _selected = [item.nodeid for item in session.items]
    for nodeid in _selected:
        _states.setdefault(nodeid, "not_run")


def pytest_deselected(items) -> None:
    global _deselected
    _deselected += len(items)


def pytest_collectreport(report) -> None:
    global _collection_errors
    if report.failed:
        _collection_errors += 1


def pytest_runtest_logreport(report) -> None:
    nodeid = report.nodeid
    _states.setdefault(nodeid, "not_run")
    was_xfail = bool(getattr(report, "wasxfail", False))
    if report.when == "setup":
        if report.failed:
            _states[nodeid] = "errors"
        elif report.skipped:
            _states[nodeid] = "xfailed" if was_xfail else "skipped"
        return
    if report.when == "call":
        if report.passed:
            _states[nodeid] = "xpassed" if was_xfail else "passed"
        elif report.skipped:
            _states[nodeid] = "xfailed" if was_xfail else "skipped"
        elif report.failed:
            _states[nodeid] = "xpassed" if was_xfail else "failed"
        return
    if report.when == "teardown" and report.failed:
        _states[nodeid] = "errors"


def pytest_sessionfinish(session, exitstatus) -> None:
    report_path = os.environ.get("SEMISKILL_FULL_SUITE_REPORT_PATH")
    nonce = os.environ.get("SEMISKILL_FULL_SUITE_RUN_NONCE")
    if not report_path or not nonce:
        return
    counts = {
        "collected": len(_selected),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "not_run": 0,
        "collection_errors": _collection_errors,
        "deselected": _deselected,
    }
    for nodeid in _selected:
        counts[_states.get(nodeid, "not_run")] += 1
    document = {
        "schema_version": REPORT_SCHEMA,
        "run_nonce": nonce,
        "exit_code": int(exitstatus),
        "counts": counts,
    }
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent,
        prefix=f".{target.name}.", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(document, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
