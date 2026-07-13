"""Scanner contract shared by every L6 pipeline stage.

Every stage returns a ScanResult with a SAFETY score in [0,1] (1.0 = clean, 0.0 = maximally unsafe),
so it composes with the L6 sensor's error_signal = target - measured. A deterministic must-block
finding sets hard_fail, which short-circuits the pipeline (nothing later runs, and the skill can never
advance to review/approval). Skill bodies/files handed to scanners are UNTRUSTED — scanners analyze
them as data, never execute them.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Protocol, runtime_checkable

HARD_FAIL_SEVERITY = 0.9   # a finding at/above this severity blocks the skill outright


class ScanStage(IntEnum):
    STATIC_STRUCTURE = 1
    SECURITY_AUDIT = 2
    INJECTION = 3
    SECRET_PII = 4
    JUDGE_RISK = 5
    AGGREGATE = 6


@dataclass(frozen=True)
class Finding:
    code: str            # kebab-slug, e.g. "executable-payload"
    severity: float      # 0..1
    detail: str = ""


@dataclass(frozen=True)
class SkillSubmission:
    slug: str
    name: str
    body: str                        # UNTRUSTED
    files: dict[str, str]            # UNTRUSTED {relpath: content}
    allowed_tools: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: dict) -> "SkillSubmission":
        return cls(
            slug=str(payload.get("slug", "")),
            name=str(payload.get("name", "")),
            body=str(payload.get("body", "")),
            files=dict(payload.get("files") or {}),
            allowed_tools=tuple(payload.get("allowed_tools") or []),
        )

    def texts(self) -> list[str]:
        """All untrusted text blobs (body + each file), for content scanners."""
        return [self.body, *self.files.values()]


@dataclass(frozen=True)
class ScanResult:
    stage: ScanStage
    safety_score: float
    findings: tuple[Finding, ...] = ()
    hard_fail: bool = False

    def __post_init__(self):
        if not 0.0 <= self.safety_score <= 1.0:
            raise ValueError(f"safety_score must be in [0,1], got {self.safety_score}")


def result_from(stage: ScanStage, findings: Iterable[Finding]) -> ScanResult:
    """Fold findings into a ScanResult: safety = 1 - clamped(sum severities); hard_fail if any finding
    is at/above HARD_FAIL_SEVERITY."""
    findings = tuple(findings)
    penalty = min(1.0, sum(f.severity for f in findings))
    hard = any(f.severity >= HARD_FAIL_SEVERITY for f in findings)
    return ScanResult(stage=stage, safety_score=round(1.0 - penalty, 3),
                      findings=findings, hard_fail=hard)


@runtime_checkable
class Scanner(Protocol):
    stage: ScanStage

    def scan(self, submission: SkillSubmission) -> ScanResult: ...
