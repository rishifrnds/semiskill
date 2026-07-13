"""Action-descriptor security gate: classify high-blast-radius actions and block or require sign-off
BEFORE they execute. Pure mechanism. Ported from aios/governance/gate.py.

`action` runs ONLY inside the permitted branch, so a blocked action cannot run. Audit is fail-closed:
DENY / REQUIRE_SIGNOFF write a GATE_DECISION artifact before any execution; a failed write propagates
(the action never runs). ALLOW decisions are not logged (no side effect to audit).
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore


class Decision(str, Enum):
    ALLOW = "allow"
    REQUIRE_SIGNOFF = "require_signoff"
    DENY = "deny"


_RANK = {Decision.ALLOW: 0, Decision.REQUIRE_SIGNOFF: 1, Decision.DENY: 2}


@dataclass(frozen=True)
class ActionDescriptor:
    action_type: str
    targets: list[str]
    actor: str
    effects: dict = field(default_factory=dict)
    input_refs: list[uuid.UUID] = field(default_factory=list)

    @classmethod
    def create(cls, *, action_type, targets, actor, effects=None, input_refs=None):
        return cls(action_type=action_type, targets=list(targets), actor=actor,
                   effects=dict(effects or {}), input_refs=list(input_refs or []))


@dataclass(frozen=True)
class Rule:
    action_type: str
    decision: Decision
    reason: str
    target_prefixes: tuple[str, ...] | None = None
    target_match: str | None = None

    def __post_init__(self) -> None:
        if self.target_prefixes is not None and len(self.target_prefixes) == 0:
            raise ValueError("target_prefixes=() is ambiguous; use None for wildcard or omit")


@dataclass(frozen=True)
class Policy:
    rules: tuple[Rule, ...]
    default: Decision = Decision.ALLOW


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    reason: str
    matched_rule: Rule | None


def _rule_matches(rule: Rule, desc: ActionDescriptor) -> bool:
    if rule.action_type != desc.action_type:
        return False
    if rule.target_prefixes is None and rule.target_match is None:
        return True
    for t in desc.targets:
        if rule.target_prefixes and any(t.startswith(p) for p in rule.target_prefixes):
            return True
        if rule.target_match is not None and t == rule.target_match:
            return True
    return False


def evaluate(descriptor: ActionDescriptor, policy: Policy) -> GateResult:
    """Pure. Most-restrictive matching rule wins (DENY > REQUIRE_SIGNOFF > ALLOW). Ties resolve to
    the first such rule in declaration order. No match -> the policy's default."""
    matches = [r for r in policy.rules if _rule_matches(r, descriptor)]
    if not matches:
        return GateResult(policy.default, "default", None)
    winner = max(matches, key=lambda r: _RANK[r.decision])
    return GateResult(winner.decision, winner.reason, winner)


class GateDenied(Exception):
    """A DENY rule blocked the action."""


class GateBlocked(Exception):
    """A REQUIRE_SIGNOFF action was not approved."""


def _log_decision(store: ArtifactStore, descriptor: ActionDescriptor, result: GateResult,
                  *, outcome: str) -> Artifact:
    return store.append(Artifact.new(
        artifact_type=ArtifactType.GATE_DECISION, source_system=SourceSystem.CLI,
        actor="governance", actor_kind=ActorKind.SERVICE_ACCOUNT,
        input_refs=descriptor.input_refs,
        payload={"action_type": descriptor.action_type, "targets": descriptor.targets,
                 "decision": result.decision.value, "reason": result.reason, "outcome": outcome}))


def guarded_run(descriptor: ActionDescriptor, *, policy: Policy, store: ArtifactStore,
                action: Callable[[], Any],
                approver: Callable[[ActionDescriptor], bool] | None = None) -> Any:
    """Enforce the gate. `action` is invoked ONLY inside the permitted branch."""
    result = evaluate(descriptor, policy)
    if result.decision == Decision.DENY:
        _log_decision(store, descriptor, result, outcome="denied")
        raise GateDenied(result.reason)
    if result.decision == Decision.REQUIRE_SIGNOFF:
        try:
            approved = bool(approver(descriptor)) if approver is not None else False
        except Exception:
            _log_decision(store, descriptor, result, outcome="approver_error")
            raise
        _log_decision(store, descriptor, result, outcome="approved" if approved else "rejected")
        if not approved:
            raise GateBlocked(result.reason)
        return action()
    return action()
