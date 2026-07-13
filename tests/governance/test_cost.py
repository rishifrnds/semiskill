from decimal import Decimal
import pytest
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.governance.cost import (
    SMALL, LARGE, route, call_cost, build_cost_policy, total_spend, cost_per_verified_skill,
    guard_llm_call)
from semiskill.governance.gate import Decision, GateDenied


class FakeStore:
    def __init__(self):
        self.rows = []

    def append(self, a):
        self.rows.append(a)
        return a

    def get(self, aid):
        return next((r for r in self.rows if r.artifact_id == aid), None)

    def by_type(self, t):
        return [r for r in self.rows if r.artifact_type == t]


class _Res:
    def __init__(self, cost, tok):
        self.cost, self.tok = cost, tok


def _guard(store, model, est, cap, ran):
    return guard_llm_call(store, model=model, task_kind="scan", est_cost=est, cap=cap,
                          run=lambda: (ran.append(1), _Res(Decimal("0.005"), 500))[1],
                          actual_cost=lambda r: r.cost, tokens=lambda r: r.tok, input_refs=[])


def test_route_small_vs_large():
    assert route(bounded=True) == SMALL and route(bounded=False) == LARGE


def test_call_cost():
    assert call_cost(SMALL, 1000, 1000) == Decimal("0.006")   # (1000*1 + 1000*5)/1e6


def test_policy_denies_disallowed_model():
    p = build_cost_policy("gpt-4", spent=Decimal("0"), est_cost=Decimal("0.01"), cap=Decimal("1"))
    assert p.rules and p.rules[0].decision == Decision.DENY


def test_policy_denies_over_budget():
    p = build_cost_policy(SMALL, spent=Decimal("0.99"), est_cost=Decimal("0.02"), cap=Decimal("1"))
    assert p.rules and p.rules[0].decision == Decision.DENY


def test_policy_allows_within_budget():
    p = build_cost_policy(SMALL, spent=Decimal("0"), est_cost=Decimal("0.01"), cap=Decimal("1"))
    assert p.rules == ()


def test_guard_runs_and_ledgers():
    store, ran = FakeStore(), []
    res = _guard(store, SMALL, Decimal("0.01"), Decimal("1"), ran)
    assert ran == [1] and total_spend(store) == Decimal("0.005")
    assert res.ledger.artifact_type is ArtifactType.COST_LEDGER


def test_guard_blocks_over_budget_without_running():
    store, ran = FakeStore(), []
    with pytest.raises(GateDenied):
        _guard(store, SMALL, Decimal("2"), Decimal("1"), ran)
    assert ran == [] and total_spend(store) == Decimal("0")


def test_cost_per_verified_skill():
    store = FakeStore()
    store.append(Artifact.new(artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI,
                              actor="c", actor_kind=ActorKind.AGENT))
    _guard(store, SMALL, Decimal("0.01"), Decimal("1"), [])
    assert cost_per_verified_skill(store) == Decimal("0.005")
