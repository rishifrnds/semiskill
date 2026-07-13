"""L6 calibrated LLM-as-judge sensor. Ported from aios/sensor/judge.py.

Trustworthy ONLY when calibrated: scored against a rubric, calibrated to a held-out human gold-set
via Cohen's κ, and judge readings are blocked fail-closed when κ < threshold or the κ series has
drifted. The judge is injected. Held-out integrity: the judge NEVER sees human labels, and the
gold-set is ACL-restricted. A judge whose model family == the candidate's is rejected (self-preference).
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Protocol
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.sensor.reading import Setpoint, record_sensor_reading, SELF_MEASURING


@dataclass(frozen=True)
class DriftVerdict:
    drifted: bool
    reason: str               # "floor" | "drop" | "ok"
    latest: float
    baseline: float | None
    drop: float | None


def detect_drift(series: list[float], *, min_kappa: float = 0.6, max_drop: float = 0.1,
                 baseline_window: int = 3) -> DriftVerdict:
    """Pure drift predicate over a chronological κ series. DRIFTED on floor (latest < min_kappa) OR
    drop (baseline − latest ≥ max_drop, baseline = peak of the prior window). history < 2 ⇒ floor only."""
    if not series:
        raise ValueError("series must be non-empty")
    latest = series[-1]
    prior = series[-(baseline_window + 1):-1]
    baseline = max(prior) if prior else None
    drop = round(baseline - latest, 3) if baseline is not None else None
    if latest < min_kappa:
        return DriftVerdict(True, "floor", latest, baseline, drop)
    if drop is not None and drop >= max_drop:
        return DriftVerdict(True, "drop", latest, baseline, drop)
    return DriftVerdict(False, "ok", latest, baseline, drop)


class Judge(Protocol):
    def score(self, *, candidate: str, rubric: str) -> float: ...   # [0,1]


@dataclass(frozen=True)
class GoldItem:
    candidate: str
    human_label: int            # 1 = safe/pass, 0 = unsafe/fail


def cohen_kappa(human: list[int], machine: list[int]) -> float:
    """Cohen's κ for binary labels: (p_o − p_e)/(1 − p_e), 3 dp. Degenerate p_e==1 ⇒ 1.0."""
    n = len(human)
    if n == 0 or len(machine) != n:
        raise ValueError("human and machine label lists must be non-empty and equal length")
    po = sum(1 for h, m in zip(human, machine) if h == m) / n
    h1, m1 = sum(human) / n, sum(machine) / n
    pe = h1 * m1 + (1 - h1) * (1 - m1)
    if pe == 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 3)


def record_gold_set(store: ArtifactStore, *, items: list[GoldItem], rubric_version: str,
                    permissions_label: str = "regulated") -> Artifact:
    """Append a GOLD_SET artifact. Default ACL 'regulated' (SemiSkill's most-restrictive canonical
    label) — held out from the judge/agent; the judge never sees the human labels regardless."""
    if not items:
        raise ValueError("gold set must be non-empty")
    art = Artifact.new(
        artifact_type=ArtifactType.GOLD_SET, source_system=SourceSystem.WEB,
        actor="human", actor_kind=ActorKind.HUMAN,
        payload={"rubric_version": rubric_version, "n_items": len(items),
                 "items": [{"candidate": it.candidate, "human_label": it.human_label} for it in items]})
    return store.append(replace(art, permissions_label=permissions_label))


def latest_gold_set(store: ArtifactStore, *, rubric_version: str) -> Artifact | None:
    matches = [a for a in store.by_type(ArtifactType.GOLD_SET)
               if a.payload.get("rubric_version") == rubric_version]
    return matches[-1] if matches else None


class JudgeUncalibrated(ValueError):
    """The judge is uncalibrated or its latest κ is below threshold."""


def calibrate_judge(store: ArtifactStore, *, gold_set: Artifact, judge: Judge, judge_model: str,
                    rubric: str, rubric_version: str, pass_threshold: float = 0.5,
                    kappa_target: float = 0.6) -> Artifact:
    """Run the judge over the gold-set candidates (NEVER passing human labels), binarize at
    pass_threshold, compute Cohen's κ vs the human labels, and record a judge_calibration
    SENSOR_READING. Raw κ in payload['kappa']; eval_score gets κ clamped to [0,1]."""
    if gold_set.artifact_type != ArtifactType.GOLD_SET:
        raise ValueError(f"gold_set must be a GOLD_SET artifact, got {gold_set.artifact_type!r}")
    items = gold_set.payload.get("items")
    if not items:
        raise ValueError("gold_set payload['items'] is missing or empty")
    human = [it["human_label"] for it in items]
    machine = [1 if judge.score(candidate=it["candidate"], rubric=rubric) >= pass_threshold else 0
               for it in items]
    kappa = cohen_kappa(human, machine)
    return record_sensor_reading(
        store, scored_ref=gold_set.artifact_id,
        setpoint=Setpoint(objective_tag="judge_calibration", target=kappa_target),
        measured=max(0.0, min(1.0, kappa)),
        ground_truth_ref=str(gold_set.artifact_id),
        detail={"kappa": kappa, "rubric_version": rubric_version, "judge_model": judge_model,
                "n_items": len(human), "kind": "calibration"})


def _calibration_readings(store: ArtifactStore, *, rubric_version: str) -> list[Artifact]:
    return [a for a in store.by_type(ArtifactType.SENSOR_READING)
            if a.objective_tag == "judge_calibration"
            and a.payload.get("rubric_version") == rubric_version]


def kappa_series(store: ArtifactStore, *, rubric_version: str) -> list[float]:
    return [a.payload["kappa"] for a in _calibration_readings(store, rubric_version=rubric_version)]


def latest_kappa(store: ArtifactStore, *, rubric_version: str) -> float | None:
    s = kappa_series(store, rubric_version=rubric_version)
    return s[-1] if s else None


def require_calibrated(store: ArtifactStore, *, rubric_version: str, min_kappa: float = 0.6) -> float:
    """FAIL-CLOSED κ-gate: raise JudgeUncalibrated if never calibrated or latest κ < min_kappa."""
    k = latest_kappa(store, rubric_version=rubric_version)
    if k is None:
        raise JudgeUncalibrated(f"no calibration for rubric_version={rubric_version!r}")
    if k < min_kappa:
        raise JudgeUncalibrated(f"judge κ={k} < min_kappa={min_kappa} for {rubric_version!r}")
    return k


class JudgeDrifted(JudgeUncalibrated):
    """The judge's κ series has drifted (floor or drop). A drifted judge is not trustworthy."""


def require_no_drift(store: ArtifactStore, *, rubric_version: str, min_kappa: float = 0.6,
                     max_drop: float = 0.1, baseline_window: int = 3) -> DriftVerdict:
    """FAIL-CLOSED drift gate. On DRIFT records a SELF_MEASURING drift SENSOR_READING (the queryable
    block audit) then raises JudgeDrifted. Never-calibrated ⇒ JudgeUncalibrated."""
    cals = _calibration_readings(store, rubric_version=rubric_version)
    if not cals:
        raise JudgeUncalibrated(f"no calibration for rubric_version={rubric_version!r}")
    verdict = detect_drift([a.payload["kappa"] for a in cals], min_kappa=min_kappa,
                           max_drop=max_drop, baseline_window=baseline_window)
    if verdict.drifted:
        record_sensor_reading(
            store, scored_ref=cals[-1].artifact_id,
            setpoint=Setpoint(objective_tag="drift", target=min_kappa),
            measured=max(0.0, min(1.0, verdict.latest)), ground_truth_ref=SELF_MEASURING,
            detail={"reason": verdict.reason, "baseline": verdict.baseline, "drop": verdict.drop,
                    "max_drop": max_drop, "baseline_window": baseline_window,
                    "rubric_version": rubric_version, "kind": "drift"})
        raise JudgeDrifted(f"judge κ drifted ({verdict.reason}) for {rubric_version!r}: "
                           f"latest={verdict.latest}, baseline={verdict.baseline}, drop={verdict.drop}")
    return verdict


class JudgeOperationalError(Exception):
    """The judge could not produce a usable verdict (API/transport error). Fail-soft skip."""
