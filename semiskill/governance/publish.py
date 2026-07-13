"""The gated publish actuator (L4).

Publishing is DENY-by-default and REQUIRE_SIGNOFF: the only way a skill becomes discoverable is a
human sign-off through this actuator, which appends the published `approval` artifact. Server-side it
re-checks that the aggregate review verdict is 'approve' and that no hard-fail scan is in the chain
(defense in depth). A submitter role is trigger-blocked from writing approvals, so this actuator is
structurally the only publish path (ADR-002).
"""
from __future__ import annotations
from dataclasses import replace
from typing import Callable
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.governance.gate import ActionDescriptor, Decision, Rule, Policy, guarded_run


class PublishRefused(Exception):
    """A server-side precondition for publishing was not met."""


_PUBLISH_POLICY = Policy(
    rules=(Rule("publish", Decision.REQUIRE_SIGNOFF,
                "publish writes the discoverable catalog (ADR-002)"),),
    default=Decision.DENY)


def _has_hard_fail_scan(store: ArtifactStore, skill_version_id) -> bool:
    for t in (ArtifactType.SCAN_RUN, ArtifactType.INJECTION_TEST):
        for a in store.by_type(t):
            if skill_version_id in a.input_refs and a.payload.get("hard_fail"):
                return True
    return False


def publish_skill(*, store: ArtifactStore, skill_version_id, review_id, approver_actor: str,
                  approver: Callable[[ActionDescriptor], bool]) -> Artifact:
    """Publish a scanned+reviewed skill after human sign-off. Returns the published approval artifact.
    Raises PublishRefused on a bad precondition, GateBlocked if the human does not approve."""
    sv = store.get(skill_version_id)
    review = store.get(review_id)
    if sv is None or sv.artifact_type is not ArtifactType.SKILL_VERSION:
        raise PublishRefused("skill_version not found")
    if review is None or review.artifact_type is not ArtifactType.REVIEW:
        raise PublishRefused("review not found")
    if review.payload.get("verdict") != "approve":
        raise PublishRefused(f"review verdict is {review.payload.get('verdict')!r}, not approve")
    if _has_hard_fail_scan(store, skill_version_id):
        raise PublishRefused("scan chain contains a hard_fail; cannot publish")

    desc = ActionDescriptor.create(
        action_type="publish",
        targets=[f"catalog/{sv.payload.get('slug')}@{sv.payload.get('version')}"],
        actor=approver_actor, input_refs=[skill_version_id, review_id])

    def _do() -> Artifact:
        approval = Artifact.new(
            artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB,
            actor=approver_actor, actor_kind=ActorKind.HUMAN,
            input_refs=[skill_version_id, review_id],
            payload={"verdict": "approve", "published": True})
        approval = replace(approval, rollback_ref={"action": "unpublish",
                                                   "skill_version_id": str(skill_version_id)})
        return store.append(approval)

    return guarded_run(desc, policy=_PUBLISH_POLICY, store=store, action=_do, approver=approver)
