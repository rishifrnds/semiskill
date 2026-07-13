"""Stage 2 — security-audit scan.

Wraps the locally-installed security skills (`security-scan` / `security-audit`, backed by the
claude-flow CLI) over the submission and maps their findings to a ScanResult. The runner is
INJECTABLE so the pipeline stays hermetic in tests; the default runner shells `npx` and requires the
egress-controlled sandbox + a pinned registry in production.

GAP: without that sandbox + tool installed, this stage cannot run live. Rather than fail open
silently, an unavailable tool yields a VISIBLE `security-audit-skipped` finding in the scan trail so a
human reviewer knows stage 2 did not execute. Substitutes for the (uninstalled) cloudflare skill (ADR-006).
"""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable
from semiskill.scanners.base import ScanStage, Finding, ScanResult, SkillSubmission, result_from

_SEV = {"critical": 0.95, "high": 0.9, "medium": 0.5, "low": 0.2, "info": 0.05}


class ToolUnavailable(Exception):
    """The external security-audit tool could not be run (not installed / no egress / bad output)."""


def npx_security_runner(submission: SkillSubmission) -> dict:
    """Default runner: materialize the submission and run the local security-scan CLI. Raises
    ToolUnavailable on any failure. Requires the egress sandbox + claude-flow in production."""
    if shutil.which("npx") is None:
        raise ToolUnavailable("npx not on PATH")
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "SKILL.md").write_text(submission.body, encoding="utf-8")
        for rel, content in submission.files.items():
            p = Path(d) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                p.write_text(content, encoding="utf-8")
            except OSError:
                pass
        try:
            out = subprocess.run(
                ["npx", "@claude-flow/cli", "security", "scan", "--depth", "full", "--output", "json"],
                cwd=d, capture_output=True, text=True, timeout=120)
        except Exception as e:  # noqa: BLE001 - normalize any spawn failure
            raise ToolUnavailable(str(e))
        if out.returncode != 0:
            raise ToolUnavailable(f"security scan exited {out.returncode}: {out.stderr[:200]}")
        try:
            return json.loads(out.stdout)
        except Exception as e:  # noqa: BLE001
            raise ToolUnavailable(f"unparseable security report: {e}")


class SecurityAuditScanner:
    stage = ScanStage.SECURITY_AUDIT

    def __init__(self, runner: Callable[[SkillSubmission], dict] | None = None):
        self._runner = runner or npx_security_runner

    def scan(self, submission: SkillSubmission) -> ScanResult:
        try:
            report = self._runner(submission)
        except ToolUnavailable as e:
            # Visible skip: severity 0 (does not lower the score) but present in the trail so a
            # reviewer sees stage 2 did not run. Escalating this to fail-closed is a governance choice.
            return result_from(self.stage, [Finding("security-audit-skipped", 0.0, str(e))])
        findings = [
            Finding(f"audit:{item.get('type', 'finding')}",
                    _SEV.get(str(item.get("severity", "")).lower(), 0.4),
                    str(item.get("detail", "")))
            for item in report.get("findings", [])
        ]
        return result_from(self.stage, findings)
