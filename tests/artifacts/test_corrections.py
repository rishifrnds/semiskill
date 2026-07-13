import uuid
from dataclasses import replace
import psycopg
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


def _review(verdict: str) -> Artifact:
    return Artifact.new(artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI,
                        actor="agent", actor_kind=ActorKind.AGENT, payload={"verdict": verdict})


@pytest.mark.integration
def test_correction_appends_new_row_via_corrects_ref(store, pg_dsn):
    first = _review("reject")
    store.append(first)
    # A correction is a NEW row that points back via corrects_ref — never an UPDATE.
    second = replace(_review("approve"), corrects_ref=first.artifact_id)
    store.append(second)
    assert store.get(second.artifact_id).corrects_ref == first.artifact_id
    # Original row is untouched, and there are exactly two rows (INSERT, not UPDATE).
    assert store.get(first.artifact_id).payload == {"verdict": "reject"}
    with psycopg.connect(pg_dsn) as conn:
        n = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
    assert n == 2


@pytest.mark.integration
def test_correction_requires_existing_target(store):
    bad = replace(_review("approve"), corrects_ref=uuid.uuid4())  # points at a non-existent artifact
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.append(bad)
