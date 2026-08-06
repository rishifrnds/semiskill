import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.mark.integration
def test_append_then_get_roundtrip(store):
    a = Artifact.new(artifact_type=ArtifactType.SKILL_VERSION, source_system=SourceSystem.CLI,
                     actor="rishi", actor_kind=ActorKind.HUMAN,
                     payload={"slug": "dv/uvm-testbench", "version": "1.0.0"})
    store.append(a)
    got = store.get(a.artifact_id)
    assert got.artifact_id == a.artifact_id
    assert got.artifact_type == ArtifactType.SKILL_VERSION
    assert got.payload == {"slug": "dv/uvm-testbench", "version": "1.0.0"}
    assert got.permissions_label == "team" and got.objective_tag == "velocity"


@pytest.mark.integration
def test_input_refs_link_chain(store):
    sv = Artifact.new(artifact_type=ArtifactType.SKILL_VERSION, source_system=SourceSystem.CLI,
                      actor="rishi", actor_kind=ActorKind.HUMAN)
    store.append(sv)
    scan = Artifact.new(artifact_type=ArtifactType.SCAN_RUN, source_system=SourceSystem.CLI,
                        actor="pipeline", actor_kind=ActorKind.SERVICE_ACCOUNT,
                        input_refs=[sv.artifact_id])
    store.append(scan)
    assert store.get(scan.artifact_id).input_refs == [sv.artifact_id]
    assert [x.artifact_type for x in store.by_type(ArtifactType.SKILL_VERSION)] == [ArtifactType.SKILL_VERSION]


@pytest.mark.integration
def test_eval_score_and_labels_persist(store):
    a = (Artifact.new(artifact_type=ArtifactType.SCAN_RUN, source_system=SourceSystem.CLI,
                      actor="pipeline", actor_kind=ActorKind.SERVICE_ACCOUNT)
         .with_eval_score(0.95))
    store.append(a)
    got = store.get(a.artifact_id)
    assert got.eval_score == 0.95


@pytest.mark.integration
def test_append_many_rolls_back_every_row_when_one_insert_fails(store):
    assert hasattr(store, "append_many"), "collector requires an explicit transactional batch API"
    first = Artifact.new(
        artifact_type=ArtifactType.SKILL_VERSION,
        source_system=SourceSystem.CLI,
        actor="collector",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        payload={"slug": "dv-atomic-first"},
    )
    duplicate = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="collector",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
    )
    duplicate = Artifact(
        **{**duplicate.__dict__, "artifact_id": first.artifact_id}
    )

    with pytest.raises(Exception):
        store.append_many([first, duplicate])

    assert store.get(first.artifact_id) is None
