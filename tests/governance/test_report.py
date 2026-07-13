import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.governance.report import calibration_report, governance_posture
from semiskill.sensor.judge import GoldItem, record_gold_set, calibrate_judge

MIG = Path("semiskill/artifacts/migrations")
RV = "skill_safety_v1"
_GOLD = [GoldItem("safe", 1), GoldItem("evil", 0)]


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


class _J:
    def __init__(self, fn):
        self._fn = fn

    def score(self, *, candidate, rubric):
        return self._fn(candidate)


def _calibrate(store, fn):
    gs = record_gold_set(store, items=_GOLD, rubric_version=RV)
    calibrate_judge(store, gold_set=gs, judge=_J(fn), judge_model="fake", rubric="r", rubric_version=RV)


@pytest.mark.integration
def test_uncalibrated_report(store):
    r = calibration_report(store, rubric_version=RV)
    assert r.latest_kappa is None and r.calibrated is False and r.drift_reason == "uncalibrated"


@pytest.mark.integration
def test_calibrated_report_passes_gate(store):
    _calibrate(store, lambda c: 1.0 if c == "safe" else 0.0)   # κ=1
    r = calibration_report(store, rubric_version=RV)
    assert r.latest_kappa == 1.0 and r.calibrated is True and r.drifted is False


@pytest.mark.integration
def test_report_flags_drift_floor(store):
    _calibrate(store, lambda c: 0.0)                            # κ=0 -> floor
    r = calibration_report(store, rubric_version=RV)
    assert r.calibrated is False and r.drifted is True and r.drift_reason == "floor"


@pytest.mark.integration
def test_governance_posture(store):
    p = governance_posture(store)
    assert p.egress_default == "deny"
    assert len(p.restricted_roles) == 3
    assert "Read" in p.allowed_skill_tools and "Bash" in p.dangerous_skill_tools
