import pytest
from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.governance.gate import (
    ActionDescriptor, Decision, Rule, Policy, evaluate, guarded_run, GateDenied, GateBlocked)


class FakeStore:
    def __init__(self):
        self.rows: list[Artifact] = []

    def append(self, a):
        self.rows.append(a)
        return a

    def get(self, aid):
        return next((r for r in self.rows if r.artifact_id == aid), None)

    def by_type(self, t):
        return [r for r in self.rows if r.artifact_type == t]


def _desc(action_type="publish", targets=("catalog/dv/x@1.0",)):
    return ActionDescriptor.create(action_type=action_type, targets=list(targets), actor="alice")


def test_deny_precedence_over_allow():
    policy = Policy(rules=(
        Rule("publish", Decision.ALLOW, "ok"),
        Rule("publish", Decision.DENY, "no"),
    ))
    assert evaluate(_desc(), policy).decision == Decision.DENY


def test_default_deny_blocks_unlisted_action():
    policy = Policy(rules=(Rule("publish", Decision.REQUIRE_SIGNOFF, "signoff"),),
                    default=Decision.DENY)
    ran = []
    with pytest.raises(GateDenied):
        guarded_run(_desc(action_type="sneaky-write"), policy=policy, store=FakeStore(),
                    action=lambda: ran.append(1))
    assert ran == []                                  # action never ran


def test_require_signoff_approved_runs_and_audits():
    store = FakeStore()
    policy = Policy(rules=(Rule("publish", Decision.REQUIRE_SIGNOFF, "signoff"),), default=Decision.DENY)
    out = guarded_run(_desc(), policy=policy, store=store, action=lambda: "published",
                      approver=lambda d: True)
    assert out == "published"
    audits = store.by_type(ArtifactType.GATE_DECISION)
    assert len(audits) == 1 and audits[0].payload["outcome"] == "approved"


def test_require_signoff_rejected_blocks_and_audits():
    store = FakeStore()
    policy = Policy(rules=(Rule("publish", Decision.REQUIRE_SIGNOFF, "signoff"),), default=Decision.DENY)
    ran = []
    with pytest.raises(GateBlocked):
        guarded_run(_desc(), policy=policy, store=store, action=lambda: ran.append(1),
                    approver=lambda d: False)
    assert ran == []
    assert store.by_type(ArtifactType.GATE_DECISION)[0].payload["outcome"] == "rejected"


def test_require_signoff_without_approver_blocks():
    store = FakeStore()
    policy = Policy(rules=(Rule("publish", Decision.REQUIRE_SIGNOFF, "signoff"),), default=Decision.DENY)
    with pytest.raises(GateBlocked):
        guarded_run(_desc(), policy=policy, store=store, action=lambda: "x", approver=None)


def test_allow_runs_without_audit():
    store = FakeStore()
    policy = Policy(rules=(Rule("publish", Decision.ALLOW, "ok"),))
    assert guarded_run(_desc(), policy=policy, store=store, action=lambda: "ok") == "ok"
    assert store.by_type(ArtifactType.GATE_DECISION) == []
