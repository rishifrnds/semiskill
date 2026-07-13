from __future__ import annotations
import uuid
from typing import Protocol
import psycopg
import psycopg.rows
from psycopg.types.json import Jsonb
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind

_COLS = (
    "artifact_id artifact_type source_system actor actor_kind timestamp_start "
    "timestamp_end input_refs output_refs permissions_label objective_tag "
    "ground_truth_ref eval_score rollback_ref cost_usd corrects_ref payload"
).split()


class ArtifactStore(Protocol):
    def append(self, a: Artifact) -> Artifact: ...
    def get(self, artifact_id: uuid.UUID) -> Artifact | None: ...
    def by_type(self, t: ArtifactType) -> list[Artifact]: ...


def _row_to_artifact(row: dict) -> Artifact:
    return Artifact(
        artifact_id=row["artifact_id"],
        artifact_type=ArtifactType(row["artifact_type"]),
        source_system=SourceSystem(row["source_system"]),
        actor=row["actor"],
        actor_kind=ActorKind(row["actor_kind"]),
        timestamp_start=row["timestamp_start"],
        timestamp_end=row["timestamp_end"],
        input_refs=list(row["input_refs"]),
        output_refs=list(row["output_refs"]),
        permissions_label=row["permissions_label"],
        objective_tag=row["objective_tag"],
        ground_truth_ref=row["ground_truth_ref"],
        eval_score=float(row["eval_score"]) if row["eval_score"] is not None else None,
        rollback_ref=row["rollback_ref"],
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        corrects_ref=row["corrects_ref"],
        payload=row["payload"],
    )


class PostgresArtifactStore:
    """Append-only artifact store. INSERT + SELECT only — there is no update path (corrections are
    new rows linked by corrects_ref; the DB trigger blocks UPDATE/DELETE regardless)."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def append(self, a: Artifact) -> Artifact:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                f"INSERT INTO artifacts ({','.join(_COLS)}) VALUES ({','.join(['%s'] * len(_COLS))})",
                (
                    a.artifact_id, a.artifact_type.value, a.source_system.value, a.actor,
                    a.actor_kind.value, a.timestamp_start, a.timestamp_end, a.input_refs,
                    a.output_refs, a.permissions_label, a.objective_tag, a.ground_truth_ref,
                    a.eval_score,
                    Jsonb(a.rollback_ref) if a.rollback_ref is not None else None,
                    a.cost_usd, a.corrects_ref, Jsonb(a.payload),
                ),
            )
            conn.commit()
        return a

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id=%s", (artifact_id,)
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def by_type(self, t: ArtifactType) -> list[Artifact]:
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_type=%s ORDER BY timestamp_start", (t.value,)
            ).fetchall()
        return [_row_to_artifact(r) for r in rows]
