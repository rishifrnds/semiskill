import pytest
from semiskill.scanners.base import (
    ScanStage, Finding, ScanResult, SkillSubmission, result_from)


def test_scanresult_bounds_enforced():
    with pytest.raises(ValueError):
        ScanResult(stage=ScanStage.STATIC_STRUCTURE, safety_score=1.5)


def test_result_from_clean_is_full_safety():
    r = result_from(ScanStage.STATIC_STRUCTURE, [])
    assert r.safety_score == 1.0 and r.hard_fail is False


def test_result_from_hardfails_on_severe_finding():
    r = result_from(ScanStage.SECRET_PII, [Finding("live-credential", 0.95, "aws key")])
    assert r.safety_score == pytest.approx(0.05)
    assert r.hard_fail is True


def test_result_from_soft_findings_do_not_hardfail():
    r = result_from(ScanStage.STATIC_STRUCTURE,
                    [Finding("unlisted-tool", 0.4), Finding("oversized-file", 0.2)])
    assert r.hard_fail is False
    assert r.safety_score == pytest.approx(0.4)


def test_penalty_clamped_to_zero_floor():
    r = result_from(ScanStage.INJECTION,
                    [Finding("a", 0.6), Finding("b", 0.7)])  # sum 1.3 -> clamp
    assert r.safety_score == 0.0


def test_submission_from_payload_and_texts():
    s = SkillSubmission.from_payload({
        "slug": "dv/x", "name": "X", "body": "B",
        "files": {"scripts/gen.py": "code"}, "allowed_tools": ["Read", "Write"]})
    assert s.slug == "dv/x" and s.allowed_tools == ("Read", "Write")
    assert s.texts() == ["B", "code"]
