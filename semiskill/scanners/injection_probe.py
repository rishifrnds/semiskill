"""Stage 3 — prompt-injection / policy test (deterministic, 100% of submissions).

Runs the untrusted submission against the held-out injection corpus via the restricted-role probe.
Any class that fires (injection, exfiltration, scope-violation à la EchoLeak, tool-abuse) is a
hard_fail — the pipeline never learns the corpus patterns, only that a class matched.
"""
from __future__ import annotations
from semiskill.scanners.base import ScanStage, Finding, ScanResult, SkillSubmission, result_from
from semiskill.sensor.corpus import probe_skill


class InjectionProbeScanner:
    stage = ScanStage.INJECTION

    def __init__(self, dsn: str):
        self._dsn = dsn

    def scan(self, s: SkillSubmission) -> ScanResult:
        text = "\n".join(s.texts())
        res = probe_skill(self._dsn, text)
        findings = [Finding(f"injection:{cls}", 0.95, "matched held-out corpus")
                    for cls in res.failing_classes]
        return result_from(self.stage, findings)
