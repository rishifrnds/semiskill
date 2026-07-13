"""L5 cost economics: model routing + a budget/model policy enforced through the gate, plus a
Decimal-safe COST_LEDGER. Ported from aios/governance/cost.py. This module AUTHORS policy;
governance/gate.py ENFORCES it. Model IDs live ONLY here (config-overridable).

Token-maxing (CLAUDE.md #4): route cheap/bounded scans to SMALL, escalate to LARGE on ambiguity;
track cost-per-verified-skill.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.governance.gate import ActionDescriptor, Decision, Policy, Rule, guarded_run

SMALL: str = os.environ.get("SEMISKILL_MODEL_SMALL", "claude-haiku-4-5")   # cheap/bounded scans
LARGE: str = os.environ.get("SEMISKILL_MODEL_LARGE", "claude-sonnet-5")    # escalate on ambiguity
ALLOWED_MODELS: frozenset[str] = frozenset({SMALL, LARGE, "claude-opus-4-8"})

# USD per 1,000,000 tokens (input, output) — illustrative internal rate card.
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
    "claude-sonnet-5": (Decimal("3"), Decimal("15")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
}
assert ALLOWED_MODELS <= set(PRICES), f"models allowed but unpriced: {ALLOWED_MODELS - set(PRICES)}"


def call_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """USD cost of one model call. KeyError on an unpriced model (fail-closed)."""
    p_in, p_out = PRICES[model]
    return (Decimal(input_tokens) * p_in + Decimal(output_tokens) * p_out) / Decimal(1_000_000)


def route(*, bounded: bool) -> str:
    """Bounded/mechanical scan -> SMALL; ambiguous/suspected-malicious -> LARGE."""
    return SMALL if bounded else LARGE


def build_cost_policy(model: str, *, spent: Decimal, est_cost: Decimal, cap: Decimal) -> Policy:
    """Deny-precedence gate Policy for ONE llm_call: DENY a disallowed model, else DENY if the
    estimate would exceed the cap, else default ALLOW."""
    if model not in ALLOWED_MODELS:
        return Policy(rules=(Rule("llm_call", Decision.DENY, f"disallowed model: {model}",
                                  target_match=model),))
    if spent + est_cost > cap:
        return Policy(rules=(Rule("llm_call", Decision.DENY,
                                  f"over budget: spent {spent} + est {est_cost} > cap {cap}",
                                  target_match=model),))
    return Policy(rules=())


def total_spend(store: ArtifactStore) -> Decimal:
    """Sum of ACTUAL cost across COST_LEDGER artifacts, string-safe (not the float column)."""
    return sum((Decimal(a.payload["cost_usd"]) for a in store.by_type(ArtifactType.COST_LEDGER)),
               Decimal("0"))


def cost_per_verified_skill(store: ArtifactStore) -> Decimal:
    """Total spend / number of verified skills (one REVIEW artifact per verified skill)."""
    n = len(store.by_type(ArtifactType.REVIEW))
    return total_spend(store) / Decimal(max(1, n))


@dataclass(frozen=True)
class LedgerResult:
    result: object
    ledger: Artifact


def guard_llm_call(store: ArtifactStore, *, model: str, task_kind: str, est_cost: Decimal,
                   cap: Decimal, run: Callable[[], object], actual_cost: Callable[[object], Decimal],
                   tokens: Callable[[object], int], input_refs: list,
                   approver: Callable | None = None) -> LedgerResult:
    """Governed model call: gate on the ESTIMATE (blocked call never runs), then ledger the ACTUAL.
    The call is complete only once the COST_LEDGER is written."""
    spent = total_spend(store)
    policy = build_cost_policy(model, spent=spent, est_cost=est_cost, cap=cap)
    descriptor = ActionDescriptor.create(
        action_type="llm_call", targets=[model], actor="governance", input_refs=input_refs,
        effects={"est_cost_usd": str(est_cost), "spent_usd": str(spent), "cap_usd": str(cap)})
    result = guarded_run(descriptor, policy=policy, store=store, action=run, approver=approver)
    actual = Decimal(str(actual_cost(result)))
    tok = tokens(result)
    ledger = store.append(replace(
        Artifact.new(artifact_type=ArtifactType.COST_LEDGER, source_system=SourceSystem.CLI,
                     actor="governance", actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=input_refs,
                     payload={"model": model, "task_kind": task_kind, "tokens": tok,
                              "est_cost_usd": str(est_cost), "cost_usd": str(actual)}),
        cost_usd=float(actual)))
    return LedgerResult(result=result, ledger=ledger)
