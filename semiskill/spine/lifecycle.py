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


def derive_state(skill_version_id, artifacts: Iterable[Artifact]) -> SkillState:
    """Highest lifecycle state reachable for `skill_version_id` given the artifacts that reference
    it (via input_refs). PURE — never mutates, never stored (the lifecycle is NOT a column).

    ADR-002 gate is structural: APPROVED/PUBLISHED require a real `approval` artifact, which only the
    gated actuator can write (a submitter role is trigger-blocked from inserting approvals). The
    LATEST approval wins, so a later unpublish (a correcting approval with published=false) removes
    the skill from the catalog. A forged verdict on a non-approval artifact never counts.
    """
    related = [a for a in artifacts if skill_version_id in a.input_refs]
    types = {a.artifact_type for a in related}
    approvals = [a for a in related if a.artifact_type is ArtifactType.APPROVAL]
    # An approval superseded by a correction (another approval's corrects_ref → it) is inactive;
    # the active one is the head of the correction chain (deterministic, not timestamp-dependent).
    superseded = {a.corrects_ref for a in approvals if a.corrects_ref is not None}
    active = [a for a in approvals if a.artifact_id not in superseded]
    latest = max(active, key=lambda a: a.timestamp_start, default=None)

    if latest is not None and latest.payload.get("verdict") == "approve":
        if latest.payload.get("published") is True:
            return SkillState.PUBLISHED
        return SkillState.APPROVED
    if ArtifactType.REVIEW in types:
        return SkillState.REVIEWED
    if ArtifactType.SCAN_RUN in types and ArtifactType.INJECTION_TEST in types:
        return SkillState.SCANNED
    return SkillState.SUBMITTED
