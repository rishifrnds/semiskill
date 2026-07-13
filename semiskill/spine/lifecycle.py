from __future__ import annotations
from enum import IntEnum
from collections.abc import Iterable
from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.spine.states import EventClass


class SkillState(IntEnum):
    SUBMITTED = 1
    SCANNED = 2
    REVIEWED = 3
    APPROVED = 4
    PUBLISHED = 5


# Which spine EventClass each domain state's driving artifact belongs to.
STATE_SPINE_CLASS = {
    SkillState.SUBMITTED: EventClass.CAPTURED,
    SkillState.SCANNED: EventClass.ANALYZED,
    SkillState.REVIEWED: EventClass.PROPOSED,
    SkillState.APPROVED: EventClass.EXECUTED,
    SkillState.PUBLISHED: EventClass.EXECUTED,
}


def _is_positive_approval(a: Artifact) -> bool:
    """A publish gate can only be opened by an actual `approval` artifact with an approve verdict.
    A forged verdict on any OTHER artifact type does not count."""
    return a.artifact_type is ArtifactType.APPROVAL and a.payload.get("verdict") == "approve"


def derive_state(skill_version_id, artifacts: Iterable[Artifact]) -> SkillState:
    """Highest lifecycle state reachable for `skill_version_id` given the artifacts that reference
    it (via input_refs). PURE — never mutates, never stored (the lifecycle is NOT a column).

    ADR-002 gate is structural: APPROVED/PUBLISHED are returnable only when a positive `approval`
    artifact is present. Since artifacts are append-only and the `approval` type is written only by
    the (Phase-C) approval actuator, no submitter-controlled path can fabricate a published state.
    """
    related = [a for a in artifacts if skill_version_id in a.input_refs]
    types = {a.artifact_type for a in related}
    approvals = [a for a in related if _is_positive_approval(a)]

    if approvals and any(a.payload.get("published") is True for a in approvals):
        return SkillState.PUBLISHED
    if approvals:
        return SkillState.APPROVED
    if ArtifactType.REVIEW in types:
        return SkillState.REVIEWED
    if ArtifactType.SCAN_RUN in types and ArtifactType.INJECTION_TEST in types:
        return SkillState.SCANNED
    return SkillState.SUBMITTED
