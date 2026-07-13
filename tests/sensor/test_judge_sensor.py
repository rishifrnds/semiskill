import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.sensor.judge import (
    GoldItem, record_gold_set, calibrate_judge, require_calibrated, require_no_drift,
    JudgeUncalibrated, JudgeDrifted)
from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.judge_risk import JudgeRiskScanner

MIG = Path("semiskill/artifacts/migrations")
RV = "skill_safety_v1"
_GOLD = [GoldItem("safe A", 1), GoldItem("safe B", 1), GoldItem("evil C", 0), GoldItem("evil D", 0)]


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


class FakeJudge:
    def __init__(self, fn):
        self._fn = fn

    def score(self, *, candidate, rubric):
        return self._fn(candidate)


def _agree(c):
    return 1.0 if c.startswith("safe") else 0.0     # matches labels -> κ=1


def _disagree(c):
    return 0.0                                       # all fail -> κ=0 (floor)


def _sub(body):
    return SkillSubmission(slug="dv/x", name="X", body=body, files={}, allowed_tools=())


def _calibrate(store, judge_fn):
    gs = record_gold_set(store, items=_GOLD, rubric_version=RV)
    calibrate_judge(store, gold_set=gs, judge=FakeJudge(judge_fn), judge_model="fake",
                    rubric="r", rubric_version=RV)


@pytest.mark.integration
def test_calibrate_agree_passes_kappa_gate(store):
    _calibrate(store, _agree)
    assert require_calibrated(store, rubric_version=RV) >= 0.6


@pytest.mark.integration
def test_calibrate_disagree_fails_kappa_gate(store):
    _calibrate(store, _disagree)
    with pytest.raises(JudgeUncalibrated):
        require_calibrated(store, rubric_version=RV)


@pytest.mark.integration
def test_uncalibrated_raises(store):
    with pytest.raises(JudgeUncalibrated):
        require_calibrated(store, rubric_version=RV)


@pytest.mark.integration
def test_drift_floor_raises_and_audits(store):
    _calibrate(store, _disagree)                      # κ=0 -> floor
    with pytest.raises(JudgeDrifted):
        require_no_drift(store, rubric_version=RV)
    assert any(a.objective_tag == "drift" for a in store.by_type(ArtifactType.SENSOR_READING))


@pytest.mark.integration
def test_judge_risk_uncalibrated_skips(store):
    r = JudgeRiskScanner(store=store, judge=FakeJudge(lambda c: 1.0),
                         judge_model_family="openai").scan(_sub("clean"))
    assert r.safety_score == 1.0 and any(f.code == "judge-skipped" for f in r.findings)


@pytest.mark.integration
def test_judge_risk_scores_when_calibrated(store):
    _calibrate(store, _agree)
    hi = JudgeRiskScanner(store=store, judge=FakeJudge(lambda c: 0.95),
                          judge_model_family="openai", candidate_model_family="anthropic")
    assert hi.scan(_sub("clean")).safety_score == 0.95
    lo = JudgeRiskScanner(store=store, judge=FakeJudge(lambda c: 0.1),
                          judge_model_family="openai", candidate_model_family="anthropic")
    r = lo.scan(_sub("suspicious"))
    assert r.safety_score == 0.1 and any(f.code == "judge-risk" for f in r.findings)
    assert r.hard_fail is False                       # advisory only


@pytest.mark.integration
def test_judge_risk_same_family_skips(store):
    _calibrate(store, _agree)
    r = JudgeRiskScanner(store=store, judge=FakeJudge(lambda c: 0.9),
                         judge_model_family="anthropic",
                         candidate_model_family="anthropic").scan(_sub("x"))
    assert any(f.code == "judge-skipped" for f in r.findings)
