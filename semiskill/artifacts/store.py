from __future__ import annotations
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
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


@dataclass(frozen=True, slots=True)
class PublicationProjectionRow:
    approval_id: uuid.UUID
    skill_version_id: uuid.UUID
    automated_review_id: uuid.UUID
    content_review_id: uuid.UUID
    corrects_ref: uuid.UUID | None
    decision: Literal["approve", "unpublish"]
    slug: str
    version: str
    payload_sha256: str
    permissions_label: str
    environment: Literal["development", "test", "production"]
    policy_version: str
    approve_threshold: Decimal
    chain_sha256: str
    activated_at: datetime
    activated_by: str


@dataclass(frozen=True, slots=True)
class PublicationReconciliationBundle:
    artifacts: tuple[Artifact, ...]
    projections: tuple[PublicationProjectionRow, ...]


class ArtifactStore(Protocol):
    def append(self, a: Artifact) -> Artifact: ...
    def append_approval(self, a: Artifact) -> Artifact: ...
    def activate_approval(self, approval_id: uuid.UUID) -> uuid.UUID: ...
    def append_many(self, artifacts: list[Artifact]) -> list[Artifact]: ...
    def get(self, artifact_id: uuid.UUID) -> Artifact | None: ...
    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]: ...
    def by_type(self, t: ArtifactType) -> list[Artifact]: ...
    def verified_publication_ids(self) -> set[uuid.UUID]: ...
    def publication_reconciliation_bundle(self) -> PublicationReconciliationBundle: ...
    def publication_registry_entry(self, slug: str) -> dict | None: ...


class ReconciledArtifactStore:
    """Immutable read view used so one decision never spans multiple database snapshots."""

    def __init__(self, bundle: PublicationReconciliationBundle):
        if not isinstance(bundle, PublicationReconciliationBundle):
            raise ValueError("publication reconciliation bundle has the wrong type")
        rows = tuple(bundle.artifacts)
        projections = tuple(bundle.projections)
        if any(not isinstance(row, Artifact) for row in rows):
            raise ValueError("publication reconciliation bundle has a malformed artifact row")
        if any(not isinstance(row, PublicationProjectionRow) for row in projections):
            raise ValueError("publication reconciliation bundle has a malformed projection row")
        by_id = {row.artifact_id: row for row in rows}
        projection_ids = {row.approval_id for row in projections}
        if len(by_id) != len(rows):
            raise ValueError("publication reconciliation bundle has duplicate artifact IDs")
        if len(projection_ids) != len(projections):
            raise ValueError("publication reconciliation bundle has duplicate projection IDs")
        self._rows = rows
        self._by_id = by_id
        self._projections = projections
        self._projected_ids = frozenset(projection_ids)

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        return self._by_id.get(artifact_id)

    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]:
        return [self._by_id[artifact_id] for artifact_id in artifact_ids if artifact_id in self._by_id]

    def by_type(self, t: ArtifactType) -> list[Artifact]:
        return [row for row in self._rows if row.artifact_type is t]

    def verified_publication_ids(self) -> set[uuid.UUID]:
        return set(self._projected_ids)

    def publication_projections(self) -> tuple[PublicationProjectionRow, ...]:
        return self._projections


def _insert_values(a: Artifact) -> tuple:
    return (
        a.artifact_id, a.artifact_type.value, a.source_system.value, a.actor,
        a.actor_kind.value, a.timestamp_start, a.timestamp_end, a.input_refs,
        a.output_refs, a.permissions_label, a.objective_tag, a.ground_truth_ref,
        a.eval_score,
        Jsonb(a.rollback_ref) if a.rollback_ref is not None else None,
        a.cost_usd, a.corrects_ref, Jsonb(a.payload),
    )


def _approval_values(a: Artifact) -> tuple:
    """Arguments for the role-scoped approval append function (artifact_type is hard-coded there)."""
    return (
        a.artifact_id, a.source_system.value, a.actor, a.actor_kind.value,
        a.timestamp_start, a.timestamp_end, a.input_refs, a.output_refs,
        a.permissions_label, a.objective_tag, a.ground_truth_ref, a.eval_score,
        Jsonb(a.rollback_ref) if a.rollback_ref is not None else None,
        a.cost_usd, a.corrects_ref, Jsonb(a.payload),
    )


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


def _row_to_projection(row: dict) -> PublicationProjectionRow:
    return PublicationProjectionRow(
        approval_id=row["approval_id"],
        skill_version_id=row["skill_version_id"],
        automated_review_id=row["automated_review_id"],
        content_review_id=row["content_review_id"],
        corrects_ref=row["corrects_ref"],
        decision=row["decision"],
        slug=row["slug"],
        version=row["version"],
        payload_sha256=row["payload_sha256"],
        permissions_label=row["permissions_label"],
        environment=row["environment"],
        policy_version=row["policy_version"],
        approve_threshold=row["approve_threshold"],
        chain_sha256=row["chain_sha256"],
        activated_at=row["activated_at"],
        activated_by=row["activated_by"],
    )


class PostgresArtifactStore:
    """Append-only artifact store. INSERT + SELECT only — there is no update path (corrections are
    new rows linked by corrects_ref; the DB trigger blocks UPDATE/DELETE regardless)."""

    def __init__(self, dsn: str, *, approval_dsn: str | None = None):
        self._dsn = dsn
        configured_approval_dsn = approval_dsn or os.environ.get(
            "SEMISKILL_APPROVAL_DATABASE_URL"
        )
        runtime_info = psycopg.conninfo.conninfo_to_dict(dsn)
        database_name = runtime_info.get("dbname", "")
        if configured_approval_dsn and not database_name.lower().endswith("_test"):
            approval_info = psycopg.conninfo.conninfo_to_dict(configured_approval_dsn)
            if approval_info.get("dbname") != database_name:
                raise ValueError("approval actuator must target the catalog database")
            runtime_user = runtime_info.get("user")
            approval_user = approval_info.get("user")
            if not runtime_user or not approval_user or runtime_user == approval_user:
                raise ValueError("approval actuator requires a distinct database identity")
        self._approval_dsn = configured_approval_dsn or (
            dsn if database_name.lower().endswith("_test") else None
        )

    def database_identity(self, *, environment: str) -> dict:
        """Return a stable non-secret identity for scoreboard provenance."""
        info = psycopg.conninfo.conninfo_to_dict(self._dsn)
        safe = {
            "engine": "postgresql",
            "environment": environment,
            "database_name": info.get("dbname") or "",
            "host": info.get("host") or "",
            "port": str(info.get("port") or "5432"),
        }
        digest_input = json.dumps(safe, sort_keys=True, separators=(",", ":")).encode("utf-8")
        safe["identity_sha256"] = "sha256:" + hashlib.sha256(digest_input).hexdigest()
        return safe

    def append(self, a: Artifact) -> Artifact:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                f"INSERT INTO artifacts ({','.join(_COLS)}) VALUES ({','.join(['%s'] * len(_COLS))})",
                _insert_values(a),
            )
            conn.commit()
        return a

    def append_approval(self, a: Artifact) -> Artifact:
        """Atomically append a human decision and activate only publishing corrections.

        Reject decisions remain immutable audit artifacts but cannot affect catalog visibility.
        Approve/unpublish decisions commit only if the role-scoped database actuator accepts the
        exact chain and writes its append-only verified projection in the same transaction.
        """
        if a.artifact_type is not ArtifactType.APPROVAL:
            raise ValueError("append_approval requires an approval artifact")
        if self._approval_dsn is None:
            raise RuntimeError("dedicated approval actuator database identity is not configured")
        with psycopg.connect(self._approval_dsn) as conn:
            appended = conn.execute(
                "SELECT append_verified_approval(" + ",".join(["%s"] * 16) + ")",
                _approval_values(a),
            ).fetchone()
            if appended is None or not isinstance(appended[0], uuid.UUID):
                raise RuntimeError("verified approval actuator did not confirm the append")
            conn.commit()
        if appended[0] == a.artifact_id:
            return a
        existing = self.get(appended[0])
        if existing is None or existing.artifact_type is not ArtifactType.APPROVAL:
            raise RuntimeError("verified approval actuator returned an unknown idempotent decision")
        return existing

    def activate_approval(self, approval_id: uuid.UUID) -> uuid.UUID:
        """Activate an imported exact approval through the same role-scoped deterministic gate."""
        if self._approval_dsn is None:
            raise RuntimeError("dedicated approval actuator database identity is not configured")
        with psycopg.connect(self._approval_dsn) as conn:
            row = conn.execute(
                "SELECT activate_verified_publication(%s)", (approval_id,),
            ).fetchone()
            if row is None or row[0] != approval_id:
                raise RuntimeError("verified publication actuator did not confirm the approval")
            conn.commit()
        return approval_id

    def append_many(self, artifacts: list[Artifact]) -> list[Artifact]:
        """Append a collector batch in one transaction or append none of it.

        Validation belongs before this boundary, but database constraints still can reject an
        insert.  The connection context rolls the entire transaction back if any row fails.
        """
        rows = list(artifacts)
        if not rows:
            return []
        statement = (
            f"INSERT INTO artifacts ({','.join(_COLS)}) "
            f"VALUES ({','.join(['%s'] * len(_COLS))})"
        )
        with psycopg.connect(self._dsn) as conn:
            for artifact in rows:
                conn.execute(statement, _insert_values(artifact))
            conn.commit()
        return rows

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id=%s", (artifact_id,)
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]:
        ids = list(dict.fromkeys(artifact_ids))
        if not ids:
            return []
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ANY(%s)", (ids,),
            ).fetchall()
        by_id = {row["artifact_id"]: _row_to_artifact(row) for row in rows}
        return [by_id[artifact_id] for artifact_id in ids if artifact_id in by_id]

    def by_type(self, t: ArtifactType) -> list[Artifact]:
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_type=%s ORDER BY timestamp_start", (t.value,)
            ).fetchall()
        return [_row_to_artifact(r) for r in rows]

    def verified_publication_ids(self) -> set[uuid.UUID]:
        """Return actuator-projected decisions; raw approval JSON never enters this set."""
        with psycopg.connect(self._dsn) as conn:
            rows = conn.execute(
                "SELECT approval_id FROM verified_publication_events"
            ).fetchall()
        return {row[0] for row in rows}

    def publication_reconciliation_bundle(self) -> PublicationReconciliationBundle:
        """Read evidence and actuator state from one repeatable-read transaction."""
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_type IN "
                "('skill_version','scan_run','injection_test','review','approval') "
                "ORDER BY timestamp_start, artifact_id"
            ).fetchall()
            projected = conn.execute(
                "SELECT approval_id,skill_version_id,automated_review_id,content_review_id,"
                "corrects_ref,decision,slug,version,payload_sha256,permissions_label,"
                "environment,policy_version,approve_threshold,chain_sha256,activated_at,"
                "activated_by FROM verified_publication_events ORDER BY activated_at,approval_id"
            ).fetchall()
        return PublicationReconciliationBundle(
            artifacts=tuple(_row_to_artifact(row) for row in rows),
            projections=tuple(_row_to_projection(row) for row in projected),
        )

    def publication_registry_entry(self, slug: str) -> dict | None:
        """Read the actuator's immutable current-phase publication allowlist."""
        with psycopg.connect(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(
                "SELECT slug,role,level,permissions_label,active,judge_required,registry_sha256 "
                "FROM publication_registry_entry_v1(%s)",
                (slug,),
            ).fetchone()
        return dict(row) if row is not None else None
