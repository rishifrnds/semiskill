import uuid
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore

MIG = Path("semiskill/artifacts/migrations")


def _artifact(slug: str) -> Artifact:
    return Artifact.new(
        artifact_type=ArtifactType.SKILL_VERSION, source_system=SourceSystem.CLI,
        actor="rishi", actor_kind=ActorKind.HUMAN, payload={"slug": slug},
    )


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


def test_non_test_approval_actuator_requires_distinct_database_identity(monkeypatch):
    monkeypatch.delenv("SEMISKILL_APPROVAL_DATABASE_URL", raising=False)
    monkeypatch.delenv("SEMISKILL_REVIEW_COORDINATOR_DATABASE_URL", raising=False)
    monkeypatch.delenv("SEMISKILL_EXPORT_DATABASE_URL", raising=False)
    runtime = "postgresql://runtime:secret@db.internal:5432/semiskill"
    with pytest.raises(ValueError, match="distinct database identity"):
        PostgresArtifactStore(runtime, approval_dsn=runtime)
    with pytest.raises(ValueError, match="catalog database"):
        PostgresArtifactStore(
            runtime,
            approval_dsn="postgresql://actuator:secret@db.internal:5432/other_catalog",
        )

    store = PostgresArtifactStore(
        runtime,
        approval_dsn="postgresql://actuator:secret@db.internal:5432/semiskill",
    )
    assert store._approval_dsn.endswith("/semiskill")


def test_constructing_a_store_opens_no_connection(monkeypatch):
    """J-010e8: connecting must be lazy — construction alone must never touch the network."""
    def _refuse(*args, **kwargs):
        raise AssertionError("PostgresArtifactStore.__init__ must not open a connection")
    monkeypatch.setattr("psycopg.connect", _refuse)
    monkeypatch.setattr("psycopg_pool.ConnectionPool.__init__", _refuse)
    PostgresArtifactStore("postgresql://runtime:secret@db.internal:5432/semiskill")


@pytest.mark.integration
def test_repeated_calls_reuse_pooled_connections_instead_of_reconnecting(store):
    """J-010e8: the defect this fixes — every call used to open a brand-new physical connection.

    The pool's `min_size` connection is filled by a background worker started at construction,
    which can race a call made immediately afterward into opening one extra on-demand
    connection — that race is harmless and not what this test is about. What must NOT happen,
    before or after that warm-up settles, is a new physical connection per call: once
    `connections_num` stops moving, it must stay flat no matter how many more calls follow.
    Before this fix `_pools` did not exist at all (AttributeError); with it unpooled, this loop
    would have grown `connections_num` by one every iteration instead of holding steady.
    """
    a = _artifact("dv/pool-check")
    store.append(a)
    store.get(a.artifact_id)
    pool = store._pools[store._dsn]
    warm = pool.get_stats()["connections_num"]
    for _ in range(5):
        store.get(a.artifact_id)
        store.by_type(ArtifactType.SKILL_VERSION)
    assert pool.get_stats()["connections_num"] == warm, (
        f"connections_num grew past {warm} after warm-up — pooling is not reusing connections"
    )


@pytest.mark.integration
def test_dict_row_factory_never_leaks_into_a_tuple_returning_call(store):
    """A pooled connection that served a dict_row method must not poison a later tuple call."""
    a = _artifact("dv/row-factory-check")
    store.append(a)
    store.by_type(ArtifactType.SKILL_VERSION)  # uses row_factory=dict_row internally
    # verified_publication_ids does `row[0]` on plain tuples; a leaked dict_row raises KeyError.
    assert store.verified_publication_ids() == set()


@pytest.mark.integration
def test_append_commit_is_visible_from_a_separate_store_instance(pg_dsn):
    """Pooling must not change durability: a committed write is visible through a fresh pool."""
    writer = PostgresArtifactStore(pg_dsn)
    reader = PostgresArtifactStore(pg_dsn)
    a = _artifact("dv/cross-instance-visibility")
    writer.append(a)
    got = reader.get(a.artifact_id)
    assert got is not None and got.artifact_id == a.artifact_id
    reader.close()
    writer.close()


@pytest.mark.integration
def test_close_closes_and_drops_every_pool(store):
    store.get(uuid.uuid4())
    assert store._pools
    store.close()
    assert store._pools == {}
