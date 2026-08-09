"""ADR-024/ADR-030 Stage 2 — the real `docker run` engine, wired to `Stage2Adapter`.

Fail-closed like everything else in this pipeline: any docker/semgrep failure or malformed output
becomes an exception, which `Stage2Adapter.scan_with_binding()` already catches and turns into
`security-audit-skipped` (never a clean pass) — this module asserts nothing about its own
trustworthiness, that is the policy/adapter's job. Its only job is to run the pinned, sandboxed
container and translate its raw JSON into the exact bounded report shape `stage2_report.py`
validates.

Sandboxing (verified working during J-010f4, not assumed): `--network none` (no egress),
`--read-only` root filesystem, `--tmpfs /tmp` + `HOME=/tmp` (Semgrep needs to write its own
settings file — `/home/semgrep/.semgrep` — even for a read-only scan; without a writable HOME it
crashes before scanning anything), `--cap-drop ALL --security-opt no-new-privileges`, and
`--user semgrep` (defense-in-depth; the upstream `-nonroot` image already defaults to this).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from semiskill.scanners.stage2_report import REPORT_SCHEMA_VERSION

DEFAULT_TIMEOUT_SECONDS = 120

# Semgrep's own severity vocabulary (ERROR/WARNING/INFO) has less range than stage2_report.py's
# five levels. Every rule in the SemiSkill pack sets `metadata.semiskill_severity` explicitly;
# this is the fallback for a rule that doesn't (e.g. an upstream/registry rule, if one is ever
# added), so a missing explicit severity fails toward MORE scrutiny, not less.
_SEVERITY_FALLBACK = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
_KNOWN_SEVERITIES = {"critical", "high", "medium", "low", "info"}


class Stage2EngineError(RuntimeError):
    """The docker/semgrep invocation itself failed — absent evidence, never a report."""


def docker_semgrep_engine(*, staged_root: Path, expected_files, policy,
                           timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
                           docker_binary: str = "docker") -> dict:
    """Run the pinned Semgrep image against `staged_root`, then translate its report.

    Matches the `engine: Callable[..., dict]` contract `Stage2Adapter` calls with
    `(staged_root=..., expected_files=..., policy=...)`. `policy.rule_pack_path`'s file is
    mounted read-only as the scan config at a fixed container path, separate from the payload —
    a rule pack co-located with the scanned tree would be scanned along with it and could
    trivially self-match its own detection patterns.
    """
    staged_root = Path(staged_root).resolve()
    rule_pack_path = Path(policy.rule_pack_path).resolve()
    image_ref = f"semgrep/semgrep@{policy.image_manifest_digest}"

    cmd = [
        docker_binary, "run", "--rm",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp",
        "-e", "HOME=/tmp",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "semgrep",
        "-v", f"{staged_root}:/payload:ro",
        "-v", f"{rule_pack_path}:/rules/semiskill.yml:ro",
        "-w", "/payload",
        image_ref,
        "semgrep", "scan",
        "--config", "/rules/semiskill.yml",
        "/payload",
        "--oss-only", "--disable-nosem", "--no-git-ignore",
        "--scan-unknown-extensions", "--metrics=off", "--disable-version-check",
        "--json", "--quiet",
    ]
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        return _empty_report(timed_out=True)
    except OSError as exc:
        raise Stage2EngineError(f"could not invoke {docker_binary!r}: {exc}") from exc

    # 0 = clean scan, 1 = findings present — both are normal completions. Anything else (crash,
    # bad args, sandbox rejection) is a real engine failure, never silently treated as clean.
    if completed.returncode not in (0, 1):
        raise Stage2EngineError(
            f"semgrep exited {completed.returncode}: {completed.stderr[-2000:]}"
        )
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Stage2EngineError(
            f"semgrep produced non-JSON stdout: {exc}; stderr={completed.stderr[-2000:]!r}"
        ) from exc

    return _translate(raw, staged_root=staged_root)


def _empty_report(*, timed_out: bool = False, resource_exceeded: bool = False) -> dict:
    return {
        "schema_version": REPORT_SCHEMA_VERSION, "analyzed_files": [], "skipped_files": [],
        "findings": [], "errors": [], "truncated": False, "timed_out": timed_out,
        "resource_exceeded": resource_exceeded,
    }


def _relpath(raw_path: str, *, staged_root: Path) -> str:
    """Semgrep reports paths as seen inside the container (`/payload/...`); translate back to
    the host-relative form `stage2_report.py` compares against `expected_files`."""
    path = Path(raw_path)
    try:
        return path.relative_to("/payload").as_posix()
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(staged_root).as_posix()
    except ValueError:
        return Path(raw_path).as_posix()


def _rule_id(check_id: str) -> str:
    """Semgrep prefixes a rule's `id:` with its config file's parent directory name when loaded
    via `--config <path>` — mounting our pack at the fixed path `/rules/semiskill.yml` (see
    `docker_semgrep_engine`) makes this deterministically `rules.<id>` every time. Strip it so
    `rule_id` matches what the pack file actually declares, not an artifact of our mount path."""
    return check_id.removeprefix("rules.")


def _translate(raw: dict, *, staged_root: Path) -> dict:
    paths = raw.get("paths") or {}
    analyzed = sorted({
        _relpath(p, staged_root=staged_root) for p in (paths.get("scanned") or [])
    })
    skipped = sorted({
        _relpath(p, staged_root=staged_root) for p in (paths.get("skipped") or [])
    })

    findings = []
    for index, item in enumerate(raw.get("results") or []):
        extra = item.get("extra") or {}
        metadata = extra.get("metadata") or {}
        severity = metadata.get("semiskill_severity")
        if severity not in _KNOWN_SEVERITIES:
            severity = _SEVERITY_FALLBACK.get(str(extra.get("severity", "")).upper(), "medium")
        message = str(extra.get("message") or "(no message)")[:4096]
        rule_id = _rule_id(str(item.get("check_id", "unknown")))
        findings.append({
            "id": f"{rule_id}:{index}",
            "rule_id": rule_id,
            "path": _relpath(item.get("path", ""), staged_root=staged_root),
            "line": _positive_int(((item.get("start") or {}).get("line"))),
            "severity": severity,
            "message": message,
        })

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "analyzed_files": analyzed,
        "skipped_files": skipped,
        "findings": findings,
        "errors": [str(e) for e in (raw.get("errors") or [])],
        "truncated": False,
        "timed_out": False,
        "resource_exceeded": False,
    }


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return 1
    return value
