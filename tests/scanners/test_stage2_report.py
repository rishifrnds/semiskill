"""ADR-024 Stage 2 — validation of the engine's bounded, exact-key report.

The container is untrusted output, not a trusted narrator. It reports what it analyzed and what it
found; it may never assert its own identity, and it may never leave coverage ambiguous. ADR-024
makes any ignored, skipped, unparsed, truncated, timed-out, resource-killed, extra or missing file a
blocking Stage-2 `not_run`, so every case below is a refusal rather than a degraded pass.
"""
import pytest

from semiskill.scanners.stage2_report import (
    REPORT_SCHEMA_VERSION,
    Stage2ReportRefused,
    validate_report,
)

EXPECTED = ("SKILL.md", "refs/a.txt")


def _report(**overrides):
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "analyzed_files": list(EXPECTED),
        "skipped_files": [],
        "findings": [],
        "errors": [],
        "truncated": False,
        "timed_out": False,
        "resource_exceeded": False,
    }
    report.update(overrides)
    return report


def _finding(**overrides):
    finding = {
        "id": "f1",
        "rule_id": "semiskill.exfiltration.curl-pipe-sh",
        "path": "SKILL.md",
        "line": 12,
        "severity": "high",
        "message": "pipes a remote script into a shell",
    }
    finding.update(overrides)
    return finding


def test_a_clean_exact_coverage_report_validates(tmp_path):
    result = validate_report(_report(), expected_files=EXPECTED)

    assert result.findings == ()
    assert result.analyzed_files == EXPECTED


def test_findings_are_returned_with_mapped_severities():
    result = validate_report(
        _report(findings=[_finding(), _finding(id="f2", severity="low", path="refs/a.txt")]),
        expected_files=EXPECTED,
    )

    assert [f.severity for f in result.findings] == [0.9, 0.2]
    assert result.findings[0].code.startswith("stage2:")


# --- coverage must be exact ------------------------------------------------------------------

def test_a_missing_analyzed_file_is_refused():
    with pytest.raises(Stage2ReportRefused, match="coverage"):
        validate_report(_report(analyzed_files=["SKILL.md"]), expected_files=EXPECTED)


def test_an_extra_analyzed_file_is_refused():
    """An engine reporting a file the host never staged means the two disagree about the payload."""
    with pytest.raises(Stage2ReportRefused, match="coverage"):
        validate_report(
            _report(analyzed_files=[*EXPECTED, "smuggled.txt"]), expected_files=EXPECTED,
        )


def test_duplicate_analyzed_entries_cannot_fake_coverage():
    with pytest.raises(Stage2ReportRefused):
        validate_report(
            _report(analyzed_files=["SKILL.md", "SKILL.md"]), expected_files=EXPECTED,
        )


@pytest.mark.parametrize("field", ["skipped_files", "errors"])
def test_any_skip_or_error_is_blocking(field):
    with pytest.raises(Stage2ReportRefused):
        validate_report(_report(**{field: ["refs/a.txt"]}), expected_files=EXPECTED)


@pytest.mark.parametrize("flag", ["truncated", "timed_out", "resource_exceeded"])
def test_truncation_timeout_and_resource_kill_are_blocking(flag):
    with pytest.raises(Stage2ReportRefused, match=flag):
        validate_report(_report(**{flag: True}), expected_files=EXPECTED)


# --- the container may not assert its own identity -------------------------------------------

@pytest.mark.parametrize("smuggled", [
    "image_digest",
    "rule_pack_sha256",
    "payload_sha256",
    "slug",
    "version",
    "adapter_commit",
    "approved",
])
def test_container_supplied_identity_is_refused(smuggled):
    """The host binds identity. A report that asserts its own provenance is forging the chain."""
    with pytest.raises(Stage2ReportRefused, match="unknown"):
        validate_report(_report(**{smuggled: "anything"}), expected_files=EXPECTED)


def test_unknown_report_field_is_refused():
    with pytest.raises(Stage2ReportRefused, match="unknown"):
        validate_report(_report(extra_field=1), expected_files=EXPECTED)


def test_missing_report_field_is_refused():
    report = _report()
    del report["errors"]
    with pytest.raises(Stage2ReportRefused, match="missing"):
        validate_report(report, expected_files=EXPECTED)


def test_wrong_schema_version_is_refused():
    with pytest.raises(Stage2ReportRefused, match="schema"):
        validate_report(_report(schema_version="something.else/v9"), expected_files=EXPECTED)


# --- findings are bounded and well-formed ------------------------------------------------------

def test_duplicate_finding_ids_are_refused():
    with pytest.raises(Stage2ReportRefused, match="duplicate"):
        validate_report(
            _report(findings=[_finding(), _finding()]), expected_files=EXPECTED,
        )


def test_unknown_severity_is_refused():
    with pytest.raises(Stage2ReportRefused, match="severity"):
        validate_report(_report(findings=[_finding(severity="apocalyptic")]),
                        expected_files=EXPECTED)


@pytest.mark.parametrize("path", ["/etc/passwd", "../escape.txt", "refs/../../escape.txt",
                                  "C:/Windows/x.txt", "unstaged.txt"])
def test_finding_path_outside_the_expected_set_is_refused(path):
    with pytest.raises(Stage2ReportRefused, match="path"):
        validate_report(_report(findings=[_finding(path=path)]), expected_files=EXPECTED)


def test_unknown_finding_field_is_refused():
    with pytest.raises(Stage2ReportRefused, match="unknown"):
        validate_report(_report(findings=[_finding(confidence="high")]), expected_files=EXPECTED)


def test_too_many_findings_is_refused():
    from semiskill.scanners.stage2_report import MAX_FINDINGS
    findings = [_finding(id=f"f{i}") for i in range(MAX_FINDINGS + 1)]
    with pytest.raises(Stage2ReportRefused, match="bound"):
        validate_report(_report(findings=findings), expected_files=EXPECTED)


def test_oversized_string_is_refused():
    from semiskill.scanners.stage2_report import MAX_STRING_BYTES
    with pytest.raises(Stage2ReportRefused, match="bound"):
        validate_report(
            _report(findings=[_finding(message="x" * (MAX_STRING_BYTES + 1))]),
            expected_files=EXPECTED,
        )


@pytest.mark.parametrize("value", [None, "12", 1.5, True])
def test_non_integer_line_is_refused(value):
    with pytest.raises(Stage2ReportRefused, match="line"):
        validate_report(_report(findings=[_finding(line=value)]), expected_files=EXPECTED)


def test_report_must_be_a_mapping():
    with pytest.raises(Stage2ReportRefused):
        validate_report([], expected_files=EXPECTED)


def test_an_empty_expected_set_is_refused():
    """Scanning nothing and reporting success is the fail-open shape this stage exists to prevent."""
    with pytest.raises(Stage2ReportRefused):
        validate_report(_report(analyzed_files=[]), expected_files=())
