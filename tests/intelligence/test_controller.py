import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.intelligence.controller import review_queue, controller_decision, ControllerDecision
from semiskill.intelligence.stability import ExecRecord, StabilityParams
from semiskill.sensor.judge import GoldItem, record_gold_set, calibrate_judge
from tests.support import publish_test_skill

MIG = Path("semiskill/artifacts/migrations")
RV = "skill_safety_v1"


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _review(store, slug, safety, verdict="request-changes"):
    sv = store.append(build_skill_version(skill_md=f"---\nname: {slug}\nslug: {slug}\n---\nb", actor="a"))
    review = store.append(Artifact.new(
        artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI, actor="ctl",
        actor_kind=ActorKind.AGENT, input_refs=[sv.artifact_id],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": verdict, "aggregate_safety": safety, "judge_required": True,
                 "scan_artifact_ids": []}))
    return sv, review


class _J:
    def __init__(self, fn):
        self._fn = fn

    def score(self, *, candidate, rubric):
        return self._fn(candidate)


@pytest.mark.integration
def test_review_queue_ranks_by_risk(store, pg_dsn):
    _review(store, "dv/low-risk", 0.9)
    _review(store, "dv/high-risk", 0.2)
    _review(store, "dv/mid-risk", 0.6)
    q = review_queue(store)
    assert [i.slug for i in q] == ["dv/high-risk", "dv/mid-risk", "dv/low-risk"]  # riskiest first


@pytest.mark.integration
def test_approved_skill_leaves_the_queue(store, pg_dsn):
    sv, review = _review(store, "dv/x", 0.95, verdict="approve")
    assert any(i.slug == "dv/x" for i in review_queue(store))
    publish_test_skill(store, sv)
    assert not any(i.slug == "dv/x" for i in review_queue(store))     # decided -> out of queue


@pytest.mark.integration
def test_drift_blocks_controller_from_acting(store, pg_dsn):
    # calibrate with a DISAGREEING judge -> κ=0 -> floor drift
    gs = record_gold_set(store, items=[GoldItem("safe", 1), GoldItem("evil", 0)], rubric_version=RV)
    calibrate_judge(store, gold_set=gs, judge=_J(lambda c: 0.0), judge_model="fake",
                    rubric="r", rubric_version=RV)
    d = controller_decision(store, error_signal=0.5, history=[], params=StabilityParams(),
                            now=1.0, rubric_version=RV)
    assert d.action == "route_to_human" and "judge not trustworthy" in d.reason


@pytest.mark.integration
def test_controller_acts_when_calibrated_and_stable(store, pg_dsn):
    gs = record_gold_set(store, items=[GoldItem("safe", 1), GoldItem("evil", 0)], rubric_version=RV)
    calibrate_judge(store, gold_set=gs, judge=_J(lambda c: 1.0 if c == "safe" else 0.0),
                    judge_model="fake", rubric="r", rubric_version=RV)  # κ=1
    d = controller_decision(store, error_signal=0.5, history=[], params=StabilityParams(),
                            now=1.0, rubric_version=RV)
    assert d.action == "act"


def test_controller_deadband_skips_without_judge():
    d = controller_decision(_NoStore(), error_signal=0.01, history=[], params=StabilityParams(), now=1.0)
    assert d.action == "skip"


def test_controller_blocked_control_routes_to_human():
    hist = [ExecRecord("p", "executed_failed", 0.5, 0.0, i) for i in range(3)]  # breaker
    d = controller_decision(_NoStore(), error_signal=0.5, history=hist, params=StabilityParams(), now=9.0)
    assert d.action == "route_to_human" and d.reason == "blocked:breaker"


class _NoStore:
    def by_type(self, t):
        return []

    def get(self, aid):
        return None
