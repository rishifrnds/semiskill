"""The six-control stability gate for the L5 controller. Ported from aios/intelligence/stability.py.

Six PURE predicates over an objective's EXECUTION history, composed DENY-PRECEDENCE (first deny wins,
the reason names the control) — mirroring the L4 gate's deny-precedence Policy. Deadband short-circuits
to a no-op `skipped` (not a failure). No I/O — the caller supplies the history + the latest error signal.
Keeps the controller from oscillating / running away on a noisy security-verdict stream.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecRecord:
    action: str
    outcome: str            # executed_ok | executed_failed | blocked:<control> | skipped:deadband
    error_signal: float
    cost: float
    timestamp: float        # epoch seconds


@dataclass(frozen=True)
class StabilityParams:
    deadband: float = 0.05
    cooldown_window: float = 0.0
    breaker_threshold: int = 3
    hysteresis_hi: float = 0.10
    hysteresis_lo: float = 0.05
    trajectory_window: int = 3
    cost_budget: float = 1.0

    @classmethod
    def from_env(cls) -> "StabilityParams":
        d = cls()
        g = os.environ.get
        return cls(
            deadband=float(g("SEMISKILL_STABILITY_DEADBAND", d.deadband)),
            cooldown_window=float(g("SEMISKILL_STABILITY_COOLDOWN_WINDOW", d.cooldown_window)),
            breaker_threshold=int(g("SEMISKILL_STABILITY_BREAKER_THRESHOLD", d.breaker_threshold)),
            hysteresis_hi=float(g("SEMISKILL_STABILITY_HYSTERESIS_HI", d.hysteresis_hi)),
            hysteresis_lo=float(g("SEMISKILL_STABILITY_HYSTERESIS_LO", d.hysteresis_lo)),
            trajectory_window=int(g("SEMISKILL_STABILITY_TRAJECTORY_WINDOW", d.trajectory_window)),
            cost_budget=float(g("SEMISKILL_STABILITY_COST_BUDGET", d.cost_budget)),
        )


@dataclass(frozen=True)
class StabilityVerdict:
    allow: bool
    reason: str             # "allow" | "skipped:deadband" | "blocked:<control>"


_REAL_OUTCOMES = ("executed_ok", "executed_failed")


def _real(history: list[ExecRecord]) -> list[ExecRecord]:
    return [r for r in history if r.outcome in _REAL_OUTCOMES]


def deadband_skip(latest_error_signal: float, params: StabilityParams) -> bool:
    """|error| <= deadband ⇒ within tolerance ⇒ skip (a no-op, not a failure)."""
    return abs(latest_error_signal) <= params.deadband


def cooldown_block(history: list[ExecRecord], params: StabilityParams, now: float) -> bool:
    """A real execution within cooldown_window seconds of now ⇒ block (let effects settle)."""
    if params.cooldown_window <= 0.0:
        return False
    reals = _real(history)
    if not reals:
        return False
    return (now - max(r.timestamp for r in reals)) < params.cooldown_window


def circuit_breaker_block(history: list[ExecRecord], params: StabilityParams) -> bool:
    """>= N consecutive trailing executed_failed (a success resets the streak) ⇒ HALT."""
    streak = 0
    for r in reversed(_real(history)):
        if r.outcome == "executed_failed":
            streak += 1
            if streak >= params.breaker_threshold:
                return True
        else:
            break
    return False


def hysteresis_block(history: list[ExecRecord], latest_error_signal: float,
                     params: StabilityParams) -> bool:
    """Schmitt trigger: start acting only when |error| >= hi; once acting, keep acting until |error| < lo."""
    mag = abs(latest_error_signal)
    acting = len(_real(history)) > 0
    return mag < (params.hysteresis_lo if acting else params.hysteresis_hi)


def trajectory_block(history: list[ExecRecord], params: StabilityParams) -> bool:
    """Over the last K real executions, |error_signal| must be strictly decreasing; else block.
    Fewer than K real executions ⇒ insufficient evidence ⇒ do not block."""
    reals = _real(history)
    if len(reals) < params.trajectory_window:
        return False
    mags = [abs(r.error_signal) for r in reals[-params.trajectory_window:]]
    improving = all(b < a for a, b in zip(mags, mags[1:]))
    return not improving


def cost_per_outcome_block(history: list[ExecRecord], params: StabilityParams) -> bool:
    """total cost / total error reduced over the real-execution window > cost_budget ⇒ block. Spend
    with no reduction ⇒ block. Zero spend ⇒ never block."""
    reals = _real(history)
    if len(reals) < 2:
        return False
    total_cost = sum(r.cost for r in reals)
    if total_cost <= 0.0:
        return False
    reduced = abs(reals[0].error_signal) - abs(reals[-1].error_signal)
    if reduced <= 0.0:
        return True
    return (total_cost / reduced) > params.cost_budget


def evaluate_stability(history: list[ExecRecord], *, latest_error_signal: float,
                       params: StabilityParams, now: float) -> StabilityVerdict:
    """Compose the controls DENY-PRECEDENCE. Deadband short-circuits to skipped (no-op); then the
    deny controls in declaration order — the first to fire names the verdict."""
    if deadband_skip(latest_error_signal, params):
        return StabilityVerdict(False, "skipped:deadband")
    if cooldown_block(history, params, now):
        return StabilityVerdict(False, "blocked:cooldown")
    if circuit_breaker_block(history, params):
        return StabilityVerdict(False, "blocked:breaker")
    if hysteresis_block(history, latest_error_signal, params):
        return StabilityVerdict(False, "blocked:hysteresis")
    if trajectory_block(history, params):
        return StabilityVerdict(False, "blocked:trajectory")
    if cost_per_outcome_block(history, params):
        return StabilityVerdict(False, "blocked:cost")
    return StabilityVerdict(True, "allow")
