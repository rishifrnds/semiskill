from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.spine.lifecycle import SkillState, derive_state, STATE_SPINE_CLASS
from semiskill.spine.states import EventClass


def _sv() -> Artifact:
    return Artifact.new(artifact_type=ArtifactType.SKILL_VERSION, source_system=SourceSystem.CLI,
                        actor="rishi", actor_kind=ActorKind.HUMAN, payload={"slug": "dv/uvm-testbench"})


def _ref(t, sv_id, *, actor="pipeline", actor_kind=ActorKind.SERVICE_ACCOUNT, payload=None):
    return Artifact.new(artifact_type=t, source_system=SourceSystem.CLI, actor=actor,
                        actor_kind=actor_kind, input_refs=[sv_id], payload=payload or {})


def _approval(sv_id, *, decision="approve", published=True, corrects_ref=None):
    artifact = _ref(
        ArtifactType.APPROVAL, sv_id, actor="alice", actor_kind=ActorKind.HUMAN,
        payload={"schema_version": "approval/v1", "decision": decision,
                 "published": published, "skill": {"artifact_id": str(sv_id)}},
    )
    if corrects_ref is not None:
        from dataclasses import replace
        artifact = replace(artifact, corrects_ref=corrects_ref)
    return artifact


def test_derive_state_progresses_with_artifacts():
    sv = _sv()
    arts = [sv]
    assert derive_state(sv.artifact_id, arts) == SkillState.SUBMITTED
    arts += [_ref(ArtifactType.SCAN_RUN, sv.artifact_id),
             _ref(ArtifactType.INJECTION_TEST, sv.artifact_id)]
    assert derive_state(sv.artifact_id, arts) == SkillState.SCANNED
    arts.append(_ref(ArtifactType.REVIEW, sv.artifact_id))
    assert derive_state(sv.artifact_id, arts) == SkillState.REVIEWED
    legacy = _ref(ArtifactType.APPROVAL, sv.artifact_id, actor="alice",
                  actor_kind=ActorKind.HUMAN, payload={"verdict": "approve", "published": True})
    arts.append(legacy)
    assert derive_state(sv.artifact_id, arts) == SkillState.REVIEWED
    arts.append(_approval(sv.artifact_id, published=True))
    assert derive_state(sv.artifact_id, arts) == SkillState.PUBLISHED


def test_scanned_requires_both_scan_and_injection():
    sv = _sv()
    arts = [sv, _ref(ArtifactType.SCAN_RUN, sv.artifact_id)]  # no injection_test yet
    assert derive_state(sv.artifact_id, arts) == SkillState.SUBMITTED


def test_no_published_state_without_approval():
    """A submitter appends everything they can EXCEPT a positive approval — including a forged
    verdict/published on a non-approval artifact. State must floor below APPROVED."""
    sv = _sv()
    arts = [
        sv,
        _ref(ArtifactType.SCAN_RUN, sv.artifact_id),
        _ref(ArtifactType.INJECTION_TEST, sv.artifact_id),
        _ref(ArtifactType.REVIEW, sv.artifact_id, actor="mallory", actor_kind=ActorKind.HUMAN,
             payload={"verdict": "approve", "published": True}),   # forged on a review
        _ref(ArtifactType.COMMENT, sv.artifact_id, actor="mallory", actor_kind=ActorKind.HUMAN,
             payload={"verdict": "approve", "published": True}),   # forged on a comment
        _ref(ArtifactType.RATING, sv.artifact_id, actor="mallory", actor_kind=ActorKind.HUMAN),
    ]
    st = derive_state(sv.artifact_id, arts)
    assert st < SkillState.APPROVED
    assert st == SkillState.REVIEWED


def test_rejected_approval_does_not_publish():
    sv = _sv()
    arts = [sv,
            _ref(ArtifactType.SCAN_RUN, sv.artifact_id),
            _ref(ArtifactType.INJECTION_TEST, sv.artifact_id),
            _ref(ArtifactType.REVIEW, sv.artifact_id),
            _approval(sv.artifact_id, decision="reject", published=False)]
    assert derive_state(sv.artifact_id, arts) == SkillState.REVIEWED


def test_unpublish_correction_removes_published_state_but_preserves_approval_history():
    sv = _sv()
    published = _approval(sv.artifact_id, published=True)
    correction = _approval(
        sv.artifact_id, decision="unpublish", published=False,
        corrects_ref=published.artifact_id,
    )
    assert derive_state(sv.artifact_id, [sv, published]) == SkillState.PUBLISHED
    assert derive_state(sv.artifact_id, [sv, published, correction]) == SkillState.APPROVED


def test_unrelated_artifacts_ignored():
    sv, other = _sv(), _sv()
    foreign_approval = _ref(ArtifactType.APPROVAL, other.artifact_id, actor="alice",
                            actor_kind=ActorKind.HUMAN, payload={"verdict": "approve", "published": True})
    assert derive_state(sv.artifact_id, [sv, other, foreign_approval]) == SkillState.SUBMITTED


def test_state_maps_to_spine_class():
    assert STATE_SPINE_CLASS[SkillState.SUBMITTED] == EventClass.CAPTURED
    assert STATE_SPINE_CLASS[SkillState.PUBLISHED] == EventClass.EXECUTED
