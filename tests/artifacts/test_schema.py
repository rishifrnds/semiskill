import uuid
import pytest
from semiskill.artifacts.schema import (
    Artifact, ArtifactType, SourceSystem, ActorKind,
    PERMISSIONS_LABELS, OBJECTIVE_TAGS,
)


def _skill_version() -> Artifact:
    return Artifact.new(
        artifact_type=ArtifactType.SKILL_VERSION,
        source_system=SourceSystem.CLI,
        actor="rishi",
        actor_kind=ActorKind.HUMAN,
        payload={"slug": "dv/uvm-testbench", "version": "1.0.0"},
    )


def test_new_sets_id_and_start():
    a = _skill_version()
    assert isinstance(a.artifact_id, uuid.UUID)
    assert a.timestamp_start.tzinfo is not None
    assert a.eval_score is None and a.input_refs == []
    assert a.permissions_label == "team" and a.objective_tag == "velocity"


def test_eval_score_bounds_enforced():
    a = _skill_version()
    with pytest.raises(ValueError):
        a.with_eval_score(1.5)
    with pytest.raises(ValueError):
        a.with_eval_score(-0.1)
    assert a.with_eval_score(0.8).eval_score == 0.8


def test_enum_vocabularies():
    # Locks the ADR-001 domain vocabulary.
    assert {s.value for s in SourceSystem} == {"github", "sharepoint", "cli", "web"}
    assert {k.value for k in ActorKind} == {"human", "service-account", "agent"}
    phase_a_types = {"skill_version", "scan_run", "injection_test", "review",
                     "approval", "comment", "rating", "reuse_event"}
    assert phase_a_types <= {x.value for x in ArtifactType}
    assert PERMISSIONS_LABELS == ("public", "team", "need-to-know", "regulated")
    assert OBJECTIVE_TAGS == ("safety", "velocity", "reuse", "compliance")
