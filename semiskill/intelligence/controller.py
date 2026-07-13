"""L5 Intelligence controller — SUGGEST-ONLY (human-gated; never auto-publishes).

Two jobs: (1) rank the human review queue by risk so the most-suspicious pending skills surface
first; (2) decide whether the controller may auto-act on a security error signal — gated so a DRIFTED
or uncalibrated judge blocks auto-acting (route_to_human), and the six-control stability gate governs
otherwise. "act" here means "surface a confident recommendation", never a publish — publishing stays
behind the human approval actuator (ADR-002).
"""
from __future__ import annotations
from dataclasses import dataclass
from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import ArtifactStore
from semiskill.sensor.judge import require_no_drift, JudgeUncalibrated
from semiskill.intelligence.stability import evaluate_stability, StabilityParams


@dataclass(frozen=True)
class QueueItem:
    skill_version_id: object
    slug: str
    verdict: str
    aggregate_safety: float
    review_id: object


def review_queue(store: ArtifactStore) -> list[QueueItem]:
    """Skills awaiting a human decision (have a REVIEW, no active approve-approval yet), ranked by
    risk — lowest aggregate safety first (most-suspicious to the top)."""
    approvals = store.by_type(ArtifactType.APPROVAL)
    superseded = {a.corrects_ref for a in approvals if a.corrects_ref is not None}
    decided = {a.input_refs[0] for a in approvals
               if a.artifact_id not in superseded and a.payload.get("verdict") == "approve"
               and a.input_refs}
    items: list[QueueItem] = []
    for r in store.by_type(ArtifactType.REVIEW):
        sv_id = r.input_refs[0] if r.input_refs else None
        if sv_id is None or sv_id in decided:
            continue
        sv = store.get(sv_id)
        items.append(QueueItem(
            skill_version_id=sv_id, slug=(sv.payload.get("slug", "?") if sv else "?"),
            verdict=r.payload.get("verdict", "?"),
            aggregate_safety=float(r.payload.get("aggregate_safety", 1.0)),
            review_id=r.artifact_id))
    items.sort(key=lambda i: i.aggregate_safety)
    return items


@dataclass(frozen=True)
class ControllerDecision:
    action: str            # "act" | "route_to_human" | "skip"
    reason: str


def controller_decision(store: ArtifactStore, *, error_signal: float, history: list, params: StabilityParams,
                        now: float, rubric_version: str | None = None,
                        min_kappa: float = 0.6) -> ControllerDecision:
    """Suggest-only. A DRIFTED/uncalibrated judge (when a rubric is in play) blocks auto-acting —
    route_to_human. Otherwise the six-control stability gate governs (skipped:deadband → skip; any
    block → route_to_human; allow → act)."""
    if rubric_version is not None:
        try:
            require_no_drift(store, rubric_version=rubric_version, min_kappa=min_kappa)
        except JudgeUncalibrated as e:
            return ControllerDecision("route_to_human", f"judge not trustworthy: {e}")
    v = evaluate_stability(history, latest_error_signal=error_signal, params=params, now=now)
    if v.reason.startswith("skipped"):
        return ControllerDecision("skip", v.reason)
    if not v.allow:
        return ControllerDecision("route_to_human", v.reason)
    return ControllerDecision("act", "allow")
