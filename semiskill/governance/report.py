"""Governance reporting — the calibration (κ) report and the security posture summary.

Read-only projections over the artifact log + policy modules, for the Phase F calibration report and
adoption docs. No side effects.
"""
from __future__ import annotations
from dataclasses import dataclass
from semiskill.artifacts.store import ArtifactStore
from semiskill.sensor.judge import kappa_series, latest_kappa, detect_drift
from semiskill.governance.cost import total_spend, cost_per_verified_skill
from semiskill.governance.policy import ALLOWED_SKILL_TOOLS, DANGEROUS_SKILL_TOOLS


@dataclass(frozen=True)
class CalibrationReport:
    rubric_version: str
    latest_kappa: float | None
    kappa_series: list[float]
    min_kappa: float
    calibrated: bool          # latest κ present AND >= min_kappa
    drifted: bool
    drift_reason: str         # "uncalibrated" | "floor" | "drop" | "ok"


def calibration_report(store: ArtifactStore, *, rubric_version: str = "skill_safety_v1",
                       min_kappa: float = 0.6) -> CalibrationReport:
    series = kappa_series(store, rubric_version=rubric_version)
    latest = latest_kappa(store, rubric_version=rubric_version)
    if series:
        dv = detect_drift(series, min_kappa=min_kappa)
        drifted, reason = dv.drifted, dv.reason
    else:
        drifted, reason = False, "uncalibrated"
    return CalibrationReport(
        rubric_version=rubric_version, latest_kappa=latest, kappa_series=series, min_kappa=min_kappa,
        calibrated=(latest is not None and latest >= min_kappa), drifted=drifted, drift_reason=reason)


@dataclass(frozen=True)
class GovernancePosture:
    egress_default: str        # "deny"
    restricted_roles: list[str]
    allowed_skill_tools: list[str]
    dangerous_skill_tools: list[str]
    total_spend_usd: str
    cost_per_verified_skill_usd: str


def governance_posture(store: ArtifactStore) -> GovernancePosture:
    return GovernancePosture(
        egress_default="deny",
        restricted_roles=[
            "semiskill_app — reads only via SECURITY DEFINER functions; cannot SELECT artifacts",
            "semiskill_submitter — may submit/interact; cannot forge scan_run/review/approval",
            "semiskill_pipeline — may probe the held-out corpus; cannot read its patterns or gold-set labels",
        ],
        allowed_skill_tools=sorted(ALLOWED_SKILL_TOOLS),
        dangerous_skill_tools=sorted(DANGEROUS_SKILL_TOOLS),
        total_spend_usd=str(total_spend(store)),
        cost_per_verified_skill_usd=str(cost_per_verified_skill(store)))
