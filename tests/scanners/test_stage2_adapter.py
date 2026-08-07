"""ADR-024 Stage 2 — the host adapter that binds identity and refuses to fail open.

Two properties matter most here. First, an unapproved supply chain can never produce a passing
Stage 2: BLK-003 is enforced in code, not merely in prose. Second, every refusal path lands on the
`security-audit-skipped` finding, which `pipeline._write_scan` maps to a blocking `not_run` — so a
broken, hostile or unapproved scan is always visibly absent evidence, never a quiet pass.
"""
import pytest

from semiskill.scanners.base import ScanStage, SkillSubmission
from semiskill.scanners.stage2_adapter import Stage2Adapter, Stage2Policy
from semiskill.scanners.stage2_report import REPORT_SCHEMA_VERSION

_RULE_PACK = "rules:\n  - id: semiskill.example\n"


def _policy(tmp_path, *, approved=True, rule_pack=_RULE_PACK, digest=None):
    pack = tmp_path / "rules.yml"
    pack.write_text(rule_pack, encoding="utf-8")
    import hashlib
    computed = hashlib.sha256(pack.read_bytes()).hexdigest()
    return Stage2Policy(
        image_manifest_digest="sha256:" + "a" * 64,
        rule_pack_path=pack,
        rule_pack_sha256=digest or computed,
        adapter_commit="deadbeef",
        approved=approved,
    )


def _submission(files=None, body="# Title\n\nA procedure.\n"):
    return SkillSubmission(slug="dv-x", name="dv-x", body=body, files=dict(files or {}))


def _engine(report=None, *, raises=None, capture=None):
    def run(*, staged_root, expected_files, policy):
        if capture is not None:
            capture.append({"root": staged_root, "expected": expected_files, "policy": policy})
        if raises is not None:
            raise raises
        return report if report is not None else {
            "schema_version": REPORT_SCHEMA_VERSION,
            "analyzed_files": list(expected_files),
            "skipped_files": [],
            "findings": [],
            "errors": [],
            "truncated": False,
            "timed_out": False,
            "resource_exceeded": False,
        }
    return run


def _skipped(result):
    return [f for f in result.findings if f.code == "security-audit-skipped"]


def test_clean_scan_passes_and_reports_no_findings(tmp_path):
    adapter = Stage2Adapter(engine=_engine(), policy=_policy(tmp_path))

    result, binding = adapter.scan_with_binding(_submission())

    assert result.stage is ScanStage.SECURITY_AUDIT
    assert result.findings == () and result.hard_fail is False
    assert result.safety_score == 1.0
    assert binding["analyzed_files"] == ("SKILL.md",)


def test_an_unapproved_supply_chain_can_never_pass(tmp_path):
    """BLK-003 enforced in code. Until AppSec promotes the chain, Stage 2 is absent evidence."""
    adapter = Stage2Adapter(engine=_engine(), policy=_policy(tmp_path, approved=False))

    result, binding = adapter.scan_with_binding(_submission())

    assert _skipped(result), "an unapproved chain must produce the blocking not_run marker"
    assert binding["refused"] is True
    assert "approved" in binding["refusal"]


def test_unapproved_chain_never_invokes_the_engine(tmp_path):
    calls = []
    adapter = Stage2Adapter(
        engine=_engine(capture=calls), policy=_policy(tmp_path, approved=False),
    )

    adapter.scan(_submission())

    assert calls == [], "an unapproved image must not be executed at all"


def test_rule_pack_hash_is_computed_independently_not_taken_on_trust(tmp_path):
    """The policy states a hash; the host recomputes it. A mismatch means the pack changed."""
    adapter = Stage2Adapter(
        engine=_engine(), policy=_policy(tmp_path, digest="sha256:" + "b" * 64),
    )

    result, binding = adapter.scan_with_binding(_submission())

    assert _skipped(result)
    assert "rule_pack" in binding["refusal"]


def test_engine_failure_is_absent_evidence_not_a_pass(tmp_path):
    adapter = Stage2Adapter(
        engine=_engine(raises=RuntimeError("container died")), policy=_policy(tmp_path),
    )

    result, _ = adapter.scan_with_binding(_submission())

    assert _skipped(result)


def test_an_invalid_report_is_absent_evidence_not_a_pass(tmp_path):
    adapter = Stage2Adapter(
        engine=_engine(report={"schema_version": "wrong"}), policy=_policy(tmp_path),
    )

    result, binding = adapter.scan_with_binding(_submission())

    assert _skipped(result)
    assert binding["refused"] is True


def test_a_report_claiming_partial_coverage_is_refused(tmp_path):
    def short_report(*, staged_root, expected_files, policy):
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "analyzed_files": ["SKILL.md"],          # ignores the vendored file
            "skipped_files": [], "findings": [], "errors": [],
            "truncated": False, "timed_out": False, "resource_exceeded": False,
        }

    adapter = Stage2Adapter(engine=short_report, policy=_policy(tmp_path))
    result, _ = adapter.scan_with_binding(_submission({"_shared/a.md": "x"}))

    assert _skipped(result)


def test_a_high_severity_finding_hard_fails_the_stage(tmp_path):
    def finding_report(*, staged_root, expected_files, policy):
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "analyzed_files": list(expected_files),
            "skipped_files": [],
            "findings": [{
                "id": "f1", "rule_id": "semiskill.exfil", "path": "SKILL.md",
                "line": 3, "severity": "critical", "message": "exfiltrates a secret",
            }],
            "errors": [], "truncated": False, "timed_out": False, "resource_exceeded": False,
        }

    adapter = Stage2Adapter(engine=finding_report, policy=_policy(tmp_path))
    result, _ = adapter.scan_with_binding(_submission())

    assert result.hard_fail is True


def test_binding_carries_host_bound_identity_only(tmp_path):
    policy = _policy(tmp_path)
    adapter = Stage2Adapter(engine=_engine(), policy=policy)

    _, binding = adapter.scan_with_binding(_submission())

    assert binding["image_manifest_digest"] == policy.image_manifest_digest
    assert binding["rule_pack_sha256"] == policy.rule_pack_sha256
    assert binding["adapter_commit"] == policy.adapter_commit
    assert binding["slug"] == "dv-x"
    assert len(binding["payload_sha256"]) == 64
    assert binding["report_schema_version"] == REPORT_SCHEMA_VERSION


def test_payload_controlled_scanner_config_is_isolated_and_recorded_in_the_binding(tmp_path):
    adapter = Stage2Adapter(engine=_engine(), policy=_policy(tmp_path))

    result, binding = adapter.scan_with_binding(_submission({".semgrepignore": "*"}))

    assert binding["isolated_files"] == (".semgrepignore",)
    assert result.findings == ()


def test_a_hostile_path_refuses_before_the_engine_runs(tmp_path):
    calls = []
    adapter = Stage2Adapter(engine=_engine(capture=calls), policy=_policy(tmp_path))

    result, _ = adapter.scan_with_binding(_submission({"../escape.txt": "owned"}))

    assert _skipped(result)
    assert calls == []


def test_staging_is_cleaned_up_even_when_the_engine_explodes(tmp_path):
    calls = []

    def exploding(*, staged_root, expected_files, policy):
        calls.append(staged_root)
        raise RuntimeError("boom")

    adapter = Stage2Adapter(engine=exploding, policy=_policy(tmp_path))
    adapter.scan(_submission())

    assert calls and not calls[0].exists(), "staging must not outlive the scan"


def test_scan_satisfies_the_scanner_protocol(tmp_path):
    from semiskill.scanners.base import Scanner
    adapter = Stage2Adapter(engine=_engine(), policy=_policy(tmp_path))

    assert isinstance(adapter, Scanner)
    assert adapter.scan(_submission()).stage is ScanStage.SECURITY_AUDIT
