from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.security_audit import SecurityAuditScanner, ToolUnavailable


def _sub():
    return SkillSubmission(slug="dv/x", name="X", body="body", files={}, allowed_tools=())


def test_critical_finding_hardfails():
    sc = SecurityAuditScanner(runner=lambda s: {"findings": [
        {"severity": "critical", "type": "cve", "detail": "CVE-2025-1"}]})
    r = sc.scan(_sub())
    assert r.hard_fail is True and any(f.code == "audit:cve" for f in r.findings)


def test_clean_report_is_safe():
    sc = SecurityAuditScanner(runner=lambda s: {"findings": []})
    r = sc.scan(_sub())
    assert r.safety_score == 1.0 and r.hard_fail is False


def test_medium_finding_lowers_score_without_hardfail():
    sc = SecurityAuditScanner(runner=lambda s: {"findings": [{"severity": "medium", "type": "xss"}]})
    r = sc.scan(_sub())
    assert 0.0 < r.safety_score < 1.0 and r.hard_fail is False


def test_tool_unavailable_is_visible_skip_not_failure():
    def boom(s):
        raise ToolUnavailable("npx not on PATH")
    r = SecurityAuditScanner(runner=boom).scan(_sub())
    assert r.safety_score == 1.0                                   # advisory: does not lower score
    assert any(f.code == "security-audit-skipped" for f in r.findings)   # but present in the trail
