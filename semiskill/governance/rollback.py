"""Gated unpublish / quarantine (L4).

Reverses a publish by appending a NEW correcting approval (corrects_ref → the published approval)
with published=false — append-only, never an UPDATE. The catalog is latest/active-approval-wins, so
the correction immediately removes the skill from discovery; the original approval stays in the log
for audit. REQUIRE_SIGNOFF, like publish.
"""
from __future__ import annotations
from dataclasses import replace
from typing import Callable
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.governance.gate import ActionDescriptor, Decision, Rule, Policy, guarded_run


class RollbackRefused(Exception):
    """The referenced published approval could not be found."""


_ROLLBACK_POLICY = Policy(
    rules=(Rule("rollback", Decision.REQUIRE_SIGNOFF, "unpublish/quarantine is a gated action"),),
    default=Decision.DENY)


def unpublish_skill(*, store: ArtifactStore, skill_version_id, published_approval_id,
                    approver_actor: str, approver: Callable[[ActionDescriptor], bool],
                    quarantine: bool = True) -> Artifact:
    """Unpublish (and optionally quarantine) a published skill after human sign-off."""
    pub = store.get(published_approval_id)
    if pub is None or pub.artifact_type is not ArtifactType.APPROVAL:
        raise RollbackRefused("published approval not found")

    desc = ActionDescriptor.create(
        action_type="rollback", targets=[f"catalog/{skill_version_id}"],
        actor=approver_actor, input_refs=[skill_version_id, published_approval_id])

    def _do() -> Artifact:
        corr = Artifact.new(
            artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
            actor=approver_actor, actor_kind=ActorKind.HUMAN, input_refs=[skill_version_id],
            payload={"verdict": "approve", "published": False, "quarantined": quarantine})
        corr = replace(corr, corrects_ref=published_approval_id)
        return store.append(corr)

    return guarded_run(desc, policy=_ROLLBACK_POLICY, store=store, action=_do, approver=approver)
