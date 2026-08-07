"""ADR-024 Stage 2 — validation of the engine's bounded, exact-key report.

The container is untrusted output. It is allowed to say what it analyzed and what it found; it is
never allowed to assert its own identity, its image digest, the rule-pack hash, or that it was
approved. The trusted host binds all of that separately, so any provenance-shaped key appearing here
is a forgery attempt and is refused as an unknown field.

Coverage is exact or it is nothing. ADR-024 makes any ignored, skipped, unparsed, truncated,
timed-out, resource-killed, extra or missing file a blocking Stage-2 `not_run`, because a scan that
silently covered less than the payload produces a clean verdict for bytes nobody looked at. There is
therefore no partial-credit path in this module: every anomaly raises.
"""
from __future__ import annotations

from dataclasses import dataclass

from semiskill.scanners.base import Finding

REPORT_SCHEMA_VERSION = "semiskill.stage2-report/v1"

# Bounds exist so a hostile or malfunctioning engine cannot exhaust the host by reporting a
# multi-gigabyte finding list. Exceeding a bound is a refusal, never a truncation - truncating here
# would recreate the silent-coverage-loss defect one layer up.
MAX_FINDINGS = 1000
MAX_STRING_BYTES = 4096
MAX_FILES = 10_000

_REPORT_KEYS = frozenset({
    "schema_version",
    "analyzed_files",
    "skipped_files",
    "findings",
    "errors",
    "truncated",
    "timed_out",
    "resource_exceeded",
})

_FINDING_KEYS = frozenset({"id", "rule_id", "path", "line", "severity", "message"})

# Shared with the retired runner's mapping so a high/critical Stage-2 finding hard-fails the
# pipeline at the existing HARD_FAIL_SEVERITY threshold rather than merely lowering a score.
_SEVERITY = {
    "critical": 0.95,
    "high": 0.9,
    "medium": 0.5,
    "low": 0.2,
    "info": 0.05,
}

_BLOCKING_FLAGS = ("truncated", "timed_out", "resource_exceeded")


class Stage2ReportRefused(Exception):
    """The engine's report could not be trusted to prove exact coverage."""


@dataclass(frozen=True)
class ValidatedReport:
    analyzed_files: tuple[str, ...]
    findings: tuple[Finding, ...]


def _require_bounded_string(value: object, *, what: str) -> str:
    if not isinstance(value, str):
        raise Stage2ReportRefused(f"{what} must be a string, got {type(value).__name__}")
    if len(value.encode("utf-8")) > MAX_STRING_BYTES:
        raise Stage2ReportRefused(f"{what} exceeds the {MAX_STRING_BYTES}-byte bound")
    return value


def _require_bool(report: dict, key: str) -> bool:
    value = report[key]
    if not isinstance(value, bool):
        raise Stage2ReportRefused(f"{key} must be a boolean, got {type(value).__name__}")
    return value


def _require_string_list(value: object, *, what: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise Stage2ReportRefused(f"{what} must be a list, got {type(value).__name__}")
    if len(value) > MAX_FILES:
        raise Stage2ReportRefused(f"{what} exceeds the {MAX_FILES}-entry bound")
    return tuple(_require_bounded_string(item, what=f"{what} entry") for item in value)


def validate_report(report: object, *, expected_files) -> ValidatedReport:
    """Validate an engine report against the host's exact expected coverage set.

    Raises `Stage2ReportRefused` on anything that makes the result unsafe to credit.
    """
    expected = tuple(expected_files)
    if not expected:
        raise Stage2ReportRefused("expected coverage set is empty; nothing was staged to scan")
    if not isinstance(report, dict):
        raise Stage2ReportRefused(f"report must be an object, got {type(report).__name__}")

    unknown = sorted(set(report) - _REPORT_KEYS)
    if unknown:
        # Provenance-shaped keys land here on purpose: the container cannot vouch for itself.
        raise Stage2ReportRefused(f"unknown report field(s): {unknown}")
    missing = sorted(_REPORT_KEYS - set(report))
    if missing:
        raise Stage2ReportRefused(f"missing report field(s): {missing}")

    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise Stage2ReportRefused(
            f"schema mismatch: expected {REPORT_SCHEMA_VERSION!r}, "
            f"got {report['schema_version']!r}"
        )

    for flag in _BLOCKING_FLAGS:
        if _require_bool(report, flag):
            raise Stage2ReportRefused(f"engine reported {flag}; Stage 2 cannot claim coverage")

    skipped = _require_string_list(report["skipped_files"], what="skipped_files")
    if skipped:
        raise Stage2ReportRefused(f"engine skipped file(s): {list(skipped)}")

    errors = _require_string_list(report["errors"], what="errors")
    if errors:
        raise Stage2ReportRefused(f"engine reported error(s): {list(errors)}")

    analyzed = _require_string_list(report["analyzed_files"], what="analyzed_files")
    if len(set(analyzed)) != len(analyzed):
        raise Stage2ReportRefused("analyzed_files contains duplicate entries")
    if tuple(sorted(analyzed)) != tuple(sorted(expected)):
        missing_files = sorted(set(expected) - set(analyzed))
        extra_files = sorted(set(analyzed) - set(expected))
        raise Stage2ReportRefused(
            f"coverage mismatch: missing {missing_files}, unexpected {extra_files}"
        )

    findings_raw = report["findings"]
    if not isinstance(findings_raw, list):
        raise Stage2ReportRefused(
            f"findings must be a list, got {type(findings_raw).__name__}"
        )
    if len(findings_raw) > MAX_FINDINGS:
        raise Stage2ReportRefused(f"findings exceed the {MAX_FINDINGS}-entry bound")

    seen_ids: set[str] = set()
    findings: list[Finding] = []
    allowed_paths = set(expected)
    for item in findings_raw:
        if not isinstance(item, dict):
            raise Stage2ReportRefused(
                f"each finding must be an object, got {type(item).__name__}"
            )
        unknown_finding = sorted(set(item) - _FINDING_KEYS)
        if unknown_finding:
            raise Stage2ReportRefused(f"unknown finding field(s): {unknown_finding}")
        missing_finding = sorted(_FINDING_KEYS - set(item))
        if missing_finding:
            raise Stage2ReportRefused(f"missing finding field(s): {missing_finding}")

        finding_id = _require_bounded_string(item["id"], what="finding id")
        if finding_id in seen_ids:
            raise Stage2ReportRefused(f"duplicate finding id: {finding_id!r}")
        seen_ids.add(finding_id)

        rule_id = _require_bounded_string(item["rule_id"], what="finding rule_id")
        message = _require_bounded_string(item["message"], what="finding message")
        path = _require_bounded_string(item["path"], what="finding path")
        if path not in allowed_paths:
            # Covers absolute, traversing and simply-unstaged paths in one rule: the only paths a
            # finding may name are the ones the host actually staged.
            raise Stage2ReportRefused(f"finding path is not in the staged payload: {path!r}")

        line = item["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise Stage2ReportRefused(f"finding line must be a positive integer, got {line!r}")

        severity_name = item["severity"]
        if not isinstance(severity_name, str) or severity_name.lower() not in _SEVERITY:
            raise Stage2ReportRefused(f"unknown finding severity: {severity_name!r}")

        findings.append(Finding(
            code=f"stage2:{rule_id}",
            severity=_SEVERITY[severity_name.lower()],
            detail=f"{path}:{line} {message}",
        ))

    return ValidatedReport(analyzed_files=tuple(analyzed), findings=tuple(findings))
